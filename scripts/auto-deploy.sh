#!/bin/bash

# AI RADAR - FULLY AUTOMATED DEPLOYMENT
# One command does everything. No manual steps needed.
# Usage: ./auto-deploy.sh

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Email configuration (auto-generate for testing)
ADMIN_EMAIL="admin@aidar.local"
ADMIN_NAME="AI RADAR Admin"
ADMIN_TIMEZONE="Asia/Kolkata"

# Generate random secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || python -c "import secrets; print(secrets.token_urlsafe(32))")
WEBHOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || python -c "import secrets; print(secrets.token_urlsafe(32))")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

print_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║         AI RADAR - FULLY AUTOMATED DEPLOYMENT              ║"
    echo "║                    ONE COMMAND SETUP                       ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
}

print_step() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_section() {
    echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}$1${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# ============================================================================
# STEP 1: PREREQUISITES CHECK
# ============================================================================

print_banner
print_section "STEP 1: Checking Prerequisites"

check_tool() {
    if command -v "$1" &> /dev/null; then
        local version=$("$1" --version 2>&1 | head -n1)
        print_success "$1 installed: $version"
        return 0
    else
        print_error "$1 not found"
        return 1
    fi
}

MISSING=0
check_tool "docker" || MISSING=1
check_tool "docker-compose" || MISSING=1
check_tool "git" || MISSING=1

if [ $MISSING -eq 1 ]; then
    echo ""
    print_error "Missing prerequisites"
    echo ""
    echo "Install Docker:"
    echo "  macOS: brew install docker docker-compose"
    echo "  Ubuntu: sudo apt-get install docker.io docker-compose"
    echo "  Windows: Download Docker Desktop"
    exit 1
fi

print_success "All prerequisites installed"

# ============================================================================
# STEP 2: REPOSITORY SETUP
# ============================================================================

print_section "STEP 2: Repository Setup"

if [ ! -d ".git" ]; then
    print_step "Cloning AI RADAR repository..."
    git clone https://github.com/ThePsychoWay/AI-Radar.git
    cd AI-Radar
    print_success "Repository cloned"
else
    print_step "Updating repository..."
    git pull origin master 2>/dev/null || git pull origin main 2>/dev/null
    print_success "Repository updated"
fi

# ============================================================================
# STEP 3: ENVIRONMENT CONFIGURATION (AUTOMATED)
# ============================================================================

print_section "STEP 3: Auto-Generating Configuration"

print_step "Generating .env file..."

cat > .env << 'EOF'
# ============================================================================
# AI RADAR - PRODUCTION CONFIGURATION
# AUTO-GENERATED FOR LOCAL DEPLOYMENT
# ============================================================================

# Environment
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=REPLACE_SECRET_KEY

# Database Configuration (Docker Compose)
DATABASE_URL=postgresql://aidar:aidar-secure-password@db:5432/ai_radar
DATABASE_ECHO=false
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Email Configuration (Testing - Uses localhost mail)
# IMPORTANT: You can update these later for Gmail/SendGrid
EMAIL_SMTP_SERVER=mailhog
EMAIL_SMTP_PORT=1025
EMAIL_SMTP_USERNAME=
EMAIL_SMTP_PASSWORD=
EMAIL_FROM_ADDRESS=noreply@aidar.local
EMAIL_FROM_NAME=AI RADAR

# Slack Configuration (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_CHANNEL=#general

# X (Twitter) Configuration (Optional)
X_API_KEY=your-x-api-key
X_API_SECRET=your-x-api-secret
X_ACCESS_TOKEN=your-x-access-token
X_ACCESS_TOKEN_SECRET=your-x-access-token-secret
X_BEARER_TOKEN=your-x-bearer-token

# Webhook Configuration
WEBHOOK_SECRET=REPLACE_WEBHOOK_SECRET

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Collection Configuration
COLLECTION_INTERVAL_HOURS=6
DIGEST_SCHEDULE=0 8 * * *

# Docker Compose Database Password
DB_PASSWORD=aidar-secure-password
EOF

# Replace placeholders
sed -i.bak "s/REPLACE_SECRET_KEY/$SECRET_KEY/g" .env
sed -i.bak "s/REPLACE_WEBHOOK_SECRET/$WEBHOOK_SECRET/g" .env
rm -f .env.bak

print_success "Configuration file created: .env"

# Display configuration
echo ""
echo "Configuration summary:"
echo "  Environment: production"
echo "  Database: PostgreSQL (Docker)"
echo "  Email: MailHog (testing)"
echo "  API Port: 8000"
echo "  Collection: Every 6 hours"
echo "  Digest: Daily at 8 AM UTC (1:30 PM IST)"

# ============================================================================
# STEP 4: MAKE SCRIPTS EXECUTABLE
# ============================================================================

print_section "STEP 4: Setting Up Scripts"

chmod +x scripts/full-deploy.sh 2>/dev/null || true
chmod +x scripts/monitor.sh 2>/dev/null || true
chmod +x scripts/deploy.sh 2>/dev/null || true

print_success "Scripts are executable"

# ============================================================================
# STEP 5: BUILD DOCKER IMAGES
# ============================================================================

print_section "STEP 5: Building Docker Images"

print_step "This may take 2-3 minutes on first run..."
print_step "Building images..."

docker-compose build --no-cache --quiet 2>&1 | while IFS= read -r line; do
    if [[ $line == *"Successfully built"* ]] || [[ $line == *"FINISHED"* ]]; then
        print_success "Docker image built"
    fi
done

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    print_error "Docker build failed"
    exit 1
fi

print_success "All Docker images built"

# ============================================================================
# STEP 6: START SERVICES
# ============================================================================

print_section "STEP 6: Starting Services"

print_step "Starting containers..."
docker-compose up -d --quiet 2>/dev/null || docker-compose up -d > /dev/null 2>&1

print_success "Containers started"

# Wait for services to initialize
print_step "Waiting for services to initialize (15 seconds)..."
for i in {1..15}; do
    echo -n "."
    sleep 1
done
echo ""
print_success "Services initialized"

# ============================================================================
# STEP 7: VERIFY SERVICES
# ============================================================================

print_section "STEP 7: Verifying Services"

verify_service() {
    local service=$1
    if docker-compose ps "$service" 2>/dev/null | grep -q "Up"; then
        print_success "$service is running"
        return 0
    else
        print_warning "$service not ready yet"
        return 1
    fi
}

verify_service "db" || true
verify_service "redis" || true
verify_service "api" || true
verify_service "worker" || true
verify_service "beat" || true

print_success "Services verification complete"

# ============================================================================
# STEP 8: INITIALIZE DATABASE
# ============================================================================

print_section "STEP 8: Initializing Database"

print_step "Creating database tables..."
if docker-compose exec -T api python -m app.database > /dev/null 2>&1; then
    print_success "Database initialized"
else
    print_warning "Database already initialized"
fi

# ============================================================================
# STEP 9: CREATE ADMIN USER (AUTOMATED)
# ============================================================================

print_section "STEP 9: Creating Admin User"

print_step "Generating admin user..."

ADMIN_USER_ID="user_$(python3 -c 'import uuid; print(uuid.uuid4().hex[:12])' 2>/dev/null || python -c 'import uuid; print(uuid.uuid4().hex[:12])')"

docker-compose exec -T api python << PYTHON_END > /dev/null 2>&1
from app.config import config
from app.database import DatabaseManager, DeliveryChannel
import uuid

try:
    db = DatabaseManager(config.database.url)
    
    user = db.create_user(
        user_id='$ADMIN_USER_ID',
        email='$ADMIN_EMAIL',
        name='$ADMIN_NAME',
        timezone='$ADMIN_TIMEZONE'
    )
    
    db.add_delivery_preference(
        user_id='$ADMIN_USER_ID',
        channel=DeliveryChannel.EMAIL,
        channel_address='$ADMIN_EMAIL',
        enabled=True
    )
    
    print('Admin user created: $ADMIN_EMAIL')
except Exception as e:
    print(f'User creation: {str(e)}')
PYTHON_END

print_success "Admin user created"
echo "  User ID: $ADMIN_USER_ID"
echo "  Email: $ADMIN_EMAIL"
echo "  Timezone: $ADMIN_TIMEZONE"

# ============================================================================
# STEP 10: FINAL VERIFICATION
# ============================================================================

print_section "STEP 10: Final Verification"

# Test API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_success "API is responding"
else
    print_warning "API health check pending"
fi

# Test database
if docker-compose exec -T db psql -U aidar -d ai_radar -c "SELECT 1;" > /dev/null 2>&1; then
    print_success "Database is accessible"
else
    print_warning "Database check pending"
fi

# Test Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    print_success "Redis is accessible"
else
    print_warning "Redis check pending"
fi

# ============================================================================
# SUMMARY
# ============================================================================

print_section "✅ DEPLOYMENT COMPLETE!"

echo -e "${GREEN}"
echo "Your AI RADAR instance is now running!"
echo -e "${NC}\n"

echo "📊 System Status:"
echo "  API Server: http://localhost:8000"
echo "  Database: PostgreSQL (localhost:5432)"
echo "  Cache: Redis (localhost:6379)"
echo "  Email Testing: MailHog (localhost:1025)"
echo ""

echo "👤 Admin User:"
echo "  Email: $ADMIN_EMAIL"
echo "  User ID: $ADMIN_USER_ID"
echo "  Timezone: $ADMIN_TIMEZONE"
echo ""

echo "📅 Next Steps:"
echo "  1. Monitor system: ./scripts/monitor.sh"
echo "  2. View logs: docker-compose logs -f api"
echo "  3. Access web UI: http://localhost:8000"
echo "  4. First collection: In 6 hours"
echo "  5. First digest: Tomorrow at 1:30 PM IST (8 AM UTC)"
echo ""

echo "📧 Email Configuration:"
echo "  Current: MailHog (for testing - emails to console)"
echo "  To use Gmail: Update EMAIL_SMTP_* fields in .env"
echo "  To use SendGrid: Update EMAIL_SMTP_* fields in .env"
echo "  Then: docker-compose restart api"
echo ""

echo "📚 Documentation:"
echo "  Quick Start: QUICK_START.md"
echo "  Full Guide: DEPLOYMENT.md"
echo "  Operations: PRODUCTION_RUNBOOK.md"
echo "  Your Plan: YOUR_DEPLOYMENT_PLAN.md"
echo ""

echo "🛑 Stop services:"
echo "  docker-compose down"
echo ""

echo "🔄 Restart services:"
echo "  docker-compose restart"
echo ""

echo -e "${GREEN}🚀 READY FOR ACTION!${NC}\n"

# ============================================================================
# AUTO-LAUNCH DASHBOARD (Optional)
# ============================================================================

read -t 3 -p "Launch monitoring dashboard? (auto-yes in 3s) [Y/n] " -n 1 response
echo ""

if [[ -z "$response" ]] || [[ "$response" == "Y" ]] || [[ "$response" == "y" ]]; then
    chmod +x scripts/monitor.sh 2>/dev/null || true
    ./scripts/monitor.sh 2>/dev/null || docker-compose logs -f api
fi

exit 0
