# Colink Backend Architecture Documentation

## Overview

Colink is a single-tenant, real-time collaboration platform built with API-first microservices architecture. This documentation provides comprehensive technical specifications for the backend system.

## Documentation Structure

### 1. Architecture
- [Executive Summary](./architecture/00-executive-summary.md) - High-level overview and stack decisions
- [System Architecture](./architecture/01-system-architecture.md) - C4 diagrams and service interactions
- [Core Data Flows](./architecture/02-data-flows.md) - Sequence diagrams for key journeys
- [Security Model](./architecture/03-security-model.md) - Authentication, authorization, and compliance
- [Scalability & Reliability](./architecture/04-scalability-reliability.md) - Patterns for scale and fault tolerance

### 2. Diagrams
- [Context Diagram](./diagrams/c4-context.md) - System context (C4 Level 1)
- [Container Diagram](./diagrams/c4-container.md) - Container view (C4 Level 2)
- [Entity Relationship Diagram](./diagrams/erd.md) - Database schema relationships

### 3. Service Inventory
- [Service Inventory](./architecture/05-service-inventory.md) - All microservices with responsibilities and contracts

### 4. Detailed Specifications

All detailed specs (API contracts, event schemas, database DDL, security configs) are documented inline within the architecture documents above:

- **API Specs (OpenAPI 3.1)**: See [ARCHITECTURE.md](../ARCHITECTURE.md#api-example-creating-a-message) - Full specs defined in original blueprint
- **Data Model**: Database schemas in [05-service-inventory.md](./architecture/05-service-inventory.md) under each service
- **Event Contracts**: Kafka event schemas in [02-data-flows.md](./architecture/02-data-flows.md)
- **Security Details**: Keycloak config, JWT validation, RBAC in [03-security-model.md](./architecture/03-security-model.md)
- **Real-Time**: WebSocket architecture in [01-system-architecture.md](./architecture/01-system-architecture.md#real-time-websocket)
- **Search**: OpenSearch details in [04-scalability-reliability.md](./architecture/04-scalability-reliability.md)
- **File Handling**: Presigned URLs, virus scanning in [02-data-flows.md](./architecture/02-data-flows.md#4-upload-file--attach-to-message)

## Quick Start

1. **Read the Executive Summary**: Start with [00-executive-summary.md](./architecture/00-executive-summary.md)
2. **Review System Architecture**: Understand the container diagram in [01-system-architecture.md](./architecture/01-system-architecture.md)
3. **Explore Service Contracts**: Review [05-service-inventory.md](./architecture/05-service-inventory.md) for all service details
4. **Understand Data Model**: Database schemas are in each service section of [05-service-inventory.md](./architecture/05-service-inventory.md)
5. **Study Event Flows**: Check [02-data-flows.md](./architecture/02-data-flows.md) for sequence diagrams and event schemas

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Runtime | Python | 3.12 |
| Framework | FastAPI | 0.109+ |
| ASGI Server | Uvicorn | 0.27+ |
| Database | PostgreSQL | 16 |
| Cache | Redis | 7 |
| Message Queue | Redpanda/Kafka | Latest |
| Object Storage | MinIO/S3 | Latest |
| Search | OpenSearch | 2.x |
| Identity | Keycloak | 23.x |
| API Gateway | Traefik | 3.x |

## Development Workflow

See [Local Development Guide](../README.md#local-development) in the root README for setup instructions.

## Implementation Phases

1. **Phase 1**: Auth & Users (Keycloak integration, user profiles)
2. **Phase 2**: Channels (Channel CRUD, membership)
3. **Phase 3**: Messaging (Real-time messaging, DMs)
4. **Phase 4**: Threads & Reactions
5. **Phase 5**: Presence & Typing
6. **Phase 6**: Files (Upload, virus scan, storage)
7. **Phase 7**: Search (Full-text indexing)
8. **Phase 8**: Admin & Moderation

## Support

For questions or issues, refer to the project README or contact the engineering team.
