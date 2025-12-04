# Superadmin Setup Guide

Quick guide to set up the superadmin user on your Colink instance.

## Quick Start

**Run this command inside Docker:**

```bash
docker exec colink-auth-proxy python /app/scripts/setup_superadmin.py
```

**That's it!** The superadmin user will be created with these credentials:

```
Username: superadmin
Email:    superadmin@colink.dev
Password: SuperAdmin@123
```

## Login

1. Go to `http://localhost:3000/login`
2. Click "Sign in with Keycloak"
3. Enter superadmin credentials
4. You'll be redirected to the admin dashboard at `/admin`

## What You Get

### Admin Dashboard (`/admin`)
- View all users in the system
- Delete users
- See user roles and status
- Manage system users

### Analytics Dashboard (`/analytics`)
Access from the sidebar or go to `http://localhost:3000/analytics`:
- Total users, channels, and messages
- Top 5 most active channels
- Daily message trends (last 7 days)
- Active users and engagement metrics

### Hidden from Regular Users
- Superadmin won't appear in Direct Messages lists
- Regular users can't initiate DMs with superadmin
- Automatic filtering from user searches

## Change Default Password

```bash
docker exec -e SUPERADMIN_PASSWORD="YourSecurePassword!" \
  colink-auth-proxy python /app/scripts/setup_superadmin.py
```

## Verify Setup

After running the script, you should see:

```
================================================
   ✓ Superadmin Setup Complete!
================================================

Superadmin Credentials:
  Username: superadmin
  Email:    superadmin@colink.dev
  Password: SuperAdmin@123

Access:
  1. Log in at: http://localhost:3000/login
  2. Admin Dashboard: http://localhost:3000/admin
  3. Analytics Dashboard: http://localhost:3000/analytics
```

## Troubleshooting

### Can't log in?
1. Clear browser cache and cookies
2. Verify superadmin exists: `docker exec colink-auth-proxy python /app/scripts/setup_superadmin.py`
3. Check password (default: `SuperAdmin@123`)

### Script fails?
1. Check services are running: `docker-compose ps`
2. Check auth-proxy logs: `docker logs colink-auth-proxy`
3. Ensure database is healthy: `docker exec colink-postgres pg_isready`

### Redirected to channels instead of admin?
This was fixed in recent commits. If you pulled new code:
1. Rebuild frontend: `docker-compose build frontend`
2. Restart: `docker-compose up -d frontend`
3. Hard refresh browser (Cmd+Shift+R or Ctrl+Shift+R)

## For New Installations

If you're setting up Colink on a new machine:

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd colink-slack-clone
   ```

2. **Start all services**
   ```bash
   docker-compose up -d
   ```

3. **Wait for services to be ready** (about 30-60 seconds)
   ```bash
   docker-compose ps
   ```

4. **Run superadmin setup**
   ```bash
   docker exec colink-auth-proxy python /app/scripts/setup_superadmin.py
   ```

5. **Access the application**
   - Frontend: `http://localhost:3000`
   - Admin Dashboard: `http://localhost:3000/admin`

## Recent Changes (Git Pull)

The recent commits you pulled include:

### ✨ New Features:
- **Analytics Dashboard** - Business intelligence and usage statistics
- **Theme Toggle** - Dark/light mode support
- **Grafana Monitoring** - Enhanced system monitoring
- **Enhanced Admin Features** - Improved user management

### ⚠️ Breaking Changes:
The `powerbi` commit modified auth routing logic. The superadmin setup scripts
account for these changes and ensure proper admin access control.

## Advanced Configuration

See `scripts/README.md` for:
- Environment variable customization
- Bash script alternative
- Detailed troubleshooting
- Security best practices

---

**Need help?** Check the detailed documentation in `scripts/README.md`
