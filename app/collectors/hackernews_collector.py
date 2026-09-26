"""
Hacker News Collector — Fetch trending posts from Y Combinator Hacker News API.

Uses official HN Firebase API (no authentication required).
Fetches: top stories, best stories, newest stories.
Output: Normalized Article objects (HN posts as articles).
"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from dataclasses import asdict
from pathlib import Path
import hashlib

import requests

from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)

# Hacker News Firebase API
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
TOP_STORIES_URL = f"{HN_API_BASE}/topstories.json"
BEST_STORIES_URL = f"{HN_API_BASE}/beststories.json"
NEW_STORIES_URL = f"{HN_API_BASE}/newstories.json"


class HackerNewsCollector:
    """Collect trending posts from Hacker News."""

    # Story types to fetch
    STORY_TYPES = {
        "top": TOP_STORIES_URL,
        "best": BEST_STORIES_URL,
        "new": NEW_STORIES_URL,
    }

    def __init__(self, max_stories_per_type: int = 30, max_total: int = 100):
        """
        Initialize Hacker News collector.

        Args:
            max_stories_per_type: Maximum stories to fetch per type (top/best/new).
            max_total: Maximum total stories to collect.
        """
        self.max_stories_per_type = max_stories_per_type
        self.max_total = max_total
        self.articles: List[Article] = []
        self.session = requests.Session()

    def fetch_all(self) -> List[Article]:
        """
        Fetch trending stories from all types.

        Returns:
            List of normalized Article objects.
        """
        self.articles = []
        seen_stories = set()  # Track by story ID to avoid duplicates

        for story_type, url in self.STORY_TYPES.items():
            try:
                logger.info(f"Fetching {story_type} stories from Hacker News...")
                stories = self._fetch_stories(url, story_type, seen_stories)

                for story in stories:
                    story_id = story.metadata.get("hn_story_id")
                    if story_id not in seen_stories:
                        seen_stories.add(story_id)
                        self.articles.append(story)

                logger.info(f"✓ {story_type}: {len(stories)} stories added")

            except Exception as e:
                logger.error(f"✗ {story_type} fetch failed: {e}")

        # Limit to max_total
        self.articles = self.articles[: self.max_total]
        return self.articles

    def _fetch_stories(
        self, url: str, story_type: str, seen_ids: set
    ) -> List[Article]:
        """
        Fetch story IDs from a HN endpoint and normalize them.

        Args:
            url: API endpoint URL.
            story_type: Type of stories (top/best/new).
            seen_ids: Set of already-seen story IDs to skip.

        Returns:
            List of Article objects.
        """
        try:
            # Fetch list of story IDs
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            story_ids = response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to fetch story IDs: {e}")
            raise

        articles = []
        # Limit stories to fetch per type
        story_ids = story_ids[: self.max_stories_per_type]

        for story_id in story_ids:
            if story_id in seen_ids:
                continue

            try:
                story = self._fetch_and_normalize_story(story_id, story_type)
                if story:
                    articles.append(story)
            except Exception as e:
                logger.warning(f"Failed to fetch story {story_id}: {e}")

        return articles

    def _fetch_and_normalize_story(self, story_id: int, story_type: str) -> Optional[Article]:
        """
        Fetch a single story and normalize to Article.

        Args:
            story_id: HN story ID.
            story_type: Type (top/best/new) for categorization.

        Returns:
            Normalized Article or None if fetch fails.
        """
        url = f"{HN_API_BASE}/item/{story_id}.json"

        try:
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            story_data = response.json()

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch story {story_id}: {e}")
            return None

        # Skip if not a story type we want
        if story_data.get("type") not in ("story", "job"):
            return None

        # Skip if deleted
        if story_data.get("deleted") or story_data.get("dead"):
            return None

        return self._normalize_story(story_data, story_type)

    @staticmethod
    def _normalize_story(story: dict, story_type: str) -> Article:
        """
        Normalize a HN story to Article schema.

        Args:
            story: HN API story object.
            story_type: Type (top/best/new) for tagging.

        Returns:
            Normalized Article.
        """
        story_id = story.get("id", 0)
        article_id = hashlib.sha256(str(story_id).encode()).hexdigest()[:12]

        title = story.get("title", "Untitled")

        # Build summary from score, comments, and URL info
        score = story.get("score", 0)
        descendants = story.get("descendants", 0)
        story_url = story.get("url", "")

        summary_parts = [
            f"⬆️ {score} points",
            f"💬 {descendants} comments",
        ]
        if story_url and story_url.startswith("http"):
            try:
                # Extract domain from URL
                from urllib.parse import urlparse

                domain = urlparse(story_url).netloc.replace("www.", "")
                summary_parts.append(f"📍 {domain}")
            except Exception:
                pass

        summary = " | ".join(summary_parts)

        # Published time - convert Unix timestamp to ISO
        timestamp = story.get("time", 0)
        try:
            published_at = datetime.fromtimestamp(timestamp).isoformat()
        except (ValueError, OSError):
            published_at = datetime.now().isoformat()

        # Author
        author = story.get("by", None)

        # Tags
        tags = [story_type, "hacker-news", "tech-news"]
        story_type_label = story.get("type", "story")
        if story_type_label == "job":
            tags.append("job")

        # URL - prioritize story URL, fall back to HN comments link
        url = story_url
        if not url or not url.startswith("http"):
            url = f"https://news.ycombinator.com/item?id={story_id}"

        return Article(
            source="hacker-news",
            id=article_id,
            title=title,
            url=url,
            summary=summary,
            published_at=published_at,
            author=author,
            category="news",
            tags=tags,
            metadata={
                "hn_story_id": story_id,
                "score": score,
                "descendants": descendants,
                "story_type": story.get("type", "story"),
                "hn_comments_url": f"https://news.ycombinator.com/item?id={story_id}",
                "original_url": story_url,
                "story_category": story_type,
                "fetched_at": datetime.now().isoformat(),
            },
        )

    def save_to_json(self, output_dir: str = "data/raw") -> str:
        """
        Save collected stories to JSON file.

        Args:
            output_dir: Directory to save to.

        Returns:
            Path to saved file.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(output_dir) / f"hackernews_{timestamp}.json"

        # Convert articles to dicts
        articles_dict = [asdict(article) for article in self.articles]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(articles_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Saved {len(self.articles)} stories to {filepath}")
        return str(filepath)

    def to_json_string(self) -> str:
        """Return stories as JSON string."""
        articles_dict = [asdict(article) for article in self.articles]
        return json.dumps(articles_dict, indent=2, ensure_ascii=False)


def main():
    """CLI entry point."""
    import sys

    logging.basicConfig(level=logging.INFO)

    collector = HackerNewsCollector()
    stories = collector.fetch_all()

    print(f"\n{'='*60}")
    print(f"✓ Fetched {len(stories)} stories from Hacker News")
    print(f"{'='*60}")

    # Save to file
    filepath = collector.save_to_json()

    # Print sample
    if stories:
        print(f"\n📰 Sample stories:")
        for story in stories[:5]:
            meta = story.metadata
            print(f"  • {story.title}")
            print(f"    ⬆️ {meta.get('score', 0)} points | 💬 {meta.get('descendants', 0)} comments")
            print(f"    🔗 {story.url}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
