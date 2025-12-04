# AWS Deployment Guide for Colink

Complete guide for deploying Colink on AWS EC2 instances.

---

## Quick Start

### 1. Launch EC2 Instance

**Recommended Instance Type**: `t3.large` or better
- **vCPUs**: 2+
- **RAM**: 8GB+
- **Storage**: 30GB+ SSD

**AMI**: Amazon Linux 2023 or Amazon Linux 2

### 2. Configure Security Group

Allow the following inbound ports:

| Port | Service | Description |
|------|---------|-------------|
| 22 | SSH | Server management |
| 3000 | Frontend | Main application UI |
| 8001 | Auth Proxy | Authentication API |
| 8002 | Message Service | Messaging API |
| 8003 | Channel Service | Channel API |
| 8080 | Keycloak | Identity provider |
| 9001 | MinIO Console | Object storage UI |
| 3001 | Grafana | Metrics dashboard |
| 9090 | Prometheus | Metrics API |

**Security Group Rules Example**:
```
Type: Custom TCP
Protocol: TCP
Port Range: 3000, 8001-8003, 8080, 9001, 3001, 9090
Source: 0.0.0.0/0 (or your IP range for better security)
```

### 3. Connect to Your Instance

```bash
ssh -i your-key.pem ec2-user@your-instance-ip
```

### 4. Download and Run Deployment Script

```bash
# Download the script
wget https://raw.githubusercontent.com/yourorg/colink-slack-clone/main/scripts/aws-deploy.sh

# Make it executable
chmod +x aws-deploy.sh

# Run the script (requires sudo)
sudo ./aws-deploy.sh
```

The script will:
- ✅ Install all dependencies (Docker, Node.js, etc.)
- ✅ Clone the repository
- ✅ Configure environment variables
- ✅ Build all Docker images
- ✅ Start all services
- ✅ Create superadmin user
- ✅ Set up systemd service
- ✅ Configure log rotation

**Estimated Time**: 15-20 minutes

---

## Manual Deployment (Alternative)

If you prefer manual deployment or need more control:

### Step 1: Update System and Install Dependencies

```bash
# Update system
sudo yum update -y

# Install Docker
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker

# Install Docker Compose
sudo curl -SL "https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64" \
    -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Node.js 18.x
curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo yum install -y nodejs

# Install Git
sudo yum install -y git
```

### Step 2: Clone Repository

```bash
# Clone to /opt/colink
sudo mkdir -p /opt/colink
sudo git clone https://github.com/yourorg/colink-slack-clone.git /opt/colink
cd /opt/colink
```

### Step 3: Configure Environment

```bash
# Get your public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

# Create .env file
cat > .env <<EOF
# Update these URLs with your actual IP or domain
NEXT_PUBLIC_AUTH_PROXY_URL=http://${PUBLIC_IP}:8001
NEXT_PUBLIC_CHANNEL_SERVICE_URL=http://${PUBLIC_IP}:8003
NEXT_PUBLIC_MESSAGE_SERVICE_URL=http://${PUBLIC_IP}:8002
NEXT_PUBLIC_THREADS_SERVICE_URL=http://${PUBLIC_IP}:8005
NEXT_PUBLIC_REACTIONS_SERVICE_URL=http://${PUBLIC_IP}:8006
NEXT_PUBLIC_FILES_SERVICE_URL=http://${PUBLIC_IP}:8007
NEXT_PUBLIC_NOTIFICATIONS_SERVICE_URL=http://${PUBLIC_IP}:8008
NEXT_PUBLIC_WEBSOCKET_URL=http://${PUBLIC_IP}:8009
NEXT_PUBLIC_KEYCLOAK_URL=http://${PUBLIC_IP}:8080
NEXT_PUBLIC_KEYCLOAK_REALM=colink
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=web-app

# Database credentials (change these!)
POSTGRES_USER=colink_user
POSTGRES_PASSWORD=$(openssl rand -base64 32)
POSTGRES_DB=colink_db

# Generate secure passwords
JWT_SECRET=$(openssl rand -base64 64)
KEYCLOAK_ADMIN_PASSWORD=$(openssl rand -base64 24)
MINIO_ROOT_PASSWORD=$(openssl rand -base64 24)
EOF
```

### Step 4: Build and Start

```bash
# Build all services
sudo docker-compose build --parallel

# Start all services
sudo docker-compose up -d

# Wait for services to be ready (2-3 minutes)
sleep 120
```

### Step 5: Create Superadmin

```bash
# Create superadmin user
sudo docker-compose exec auth-proxy python /app/scripts/setup_superadmin.py
```

### Step 6: Verify Deployment

```bash
# Check service status
sudo docker-compose ps

# Check logs
sudo docker-compose logs -f

# Test frontend
curl http://localhost:3000

# Test API
curl http://localhost:8001/health
```

---

## Configuration

### Custom Domain Setup

If you have a domain name:

1. **Point your domain to the EC2 instance**:
   - Create an A record pointing to your instance's Elastic IP

2. **Update .env file**:
   ```bash
   # Replace all http://YOUR_IP:PORT with your domain
   NEXT_PUBLIC_AUTH_PROXY_URL=https://api.yourdomain.com
   NEXT_PUBLIC_KEYCLOAK_URL=https://auth.yourdomain.com
   # etc...
   ```

3. **Set up SSL/TLS** (recommended):
   - Use AWS Certificate Manager (ACM) with Application Load Balancer (ALB)
   - Or use Let's Encrypt with Nginx/Traefik reverse proxy

### Environment Variables

Key environment variables you may want to customize:

```bash
# Superadmin credentials
SUPERADMIN_USERNAME=admin
SUPERADMIN_EMAIL=admin@yourdomain.com
SUPERADMIN_PASSWORD=YourSecurePassword123!

# Database
POSTGRES_USER=colink_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=colink_db

# Redis (optional authentication)
REDIS_PASSWORD=your_redis_password

# JWT signing key
JWT_SECRET=your_jwt_secret_key

# Keycloak admin
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=your_keycloak_password

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password
```

---

## Post-Deployment Tasks

### 1. Change Default Passwords

```bash
# Update .env file with secure passwords
sudo vim /opt/colink/.env

# Restart services
cd /opt/colink
sudo docker-compose restart
```

### 2. Set Up Backups

**PostgreSQL Backup**:
```bash
# Create backup script
cat > /opt/colink/backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/colink/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker-compose exec -T postgres pg_dump -U colink_user colink_db > "$BACKUP_DIR/colink_db_$DATE.sql"

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete

echo "Backup completed: colink_db_$DATE.sql"
EOF

chmod +x /opt/colink/backup.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /opt/colink/backup.sh" | sudo crontab -
```

**Sync to S3** (optional):
```bash
# Install AWS CLI
sudo yum install -y aws-cli

# Configure AWS credentials
aws configure

# Sync backups to S3
aws s3 sync /opt/colink/backups s3://your-backup-bucket/colink-backups/
```

### 3. Set Up Monitoring

**CloudWatch Logs** (optional):
```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
sudo rpm -U ./amazon-cloudwatch-agent.rpm

# Configure to send Docker logs to CloudWatch
# Follow AWS documentation for detailed setup
```

### 4. Configure Grafana

1. Access Grafana: `http://your-ip:3001`
2. Login with `admin` / `admin`
3. Change default password
4. Add Prometheus data source: `http://prometheus:9090`
5. Import dashboard from `monitoring/grafana-dashboard.json`

### 5. Configure Keycloak

1. Access Keycloak: `http://your-ip:8080/admin`
2. Login with credentials from `.env` file
3. Configure email settings (Settings → Email)
4. Enable required authentication features
5. Configure 2FA if needed

---

## Maintenance

### View Logs

```bash
# All services
sudo docker-compose logs -f

# Specific service
sudo docker-compose logs -f frontend
sudo docker-compose logs -f message
sudo docker-compose logs -f auth-proxy
```

### Restart Services

```bash
# All services
cd /opt/colink
sudo docker-compose restart

# Specific service
sudo docker-compose restart frontend
```

### Update Application

```bash
cd /opt/colink

# Pull latest changes
sudo git pull origin main

# Rebuild and restart
sudo docker-compose build
sudo docker-compose up -d
```

### Check Service Status

```bash
# Docker containers
sudo docker-compose ps

# System resources
htop
df -h
free -h

# Network connections
sudo netstat -tlnp
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check Docker status
sudo systemctl status docker

# Check logs for errors
sudo docker-compose logs

# Check disk space
df -h

# Check memory
free -h
```

### Cannot Access Frontend

1. **Check if frontend container is running**:
   ```bash
   sudo docker-compose ps frontend
   ```

2. **Check frontend logs**:
   ```bash
   sudo docker-compose logs frontend
   ```

3. **Verify Security Group** allows port 3000

4. **Check if port is listening**:
   ```bash
   sudo netstat -tlnp | grep 3000
   ```

### Database Connection Issues

```bash
# Check PostgreSQL container
sudo docker-compose ps postgres

# Test database connection
sudo docker-compose exec postgres psql -U colink_user -d colink_db -c "SELECT 1;"

# Check database logs
sudo docker-compose logs postgres
```

### Keycloak Not Accessible

Keycloak takes 1-2 minutes to start:

```bash
# Wait for Keycloak
sleep 120

# Check Keycloak logs
sudo docker-compose logs keycloak | grep -i "started"

# Restart Keycloak if needed
sudo docker-compose restart keycloak
```

### Out of Memory

If services are crashing due to memory:

1. **Upgrade instance type** to one with more RAM (t3.xlarge)
2. **Add swap space**:
   ```bash
   sudo dd if=/dev/zero of=/swapfile bs=1G count=4
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

### Full System Reset

⚠️ **WARNING**: This deletes all data!

```bash
cd /opt/colink

# Stop and remove everything
sudo docker-compose down -v

# Remove all images
sudo docker system prune -af --volumes

# Restart deployment
sudo docker-compose up -d
```

---

## Security Best Practices

### 1. Use Elastic IP

Assign an Elastic IP to your instance so the IP doesn't change on restart.

### 2. Restrict Security Group

Update Security Group to allow traffic only from known IPs:
```
Source: YOUR_IP/32
```

### 3. Enable HTTPS

Set up SSL/TLS certificates using:
- AWS Certificate Manager + Application Load Balancer
- Let's Encrypt with Certbot
- Cloudflare proxy

### 4. Change Default Passwords

Update all default passwords in `.env`:
- Superadmin password
- Database passwords
- Keycloak admin password
- MinIO credentials

### 5. Enable AWS Security Features

- Enable AWS CloudTrail for audit logging
- Use IAM roles instead of access keys
- Enable VPC Flow Logs
- Use AWS Systems Manager Session Manager instead of SSH

### 6. Regular Updates

```bash
# Update system packages
sudo yum update -y

# Update Docker images
cd /opt/colink
sudo git pull
sudo docker-compose pull
sudo docker-compose up -d
```

---

## Cost Estimation

### AWS Costs (Monthly, us-east-1)

| Resource | Spec | Cost |
|----------|------|------|
| **EC2 Instance** | t3.large (2 vCPU, 8GB RAM) | ~$60 |
| **EBS Storage** | 30GB gp3 | ~$3 |
| **Data Transfer** | 50GB outbound | ~$5 |
| **Elastic IP** | 1 IP | Free (if attached) |
| **Total** | | **~$68/month** |

For production with Load Balancer + RDS:

| Resource | Spec | Cost |
|----------|------|------|
| **EC2 Instance** | t3.xlarge (4 vCPU, 16GB RAM) | ~$120 |
| **Application Load Balancer** | Standard | ~$23 |
| **RDS PostgreSQL** | db.t3.large | ~$110 |
| **ElastiCache Redis** | cache.t3.medium | ~$50 |
| **S3 Storage** | 100GB | ~$3 |
| **Total** | | **~$306/month** |

---

## Support

For issues or questions:

1. Check logs: `sudo docker-compose logs -f`
2. Review documentation: `/opt/colink/README.md`
3. Check AWS Security Group settings
4. Verify instance has sufficient resources

---

**Deployment Script**: [aws-deploy.sh](./aws-deploy.sh)
**Project Repository**: Update with your actual repo URL
**Last Updated**: 2025-12-04
