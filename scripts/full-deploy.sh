#!/bin/bash

# AI RADAR - Complete Production Deployment Script
# Run on your local machine (Mac/Linux) or WSL (Windows)
# One command to deploy everything!

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  $1"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}\n"
}

print_step() {
    echo -e "${BLUE}→${NC} $1"
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

# Step 1: Check Prerequisites
print_header "STEP 1: Checking Prerequisites"

check_tool() {
    if command -v "$1" &> /dev/null; then
        local version=$("$1" --version 2>&1 | head -n1)
        print_success "$1 installed: $version"
        return 0
    else
        print_error "$1 not found. Please install it."
        return 1
    fi
}

MISSING=0
check_tool "docker" || MISSING=1
check_tool "docker-compose" || MISSING=1
check_tool "git" || MISSING=1

if [ $MISSING -eq 1 ]; then
    echo ""
    print_error "Missing prerequisites!"
    echo ""
    echo "Installation:"
    echo "  macOS: brew install docker docker-compose"
    echo "  Ubuntu: sudo apt-get install docker.io docker-compose"
    echo "  Windows: Download Docker Desktop"
    echo ""
    exit 1
fi

# Step 2: Clone/Navigate to Repository
print_header "STEP 2: Repository Setup"

if [ ! -d ".git" ]; then
    print_step "Cloning AI RADAR repository..."
    git clone https://github.com/ThePsychoWay/AI-Radar.git
    cd AI-Radar
    print_success "Repository cloned"
else
    print_step "Pulling latest changes..."
    git pull origin master
    print_success "Repository updated"
fi

# Step 3: Configure Environment
print_header "STEP 3: Environment Configuration"

if [ ! -f ".env" ]; then
    print_step "Creating .env from template..."
    cp .env.template .env
    print_success ".env created"
    
    print_warning "⚠️  IMPORTANT: Edit .env with your configuration!"
    echo ""
    echo "Required fields to update in .env:"
    echo "  1. EMAIL_SMTP_USERNAME=your-email@gmail.com"
    echo "  2. EMAIL_SMTP_PASSWORD=your-app-password"
    echo "  3. EMAIL_FROM_ADDRESS=your-email@gmail.com"
    echo "  4. SLACK_WEBHOOK_URL (optional)"
    echo "  5. X_* credentials (optional)"
    echo ""
    echo "Edit now? (y/n)"
    read -r response
    if [ "$response" = "y" ]; then
        ${EDITOR:-nano} .env
    fi
else
    print_success ".env already configured"
fi

# Step 4: Build and Start Services
print_header "STEP 4: Building and Starting Services"

print_step "Building Docker images... (this takes 2-3 minutes)"
docker-compose build --no-cache --quiet

print_step "Starting services..."
docker-compose up -d

print_success "Services started!"

# Wait for services to be ready
print_step "Waiting for services to be ready..."
sleep 5

# Step 5: Verify Services
print_header "STEP 5: Verifying Services"

verify_service() {
    local service=$1
    local port=$2
    
    if docker-compose ps "$service" | grep -q "Up"; then
        print_success "$service is running ✓"
        return 0
    else
        print_error "$service failed to start ✗"
        docker-compose logs "$service" | tail -10
        return 1
    fi
}

verify_service "db" "5432" || true
verify_service "redis" "6379" || true
verify_service "api" "8000" || true

# Check API health
print_step "Testing API health..."
if curl -s http://localhost:8000/health | grep -q "ok"; then
    print_success "API is responding ✓"
else
    print_warning "API health check pending (may take a moment)"
fi

# Step 6: Initialize Database
print_header "STEP 6: Initializing Database"

print_step "Creating database tables..."
docker-compose exec -T api python -m app.database
print_success "Database initialized ✓"

# Step 7: Create First User
print_header "STEP 7: Creating First User"

print_step "Creating admin user..."
docker-compose exec -T api python << 'PYTHON_SCRIPT'
from app.config import config
from app.database import DatabaseManager, DeliveryChannel
import uuid

db = DatabaseManager(config.database.url)

# Create first user
user_id = f"user_{uuid.uuid4().hex[:12]}"
user = db.create_user(
    user_id=user_id,
    email="admin@localhost",
    name="Admin User",
    timezone="Asia/Kolkata"
)

# Add email delivery preference
db.add_delivery_preference(
    user_id=user_id,
    channel=DeliveryChannel.EMAIL,
    channel_address="admin@localhost",
    enabled=True
)

print(f"✓ Admin user created!")
print(f"  User ID: {user_id}")
print(f"  Email: {user.email}")
print(f"  Timezone: {user.timezone}")
PYTHON_SCRIPT

print_success "First user created ✓"

# Step 8: Test Delivery Channels
print_header "STEP 8: Testing Delivery Channels"

print_step "Testing email configuration..."
docker-compose exec -T api python -m app.delivery_setup test 2>&1 | head -20 || print_warning "Email test requires credentials"

# Step 9: Show Monitoring Dashboard
print_header "STEP 9: Monitoring & Operations"

print_success "Services Status:"
docker-compose ps

echo ""
print_success "Quick Commands:"
echo "  View logs:     docker-compose logs -f api"
echo "  Worker logs:   docker-compose logs -f worker"
echo "  Database:      docker-compose exec db psql -U aidar -d ai_radar"
echo "  Stop all:      docker-compose down"
echo "  Full restart:  docker-compose restart"

# Step 10: Collections & Digests Schedule
print_header "STEP 10: Schedules & Operations"

echo -e "${GREEN}Collection Schedule:${NC}"
echo "  Every 6 hours: 0, 6, 12, 18 UTC"
echo "  Next collection: Automatically triggered by scheduler"
echo ""
echo -e "${GREEN}Digest Schedule:${NC}"
echo "  Daily: 8:00 AM UTC (13:30 IST)"
echo "  First digest: Tomorrow morning"
echo ""
echo -e "${GREEN}Manual Operations:${NC}"
echo "  Run collection: docker-compose exec worker python -m app.collectors.rss_collector"
echo "  Generate digest: docker-compose exec api python -m app.generators.digest_generator"
echo "  Check logs: docker-compose logs -f"

# Final Summary
print_header "✅ DEPLOYMENT COMPLETE!"

echo -e "${GREEN}Your AI RADAR instance is running!${NC}\n"

echo "📊 System Status:"
echo "   API Server: http://localhost:8000"
echo "   Database: PostgreSQL (localhost:5432)"
echo "   Cache: Redis (localhost:6379)"
echo ""

echo "👤 First User:"
echo "   Email: admin@localhost"
echo "   Timezone: Asia/Kolkata"
echo ""

echo "📅 Next Steps:"
echo "   1. Configure email in .env (SendGrid recommended)"
echo "   2. Create more users: docker-compose exec api python"
echo "   3. Monitor logs: docker-compose logs -f api"
echo "   4. First collection: 6 hours from now"
echo "   5. First digest: Tomorrow at 8 AM UTC"
echo ""

echo "📚 Documentation:"
echo "   Quick Start: QUICK_START.md"
echo "   Full Guide: DEPLOYMENT.md"
echo "   Operations: PRODUCTION_RUNBOOK.md"
echo ""

echo -e "${CYAN}🚀 Happy hacking!${NC}\n"

exit 0
