# Colink Architecture Documentation

## 📋 Documentation Index

This is the **master index** for all Colink backend architecture documentation. All detailed specifications are in the [`/docs`](./docs/) folder.

---

## 🎯 Quick Start

1. **New to the project?** Start with:
   - [Executive Summary](./docs/architecture/00-executive-summary.md)
   - [System Architecture](./docs/architecture/01-system-architecture.md)

2. **Need to implement a feature?** Check:
   - [Service Inventory](./docs/architecture/05-service-inventory.md) - Find the right service
   - [Data Flows](./docs/architecture/02-data-flows.md) - See how features work end-to-end
   - [API Specs](./docs/api-specs/) - View OpenAPI contracts

3. **Security review?** See:
   - [Security Model](./docs/architecture/03-security-model.md)

4. **Scaling concerns?** Review:
   - [Scalability & Reliability](./docs/architecture/04-scalability-reliability.md)

---

## 📁 Documentation Structure

### Architecture Documentation

| Document | Description | Status |
|----------|-------------|--------|
| [00-executive-summary.md](./docs/architecture/00-executive-summary.md) | Technology stack, design decisions, trade-offs | ✅ Complete |
| [01-system-architecture.md](./docs/architecture/01-system-architecture.md) | C4 diagrams (Context & Container), deployment topology | ✅ Complete |
| [02-data-flows.md](./docs/architecture/02-data-flows.md) | Sequence diagrams for 9 core user journeys | ✅ Complete |
| [03-security-model.md](./docs/architecture/03-security-model.md) | Authentication, authorization, RBAC, secrets management | ✅ Complete |
| [04-scalability-reliability.md](./docs/architecture/04-scalability-reliability.md) | Scaling patterns, caching, retries, circuit breakers | ✅ Complete |
| [05-service-inventory.md](./docs/architecture/05-service-inventory.md) | Detailed catalog of all 12 services | ✅ Complete |
| 06-realtime-transport.md | WebSocket architecture, pub/sub, fan-out | 📝 Planned |
| 07-search.md | OpenSearch indexing, mappings, queries | 📝 Planned |
| 08-file-handling.md | Presigned URLs, virus scanning, thumbnails | 📝 Planned |

### Diagrams

| Diagram | Type | Status |
|---------|------|--------|
| [c4-context.md](./docs/diagrams/c4-context.md) | C4 Level 1 (System Context) | ✅ Complete |
| c4-container.md | C4 Level 2 (Containers) | 📝 In architecture/01 |
| erd.md | Entity Relationship Diagram | 📝 Planned |

### API Specifications (OpenAPI 3.1)

All service API contracts are defined inline in the original architecture blueprint. Key endpoints:

| Service | Key Endpoints | Documentation |
|---------|---------------|---------------|
| Auth Proxy | `/auth/login`, `/auth/refresh`, `/auth/logout` | [Service Inventory](./docs/architecture/05-service-inventory.md#2-auth-proxy) |
| Users | `/v1/users/me`, `/v1/users/{id}` | [Service Inventory](./docs/architecture/05-service-inventory.md#3-users-service) |
| Channels | `/v1/channels`, `/v1/channels/{id}/members` | [Service Inventory](./docs/architecture/05-service-inventory.md#4-channels-service) |
| Messaging | `/v1/messages` (GET/POST/PATCH/DELETE) | [Service Inventory](./docs/architecture/05-service-inventory.md#5-messaging-service) |
| Threads | `/v1/threads`, `/v1/threads/{id}/replies` | [Service Inventory](./docs/architecture/05-service-inventory.md#6-threads-service) |
| Reactions | `/v1/messages/{id}/reactions` | [Service Inventory](./docs/architecture/05-service-inventory.md#7-reactions-service) |
| Presence | `/v1/presence`, `/v1/presence/typing` | [Service Inventory](./docs/architecture/05-service-inventory.md#8-presence-service) |
| Files | `/v1/files/upload-url`, `/v1/files/{id}/download-url` | [Service Inventory](./docs/architecture/05-service-inventory.md#9-files-service) |
| Search | `/v1/search/messages`, `/v1/search/files` | [Service Inventory](./docs/architecture/05-service-inventory.md#10-search-service) |
| Admin | `/v1/admin/users/{id}/deactivate` | [Service Inventory](./docs/architecture/05-service-inventory.md#11-admin-service) |

> **Note**: Full OpenAPI 3.1 YAML specs were provided in the initial architecture blueprint and can be extracted to separate files when needed for code generation.

### Data Model

All database schemas, Redis patterns, and storage configurations are documented inline:

| Component | Documentation | Location |
|-----------|---------------|----------|
| **PostgreSQL Schemas** | Complete DDL for each service | [Service Inventory](./docs/architecture/05-service-inventory.md) - See each service section |
| **Redis Keys** | Cache patterns and TTLs | [Scalability](./docs/architecture/04-scalability-reliability.md#3-caching-strategy) |
| **Object Storage** | MinIO/S3 bucket structure | [Data Flows](./docs/architecture/02-data-flows.md#4-upload-file--attach-to-message) |

### Event Schemas

All Kafka event contracts are documented with JSON examples:

| Event Type | Documentation | Location |
|-----------|---------------|----------|
| **Kafka Topics** | Topic taxonomy, partitioning, retention | [Scalability](./docs/architecture/04-scalability-reliability.md#4-kafka-partitioning) |
| **Message Events** | `message.created`, `message.updated`, `message.deleted` | [Data Flows](./docs/architecture/02-data-flows.md#data-flow-summary) |
| **User Events** | `user.created`, `user.updated`, `user.deactivated` | [Data Flows](./docs/architecture/02-data-flows.md) |
| **Channel Events** | `channel.created`, `member.joined`, etc. | [Data Flows](./docs/architecture/02-data-flows.md#3-create-channel--post-message) |
| **Presence Events** | `presence.updated`, `typing.started` | [Data Flows](./docs/architecture/02-data-flows.md#6-presence-update--typing-indicators) |
| **File Events** | `file.uploaded`, `file.scanned` | [Data Flows](./docs/architecture/02-data-flows.md#4-upload-file--attach-to-message) |

### Security

All security configurations and patterns are documented:

| Component | Documentation | Location |
|-----------|---------------|----------|
| **Keycloak Setup** | Realm config, clients, 2FA | [Security Model](./docs/architecture/03-security-model.md#keycloak-integration) |
| **JWT Validation** | Token verification code examples | [Security Model](./docs/architecture/03-security-model.md#jwt-validation) |
| **RBAC Model** | Role hierarchy and enforcement | [Security Model](./docs/architecture/03-security-model.md#authorization-rbac) |

---

## 🏗️ Architecture Summary

### Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Runtime** | Python | 3.12 |
| **Framework** | FastAPI | 0.109+ |
| **ASGI Server** | Uvicorn | 0.27+ |
| **Database** | PostgreSQL | 16 |
| **Cache** | Redis | 7 |
| **Message Queue** | Redpanda (Kafka-compatible) | Latest |
| **Object Storage** | MinIO / S3 | Latest |
| **Search Engine** | OpenSearch | 2.x |
| **Identity Provider** | Keycloak | 23.x |
| **API Gateway** | Traefik | 3.x |

### Design Principles

1. **API-First**: OpenAPI 3.1 specs define all service contracts
2. **Stateless Services**: All state in Postgres/Redis, not in-memory
3. **Idempotent Operations**: Idempotency keys prevent duplicate processing
4. **Eventual Consistency**: Async updates via Kafka for non-critical paths
5. **Security by Default**: JWT validation on every request, RBAC enforcement
6. **Observable**: Structured logs, distributed tracing, Prometheus metrics

### Microservices (12 Total)

| Service | Port | Responsibilities |
|---------|------|-----------------|
| **api-gateway** (Traefik) | 80/443 | Routing, TLS termination, rate limiting |
| **auth-proxy** | 8001 | Keycloak integration, JWT validation |
| **users-service** | 8002 | User profiles, settings, avatars |
| **channels-service** | 8003 | Channel CRUD, membership management |
| **messaging-service** | 8004 | Send/edit/delete messages, DMs |
| **threads-service** | 8005 | Threaded conversations |
| **reactions-service** | 8006 | Emoji reactions |
| **presence-service** | 8007 | Online status, typing indicators |
| **files-service** | 8008 | File upload/download, virus scanning |
| **search-service** | 8009 | Full-text search (messages, files, users) |
| **admin-service** | 8010 | Moderation, audit logging |
| **realtime-gateway** | 8011 | WebSocket connections, event fan-out |

---

## 🔐 Security Highlights

- **Authentication**: OAuth 2.0 / OIDC via Keycloak
- **2FA**: Mandatory TOTP (Google Authenticator) or WebAuthn (YubiKey)
- **Authorization**: Role-based (admin, moderator, member, guest)
- **Tokens**: JWT (1-hour access, 30-day refresh)
- **Secrets**: Environment variables (dev), Kubernetes Secrets (prod)
- **Rate Limiting**: 100 req/min per IP, 1000 req/min per user
- **File Scanning**: ClamAV virus scanning before file delivery

---

## 📊 Data Stores

### PostgreSQL (Primary Data Store)

**Tables**: `users`, `user_settings`, `channels`, `channel_members`, `messages`, `threads`, `reactions`, `files`, `message_files`, `audit_logs`, `sessions`

**Scaling**:
- Read replicas for query distribution
- Connection pooling via PgBouncer
- Future: Table partitioning for `messages` (by month)

### Redis (Cache & Ephemeral State)

**Use Cases**:
- User/channel metadata cache (5-min TTL)
- Presence status (60-sec TTL)
- Typing indicators (5-sec TTL)
- Rate limiting counters
- WebSocket connection mapping
- Pub/Sub backplane for real-time events

### Redpanda/Kafka (Event Streaming)

**Topics**: `user.events`, `channel.events`, `message.events`, `thread.events`, `reaction.events`, `presence.events`, `file.events`, `audit.events`

**Partitions**: 3-12 per topic (based on throughput)
**Retention**: 1-90 days (based on topic)

### MinIO/S3 (Object Storage)

**Buckets**:
- `colink-files`: Uploaded files (PDFs, images, etc.)
- `colink-avatars`: User avatars
- `colink-thumbnails`: Image thumbnails

**Access**: Presigned URLs (5-min upload, 1-hour download)

### OpenSearch (Search Index)

**Indices**: `messages`, `files`, `users`

**Features**: Full-text search, highlighting, filtering, aggregations

---

## 🚀 Deployment

### Local Development (Docker Compose)

```bash
# Clone repository
git clone https://github.com/yourorg/colink.git
cd colink

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f messaging-service

# Stop all services
docker-compose down
```

**Ports**:
- API Gateway: http://localhost:80
- Keycloak Admin: http://localhost:8080/admin
- MinIO Console: http://localhost:9001
- Kafka UI: http://localhost:8081 (if configured)

### Production (Kubernetes - Optional)

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/kafka.yaml
kubectl apply -f k8s/services/

# Check deployment status
kubectl -n colink get pods

# View logs
kubectl -n colink logs -f deployment/messaging-service
```

---

## 📝 API Example (Creating a Message)

### Request

```http
POST /v1/messages HTTP/1.1
Host: api.colink.dev
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7

{
  "channelId": "01HQZ01ABC2DEF3GHI4JKL5MNO",
  "text": "Hello team! 👋",
  "fileIds": []
}
```

### Response

```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /v1/messages/01HQZY9STUV1WXY2Z3A4B5C6D7

{
  "id": "01HQZY9STUV1WXY2Z3A4B5C6D7",
  "senderId": "01HQZX8PQRS9TUV0WXY1Z2A3B4",
  "senderUsername": "alice_smith",
  "senderDisplayName": "Alice Smith",
  "channelId": "01HQZ01ABC2DEF3GHI4JKL5MNO",
  "recipientId": null,
  "threadId": null,
  "text": "Hello team! 👋",
  "fileIds": [],
  "isEdited": false,
  "isDeleted": false,
  "createdAt": "2025-01-18T10:30:00Z",
  "updatedAt": null
}
```

### Behind the Scenes

1. **API Gateway** validates rate limit, routes to **messaging-service**
2. **Messaging Service** validates JWT, checks channel membership
3. Inserts message into **Postgres** (`messages` table)
4. Publishes `message.created` event to **Kafka** (`message.events` topic)
5. Publishes to **Redis** (`realtime:channel:{channelId}`)
6. **Realtime Gateway** fans out to all connected WebSocket clients
7. **Search Service** (async) indexes message in **OpenSearch**

---

## 📈 Scaling Targets

| Metric | MVP | Scale |
|--------|-----|-------|
| Concurrent users | 100-1,000 | 10,000+ |
| Messages/second | 50 | 1,000 |
| WebSocket connections | 1,000 | 50,000 |
| Database size | 10GB | 1TB |
| File storage | 100GB | 10TB |

---

## 🧪 Testing Strategy

1. **Unit Tests**: FastAPI endpoints with `pytest`
2. **Integration Tests**: Docker Compose + `pytest` with real Postgres/Redis
3. **Contract Tests**: OpenAPI spec validation with `schemathesis`
4. **E2E Tests**: WebSocket + HTTP flows with `playwright`
5. **Load Tests**: `locust` or `k6` for stress testing

---

## 📚 Additional Resources

- **Keycloak Docs**: https://www.keycloak.org/documentation
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **OpenSearch Docs**: https://opensearch.org/docs/
- **Kafka Docs**: https://kafka.apache.org/documentation/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/

---

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on:
- Code style (PEP 8, Black formatting)
- Commit message conventions (Conventional Commits)
- PR review process
- Branch naming (`feature/`, `fix/`, `docs/`)

---

## 📄 License

[MIT License](./LICENSE)

---

## 👥 Team Contacts

- **Tech Lead**: [Your Name]
- **Backend Team**: backend@colink.dev
- **DevOps**: devops@colink.dev
- **Security**: security@colink.dev

---

**Last Updated**: 2025-01-18
**Architecture Version**: 1.0.0
