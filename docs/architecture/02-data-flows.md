# Core Data Flows

This document describes the detailed sequence diagrams for key user journeys in Colink.

---

## 1. User Sign-In with 2FA

```mermaid
sequenceDiagram
    participant U as User
    participant G as Gateway
    participant A as Auth Proxy
    participant K as Keycloak
    participant P as Postgres
    participant Kafka as Kafka

    U->>G: POST /auth/login<br/>{username, password}
    G->>A: Forward request
    A->>K: OIDC token request<br/>(password grant)
    K->>K: Validate credentials
    K-->>A: 401 + require_2fa challenge
    A-->>U: 401 Requires 2FA<br/>{challengeId, methods: [totp, webauthn]}

    Note over U: User enters TOTP code<br/>from authenticator app

    U->>G: POST /auth/login/verify<br/>{challengeId, method: totp, code: 123456}
    G->>A: Forward with challenge session
    A->>K: Complete 2FA flow
    K->>K: Validate TOTP code
    K-->>A: 200 + access_token + refresh_token
    A->>P: UPDATE sessions<br/>SET last_login = NOW()
    A->>Kafka: Publish user.logged_in event
    A-->>G: 200 + tokens + user profile
    G-->>U: 200 + tokens + user profile
```

**Key Points**:
- 2FA is mandatory (enforced by Keycloak authentication flow)
- Challenge session stored in Keycloak (stateless for auth-proxy)
- Tokens cached in Redis (1-hour TTL for JWKS)
- Audit event published to Kafka

---

## 2. Send Direct Message (DM)

```mermaid
sequenceDiagram
    participant U as User
    participant G as Gateway
    participant M as Messaging Service
    participant P as Postgres
    participant K as Kafka
    participant R as Redis
    participant RT as Realtime Gateway
    participant U2 as Recipient

    U->>G: POST /v1/messages<br/>{recipientId, text, idempotencyKey}
    G->>M: Forward with JWT
    M->>M: Validate JWT<br/>Extract user_id
    M->>M: Check idempotency<br/>(Redis key exists?)
    M->>P: Check if users can DM<br/>(not blocked, both active)
    M->>P: BEGIN TRANSACTION
    M->>P: INSERT INTO messages<br/>(sender_id, recipient_id, text)
    M->>P: COMMIT
    M->>K: Publish message.created event<br/>(key=dm_id, idempotencyKey)
    M->>R: SET idempotency:{key}<br/>(24h TTL)
    M->>R: PUBLISH realtime:dm:{dm_id}<br/>(fan-out to Redis subscribers)
    M-->>G: 201 + message object
    G-->>U: 201 + message object

    RT->>R: SUBSCRIBE realtime:dm:{dm_id}
    R-->>RT: New message event
    RT->>RT: Lookup recipient WebSocket<br/>(ws:user:{recipient_id}:conns)
    RT->>U2: WebSocket SEND<br/>{type: message.new, data: {...}}

    Note over K: Search service consumes<br/>message.created event,<br/>indexes in OpenSearch
```

**Key Points**:
- Idempotency key prevents duplicate sends (network retries)
- Kafka event ensures eventual consistency (search index updated async)
- Redis pub/sub provides low-latency real-time delivery
- WebSocket connection mapping stored in Redis

---

## 3. Create Channel & Post Message

```mermaid
sequenceDiagram
    participant U as User
    participant Ch as Channels Service
    participant M as Messaging Service
    participant P as Postgres
    participant K as Kafka
    participant RT as Realtime Gateway
    participant U2 as Channel Members

    U->>Ch: POST /v1/channels<br/>{name, displayName, isPrivate, idempotencyKey}
    Ch->>Ch: Validate JWT<br/>Extract user_id
    Ch->>P: BEGIN TRANSACTION
    Ch->>P: INSERT INTO channels<br/>(name, created_by, is_private)
    Ch->>P: INSERT INTO channel_members<br/>(channel_id, user_id, role=owner)
    Ch->>P: COMMIT
    Ch->>K: Publish channel.created event
    Ch-->>U: 201 + channel object

    Note over U: User posts first message

    U->>M: POST /v1/messages<br/>{channelId, text, idempotencyKey}
    M->>M: Validate JWT
    M->>P: SELECT FROM channel_members<br/>WHERE channel_id AND user_id<br/>(verify membership)
    alt Not a member
        M-->>U: 403 Forbidden
    end
    M->>P: INSERT INTO messages<br/>(sender_id, channel_id, text)
    M->>K: Publish message.created event<br/>(key=channel_id)
    M-->>U: 201 + message object

    RT->>K: Consume message.created event
    RT->>P: SELECT user_id FROM channel_members<br/>WHERE channel_id<br/>(get all members)
    RT->>R: For each member:<br/>GET ws:user:{user_id}:conns
    RT->>U2: WebSocket SEND to all<br/>online members<br/>{type: message.new, data: {...}}
```

**Key Points**:
- Channel creation is atomic (channel + membership in single transaction)
- Channel messages require membership check before insert
- Fan-out logic: Realtime gateway fetches all channel members, sends to each WebSocket connection
- Offline members see message on next login (query `/v1/messages?channelId=...`)

---

## 4. Upload File & Attach to Message

```mermaid
sequenceDiagram
    participant U as User
    participant F as Files Service
    participant S3 as MinIO
    participant AV as ClamAV
    participant P as Postgres
    participant K as Kafka
    participant M as Messaging Service

    U->>F: POST /v1/files/upload-url<br/>{filename, size, mimeType, idempotencyKey}
    F->>F: Validate size (<100MB)<br/>Validate MIME (whitelist)
    F->>F: Generate file_id (ULID)<br/>Generate object_key
    F->>S3: Generate presigned PUT URL<br/>(5-minute TTL)
    F->>P: INSERT INTO files<br/>(id, filename, size, status=pending_upload)
    F-->>U: 200 {presignedUrl, fileId, expiresIn: 300}

    U->>S3: PUT to presigned URL<br/>(binary file data)
    S3-->>U: 200 OK

    U->>F: POST /v1/files/{fileId}/confirm
    F->>S3: HEAD object<br/>(verify object exists)
    alt Object not found
        F-->>U: 404 File not uploaded
    end
    F->>P: UPDATE files<br/>SET status=scanning
    F->>AV: POST /scan<br/>{objectKey}
    AV-->>F: 202 Accepted<br/>(async scan)
    F-->>U: 200 {file metadata, status: scanning}

    Note over AV: ClamAV scans file

    AV->>F: POST /files/{fileId}/scan-result<br/>{status: clean}
    F->>P: UPDATE files<br/>SET status=scanned, scanned_at=NOW()
    F->>K: Publish file.scanned event
    F-->>AV: 200 OK

    Note over U: User attaches file to message

    U->>M: POST /v1/messages<br/>{channelId, text, fileIds: [fileId]}
    M->>P: SELECT FROM files<br/>WHERE id IN (fileIds)<br/>AND uploaded_by = user_id<br/>AND status = scanned
    alt File not scanned or not owned
        M-->>U: 403 Forbidden
    end
    M->>P: BEGIN TRANSACTION
    M->>P: INSERT INTO messages
    M->>P: INSERT INTO message_files<br/>(message_id, file_id)
    M->>P: COMMIT
    M->>K: Publish message.created event<br/>(includes file_ids)
    M-->>U: 201 + message object
```

**Key Points**:
- Presigned URL offloads upload traffic from application servers
- Two-step upload: (1) presigned URL, (2) confirm after upload
- Virus scanning is asynchronous (callback from ClamAV)
- Files can only be attached by uploader and after scan completes

---

## 5. Search Messages

```mermaid
sequenceDiagram
    participant U as User
    participant S as Search Service
    participant OS as OpenSearch
    participant P as Postgres

    U->>S: GET /v1/search/messages?<br/>q=urgent&channelId=123&limit=20
    S->>S: Validate JWT<br/>Extract user_id
    S->>P: SELECT channel_id FROM channel_members<br/>WHERE user_id<br/>(get user's accessible channels)
    S->>OS: Query:<br/>match: {text: "urgent"}<br/>term: {channel_id: 123, is_deleted: false}<br/>filter: {channel_id IN accessible_channels}
    OS-->>S: Hits with highlights<br/>[{message_id, text, score, highlights}]
    S->>S: Filter deleted messages<br/>(double-check against Postgres)
    S->>P: SELECT metadata FROM messages<br/>WHERE id IN (hit_ids)<br/>(hydrate sender info)
    S-->>U: 200 {data: [{id, text, highlights, sender}], total}
```

**Key Points**:
- Search respects channel membership (user can only search channels they're in)
- Deleted messages excluded via OpenSearch filter + Postgres double-check
- Highlights show matched terms in context (`<em>` tags)
- Eventual consistency: newly created messages may take 5-10s to appear in search

---

## 6. Presence Update & Typing Indicators

### Presence Update

```mermaid
sequenceDiagram
    participant U as User
    participant Pr as Presence Service
    participant R as Redis
    participant K as Kafka
    participant RT as Realtime Gateway
    participant U2 as Other Users

    U->>Pr: POST /v1/presence<br/>{status: online, customStatus: "In a meeting"}
    Pr->>Pr: Validate JWT
    Pr->>R: SETEX presence:user:{user_id}<br/>value={status, customStatus}<br/>TTL=60s
    Pr->>K: Publish presence.updated event
    Pr-->>U: 200 OK

    RT->>K: Consume presence.updated event
    RT->>RT: Determine subscribers<br/>(users in same channels)
    RT->>U2: WebSocket SEND<br/>{type: presence.update, userId, status}

    Note over U: Client heartbeat every 30s<br/>to keep presence alive
```

### Typing Indicator

```mermaid
sequenceDiagram
    participant U as User
    participant Pr as Presence Service
    participant R as Redis
    participant K as Kafka
    participant RT as Realtime Gateway
    participant U2 as Channel Members

    U->>Pr: POST /v1/presence/typing<br/>{channelId}
    Pr->>Pr: Validate JWT<br/>Verify channel membership
    Pr->>R: SETEX typing:{channel_id}:{user_id}<br/>value={username}<br/>TTL=5s
    Pr->>K: Publish typing.started event<br/>(key=channel_id)
    Pr-->>U: 204 No Content

    RT->>K: Consume typing.started event
    RT->>RT: Get channel subscribers
    RT->>U2: WebSocket SEND<br/>{type: typing.start, channelId, userId, username}

    Note over U: If user stops typing,<br/>Redis key expires after 5s

    Note over RT: On key expiry,<br/>publish typing.stopped event
```

**Key Points**:
- Presence stored in Redis with TTL (60s for status, 5s for typing)
- Client must heartbeat to maintain "online" status
- Typing indicators are ephemeral (auto-expire if no activity)
- Events fan out only to relevant users (same channels)

---

## 7. React with Emoji

```mermaid
sequenceDiagram
    participant U as User
    participant Re as Reactions Service
    participant P as Postgres
    participant K as Kafka
    participant R as Redis
    participant RT as Realtime Gateway
    participant U2 as Viewers

    U->>Re: POST /v1/messages/{messageId}/reactions<br/>{emoji: "👍", idempotencyKey}
    Re->>Re: Validate JWT<br/>Validate emoji format
    Re->>P: INSERT INTO reactions<br/>(message_id, user_id, emoji)<br/>ON CONFLICT (message_id, user_id, emoji) DO NOTHING
    alt Already reacted
        Re-->>U: 409 Conflict
    end
    Re->>K: Publish reaction.added event<br/>(key=message_id, idempotent)
    Re->>R: INCR message:{message_id}:reactions:{emoji}
    Re->>R: SET idempotency:{key} (24h TTL)
    Re-->>U: 201 + reaction object

    RT->>K: Consume reaction.added event
    RT->>RT: Determine message viewers<br/>(channel members or DM participants)
    RT->>U2: WebSocket SEND<br/>{type: reaction.added, messageId, userId, emoji}
```

**Key Points**:
- Duplicate reactions prevented by unique constraint (message_id, user_id, emoji)
- Redis counter caches reaction counts (invalidated on removal)
- Real-time updates show reactions immediately to all viewers

---

## 8. Threaded Reply

```mermaid
sequenceDiagram
    participant U as User
    participant T as Threads Service
    participant M as Messaging Service
    participant P as Postgres
    participant K as Kafka

    U->>T: POST /v1/threads<br/>{parentMessageId, text, idempotencyKey}
    T->>T: Validate JWT
    T->>P: SELECT FROM messages<br/>WHERE id = parentMessageId<br/>(verify parent exists)
    alt Parent not found
        T-->>U: 404 Parent message not found
    end
    T->>P: BEGIN TRANSACTION
    T->>P: INSERT INTO threads<br/>(parent_message_id)<br/>ON CONFLICT (parent_message_id) DO NOTHING<br/>RETURNING id
    T->>M: Internal call:<br/>POST /internal/messages<br/>{threadId, senderId, text}
    M->>P: INSERT INTO messages<br/>(sender_id, thread_id, text)
    T->>P: UPDATE threads<br/>SET reply_count = reply_count + 1,<br/>last_reply_at = NOW()
    T->>P: COMMIT
    T->>K: Publish thread.created event<br/>(if new thread)
    T->>K: Publish reply.created event
    T-->>U: 201 {thread, reply}
```

**Key Points**:
- Thread created atomically with first reply
- Subsequent replies increment `reply_count`
- Thread ID links replies to parent message
- Real-time updates notify thread subscribers

---

## 9. Admin Moderation (Delete Message)

```mermaid
sequenceDiagram
    participant A as Admin
    participant Ad as Admin Service
    participant M as Messaging Service
    participant P as Postgres
    participant K as Kafka
    participant OS as OpenSearch

    A->>Ad: POST /v1/admin/messages/{messageId}/moderate<br/>{action: delete, reason: "spam"}
    Ad->>Ad: Validate JWT<br/>Check admin role
    alt Not admin
        Ad-->>A: 403 Forbidden
    end
    Ad->>P: BEGIN TRANSACTION
    Ad->>P: UPDATE messages<br/>SET is_deleted=true,<br/>deleted_at=NOW()
    Ad->>P: INSERT INTO audit_logs<br/>(actor_id, action, target_id, metadata)
    Ad->>P: COMMIT
    Ad->>K: Publish message.moderated event<br/>{messageId, action, reason, actorId}
    Ad-->>A: 200 OK

    Note over K: Search service consumes event

    OS->>K: Consume message.moderated
    OS->>OS: DELETE FROM messages index<br/>WHERE message_id
    OS->>OS: OR UPDATE is_deleted=true
```

**Key Points**:
- Soft delete (message not physically removed, just flagged)
- Audit log records who performed moderation and why
- Search index updated to exclude deleted message
- Real-time gateway can push deletion event to connected clients (optional)

---

## Data Flow Summary

| Journey | Services Involved | Data Stores | Events Published |
|---------|------------------|-------------|------------------|
| **Sign-In with 2FA** | Auth Proxy, Keycloak | Postgres (sessions) | `user.logged_in` |
| **Send DM** | Messaging | Postgres, Redis, Kafka | `message.created` |
| **Create Channel** | Channels | Postgres, Kafka | `channel.created` |
| **Post Message** | Messaging | Postgres, Redis, Kafka | `message.created` |
| **Upload File** | Files, ClamAV | Postgres, MinIO, Kafka | `file.uploaded`, `file.scanned` |
| **Search Messages** | Search | OpenSearch, Postgres | - (consumer only) |
| **Update Presence** | Presence | Redis, Kafka | `presence.updated` |
| **Typing Indicator** | Presence | Redis, Kafka | `typing.started` |
| **React with Emoji** | Reactions | Postgres, Redis, Kafka | `reaction.added` |
| **Threaded Reply** | Threads, Messaging | Postgres, Kafka | `thread.created`, `reply.created` |
| **Admin Moderate** | Admin, Messaging | Postgres, Kafka | `message.moderated` |

---

## Next Steps

1. **Review Service Contracts**: [05-service-inventory.md](./05-service-inventory.md)
2. **Study Security Model**: [03-security-model.md](./03-security-model.md)
3. **Explore API Specs**: [../api-specs/](../api-specs/)
