"""
RSS Collector — Fetch from multiple RSS feeds and normalize to common schema.

Supports: Hacker News, arXiv, tech blogs, etc.
Output: JSON files with normalized article format.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, asdict
import hashlib
from pathlib import Path

import feedparser

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Normalized article from any RSS source."""
    source: str  # "hackernews", "arxiv", "blog", etc.
    id: str  # Unique ID (hash of URL or source-provided ID)
    title: str
    url: str
    summary: str
    published_at: str  # ISO 8601
    author: Optional[str] = None
    category: str = "article"  # "news", "paper", "story", etc.
    tags: List[str] = None
    metadata: dict = None  # Source-specific extra data

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


class RSSCollector:
    """Collect articles from RSS feeds."""

    # Default feeds (AI/tech focused)
    DEFAULT_FEEDS = {
        "hackernews": "https://news.ycombinator.com/rss",
        "arxiv_ai": "https://arxiv.org/rss/cs.AI",
        "arxiv_ml": "https://arxiv.org/rss/cs.LG",
        "ycombinator_startup": "https://news.ycombinator.com/rss?scores=1",
    }

    def __init__(self, feeds: Optional[dict] = None, timeout: int = 10):
        """
        Initialize RSS collector.

        Args:
            feeds: Dict of feed_name -> feed_url. Defaults to DEFAULT_FEEDS.
            timeout: Request timeout in seconds.
        """
        self.feeds = feeds or self.DEFAULT_FEEDS
        self.timeout = timeout
        self.articles: List[Article] = []

    def fetch_all(self) -> List[Article]:
        """
        Fetch and normalize articles from all feeds.

        Returns:
            List of normalized Article objects.
        """
        self.articles = []

        for feed_name, feed_url in self.feeds.items():
            try:
                logger.info(f"Fetching {feed_name} from {feed_url}")
                articles = self._fetch_feed(feed_url, feed_name)
                self.articles.extend(articles)
                logger.info(f"✓ {feed_name}: {len(articles)} articles")
            except Exception as e:
                logger.error(f"✗ {feed_name} failed: {e}")

        return self.articles

    def _fetch_feed(self, url: str, source_name: str) -> List[Article]:
        """
        Fetch a single RSS feed and normalize articles.

        Args:
            url: Feed URL.
            source_name: Human-readable source name.

        Returns:
            List of normalized Article objects.
        """
        feed = feedparser.parse(url)

        if feed.bozo:
            logger.warning(f"Feed parsing warning for {source_name}: {feed.bozo_exception}")

        articles = []
        for entry in feed.entries[:50]:  # Limit to first 50 per feed
            try:
                article = self._normalize_entry(entry, source_name)
                articles.append(article)
            except Exception as e:
                logger.warning(f"Failed to normalize entry from {source_name}: {e}")

        return articles

    @staticmethod
    def _normalize_entry(entry, source_name: str) -> Article:
        """
        Normalize a feedparser entry to Article schema.

        Args:
            entry: feedparser entry object.
            source_name: Source feed name.

        Returns:
            Normalized Article.
        """
        # Extract fields with fallbacks
        title = entry.get("title", "Untitled")
        link = entry.get("link", "")
        summary = entry.get("summary", "")
        author = entry.get("author", None)

        # Parse published date
        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6]).isoformat()
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published_at = datetime(*entry.updated_parsed[:6]).isoformat()
        else:
            published_at = datetime.now().isoformat()

        # Generate unique ID from URL or title
        id_source = link or title
        article_id = hashlib.sha256(id_source.encode()).hexdigest()[:12]

        # Categorize by source
        if "arxiv" in source_name.lower():
            category = "paper"
            tags = ["research", "academic"]
        elif "hacker" in source_name.lower():
            category = "story"
            tags = ["news", "technology"]
        else:
            category = "article"
            tags = ["tech"]

        # Clean summary (remove HTML tags, limit length)
        summary = RSSCollector._clean_text(summary)[:500]

        return Article(
            source=source_name,
            id=article_id,
            title=title,
            url=link,
            summary=summary,
            published_at=published_at,
            author=author,
            category=category,
            tags=tags,
            metadata={
                "feed_source": source_name,
                "fetched_at": datetime.now().isoformat(),
            },
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove HTML tags and extra whitespace."""
        import re
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def save_to_json(self, output_dir: str = "data/raw") -> str:
        """
        Save collected articles to JSON file.

        Args:
            output_dir: Directory to save to.

        Returns:
            Path to saved file.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(output_dir) / f"rss_{timestamp}.json"

        # Convert articles to dicts
        articles_dict = [asdict(article) for article in self.articles]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(articles_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Saved {len(self.articles)} articles to {filepath}")
        return str(filepath)

    def to_json_string(self) -> str:
        """Return articles as JSON string."""
        articles_dict = [asdict(article) for article in self.articles]
        return json.dumps(articles_dict, indent=2, ensure_ascii=False)


def main():
    """CLI entry point."""
    import sys

    logging.basicConfig(level=logging.INFO)

    collector = RSSCollector()
    articles = collector.fetch_all()

    print(f"\n{'='*60}")
    print(f"✓ Fetched {len(articles)} articles from {len(collector.feeds)} feeds")
    print(f"{'='*60}")

    # Save to file
    filepath = collector.save_to_json()

    # Print sample
    if articles:
        print(f"\n📰 Sample articles:")
        for article in articles[:3]:
            print(f"  • {article.title[:60]}...")
            print(f"    Source: {article.source} | URL: {article.url[:50]}...")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
