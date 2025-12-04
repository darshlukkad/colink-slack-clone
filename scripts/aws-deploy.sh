#!/bin/bash

################################################################################
# Colink AWS Deployment Script
#
# This script automates the complete deployment of Colink on AWS Linux
# It will:
# - Install all required dependencies (Docker, Node.js, etc.)
# - Clone the repository
# - Configure environment variables
# - Build and deploy all services
# - Create superadmin user
# - Set up monitoring
#
# Usage:
#   chmod +x aws-deploy.sh
#   sudo ./aws-deploy.sh
#
# Requirements:
# - AWS Linux 2 or Amazon Linux 2023
# - Root or sudo access
# - At least 8GB RAM
# - 20GB+ free disk space
################################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/yourorg/colink-slack-clone.git"  # UPDATE THIS
REPO_BRANCH="main"
INSTALL_DIR="/opt/colink"
APP_USER="colink"
SUPERADMIN_USERNAME="admin"
SUPERADMIN_EMAIL="admin@colink.local"
SUPERADMIN_PASSWORD="Admin@123456"  # CHANGE THIS IN PRODUCTION

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run as root or with sudo"
        exit 1
    fi
}

check_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        print_info "Detected OS: $OS"

        if [[ ! "$OS" =~ "Amazon Linux" ]] && [[ ! "$OS" =~ "Amazon" ]]; then
            print_warning "This script is optimized for Amazon Linux. Proceeding anyway..."
        fi
    else
        print_error "Cannot determine OS. This script requires Amazon Linux 2 or AL2023"
        exit 1
    fi
}

check_resources() {
    print_header "Checking System Resources"

    # Check RAM
    TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$TOTAL_RAM" -lt 7 ]; then
        print_warning "System has ${TOTAL_RAM}GB RAM. Recommended: 8GB+"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "RAM: ${TOTAL_RAM}GB (sufficient)"
    fi

    # Check disk space
    AVAILABLE_DISK=$(df -BG / | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "$AVAILABLE_DISK" -lt 20 ]; then
        print_warning "Available disk space: ${AVAILABLE_DISK}GB. Recommended: 20GB+"
    else
        print_success "Disk space: ${AVAILABLE_DISK}GB (sufficient)"
    fi
}

################################################################################
# Installation Functions
################################################################################

install_dependencies() {
    print_header "Installing System Dependencies"

    # Update system
    print_info "Updating system packages..."
    yum update -y

    # Install basic tools
    print_info "Installing basic tools..."
    yum install -y \
        git \
        curl \
        wget \
        vim \
        htop \
        jq \
        nc \
        lsof

    print_success "System dependencies installed"
}

install_docker() {
    print_header "Installing Docker"

    if command -v docker &> /dev/null; then
        print_info "Docker already installed: $(docker --version)"
        return 0
    fi

    # Install Docker
    yum install -y docker

    # Start Docker service
    systemctl start docker
    systemctl enable docker

    # Add app user to docker group (will be created later)
    # usermod -aG docker $APP_USER || true

    print_success "Docker installed: $(docker --version)"
}

install_docker_compose() {
    print_header "Installing Docker Compose"

    if command -v docker-compose &> /dev/null; then
        print_info "Docker Compose already installed: $(docker-compose --version)"
        return 0
    fi

    # Install Docker Compose V2 (plugin)
    DOCKER_COMPOSE_VERSION="v2.24.5"

    # Create CLI plugins directory
    mkdir -p /usr/local/lib/docker/cli-plugins

    # Download Docker Compose
    curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose

    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

    # Create symlink for docker-compose command
    ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose

    print_success "Docker Compose installed: $(docker-compose --version)"
}

install_nodejs() {
    print_header "Installing Node.js"

    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        print_info "Node.js already installed: $NODE_VERSION"

        # Check if version is 18+
        MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$MAJOR_VERSION" -ge 18 ]; then
            print_success "Node.js version is sufficient"
            return 0
        else
            print_warning "Node.js version is too old. Installing newer version..."
        fi
    fi

    # Install Node.js 18.x from NodeSource
    curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
    yum install -y nodejs

    print_success "Node.js installed: $(node --version)"
    print_success "npm installed: $(npm --version)"
}

################################################################################
# Application Setup Functions
################################################################################

create_app_user() {
    print_header "Creating Application User"

    if id "$APP_USER" &>/dev/null; then
        print_info "User $APP_USER already exists"
    else
        useradd -r -m -s /bin/bash $APP_USER
        usermod -aG docker $APP_USER
        print_success "User $APP_USER created"
    fi
}

clone_repository() {
    print_header "Cloning Repository"

    # Create install directory
    mkdir -p $INSTALL_DIR

    if [ -d "$INSTALL_DIR/.git" ]; then
        print_info "Repository already exists. Pulling latest changes..."
        cd $INSTALL_DIR
        git fetch origin
        git checkout $REPO_BRANCH
        git pull origin $REPO_BRANCH
    else
        print_info "Cloning repository from $REPO_URL..."
        git clone -b $REPO_BRANCH $REPO_URL $INSTALL_DIR
    fi

    cd $INSTALL_DIR
    print_success "Repository ready at $INSTALL_DIR"
    print_info "Current commit: $(git rev-parse --short HEAD)"
}

configure_environment() {
    print_header "Configuring Environment Variables"

    cd $INSTALL_DIR

    # Get public IP
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "localhost")
    print_info "Public IP: $PUBLIC_IP"

    # Create .env file
    cat > .env <<EOF
# Colink Environment Configuration
# Generated on $(date)

# Public URLs (update with your domain if using one)
PUBLIC_URL=http://${PUBLIC_IP}:3000
API_URL=http://${PUBLIC_IP}:8001

# Frontend Configuration
NEXT_PUBLIC_API_URL=http://${PUBLIC_IP}:8001
NEXT_PUBLIC_WS_URL=http://${PUBLIC_IP}:8009
NEXT_PUBLIC_KEYCLOAK_URL=http://${PUBLIC_IP}:8080
NEXT_PUBLIC_KEYCLOAK_REALM=colink
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=web-app

# Service URLs
NEXT_PUBLIC_AUTH_PROXY_URL=http://${PUBLIC_IP}:8001
NEXT_PUBLIC_CHANNEL_SERVICE_URL=http://${PUBLIC_IP}:8003
NEXT_PUBLIC_MESSAGE_SERVICE_URL=http://${PUBLIC_IP}:8002
NEXT_PUBLIC_THREADS_SERVICE_URL=http://${PUBLIC_IP}:8005
NEXT_PUBLIC_REACTIONS_SERVICE_URL=http://${PUBLIC_IP}:8006
NEXT_PUBLIC_FILES_SERVICE_URL=http://${PUBLIC_IP}:8007
NEXT_PUBLIC_NOTIFICATIONS_SERVICE_URL=http://${PUBLIC_IP}:8008
NEXT_PUBLIC_WEBSOCKET_URL=http://${PUBLIC_IP}:8009

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=colink_db
POSTGRES_USER=colink_user
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# Keycloak Configuration
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=$(openssl rand -base64 24)
KC_DB=postgres
KC_DB_URL=jdbc:postgresql://postgres:5432/keycloak_db
KC_DB_USERNAME=keycloak_user
KC_DB_PASSWORD=$(openssl rand -base64 32)

# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=$(openssl rand -base64 24)
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=colink-files

# Redpanda Configuration
REDPANDA_BROKERS=redpanda:9092

# JWT Secret
JWT_SECRET=$(openssl rand -base64 64)

# Superadmin Configuration
SUPERADMIN_USERNAME=$SUPERADMIN_USERNAME
SUPERADMIN_EMAIL=$SUPERADMIN_EMAIL
SUPERADMIN_PASSWORD=$SUPERADMIN_PASSWORD

# Environment
NODE_ENV=production
ENVIRONMENT=production
EOF

    print_success "Environment configured"
    print_warning "Database and service passwords have been randomly generated"
}

configure_firewall() {
    print_header "Configuring Firewall"

    # Check if firewalld is installed and running
    if systemctl is-active --quiet firewalld; then
        print_info "Configuring firewalld..."

        # Open required ports
        firewall-cmd --permanent --add-port=3000/tcp   # Frontend
        firewall-cmd --permanent --add-port=8001/tcp   # Auth Proxy
        firewall-cmd --permanent --add-port=8002/tcp   # Message Service
        firewall-cmd --permanent --add-port=8003/tcp   # Channel Service
        firewall-cmd --permanent --add-port=8080/tcp   # Keycloak
        firewall-cmd --permanent --add-port=9001/tcp   # MinIO Console
        firewall-cmd --permanent --add-port=3001/tcp   # Grafana
        firewall-cmd --permanent --add-port=9090/tcp   # Prometheus

        firewall-cmd --reload
        print_success "Firewall configured"
    else
        print_info "firewalld not active. Make sure AWS Security Group allows traffic:"
        print_info "  - Port 3000 (Frontend)"
        print_info "  - Port 8080 (Keycloak)"
        print_info "  - Port 9001 (MinIO Console)"
        print_info "  - Port 3001 (Grafana)"
    fi
}

build_application() {
    print_header "Building Application"

    cd $INSTALL_DIR

    print_info "Building Docker images (this may take 10-15 minutes)..."
    docker-compose build --parallel

    print_success "Application built successfully"
}

start_application() {
    print_header "Starting Application"

    cd $INSTALL_DIR

    print_info "Starting all services..."
    docker-compose up -d

    print_success "Services started"

    # Wait for services to be healthy
    print_info "Waiting for services to be ready (60 seconds)..."
    sleep 60

    # Check service status
    print_info "Service status:"
    docker-compose ps
}

create_superadmin() {
    print_header "Creating Superadmin User"

    cd $INSTALL_DIR

    # Wait a bit more to ensure auth-proxy is fully ready
    print_info "Ensuring auth-proxy is ready..."
    sleep 10

    # Create superadmin using the script
    print_info "Creating superadmin user: $SUPERADMIN_USERNAME"

    docker-compose exec -T auth-proxy python /app/scripts/setup_superadmin.py <<EOF || {
        print_warning "Superadmin setup script not found or failed. Trying alternative method..."

        # Alternative: Create via Keycloak API
        docker-compose exec -T auth-proxy bash -c "
            python -c \"
import os
import asyncio
from sqlalchemy import create_engine, text
from passlib.hash import bcrypt

async def create_admin():
    # Database connection
    db_url = 'postgresql://colink_user:\${POSTGRES_PASSWORD}@postgres:5432/colink_db'
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(text('SELECT id FROM users WHERE username = :username'), {'username': '$SUPERADMIN_USERNAME'})
        if result.fetchone():
            print('Superadmin already exists')
            return

        # Create user
        conn.execute(text('''
            INSERT INTO users (username, email, role, is_active, created_at, updated_at)
            VALUES (:username, :email, 'admin', true, NOW(), NOW())
        '''), {
            'username': '$SUPERADMIN_USERNAME',
            'email': '$SUPERADMIN_EMAIL'
        })
        conn.commit()
        print('Superadmin created successfully')

asyncio.run(create_admin())
\"
        "
    }
EOF

    print_success "Superadmin user created"
    print_info "Username: $SUPERADMIN_USERNAME"
    print_info "Email: $SUPERADMIN_EMAIL"
    print_warning "Password: $SUPERADMIN_PASSWORD"
    print_warning "IMPORTANT: Change this password after first login!"
}

setup_systemd_service() {
    print_header "Setting up Systemd Service"

    cat > /etc/systemd/system/colink.service <<EOF
[Unit]
Description=Colink Slack Clone Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
User=root

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable colink.service

    print_success "Systemd service configured"
    print_info "Service will start automatically on boot"
}

setup_log_rotation() {
    print_header "Setting up Log Rotation"

    cat > /etc/logrotate.d/colink <<EOF
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    missingok
    delaycompress
    copytruncate
}
EOF

    print_success "Log rotation configured"
}

health_check() {
    print_header "Running Health Checks"

    cd $INSTALL_DIR

    # Check if containers are running
    RUNNING_CONTAINERS=$(docker-compose ps | grep "Up" | wc -l)
    TOTAL_CONTAINERS=$(docker-compose ps | tail -n +2 | wc -l)

    print_info "Running containers: $RUNNING_CONTAINERS/$TOTAL_CONTAINERS"

    # Test frontend
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200\|301\|302"; then
        print_success "Frontend is accessible"
    else
        print_warning "Frontend may not be ready yet"
    fi

    # Test auth-proxy
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>/dev/null | grep -q "200"; then
        print_success "Auth Proxy is healthy"
    else
        print_warning "Auth Proxy may not be ready yet"
    fi

    # Test Keycloak
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 | grep -q "200\|303"; then
        print_success "Keycloak is accessible"
    else
        print_warning "Keycloak may not be ready yet"
    fi
}

print_access_info() {
    print_header "Deployment Complete!"

    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "YOUR_SERVER_IP")

    echo -e "${GREEN}"
    echo "================================================"
    echo "   Colink Deployment Successful!"
    echo "================================================"
    echo -e "${NC}"

    echo -e "\n${BLUE}Access URLs:${NC}"
    echo -e "  Frontend:          ${GREEN}http://${PUBLIC_IP}:3000${NC}"
    echo -e "  Admin Dashboard:   ${GREEN}http://${PUBLIC_IP}:3000/admin${NC}"
    echo -e "  Analytics:         ${GREEN}http://${PUBLIC_IP}:3000/analytics${NC}"
    echo -e "  Keycloak Admin:    ${GREEN}http://${PUBLIC_IP}:8080/admin${NC}"
    echo -e "  MinIO Console:     ${GREEN}http://${PUBLIC_IP}:9001${NC}"
    echo -e "  Grafana:           ${GREEN}http://${PUBLIC_IP}:3001${NC}"
    echo -e "  Prometheus:        ${GREEN}http://${PUBLIC_IP}:9090${NC}"

    echo -e "\n${BLUE}Superadmin Credentials:${NC}"
    echo -e "  Username: ${GREEN}$SUPERADMIN_USERNAME${NC}"
    echo -e "  Email:    ${GREEN}$SUPERADMIN_EMAIL${NC}"
    echo -e "  Password: ${YELLOW}$SUPERADMIN_PASSWORD${NC}"
    echo -e "  ${RED}⚠ CHANGE THIS PASSWORD AFTER FIRST LOGIN!${NC}"

    echo -e "\n${BLUE}Keycloak Admin Credentials:${NC}"
    echo -e "  Username: ${GREEN}admin${NC}"
    echo -e "  Password: ${YELLOW}(stored in .env file)${NC}"

    echo -e "\n${BLUE}MinIO Credentials:${NC}"
    echo -e "  Username: ${GREEN}minioadmin${NC}"
    echo -e "  Password: ${YELLOW}(stored in .env file)${NC}"

    echo -e "\n${BLUE}Useful Commands:${NC}"
    echo -e "  View logs:           ${GREEN}cd $INSTALL_DIR && docker-compose logs -f${NC}"
    echo -e "  Restart services:    ${GREEN}cd $INSTALL_DIR && docker-compose restart${NC}"
    echo -e "  Stop services:       ${GREEN}cd $INSTALL_DIR && docker-compose down${NC}"
    echo -e "  Start services:      ${GREEN}cd $INSTALL_DIR && docker-compose up -d${NC}"
    echo -e "  Check status:        ${GREEN}cd $INSTALL_DIR && docker-compose ps${NC}"

    echo -e "\n${BLUE}Important Files:${NC}"
    echo -e "  Application:         ${GREEN}$INSTALL_DIR${NC}"
    echo -e "  Environment:         ${GREEN}$INSTALL_DIR/.env${NC}"
    echo -e "  Logs:                ${GREEN}/var/lib/docker/containers/${NC}"

    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Access the frontend and login with superadmin credentials"
    echo "2. Change the default superadmin password"
    echo "3. Configure AWS Security Group to allow required ports"
    echo "4. Set up a domain name and SSL certificate (recommended)"
    echo "5. Configure backup strategy for PostgreSQL data"
    echo "6. Review and customize .env file if needed"

    echo -e "\n${BLUE}Documentation:${NC}"
    echo -e "  README:              ${GREEN}$INSTALL_DIR/README.md${NC}"
    echo -e "  Architecture:        ${GREEN}$INSTALL_DIR/ARCHITECTURE.md${NC}"
    echo -e "  Quick Start:         ${GREEN}$INSTALL_DIR/QUICKSTART.md${NC}"

    echo ""
}

################################################################################
# Main Installation Flow
################################################################################

main() {
    clear

    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║                                                    ║"
    echo "║        Colink AWS Deployment Script               ║"
    echo "║                                                    ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"

    print_warning "This script will install and configure Colink on this server"
    print_warning "Estimated time: 15-20 minutes"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deployment cancelled"
        exit 0
    fi

    # Pre-flight checks
    check_root
    check_os
    check_resources

    # Install dependencies
    install_dependencies
    install_docker
    install_docker_compose
    install_nodejs

    # Setup application
    create_app_user
    clone_repository
    configure_environment
    configure_firewall

    # Build and deploy
    build_application
    start_application

    # Post-deployment setup
    create_superadmin
    setup_systemd_service
    setup_log_rotation

    # Health checks
    sleep 10
    health_check

    # Print access information
    print_access_info

    print_success "Deployment completed successfully!"
}

# Run main function
main "$@"
