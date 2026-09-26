"""
GitHub Collector — Fetch trending AI/ML repositories from GitHub public API.

Uses GitHub's public search API (no authentication required).
Searches for repos with: stars>1000, Python, machine-learning topics, recent.
Output: Normalized Article objects (repos as articles).
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

# GitHub API endpoint
GITHUB_API_BASE = "https://api.github.com"
SEARCH_ENDPOINT = f"{GITHUB_API_BASE}/search/repositories"


class GitHubCollector:
    """Collect trending AI/ML repositories from GitHub."""

    # Search queries for different AI/ML categories
    SEARCH_QUERIES = {
        "llm": 'stars:>1000 language:python topic:llm created:>2024-01-01',
        "machine-learning": 'stars:>1000 language:python topic:machine-learning created:>2024-06-01',
        "deep-learning": 'stars:>1000 language:python topic:deep-learning created:>2024-06-01',
        "ai": 'stars:>500 language:python topic:artificial-intelligence created:>2024-06-01',
        "agents": 'stars:>500 language:python topic:agent created:>2024-01-01',
        "computer-vision": 'stars:>1000 language:python topic:computer-vision created:>2024-06-01',
    }

    def __init__(self, per_page: int = 30, max_results: int = 100):
        """
        Initialize GitHub collector.

        Args:
            per_page: Results per request (max 100).
            max_results: Maximum total repos to fetch.
        """
        self.per_page = min(per_page, 100)
        self.max_results = max_results
        self.articles: List[Article] = []
        self.session = requests.Session()

    def fetch_all(self) -> List[Article]:
        """
        Fetch trending repos from all categories.

        Returns:
            List of normalized Article objects.
        """
        self.articles = []
        seen_repos = set()  # Track repos by full_name to avoid duplicates

        for category, query in self.SEARCH_QUERIES.items():
            try:
                logger.info(f"Searching GitHub for {category}...")
                repos = self._search_repos(query, category)
                
                # Filter duplicates
                new_repos = [
                    r for r in repos 
                    if r.metadata.get("repo_full_name") not in seen_repos
                ]
                
                for repo in new_repos:
                    seen_repos.add(repo.metadata["repo_full_name"])
                    self.articles.append(repo)
                
                logger.info(f"✓ {category}: {len(new_repos)} repos added")
                
            except Exception as e:
                logger.error(f"✗ {category} search failed: {e}")

        # Limit to max_results
        self.articles = self.articles[:self.max_results]
        return self.articles

    def _search_repos(self, query: str, category: str) -> List[Article]:
        """
        Search GitHub for repos matching query.

        Args:
            query: GitHub search query string.
            category: Category name for tagging.

        Returns:
            List of Article objects for matching repos.
        """
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": self.per_page,
        }

        try:
            response = self.session.get(
                SEARCH_ENDPOINT,
                params=params,
                timeout=10,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as e:
            logger.error(f"GitHub API error: {e}")
            raise

        articles = []
        for repo in data.get("items", []):
            try:
                article = self._normalize_repo(repo, category)
                articles.append(article)
            except Exception as e:
                logger.warning(f"Failed to normalize repo {repo.get('full_name')}: {e}")

        return articles

    @staticmethod
    def _normalize_repo(repo: dict, category: str) -> Article:
        """
        Normalize a GitHub repo to Article schema.

        Args:
            repo: GitHub API repository object.
            category: Category for tagging.

        Returns:
            Normalized Article.
        """
        full_name = repo.get("full_name", "unknown/repo")
        repo_id = hashlib.sha256(full_name.encode()).hexdigest()[:12]

        title = f"[{category.upper()}] {repo.get('name', 'Untitled')}"
        
        # Build description from repo info
        description_parts = []
        if repo.get("description"):
            description_parts.append(repo["description"])
        description_parts.append(f"⭐ {repo.get('stargazers_count', 0)} stars")
        if repo.get("language"):
            description_parts.append(f"📝 {repo['language']}")
        
        summary = " | ".join(description_parts)

        # Published date - use created_at if available
        published_at = repo.get("created_at", datetime.now().isoformat())
        if isinstance(published_at, str):
            published_at = published_at.split("T")[0] + "T00:00:00"

        # Extract topics as tags
        topics = repo.get("topics", [])
        if not topics:
            topics = []
        topics = list(set(topics + [category, "github", "repository"]))

        # Author
        owner = repo.get("owner", {})
        author = owner.get("login", None)

        return Article(
            source="github",
            id=repo_id,
            title=title,
            url=repo.get("html_url", ""),
            summary=summary,
            published_at=published_at,
            author=author,
            category="repository",
            tags=topics,
            metadata={
                "repo_full_name": full_name,
                "repo_name": repo.get("name", ""),
                "owner": owner.get("login", ""),
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language", ""),
                "open_issues": repo.get("open_issues_count", 0),
                "last_push": repo.get("pushed_at", ""),
                "description": repo.get("description", ""),
                "category": category,
                "fetched_at": datetime.now().isoformat(),
            },
        )

    def save_to_json(self, output_dir: str = "data/raw") -> str:
        """
        Save collected repos to JSON file.

        Args:
            output_dir: Directory to save to.

        Returns:
            Path to saved file.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(output_dir) / f"github_{timestamp}.json"

        # Convert articles to dicts
        articles_dict = [asdict(article) for article in self.articles]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(articles_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Saved {len(self.articles)} repos to {filepath}")
        return str(filepath)

    def to_json_string(self) -> str:
        """Return repos as JSON string."""
        articles_dict = [asdict(article) for article in self.articles]
        return json.dumps(articles_dict, indent=2, ensure_ascii=False)


def main():
    """CLI entry point."""
    import sys

    logging.basicConfig(level=logging.INFO)

    collector = GitHubCollector()
    repos = collector.fetch_all()

    print(f"\n{'='*60}")
    print(f"✓ Fetched {len(repos)} repos from GitHub")
    print(f"{'='*60}")

    # Save to file
    filepath = collector.save_to_json()

    # Print sample
    if repos:
        print(f"\n📦 Sample repositories:")
        for repo in repos[:5]:
            meta = repo.metadata
            print(f"  • {repo.title}")
            print(f"    ⭐ {meta.get('stars', 0)} | 🔀 {meta.get('forks', 0)} forks")
            print(f"    URL: {repo.url}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
