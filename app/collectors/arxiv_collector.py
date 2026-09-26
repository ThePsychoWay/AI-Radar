"""
arXiv Collector — Fetch latest AI/ML papers from arXiv.

Uses unofficial arXiv API (no authentication required).
Searches: cs.AI, cs.LG, cs.NE, stat.ML categories for recent papers.
Output: Normalized Article objects (papers as articles).
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import asdict
from pathlib import Path
import hashlib
from urllib.parse import urlencode

import requests
import feedparser

from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)

# arXiv API endpoints
ARXIV_SEARCH_URL = "http://export.arxiv.org/api/query?"


class ArxivCollector:
    """Collect latest AI/ML papers from arXiv."""

    # arXiv categories for AI/ML research
    CATEGORIES = {
        "cs.AI": "Artificial Intelligence",
        "cs.LG": "Machine Learning",
        "cs.NE": "Neural and Evolutionary Computing",
        "stat.ML": "Statistics - Machine Learning",
        "cs.CL": "Computation and Language (NLP)",
        "cs.CV": "Computer Vision",
    }

    def __init__(self, max_papers_per_category: int = 30, max_total: int = 150, days_back: int = 7):
        """
        Initialize arXiv collector.

        Args:
            max_papers_per_category: Maximum papers per category.
            max_total: Maximum total papers to collect.
            days_back: How many days back to search (default: 7 days).
        """
        self.max_papers_per_category = max_papers_per_category
        self.max_total = max_total
        self.days_back = days_back
        self.articles: List[Article] = []
        self.session = requests.Session()

    def fetch_all(self) -> List[Article]:
        """
        Fetch papers from all categories.

        Returns:
            List of normalized Article objects.
        """
        self.articles = []
        seen_papers = set()  # Track by paper ID to avoid duplicates

        for category_code, category_name in self.CATEGORIES.items():
            try:
                logger.info(f"Searching arXiv for {category_name}...")
                papers = self._search_category(category_code, category_name, seen_papers)

                for paper in papers:
                    paper_id = paper.metadata.get("arxiv_id")
                    if paper_id not in seen_papers:
                        seen_papers.add(paper_id)
                        self.articles.append(paper)

                logger.info(f"✓ {category_code}: {len(papers)} papers added")

            except Exception as e:
                logger.error(f"✗ {category_code} search failed: {e}")

        # Limit to max_total
        self.articles = self.articles[: self.max_total]
        return self.articles

    def _search_category(self, category: str, category_name: str, seen_ids: set) -> List[Article]:
        """
        Search arXiv for papers in a category.

        Args:
            category: arXiv category code (e.g., "cs.AI").
            category_name: Human-readable category name.
            seen_ids: Set of already-seen paper IDs to skip.

        Returns:
            List of Article objects.
        """
        # Build search query with category and date constraint
        cutoff_date = (datetime.now() - timedelta(days=self.days_back)).strftime("%Y%m%d0000")
        query = f'cat:{category} AND submittedDate:[{cutoff_date} TO 9999999999]'

        params = {
            "search_query": query,
            "start": 0,
            "max_results": self.max_papers_per_category,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            url = ARXIV_SEARCH_URL + urlencode(params)
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

        except requests.RequestException as e:
            logger.error(f"Failed to fetch from arXiv: {e}")
            raise

        # Parse Atom feed
        feed = feedparser.parse(response.content)
        articles = []

        for entry in feed.get("entries", []):
            try:
                paper_id = self._extract_arxiv_id(entry.get("id", ""))
                if paper_id in seen_ids:
                    continue

                article = self._normalize_paper(entry, category, category_name)
                if article:
                    articles.append(article)

            except Exception as e:
                logger.warning(f"Failed to normalize paper: {e}")

        return articles

    @staticmethod
    def _extract_arxiv_id(arxiv_url: str) -> str:
        """Extract paper ID from arXiv URL."""
        if "/abs/" in arxiv_url:
            return arxiv_url.split("/abs/")[-1]
        return arxiv_url

    @staticmethod
    def _normalize_paper(entry: dict, category: str, category_name: str) -> Optional[Article]:
        """
        Normalize an arXiv paper to Article schema.

        Args:
            entry: feedparser entry (paper).
            category: arXiv category code.
            category_name: Human-readable category name.

        Returns:
            Normalized Article or None.
        """
        try:
            # Extract fields
            arxiv_url = entry.get("id", "")
            arxiv_id = ArxivCollector._extract_arxiv_id(arxiv_url)
            article_id = hashlib.sha256(arxiv_id.encode()).hexdigest()[:12]

            title = entry.get("title", "Untitled").strip()
            summary = entry.get("summary", "").strip()

            # Parse authors
            authors = entry.get("authors", [])
            author_list = [a.get("name", "") for a in authors if a.get("name")]
            first_author = author_list[0] if author_list else None
            author_str = ", ".join(author_list[:3])  # First 3 authors
            if len(author_list) > 3:
                author_str += f", +{len(author_list) - 3} more"

            # Published date
            published_date = entry.get("published", "")
            if published_date:
                published_date = published_date.split("T")[0] + "T00:00:00"

            # Extract categories from entry
            tags = [category, "arxiv", "research-paper"]
            if "categories" in entry:
                cats = entry["categories"]
                if isinstance(cats, list):
                    for cat_entry in cats:
                        if isinstance(cat_entry, dict):
                            cat_term = cat_entry.get("term", "")
                        else:
                            cat_term = str(cat_entry)
                        if cat_term and cat_term not in tags:
                            tags.append(cat_term)

            # PDF link
            pdf_url = arxiv_url.replace("/abs/", "/pdf/") + ".pdf"

            return Article(
                source="arxiv",
                id=article_id,
                title=title,
                url=arxiv_url,
                summary=summary,
                published_at=published_date,
                author=first_author,
                category="research-paper",
                tags=tags,
                metadata={
                    "arxiv_id": arxiv_id,
                    "authors": author_list,
                    "authors_formatted": author_str,
                    "pdf_url": pdf_url,
                    "category_code": category,
                    "category_name": category_name,
                    "published_date": published_date,
                    "fetched_at": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            logger.warning(f"Failed to normalize paper: {e}")
            return None

    def save_to_json(self, output_dir: str = "data/raw") -> str:
        """
        Save collected papers to JSON file.

        Args:
            output_dir: Directory to save to.

        Returns:
            Path to saved file.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(output_dir) / f"arxiv_{timestamp}.json"

        # Convert articles to dicts
        articles_dict = [asdict(article) for article in self.articles]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(articles_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Saved {len(self.articles)} papers to {filepath}")
        return str(filepath)

    def to_json_string(self) -> str:
        """Return papers as JSON string."""
        articles_dict = [asdict(article) for article in self.articles]
        return json.dumps(articles_dict, indent=2, ensure_ascii=False)


def main():
    """CLI entry point."""
    import sys

    logging.basicConfig(level=logging.INFO)

    collector = ArxivCollector()
    papers = collector.fetch_all()

    print(f"\n{'='*60}")
    print(f"✓ Fetched {len(papers)} papers from arXiv")
    print(f"{'='*60}")

    # Save to file
    filepath = collector.save_to_json()

    # Print sample
    if papers:
        print(f"\n📄 Sample papers:")
        for paper in papers[:5]:
            meta = paper.metadata
            print(f"  • {paper.title}")
            print(f"    👤 {meta.get('authors_formatted', 'Unknown')}")
            print(f"    📑 {paper.metadata['category_name']} ({meta['category_code']})")
            print(f"    🔗 {paper.url}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
