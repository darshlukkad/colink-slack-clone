# Scalability & Reliability

## Overview

This document outlines the strategies and patterns used to ensure Colink can scale horizontally and maintain high availability under failure conditions.

---

## Scalability Patterns

### 1. Stateless Services

**Principle**: All application services are stateless; session/user state stored externally.

**Benefits**:
- Horizontal scaling (add replicas without coordination)
- Rolling updates with zero downtime
- Simple load balancing (round-robin)

**Implementation**:
```python
# ❌ Stateful (bad)
in_memory_cache = {}

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    if user_id in in_memory_cache:
        return in_memory_cache[user_id]
    # ...

# ✅ Stateless (good)
@app.get("/users/{user_id}")
async def get_user(
    user_id: str,
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db)
):
    cached = await redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)

    user = db.query(User).filter(User.id == user_id).first()
    await redis.setex(f"user:{user_id}", 300, json.dumps(user.dict()))
    return user
```

---

### 2. Database Scaling

#### Read Replicas

**Pattern**: Route read queries to replicas; writes to primary.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Primary (read-write)
primary_engine = create_engine(DATABASE_PRIMARY_URL)
PrimarySession = sessionmaker(bind=primary_engine)

# Replica (read-only)
replica_engine = create_engine(DATABASE_REPLICA_URL)
ReplicaSession = sessionmaker(bind=replica_engine)

# Dependency injection
async def get_write_db():
    db = PrimarySession()
    try:
        yield db
    finally:
        db.close()

async def get_read_db():
    db = ReplicaSession()
    try:
        yield db
    finally:
        db.close()

# Usage
@app.get("/users")
async def list_users(db: Session = Depends(get_read_db)):
    return db.query(User).all()

@app.post("/users")
async def create_user(user: CreateUserRequest, db: Session = Depends(get_write_db)):
    new_user = User(**user.dict())
    db.add(new_user)
    db.commit()
    return new_user
```

#### Connection Pooling

**PgBouncer** as connection pooler:

```ini
# pgbouncer.ini
[databases]
colink = host=postgres.svc.cluster.local port=5432 dbname=colink

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 3
```

**Application Connection**:
```python
DATABASE_URL = "postgresql://user:pass@pgbouncer:6432/colink"
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True  # Verify connection before use
)
```

#### Table Partitioning (Future)

**Partition `messages` by month**:

```sql
-- Parent table
CREATE TABLE messages (
    id UUID NOT NULL,
    sender_id UUID NOT NULL,
    channel_id UUID,
    text TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ...
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE messages_2025_01 PARTITION OF messages
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE messages_2025_02 PARTITION OF messages
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Auto-create partitions (pg_partman extension)
SELECT create_parent('public.messages', 'created_at', 'native', 'monthly');
```

**Benefits**:
- Faster queries (partition pruning)
- Easier archival (drop old partitions)
- Improved vacuum performance

---

### 3. Caching Strategy

#### Cache Layers

```
┌───────────────────────────────────────┐
│  Application Service                  │
│                                       │
│  ├─ L1: In-memory (5s TTL)            │
│  │   └─ functools.lru_cache           │
│  │                                    │
│  ├─ L2: Redis (5min TTL)              │
│  │   └─ User/Channel metadata         │
│  │                                    │
│  └─ L3: Postgres (source of truth)    │
└───────────────────────────────────────┘
```

#### Cache-Aside Pattern

```python
import functools
from typing import Optional

@functools.lru_cache(maxsize=1000)
def get_user_l1_cache(user_id: str) -> Optional[dict]:
    """L1: In-memory cache (5s TTL via time-based eviction)"""
    # Simple LRU cache for hot data
    return None

async def get_user(user_id: str, redis: Redis, db: Session) -> dict:
    # L1: In-memory
    cached = get_user_l1_cache(user_id)
    if cached:
        return cached

    # L2: Redis
    redis_key = f"user:{user_id}"
    cached = await redis.get(redis_key)
    if cached:
        user = json.loads(cached)
        get_user_l1_cache.cache_clear()  # Invalidate L1 on L2 hit
        get_user_l1_cache(user_id)  # Populate L1
        return user

    # L3: Database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404)

    user_dict = user.dict()

    # Populate L2
    await redis.setex(redis_key, 300, json.dumps(user_dict))

    # Populate L1
    get_user_l1_cache(user_id)

    return user_dict
```

#### Cache Invalidation

**Write-Through**:
```python
async def update_user(
    user_id: str,
    update: UpdateUserRequest,
    redis: Redis,
    db: Session
):
    user = db.query(User).filter(User.id == user_id).first()
    for key, value in update.dict(exclude_unset=True).items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)

    # Invalidate cache
    await redis.delete(f"user:{user_id}")

    # Publish cache invalidation event (for distributed cache)
    await redis.publish(
        "cache:invalidate",
        json.dumps({"entity": "user", "id": user_id})
    )

    return user
```

---

### 4. Kafka Partitioning

#### Partition Strategy

| Topic | Partitions | Partition Key | Rationale |
|-------|-----------|---------------|-----------|
| `message.events` | 12 | `channel_id` or `dm_id` | Ensures message ordering per channel/DM |
| `user.events` | 3 | `user_id` | Low volume, user lifecycle events |
| `channel.events` | 6 | `channel_id` | Channel updates are infrequent |
| `presence.events` | 3 | `user_id` | Ephemeral, high volume, 1-day retention |
| `file.events` | 3 | `file_id` | File operations are independent |

#### Consumer Scaling

**Single Partition = Single Consumer** (in a consumer group):
```
Topic: message.events (12 partitions)

Consumer Group: search-indexer
├─ Consumer 1 → Partitions [0, 1, 2]
├─ Consumer 2 → Partitions [3, 4, 5]
├─ Consumer 3 → Partitions [6, 7, 8]
└─ Consumer 4 → Partitions [9, 10, 11]
```

**Scaling**: Add more consumers (up to # of partitions)

```python
from aiokafka import AIOKafkaConsumer

async def start_consumer():
    consumer = AIOKafkaConsumer(
        'message.events',
        bootstrap_servers='kafka:9092',
        group_id='search-indexer',
        enable_auto_commit=False,  # Manual commit for at-least-once
        auto_offset_reset='earliest'
    )
    await consumer.start()

    try:
        async for msg in consumer:
            await process_message(msg.value)
            await consumer.commit()  # Commit after successful processing
    finally:
        await consumer.stop()
```

---

### 5. Real-Time Gateway Scaling

#### WebSocket Connection Distribution

```
┌────────────────────────────────────────┐
│  Load Balancer (Traefik)               │
│  Sticky sessions: None (stateless)     │
└────────────────────────────────────────┘
           │
           ├──────────────────────┬──────────────────┐
           │                      │                  │
    ┌──────▼──────┐        ┌──────▼──────┐    ┌──────▼──────┐
    │ RT Gateway 1│        │ RT Gateway 2│    │ RT Gateway 3│
    │ 5000 conns  │        │ 5000 conns  │    │ 5000 conns  │
    └──────┬──────┘        └──────┬──────┘    └──────┬──────┘
           │                      │                  │
           └──────────────────────┴──────────────────┘
                              │
                       ┌──────▼──────┐
                       │ Redis Pub/Sub│
                       │ (backplane)  │
                       └──────────────┘
```

**Connection Tracking in Redis**:
```python
import uuid

# On WebSocket connect
connection_id = str(uuid.uuid4())
user_id = current_user["user_id"]

# Map connection to user
await redis.sadd(f"ws:user:{user_id}:conns", connection_id)

# Store connection metadata
await redis.hset(
    f"ws:conn:{connection_id}",
    mapping={
        "user_id": user_id,
        "gateway_instance": INSTANCE_ID,
        "connected_at": datetime.utcnow().isoformat()
    }
)
await redis.expire(f"ws:conn:{connection_id}", 3600)

# On disconnect
await redis.srem(f"ws:user:{user_id}:conns", connection_id)
await redis.delete(f"ws:conn:{connection_id}")
```

**Fan-Out via Redis Pub/Sub**:
```python
# RT Gateway subscribes to Redis channels
async def subscribe_to_channel(channel_id: str):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"realtime:channel:{channel_id}")

    async for message in pubsub.listen():
        if message['type'] == 'message':
            event_data = json.loads(message['data'])
            await broadcast_to_channel_members(channel_id, event_data)

# Service publishes to Redis
async def publish_message_event(channel_id: str, message_data: dict):
    await redis.publish(
        f"realtime:channel:{channel_id}",
        json.dumps(message_data)
    )
```

---

## Reliability Patterns

### 1. Idempotency

#### HTTP Idempotency Key

```python
from hashlib import sha256

async def check_idempotency(
    idempotency_key: str,
    redis: Redis
) -> Optional[dict]:
    """
    Check if request was already processed

    Returns:
        Previous response if duplicate, None otherwise
    """
    redis_key = f"idempotency:{idempotency_key}"
    cached_response = await redis.get(redis_key)

    if cached_response:
        return json.loads(cached_response)

    return None

async def store_idempotent_response(
    idempotency_key: str,
    response: dict,
    redis: Redis,
    ttl: int = 86400  # 24 hours
):
    """Store response for duplicate detection"""
    redis_key = f"idempotency:{idempotency_key}"
    await redis.setex(redis_key, ttl, json.dumps(response))

# Usage
@app.post("/v1/messages")
async def create_message(
    request: CreateMessageRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db)
):
    # Check for duplicate request
    cached = await check_idempotency(idempotency_key, redis)
    if cached:
        return JSONResponse(content=cached, status_code=201)

    # Process request
    message = Message(**request.dict())
    db.add(message)
    db.commit()

    response = message.dict()

    # Store for future duplicate checks
    await store_idempotent_response(idempotency_key, response, redis)

    return response
```

#### Kafka Producer Idempotence

```python
from aiokafka import AIOKafkaProducer

producer = AIOKafkaProducer(
    bootstrap_servers='kafka:9092',
    enable_idempotence=True,  # Exactly-once semantics
    transactional_id='messaging-service-001',  # Unique per instance
    acks='all',  # Wait for all replicas
    retries=10,
    max_in_flight_requests_per_connection=5
)

await producer.start()

# Transactional write
async with producer.transaction():
    await producer.send_and_wait(
        'message.events',
        key=message.channel_id.encode(),
        value=json.dumps(message_event).encode(),
        headers=[
            ('idempotency_key', idempotency_key.encode()),
            ('trace_id', trace_id.encode())
        ]
    )
```

---

### 2. Retries & Circuit Breakers

#### Exponential Backoff Retry

```python
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    reraise=True
)
async def call_external_service(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        return response.json()
```

#### Circuit Breaker

```python
from pybreaker import CircuitBreaker, CircuitBreakerError

# Circuit opens after 5 failures, stays open for 30s
circuit_breaker = CircuitBreaker(
    fail_max=5,
    timeout_duration=30,
    expected_exception=Exception
)

@circuit_breaker
async def scan_file_with_clamav(file_path: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://clamav:3310/scan",
            json={"file_path": file_path},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

# Usage with fallback
try:
    result = await scan_file_with_clamav(file_path)
except CircuitBreakerError:
    # Circuit is open, fallback to marking as "pending_scan"
    logger.warning(f"ClamAV circuit open, deferring scan for {file_path}")
    return {"status": "pending_scan"}
```

---

### 3. Dead Letter Queues (DLQ)

**Kafka Consumer with DLQ**:

```python
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

dlq_producer = AIOKafkaProducer(bootstrap_servers='kafka:9092')

async def process_with_dlq():
    consumer = AIOKafkaConsumer(
        'message.events',
        bootstrap_servers='kafka:9092',
        group_id='search-indexer'
    )

    await consumer.start()
    await dlq_producer.start()

    try:
        async for msg in consumer:
            try:
                await process_message(msg.value)
                await consumer.commit()
            except Exception as e:
                logger.error(f"Processing failed: {e}", exc_info=True)

                # Retry count from message headers
                headers = dict(msg.headers)
                retry_count = int(headers.get('retry_count', b'0').decode())

                if retry_count < 3:
                    # Retry: send back to same topic with incremented counter
                    await dlq_producer.send(
                        'message.events',
                        key=msg.key,
                        value=msg.value,
                        headers=[
                            ('retry_count', str(retry_count + 1).encode()),
                            ('original_topic', b'message.events'),
                            ('error', str(e).encode())
                        ]
                    )
                else:
                    # Send to DLQ after 3 retries
                    await dlq_producer.send(
                        'dlq.message.events',
                        key=msg.key,
                        value=msg.value,
                        headers=[
                            ('original_topic', b'message.events'),
                            ('retry_count', str(retry_count).encode()),
                            ('error', str(e).encode()),
                            ('timestamp', str(datetime.utcnow().timestamp()).encode())
                        ]
                    )

                await consumer.commit()
    finally:
        await consumer.stop()
        await dlq_producer.stop()
```

---

### 4. Health Checks

#### Liveness Probe

```python
@app.get("/health")
async def health_check():
    """
    Liveness probe: Is the service running?
    Returns 200 if process is alive, 5xx otherwise
    """
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
```

#### Readiness Probe

```python
@app.get("/ready")
async def readiness_check(
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db)
):
    """
    Readiness probe: Is the service ready to handle requests?
    Checks dependencies (DB, Redis, Kafka)
    """
    checks = {}

    # Check Postgres
    try:
        db.execute("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)}"

    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    # Check Kafka (optional, can be slow)
    # try:
    #     admin_client = KafkaAdminClient(bootstrap_servers='kafka:9092')
    #     admin_client.list_topics(timeout=2)
    #     checks["kafka"] = "ok"
    # except Exception as e:
    #     checks["kafka"] = f"error: {str(e)}"

    all_ok = all(status == "ok" for status in checks.values())

    return JSONResponse(
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        },
        status_code=200 if all_ok else 503
    )
```

**Kubernetes Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: messaging-service
        image: colink/messaging-service:latest
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 3
```

---

### 5. Graceful Shutdown

```python
import signal
import asyncio

shutdown_event = asyncio.Event()

async def shutdown_handler(sig):
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()

async def main():
    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown_handler(s))
        )

    # Start background tasks
    consumer_task = asyncio.create_task(kafka_consumer())
    server_task = asyncio.create_task(uvicorn.serve(app))

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Graceful shutdown
    logger.info("Stopping Kafka consumer...")
    consumer_task.cancel()
    await asyncio.wait([consumer_task], timeout=30)

    logger.info("Stopping HTTP server...")
    server_task.cancel()
    await asyncio.wait([server_task], timeout=10)

    logger.info("Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Monitoring & Alerting

### Key Metrics

| Metric | Type | Alert Threshold |
|--------|------|----------------|
| HTTP request latency (P95) | Histogram | > 500ms |
| HTTP error rate | Counter | > 1% |
| Kafka consumer lag | Gauge | > 1000 messages |
| WebSocket connections | Gauge | > 10000 per instance |
| Postgres connection pool usage | Gauge | > 80% |
| Redis memory usage | Gauge | > 80% |
| File upload failures | Counter | > 5% |

### Prometheus Metrics (Example)

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Counters
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Histograms
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# Gauges
websocket_connections = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections'
)

# Middleware
@app.middleware("http")
async def prometheus_middleware(request, call_next):
    method = request.method
    path = request.url.path

    with http_request_duration_seconds.labels(method, path).time():
        response = await call_next(request)

    http_requests_total.labels(method, path, response.status_code).inc()

    return response

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

---

## Disaster Recovery

### Backup Strategy

| Data Store | Backup Frequency | Retention | Recovery Time Objective (RTO) |
|-----------|-----------------|-----------|-------------------------------|
| Postgres | Daily full + WAL archiving | 30 days | < 1 hour |
| Redis | None (ephemeral) | N/A | N/A (rebuild from Postgres) |
| MinIO/S3 | Continuous replication | 90 days | < 5 minutes (multi-AZ) |
| Kafka | Topic replication (RF=3) | Per topic | < 5 minutes |

### Postgres Backup

```bash
# Daily full backup (pg_dump)
pg_dump -h postgres -U colink -F c -f /backups/colink_$(date +%Y%m%d).dump colink

# WAL archiving (continuous)
# postgresql.conf
archive_mode = on
archive_command = 'cp %p /backups/wal/%f'

# Point-in-time recovery
pg_restore -h postgres -U colink -d colink /backups/colink_20250118.dump
```

---

## Next Steps

1. **Review Service Inventory**: [05-service-inventory.md](./05-service-inventory.md)
2. **Study Real-Time Architecture**: [06-realtime-transport.md](./06-realtime-transport.md)
3. **Explore Search Indexing**: [07-search.md](./07-search.md)
