# CLAUDE.md — AI-RADAR Build Instructions

This document is for Claude Code: **how to autonomously build, test, and deploy each phase.**

## 🎯 How This Works
1. Phoenix says "**Phase N**" or describes a feature
2. Claude Code reads this file + relevant phase spec
3. Claude creates files, writes code, runs tests, commits/pushes
4. Phoenix only approves/confirms via GitHub

## 🚀 General Workflow for Each Phase

### Before Start
- Read the phase requirements below
- Create branch: `git checkout -b phase-N`
- Install/update dependencies if needed

### During Build
1. **Create/edit files** in the correct module (e.g., `app/collectors/` for collectors)
2. **Write unit tests** in `tests/` as you go
3. **Test locally**: `python -m pytest tests/`
4. **Git commit** with clear messages: `git add . && git commit -m "Phase N: <description>"`

### After Build
- **Run all tests**: `python -m pytest tests/ -v`
- **Git push**: `git push origin phase-N`
- **Create PR** (or merge if approved): `gh pr create --title "Phase N: ..." --body "..."`

---

## 📋 Phase Specifications

### Phase 0: Foundation ✓ DONE
- ✓ Folder structure (app/, config/, data/, output/, etc.)
- ✓ README.md, CLAUDE.md, .gitignore, requirements.txt, .env.example
- ✓ Git init, first commit
- **Deliverable:** Repo structure, ready for Phase 1

---

### Phase 1: RSS Collector
**Goal:** Fetch from 3-5 RSS feeds (AI/tech focused), normalize, save to `data/raw/`.

**Files to create:**
- `app/collectors/rss_collector.py` — Main logic
- `tests/test_rss_collector.py` — Unit tests

**Feeds (start with):**
- https://news.ycombinator.com/rss
- https://feeds.arstechnica.com/arstechnica/index (or another tech RSS)
- https://arxiv.org/rss/cs.AI
- Any other curated AI/ML RSS feed

**Output format:** Save each fetch as JSON to `data/raw/rss_TIMESTAMP.json`:
```json
[
  {
    "source": "hackernews",
    "id": "unique_id",
    "title": "...",
    "url": "...",
    "published": "ISO8601",
    "summary": "..."
  }
]
```

**Test:** Fetch from at least 2 feeds, verify JSON structure.

---

### Phase 2: GitHub Radar
**Goal:** Fetch trending AI/ML repos from GitHub public API (no auth needed), normalize, save.

**Files:**
- `app/collectors/github_collector.py`
- `tests/test_github_collector.py`

**Search topics:** `stars:>1000 language:python topic:machine-learning created:>2024-01-01`

**Output:** Same JSON format as Phase 1.

---

### Phase 3: Hugging Face
**Goal:** Fetch new models from Hugging Face public API.

**Files:**
- `app/collectors/hf_collector.py`
- `tests/test_hf_collector.py`

**API:** Use public HF API (no token needed for basic queries).
**Output:** Same JSON format.

---

### Phase 4: Hacker News
**Goal:** Fetch top AI/ML stories from Hacker News.

**Files:**
- `app/collectors/hn_collector.py`
- `tests/test_hn_collector.py`

**API:** Hacker News official API (free, no auth).
**Filter keywords:** AI, LLM, machine learning, neural, model, etc.
**Output:** Same JSON format.

---

### Phase 5: arXiv
**Goal:** Fetch recent papers from arXiv (AI/LLM/agent categories).

**Files:**
- `app/collectors/arxiv_collector.py`
- `tests/test_arxiv_collector.py`

**API:** arXiv public API.
**Categories:** cs.AI, cs.CL, cs.LG (machine learning).
**Output:** Same JSON format.

---

### Phase 6: Unified Data Layer
**Goal:** Create a common schema (pydantic model) that all sources normalize into.

**Files:**
- `app/models.py` — Pydantic schemas (Article, Source, etc.)
- `app/processors/normalizer.py` — Convert RSS/HF/HN/arXiv to schema

**Schema:**
```python
class Article(BaseModel):
    source: str  # "rss", "github", "hf", "hn", "arxiv"
    id: str
    title: str
    url: str
    summary: str
    published_at: datetime
    author: Optional[str]
    category: str  # "github", "paper", "story", etc.
    tags: List[str]
    metadata: dict  # source-specific extra data
```

---

### Phase 7: Deduplication
**Goal:** Detect duplicate articles (same URL, similar title+summary).

**Files:**
- `app/processors/deduplicator.py`

**Logic:**
- Exact URL match (highest priority)
- URL + title similarity (cosine)
- Title + summary semantic similarity (if budget allows)

**Output:** Deduplicated list, marked duplicates removed.

---

### Phase 8: Verification
**Goal:** Check source reliability, confirm URLs resolve, flag spam.

**Files:**
- `app/processors/verifier.py`

**Checks:**
- URL responds (200-299 status)
- Domain reputation (whitelist of trusted sources)
- Spam detection (simple heuristics: ALL CAPS, too many links, etc.)

---

### Phase 9: Importance Ranking
**Goal:** Score each article: impact × novelty × credibility × usefulness

**Files:**
- `app/analyzers/ranker.py`

**Score formula:**
```
importance = (impact * novelty * credibility * usefulness) / 100
where:
  impact: 0-25 (breaking vs. incremental)
  novelty: 0-25 (first mention vs. repeated)
  credibility: 0-25 (source trust)
  usefulness: 0-25 (relevance to AI practitioners)
```

---

### Phase 10: Personalization
**Goal:** Filter articles based on user topic preferences.

**Files:**
- `app/processors/personalizer.py`
- `config/preferences.yaml` (user preferences)

**Preferences format:**
```yaml
topics:
  high_priority: ["LLMs", "agents", "reasoning"]
  low_priority: ["news", "funding"]
sources:
  include: ["arxiv", "github"]
  exclude: ["reddit"]
```

---

### Phase 11: Decision Engine
**Goal:** Assign labels: IGNORE, SAVE, EXPERIMENT to each article.

**Files:**
- `app/analyzers/decision_engine.py`

**Labels:**
- **SAVE**: High-importance, must-read (rank > 15)
- **EXPERIMENT**: Interesting, lower priority (rank 8-15)
- **IGNORE**: Low relevance or excluded (rank < 8)

---

### Phase 12: Daily Digest Generator
**Goal:** Generate final Markdown digest with max 10-15 items.

**Files:**
- `app/generators/digest_generator.py`

**Sections:**
1. MUST KNOW (top SAVE items)
2. GITHUB RADAR (top repos)
3. MODEL RADAR (new models)
4. FOR ME (personalized, highest novelty)
5. IGNORE (for reference, bottom items)

**Output:** `output/digest_YYYYMMDD.md`

---

### Phase 13: Config Management
**Goal:** Move hardcoded settings to YAML, support X (Twitter) accounts list.

**Files:**
- `app/config_loader.py`
- `config/feeds.yaml` — RSS URLs
- `config/preferences.yaml` — User topics
- `config/x_accounts.yaml` — Curated X accounts (fallback if no X API)

---

### Phase 14: GitHub Actions Scheduler
**Goal:** Run AI-RADAR daily at 8 AM, push digest to output folder.

**Files:**
- `.github/workflows/daily-radar.yml`

**Trigger:** `schedule: - cron: "0 8 * * *"` (8 AM daily, adjust timezone)

---

### Phase 15: Delivery
**Goal:** Send digest to Email, Google Drive, Telegram (optional).

**Files:**
- `app/delivery/email_sender.py`
- `app/delivery/drive_uploader.py` (Google Drive)
- `app/delivery/telegram_bot.py` (Telegram)

---

## 🛠 Common Tasks

### Run tests
```bash
python -m pytest tests/ -v
```

### Test a single phase
```bash
python -m pytest tests/test_rss_collector.py -v
```

### Check code style
```bash
python -m flake8 app/ --max-line-length=100
```

### View current branch status
```bash
git status
```

### Push to GitHub
```bash
git push origin phase-N
```

---

## ⚠️ Critical Notes
1. **No manual CLI work** — Claude Code handles all git/creation.
2. **Phoenix only approves** — Describe what to build, Claude does it.
3. **One phase per request** — Keep each autonomous step focused.
4. **Tests first** — Write tests as you build, run `pytest` before push.
5. **Commit often** — Clear commit messages help track progress.

---

## 🎯 Success Criteria
- ✓ All phases complete
- ✓ Daily digest generating
- ✓ GitHub Actions scheduled
- ✓ Zero manual intervention
- ✓ ~₹50-100/month cost (Claude API only)
