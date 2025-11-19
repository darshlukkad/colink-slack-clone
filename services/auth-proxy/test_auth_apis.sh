#!/bin/bash
# Auth Proxy API Testing Script
# This script tests all endpoints of the auth-proxy service

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AUTH_PROXY_URL="http://localhost:8001"
KEYCLOAK_URL="http://localhost:8080"
REALM="colink"

# Test credentials (you'll need to create a test user in Keycloak)
TEST_USERNAME="${TEST_USERNAME:-testuser}"
TEST_PASSWORD="${TEST_PASSWORD:-testpass123}"

echo -e "${YELLOW}==================================================${NC}"
echo -e "${YELLOW}Auth Proxy API Test Suite${NC}"
echo -e "${YELLOW}==================================================${NC}"
echo ""

# Function to print test results
print_test() {
    local test_name=$1
    local status=$2
    if [ "$status" -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $test_name"
    else
        echo -e "${RED}✗${NC} $test_name"
    fi
}

# Function to make HTTP request and show response
make_request() {
    local method=$1
    local endpoint=$2
    local data=$3
    local headers=$4

    echo -e "\n${YELLOW}Request:${NC} $method $endpoint"
    if [ -n "$data" ]; then
        echo -e "${YELLOW}Data:${NC} $data"
    fi

    if [ -n "$headers" ]; then
        response=$(curl -s -X "$method" "$AUTH_PROXY_URL$endpoint" \
            -H "Content-Type: application/json" \
            $headers \
            ${data:+-d "$data"})
    else
        response=$(curl -s -X "$method" "$AUTH_PROXY_URL$endpoint" \
            -H "Content-Type: application/json" \
            ${data:+-d "$data"})
    fi

    echo -e "${YELLOW}Response:${NC}"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    echo "$response"
}

# Test 1: Health Check
echo -e "\n${YELLOW}[TEST 1]${NC} Health Check"
response=$(make_request "GET" "/health")
if echo "$response" | grep -q "healthy"; then
    print_test "Health check" 0
else
    print_test "Health check" 1
fi

# Test 2: Readiness Check
echo -e "\n${YELLOW}[TEST 2]${NC} Readiness Check"
response=$(make_request "GET" "/health/ready")
if echo "$response" | grep -q "ready"; then
    print_test "Readiness check" 0
else
    print_test "Readiness check" 1
fi

# Test 3: Login (requires test user in Keycloak)
echo -e "\n${YELLOW}[TEST 3]${NC} Login"
echo -e "${YELLOW}Note:${NC} This requires a test user in Keycloak"
echo -e "${YELLOW}Username:${NC} $TEST_USERNAME"
echo -e "${YELLOW}Password:${NC} $TEST_PASSWORD"

login_data="{\"username\":\"$TEST_USERNAME\",\"password\":\"$TEST_PASSWORD\"}"
response=$(make_request "POST" "/auth/login" "$login_data")

if echo "$response" | grep -q "access_token"; then
    print_test "Login successful" 0

    # Extract tokens
    ACCESS_TOKEN=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
    REFRESH_TOKEN=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['refresh_token'])" 2>/dev/null)

    echo -e "${GREEN}Access token saved${NC}"
    echo -e "${GREEN}Refresh token saved${NC}"
else
    print_test "Login failed" 1
    echo -e "${RED}Cannot continue with authenticated tests${NC}"
    echo -e "${YELLOW}Please create a test user in Keycloak:${NC}"
    echo -e "1. Visit http://localhost:8080"
    echo -e "2. Login with admin/admin"
    echo -e "3. Go to 'colink' realm"
    echo -e "4. Create user: $TEST_USERNAME with password: $TEST_PASSWORD"
    exit 1
fi

# Test 4: Get Current User Info
echo -e "\n${YELLOW}[TEST 4]${NC} Get Current User Info"
response=$(make_request "GET" "/auth/me" "" "-H \"Authorization: Bearer $ACCESS_TOKEN\"")
if echo "$response" | grep -q "username"; then
    print_test "Get user info" 0
else
    print_test "Get user info" 1
fi

# Test 5: Refresh Token
echo -e "\n${YELLOW}[TEST 5]${NC} Refresh Token"
refresh_data="{\"refresh_token\":\"$REFRESH_TOKEN\"}"
response=$(make_request "POST" "/auth/refresh" "$refresh_data")
if echo "$response" | grep -q "access_token"; then
    print_test "Token refresh" 0

    # Update access token
    ACCESS_TOKEN=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
    echo -e "${GREEN}New access token obtained${NC}"
else
    print_test "Token refresh" 1
fi

# Test 6: Logout
echo -e "\n${YELLOW}[TEST 6]${NC} Logout"
logout_data="{\"refresh_token\":\"$REFRESH_TOKEN\"}"
response=$(make_request "POST" "/auth/logout" "$logout_data")
if echo "$response" | grep -q "Logged out"; then
    print_test "Logout" 0
else
    print_test "Logout" 1
fi

# Test 7: Try to use old refresh token (should fail)
echo -e "\n${YELLOW}[TEST 7]${NC} Verify token revocation (should fail)"
response=$(make_request "POST" "/auth/refresh" "$refresh_data")
if echo "$response" | grep -q "access_token"; then
    print_test "Token properly revoked" 1
    echo -e "${RED}Warning: Token was not revoked!${NC}"
else
    print_test "Token properly revoked" 0
fi

# Test 8: OpenAPI Documentation
echo -e "\n${YELLOW}[TEST 8]${NC} OpenAPI Documentation"
response=$(curl -s "$AUTH_PROXY_URL/openapi.json")
if echo "$response" | grep -q "openapi"; then
    print_test "OpenAPI docs available" 0
else
    print_test "OpenAPI docs available" 1
fi

# Test 9: Swagger UI
echo -e "\n${YELLOW}[TEST 9]${NC} Swagger UI"
response=$(curl -s "$AUTH_PROXY_URL/docs")
if echo "$response" | grep -q "swagger-ui"; then
    print_test "Swagger UI available" 0
else
    print_test "Swagger UI available" 1
fi

# Summary
echo -e "\n${YELLOW}==================================================${NC}"
echo -e "${YELLOW}Test Suite Complete!${NC}"
echo -e "${YELLOW}==================================================${NC}"
echo -e "\n${GREEN}Interactive API Documentation:${NC}"
echo -e "  Swagger UI: http://localhost:8001/docs"
echo -e "  ReDoc:      http://localhost:8001/redoc"
echo -e "\n${GREEN}Available Endpoints:${NC}"
echo -e "  GET  /health         - Health check"
echo -e "  GET  /health/ready   - Readiness check"
echo -e "  POST /auth/login     - Login with credentials"
echo -e "  POST /auth/refresh   - Refresh access token"
echo -e "  POST /auth/logout    - Logout and revoke token"
echo -e "  GET  /auth/me        - Get current user info"
echo ""