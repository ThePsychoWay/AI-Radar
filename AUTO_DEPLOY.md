# 🤖 FULLY AUTOMATED DEPLOYMENT

**One command. Everything automated. No manual steps.**

---

## Copy & Paste This On Your Local Machine

```bash
git clone https://github.com/ThePsychoWay/AI-Radar.git && cd AI-Radar && chmod +x scripts/auto-deploy.sh && ./scripts/auto-deploy.sh
```

That's it. Everything else is automatic.

---

## What It Does Automatically

✅ Checks Docker is installed  
✅ Clones/updates repository  
✅ Generates configuration (.env)  
✅ Creates random security keys  
✅ Builds Docker images (~2 min)  
✅ Starts all 6 services  
✅ Initializes database  
✅ Creates admin user  
✅ Verifies everything works  
✅ Shows monitoring dashboard  

---

## What You Get

**Immediately Running:**
- API Server at http://localhost:8000
- PostgreSQL Database
- Redis Cache
- Celery Workers
- Beat Scheduler
- Nginx Web Server

**Admin User Created:**
- Email: admin@aidar.local
- Ready to receive digests

**Collections Start In 6 Hours**
- Automatically fetches from 5 sources
- Deduplicates & ranks articles

**Digests Start Tomorrow at 1:30 PM IST**
- Personalized digest sent to admin user
- Via email (testing mode)

---

## During Deployment

You'll see:
```
╔════════════════════════════════════════════════════════════╗
║         AI RADAR - FULLY AUTOMATED DEPLOYMENT              ║
║                    ONE COMMAND SETUP                       ║
╚════════════════════════════════════════════════════════════╝

[10:30:45] STEP 1: Checking Prerequisites
✓ docker installed
✓ docker-compose installed
✓ git installed

[10:30:46] STEP 2: Repository Setup
→ Cloning AI RADAR repository...
✓ Repository cloned

[10:30:50] STEP 3: Auto-Generating Configuration
→ Generating .env file...
✓ Configuration file created

[10:31:05] STEP 5: Building Docker Images
This may take 2-3 minutes on first run...
✓ All Docker images built

[10:34:30] STEP 6: Starting Services
→ Starting containers...
✓ Containers started

[10:35:00] STEP 9: Creating Admin User
✓ Admin user created
  Email: admin@aidar.local
  User ID: user_abc123def456

[10:35:15] ✅ DEPLOYMENT COMPLETE!
```

---

## After Deployment

Script will offer to launch monitoring dashboard:
```
Launch monitoring dashboard? (auto-yes in 3s) [Y/n]
```

Press Enter or wait 3 seconds - starts real-time dashboard.

---

## Check Status

```bash
# View services
docker-compose ps

# View logs
docker-compose logs -f api

# Monitoring dashboard
./scripts/monitor.sh

# Stop services
docker-compose down

# Restart
docker-compose restart
```

---

## Email Configuration

**Current Setup:** MailHog (testing - shows emails in console)

**To Use Gmail:**
1. Update `.env`:
   ```
   EMAIL_SMTP_SERVER=smtp.gmail.com
   EMAIL_SMTP_USERNAME=your-email@gmail.com
   EMAIL_SMTP_PASSWORD=your-app-password
   ```
2. Restart: `docker-compose restart api`

**To Use SendGrid:**
1. Update `.env`:
   ```
   EMAIL_SMTP_SERVER=smtp.sendgrid.net
   EMAIL_SMTP_USERNAME=apikey
   EMAIL_SMTP_PASSWORD=SG.your-api-key
   ```
2. Restart: `docker-compose restart api`

---

## Troubleshooting

### Docker not found
```bash
# Install Docker
brew install docker docker-compose  # macOS
sudo apt-get install docker.io      # Ubuntu
# Or download Docker Desktop
```

### Port already in use
```bash
# Kill process using port 8000
lsof -i :8000
kill -9 <PID>

# Or restart Docker
docker-compose down
docker-compose up -d
```

### Build fails
```bash
# Rebuild fresh
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

---

## System Status

After deployment:

✅ **API Running**
- http://localhost:8000
- Responding to requests

✅ **Database Ready**
- PostgreSQL running
- Tables created
- Admin user created

✅ **Collections Scheduled**
- Every 6 hours automatically
- First run: 6 hours from deployment

✅ **Digests Scheduled**
- Daily at 8 AM UTC (1:30 PM IST)
- First digest: Tomorrow

✅ **Monitoring Active**
- Real-time dashboard
- Log tracking
- Error alerts

---

## That's It!

**One command deploys everything.**

No manual configuration needed. No copy-pasting secrets. No manual database setup.

Just run:
```bash
git clone https://github.com/ThePsychoWay/AI-Radar.git && cd AI-Radar && chmod +x scripts/auto-deploy.sh && ./scripts/auto-deploy.sh
```

**Your AI RADAR is ready.** 🚀

---

## Need Help?

- Check logs: `docker-compose logs -f api`
- View docs: `LOCAL_DEPLOYMENT.md`
- GitHub issues: https://github.com/ThePsychoWay/AI-Radar/issues
