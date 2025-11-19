# Security Model

## Overview

Colink implements a defense-in-depth security strategy with multiple layers:

1. **Transport Security**: TLS 1.3 encryption
2. **Authentication**: OAuth 2.0 / OIDC via Keycloak with mandatory 2FA
3. **Authorization**: Role-based access control (RBAC) + resource ownership
4. **Input Validation**: Schema-based validation with Pydantic
5. **Rate Limiting**: IP-based and user-based throttling
6. **Secrets Management**: Environment variables + Kubernetes Secrets
7. **Audit Logging**: Comprehensive activity tracking

---

## Authentication Architecture

### Keycloak Integration

#### Realm Configuration

**Realm**: `colink`

**Clients**:

| Client ID | Type | Purpose | Flow |
|-----------|------|---------|------|
| `web-app` | Public | Frontend application | Authorization Code + PKCE |
| `api-gateway` | Bearer-only | Token validation | N/A (validates only) |
| `service-internal` | Confidential | Service-to-service auth | Client Credentials |

#### Client: web-app (Public)

```json
{
  "clientId": "web-app",
  "enabled": true,
  "publicClient": true,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
  "implicitFlowEnabled": false,
  "serviceAccountsEnabled": false,
  "authorizationServicesEnabled": false,
  "redirectUris": [
    "https://colink.dev/auth/callback",
    "http://localhost:3000/auth/callback"
  ],
  "webOrigins": [
    "https://colink.dev",
    "http://localhost:3000"
  ],
  "attributes": {
    "pkce.code.challenge.method": "S256"
  }
}
```

**PKCE Requirements**:
- Code challenge method: S256 (SHA-256)
- Mandatory for public clients (prevents authorization code interception)

#### Client: service-internal (Confidential)

```json
{
  "clientId": "service-internal",
  "enabled": true,
  "publicClient": false,
  "standardFlowEnabled": false,
  "directAccessGrantsEnabled": false,
  "serviceAccountsEnabled": true,
  "secret": "${SERVICE_CLIENT_SECRET}"
}
```

**Use Case**: Admin service calling User service (machine-to-machine)

---

### Two-Factor Authentication (2FA)

#### Enforced 2FA Flow

**Keycloak Authentication Flow**: `Browser with Required OTP`

```
Browser Flow
├── Cookie
├── Kerberos
├── Identity Provider Redirector
├── Forms
│   ├── Username Password Form
│   └── OTP Form (REQUIRED)
└── ...
```

#### Supported 2FA Methods

##### 1. TOTP (Time-based One-Time Password)

**Configuration**:
```json
{
  "otpPolicyType": "totp",
  "otpPolicyAlgorithm": "HmacSHA256",
  "otpPolicyDigits": 6,
  "otpPolicyPeriod": 30,
  "otpPolicyInitialCounter": 0
}
```

**Compatible Apps**:
- Google Authenticator
- Authy
- Microsoft Authenticator
- 1Password

**Setup Flow**:
1. User logs in with password
2. Keycloak shows QR code
3. User scans QR code in authenticator app
4. User enters 6-digit code to verify
5. Backup codes generated (10 single-use codes)

##### 2. WebAuthn (Hardware Keys & Passkeys)

**Configuration**:
```json
{
  "webAuthnPolicyRpEntityName": "Colink",
  "webAuthnPolicySignatureAlgorithms": ["ES256", "RS256"],
  "webAuthnPolicyRpId": "colink.dev",
  "webAuthnPolicyAttestationConveyancePreference": "none",
  "webAuthnPolicyAuthenticatorAttachment": "cross-platform",
  "webAuthnPolicyRequireResidentKey": "not required",
  "webAuthnPolicyUserVerificationRequirement": "required"
}
```

**Supported Devices**:
- YubiKey 5 Series
- Google Titan Security Key
- Touch ID / Face ID (passkeys)
- Windows Hello

---

### Token Management

#### Token Lifespans

| Token Type | Lifespan | Renewable | Storage |
|------------|----------|-----------|---------|
| Access Token | 1 hour | No | Client memory (never localStorage) |
| Refresh Token | 30 days | Yes (sliding window) | HttpOnly cookie or secure storage |
| ID Token | 1 hour | No | Client memory |
| SSO Session | 24 hours idle, 7 days max | Yes | Keycloak session |

#### Token Claims

**Access Token (JWT)**:

```json
{
  "exp": 1705587600,
  "iat": 1705584000,
  "jti": "a5f3c1e7-4b2d-4c8a-9f1e-3d7b6c5a4f3e",
  "iss": "https://keycloak.colink.dev/realms/colink",
  "aud": "api-gateway",
  "sub": "01HQZX8PQRS9TUV0WXY1Z2A3B4",
  "typ": "Bearer",
  "azp": "web-app",
  "session_state": "7e5d4c3b-2a1f-4e9d-8c7b-6a5f4e3d2c1b",
  "scope": "openid email profile",
  "email_verified": true,
  "preferred_username": "alice_smith",
  "email": "alice@colink.dev",
  "realm_access": {
    "roles": ["member", "admin"]
  }
}
```

**Key Claims**:
- `sub`: User ID (used throughout system)
- `preferred_username`: Username
- `email`: User email
- `realm_access.roles`: Array of roles for RBAC

---

### JWT Validation

#### Service-Side Validation Flow

```python
from jose import jwt, JWTError
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
import httpx

# Singleton JWKS cache
jwks_cache = {"keys": None, "expires_at": 0}

async def get_jwks():
    """Fetch and cache Keycloak JWKS (1-hour TTL)"""
    import time
    if time.time() < jwks_cache["expires_at"]:
        return jwks_cache["keys"]

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://keycloak.colink.dev/realms/colink/protocol/openid-connect/certs"
        )
        resp.raise_for_status()
        jwks_cache["keys"] = resp.json()
        jwks_cache["expires_at"] = time.time() + 3600
        return jwks_cache["keys"]

security = HTTPBearer()

async def get_current_user(credentials = Depends(security)):
    """Extract and validate JWT from Authorization header"""
    token = credentials.credentials
    try:
        jwks = await get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience="api-gateway",
            issuer="https://keycloak.colink.dev/realms/colink"
        )

        return {
            "user_id": payload["sub"],
            "username": payload["preferred_username"],
            "email": payload["email"],
            "roles": payload.get("realm_access", {}).get("roles", [])
        }
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Validation Steps**:
1. Extract token from `Authorization: Bearer {token}` header
2. Fetch JWKS from Keycloak (cached for 1 hour)
3. Verify signature using RS256 algorithm
4. Validate `exp` (expiration), `iss` (issuer), `aud` (audience)
5. Extract user claims (`sub`, `roles`, `email`)

---

## Authorization (RBAC)

### Role Hierarchy

```
admin
  ├── Full platform access
  ├── User management (deactivate/reactivate)
  ├── Message moderation (delete, flag)
  └── Audit log access

moderator
  ├── Message moderation (delete, flag)
  └── Channel management

member (default)
  ├── Create channels
  ├── Send messages
  ├── Upload files
  └── Search

guest (future)
  ├── Read public channels
  └── No create/edit permissions
```

### Role Enforcement

#### Decorator Pattern (FastAPI)

```python
from functools import wraps
from fastapi import HTTPException

def require_role(*roles: str):
    """Dependency to enforce role requirements"""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        user_roles = current_user.get("roles", [])
        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {', '.join(roles)}"
            )
        return current_user
    return role_checker

# Usage
@app.post("/admin/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    # Only admins can access this endpoint
    ...
```

### Resource Ownership

#### Message Edit Authorization

```python
@app.patch("/v1/messages/{message_id}")
async def update_message(
    message_id: str,
    update: UpdateMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Check ownership
    if message.sender_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check edit window (15 minutes)
    if (datetime.utcnow() - message.created_at).total_seconds() > 900:
        raise HTTPException(status_code=403, detail="Edit window expired")

    # Proceed with update
    ...
```

#### Channel Membership Authorization

```python
async def verify_channel_membership(
    channel_id: str,
    user_id: str,
    db: Session
) -> bool:
    """Check if user is a member of the channel"""
    member = db.query(ChannelMember).filter(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == user_id
    ).first()
    return member is not None

@app.post("/v1/messages")
async def create_message(
    request: CreateMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if request.channel_id:
        if not await verify_channel_membership(
            request.channel_id,
            current_user["user_id"],
            db
        ):
            raise HTTPException(status_code=403, detail="Not a channel member")

    # Proceed with message creation
    ...
```

---

## Input Validation

### Pydantic Models

```python
from pydantic import BaseModel, Field, validator, EmailStr
import re

class CreateMessageRequest(BaseModel):
    channel_id: Optional[str] = Field(
        None,
        regex=r'^[0-9A-HJKMNP-TV-Z]{26}$',  # ULID format
        description="Channel ID (required for channel messages)"
    )
    recipient_id: Optional[str] = Field(
        None,
        regex=r'^[0-9A-HJKMNP-TV-Z]{26}$',
        description="Recipient user ID (required for DMs)"
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Message text"
    )

    @validator('text')
    def sanitize_text(cls, v):
        """Strip dangerous HTML/JavaScript"""
        import bleach
        # Allow only safe tags (bold, italic, code)
        allowed_tags = ['b', 'i', 'code', 'pre', 'a']
        allowed_attrs = {'a': ['href']}
        return bleach.clean(v, tags=allowed_tags, attributes=allowed_attrs, strip=True)

    @validator('channel_id', 'recipient_id')
    def validate_target(cls, v, values):
        """Ensure exactly one target (channel OR recipient)"""
        channel_id = values.get('channel_id')
        recipient_id = values.get('recipient_id')
        if (channel_id and recipient_id) or (not channel_id and not recipient_id):
            raise ValueError('Must specify either channel_id or recipient_id')
        return v

class CreateUserRequest(BaseModel):
    email: EmailStr
    username: str = Field(
        ...,
        regex=r'^[a-z0-9_-]{3,30}$',
        description="Lowercase alphanumeric, hyphens, underscores"
    )
    display_name: str = Field(..., min_length=1, max_length=100)

    @validator('username')
    def no_reserved_usernames(cls, v):
        reserved = ['admin', 'system', 'bot', 'colink']
        if v in reserved:
            raise ValueError(f'Username "{v}" is reserved')
        return v
```

### SQL Injection Prevention

**Parameterized Queries** (SQLAlchemy):

```python
# ✅ SAFE: Parameterized query
db.query(User).filter(User.email == email).first()

# ❌ UNSAFE: String interpolation
db.execute(f"SELECT * FROM users WHERE email = '{email}'")

# ✅ SAFE: Named parameters
db.execute(
    "SELECT * FROM users WHERE email = :email",
    {"email": email}
)
```

---

## Rate Limiting

### Traefik Middleware (IP-based)

```yaml
# traefik/config/middlewares.yml
http:
  middlewares:
    rate-limit-global:
      rateLimit:
        average: 100
        burst: 200
        period: 1m
        sourceCriterion:
          ipStrategy:
            depth: 1  # Use X-Forwarded-For first IP

    rate-limit-auth:
      rateLimit:
        average: 5
        burst: 10
        period: 1m
```

### Application-Level (User-based)

```python
import redis
from datetime import datetime

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

async def check_rate_limit(
    user_id: str,
    limit: int = 100,
    window: int = 60
) -> bool:
    """
    Sliding window rate limiter using Redis

    Args:
        user_id: User identifier
        limit: Max requests per window
        window: Time window in seconds

    Returns:
        True if within limit, False otherwise
    """
    key = f"ratelimit:user:{user_id}"
    now = datetime.utcnow().timestamp()

    pipe = redis_client.pipeline()

    # Remove old entries outside window
    pipe.zremrangebyscore(key, 0, now - window)

    # Count requests in current window
    pipe.zcard(key)

    # Add current request
    pipe.zadd(key, {str(now): now})

    # Set expiry
    pipe.expire(key, window)

    results = pipe.execute()
    count = results[1]

    return count < limit

# FastAPI dependency
async def rate_limit_dependency(
    current_user: dict = Depends(get_current_user)
):
    if not await check_rate_limit(current_user["user_id"]):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": "60"}
        )
```

---

## Secrets Management

### Development (.env file)

```bash
# .env (NOT committed to git)
DATABASE_URL=postgresql://colink:dev_password@localhost:5432/colink
REDIS_URL=redis://localhost:6379/0
KAFKA_BROKERS=localhost:9092
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_CLIENT_SECRET=<random-secret>
JWT_ALGORITHM=RS256
```

**.env.example** (committed):
```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
REDIS_URL=redis://host:6379/0
...
```

### Production (Kubernetes Secrets)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: colink-secrets
  namespace: colink
type: Opaque
stringData:
  DATABASE_URL: postgresql://user:pass@postgres.svc.cluster.local:5432/colink
  REDIS_URL: redis://redis.svc.cluster.local:6379/0
  MINIO_ACCESS_KEY: <base64-encoded>
  MINIO_SECRET_KEY: <base64-encoded>
```

**Mount in Pod**:
```yaml
spec:
  containers:
  - name: messaging-service
    envFrom:
    - secretRef:
        name: colink-secrets
```

---

## CORS (Cross-Origin Resource Sharing)

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://colink.dev",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Trace-ID"
    ],
    expose_headers=["X-Total-Count", "ETag"],
    max_age=3600  # Cache preflight for 1 hour
)
```

---

## Audit Logging

### What to Log

| Event | Actor | Target | Metadata |
|-------|-------|--------|----------|
| User deactivated | admin_user_id | user_id | reason |
| Message moderated | moderator_user_id | message_id | action, reason |
| Channel created | user_id | channel_id | name, is_private |
| File uploaded | user_id | file_id | filename, size |
| Failed login | N/A | user_id | ip_address, reason |
| Role changed | admin_user_id | user_id | old_role, new_role |

### Audit Log Format (JSONL)

```json
{
  "timestamp": "2025-01-18T15:30:00Z",
  "trace_id": "abc123",
  "actor_id": "01HQZX0ADMIN001",
  "actor_ip": "192.168.1.100",
  "action": "user.deactivated",
  "target_type": "user",
  "target_id": "01HQZX8PQRS9TUV0WXY1Z2A3B4",
  "metadata": {
    "reason": "Policy violation",
    "previous_status": "active"
  }
}
```

### Storage & Retention

- **Postgres**: `audit_logs` table (90-day retention)
- **S3**: Long-term archive (7-year retention for compliance)
- **Search**: Index in OpenSearch for querying

---

## Security Headers

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Force HTTPS in production
if ENV == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# Prevent host header injection
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["colink.dev", "*.colink.dev"]
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

---

## Vulnerability Scanning

### Dependency Scanning

```bash
# Python dependencies
pip install safety
safety check --file requirements.txt

# Container images
docker scan colink/messaging-service:latest

# Trivy (comprehensive scanner)
trivy image colink/messaging-service:latest
```

### SAST (Static Application Security Testing)

```bash
# Bandit (Python security linter)
bandit -r src/ -f json -o bandit-report.json

# Semgrep
semgrep --config=auto src/
```

---

## Compliance Considerations

### GDPR (Future Multi-Tenant)

- **Right to Access**: Provide user data export API
- **Right to Erasure**: Hard delete user data (cascade to messages, files)
- **Data Portability**: Export in JSON format
- **Consent Management**: Track consent for email notifications

### SOC 2 (Future Enterprise)

- **Access Controls**: RBAC enforced
- **Audit Logging**: Comprehensive activity tracking
- **Encryption**: TLS in transit, optional encryption at rest
- **Incident Response**: Automated alerts for security events

---

## Next Steps

1. **Review Scalability Patterns**: [04-scalability-reliability.md](./04-scalability-reliability.md)
2. **Study Data Flows**: [02-data-flows.md](./02-data-flows.md)
3. **Explore API Contracts**: [../api-specs/](../api-specs/)
