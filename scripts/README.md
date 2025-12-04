# Superadmin Setup Scripts

This directory contains scripts to set up the superadmin user with admin privileges.

## Overview

The superadmin setup creates a special administrative user that:
- Has the `admin` role in the system
- Can access the Admin Dashboard at `/admin`
- Can access the Analytics Dashboard at `/analytics`
- Is **hidden from regular users' Direct Messages lists**
- Cannot access the regular channels interface (auto-redirected to admin dashboard)

## Scripts

### 1. Bash Script: `setup_superadmin.sh`

**Usage:**

```bash
# On host machine (requires jq and psql)
./scripts/setup_superadmin.sh

# Inside Docker container
docker exec colink-auth-proxy bash /app/scripts/setup_superadmin.sh
```

**Requirements:**
- `curl` - for API calls
- `jq` - for JSON parsing
- `psql` - PostgreSQL client

### 2. Python Script: `setup_superadmin.py` (Recommended)

**Usage:**

```bash
# On host machine
cd backend
python ../scripts/setup_superadmin.py

# Inside Docker container (recommended)
docker exec colink-auth-proxy python /app/scripts/setup_superadmin.py
```

**Requirements:**
- Python 3.11+
- `httpx` - HTTP client
- `sqlalchemy` - Database ORM
- All backend dependencies (installed in Docker)

## Default Superadmin Credentials

```
Username: superadmin
Email:    superadmin@colink.dev
Password: SuperAdmin@123
```

⚠️ **Security Note:** Change the default password in production by setting the `SUPERADMIN_PASSWORD` environment variable.

## What the Scripts Do

1. **Connect to Keycloak** - Get admin access token
2. **Check User Exists** - See if superadmin already exists in Keycloak
3. **Create User in Keycloak** - Create the user if it doesn't exist
4. **Update Database** - Create or update the user in PostgreSQL with `admin` role
5. **Verify Setup** - Confirm the user was created successfully

## Environment Variables

You can customize the setup using these environment variables:

```bash
# Keycloak Configuration
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=colink
KEYCLOAK_ADMIN_USER=admin
KEYCLOAK_ADMIN_PASSWORD=admin

# Superadmin Password (default: SuperAdmin@123)
SUPERADMIN_PASSWORD=YourSecurePassword

# Database Configuration (auto-detected from environment)
DATABASE_URL=postgresql+asyncpg://colink:colink_password@postgres:5432/colink
```

## Docker Usage Examples

### Run setup inside auth-proxy container:

```bash
docker exec colink-auth-proxy python /app/scripts/setup_superadmin.py
```

### Run with custom password:

```bash
docker exec -e SUPERADMIN_PASSWORD="MySecurePassword123!" \
  colink-auth-proxy python /app/scripts/setup_superadmin.py
```

## Superadmin Features

Once set up, the superadmin user has access to:

### 1. Admin Dashboard (`/admin`)
- View all users
- Delete users
- Manage user roles (future)
- System-wide user management

### 2. Analytics Dashboard (`/analytics`)
- Total users, channels, and messages
- Top 5 most active channels
- Daily message trends (last 7 days)
- Active users statistics
- Message activity metrics

### 3. Hidden from Regular Users
The superadmin is automatically filtered out from:
- Direct Messages sidebar for non-admin users
- User search results for regular members
- Default navigation (won't open DM with admin on login)

### 4. Role-Based Access Control
- Admin users are redirected to `/admin` instead of `/channels` on login
- Admin users cannot access `/channels` (auto-redirected to admin dashboard)
- Regular users cannot access `/admin` (access denied)

## Troubleshooting

### "Failed to get admin access token"
- Ensure Keycloak is running: `docker ps | grep keycloak`
- Check Keycloak admin credentials in environment variables
- Verify Keycloak URL is accessible

### "Failed to create user in Keycloak"
- User might already exist - script will update existing user
- Check Keycloak realm name is correct
- Verify admin token has proper permissions

### "Database error"
- Ensure PostgreSQL is running: `docker ps | grep postgres`
- Check database connection string
- Verify database credentials are correct

### Script runs but user can't log in
- Clear browser cache and cookies
- Check user exists in both Keycloak and database
- Verify password is correct (default: `SuperAdmin@123`)

## Integration with Recent Changes

### Analytics Dashboard (from powerbi commit)
The analytics dashboard at `/analytics` shows:
- User engagement metrics
- Channel activity
- Message trends
- System-wide statistics

### Theme Toggle (from theme commits)
The interface now supports dark/light theme toggling:
- Theme switch in ChannelHeader
- Persistent theme preference
- Works across all pages including admin dashboard

### Grafana Monitoring (from grafana commit)
Enhanced monitoring capabilities:
- Pre-configured Grafana dashboard
- System metrics visualization
- Performance monitoring

## Migration from Previous Superadmin Setup

If you previously set up a superadmin manually, this script will:
1. Detect the existing user in Keycloak
2. Update the database record to ensure `role = 'admin'`
3. Verify the setup is correct

No data loss will occur - the script safely updates existing users.

## Security Best Practices

1. **Change Default Password** - Always set a strong `SUPERADMIN_PASSWORD`
2. **Limit Admin Access** - Only trusted personnel should have admin credentials
3. **Monitor Admin Actions** - Review admin dashboard usage regularly
4. **Use HTTPS** - In production, always use HTTPS for the frontend
5. **Secure Keycloak** - Change default Keycloak admin credentials

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the script output for error messages
3. Check Docker logs: `docker logs colink-auth-proxy`
4. Verify all services are running: `docker-compose ps`

---

**Last Updated:** December 3, 2025
**Compatible with:** Colink v1.0.0+
