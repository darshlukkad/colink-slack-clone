# Auth Proxy - Quick Test Reference

## Quick Start

### Option 1: Automated Testing (Recommended)
```bash
cd services/auth-proxy
python test_auth_apis.py
```

### Option 2: Bash Script
```bash
cd services/auth-proxy
./manual_test_guide.sh
```

### Option 3: Swagger UI
```
http://localhost:8001/docs
```

---

## Manual cURL Commands (Copy & Paste)

### 1. Login
```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}' | jq '.'
```

### 2. Get User Info
**First, save your access token:**
```bash
ACCESS_TOKEN="paste_your_token_here"
```

**Then get user info:**
```bash
curl -X GET http://localhost:8001/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.'
```

### 3. Refresh Token
**First, save your refresh token:**
```bash
REFRESH_TOKEN="paste_your_token_here"
```

**Then refresh:**
```bash
curl -X POST http://localhost:8001/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" | jq '.'
```

### 4. Logout
```bash
curl -X POST http://localhost:8001/auth/logout \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" | jq '.'
```

---

## One-Liner Test Flow

Save and execute all tokens automatically:

```bash
# Login and save tokens
LOGIN_RESP=$(curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}')

ACCESS_TOKEN=$(echo $LOGIN_RESP | jq -r '.access_token')
REFRESH_TOKEN=$(echo $LOGIN_RESP | jq -r '.refresh_token')

# Get user info
curl -s -X GET http://localhost:8001/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.'

# Refresh token
curl -s -X POST http://localhost:8001/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" | jq '.'

# Logout
curl -s -X POST http://localhost:8001/auth/logout \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" | jq '.'
```

---

## Health Checks

```bash
# Basic health
curl http://localhost:8001/health | jq '.'

# Readiness (includes database check)
curl http://localhost:8001/health/ready | jq '.'
```

---

## Verify Database

```bash
docker exec colink-postgres psql -U colink -d colink -c \
  "SELECT username, email, created_at, updated_at, last_seen_at FROM users WHERE username = 'testuser';"
```

---

## Service Management

```bash
# View logs
docker-compose logs -f auth-proxy

# Restart service
docker-compose restart auth-proxy

# Rebuild and restart
docker-compose build auth-proxy && docker-compose up -d auth-proxy
```

---

## Expected Results

### Successful Login Response
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 300
}
```

### Successful User Info Response
```json
{
  "id": "a7f040c6-1cdf-4c26-aacb-5d147172afaf",
  "username": "testuser",
  "email": "testuser@colink.local",
  "display_name": "Test User",
  "avatar_url": null,
  "role": "member",
  "status": "active"
}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` | Check if service is running: `docker-compose ps` |
| `401 Unauthorized` on login | Verify test user exists in Keycloak |
| `403 Forbidden` on /auth/me | Check Authorization header format: `Bearer TOKEN` |
| `jq: command not found` | Install jq: `brew install jq` (Mac) or remove `| jq '.'` |

---

## Quick Links

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc
- Keycloak Admin: http://localhost:8080 (admin/admin)
