# AI RADAR Deployment Guide

Complete guide to deploying AI RADAR to production.

## 📋 Pre-Deployment Checklist

- [ ] GitHub repository set up with AI RADAR code
- [ ] GitHub Actions secrets configured
- [ ] Environment variables created (.env.production)
- [ ] Database backup strategy in place
- [ ] SSL certificates ready (for HTTPS)
- [ ] Email service configured (SendGrid, AWS SES, etc)
- [ ] Slack workspace and webhook created
- [ ] Monitoring and logging setup (Sentry, etc)
- [ ] Domain name and DNS configured
- [ ] Docker Hub or registry account (for image hosting)

## 🚀 Deployment Options

### Option 1: Docker Compose (Recommended for Self-Hosted)

#### Prerequisites
- Docker & Docker Compose installed
- PostgreSQL 15+
- Redis 7+
- 2GB+ RAM, 10GB+ disk space

#### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/ThePsychoWay/AI-Radar.git
   cd AI-Radar
   ```

2. **Create environment file**
   ```bash
   cp .env.production .env.prod
   # Edit with your values
   nano .env.prod
   ```

3. **Build and start services**
   ```bash
   docker-compose --env-file .env.prod up -d
   ```

4. **Initialize database**
   ```bash
   docker-compose exec api python -m app.database
   ```

5. **Run migrations**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

6. **Verify deployment**
   ```bash
   curl http://localhost:8000/health
   docker-compose logs -f api
   ```

#### Health Checks

```bash
# API health
docker-compose exec api curl http://localhost:8000/health

# Database connection
docker-compose exec db psql -U aidar -d ai_radar -c "SELECT 1"

# Redis connection
docker-compose exec redis redis-cli ping

# View logs
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f beat
```

#### Updating

```bash
# Pull latest changes
git pull origin main

# Rebuild images
docker-compose build --no-cache

# Restart services
docker-compose up -d
```

---

### Option 2: Heroku (Easy Cloud Deployment)

#### Prerequisites
- Heroku account (free tier available)
- Heroku CLI installed
- Git repository initialized

#### Steps

1. **Create Heroku app**
   ```bash
   heroku create ai-radar-prod
   ```

2. **Add PostgreSQL**
   ```bash
   heroku addons:create heroku-postgresql:standard-0
   ```

3. **Add Redis**
   ```bash
   heroku addons:create heroku-redis:premium-0
   ```

4. **Set environment variables**
   ```bash
   heroku config:set ENVIRONMENT=production
   heroku config:set SECRET_KEY=your-secret-key
   heroku config:set EMAIL_SMTP_SERVER=smtp.sendgrid.net
   heroku config:set EMAIL_SMTP_PORT=587
   heroku config:set EMAIL_SMTP_USERNAME=apikey
   heroku config:set EMAIL_SMTP_PASSWORD=your-sendgrid-key
   # ... etc for all variables
   ```

5. **Deploy**
   ```bash
   git push heroku main
   ```

6. **Run migrations**
   ```bash
   heroku run python -m app.database
   ```

---

### Option 3: AWS ECS (Enterprise Grade)

#### Prerequisites
- AWS account with appropriate permissions
- AWS CLI configured
- ECR registry created

#### Steps

1. **Build and push Docker image**
   ```bash
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     123456789.dkr.ecr.us-east-1.amazonaws.com
   
   docker build -t ai-radar:latest .
   
   docker tag ai-radar:latest \
     123456789.dkr.ecr.us-east-1.amazonaws.com/ai-radar:latest
   
   docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-radar:latest
   ```

2. **Create RDS PostgreSQL database**
   ```bash
   aws rds create-db-instance \
     --db-instance-identifier ai-radar-db \
     --db-instance-class db.t3.micro \
     --engine postgres \
     --master-username aidar \
     --master-user-password <password>
   ```

3. **Create ElastiCache Redis**
   ```bash
   aws elasticache create-cache-cluster \
     --cache-cluster-id ai-radar-cache \
     --cache-node-type cache.t3.micro \
     --engine redis
   ```

4. **Create ECS cluster and services**
   - Create task definition for API
   - Create task definition for worker
   - Create task definition for beat
   - Create ECS services with load balancing

---

## 🔧 Configuration

### Environment Variables

See `.env.production` for all available variables.

**Critical variables:**
- `ENVIRONMENT=production`
- `SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- Email credentials (SMTP)
- Slack webhook URL
- X (Twitter) API credentials

### Email Configuration

**Option A: SendGrid (Recommended)**
```
EMAIL_SMTP_SERVER=smtp.sendgrid.net
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=apikey
EMAIL_SMTP_PASSWORD=<your-sendgrid-api-key>
```

**Option B: AWS SES**
```
EMAIL_SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=<ses-smtp-username>
EMAIL_SMTP_PASSWORD=<ses-smtp-password>
```

**Option C: Gmail (Testing only)**
```
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=your-email@gmail.com
EMAIL_SMTP_PASSWORD=<app-password>
```

### Slack Configuration

1. Create Slack app: https://api.slack.com/apps
2. Enable Incoming Webhooks
3. Add webhook to channel
4. Copy webhook URL to `SLACK_WEBHOOK_URL`

### X (Twitter) Configuration

1. Create app at https://developer.twitter.com/
2. Generate API keys and tokens
3. Set all X_* environment variables

---

## 📊 Monitoring & Logging

### Application Monitoring

**Using Sentry (Error Tracking)**
```bash
SENTRY_DSN=https://key@sentry.io/project
```

**Using DataDog**
```bash
DATADOG_API_KEY=your-key
DATADOG_APP_KEY=your-key
```

### Logs

**Docker Compose**
```bash
# View logs
docker-compose logs -f api
docker-compose logs -f worker

# Export logs
docker-compose logs api > logs.txt
```

**Heroku**
```bash
# Real-time logs
heroku logs --tail

# Search logs
heroku logs | grep ERROR
```

**AWS CloudWatch**
```bash
aws logs tail /ecs/ai-radar --follow
```

### Metrics

Monitor:
- API response time
- Collection success rate
- Digest generation time
- Delivery success rate
- Error rates
- Database query performance
- Redis cache hit rate

---

## 🔄 Scheduled Tasks

### Collection Schedule (Every 6 hours)

Default: 0, 6, 12, 18 UTC

Modify in `.env`:
```
COLLECTION_INTERVAL_HOURS=6
```

Or in GitHub Actions (`.github/workflows/scheduled-collection.yml`)

### Digest Schedule (Daily)

Default: 8:00 AM UTC (13:30 IST)

Modify:
```
DIGEST_SCHEDULE=0 8 * * *
```

Using cron format: `minute hour day month weekday`

---

## 💾 Backup Strategy

### Database Backups

**Automated (Recommended)**
- Enable automated backups in PostgreSQL
- AWS RDS: Automated backups with 7-day retention
- Heroku: Daily backups for 7 days

**Manual Backup**
```bash
# Docker Compose
docker-compose exec db pg_dump -U aidar ai_radar > backup.sql

# Restore
docker-compose exec -T db psql -U aidar ai_radar < backup.sql
```

### Data Directory Backups

```bash
# Backup data/ directory
tar czf data-backup-$(date +%Y%m%d).tar.gz data/

# Upload to S3
aws s3 cp data-backup-*.tar.gz s3://ai-radar-backups/
```

---

## 🔐 Security

### SSL/TLS

**Using Let's Encrypt (Free)**
```bash
# Docker Compose
docker run -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot certify \
  -d yourdomain.com

# Copy to nginx/ssl/
```

**Using Heroku**
```bash
heroku certs:add server.crt server.key
```

### Firewall Rules

- Allow port 80 (HTTP)
- Allow port 443 (HTTPS)
- Restrict database access to API servers only
- Restrict Redis access to internal only

### Rate Limiting

Enable rate limiting in nginx/load balancer:
```
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
```

---

## 📈 Scaling

### Vertical Scaling (Bigger Machine)

```bash
# Docker Compose
# Edit docker-compose.yml and increase:
api:
  ...
  environment:
    API_WORKERS=8  # From 4
```

### Horizontal Scaling (Multiple Machines)

**Docker Compose with multiple nodes:**
```bash
docker swarm init
docker stack deploy -c docker-compose.yml ai-radar
```

**Kubernetes:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-radar-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-radar
  template:
    metadata:
      labels:
        app: ai-radar
    spec:
      containers:
      - name: api
        image: 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-radar:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ai-radar-secrets
              key: database-url
```

---

## 🐛 Troubleshooting

### API Won't Start

```bash
# Check logs
docker-compose logs api

# Common issues:
# - Database connection: Check DATABASE_URL
# - Missing environment variables: Check .env file
# - Permission errors: Check Docker user
```

### Digests Not Sending

```bash
# Check email configuration
python -m app.delivery_setup test

# Check delivery logs
docker-compose exec db psql -U aidar -d ai_radar \
  -c "SELECT * FROM delivery_logs ORDER BY sent_at DESC LIMIT 10;"

# Check worker logs
docker-compose logs worker
```

### High Memory Usage

```bash
# Check Redis cache size
docker-compose exec redis redis-cli info memory

# Clear cache if needed
docker-compose exec redis redis-cli FLUSHDB

# Increase worker resources in docker-compose.yml
```

### Database Growth

```bash
# Check database size
docker-compose exec db psql -U aidar -d ai_radar \
  -c "SELECT pg_size_pretty(pg_database_size('ai_radar'));"

# Archive old data
python -m app.maintenance archive_old_articles --days 90

# Run VACUUM (maintenance)
docker-compose exec db psql -U aidar -d ai_radar \
  -c "VACUUM ANALYZE;"
```

---

## 📞 Support

- Issues: https://github.com/ThePsychoWay/AI-Radar/issues
- Email: support@ai-radar.example.com
- Docs: https://github.com/ThePsychoWay/AI-Radar/wiki

---

## ✅ Post-Deployment

1. ✓ Test all delivery channels
2. ✓ Verify scheduled tasks running
3. ✓ Set up monitoring and alerts
4. ✓ Document your setup
5. ✓ Create runbook for operations team
6. ✓ Set up incident response procedures
7. ✓ Schedule regular backups
8. ✓ Plan capacity management
