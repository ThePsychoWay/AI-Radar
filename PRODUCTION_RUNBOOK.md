# AI RADAR Production Runbook

Operations guide for managing AI RADAR in production.

## 📋 Deployment Checklist

### Pre-Deployment (1 week before)

- [ ] Review and test all code changes
- [ ] Update CHANGELOG.md
- [ ] Create release branch
- [ ] Prepare deployment communication
- [ ] Schedule maintenance window if needed
- [ ] Backup production database
- [ ] Notify team of deployment schedule

### Infrastructure

- [ ] SSL certificates valid and ready
- [ ] DNS configured and propagating
- [ ] Load balancer configured
- [ ] CDN configured (if using)
- [ ] Monitoring alerts configured
- [ ] Log aggregation working
- [ ] Backup system tested

### Configuration

- [ ] `.env.production` reviewed and verified
- [ ] All API keys and secrets set
- [ ] Email service credentials working
- [ ] Slack webhook tested
- [ ] X (Twitter) API keys verified
- [ ] Database credentials secure
- [ ] Redis passwords set

### Data

- [ ] Database migrations prepared
- [ ] Data validation scripts ready
- [ ] Rollback plan documented
- [ ] Backup strategy confirmed

### Team Readiness

- [ ] Team trained on deployment process
- [ ] Incident response plan in place
- [ ] Communication channels open (Slack, etc)
- [ ] Escalation procedures documented

---

## 🚀 Deployment Steps

### 1. Pre-Deployment

```bash
# Create deployment branch
git checkout -b deploy/production-YYYY-MM-DD
git pull origin main

# Run all tests
pytest tests/ -v --tb=short

# Build Docker image locally
docker build -t ai-radar:test .

# Test image
docker run --rm ai-radar:test python -m pytest tests/ -v
```

### 2. Database Migrations

```bash
# Backup production database
docker-compose exec db pg_dump -U aidar ai_radar > backup-$(date +%Y%m%d-%H%M%S).sql

# Test migrations locally
alembic upgrade head

# Verify schema
docker-compose exec db psql -U aidar -d ai_radar -c "\dt"
```

### 3. Deployment

```bash
# Docker Compose deployment
docker-compose pull
docker-compose up -d --no-deps --build api worker beat

# Verify services
docker-compose ps
docker-compose logs --tail=50 api
docker-compose logs --tail=50 worker
```

### 4. Post-Deployment Verification

```bash
# Health checks
curl http://localhost:8000/health

# Check logs for errors
docker-compose logs api | grep ERROR
docker-compose logs worker | grep ERROR

# Verify database
docker-compose exec db psql -U aidar -d ai_radar -c "SELECT COUNT(*) FROM users;"

# Test delivery channels
python -m app.delivery_setup test

# Send test digest
docker-compose exec api python -c "from app.generators import DigestGenerator; print('OK')"
```

### 5. Monitoring

```bash
# Watch logs
docker-compose logs -f api

# Monitor resources
docker stats --no-stream

# Database performance
docker-compose exec db psql -U aidar -d ai_radar -c "SELECT query, calls FROM pg_stat_statements ORDER BY calls DESC LIMIT 10;"
```

---

## 🔄 Common Operations

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart api
docker-compose restart worker

# Full restart with rebuild
docker-compose up -d --build
```

### View Logs

```bash
# Real-time logs
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api

# Specific time range
docker-compose logs --since 2h api

# Export logs
docker-compose logs > logs-$(date +%Y%m%d).txt
```

### Database Operations

```bash
# Connect to database
docker-compose exec db psql -U aidar -d ai_radar

# Backup
docker-compose exec db pg_dump -U aidar ai_radar > backup.sql

# Restore
docker-compose exec -T db psql -U aidar ai_radar < backup.sql

# Vacuum & Analyze
docker-compose exec db psql -U aidar -d ai_radar -c "VACUUM ANALYZE;"

# Check size
docker-compose exec db psql -U aidar -d ai_radar -c "SELECT pg_size_pretty(pg_database_size('ai_radar'));"

# Get connection info
docker-compose exec db psql -U aidar -d ai_radar -c "SELECT datname, numbackends FROM pg_stat_database WHERE datname='ai_radar';"
```

### User Management

```python
from app.database import DatabaseManager, DeliveryChannel

db = DatabaseManager("postgresql://...")

# Create user
user = db.create_user(
    user_id="user_123",
    email="user@example.com",
    name="John Doe",
    timezone="Asia/Kolkata"
)

# Add email preference
db.add_delivery_preference(
    user_id="user_123",
    channel=DeliveryChannel.EMAIL,
    channel_address="user@example.com",
    enabled=True
)

# Get user
user = db.get_user_by_email("user@example.com")
print(user.is_subscribed())

# Get subscribed users
users = db.get_subscribed_users()
print(f"Active users: {len(users)}")
```

### Delivery Troubleshooting

```bash
# Test email
python -m app.delivery_setup email

# Test Slack
python -m app.delivery_setup slack

# Test webhooks
python -m app.delivery_setup webhooks

# Check delivery logs
docker-compose exec db psql -U aidar -d ai_radar -c \
  "SELECT * FROM delivery_logs ORDER BY sent_at DESC LIMIT 20;"

# Check failed deliveries
docker-compose exec db psql -U aidar -d ai_radar -c \
  "SELECT * FROM delivery_logs WHERE status='failed' ORDER BY sent_at DESC LIMIT 10;"
```

### Collection Status

```bash
# Check last collection
docker-compose exec db psql -U aidar -d ai_radar -c \
  "SELECT * FROM articles ORDER BY created_at DESC LIMIT 10;"

# Collection metrics
docker-compose logs worker | grep "Collection complete"

# Recent collections
docker-compose logs --since 24h worker | grep -i "collection\|articles"
```

---

## 🐛 Incident Response

### API Down

1. Check service status
   ```bash
   docker-compose ps
   docker-compose logs api | tail -50
   ```

2. Check dependencies
   ```bash
   docker-compose exec -T api curl http://db:5432
   docker-compose exec -T api redis-cli -h redis ping
   ```

3. Restart service
   ```bash
   docker-compose restart api
   ```

4. If still down, rollback
   ```bash
   git checkout previous-commit
   docker-compose up -d --build
   ```

### Database Issues

1. Check connection
   ```bash
   docker-compose exec db psql -U aidar -d ai_radar -c "SELECT 1;"
   ```

2. Check size and activity
   ```bash
   docker-compose exec db psql -U aidar -d ai_radar -c \
     "SELECT datname, numbackends, pg_size_pretty(pg_database_size(datname)) FROM pg_stat_database WHERE datname='ai_radar';"
   ```

3. Kill long-running queries
   ```bash
   docker-compose exec db psql -U aidar -d ai_radar -c \
     "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='ai_radar' AND state='active' AND query_start < NOW() - INTERVAL '1 hour';"
   ```

4. Restart database
   ```bash
   docker-compose restart db
   ```

### High Memory Usage

1. Check container stats
   ```bash
   docker stats
   ```

2. Check for memory leaks
   ```bash
   docker-compose logs api | grep -i "memory\|gc\|collect"
   ```

3. Restart leaking service
   ```bash
   docker-compose restart api
   ```

4. Implement memory limits
   ```yaml
   # docker-compose.yml
   api:
     ...
     mem_limit: 2g
     memswap_limit: 3g
   ```

### Delivery Failures

1. Check email configuration
   ```bash
   python -m app.delivery_setup email
   ```

2. Test SMTP connection
   ```bash
   docker-compose exec api python -c \
     "from app.delivery import SMTPEmailService; SMTPEmailService(...).test_connection()"
   ```

3. Check logs
   ```bash
   docker-compose logs --since 1h api | grep -i "email\|delivery"
   ```

4. Resend failed digests
   ```bash
   docker-compose exec api python -c "from app.delivery_manager import resend_failed_digests; resend_failed_digests()"
   ```

### Collection Failures

1. Check collection logs
   ```bash
   docker-compose logs --since 1h worker | grep -i "collection\|error"
   ```

2. Test collectors manually
   ```bash
   docker-compose exec api python -m app.collectors.rss_collector
   docker-compose exec api python -m app.collectors.github_collector
   ```

3. Check source availability
   ```bash
   curl https://news.ycombinator.com
   curl https://arxiv.org
   ```

4. Restart collection
   ```bash
   docker-compose restart worker
   ```

---

## 📊 Performance Tuning

### Database Performance

```sql
-- Add indexes
CREATE INDEX idx_articles_created_at ON articles(created_at);
CREATE INDEX idx_delivery_logs_user_sent ON delivery_logs(user_id, sent_at);
CREATE INDEX idx_user_preferences_user_channel ON user_preferences(user_id, channel);

-- Analyze table
ANALYZE articles;
ANALYZE delivery_logs;

-- Check query plans
EXPLAIN ANALYZE SELECT * FROM articles WHERE created_at > NOW() - INTERVAL '24h';
```

### Redis Optimization

```bash
# Monitor Redis
docker-compose exec redis redis-cli MONITOR

# Get memory info
docker-compose exec redis redis-cli INFO memory

# Clear cache
docker-compose exec redis redis-cli FLUSHALL

# Set memory limit
docker-compose exec redis redis-cli CONFIG SET maxmemory 1gb
docker-compose exec redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Application Performance

```bash
# Add caching
CACHE_TTL=3600

# Increase workers
API_WORKERS=8
CELERY_CONCURRENCY=4

# Connection pooling
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

---

## 📈 Monitoring Checklist

### Daily

- [ ] Check API health: `curl https://yourdomain.com/health`
- [ ] Verify digests sent: Check delivery logs
- [ ] Check error rates: Monitor logs and Sentry
- [ ] Database size: Growing as expected?
- [ ] API response time: < 200ms average

### Weekly

- [ ] Collection success rate > 95%
- [ ] Delivery success rate > 99%
- [ ] No uncaught errors in Sentry
- [ ] Database backups complete
- [ ] Disk space sufficient (>20% free)
- [ ] User signups growing

### Monthly

- [ ] Review logs for trends
- [ ] Database optimization
- [ ] Performance review
- [ ] Security audit
- [ ] Capacity planning
- [ ] Upgrade planning

---

## 🔐 Security Checklist

### Weekly

- [ ] Review access logs
- [ ] Check for suspicious activity
- [ ] Verify API rate limiting working
- [ ] Confirm SSL certificate valid

### Monthly

- [ ] Security patch updates
- [ ] Dependency updates
- [ ] Password rotation
- [ ] API key rotation
- [ ] Backup integrity check

---

## 📞 Escalation Procedures

### Severity Levels

**Critical (Page immediately)**
- API completely down
- Database down
- Data loss/corruption
- Security breach
- All digests failing

**High (Contact within 1 hour)**
- Partial service degradation
- >50% delivery failure
- Performance degradation >50%
- One collector failing

**Medium (Contact within 24 hours)**
- Single email failing
- Minor performance issue
- One user issue
- Non-critical bug

**Low (Next business day)**
- Documentation issue
- Feature request
- Minor UI issue

---

## 📞 Support Contacts

- **On-call**: [Team member on-call]
- **Slack**: #ai-radar-ops
- **Email**: ops@yourdomain.com
- **PagerDuty**: [Link]

---

## 📝 Change Log

### v1.0.0 - Initial Production

- [x] Phase 0-15 complete
- [x] All collectors operational
- [x] Email delivery working
- [x] GitHub Actions CI/CD
- [x] Docker deployment ready

---

## Resources

- DEPLOYMENT.md - Deployment guide
- README.md - Project overview
- GitHub: https://github.com/ThePsychoWay/AI-Radar
- Issues: https://github.com/ThePsychoWay/AI-Radar/issues
