#!/bin/bash

# Auth Proxy Manual Testing Guide
# This script demonstrates how to test all auth-proxy endpoints

BASE_URL="http://localhost:8001"

echo "=========================================="
echo "Auth Proxy Manual Testing Guide"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo -e "${YELLOW}TEST 1: Health Check${NC}"
echo "Command:"
echo "  curl -X GET $BASE_URL/health"
echo ""
echo "Response:"
curl -s -X GET "$BASE_URL/health" | jq '.'
echo ""
echo ""

# Test 2: Readiness Check
echo -e "${YELLOW}TEST 2: Readiness Check${NC}"
echo "Command:"
echo "  curl -X GET $BASE_URL/health/ready"
echo ""
echo "Response:"
curl -s -X GET "$BASE_URL/health/ready" | jq '.'
echo ""
echo ""

# Test 3: Login
echo -e "${YELLOW}TEST 3: Login${NC}"
echo "Command:"
echo "  curl -X POST $BASE_URL/auth/login \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"username\": \"testuser\", \"password\": \"testpass123\"}'"
echo ""
echo "Response:"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}')

echo "$LOGIN_RESPONSE" | jq '.'
echo ""

# Extract tokens
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.refresh_token')

if [ "$ACCESS_TOKEN" != "null" ]; then
  echo -e "${GREEN}✓ Login successful! Tokens saved.${NC}"
else
  echo -e "${RED}✗ Login failed!${NC}"
  exit 1
fi
echo ""
echo ""

# Test 4: Get Current User Info
echo -e "${YELLOW}TEST 4: Get Current User Info${NC}"
echo "Command:"
echo "  curl -X GET $BASE_URL/auth/me \\"
echo "    -H 'Authorization: Bearer \$ACCESS_TOKEN'"
echo ""
echo "Response:"
curl -s -X GET "$BASE_URL/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.'
echo ""
echo ""

# Test 5: Refresh Token
echo -e "${YELLOW}TEST 5: Refresh Token${NC}"
echo "Command:"
echo "  curl -X POST $BASE_URL/auth/refresh \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"refresh_token\": \"\$REFRESH_TOKEN\"}'"
echo ""
echo "Response:"
REFRESH_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")

echo "$REFRESH_RESPONSE" | jq '.'
echo ""

# Update tokens
NEW_ACCESS_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.access_token')
NEW_REFRESH_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.refresh_token')

if [ "$NEW_ACCESS_TOKEN" != "null" ]; then
  echo -e "${GREEN}✓ Token refresh successful!${NC}"
  ACCESS_TOKEN="$NEW_ACCESS_TOKEN"
  REFRESH_TOKEN="$NEW_REFRESH_TOKEN"
fi
echo ""
echo ""

# Test 6: Logout
echo -e "${YELLOW}TEST 6: Logout${NC}"
echo "Command:"
echo "  curl -X POST $BASE_URL/auth/logout \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"refresh_token\": \"\$REFRESH_TOKEN\"}'"
echo ""
echo "Response:"
curl -s -X POST "$BASE_URL/auth/logout" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" | jq '.'
echo ""
echo ""

# Test 7: Verify Token Revocation
echo -e "${YELLOW}TEST 7: Verify Token Revocation (should fail)${NC}"
echo "Command:"
echo "  curl -X POST $BASE_URL/auth/refresh \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"refresh_token\": \"\$REFRESH_TOKEN\"}'"
echo ""
echo "Response:"
curl -s -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" | jq '.'
echo ""
echo -e "${GREEN}✓ Token properly revoked (401 expected)${NC}"
echo ""
echo ""

echo "=========================================="
echo -e "${GREEN}Manual Testing Complete!${NC}"
echo "=========================================="
echo ""
echo "Additional Resources:"
echo "  - Swagger UI: http://localhost:8001/docs"
echo "  - ReDoc:      http://localhost:8001/redoc"
echo "  - OpenAPI:    http://localhost:8001/openapi.json"
echo ""
