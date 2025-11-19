# Auth Proxy Service - Testing Guide

This guide provides multiple ways to test the Auth Proxy Service endpoints.

## Prerequisites

- Auth Proxy service running on `http://localhost:8001`
- Test user created in Keycloak:
  - Username: `testuser`
  - Password: `testpass123`

## Method 1: Automated Test Script (Easiest)

Run the comprehensive automated test suite:

```bash
cd services/auth-proxy
python test_auth_apis.py
```

This tests all 9 endpoints and provides detailed output with pass/fail indicators.

---

## Method 2: Bash Script with cURL

Use the interactive bash script:

```bash
cd services/auth-proxy
./manual_test_guide.sh
```

This script demonstrates all API calls with formatted output and explanations.

---

## Method 3: Swagger UI (Most User-Friendly)

### Access Swagger UI
Open your browser and navigate to:
```
http://localhost:8001/docs
```

### Testing Workflow

#### 1. **Login**
- Click on `POST /auth/login`
- Click **"Try it out"**
- Enter request body:
  ```json
  {
    "username": "testuser",
    "password": "testpass123"
  }
  ```
- Click **"Execute"**
- **Copy the `access_token` and `refresh_token`** from the response

#### 2. **Get Current User Info**
- Click on `GET /auth/me`
- Click **"Try it out"**
- Click the **"Authorize"** button (🔒) at the top right
- In the dialog, enter:
  ```
  Bearer YOUR_ACCESS_TOKEN_HERE
  ```
  (Replace `YOUR_ACCESS_TOKEN_HERE` with the token from step 1)
- Click **"Authorize"**
- Close the dialog
- Click **"Execute"**
- You should see your user information

#### 3. **Refresh Token**
- Click on `POST /auth/refresh`
- Click **"Try it out"**
- Enter request body:
  ```json
  {
    "refresh_token": "YOUR_REFRESH_TOKEN_HERE"
  }
  ```
- Click **"Execute"**
- You'll receive new access and refresh tokens

#### 4. **Logout**
- Click on `POST /auth/logout`
- Click **"Try it out"**
- Enter request body:
  ```json
  {
    "refresh_token": "YOUR_REFRESH_TOKEN_HERE"
  }
  ```
- Click **"Execute"**
- This revokes your refresh token

#### 5. **Verify Revocation**
- Try using the refresh token from step 4 in `POST /auth/refresh`
- You should get a `401 Unauthorized` error

---

## Method 4: Manual cURL Commands

### Step-by-Step Testing

#### 1. Health Check
```bash
curl -X GET http://localhost:8001/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "auth-proxy",
  "timestamp": "2025-11-19T07:25:01.977513"
}
```

---

#### 2. Readiness Check
```bash
curl -X GET http://localhost:8001/health/ready
```

**Expected Response:**
```json
{
  "status": "ready",
  "service": "auth-proxy",
  "database": "connected",
  "timestamp": "2025-11-19T07:25:02.012676"
}
```

---

#### 3. Login
```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }'
```

**Expected Response:**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 300
}
```

**Save the tokens:**
```bash
# Copy access_token to use in next requests
ACCESS_TOKEN="eyJhbGci..."
REFRESH_TOKEN="eyJhbGci..."
```

---

#### 4. Get Current User Info
```bash
curl -X GET http://localhost:8001/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Expected Response:**
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

#### 5. Refresh Token
```bash
curl -X POST http://localhost:8001/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN\"
  }"
```

**Expected Response:**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 300
}
```

---

#### 6. Logout
```bash
curl -X POST http://localhost:8001/auth/logout \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN\"
  }"
```

**Expected Response:**
```json
{
  "message": "Logged out successfully"
}
```

---

#### 7. Verify Token Revocation
```bash
# Try to use the revoked refresh token
curl -X POST http://localhost:8001/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN\"
  }"
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Invalid or expired refresh token"
}
```

---

## Method 5: Using HTTPie (Alternative to cURL)

If you have HTTPie installed (`pip install httpie`):

### Login
```bash
http POST http://localhost:8001/auth/login \
  username=testuser \
  password=testpass123
```

### Get User Info
```bash
http GET http://localhost:8001/auth/me \
  "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Refresh Token
```bash
http POST http://localhost:8001/auth/refresh \
  refresh_token=YOUR_REFRESH_TOKEN
```

### Logout
```bash
http POST http://localhost:8001/auth/logout \
  refresh_token=YOUR_REFRESH_TOKEN
```

---

## Method 6: Using Postman

### Import the Collection

Create a new Postman collection with these requests:

#### 1. Login
- **Method:** POST
- **URL:** `http://localhost:8001/auth/login`
- **Headers:** `Content-Type: application/json`
- **Body (JSON):**
  ```json
  {
    "username": "testuser",
    "password": "testpass123"
  }
  ```
- **Test Script (to save tokens):**
  ```javascript
  var jsonData = pm.response.json();
  pm.environment.set("access_token", jsonData.access_token);
  pm.environment.set("refresh_token", jsonData.refresh_token);
  ```

#### 2. Get User Info
- **Method:** GET
- **URL:** `http://localhost:8001/auth/me`
- **Headers:** `Authorization: Bearer {{access_token}}`

#### 3. Refresh Token
- **Method:** POST
- **URL:** `http://localhost:8001/auth/refresh`
- **Headers:** `Content-Type: application/json`
- **Body (JSON):**
  ```json
  {
    "refresh_token": "{{refresh_token}}"
  }
  ```

#### 4. Logout
- **Method:** POST
- **URL:** `http://localhost:8001/auth/logout`
- **Headers:** `Content-Type: application/json`
- **Body (JSON):**
  ```json
  {
    "refresh_token": "{{refresh_token}}"
  }
  ```

---

## Testing Scenarios

### Scenario 1: Complete User Journey
1. User logs in → Receives tokens
2. User accesses protected resource (`/auth/me`) → Success
3. Access token expires → Use refresh token to get new access token
4. User logs out → Tokens are revoked
5. Try to use revoked token → Fails with 401

### Scenario 2: Token Expiration
1. Login and get access token
2. Wait for token to expire (5 minutes)
3. Try to access `/auth/me` → Should fail with 401
4. Use refresh token to get new access token
5. Access `/auth/me` with new token → Success

### Scenario 3: Invalid Credentials
1. Try to login with wrong password
2. Should receive 401 Unauthorized
3. Try to login with non-existent user
4. Should receive 401 Unauthorized

### Scenario 4: Invalid Token
1. Try to access `/auth/me` with malformed token
2. Should receive 401 Unauthorized
3. Try to access `/auth/me` without Authorization header
4. Should receive 403 Forbidden

---

## Verifying Database Changes

After running tests, you can verify the database was updated correctly:

```bash
docker exec colink-postgres psql -U colink -d colink -c \
  "SELECT username, email, created_at, updated_at, last_seen_at FROM users WHERE username = 'testuser';"
```

**What to look for:**
- `created_at`: Timestamp when user was first created (with timezone `+00`)
- `updated_at`: Timestamp when user record was last updated
- `last_seen_at`: Timestamp of last `/auth/me` or login request

All timestamps should have timezone information (e.g., `2025-11-19 07:25:02.099713+00`)

---

## Troubleshooting

### Service Not Running
```bash
docker-compose ps
```

If auth-proxy is not running:
```bash
docker-compose up -d auth-proxy
docker-compose logs -f auth-proxy
```

### Test User Doesn't Exist
Create test user in Keycloak:
1. Visit http://localhost:8080
2. Login with `admin` / `admin`
3. Select `colink` realm
4. Go to Users → Add User
5. Username: `testuser`
6. Email: `testuser@colink.local`
7. First Name: `Test`, Last Name: `User`
8. Save
9. Go to Credentials tab
10. Set password: `testpass123`
11. Turn off "Temporary"
12. Save

### Port Already in Use
If port 8001 is already in use, check `.env` file and modify `AUTH_PROXY_PORT`.

---

## Additional Resources

- **Swagger UI:** http://localhost:8001/docs
- **ReDoc:** http://localhost:8001/redoc
- **OpenAPI Schema:** http://localhost:8001/openapi.json
- **Health Check:** http://localhost:8001/health
- **Readiness Check:** http://localhost:8001/health/ready

---

## Expected Test Results

When all tests pass, you should see:

✅ **9/9 tests passed**

1. ✓ Health check endpoint
2. ✓ Readiness check with database
3. ✓ Login successful
4. ✓ Get user info
5. ✓ Token refresh
6. ✓ Logout
7. ✓ Token properly revoked
8. ✓ OpenAPI docs available
9. ✓ Swagger UI available
