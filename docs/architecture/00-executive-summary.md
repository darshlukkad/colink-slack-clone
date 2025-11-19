# Executive Summary

## Project Overview

**Colink** is a single-tenant, real-time collaboration platform (Slack-like) designed with API-first microservices architecture. The backend system supports 100-1,000 concurrent users with the following core features:

- User authentication with SSO (Keycloak) and 2FA (TOTP/WebAuthn)
- Real-time messaging (channels and direct messages)
- Threaded conversations
- Emoji reactions
- Presence indicators and typing notifications
- File sharing with virus scanning
- Full-text search
- Admin moderation and audit logging

## Technology Stack

### Runtime & Framework

**Chosen**: Python 3.12 + FastAPI + Uvicorn

**Rationale**:
- **FastAPI**: Native OpenAPI support, async/await, high performance (Starlette/Uvicorn), excellent type safety with Pydantic
- **Python 3.12**: Mature ecosystem, team expertise, rich libraries for integration
- **Async I/O**: Critical for WebSocket connections and high-concurrency real-time features

**Alternatives Considered**:
- **Django Ninja**: Heavier framework, slower startup, less WebSocket-friendly
- **Go + Fiber**: Better raw performance but requires team reskilling and smaller ecosystem
- **Node.js + NestJS**: Callback complexity at scale, weaker type safety

---

### Database Layer

**Chosen**: PostgreSQL 16 (primary), Redis 7 (cache + ephemeral state)

**Rationale**:
- **PostgreSQL**:
  - ACID compliance for message integrity
  - Rich indexing (B-tree, GIN for full-text, pg_trgm for fuzzy search)
  - JSON support for flexible user settings
  - Battle-tested at scale
- **Redis**:
  - Sub-millisecond latency for presence/typing indicators
  - Pub/Sub for WebSocket fan-out
  - Rate limiting and session storage

**Alternatives Considered**:
- **MongoDB**: Not needed; relational data model (users, channels, messages) fits RDBMS better
- **Cassandra**: Overkill for single-tenant; complexity not justified
- **Polyglot persistence** (Postgres + MongoDB): Adds operational overhead for marginal benefit

---

### Message Queue & Event Streaming

**Chosen**: Redpanda (Kafka-compatible)

**Rationale**:
- **Kafka-compatible API**: Industry standard, rich ecosystem (clients, connectors)
- **Redpanda advantages**: Simpler operations (no ZooKeeper), lower latency, easier dev setup
- **Flexibility**: Can swap to Apache Kafka in production if needed

**Use Cases**:
- Async event propagation (message created → search indexing)
- Decoupling services (user deactivated → cascade to messaging/search)
- Audit trail and event sourcing

---

### Object Storage

**Chosen**: MinIO (development/staging), AWS S3 (production)

**Rationale**:
- **S3-compatible API**: Portable across environments
- **MinIO**: Self-hosted, zero-cost for dev, identical API to S3
- **Presigned URLs**: Offload upload/download traffic from application servers

**Storage**:
- File attachments (PDFs, images, videos)
- User avatars
- Thumbnails

---

### Search Engine

**Chosen**: OpenSearch 2.x

**Rationale**:
- **Full-text search**: Messages, files, user directory
- **Highlighting**: Show search term context in results
- **Scalability**: Distributed architecture, horizontal scaling
- **Open-source**: Apache 2.0 license, community-driven

**Indexing Strategy**:
- Async consumers read Kafka events (message.created, user.updated)
- Transform to OpenSearch documents
- Bulk index every 5s or 100 docs

---

### Identity & Access Management

**Chosen**: Keycloak 23.x

**Rationale**:
- **Standards-based**: OIDC, OAuth 2.0, SAML
- **2FA built-in**: TOTP (Google Authenticator), WebAuthn (YubiKey, passkeys)
- **User federation**: LDAP/AD support (future enterprise customers)
- **Admin UI**: User management, role assignment
- **Open-source**: No vendor lock-in

**Authentication Flow**:
1. Authorization Code + PKCE (web app)
2. JWT tokens (access + refresh)
3. Services validate JWT locally (JWKS cache)

---

### API Gateway

**Chosen**: Traefik 3.x

**Rationale**:
- **Dynamic routing**: Service discovery, hot reload
- **WebSocket support**: Upgrade HTTP → WS
- **Middleware**: Rate limiting, CORS, TLS termination
- **Observability**: Prometheus metrics, access logs

**Alternatives Considered**:
- **NGINX**: Static config, requires reload
- **Kong**: Enterprise features unnecessary for MVP

---

## Architecture Principles

### 1. API-First Design
- Every service exposes REST API defined by OpenAPI 3.1 spec
- Contract-driven development: spec → code generation → implementation
- Enables parallel development (frontend and backend teams)

### 2. Stateless Services
- No in-memory sessions; all state in Postgres/Redis
- Horizontal scaling via load balancer (round-robin)
- Simplifies deployment and failover

### 3. Idempotency
- HTTP: `Idempotency-Key` header for POST/PUT/DELETE
- Kafka: Producer idempotence + transactional writes
- Prevents duplicate processing (network retries, message replays)

### 4. Eventual Consistency
- Services own their data; async propagation via Kafka
- Search index may lag by seconds (acceptable for UX)
- Presence data may be stale (5s TTL in Redis)

### 5. Security by Default
- JWT validation on every request (except auth endpoints)
- RBAC enforced at service layer (admin/moderator/member roles)
- Input validation with Pydantic models
- Rate limiting per IP and per user
- TLS 1.3 for transport encryption

### 6. Observability
- Structured JSON logs to stdout
- Distributed tracing with Jaeger (trace IDs in all logs)
- Prometheus metrics (request latency, error rate, queue depth)
- Grafana dashboards for visualization

---

## Deployment Model

### Development
- **Docker Compose**: All services + dependencies in single `docker-compose.yml`
- **Hot reload**: Code changes reflect immediately (volume mounts)
- **Seed data**: `make seed` populates test users, channels, messages

### Staging/Production
- **Kubernetes** (optional): Helm charts for each service
- **Docker Swarm** (simpler alternative): Docker stack deploy
- **Health checks**: `/health` endpoint (liveness) and `/ready` (readiness)
- **Rolling updates**: Zero-downtime deployments

---

## Scalability Targets

| Metric | MVP Target | Scale Target |
|--------|-----------|--------------|
| Concurrent users | 100-1,000 | 10,000+ |
| Messages/second | 50 | 1,000 |
| Search latency | <500ms | <200ms |
| WebSocket connections | 1,000 | 50,000 |
| File storage | 100GB | 10TB |
| Database size | 10GB | 1TB |

**Scaling Strategy**:
- **Horizontal**: Add service replicas (stateless design)
- **Database**: Read replicas for queries, connection pooling (PgBouncer)
- **Redis**: Redis Cluster for sharding (if needed)
- **Kafka**: Increase partitions (12 → 48 for message.events)
- **OpenSearch**: Add data nodes

---

## Design Trade-offs

### 1. Single-Tenant vs Multi-Tenant
**Decision**: Single-tenant for MVP

**Rationale**:
- Simpler data model (no `org_id` in every table)
- Faster time-to-market
- Can migrate to multi-tenant later (add `workspace_id` column + RLS)

**Migration Path**:
- Add `workspace_id` to all tables (default to 'default')
- Update queries to filter by `workspace_id`
- Keycloak: add realm per workspace OR single realm with workspace claim

### 2. Postgres-Only vs Polyglot Persistence
**Decision**: Postgres + Redis only (no NoSQL)

**Rationale**:
- Relational data model (users ↔ channels ↔ messages) fits RDBMS
- Postgres scales to 1TB+ with proper indexing
- Reduces operational complexity (single DB to backup/monitor)

**Future**: If needed, shard messages table by `created_at` (monthly partitions)

### 3. Synchronous vs Asynchronous APIs
**Decision**: Hybrid

**Synchronous (REST)**:
- User CRUD, channel CRUD, send message, get messages
- Predictable latency, simpler client logic

**Asynchronous (Kafka)**:
- Search indexing, audit logging, notifications
- Decouples services, improves resilience

### 4. Real-Time: WebSocket vs Server-Sent Events (SSE)
**Decision**: WebSocket

**Rationale**:
- **Bidirectional**: Client can send typing indicators, presence updates
- **Lower overhead**: Single connection vs HTTP polling
- **Industry standard**: Slack, Discord, Teams all use WebSocket

**SSE Alternative**:
- Simpler (HTTP-based), automatic reconnection
- But unidirectional (server → client only)

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **Keycloak downtime** | Cache JWKS for 1h; short-lived tokens (1h) allow existing users to continue |
| **Postgres failure** | Read replicas for failover; automated backups (daily + WAL archiving) |
| **Kafka lag** | DLQ for poison messages; alerting on consumer lag >1000 |
| **Redis eviction** | Presence degrades gracefully (show "last seen" timestamp from Postgres) |
| **File upload abuse** | Virus scanning (ClamAV), MIME whitelist, size limits (100MB), rate limiting |
| **Search downtime** | Return 503; show cached recent messages; search non-critical for messaging |

---

## Success Metrics

- **Uptime**: 99.9% (8.76h downtime/year)
- **Message delivery**: <500ms P95 latency
- **Search**: <1s P95 query time
- **File upload**: <5s for 10MB file (presigned URL)
- **WebSocket reconnect**: <2s after network interruption

---

## Next Steps

1. **Review Service Inventory**: [05-service-inventory.md](./05-service-inventory.md)
2. **Study Data Flows**: [02-data-flows.md](./02-data-flows.md)
3. **Explore API Contracts**: [../api-specs/](../api-specs/)
4. **Understand Security Model**: [03-security-model.md](./03-security-model.md)
