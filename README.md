# Colink - Slack-like Collaboration Platform

[![Architecture](https://img.shields.io/badge/docs-architecture-blue)](./ARCHITECTURE.md)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

> **Real-time collaboration platform** built with microservices architecture, featuring channels, direct messages, file sharing, and full-text search.

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/darshlukkad/colink-slack-clone.git
cd colink-slack-clone

# Start all services with Docker Compose
docker-compose up -d

# Access the platform
# API Gateway: http://localhost
# Keycloak Admin: http://localhost:8080/admin
# MinIO Console: http://localhost:9001
```

---

## 📚 Documentation

Comprehensive architecture documentation is available:

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Master architecture index
- **[Executive Summary](./docs/architecture/00-executive-summary.md)** - Technology stack and design decisions
- **[System Architecture](./docs/architecture/01-system-architecture.md)** - C4 diagrams and service descriptions
- **[Data Flows](./docs/architecture/02-data-flows.md)** - Sequence diagrams for core user journeys
- **[Security Model](./docs/architecture/03-security-model.md)** - Authentication, authorization, and compliance
- **[Scalability & Reliability](./docs/architecture/04-scalability-reliability.md)** - Scaling patterns and fault tolerance
- **[Service Inventory](./docs/architecture/05-service-inventory.md)** - Detailed catalog of all microservices

---

## ✨ Features

### Core Functionality
- ✅ **Authentication**: OAuth 2.0/OIDC via Keycloak with mandatory 2FA (TOTP/WebAuthn)
- ✅ **Real-time Messaging**: WebSocket-based instant message delivery
- ✅ **Channels & DMs**: Public/private channels and direct messages
- ✅ **Threaded Conversations**: Organize discussions with message threads
- ✅ **Emoji Reactions**: React to messages with emojis
- ✅ **File Sharing**: Upload/download with virus scanning (ClamAV)
- ✅ **Full-text Search**: Search messages, files, and users (OpenSearch)
- ✅ **Presence & Typing**: Online status and typing indicators
- ✅ **Admin Moderation**: User management and message moderation
- ✅ **Audit Logging**: Comprehensive activity tracking

---

## 🏗️ Architecture

### Microservices (12 Total)

| Service | Responsibilities | Port |
|---------|-----------------|------|
| **api-gateway** | Routing, TLS, rate limiting | 80/443 |
| **auth-proxy** | Keycloak integration, JWT validation | 8001 |
| **users-service** | User profiles, settings | 8002 |
| **channels-service** | Channel CRUD, membership | 8003 |
| **messaging-service** | Messages, DMs | 8004 |
| **threads-service** | Thread replies | 8005 |
| **reactions-service** | Emoji reactions | 8006 |
| **presence-service** | Online status, typing | 8007 |
| **files-service** | File upload/download | 8008 |
| **search-service** | Full-text search | 8009 |
| **admin-service** | Moderation, audit | 8010 |
| **realtime-gateway** | WebSocket connections | 8011 |

### Technology Stack

| Component | Technology |
|-----------|-----------|
| **Runtime** | Python 3.12 |
| **Framework** | FastAPI + Uvicorn |
| **Database** | PostgreSQL 16 |
| **Cache** | Redis 7 |
| **Message Queue** | Redpanda (Kafka-compatible) |
| **Object Storage** | MinIO / S3 |
| **Search** | OpenSearch 2.x |
| **Identity** | Keycloak 23.x |
| **Gateway** | Traefik 3.x |

---

## 🛠️ Development Setup

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 18+ (for frontend, future)

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/darshlukkad/colink-slack-clone.git
cd colink-slack-clone

# 2. Copy environment file
cp .env.example .env

# 3. Start infrastructure services
docker-compose up -d postgres redis kafka minio keycloak opensearch clamav

# 4. Run database migrations
make migrate

# 5. Seed test data
make seed

# 6. Start application services
docker-compose up -d

# 7. View logs
docker-compose logs -f messaging-service
```

### Verify Services

```bash
# Check all services are running
docker-compose ps

# Health checks
curl http://localhost/health
curl http://localhost:8001/health  # Auth Proxy
curl http://localhost:8002/health  # Users Service
```

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit

# Run integration tests
pytest tests/integration

# Run all tests with coverage
pytest --cov=src --cov-report=html

# Run specific service tests
pytest tests/unit/test_messaging_service.py
```

---

## 📖 API Documentation

### Interactive API Docs (Swagger UI)

Once services are running, access interactive API documentation:

- Auth Proxy: http://localhost:8001/docs
- Users Service: http://localhost:8002/docs
- Channels Service: http://localhost:8003/docs
- Messaging Service: http://localhost:8004/docs
- Threads Service: http://localhost:8005/docs
- Reactions Service: http://localhost:8006/docs
- Presence Service: http://localhost:8007/docs
- Files Service: http://localhost:8008/docs
- Search Service: http://localhost:8009/docs
- Admin Service: http://localhost:8010/docs

### Example: Send a Message

```bash
# 1. Login and get token
TOKEN=$(curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice@colink.dev", "password": "password123"}' \
  | jq -r '.accessToken')

# 2. Send message to channel
curl -X POST http://localhost/v1/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "channelId": "01HQZ01ABC2DEF3GHI4JKL5MNO",
    "text": "Hello team! 👋"
  }'
```

---

## 🔐 Security

- **Authentication**: OAuth 2.0 / OIDC via Keycloak
- **2FA**: Mandatory (TOTP or WebAuthn)
- **Authorization**: Role-based access control (admin, moderator, member, guest)
- **Encryption**: TLS 1.3 for all external communication
- **File Scanning**: ClamAV virus scanning before delivery
- **Rate Limiting**: 100 req/min per IP, 1000 req/min per user
- **Secrets**: Environment variables (dev), Kubernetes Secrets (prod)

---

## 🚢 Deployment

### Docker Compose (Development/Staging)

```bash
# Start all services
docker-compose up -d

# Scale specific service
docker-compose up -d --scale messaging-service=3

# Stop all services
docker-compose down
```

### Kubernetes (Production - Optional)

```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/kafka.yaml
kubectl apply -f k8s/services/

# Check status
kubectl -n colink get pods

# View logs
kubectl -n colink logs -f deployment/messaging-service
```

---

## 📊 Monitoring

### Metrics & Logs

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **Jaeger**: http://localhost:16686
- **Kafka UI**: http://localhost:8081

### Key Metrics

- HTTP request latency (P95, P99)
- Kafka consumer lag
- WebSocket connections
- Database connection pool usage
- Redis memory usage
- Error rates by service

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- **Python**: PEP 8, formatted with Black
- **Commit Messages**: Conventional Commits format
- **Tests**: Required for all new features

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

---

## 👥 Team

- **Tech Lead**: Darsh Lukkad ([@darshlukkad](https://github.com/darshlukkad))
- **Architecture**: [See ARCHITECTURE.md](./ARCHITECTURE.md)

---

## 📧 Contact

- **GitHub**: [@darshlukkad](https://github.com/darshlukkad)
- **Repository**: [colink-slack-clone](https://github.com/darshlukkad/colink-slack-clone)

---

## 🗺️ Roadmap

### Phase 1 (Current) - Architecture & Documentation
- ✅ Complete architecture design
- ✅ Service contracts (OpenAPI 3.1)
- ✅ Data model design
- ✅ Event schemas (Kafka)

### Phase 2 - Core Services
- ⏳ Auth & Users services
- ⏳ Channels & Messaging
- ⏳ Real-time gateway (WebSocket)

### Phase 3 - Extended Features
- ⏳ Threads & Reactions
- ⏳ File upload & virus scanning
- ⏳ Full-text search

### Phase 4 - Admin & Moderation
- ⏳ Admin dashboard
- ⏳ Audit logging
- ⏳ User management

### Phase 5 - Frontend
- ⏳ React/Next.js web application
- ⏳ WebSocket client
- ⏳ UI/UX design

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Keycloak](https://www.keycloak.org/) - Identity and access management
- [PostgreSQL](https://www.postgresql.org/) - Reliable database
- [Redpanda](https://redpanda.com/) - Kafka-compatible streaming
- [OpenSearch](https://opensearch.org/) - Search and analytics

---

**Built with ❤️ using FastAPI, PostgreSQL, and Kafka**
