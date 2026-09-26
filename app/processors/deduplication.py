"""
Deduplication Engine — Advanced duplicate detection and cross-source linking.

Strategies:
- Levenshtein distance for fuzzy string matching
- Semantic similarity (word set overlap)
- URL path analysis
- Cross-source link resolution
- Confidence scoring
"""

import logging
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass
from enum import Enum
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)


class SimilarityMetric(Enum):
    """Similarity metrics for comparison."""
    LEVENSHTEIN = "levenshtein"
    SEQUENCE = "sequence"
    SEMANTIC = "semantic"
    COMBINED = "combined"


@dataclass
class DuplicateCandidate:
    """A pair of articles that might be duplicates."""
    
    article1: Article
    article2: Article
    score: float  # 0-1, higher = more likely duplicate
    reason: str   # Why they're considered duplicates
    metrics: Dict[str, float] = None  # Individual metric scores
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class DeduplicationEngine:
    """Advanced deduplication using multiple similarity metrics."""

    def __init__(
        self,
        metric: SimilarityMetric = SimilarityMetric.COMBINED,
        threshold: float = 0.8,
    ):
        """
        Initialize deduplication engine.

        Args:
            metric: Similarity metric to use.
            threshold: Minimum score to consider as duplicate (0-1).
        """
        self.metric = metric
        self.threshold = threshold

    def find_duplicates(self, articles: List[Article]) -> List[DuplicateCandidate]:
        """
        Find all duplicate pairs in article list.

        Args:
            articles: List of articles to check.

        Returns:
            List of DuplicateCandidate objects.
        """
        duplicates = []

        for i, article1 in enumerate(articles):
            for article2 in articles[i + 1 :]:
                score, reason, metrics = self._compare_articles(article1, article2)

                if score >= self.threshold:
                    duplicates.append(
                        DuplicateCandidate(
                            article1=article1,
                            article2=article2,
                            score=score,
                            reason=reason,
                            metrics=metrics,
                        )
                    )

        # Sort by score descending
        duplicates.sort(key=lambda x: x.score, reverse=True)
        return duplicates

    def _compare_articles(
        self, article1: Article, article2: Article
    ) -> Tuple[float, str, Dict]:
        """
        Compare two articles using selected metric.

        Returns:
            (score, reason, metrics_dict)
        """
        metrics = {}

        # Check easy cases first
        if article1.url and article2.url and article1.url == article2.url:
            return 1.0, "exact_url_match", {"url": 1.0}

        # Compute individual metrics
        title_sim = self._title_similarity(article1.title, article2.title)
        metrics["title"] = title_sim

        url_sim = self._url_similarity(article1.url or "", article2.url or "")
        metrics["url"] = url_sim

        source_sim = 1.0 if article1.source == article2.source else 0.5
        metrics["source"] = source_sim

        # Combine metrics based on strategy
        if self.metric == SimilarityMetric.LEVENSHTEIN:
            score = title_sim
            reason = "levenshtein_title_match" if score >= self.threshold else "no_match"

        elif self.metric == SimilarityMetric.SEQUENCE:
            score = (title_sim + url_sim) / 2
            reason = "sequence_similarity" if score >= self.threshold else "no_match"

        elif self.metric == SimilarityMetric.SEMANTIC:
            semantic_sim = self._semantic_similarity(article1, article2)
            metrics["semantic"] = semantic_sim
            score = semantic_sim
            reason = "semantic_similarity" if score >= self.threshold else "no_match"

        else:  # COMBINED
            # Weighted combination
            score = (
                title_sim * 0.4 +
                url_sim * 0.3 +
                self._semantic_similarity(article1, article2) * 0.3
            )
            metrics["semantic"] = metrics.get("semantic", 0)
            reason = "combined_similarity" if score >= self.threshold else "no_match"

        return score, reason, metrics

    @staticmethod
    def _title_similarity(title1: str, title2: str) -> float:
        """
        Compare titles using fuzzy matching (Levenshtein-like).

        Uses difflib.SequenceMatcher for efficient comparison.
        """
        if not title1 or not title2:
            return 0.0

        # Normalize: lowercase, remove extra spaces
        t1 = " ".join(title1.lower().split())
        t2 = " ".join(title2.lower().split())

        if t1 == t2:
            return 1.0

        # Use SequenceMatcher for fuzzy comparison
        ratio = SequenceMatcher(None, t1, t2).ratio()
        return ratio

    @staticmethod
    def _url_similarity(url1: str, url2: str) -> float:
        """
        Compare URLs by path and domain.

        Returns:
            Similarity score 0-1.
        """
        if not url1 or not url2:
            return 0.0

        if url1 == url2:
            return 1.0

        # Parse URLs
        try:
            parsed1 = urlparse(url1)
            parsed2 = urlparse(url2)
        except Exception:
            return 0.0

        # Check domain
        domain1 = f"{parsed1.netloc}{parsed1.path}"
        domain2 = f"{parsed2.netloc}{parsed2.path}"

        if domain1 == domain2:
            return 1.0

        # Check if one is subset of other (e.g., tracking params)
        if domain1.startswith(domain2) or domain2.startswith(domain1):
            return 0.9

        # Fuzzy path matching
        path1 = parsed1.path.lower()
        path2 = parsed2.path.lower()

        if path1 and path2:
            ratio = SequenceMatcher(None, path1, path2).ratio()
            if ratio > 0.7:
                return ratio * 0.8  # Slightly discount path-only matches
        
        return 0.0

    @staticmethod
    def _semantic_similarity(article1: Article, article2: Article) -> float:
        """
        Compare articles semantically using word overlap and metadata.

        Returns:
            Similarity score 0-1.
        """
        # Extract key terms
        words1 = set(
            re.findall(r'\b\w+\b', article1.title.lower()) +
            re.findall(r'\b\w+\b', article1.summary.lower())
        )
        words2 = set(
            re.findall(r'\b\w+\b', article2.title.lower()) +
            re.findall(r'\b\w+\b', article2.summary.lower())
        )

        if not words1 or not words2:
            return 0.0

        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'it', 'this', 'that',
            'new', 'test', 'article', 'post', 'news', 'about'
        }
        
        words1 = words1 - stop_words
        words2 = words2 - stop_words

        if not words1 or not words2:
            return 0.0

        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        jaccard = intersection / union if union > 0 else 0.0

        # Tag overlap
        tags1 = set(article1.tags)
        tags2 = set(article2.tags)
        tag_overlap = len(tags1 & tags2) / max(len(tags1), len(tags2)) if (tags1 or tags2) else 0.0

        # Combined semantic score
        semantic_score = (jaccard * 0.7) + (tag_overlap * 0.3)

        return semantic_score

    def group_duplicates(
        self, articles: List[Article]
    ) -> List[List[Article]]:
        """
        Group articles into clusters of duplicates.

        Uses transitive closure: if A duplicates B and B duplicates C,
        then A, B, C are in the same group.

        Args:
            articles: List of articles to group.

        Returns:
            List of groups (each group is a list of duplicate articles).
        """
        if not articles:
            return []

        # Find all duplicates
        duplicates = self.find_duplicates(articles)

        # Build adjacency graph
        graph: Dict[int, Set[int]] = {i: set() for i in range(len(articles))}

        for dup in duplicates:
            idx1 = articles.index(dup.article1)
            idx2 = articles.index(dup.article2)
            graph[idx1].add(idx2)
            graph[idx2].add(idx1)

        # Find connected components (transitive closure)
        visited = set()
        groups = []

        def dfs(idx: int, group: List[int]) -> None:
            """Depth-first search to find connected component."""
            visited.add(idx)
            group.append(idx)
            for neighbor in graph[idx]:
                if neighbor not in visited:
                    dfs(neighbor, group)

        for i in range(len(articles)):
            if i not in visited:
                group = []
                dfs(i, group)
                groups.append([articles[j] for j in group])

        return groups

    def deduplicate(
        self, articles: List[Article], keep_first: bool = True
    ) -> List[Article]:
        """
        Deduplicate articles, keeping representative from each group.

        Args:
            articles: Articles to deduplicate.
            keep_first: If True, keep first article in each group.

        Returns:
            Deduplicated articles.
        """
        groups = self.group_duplicates(articles)

        result = []
        for group in groups:
            if keep_first:
                result.append(group[0])
            else:
                # Keep most popular (by score or likes)
                best = max(
                    group,
                    key=lambda a: a.metadata.get("score", a.metadata.get("likes", 0))
                )
                result.append(best)

        return result

    def get_statistics(self, duplicates: List[DuplicateCandidate]) -> Dict:
        """Generate statistics about found duplicates."""
        if not duplicates:
            return {
                "total_duplicates": 0,
                "high_confidence": 0,
                "medium_confidence": 0,
                "low_confidence": 0,
                "average_score": 0.0,
            }

        scores = [d.score for d in duplicates]

        return {
            "total_duplicates": len(duplicates),
            "high_confidence": sum(1 for d in duplicates if d.score >= 0.95),
            "medium_confidence": sum(1 for d in duplicates if 0.85 <= d.score < 0.95),
            "low_confidence": sum(1 for d in duplicates if d.score < 0.85),
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "most_common_reason": self._most_common(
                [d.reason for d in duplicates]
            ),
        }

    @staticmethod
    def _most_common(items: List[str]) -> str:
        """Find most common item in list."""
        if not items:
            return ""
        from collections import Counter
        return Counter(items).most_common(1)[0][0]


def main():
    """CLI example."""
    import sys

    logging.basicConfig(level=logging.INFO)

    print("Deduplication Engine initialized")
    print("Strategies: levenshtein, sequence, semantic, combined")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
