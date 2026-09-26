# 🚀 AI RADAR - Quick Start Guide (5 Minutes)

**For the impatient: Get AI RADAR running in 5 minutes!**

---

## Prerequisites

- Docker & Docker Compose (1 minute to install)
- A text editor

**That's it!**

---

## Step 1: Clone Repository (1 min)

```bash
git clone https://github.com/ThePsychoWay/AI-Radar.git
cd AI-Radar
```

---

## Step 2: Configure Environment (2 min)

```bash
# Copy template
cp .env.template .env

# Edit configuration (open in your favorite editor)
nano .env
# OR
vim .env
# OR
# Just open .env in VS Code, Sublime, etc
```

**Minimal configuration (get email working):**

```env
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=change-me-to-random-string

# Email (choose one option below)

# Option A: Gmail (for testing)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=your-email@gmail.com
EMAIL_SMTP_PASSWORD=your-app-password
EMAIL_FROM_ADDRESS=your-email@gmail.com

# Option B: SendGrid (recommended)
# Create free account at https://sendgrid.com
EMAIL_SMTP_SERVER=smtp.sendgrid.net
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=apikey
EMAIL_SMTP_PASSWORD=YOUR_SENDGRID_API_KEY_HERE
EMAIL_FROM_ADDRESS=noreply@yourdomain.com

# Slack (optional - skip if not using)
# Get from https://api.slack.com/apps → Incoming Webhooks
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## Step 3: Deploy (1 min)

```bash
# Make deployment script executable
chmod +x scripts/deploy.sh

# Run deployment
./scripts/deploy.sh docker
```

**What this does:**
1. ✅ Builds Docker images
2. ✅ Starts PostgreSQL, Redis, API, Worker, Beat, Nginx
3. ✅ Initializes database
4. ✅ Tests delivery channels
5. ✅ Shows you what's running

---

## Step 4: Verify It's Working (1 min)

```bash
# Check services are running
docker-compose ps

# Should see:
# - ai_radar_api running on port 8000
# - ai_radar_db running on port 5432
# - ai_radar_redis running on port 6379
# - ai_radar_worker running
# - ai_radar_beat running
# - ai_radar_nginx running on port 80

# Test API
curl http://localhost:8000/health

# View logs
docker-compose logs api
```

---

## ✅ You're Done!

**Your AI RADAR instance is running!**

### What's happening now:

1. 🔄 **Collection** - Every 6 hours (0, 6, 12, 18 UTC)
   - Fetches from 5 sources
   - Deduplicates & ranks
   - Stores results

2. 📧 **Digest Generation** - Daily at 8:00 AM UTC
   - Creates personalized digest
   - Formats for email
   - Sends to users

3. 👁️ **Monitoring** - Always running
   - GitHub Actions CI/CD
   - Health checks
   - Error tracking

---

## 📝 Common Tasks

### Create Your First User

```bash
docker-compose exec api python << 'EOF'
from app.database import DatabaseManager
from app.config import config

db = DatabaseManager(config.database.url)
user = db.create_user(
    user_id="user_1",
    email="your-email@example.com",
    name="Your Name",
    timezone="Asia/Kolkata"
)

# Add email delivery
db.add_delivery_preference(
    user_id="user_1",
    channel="email",
    channel_address="your-email@example.com",
    enabled=True
)

print(f"✓ User created: {user.email}")
EOF
```

### View Logs

```bash
# API logs
docker-compose logs -f api

# Worker logs
docker-compose logs -f worker

# All logs
docker-compose logs -f
```

### Stop Everything

```bash
docker-compose down
```

### Restart Services

```bash
docker-compose restart
```

### Remove Everything (Clean Slate)

```bash
docker-compose down -v  # -v removes volumes
rm ai_radar.db  # SQLite if used locally
```

---

## 🔧 Troubleshooting

### Port Already in Use

```bash
# Change port in docker-compose.yml
# Find:
#   ports:
#     - "8000:8000"
# Change to:
#   ports:
#     - "9000:8000"  # New external port
```

### Email Not Sending

```bash
# Test email configuration
docker-compose exec api python -m app.delivery_setup test

# Get guides
docker-compose exec api python -m app.delivery_setup guides
```

### Database Issues

```bash
# Check database
docker-compose exec db psql -U aidar -d ai_radar -c "SELECT 1;"

# Restart database
docker-compose restart db
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Reduce workers in docker-compose.yml
# Change API_WORKERS=8 to API_WORKERS=4
docker-compose restart api
```

---

## 📚 Next Steps

1. **Read Documentation**
   - `DEPLOYMENT.md` - Full deployment options
   - `PRODUCTION_RUNBOOK.md` - Operations guide
   - `README.md` - Project overview

2. **Configure Delivery**
   - Set up Slack (optional)
   - Add more email users
   - Configure webhooks (optional)

3. **Monitor Performance**
   - Check API response time
   - Monitor collection success
   - Track delivery rates

4. **Customize**
   - Add custom RSS feeds
   - Configure interest topics
   - Set up preferences

---

## 🆘 Help!

### Where to Get Help

- **Documentation**: See files in repository
- **Issues**: https://github.com/ThePsychoWay/AI-Radar/issues
- **Discussions**: https://github.com/ThePsychoWay/AI-Radar/discussions

### Common Questions

**Q: Where are my digests?**
A: First digest tomorrow at 8:00 AM UTC. Check logs: `docker-compose logs worker`

**Q: How do I add more users?**
A: Use the Python script above (Create Your First User)

**Q: Can I use SQLite instead of PostgreSQL?**
A: Yes! Set `DATABASE_URL=sqlite:///./ai_radar.db` in .env

**Q: How do I backup my data?**
A: See PRODUCTION_RUNBOOK.md section "Backup Strategy"

**Q: Can I scale to multiple servers?**
A: Yes! See DEPLOYMENT.md section "Scaling"

---

## 🎉 Congratulations!

**You now have a fully functional AI RADAR instance running!**

### What You Have:

✅ **5 Data Collectors**
- Hacker News, arXiv, GitHub, HuggingFace, RSS

✅ **Smart Processing**
- Deduplication, quality scoring, importance ranking
- Personalization engine

✅ **Multiple Delivery Methods**
- Email (HTML), Slack, Webhooks, X/Twitter

✅ **Automated Scheduling**
- Collections every 6 hours
- Daily digests at 8 AM UTC

✅ **Complete Infrastructure**
- Docker containerization
- PostgreSQL database
- Redis caching
- Nginx reverse proxy

✅ **Production Ready**
- GitHub Actions CI/CD
- Comprehensive monitoring
- Operations runbook
- Security hardened

---

## 🚀 Ready to Scale?

See `DEPLOYMENT.md` for:
- Heroku deployment (Easy cloud)
- AWS ECS deployment (Enterprise grade)
- Advanced configuration options
- Performance tuning

---

**Enjoy your AI RADAR! 🎯**
