# Auth Proxy API Testing Guide

This guide provides multiple ways to test the auth-proxy service APIs.

## Prerequisites

Before testing, you need to create a test user in Keycloak:

1. Visit Keycloak Admin Console: http://localhost:8080
2. Login with credentials: `admin` / `admin`
3. Select the `colink` realm (dropdown in top-left)
4. Go to **Users** → **Add user**
5. Create a user:
   - Username: `testuser`
   - Email: `testuser@colink.local`
   - First Name: `Test`
   - Last Name: `User`
   - Email Verified: `ON`
   - Click **Create**
6. Set password:
   - Go to **Credentials** tab
   - Click **Set Password**
   - Password: `testpass123`
   - Temporary: `OFF`
   - Click **Save**

## Method 1: Interactive Web UI (Easiest)

Visit the auto-generated API documentation:

### Swagger UI
```bash
open http://localhost:8001/docs
```

**Features:**
- Interactive API testing
- Try out each endpoint directly in your browser
- See request/response schemas
- Built-in authentication

**Steps:**
1. Click on `/auth/login` → **Try it out**
2. Enter credentials:
   ```json
   {
     "username": "testuser",
     "password": "testpass123"
   }
   ```
3. Click **Execute**
4. Copy the `access_token` from the response
5. Click **Authorize** button at the top
6. Paste token in format: `Bearer <your_token>`
7. Now you can test authenticated endpoints like `/auth/me`

### ReDoc (Alternative)
```bash
open http://localhost:8001/redoc
```

- Read-only, better for documentation
- Clean, three-panel layout
- Better for understanding API structure

## Method 2: Automated Testing Scripts

### Python Script (Recommended)

```bash
# Run with default credentials
python3 services/auth-proxy/test_auth_apis.py

# Or with custom credentials
TEST_USERNAME=myuser TEST_PASSWORD=mypass python3 services/auth-proxy/test_auth_apis.py
```

**Features:**
- Comprehensive test coverage
- Colored output
- Automatic token management
- Detailed request/response logging

### Bash Script (Alternative)

```bash
# Run with default credentials
./services/auth-proxy/test_auth_apis.sh

# Or with custom credentials
TEST_USERNAME=myuser TEST_PASSWORD=mypass ./services/auth-proxy/test_auth_apis.sh
```

## Method 3: Manual cURL Commands

### 1. Health Check
```bash
curl http://localhost:8001/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "auth-proxy",
  "timestamp": "2025-11-19T06:30:00.000000"
}
```

### 2. Readiness Check
```bash
curl http://localhost:8001/health/ready
```

Expected response:
```json
{
  "status": "ready",
  "service": "auth-proxy",
  "database": "connected",
  "timestamp": "2025-11-19T06:30:00.000000"
}
```

### 3. Login
```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }'
```

Expected response:
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Save the tokens for next steps:**
```bash
# Extract and save tokens
export ACCESS_TOKEN=$(curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

export REFRESH_TOKEN=$(curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['refresh_token'])")

echo "Tokens saved!"
```

### 4. Get Current User Info
```bash
curl http://localhost:8001/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Expected response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "testuser",
  "email": "testuser@colink.local",
  "display_name": "Test User",
  "avatar_url": null,
  "role": "MEMBER",
  "status": "ACTIVE"
}
```

### 5. Refresh Access Token
```bash
curl -X POST http://localhost:8001/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
```

### 6. Logout
```bash
curl -X POST http://localhost:8001/auth/logout \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
```

Expected response:
```json
{
  "message": "Logged out successfully"
}
```

## Method 4: Using HTTPie (Prettier Alternative to cURL)

Install HTTPie:
```bash
# macOS
brew install httpie

# Ubuntu/Debian
sudo apt install httpie

# pip
pip install httpie
```

### Examples:

```bash
# Health check
http GET localhost:8001/health

# Login
http POST localhost:8001/auth/login username=testuser password=testpass123

# Get user info
http GET localhost:8001/auth/me Authorization:"Bearer $ACCESS_TOKEN"

# Refresh token
http POST localhost:8001/auth/refresh refresh_token="$REFRESH_TOKEN"

# Logout
http POST localhost:8001/auth/logout refresh_token="$REFRESH_TOKEN"
```

## Method 5: Using Postman

1. **Import OpenAPI spec:**
   - Open Postman
   - File → Import → Link
   - Enter: `http://localhost:8001/openapi.json`
   - Click Import

2. **Create environment:**
   - Click Environments
   - Create new environment "Auth Proxy Local"
   - Add variables:
     - `base_url`: `http://localhost:8001`
     - `access_token`: (will be set automatically)
     - `refresh_token`: (will be set automatically)

3. **Test endpoints:**
   - Use the imported collection
   - Set up "Tests" tab to automatically save tokens:
     ```javascript
     if (pm.response.code === 200) {
         const json = pm.response.json();
         if (json.access_token) {
             pm.environment.set("access_token", json.access_token);
         }
         if (json.refresh_token) {
             pm.environment.set("refresh_token", json.refresh_token);
         }
     }
     ```

## Testing Checklist

- [ ] Health check returns healthy status
- [ ] Readiness check shows database connected
- [ ] Login with valid credentials returns tokens
- [ ] Login with invalid credentials returns 401
- [ ] Get user info with valid token returns user data
- [ ] Get user info without token returns 401
- [ ] Refresh token returns new access token
- [ ] Logout revokes refresh token
- [ ] Using revoked token fails
- [ ] OpenAPI docs are accessible
- [ ] Swagger UI is accessible

## Common Issues

### 1. Login fails with 401
- Verify user exists in Keycloak
- Check username/password are correct
- Ensure Keycloak service is running: `docker-compose ps keycloak`

### 2. "Service unavailable" errors
- Check if auth-proxy is running: `docker-compose ps auth-proxy`
- Check logs: `docker-compose logs auth-proxy`
- Verify Keycloak is accessible: `curl http://localhost:8080`

### 3. Database connection errors
- Ensure PostgreSQL is running: `docker-compose ps postgres`
- Check database health: `docker-compose exec postgres pg_isready`

### 4. Token validation fails
- Check Keycloak realm is "colink"
- Verify Keycloak URL is accessible from the container
- Check logs for JWKS errors: `docker-compose logs auth-proxy`

## Additional Resources

- **API Documentation**: http://localhost:8001/docs
- **ReDoc Documentation**: http://localhost:8001/redoc
- **OpenAPI Spec**: http://localhost:8001/openapi.json
- **Keycloak Admin**: http://localhost:8080
- **Service Logs**: `docker-compose logs -f auth-proxy`

## Next Steps

After testing the auth-proxy service, you can:

1. Integrate it with the frontend application
2. Implement rate limiting
3. Add request logging and monitoring
4. Set up automated integration tests
5. Configure production Keycloak realm
