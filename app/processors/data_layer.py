"""
Unified Data Layer — Merge and deduplicate articles from all collectors.

Handles:
- Merging data from multiple sources (RSS, GitHub, HN, arXiv, HF)
- Deduplication by content similarity and direct ID matching
- Cross-source ID mapping
- Unified querying and filtering
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import asdict, dataclass, field
from pathlib import Path
from enum import Enum
import hashlib
from collections import defaultdict

from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)


class DeduplicationStrategy(Enum):
    """Strategies for deduplicating articles."""
    EXACT = "exact"           # Exact ID matching
    SIMILARITY = "similarity"  # URL/title similarity
    COMBINED = "combined"      # Both exact and similarity


@dataclass
class UnifiedArticle:
    """Article unified across sources with deduplication metadata."""
    
    # Core article data
    article: Article
    
    # Deduplication tracking
    source_articles: List[Article] = field(default_factory=list)  # All source versions
    canonical_source: str = ""  # Primary source
    sources: List[str] = field(default_factory=list)  # All sources found
    
    # Cross-source mapping
    source_ids: Dict[str, str] = field(default_factory=dict)  # source -> ID mapping
    
    # Unified metadata
    confidence: float = 1.0  # Dedup confidence (0-1)
    first_seen: str = ""
    last_seen: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "article": asdict(self.article),
            "source_articles": [asdict(a) for a in self.source_articles],
            "canonical_source": self.canonical_source,
            "sources": self.sources,
            "source_ids": self.source_ids,
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


class UnifiedDataLayer:
    """Unified data layer for all collected articles."""

    def __init__(self, strategy: DeduplicationStrategy = DeduplicationStrategy.COMBINED):
        """
        Initialize data layer.

        Args:
            strategy: Deduplication strategy to use.
        """
        self.strategy = strategy
        self.unified_articles: List[UnifiedArticle] = []
        self.id_map: Dict[str, int] = {}  # Maps source IDs to unified article index
        self.seen_content_hashes: Set[str] = set()  # For similarity dedup

    def add_articles(self, articles: List[Article], source: str) -> int:
        """
        Add articles from a source.

        Args:
            articles: List of Article objects.
            source: Source identifier (e.g., "rss", "github", "hackernews").

        Returns:
            Number of articles added/merged.
        """
        added = 0

        for article in articles:
            if self._add_or_merge_article(article, source):
                added += 1

        logger.info(f"✓ Added/merged {added} articles from {source}")
        return added

    def _add_or_merge_article(self, article: Article, source: str) -> bool:
        """
        Add article or merge with existing if duplicate.

        Args:
            article: Article to add.
            source: Source identifier.

        Returns:
            True if added/merged, False if skipped.
        """
        # Check for exact match
        unified_idx = self._find_exact_match(article, source)

        if unified_idx is not None:
            # Merge with existing
            self._merge_article(unified_idx, article, source)
            return True

        # Check for similarity match (if using similarity strategy)
        if self.strategy in (DeduplicationStrategy.SIMILARITY, DeduplicationStrategy.COMBINED):
            unified_idx = self._find_similarity_match(article)
            if unified_idx is not None:
                self._merge_article(unified_idx, article, source)
                return True

        # New article - create unified entry
        unified = UnifiedArticle(
            article=article,
            source_articles=[article],
            canonical_source=source,
            sources=[source],
            source_ids={source: article.id},
            confidence=1.0,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
        )

        # Store in unified articles
        idx = len(self.unified_articles)
        self.unified_articles.append(unified)

        # Register ID mapping
        self._register_id_mapping(article, source, idx)

        # Register content hash for similarity
        content_hash = self._compute_content_hash(article)
        self.seen_content_hashes.add(content_hash)

        return True

    def _find_exact_match(self, article: Article, source: str) -> Optional[int]:
        """
        Find exact match using source ID mapping.

        Args:
            article: Article to find.
            source: Source identifier.

        Returns:
            Index of unified article or None.
        """
        key = f"{source}:{article.id}"
        return self.id_map.get(key)

    def _find_similarity_match(self, article: Article, threshold: float = 0.8) -> Optional[int]:
        """
        Find similar match by URL or title.

        Args:
            article: Article to find.
            threshold: Similarity threshold (0-1).

        Returns:
            Index of unified article or None.
        """
        content_hash = self._compute_content_hash(article)

        # Check for exact hash match
        if content_hash in self.seen_content_hashes:
            for idx, unified in enumerate(self.unified_articles):
                if self._compute_content_hash(unified.article) == content_hash:
                    return idx

        # Check for URL similarity
        if article.url:
            for idx, unified in enumerate(self.unified_articles):
                if unified.article.url == article.url:
                    return idx

        # Check for title similarity
        if article.title and len(self.unified_articles) < 1000:  # Avoid O(n) for large sets
            title_hash = hashlib.sha256(article.title.lower().encode()).hexdigest()
            for idx, unified in enumerate(self.unified_articles):
                if hashlib.sha256(
                    unified.article.title.lower().encode()
                ).hexdigest() == title_hash:
                    return idx

        return None

    def _merge_article(self, unified_idx: int, article: Article, source: str) -> None:
        """
        Merge article into existing unified article.

        Args:
            unified_idx: Index of unified article.
            article: Article to merge.
            source: Source identifier.
        """
        unified = self.unified_articles[unified_idx]

        # Add source article
        if article not in unified.source_articles:
            unified.source_articles.append(article)

        # Add source if not already present
        if source not in unified.sources:
            unified.sources.append(source)

        # Register ID mapping
        self._register_id_mapping(article, source, unified_idx)

        # Update confidence (lower for merges)
        unified.confidence = max(0.5, unified.confidence - 0.1)

        # Update timestamps
        unified.last_seen = datetime.now().isoformat()

    def _register_id_mapping(self, article: Article, source: str, idx: int) -> None:
        """Register source ID to unified article mapping."""
        key = f"{source}:{article.id}"
        self.id_map[key] = idx

    @staticmethod
    def _compute_content_hash(article: Article) -> str:
        """
        Compute hash of article content for deduplication.

        Args:
            article: Article to hash.

        Returns:
            SHA-256 hash hex string.
        """
        content = f"{article.title}|{article.url}|{article.source}"
        return hashlib.sha256(content.encode()).hexdigest()

    def filter_by_source(self, source: str) -> List[UnifiedArticle]:
        """Filter unified articles by source."""
        return [u for u in self.unified_articles if source in u.sources]

    def filter_by_category(self, category: str) -> List[UnifiedArticle]:
        """Filter unified articles by category."""
        return [u for u in self.unified_articles if u.article.category == category]

    def filter_by_tag(self, tag: str) -> List[UnifiedArticle]:
        """Filter unified articles by tag."""
        return [u for u in self.unified_articles if tag in u.article.tags]

    def get_by_title(self, title_substring: str) -> List[UnifiedArticle]:
        """Search articles by title substring."""
        title_lower = title_substring.lower()
        return [
            u for u in self.unified_articles
            if title_lower in u.article.title.lower()
        ]

    def get_statistics(self) -> Dict:
        """Get statistics about unified data."""
        source_counts = defaultdict(int)
        category_counts = defaultdict(int)
        tag_counts = defaultdict(int)

        for unified in self.unified_articles:
            for source in unified.sources:
                source_counts[source] += 1

            category_counts[unified.article.category] += 1

            for tag in unified.article.tags:
                tag_counts[tag] += 1

        return {
            "total_unified_articles": len(self.unified_articles),
            "total_source_articles": sum(
                len(u.source_articles) for u in self.unified_articles
            ),
            "average_sources_per_article": (
                sum(len(u.sources) for u in self.unified_articles)
                / len(self.unified_articles)
                if self.unified_articles
                else 0
            ),
            "source_distribution": dict(source_counts),
            "category_distribution": dict(category_counts),
            "top_tags": sorted(
                tag_counts.items(), key=lambda x: x[1], reverse=True
            )[:10],
        }

    def save_to_json(self, output_dir: str = "data/processed") -> str:
        """
        Save unified data to JSON file.

        Args:
            output_dir: Directory to save to.

        Returns:
            Path to saved file.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(output_dir) / f"unified_{timestamp}.json"

        # Convert to dicts
        data = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "strategy": self.strategy.value,
                "total_unified": len(self.unified_articles),
                "statistics": self.get_statistics(),
            },
            "articles": [u.to_dict() for u in self.unified_articles],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Saved unified data to {filepath}")
        return str(filepath)

    def to_articles_list(self) -> List[Article]:
        """
        Export unified articles as Article objects (canonical versions).

        Returns:
            List of Article objects.
        """
        return [u.article for u in self.unified_articles]

    def __len__(self) -> int:
        """Number of unified articles."""
        return len(self.unified_articles)

    def __getitem__(self, idx: int) -> UnifiedArticle:
        """Get unified article by index."""
        return self.unified_articles[idx]


def main():
    """CLI example."""
    import sys

    logging.basicConfig(level=logging.INFO)

    # Example usage
    print("Unified Data Layer initialized")
    print("Example: Merge articles from multiple collectors")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
