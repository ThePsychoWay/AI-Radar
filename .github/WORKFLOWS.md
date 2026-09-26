# GitHub Actions Workflows

AI RADAR uses GitHub Actions for automated testing, collection, and digest generation.

## Available Workflows

### 1. CI Pipeline (`ci.yml`)

**Trigger:** Push to `master`, `main`, `develop`; Pull requests

**What it does:**
- Runs pytest suite on Python 3.11 and 3.12
- Linting with flake8
- Code quality checks (black, isort, pylint)
- Security scanning (bandit, safety)
- Coverage reporting
- Documentation generation

**Artifacts:**
- Coverage reports (HTML)
- Security reports (JSON)
- Documentation (HTML)

**Frequency:** On every commit/PR

---

### 2. Scheduled Collection (`scheduled-collection.yml`)

**Trigger:** Every 6 hours (0:00, 6:00, 12:00, 18:00 UTC) + manual trigger

**What it does:**
- Runs all 5 collectors (RSS, GitHub, HackerNews, arXiv, HuggingFace)
- Saves raw data as JSON
- Generates collection report
- Commits data to repo (with 7-day retention)
- Archives for inspection

**Collected Data:**
- `data/raw/rss_YYYYMMDD_HHMMSS.json`
- `data/raw/github_YYYYMMDD_HHMMSS.json`
- `data/raw/hackernews_YYYYMMDD_HHMMSS.json`
- `data/raw/arxiv_YYYYMMDD_HHMMSS.json`
- `data/raw/huggingface_YYYYMMDD_HHMMSS.json`
- `data/collection_report_YYYYMMDD_HHMMSS.json`

**Frequency:** Every 6 hours

---

### 3. Daily Digest (`daily-digest.yml`)

**Trigger:** Daily at 8:00 AM UTC (13:30 IST) + manual trigger

**What it does:**
1. Runs all collectors
2. Unifies data across sources
3. Deduplicates articles
4. Verifies quality
5. Ranks by importance
6. Generates multi-format digest:
   - Email HTML (with CSS)
   - Markdown
   - JSON

**Output Formats:**
- `output/digest_email_YYYYMMDD_HHMMSS.html` — Styled email template
- `output/digest_YYYYMMDD_HHMMSS.md` — Markdown version
- `output/digest_YYYYMMDD_HHMMSS.json` — Full metadata

**Frequency:** Daily at 8 AM UTC

---

## Schedule (UTC / IST)

| Workflow | UTC Time | IST Time | Frequency |
|----------|----------|----------|-----------|
| Scheduled Collection | 0, 6, 12, 18 | 5:30, 11:30, 17:30, 23:30 | Every 6 hours |
| Daily Digest | 8 | 13:30 | Once daily |

---

## Environment Variables

### Required
- `PYTHONUNBUFFERED=1` — Unbuffered Python output

### Optional
- `DEBUG=true` — Enable debug logging
- `LOG_LEVEL=INFO` — Set log level

---

## Secrets (Configure in GitHub Settings)

If integrating with external services, add these secrets:

```
X_API_KEY               # Twitter API key
X_API_SECRET            # Twitter API secret
X_ACCESS_TOKEN          # Twitter access token
X_ACCESS_TOKEN_SECRET   # Twitter token secret
X_BEARER_TOKEN          # Twitter bearer token

EMAIL_SMTP_SERVER       # SMTP server for email delivery
EMAIL_SMTP_PORT         # SMTP port
EMAIL_FROM_ADDRESS      # Sender email
EMAIL_PASSWORD          # Email password

GCS_BUCKET              # Google Cloud Storage bucket (for backups)
GCS_CREDENTIALS         # GCS service account JSON
```

---

## Workflow Configuration

### Cron Expressions

Workflows use cron expressions for scheduling:

```
minute hour day_of_month month day_of_week
  0     8      *          *       *         → Daily at 8 AM
  0    */6     *          *       *         → Every 6 hours
  0     0     */7         *       *         → Every 7 days
  0     9     *          *       1-5        → Weekdays at 9 AM
```

### Manual Triggers

All workflows support manual triggering via GitHub Actions tab:

1. Go to `Actions` tab
2. Select workflow
3. Click `Run workflow`
4. Confirm

---

## Monitoring

### Artifacts

- **Daily:** Check `daily-digests` artifact for generated digest
- **Hourly:** Check `collected-data` artifact for raw data

### Logs

Each workflow run shows:
- Collector statistics (articles per source)
- Processing metrics (dedup, verify, rank)
- Generation time
- File sizes
- Any errors

### Status Badge

Add to README:

```markdown
![CI Pipeline](https://github.com/ThePsychoWay/AI-Radar/workflows/CI%20Pipeline/badge.svg)
```

---

## Workflow Files

```
.github/
├── workflows/
│   ├── ci.yml                    # CI pipeline
│   ├── scheduled-collection.yml  # Data collection
│   └── daily-digest.yml          # Daily digest
└── WORKFLOWS.md                  # This file
```

---

## Troubleshooting

### Collection failures

Check the collection report JSON:
```bash
cat data/collection_report_*.json
```

If a collector fails:
1. Check logs for the specific collector
2. Verify API connectivity (test with `curl`)
3. Review rate limits for that source
4. Retry manually via `workflow_dispatch`

### Digest generation failures

Check error logs in the workflow run:
- Look for specific exception message
- Verify all articles have required fields
- Check for memory issues (size of unified data)

### CI failures

Common issues:
- **Import errors:** Check if all dependencies are in `requirements.txt`
- **Test failures:** Likely a code change broke existing tests
- **Coverage drop:** Some lines not covered by tests
- **Linting errors:** Code style violations

Fix locally:
```bash
# Format code
black app tests

# Sort imports
isort app tests

# Run tests
pytest tests/

# Check coverage
pytest tests/ --cov=app
```

---

## Performance

Typical workflow execution times:

| Workflow | Duration | Notes |
|----------|----------|-------|
| CI Pipeline | 60-120s | Varies by Python version |
| Collection | 120-180s | Depends on API response times |
| Digest | 180-300s | Includes all processing steps |

---

## Future Enhancements

- [ ] Email delivery (via SendGrid or AWS SES)
- [ ] Twitter/X posting workflow
- [ ] Slack notifications
- [ ] Weekly summary report
- [ ] Monthly trending analysis
- [ ] Cloud storage backup (S3, GCS)
- [ ] Performance benchmarking
- [ ] Custom webhook integration

---

For questions or issues, check the main `README.md`.
