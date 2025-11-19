# Service Inventory

## Overview

This document provides a comprehensive catalog of all microservices in the Colink platform, their responsibilities, dependencies, and API contracts.

---

## Service Summary Table

| Service | Port | Language | Responsibilities | DB Access | Cache | Kafka Producer | Kafka Consumer |
|---------|------|----------|-----------------|-----------|-------|----------------|----------------|
| **api-gateway** | 80/443 | Traefik | Routing, TLS, rate limiting | - | Redis (rate limit) | - | - |
| **auth-proxy** | 8001 | Python/FastAPI | Authentication, JWT validation | Postgres (sessions) | Redis (JWKS) | user.events | - |
| **users-service** | 8002 | Python/FastAPI | User profiles, settings | Postgres (users) | Redis (user cache) | user.events | - |
| **channels-service** | 8003 | Python/FastAPI | Channel CRUD, membership | Postgres (channels) | Redis (channel cache) | channel.events | - |
| **messaging-service** | 8004 | Python/FastAPI | Messages, DMs | Postgres (messages) | Redis (unread counts) | message.events | user.deactivated |
| **threads-service** | 8005 | Python/FastAPI | Thread replies | Postgres (threads) | - | thread.events | message.deleted |
| **reactions-service** | 8006 | Python/FastAPI | Emoji reactions | Postgres (reactions) | Redis (reaction counts) | reaction.events | message.deleted |
| **presence-service** | 8007 | Python/FastAPI | Online status, typing | - | Redis (TTL state) | presence.events | - |
| **files-service** | 8008 | Python/FastAPI | File upload/download | Postgres (file metadata) | Redis (file cache) | file.events | - |
| **search-service** | 8009 | Python/FastAPI | Full-text search | OpenSearch only | Redis (recent queries) | - | All events (indexing) |
| **admin-service** | 8010 | Python/FastAPI | Moderation, audit | Postgres (audit_logs) | - | audit.events | - |
| **realtime-gateway** | 8011 | Python/FastAPI | WebSocket connections | - | Redis (conn mapping) | - | All real-time events |

---

## Detailed Service Descriptions

### 1. API Gateway (Traefik)

**Purpose**: Edge routing and security enforcement

**Technology**: Traefik 3.x (Go-based reverse proxy)

**Responsibilities**:
- HTTP/HTTPS request routing to backend services
- WebSocket upgrade handling (`/ws` → realtime-gateway)
- TLS termination (Let's Encrypt + manual certs)
- Rate limiting (IP-based: 100 req/min, burst 200)
- CORS policy enforcement
- Access logging with request tracing

**Configuration** (dynamic via Docker labels or Kubernetes ingress):
```yaml
http:
  routers:
    auth-router:
      rule: "PathPrefix(`/auth`)"
      service: auth-proxy
      middlewares:
        - rate-limit-auth
        - cors

    api-router:
      rule: "PathPrefix(`/v1`)"
      service: dynamic-backend
      middlewares:
        - rate-limit-global
        - cors

    ws-router:
      rule: "Path(`/ws`)"
      service: realtime-gateway

  middlewares:
    rate-limit-global:
      rateLimit:
        average: 100
        burst: 200
        period: 1m

    cors:
      headers:
        accessControlAllowOrigins:
          - "https://colink.dev"
          - "http://localhost:3000"
        accessControlAllowMethods:
          - "GET"
          - "POST"
          - "PUT"
          - "PATCH"
          - "DELETE"
        accessControlAllowHeaders:
          - "Authorization"
          - "Content-Type"
          - "Idempotency-Key"
```

**Health Check**: `/ping` (always returns 200 OK)

**Scaling**: Active-active with DNS round-robin or L4 load balancer

---

### 2. Auth Proxy

**Purpose**: Authentication and token management

**Port**: 8001

**Endpoints**:
- `POST /auth/login` - Initiate login (username/password)
- `POST /auth/login/verify` - Complete 2FA verification
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Revoke tokens
- `POST /auth/introspect` - Validate token (internal)

**Dependencies**:
- **Keycloak**: OIDC token endpoint, user authentication
- **Postgres**: `sessions` table (refresh token storage)
- **Redis**: JWKS cache (1-hour TTL)

**Kafka Topics Produced**:
- `user.events`: `user.logged_in`, `user.logged_out`

**Key Business Logic**:
- Proxy to Keycloak for password + 2FA flow
- Store refresh tokens in Postgres (hashed with SHA-256)
- Cache Keycloak JWKS for local JWT validation
- Generate trace IDs for request correlation

**Environment Variables**:
```bash
KEYCLOAK_URL=https://keycloak.colink.dev
KEYCLOAK_REALM=colink
KEYCLOAK_CLIENT_ID=web-app
KEYCLOAK_CLIENT_SECRET=<secret>
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
KAFKA_BROKERS=kafka:9092
```

**Scaling**: Stateless, horizontal scaling behind load balancer

---

### 3. Users Service

**Purpose**: User profile and settings management

**Port**: 8002

**Endpoints**:
- `GET /v1/users/me` - Get current user profile
- `PATCH /v1/users/me` - Update current user profile
- `GET /v1/users/{userId}` - Get user by ID
- `GET /v1/users` - List/search users
- `GET /v1/users/me/settings` - Get user settings
- `PATCH /v1/users/me/settings` - Update user settings
- `POST /v1/users/{userId}/avatar` - Upload avatar (presigned URL)

**Dependencies**:
- **Postgres**: `users`, `user_settings` tables
- **Redis**: User cache (`user:{id}`, 5-min TTL)
- **Kafka**: Event publishing

**Kafka Topics Produced**:
- `user.events`: `user.created`, `user.updated`, `user.deactivated`

**Key Business Logic**:
- User profile CRUD with optimistic concurrency (ETags)
- Avatar upload via presigned URLs (MinIO)
- User search with fuzzy matching (pg_trgm)
- Settings stored as JSONB in Postgres

**Database Schema**:
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(30) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    avatar_url TEXT,
    title VARCHAR(100),
    timezone VARCHAR(50) DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    notifications JSONB DEFAULT '{"desktop": true, "email": true, "sound": true}',
    theme VARCHAR(10) DEFAULT 'auto' CHECK (theme IN ('light', 'dark', 'auto')),
    language VARCHAR(10) DEFAULT 'en-US'
);
```

---

### 4. Channels Service

**Purpose**: Channel and membership management

**Port**: 8003

**Endpoints**:
- `GET /v1/channels` - List user's channels
- `POST /v1/channels` - Create channel
- `GET /v1/channels/{channelId}` - Get channel details
- `PATCH /v1/channels/{channelId}` - Update channel (owner/admin)
- `GET /v1/channels/{channelId}/members` - List members
- `POST /v1/channels/{channelId}/members` - Add member
- `DELETE /v1/channels/{channelId}/members/{userId}` - Remove member

**Dependencies**:
- **Postgres**: `channels`, `channel_members` tables
- **Redis**: Channel cache (`channel:{id}`, `channel:members:{id}`)
- **Kafka**: Event publishing

**Kafka Topics Produced**:
- `channel.events`: `channel.created`, `channel.updated`, `channel.archived`, `member.joined`, `member.left`

**Key Business Logic**:
- Channel name uniqueness (unique constraint)
- Role-based permissions (owner > admin > member)
- Public vs private channels (membership required for private)
- Archive instead of delete (soft delete pattern)

**Database Schema**:
```sql
CREATE TABLE channels (
    id UUID PRIMARY KEY,
    name VARCHAR(80) UNIQUE NOT NULL CHECK (name ~ '^[a-z0-9-]{1,80}$'),
    display_name VARCHAR(80) NOT NULL,
    description TEXT,
    is_private BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    archived_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE channel_members (
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (channel_id, user_id)
);
```

---

### 5. Messaging Service

**Purpose**: Message creation, retrieval, and management

**Port**: 8004

**Endpoints**:
- `GET /v1/messages` - List messages (channel or DM)
- `POST /v1/messages` - Send message
- `GET /v1/messages/{messageId}` - Get message by ID
- `PATCH /v1/messages/{messageId}` - Edit message (15-min window)
- `DELETE /v1/messages/{messageId}` - Delete message (soft delete)

**Dependencies**:
- **Postgres**: `messages`, `message_files` tables
- **Redis**: Unread counts cache (`dm:unread:{user_id}`)
- **Kafka**: Event publishing and consumption

**Kafka Topics Produced**:
- `message.events`: `message.created`, `message.updated`, `message.deleted`

**Kafka Topics Consumed**:
- `user.events`: `user.deactivated` (redact user's messages)

**Key Business Logic**:
- Channel messages require membership verification
- DMs require both users to be active (not blocked)
- Idempotency via `Idempotency-Key` header (24-hour window)
- Edit window: 15 minutes from creation
- Soft delete: `is_deleted` flag, `deleted_at` timestamp
- File attachments via `message_files` junction table

**Database Schema**:
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    sender_id UUID NOT NULL REFERENCES users(id),
    channel_id UUID REFERENCES channels(id) ON DELETE CASCADE,
    recipient_id UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
    text TEXT NOT NULL CHECK (LENGTH(text) <= 4000),
    is_edited BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT message_target_check CHECK (
        (channel_id IS NOT NULL AND recipient_id IS NULL) OR
        (channel_id IS NULL AND recipient_id IS NOT NULL)
    )
);

CREATE INDEX idx_messages_channel_id ON messages(channel_id) WHERE channel_id IS NOT NULL;
CREATE INDEX idx_messages_recipient_id ON messages(recipient_id) WHERE recipient_id IS NOT NULL;
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
```

---

### 6. Threads Service

**Purpose**: Threaded conversation management

**Port**: 8005

**Endpoints**:
- `POST /v1/threads` - Create thread or add reply
- `GET /v1/threads/{threadId}` - Get thread metadata
- `GET /v1/threads/{threadId}/replies` - List thread replies

**Dependencies**:
- **Postgres**: `threads` table, `messages` table (for replies)
- **Kafka**: Event publishing and consumption

**Kafka Topics Produced**:
- `thread.events`: `thread.created`, `reply.created`

**Kafka Topics Consumed**:
- `message.events`: `message.deleted` (cascade delete thread replies)

**Key Business Logic**:
- First reply creates thread (if not exists)
- Thread metadata: `reply_count`, `last_reply_at`
- Thread replies are messages with `thread_id` set
- Internal call to messaging service for reply creation

**Database Schema**:
```sql
CREATE TABLE threads (
    id UUID PRIMARY KEY,
    parent_message_id UUID NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
    reply_count INT DEFAULT 0,
    last_reply_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

### 7. Reactions Service

**Purpose**: Emoji reaction management

**Port**: 8006

**Endpoints**:
- `GET /v1/messages/{messageId}/reactions` - Get all reactions for message
- `POST /v1/messages/{messageId}/reactions` - Add reaction
- `DELETE /v1/messages/{messageId}/reactions/{emoji}` - Remove reaction

**Dependencies**:
- **Postgres**: `reactions` table
- **Redis**: Reaction counts cache (`message:{id}:reactions:{emoji}`)
- **Kafka**: Event publishing and consumption

**Kafka Topics Produced**:
- `reaction.events`: `reaction.added`, `reaction.removed`

**Kafka Topics Consumed**:
- `message.events`: `message.deleted` (cascade delete reactions)

**Key Business Logic**:
- One reaction per user per emoji per message (unique constraint)
- Emoji validation (Unicode emoji ranges)
- Aggregate reactions by emoji for display
- Cache invalidation on add/remove

**Database Schema**:
```sql
CREATE TABLE reactions (
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emoji VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (message_id, user_id, emoji)
);

CREATE INDEX idx_reactions_message_id ON reactions(message_id);
```

---

### 8. Presence Service

**Purpose**: User online status and typing indicators

**Port**: 8007

**Endpoints**:
- `POST /v1/presence` - Update user presence (online/away/dnd)
- `GET /v1/presence/users` - Get presence for multiple users
- `POST /v1/presence/typing` - Send typing indicator

**Dependencies**:
- **Redis**: Ephemeral state with TTL
  - `presence:user:{user_id}` (60s TTL)
  - `typing:{channel_id}:{user_id}` (5s TTL)
- **Kafka**: Event publishing

**Kafka Topics Produced**:
- `presence.events`: `presence.updated`, `typing.started`, `typing.stopped`

**Key Business Logic**:
- Presence stored only in Redis (no Postgres)
- Heartbeat required every 30s to maintain "online" status
- Typing indicator auto-expires after 5s
- Batch presence queries (multiple user IDs in single request)

**Redis Keys**:
```python
# Presence
SET presence:user:{user_id} '{"status": "online", "customStatus": "In a meeting"}' EX 60

# Typing
SETEX typing:{channel_id}:{user_id} 5 '{"username": "alice_smith"}'
```

---

### 9. Files Service

**Purpose**: File upload, download, and virus scanning

**Port**: 8008

**Endpoints**:
- `POST /v1/files/upload-url` - Request presigned upload URL
- `POST /v1/files/{fileId}/confirm` - Confirm upload and trigger scan
- `GET /v1/files/{fileId}` - Get file metadata
- `GET /v1/files/{fileId}/download-url` - Get presigned download URL
- `DELETE /v1/files/{fileId}` - Delete file

**Dependencies**:
- **Postgres**: `files` table
- **MinIO**: Object storage
- **ClamAV**: Virus scanning
- **Kafka**: Event publishing

**Kafka Topics Produced**:
- `file.events`: `file.uploaded`, `file.scanned`, `file.deleted`

**Key Business Logic**:
- Two-phase upload: (1) presigned URL, (2) confirm
- MIME type whitelist (images, PDFs, documents)
- Size limit: 100MB per file
- Virus scanning via ClamAV (async callback)
- Thumbnail generation for images (Kafka consumer)
- Presigned URL TTL: 5 minutes (upload), 1 hour (download)

**Database Schema**:
```sql
CREATE TABLE files (
    id UUID PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    size BIGINT NOT NULL CHECK (size > 0 AND size <= 104857600),
    mime_type VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending_upload' CHECK (
        status IN ('pending_upload', 'uploaded', 'scanning', 'scanned', 'infected', 'deleted')
    ),
    object_key VARCHAR(500) NOT NULL UNIQUE,
    thumbnail_url TEXT,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scanned_at TIMESTAMP WITH TIME ZONE
);
```

---

### 10. Search Service

**Purpose**: Full-text search across messages, files, and users

**Port**: 8009

**Endpoints**:
- `GET /v1/search/messages` - Search messages
- `GET /v1/search/files` - Search files by filename
- `GET /v1/search/users` - Search users by name/email

**Dependencies**:
- **OpenSearch**: Primary data store for indexed content
- **Postgres**: Hydrate metadata, verify access permissions
- **Redis**: Cache recent searches
- **Kafka**: Consume all events for indexing

**Kafka Topics Consumed**:
- All domain events (`message.events`, `user.events`, `file.events`, etc.)

**Key Business Logic**:
- Async indexing (5s delay or 100-doc batch)
- Channel membership enforced in queries
- Deleted messages excluded from results
- Highlighting with `<em>` tags
- Pagination via `offset` + `limit` (max 100 per page)

**OpenSearch Indices**:
- `messages`: Full-text on message text, filters on channel_id, sender_id, created_at
- `files`: Full-text on filename, filters on mime_type, uploaded_by
- `users`: Full-text on username, display_name, email

---

### 11. Admin Service

**Purpose**: Administrative operations and audit logging

**Port**: 8010

**Endpoints**:
- `POST /v1/admin/users/{userId}/deactivate` - Deactivate user (requires admin role)
- `POST /v1/admin/messages/{messageId}/moderate` - Moderate message (delete/flag)
- `GET /v1/admin/audit-logs` - Query audit logs (admin only)

**Dependencies**:
- **Postgres**: `audit_logs` table
- **Kafka**: Event publishing

**Kafka Topics Produced**:
- `audit.events`: `audit.log`
- `user.events`: `user.deactivated`
- `message.events`: `message.moderated`

**Key Business Logic**:
- RBAC: Requires `admin` or `moderator` role
- All actions logged to `audit_logs` table
- User deactivation triggers cascade (messages redacted, files deleted)
- Message moderation is soft delete with reason

**Database Schema**:
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    actor_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_actor_id ON audit_logs(actor_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
```

---

### 12. Realtime Gateway

**Purpose**: WebSocket connections and real-time event fan-out

**Port**: 8011

**Protocol**: WebSocket (`/ws`)

**Endpoints**:
- `WS /ws` - WebSocket upgrade (requires JWT in query param)

**Dependencies**:
- **Redis**: Connection mapping, pub/sub backplane
- **Kafka**: Consume all real-time events

**Kafka Topics Consumed**:
- All real-time events (`message.events`, `presence.events`, `reaction.events`, etc.)

**Key Business Logic**:
- JWT validation on WebSocket connect
- Connection tracking in Redis (`ws:user:{user_id}:conns`)
- Subscribe to Redis channels (`realtime:channel:{id}`, `realtime:dm:{id}`)
- Fan-out events to subscribed WebSocket connections
- Heartbeat: Ping every 30s, timeout after 60s

**Message Envelope**:
```json
{
  "type": "message.new",
  "channelId": "01HQZ01ABC2DEF3GHI4JKL5MNO",
  "data": {
    "id": "01HQZY9STUV1WXY2Z3A4B5C6D7",
    "senderId": "01HQZX8PQRS9TUV0WXY1Z2A3B4",
    "text": "Hello!",
    "createdAt": "2025-01-18T10:30:00Z"
  },
  "timestamp": "2025-01-18T10:30:00.123Z"
}
```

---

## Inter-Service Communication

### Synchronous (HTTP)

| Source | Target | Method | Purpose |
|--------|--------|--------|---------|
| API Gateway | All services | Proxy | Route requests based on path |
| Threads | Messaging | POST /internal/messages | Create thread reply message |

### Asynchronous (Kafka)

All services communicate via Kafka events for:
- Eventual consistency (search indexing)
- Decoupling (user deactivation → cascade effects)
- Audit trail (all events logged)

---

## Next Steps

1. **Review API Specifications**: [../api-specs/](../api-specs/)
2. **Study Event Contracts**: [../events/kafka-topics.md](../events/kafka-topics.md)
3. **Understand Data Model**: [../data-model/postgresql-schema.sql](../data-model/postgresql-schema.sql)
