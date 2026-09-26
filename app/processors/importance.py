"""
Importance Ranking Engine — Article importance scoring based on multiple factors.

Evaluates:
- Source authority (from verification scores)
- Engagement metrics (likes, stars, upvotes)
- Recency and freshness decay
- Topic relevance and keyword matching
- Trend velocity (increasing attention)
- Author reputation
- Citation/reference counts
- User interest alignment
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta, timezone
import re
from math import log, exp

from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)


class ImportanceLevel(Enum):
    """Article importance classification."""
    CRITICAL = "critical"  # Must read (9.0-10.0)
    VERY_HIGH = "very_high"  # Highly important (7.5-8.9)
    HIGH = "high"  # Important (6.0-7.4)
    MODERATE = "moderate"  # Worth reading (4.0-5.9)
    LOW = "low"  # Optional (2.0-3.9)
    MINIMAL = "minimal"  # Skip (0.0-1.9)


@dataclass
class ImportanceScore:
    """Complete importance assessment."""

    article: Article
    overall_score: float  # 0-10, aggregate importance
    importance_level: ImportanceLevel

    # Component scores (0-10)
    authority_score: float  # Source trust + author reputation
    engagement_score: float  # Engagement metrics
    recency_score: float  # Freshness with decay
    relevance_score: float  # Topic/keyword matching
    trend_score: float  # Trending velocity
    citation_score: float  # References/mentions

    # Metadata
    reasoning: List[str] = None  # Why this score
    trending: bool = False  # Whether trending
    trending_velocity: float = 0.0  # Change per day
    matched_interests: List[str] = None  # Matched user interests

    def __post_init__(self):
        if self.reasoning is None:
            self.reasoning = []
        if self.matched_interests is None:
            self.matched_interests = []


class ImportanceRankingEngine:
    """Advanced article importance scoring."""

    def __init__(
        self,
        source_authority_weight: float = 0.20,
        engagement_weight: float = 0.15,
        recency_weight: float = 0.15,
        relevance_weight: float = 0.25,
        trend_weight: float = 0.15,
        citation_weight: float = 0.10,
        user_interests: Optional[List[str]] = None,
    ):
        """
        Initialize importance ranking engine.

        Args:
            source_authority_weight: Weight for source authority (0-1).
            engagement_weight: Weight for engagement metrics.
            recency_weight: Weight for freshness.
            relevance_weight: Weight for topic relevance.
            trend_weight: Weight for trending velocity.
            citation_weight: Weight for citations.
            user_interests: List of user interest keywords/tags.
        """
        # Validate weights sum to 1.0
        total_weight = (
            source_authority_weight
            + engagement_weight
            + recency_weight
            + relevance_weight
            + trend_weight
            + citation_weight
        )
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total_weight}, not 1.0")

        self.source_authority_weight = source_authority_weight
        self.engagement_weight = engagement_weight
        self.recency_weight = recency_weight
        self.relevance_weight = relevance_weight
        self.trend_weight = trend_weight
        self.citation_weight = citation_weight
        self.user_interests = user_interests or []

        # Known high-authority sources
        self.high_authority_sources = {
            "arxiv", "nature", "science", "ieee", "acm",
            "hackernews", "github", "medium", "techcrunch"
        }

    def rank_article(
        self,
        article: Article,
        verification_score: Optional[float] = None,
        engagement_metrics: Optional[Dict] = None,
        trending_data: Optional[Dict] = None,
    ) -> ImportanceScore:
        """
        Comprehensively rank an article's importance.

        Args:
            article: Article to rank.
            verification_score: Source reliability (0-1, from verification engine).
            engagement_metrics: Dict with 'score', 'stars', 'upvotes', 'views', 'likes'.
            trending_data: Dict with 'velocity', 'trend_direction', 'mentions_per_day'.

        Returns:
            ImportanceScore with detailed assessment.
        """
        reasoning = []

        # Calculate component scores
        authority_score = self._calculate_authority_score(
            article, verification_score, reasoning
        )

        engagement_score = self._calculate_engagement_score(
            article, engagement_metrics, reasoning
        )

        recency_score = self._calculate_recency_score(article, reasoning)

        relevance_score, matched_interests = self._calculate_relevance_score(
            article, reasoning
        )

        trend_score, trending, velocity = self._calculate_trend_score(
            trending_data, reasoning
        )

        citation_score = self._calculate_citation_score(article, reasoning)

        # Calculate weighted overall score (0-10 scale)
        overall_score = (
            authority_score * self.source_authority_weight
            + engagement_score * self.engagement_weight
            + recency_score * self.recency_weight
            + relevance_score * self.relevance_weight
            + trend_score * self.trend_weight
            + citation_score * self.citation_weight
        )

        # Determine importance level
        if overall_score >= 9.0:
            importance_level = ImportanceLevel.CRITICAL
        elif overall_score >= 7.5:
            importance_level = ImportanceLevel.VERY_HIGH
        elif overall_score >= 6.0:
            importance_level = ImportanceLevel.HIGH
        elif overall_score >= 4.0:
            importance_level = ImportanceLevel.MODERATE
        elif overall_score >= 2.0:
            importance_level = ImportanceLevel.LOW
        else:
            importance_level = ImportanceLevel.MINIMAL

        return ImportanceScore(
            article=article,
            overall_score=overall_score,
            importance_level=importance_level,
            authority_score=authority_score,
            engagement_score=engagement_score,
            recency_score=recency_score,
            relevance_score=relevance_score,
            trend_score=trend_score,
            citation_score=citation_score,
            reasoning=reasoning,
            trending=trending,
            trending_velocity=velocity,
            matched_interests=matched_interests,
        )

    def _calculate_authority_score(
        self, article: Article, verification_score: Optional[float], reasoning: List[str]
    ) -> float:
        """Score based on source authority and author reputation."""
        score = 5.0  # Baseline

        # Use verification score if provided
        if verification_score is not None:
            verification_component = verification_score * 8.0  # Scale to 0-8
            score = 2.0 + verification_component
        else:
            # Heuristic: check source
            source_lower = (article.source or "").lower()
            if any(auth in source_lower for auth in self.high_authority_sources):
                score += 2.0
                reasoning.append("High-authority source")

        # Author reputation (heuristic)
        if article.author and len(article.author) > 3:
            score += 0.5
            if any(title in article.author.lower() for title in ["dr", "prof", "phd"]):
                score += 1.0
                reasoning.append("Academic author")

        return min(10.0, score)

    def _calculate_engagement_score(
        self, article: Article, engagement_metrics: Optional[Dict], reasoning: List[str]
    ) -> float:
        """Score based on engagement metrics (likes, stars, upvotes, views)."""
        score = 3.0  # Baseline

        if engagement_metrics:
            # Score (HN, Reddit upvotes)
            hn_score = engagement_metrics.get("score", 0)
            if hn_score > 500:
                score += 3.0
                reasoning.append(f"High engagement (score: {hn_score})")
            elif hn_score > 200:
                score += 2.0
            elif hn_score > 50:
                score += 1.0

            # Stars (GitHub)
            stars = engagement_metrics.get("stars", 0)
            if stars > 5000:
                score += 3.0
                reasoning.append(f"Very popular (stars: {stars})")
            elif stars > 1000:
                score += 2.0
            elif stars > 100:
                score += 1.0

            # Generic upvotes/likes
            upvotes = engagement_metrics.get("upvotes", 0) or engagement_metrics.get("likes", 0)
            if upvotes > 1000:
                score += 2.0
            elif upvotes > 100:
                score += 1.0

            # Views (if significant)
            views = engagement_metrics.get("views", 0)
            if views > 100000:
                score += 2.0
                reasoning.append(f"Widely read (views: {views})")

        else:
            # Heuristic from article metadata
            metadata_score = article.metadata.get("score", 0) if article.metadata else 0
            if metadata_score > 0:
                # Log scale for large numbers
                score += min(5.0, log(max(1, metadata_score + 1)) / 2)

        return min(10.0, score)

    def _calculate_recency_score(self, article: Article, reasoning: List[str]) -> float:
        """Score based on recency with decay curve."""
        if not article.published_at:
            return 5.0  # Unknown date

        now = datetime.now(timezone.utc)
        if article.published_at.tzinfo is None:
            now = datetime.now()

        age_days = (now - article.published_at).days

        if age_days < 0:
            return 5.0  # Future date, uncertain

        # Decay curve: fresh articles score high, old articles decay
        if age_days == 0:
            score = 10.0
            reasoning.append("Published today")
        elif age_days <= 1:
            score = 9.5
        elif age_days <= 7:
            score = 8.0 - (age_days * 0.2)
            reasoning.append(f"Recent ({age_days} days old)")
        elif age_days <= 30:
            score = 7.0 - ((age_days - 7) * 0.15)
        elif age_days <= 90:
            score = 6.0 - ((age_days - 30) * 0.05)
        else:
            score = max(2.0, 5.0 - ((age_days - 90) * 0.01))
            reasoning.append(f"Older article ({age_days} days)")

        return max(0.0, min(10.0, score))

    def _calculate_relevance_score(
        self, article: Article, reasoning: List[str]
    ) -> Tuple[float, List[str]]:
        """Score based on topic relevance and keyword matching."""
        score = 5.0  # Baseline
        matched_interests = []

        if not self.user_interests:
            return score, matched_interests

        # Extract keywords from article
        title_lower = (article.title or "").lower()
        summary_lower = (article.summary or "").lower()
        tags = [t.lower() for t in (article.tags or [])]
        content = f"{title_lower} {summary_lower}"

        # Match user interests
        for interest in self.user_interests:
            interest_lower = interest.lower()

            # Direct tag match (high confidence)
            if interest_lower in tags:
                score += 2.0
                matched_interests.append(interest)
                reasoning.append(f"Tagged: {interest}")

            # Title match (high confidence)
            elif interest_lower in title_lower or re.search(
                rf"\b{re.escape(interest_lower)}\b", title_lower
            ):
                score += 1.5
                matched_interests.append(interest)
                reasoning.append(f"Title match: {interest}")

            # Content match (lower confidence)
            elif re.search(rf"\b{re.escape(interest_lower)}\b", content):
                score += 0.5
                matched_interests.append(interest)

        if matched_interests:
            reasoning.append(f"Matches interests: {', '.join(matched_interests)}")

        return min(10.0, score), matched_interests

    def _calculate_trend_score(
        self, trending_data: Optional[Dict], reasoning: List[str]
    ) -> Tuple[float, bool, float]:
        """Score based on trending velocity and momentum."""
        score = 4.0  # Baseline
        trending = False
        velocity = 0.0

        if trending_data:
            velocity = trending_data.get("velocity", 0.0)
            mentions_per_day = trending_data.get("mentions_per_day", 0)
            trend_direction = trending_data.get("trend_direction", "stable")  # up, down, stable

            if trend_direction == "up":
                trending = True
                # Score based on velocity
                if velocity > 10:  # 10+ new mentions/day
                    score = 9.0
                    reasoning.append(f"Rapidly trending (velocity: {velocity:.1f})")
                elif velocity > 5:
                    score = 7.5
                    reasoning.append(f"Trending (velocity: {velocity:.1f})")
                elif velocity > 2:
                    score = 6.0
                    reasoning.append(f"Slowly trending (velocity: {velocity:.1f})")
                else:
                    score = 5.0

            elif trend_direction == "down":
                score = 3.0
                reasoning.append("Trending downward")

            # High mention count
            if mentions_per_day > 100:
                score = min(10.0, score + 2.0)
                reasoning.append(f"High volume (mentions: {mentions_per_day}/day)")

        return min(10.0, score), trending, velocity

    def _calculate_citation_score(self, article: Article, reasoning: List[str]) -> float:
        """Score based on citations or reference count."""
        score = 4.0  # Baseline

        # Check metadata for citation count
        if article.metadata:
            citations = article.metadata.get("citations", 0)
            references = article.metadata.get("references", 0)
            backlinks = article.metadata.get("backlinks", 0)

            if citations > 100:
                score += 3.0
                reasoning.append(f"Highly cited ({citations} citations)")
            elif citations > 10:
                score += 2.0
            elif citations > 0:
                score += 1.0

            if references > 50:
                score += 1.5
            if backlinks > 100:
                score += 2.0
                reasoning.append(f"Well-referenced ({backlinks} backlinks)")

        return min(10.0, score)

    def rank_batch(
        self,
        articles: List[Article],
        verification_scores: Optional[Dict] = None,
        engagement_metrics: Optional[Dict] = None,
        trending_data: Optional[Dict] = None,
    ) -> List[ImportanceScore]:
        """
        Rank multiple articles.

        Args:
            articles: Articles to rank.
            verification_scores: Dict mapping article.id -> verification_score.
            engagement_metrics: Dict mapping article.id -> engagement dict.
            trending_data: Dict mapping article.id -> trending dict.

        Returns:
            List of ImportanceScore objects.
        """
        results = []

        for article in articles:
            article_id = article.id
            ver_score = verification_scores.get(article_id) if verification_scores else None
            eng_metrics = engagement_metrics.get(article_id) if engagement_metrics else None
            trend_data = trending_data.get(article_id) if trending_data else None

            score = self.rank_article(article, ver_score, eng_metrics, trend_data)
            results.append(score)

        return results

    def rank_and_sort(
        self,
        articles: List[Article],
        verification_scores: Optional[Dict] = None,
        engagement_metrics: Optional[Dict] = None,
        trending_data: Optional[Dict] = None,
        descending: bool = True,
    ) -> List[ImportanceScore]:
        """
        Rank articles and sort by importance.

        Args:
            articles: Articles to rank.
            verification_scores: Verification score dict.
            engagement_metrics: Engagement metrics dict.
            trending_data: Trending data dict.
            descending: If True, sort high-to-low. If False, low-to-high.

        Returns:
            Sorted list of ImportanceScore objects.
        """
        scores = self.rank_batch(
            articles, verification_scores, engagement_metrics, trending_data
        )
        scores.sort(
            key=lambda x: x.overall_score, reverse=descending
        )
        return scores

    def filter_by_importance(
        self,
        articles: List[Article],
        min_importance: ImportanceLevel = ImportanceLevel.MODERATE,
        verification_scores: Optional[Dict] = None,
        engagement_metrics: Optional[Dict] = None,
        trending_data: Optional[Dict] = None,
    ) -> Tuple[List[Article], List[ImportanceScore]]:
        """
        Filter articles by minimum importance level.

        Args:
            articles: Articles to filter.
            min_importance: Minimum importance level to keep.
            verification_scores: Verification score dict.
            engagement_metrics: Engagement metrics dict.
            trending_data: Trending data dict.

        Returns:
            (filtered_articles, importance_scores_for_all)
        """
        scores = self.rank_batch(
            articles, verification_scores, engagement_metrics, trending_data
        )

        # Rank importance levels
        level_rank = {
            ImportanceLevel.CRITICAL: 5,
            ImportanceLevel.VERY_HIGH: 4,
            ImportanceLevel.HIGH: 3,
            ImportanceLevel.MODERATE: 2,
            ImportanceLevel.LOW: 1,
            ImportanceLevel.MINIMAL: 0,
        }

        min_rank = level_rank.get(min_importance, 2)

        filtered = [
            score.article
            for score in scores
            if level_rank.get(score.importance_level, 0) >= min_rank
        ]

        return filtered, scores

    def get_statistics(self, scores: List[ImportanceScore]) -> Dict:
        """Generate statistics about ranking results."""
        if not scores:
            return {
                "total_articles": 0,
                "critical": 0,
                "very_high": 0,
                "high": 0,
                "moderate": 0,
                "low": 0,
                "minimal": 0,
                "average_score": 0.0,
                "trending_articles": 0,
                "trending_percentage": 0.0,
            }

        level_counts = {
            ImportanceLevel.CRITICAL: 0,
            ImportanceLevel.VERY_HIGH: 0,
            ImportanceLevel.HIGH: 0,
            ImportanceLevel.MODERATE: 0,
            ImportanceLevel.LOW: 0,
            ImportanceLevel.MINIMAL: 0,
        }

        for score in scores:
            level_counts[score.importance_level] += 1

        trending_count = sum(1 for s in scores if s.trending)

        return {
            "total_articles": len(scores),
            "critical": level_counts[ImportanceLevel.CRITICAL],
            "very_high": level_counts[ImportanceLevel.VERY_HIGH],
            "high": level_counts[ImportanceLevel.HIGH],
            "moderate": level_counts[ImportanceLevel.MODERATE],
            "low": level_counts[ImportanceLevel.LOW],
            "minimal": level_counts[ImportanceLevel.MINIMAL],
            "average_score": sum(s.overall_score for s in scores) / len(scores),
            "average_authority": sum(s.authority_score for s in scores) / len(scores),
            "average_engagement": sum(s.engagement_score for s in scores) / len(scores),
            "average_recency": sum(s.recency_score for s in scores) / len(scores),
            "average_relevance": sum(s.relevance_score for s in scores) / len(scores),
            "trending_articles": trending_count,
            "trending_percentage": (trending_count / len(scores)) * 100 if scores else 0.0,
        }

    def generate_report(self, score: ImportanceScore) -> str:
        """Generate human-readable importance report."""
        lines = [
            f"\n{'='*60}",
            f"Article: {score.article.title[:60]}...",
            f"{'='*60}",
            f"\nImportance Level: {score.importance_level.value.upper()}",
            f"Overall Score: {score.overall_score:.1f}/10",
            f"\nComponent Scores:",
            f"  • Authority:      {score.authority_score:.1f}/10",
            f"  • Engagement:     {score.engagement_score:.1f}/10",
            f"  • Recency:        {score.recency_score:.1f}/10",
            f"  • Relevance:      {score.relevance_score:.1f}/10",
            f"  • Trend:          {score.trend_score:.1f}/10",
            f"  • Citation:       {score.citation_score:.1f}/10",
        ]

        if score.trending:
            lines.append(
                f"\n📈 TRENDING (velocity: {score.trending_velocity:.2f} mentions/day)"
            )

        if score.matched_interests:
            lines.append(f"\n✓ Matches interests: {', '.join(score.matched_interests)}")

        if score.reasoning:
            lines.append(f"\nReasoning:")
            for reason in score.reasoning[:5]:  # Top 5 reasons
                lines.append(f"  • {reason}")

        lines.append(f"{'='*60}\n")

        return "\n".join(lines)


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)
    print("Importance Ranking Engine initialized")
    print("Importance Levels: critical, very_high, high, moderate, low, minimal")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
