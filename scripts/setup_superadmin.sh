#!/bin/bash

###############################################################################
# Superadmin Setup Script
#
# This script creates a superadmin user with admin privileges in both
# Keycloak and the PostgreSQL database.
#
# Usage:
#   ./scripts/setup_superadmin.sh
#
# Or inside Docker:
#   docker exec colink-auth-proxy bash /app/scripts/setup_superadmin.sh
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   Colink Superadmin Setup Script${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Configuration
KEYCLOAK_URL="${KEYCLOAK_URL:-http://keycloak:8080}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-colink}"
KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-colink-client}"
KEYCLOAK_ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-admin}"

# Superadmin user details
SUPERADMIN_USERNAME="superadmin"
SUPERADMIN_EMAIL="superadmin@colink.dev"
SUPERADMIN_PASSWORD="${SUPERADMIN_PASSWORD:-SuperAdmin@123}"
SUPERADMIN_DISPLAY_NAME="Super Admin"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Keycloak URL: $KEYCLOAK_URL"
echo "  Realm: $KEYCLOAK_REALM"
echo "  Username: $SUPERADMIN_USERNAME"
echo "  Email: $SUPERADMIN_EMAIL"
echo ""

# Step 1: Get Keycloak admin access token
echo -e "${BLUE}[1/5]${NC} Getting Keycloak admin access token..."
ADMIN_TOKEN=$(curl -s -X POST \
  "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$KEYCLOAK_ADMIN_USER" \
  -d "password=$KEYCLOAK_ADMIN_PASSWORD" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | jq -r '.access_token')

if [ -z "$ADMIN_TOKEN" ] || [ "$ADMIN_TOKEN" = "null" ]; then
  echo -e "${RED}❌ Failed to get admin access token${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Admin token acquired${NC}"

# Step 2: Check if superadmin user already exists in Keycloak
echo -e "${BLUE}[2/5]${NC} Checking if superadmin user exists in Keycloak..."
EXISTING_USER=$(curl -s -X GET \
  "$KEYCLOAK_URL/admin/realms/$KEYCLOAK_REALM/users?username=$SUPERADMIN_USERNAME&exact=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json")

USER_ID=$(echo "$EXISTING_USER" | jq -r '.[0].id // empty')

if [ -n "$USER_ID" ]; then
  echo -e "${YELLOW}⚠ User already exists in Keycloak (ID: $USER_ID)${NC}"
  KEYCLOAK_USER_ID=$USER_ID
else
  # Step 3: Create superadmin user in Keycloak
  echo -e "${BLUE}[3/5]${NC} Creating superadmin user in Keycloak..."

  CREATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    "$KEYCLOAK_URL/admin/realms/$KEYCLOAK_REALM/users" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "username": "'"$SUPERADMIN_USERNAME"'",
      "email": "'"$SUPERADMIN_EMAIL"'",
      "enabled": true,
      "emailVerified": true,
      "firstName": "Super",
      "lastName": "Admin",
      "credentials": [{
        "type": "password",
        "value": "'"$SUPERADMIN_PASSWORD"'",
        "temporary": false
      }]
    }')

  HTTP_CODE=$(echo "$CREATE_RESPONSE" | tail -n1)

  if [ "$HTTP_CODE" = "201" ]; then
    echo -e "${GREEN}✓ Superadmin user created in Keycloak${NC}"

    # Get the created user's ID
    KEYCLOAK_USER_ID=$(curl -s -X GET \
      "$KEYCLOAK_URL/admin/realms/$KEYCLOAK_REALM/users?username=$SUPERADMIN_USERNAME&exact=true" \
      -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.[0].id')
  else
    echo -e "${RED}❌ Failed to create user in Keycloak (HTTP $HTTP_CODE)${NC}"
    exit 1
  fi
fi

echo "  Keycloak User ID: $KEYCLOAK_USER_ID"

# Step 4: Update user in PostgreSQL database
echo -e "${BLUE}[4/5]${NC} Creating/updating superadmin user in PostgreSQL..."

# Check if running inside Docker or on host
if [ -f "/.dockerenv" ]; then
  # Inside Docker container
  PGHOST="${DATABASE_HOST:-postgres}"
  PGPORT="${DATABASE_PORT:-5432}"
  PGDATABASE="${DATABASE_NAME:-colink}"
  PGUSER="${DATABASE_USER:-colink}"
  PGPASSWORD="${DATABASE_PASSWORD:-colink_password}"
else
  # On host machine
  PGHOST="${DATABASE_HOST:-localhost}"
  PGPORT="${DATABASE_PORT:-5432}"
  PGDATABASE="${DATABASE_NAME:-colink}"
  PGUSER="${DATABASE_USER:-colink}"
  PGPASSWORD="${DATABASE_PASSWORD:-colink_password}"
fi

export PGPASSWORD

# SQL query to upsert superadmin user
SQL_QUERY="
INSERT INTO users (id, keycloak_id, username, email, display_name, role, status, created_at, last_seen_at)
VALUES (
  gen_random_uuid(),
  '$KEYCLOAK_USER_ID',
  '$SUPERADMIN_USERNAME',
  '$SUPERADMIN_EMAIL',
  '$SUPERADMIN_DISPLAY_NAME',
  'admin',
  'active',
  NOW(),
  NOW()
)
ON CONFLICT (keycloak_id)
DO UPDATE SET
  username = EXCLUDED.username,
  email = EXCLUDED.email,
  display_name = EXCLUDED.display_name,
  role = 'admin',
  status = 'active',
  last_seen_at = NOW();
"

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "$SQL_QUERY" > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Superadmin user created/updated in database${NC}"
else
  echo -e "${RED}❌ Failed to update database${NC}"
  exit 1
fi

# Step 5: Verify the setup
echo -e "${BLUE}[5/5]${NC} Verifying superadmin setup..."

VERIFY_QUERY="SELECT username, email, role, status FROM users WHERE keycloak_id = '$KEYCLOAK_USER_ID';"
VERIFY_RESULT=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c "$VERIFY_QUERY")

if [ -n "$VERIFY_RESULT" ]; then
  echo -e "${GREEN}✓ Verification successful${NC}"
  echo ""
  echo -e "${GREEN}Database record:${NC}"
  echo "$VERIFY_RESULT"
else
  echo -e "${YELLOW}⚠ Could not verify database record${NC}"
fi

# Display success message
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}   ✓ Superadmin Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${YELLOW}Superadmin Credentials:${NC}"
echo "  Username: $SUPERADMIN_USERNAME"
echo "  Email:    $SUPERADMIN_EMAIL"
echo "  Password: $SUPERADMIN_PASSWORD"
echo ""
echo -e "${YELLOW}Access:${NC}"
echo "  1. Log in at: http://localhost:3000/login"
echo "  2. Admin Dashboard: http://localhost:3000/admin"
echo "  3. Analytics Dashboard: http://localhost:3000/analytics"
echo ""
echo -e "${BLUE}Note: The superadmin user will be hidden from regular users' DM lists${NC}"
echo ""
