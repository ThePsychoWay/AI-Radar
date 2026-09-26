# AI RADAR 🎯
**A Personal AI Intelligence System** — Automated daily digest of curated AI/tech news.

## 🎯 Purpose
Replace doomscrolling with a **5-10 minute daily digest** of 10-15 hand-picked AI/tech stories. No noise, no FOMO—just what matters.

## 🏗 Architecture
```
RSS/GitHub/HF/HN/arXiv → Normalize → Deduplicate → Verify → 
Classify → Rank → Filter → Digest → Email/Drive/Telegram
```

**16 Phases:**
0. Foundation (folder structure, README, git)
1-5. Data collectors (RSS, GitHub, Hugging Face, Hacker News, arXiv)
6-12. Processing pipeline (normalize, dedupe, verify, rank, personalize, digest)
13-15. Config, scheduler, delivery

## 🚀 Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your Anthropic API key, etc.

# Run daily digest
python app.py

# Schedule with GitHub Actions (coming in Phase 14)
```

## 📁 Project Structure
```
AI-Radar/
  app/
    collectors/      # Data source fetchers
    processors/      # Normalize, dedupe, verify
    analyzers/       # Importance ranking, classification
    generators/      # Digest generation
  config/            # YAML configs, ignore rules
  data/
    raw/             # Fresh fetches
    processed/       # Cleaned, merged data
  output/            # Generated digests
  prompts/           # Claude prompts for analysis
  tests/             # Unit tests
  README.md          # This file
  CLAUDE.md          # Instructions for Claude Code
  requirements.txt   # Python dependencies
  .env.example       # Environment template
  .gitignore         # Git ignore rules
```

## 🔑 Environment Variables
See `.env.example` for all required keys (Anthropic API key, etc.).

## 🤖 Built With
- **Python 3.9+**
- **Claude API** for intelligent analysis
- **GitHub Actions** for daily scheduling
- **SQLite** for local storage
- **Zero paid services** (except Claude API, ~₹50-100/month)

## 📝 Digest Sections
1. **MUST KNOW** — Breaking changes, critical research
2. **GITHUB RADAR** — Trending AI repos
3. **MODEL RADAR** — New models, benchmarks
4. **FOR ME** — Personalized picks based on preferences
5. **IGNORE** — Filtered out stories (FYI)

---
**Status:** Phase 0 Complete ✓  
**Next:** Phase 1 (RSS Collector)
