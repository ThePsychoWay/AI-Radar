# AI RADAR - Complete Local Deployment Guide

**For Phoenix: Full end-to-end setup on your machine**

---

## ⚡ TL;DR (5 Minutes)

```bash
# Clone repo
git clone https://github.com/ThePsychoWay/AI-Radar.git
cd AI-Radar

# Configure environment
cp .env.template .env
nano .env  # Edit email config

# Deploy everything
chmod +x scripts/full-deploy.sh
./scripts/full-deploy.sh docker
```

**Done!** Services running, first user created, monitoring ready.

---

## 📋 Step-by-Step Deployment

### Step 1: Prerequisites (2 min)

**macOS:**
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Docker & Docker Compose
brew install docker docker-compose

# Or just download Docker Desktop (includes both)
# https://www.docker.com/products/docker-desktop
```

**Ubuntu/Linux:**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git

# Add your user to docker group (optional, avoid sudo)
sudo usermod -aG docker $USER
```

**Windows:**
- Download Docker Desktop: https://www.docker.com/products/docker-desktop
- Install & restart
- Open PowerShell or WSL terminal

**Verify Installation:**
```bash
docker --version
docker-compose --version
git --version
```

---

### Step 2: Clone Repository (1 min)

```bash
# Navigate to where you want the project
cd ~/projects  # or your preferred location

# Clone
git clone https://github.com/ThePsychoWay/AI-Radar.git
cd AI-Radar

# Verify structure
ls -la
# Should show: README.md, DEPLOYMENT.md, docker-compose.yml, .env.template, etc.
```

---

### Step 3: Configure Environment (3 min)

```bash
# Copy template to .env
cp .env.template .env

# Edit with your configuration
nano .env
# or: vim .env
# or: code .env (VS Code)
# or: open .env (macOS, opens in default editor)
```

**Edit these REQUIRED fields:**

```env
# Email Configuration (choose one)

# Option A: Gmail (for testing)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=your-email@gmail.com
EMAIL_SMTP_PASSWORD=your-app-specific-password
EMAIL_FROM_ADDRESS=your-email@gmail.com

# How to get Gmail app password:
# 1. Go to https://myaccount.google.com/security
# 2. Enable 2-step verification
# 3. Create "App Password" for Mail
# 4. Copy the 16-char password here

# Option B: SendGrid (Recommended)
# Create free account: https://sendgrid.com/signup
# Then:
EMAIL_SMTP_SERVER=smtp.sendgrid.net
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=apikey
EMAIL_SMTP_PASSWORD=SG.your-api-key-here
EMAIL_FROM_ADDRESS=noreply@yourdomain.com

# Slack (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# X/Twitter (Optional - leave as-is for now)
X_API_KEY=your-key
X_API_SECRET=your-secret
# ... rest of X config
```

**Save file:**
- `nano`: Press `Ctrl+X`, then `Y`, then `Enter`
- `vim`: Press `Esc`, type `:wq`, press `Enter`
- `code`: Press `Ctrl+S`

---

### Step 4: Deploy Everything (3-5 min)

```bash
# Make scripts executable
chmod +x scripts/full-deploy.sh
chmod +x scripts/deploy.sh

# Run full deployment
./scripts/full-deploy.sh docker
```

**What this does automatically:**
1. ✅ Checks Docker is installed
2. ✅ Updates repo
3. ✅ Validates .env
4. ✅ Builds Docker images (~2 min)
5. ✅ Starts all services
6. ✅ Initializes database
7. ✅ Creates first user
8. ✅ Tests delivery channels
9. ✅ Shows status

**Or manually step-by-step:**

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Wait a moment
sleep 10

# Initialize database
docker-compose exec -T api python -m app.database

# Verify
docker-compose ps
```

---

### Step 5: Verify Everything Works (2 min)

```bash
# Check all services running
docker-compose ps

# Expected output:
# NAME              STATUS
# ai_radar_db       Up (healthy)
# ai_radar_redis    Up (healthy)
# ai_radar_api      Up (healthy)
# ai_radar_worker   Up
# ai_radar_beat     Up
# ai_radar_nginx    Up

# Test API
curl http://localhost:8000/health
# Should return: {"status": "ok"}

# View logs
docker-compose logs api | tail -20
docker-compose logs worker | tail -20
```

---

### Step 6: Create First User (30 seconds)

**Option A: Interactive Script**
```bash
docker-compose exec -T api python << 'EOF'
from app.config import config
from app.database import DatabaseManager, DeliveryChannel
import uuid

db = DatabaseManager(config.database.url)

# Get user input
email = input("Enter email: ")
name = input("Enter name: ")
timezone = input("Enter timezone [Asia/Kolkata]: ") or "Asia/Kolkata"

# Create user
user_id = f"user_{uuid.uuid4().hex[:12]}"
user = db.create_user(
    user_id=user_id,
    email=email,
    name=name,
    timezone=timezone
)

# Add email preference
db.add_delivery_preference(
    user_id=user_id,
    channel=DeliveryChannel.EMAIL,
    channel_address=email,
    enabled=True
)

print(f"\n✓ User created!")
print(f"  ID: {user_id}")
print(f"  Email: {email}")
print(f"  First digest: Tomorrow at 8:00 AM UTC")
EOF
```

**Option B: Pre-configured**
```bash
docker-compose exec -T api python -c "
from app.config import config
from app.database import DatabaseManager, DeliveryChannel
import uuid

db = DatabaseManager(config.database.url)
user = db.create_user(
    user_id=f'user_{uuid.uuid4().hex[:12]}',
    email='you@example.com',
    name='Your Name',
    timezone='Asia/Kolkata'
)
db.add_delivery_preference(
    user_id=user.id,
    channel=DeliveryChannel.EMAIL,
    channel_address=user.email,
    enabled=True
)
print(f'✓ User: {user.email}')
"
```

---

### Step 7: Monitor & Scale (Ongoing)

**Real-time Logs**
```bash
# API logs (most important)
docker-compose logs -f api

# Worker logs (collections & digests)
docker-compose logs -f worker

# Beat logs (scheduler)
docker-compose logs -f beat

# All logs
docker-compose logs -f

# Specific timeframe
docker-compose logs --since 1h api
docker-compose logs --tail 100 api
```

**System Metrics**
```bash
# Resource usage
docker stats

# Database size
docker-compose exec db psql -U aidar -d ai_radar -c \
  "SELECT pg_size_pretty(pg_database_size('ai_radar'));"

# Collection status
docker-compose logs --since 24h worker | grep -i "collection"

# Delivery logs
docker-compose exec db psql -U aidar -d ai_radar -c \
  "SELECT * FROM delivery_logs ORDER BY sent_at DESC LIMIT 10;"
```

**Scaling Workers**
```bash
# Single worker (default - use for testing)
docker-compose up -d

# Multiple workers (production)
docker-compose up -d --scale worker=3

# Increase API workers
# Edit docker-compose.yml: API_WORKERS=8
docker-compose restart api
```

---

## 🔧 Common Operations

### Restart Services

```bash
# Restart everything
docker-compose restart

# Restart specific service
docker-compose restart api
docker-compose restart worker
docker-compose restart beat

# Full rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Access Database Directly

```bash
# PostgreSQL shell
docker-compose exec db psql -U aidar -d ai_radar

# Once inside:
\dt                    # List tables
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM articles;
SELECT COUNT(*) FROM delivery_logs;
\q                     # Exit
```

### View Application Logs

```bash
# Last 50 lines of API errors
docker-compose logs api | grep ERROR

# Export all logs to file
docker-compose logs > logs-$(date +%Y%m%d-%H%M%S).txt

# Watch for specific pattern
docker-compose logs -f api | grep "collection"
```

### Manual Collection

```bash
# Trigger RSS collection
docker-compose exec -T api python -m app.collectors.rss_collector

# Trigger GitHub collection
docker-compose exec -T api python -m app.collectors.github_collector

# Generate digest
docker-compose exec -T api python -m app.generators.digest_generator
```

---

## 🐛 Troubleshooting

### Issue: Port Already in Use

**Error:** `Error response from daemon: Ports are not available`

**Solution:**
```bash
# Find what's using port 8000
lsof -i :8000  # macOS/Linux

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
# Find: ports: ["8000:8000"]
# Change to: ports: ["9000:8000"]
```

### Issue: Database Connection Failed

```bash
# Check database is running
docker-compose logs db | tail -20

# Restart database
docker-compose restart db

# Wait and try again
sleep 10
docker-compose exec db psql -U aidar -d ai_radar -c "SELECT 1;"
```

### Issue: Out of Memory

```bash
# Check memory
docker stats

# Free memory
docker-compose down -v

# Increase Docker memory (in Docker Desktop settings)
# Or restart Docker daemon

# Reduce workers in docker-compose.yml
API_WORKERS=2
docker-compose restart api
```

### Issue: Services Won't Start

```bash
# Check logs
docker-compose logs

# Force rebuild
docker-compose build --no-cache --force-rm

# Start fresh
docker-compose down -v
docker-compose up -d
```

---

## 📊 Monitoring Checklist

### Daily
- [ ] API responding: `curl http://localhost:8000/health`
- [ ] No ERROR logs: `docker-compose logs api | grep ERROR`
- [ ] Collections running: `docker-compose logs worker | grep collection`

### Weekly
- [ ] Database size: Check growth is reasonable
- [ ] Delivery success: Check logs for failures
- [ ] Resource usage: `docker stats`

### Monthly
- [ ] Backup database: `docker-compose exec db pg_dump -U aidar ai_radar > backup.sql`
- [ ] Update code: `git pull origin master`
- [ ] Security check: Review logs for suspicious activity

---

## 🚀 Next Steps

### Immediate
1. ✅ Email configured & tested
2. ✅ First user created
3. ✅ Services running
4. ✅ Monitoring set up

### Next 24 Hours
1. Send test digest manually
2. Add more users if needed
3. Configure Slack webhook (optional)
4. Monitor first collection cycle

### Next Week
1. Deploy to production server (AWS, Heroku, etc)
2. Set up automated backups
3. Enable monitoring/alerting
4. Create operations runbook

---

## 📞 Support

- **Quick Help**: `./scripts/full-deploy.sh` (explains each step)
- **Documentation**: See `DEPLOYMENT.md`, `PRODUCTION_RUNBOOK.md`
- **Issues**: https://github.com/ThePsychoWay/AI-Radar/issues
- **Logs**: `docker-compose logs -f`

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] All 5 services running: `docker-compose ps`
- [ ] API responds: `curl http://localhost:8000/health`
- [ ] Database accessible: `docker-compose exec db psql -U aidar -d ai_radar -c "SELECT 1;"`
- [ ] First user created: `docker-compose exec db psql -U aidar -d ai_radar -c "SELECT * FROM users;"`
- [ ] No major errors: `docker-compose logs | grep ERROR` (should be empty)
- [ ] Email configured: `docker-compose exec api python -m app.delivery_setup test`

---

**Ready to deploy? Run:** 
```bash
./scripts/full-deploy.sh docker
```

**Happy coding!** 🚀
