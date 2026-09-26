#!/bin/bash

# AI RADAR Deployment Script
# Quick setup and deployment helper

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
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

check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed"
        return 1
    fi
    print_success "$1 is installed"
    return 0
}

# Main script
print_header "AI RADAR Deployment Setup"

# Check prerequisites
print_header "Checking Prerequisites"

MISSING=0

check_command "python3" || MISSING=1
check_command "pip" || MISSING=1
check_command "git" || MISSING=1

if [ "$1" == "docker" ]; then
    check_command "docker" || MISSING=1
    check_command "docker-compose" || MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    print_error "Some required tools are missing. Please install them first."
    exit 1
fi

# Create .env file
print_header "Environment Setup"

if [ ! -f .env ]; then
    print_warning "No .env file found. Creating from template..."
    cp .env.template .env
    print_success ".env file created"
    print_warning "Please edit .env with your configuration"
    nano .env || vim .env
else
    print_success ".env file already exists"
fi

# Install Python dependencies
print_header "Installing Dependencies"

python3 -m venv venv 2>/dev/null || true
source venv/bin/activate

pip install --upgrade pip setuptools wheel > /dev/null
pip install -r requirements.txt > /dev/null

print_success "Dependencies installed"

# Initialize database
print_header "Database Setup"

if [ ! -f "ai_radar.db" ] && [ "$1" != "docker" ]; then
    print_warning "Initializing SQLite database..."
    python -m app.database
    print_success "Database initialized"
else
    print_warning "Database file already exists or using Docker"
fi

# Setup delivery channels
print_header "Delivery Channels Setup"

python -m app.delivery_setup guides > /tmp/delivery_setup.txt
print_success "Setup guides available in /tmp/delivery_setup.txt"

# Docker deployment
if [ "$1" == "docker" ]; then
    print_header "Docker Deployment"

    # Check docker-compose file
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found"
        exit 1
    fi

    # Build images
    print_warning "Building Docker images... (this may take a few minutes)"
    docker-compose build

    # Start services
    print_warning "Starting services..."
    docker-compose up -d

    # Wait for services to be ready
    sleep 5

    # Initialize database
    print_warning "Initializing database..."
    docker-compose exec -T api python -m app.database

    # Check health
    print_header "Health Checks"

    if docker-compose exec -T api curl -s http://localhost:8000/health > /dev/null; then
        print_success "API is running"
    else
        print_error "API health check failed"
        docker-compose logs api
        exit 1
    fi

    if docker-compose exec -T db psql -U aidar -d ai_radar -c "SELECT 1" > /dev/null 2>&1; then
        print_success "Database is running"
    else
        print_error "Database health check failed"
        exit 1
    fi

    print_success "Docker deployment complete!"
    echo ""
    echo "Services running:"
    docker-compose ps
    echo ""
    echo "Access your application at http://localhost:8000"
    echo ""
    echo "View logs with:"
    echo "  docker-compose logs -f api"
    echo "  docker-compose logs -f worker"

else
    # Local deployment
    print_header "Local Deployment"

    # Run tests
    print_warning "Running tests..."
    pytest tests/ -v --tb=short

    # Start collection
    print_warning "Running initial collection..."
    python -m app.collectors.rss_collector

    print_success "Local setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Configure .env with your credentials"
    echo "2. Run scheduled jobs:"
    echo "   python -m app.delivery_setup test"
    echo "3. Start the API:"
    echo "   python app.py"

fi

# Summary
print_header "Deployment Complete!"

echo "Configuration file: .env"
echo "Database: ./ai_radar.db"
echo "Data directories: ./data/raw, ./data/processed"
echo ""
echo "For production deployment, see DEPLOYMENT.md"
echo ""
print_success "Happy coding!"
