"""
Decision Engine — High-level recommendation creation and ranking.

Combines importance, personalization, and user preferences to create
actionable recommendations with suggested delivery timing.

Handles:
- Score combination (importance + personalization)
- Quality filtering based on thresholds
- Category/source/tag filtering
- Duplicate suppression
- Recommendation ranking
- Notification scheduling
- Feedback collection
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone

from app.collectors.rss_collector import Article
from app.processors.importance import ImportanceScore, ImportanceLevel
from app.processors.personalization import PersonalizationEngine

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Type of recommendation."""
    CRITICAL = "critical"  # Must-read, highly important
    FEATURED = "featured"  # High priority, should read today
    RELEVANT = "relevant"  # Matches interests, good to read
    DISCOVER = "discover"  # Interesting but not core interest
    CATCH_UP = "catch_up"  # Lower priority, background reading


class NotificationUrgency(Enum):
    """How urgently to notify user."""
    IMMEDIATE = "immediate"  # Within minutes (critical/breaking)
    HIGH = "high"  # Within 2 hours (morning digest)
    NORMAL = "normal"  # Within 4 hours (daily digest)
    LOW = "low"  # Can wait, include in weekly


@dataclass
class RecommendationScore:
    """Detailed scoring for a recommendation."""

    article_id: str
    combined_score: float  # 0-11 (importance 0-10 + personalization 0-1)
    importance_score: float  # 0-10
    personalization_boost: float  # 0-1
    quality_score: float  # 0-1 (from verification)
    recency_score: float  # 0-1 (freshness bonus)
    engagement_potential: float  # 0-1 (predicted user engagement)
    reasoning: List[str] = field(default_factory=list)  # Why recommended


@dataclass
class Recommendation:
    """Final recommendation to show user."""

    article: Article
    recommendation_type: RecommendationType
    combined_score: float
    scoring: RecommendationScore
    personalization_boost: float
    matched_interests: List[str] = field(default_factory=list)
    notification_urgency: NotificationUrgency = NotificationUrgency.NORMAL
    suggested_delivery_time: Optional[datetime] = None
    summary_snippet: str = ""  # Short teaser
    action_buttons: List[str] = field(default_factory=lambda: ["Read", "Save", "Share"])
    feedback_tags: List[str] = field(default_factory=list)  # For feedback collection


class DecisionEngine:
    """Recommendation decision and ranking engine."""

    def __init__(
        self,
        personalization_engine: PersonalizationEngine,
        quality_threshold: float = 0.5,
        min_importance_score: float = 2.0,
    ):
        """
        Initialize decision engine.

        Args:
            personalization_engine: User personalization engine for filtering/scoring.
            quality_threshold: Minimum quality score (0-1) for inclusion.
            min_importance_score: Minimum importance score (0-10) for inclusion.
        """
        self.personalization = personalization_engine
        self.quality_threshold = quality_threshold
        self.min_importance_score = min_importance_score

        # Track recommendations for deduplication
        self.recent_recommendations = []  # Last 100 recommendations
        self.feedback_history = []  # User feedback on recommendations

    def score_article(
        self,
        article: Article,
        importance_score: ImportanceScore,
        quality_score: float = 0.7,
    ) -> RecommendationScore:
        """
        Score an article for recommendation.

        Args:
            article: Article to score.
            importance_score: Pre-calculated importance score.
            quality_score: Quality level (0-1, typically from verification engine).

        Returns:
            RecommendationScore with detailed breakdown.
        """
        # Get personalization boost
        personalization_boost = self.personalization.get_personalized_boost(article)

        # Combine scores
        # Importance: 0-10, Personalization: 0-1
        # Combined: 0-11 (weighted by importance since it's primary signal)
        combined_score = (importance_score.overall_score * 0.85) + (personalization_boost * 10 * 0.15)

        # Recency bonus (fresh articles score higher)
        age_days = (datetime.now(timezone.utc) - article.published_at).days
        if age_days == 0:
            recency_score = 1.0
        elif age_days <= 1:
            recency_score = 0.95
        elif age_days <= 3:
            recency_score = 0.85
        elif age_days <= 7:
            recency_score = 0.7
        else:
            recency_score = max(0.3, 1.0 - (age_days / 30.0))

        # Engagement potential based on importance level
        engagement_potential = self._estimate_engagement(importance_score, personalization_boost)

        reasoning = []

        if importance_score.overall_score >= 9.0:
            reasoning.append(f"Critical importance ({importance_score.overall_score:.1f}/10)")
        elif importance_score.overall_score >= 7.5:
            reasoning.append(f"Very high importance ({importance_score.overall_score:.1f}/10)")
        elif importance_score.overall_score >= 6.0:
            reasoning.append(f"High importance ({importance_score.overall_score:.1f}/10)")

        if personalization_boost >= 0.5:
            reasoning.append("Strong match to your interests")
        elif personalization_boost >= 0.2:
            reasoning.append("Matches your interests")

        if quality_score >= 0.8:
            reasoning.append("High-quality source")

        if importance_score.trending:
            reasoning.append("Currently trending")

        return RecommendationScore(
            article_id=article.id,
            combined_score=combined_score,
            importance_score=importance_score.overall_score,
            personalization_boost=personalization_boost,
            quality_score=quality_score,
            recency_score=recency_score,
            engagement_potential=engagement_potential,
            reasoning=reasoning,
        )

    def _estimate_engagement(self, importance_score: ImportanceScore, personalization_boost: float) -> float:
        """Estimate likelihood user will engage with article."""
        engagement = 0.0

        # Importance level contributes to engagement potential
        if importance_score.importance_level == importance_score.importance_level.__class__.CRITICAL:
            engagement += 0.8
        elif importance_score.importance_level == importance_score.importance_level.__class__.VERY_HIGH:
            engagement += 0.6
        elif importance_score.importance_level == importance_score.importance_level.__class__.HIGH:
            engagement += 0.4

        # Personalization boost
        engagement += personalization_boost * 0.3

        # Trending factor
        if importance_score.trending:
            engagement += 0.2

        return min(1.0, engagement)

    def decide_recommendation_type(self, scoring: RecommendationScore) -> RecommendationType:
        """
        Decide recommendation type based on scoring.

        Returns:
            RecommendationType enum.
        """
        combined = scoring.combined_score

        # Critical threshold
        if combined >= 9.5 and scoring.quality_score >= 0.7:
            return RecommendationType.CRITICAL

        # Featured threshold
        if combined >= 7.5 and scoring.quality_score >= 0.6:
            return RecommendationType.FEATURED

        # Relevant threshold
        if combined >= 5.0 and scoring.quality_score >= 0.5:
            return RecommendationType.RELEVANT

        # Discover threshold
        if combined >= 3.0 and scoring.quality_score >= 0.4:
            return RecommendationType.DISCOVER

        # Fallback
        return RecommendationType.CATCH_UP

    def decide_notification_urgency(
        self,
        rec_type: RecommendationType,
        importance: float,
        trending: bool,
    ) -> NotificationUrgency:
        """
        Decide notification urgency.

        Args:
            rec_type: Recommendation type.
            importance: Importance score (0-10).
            trending: Whether article is trending.

        Returns:
            NotificationUrgency enum.
        """
        if rec_type == RecommendationType.CRITICAL:
            return NotificationUrgency.IMMEDIATE if trending else NotificationUrgency.HIGH

        elif rec_type == RecommendationType.FEATURED:
            return NotificationUrgency.HIGH if importance >= 8.0 else NotificationUrgency.NORMAL

        elif rec_type == RecommendationType.RELEVANT:
            return NotificationUrgency.NORMAL

        elif rec_type == RecommendationType.DISCOVER:
            return NotificationUrgency.LOW

        else:
            return NotificationUrgency.LOW

    def suggest_delivery_time(
        self,
        urgency: NotificationUrgency,
        user_timezone: str = "UTC",
    ) -> datetime:
        """
        Suggest when to deliver notification.

        Args:
            urgency: Notification urgency level.
            user_timezone: User's timezone (for scheduling preferences).

        Returns:
            Suggested delivery datetime.
        """
        now = datetime.now(timezone.utc)

        if urgency == NotificationUrgency.IMMEDIATE:
            # Send within 5 minutes
            return now + timedelta(minutes=5)

        elif urgency == NotificationUrgency.HIGH:
            # Send within 2 hours (morning digest window)
            return now + timedelta(hours=2)

        elif urgency == NotificationUrgency.NORMAL:
            # Send in daily digest (8 AM next day, simplified)
            return (now + timedelta(days=1)).replace(hour=8, minute=0, second=0)

        else:  # LOW
            # Send in weekly digest
            return (now + timedelta(weeks=1)).replace(hour=8, minute=0, second=0)

    def should_include_article(
        self,
        article: Article,
        scoring: RecommendationScore,
        category_filter: Optional[List[str]] = None,
        source_filter: Optional[List[str]] = None,
        tag_filter: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """
        Decide whether to include article in recommendations.

        Returns:
            (include, reason_if_excluded)
        """
        # Quality threshold check
        if scoring.quality_score < self.quality_threshold:
            return False, f"Quality too low ({scoring.quality_score:.2f} < {self.quality_threshold})"

        # Importance threshold check
        if scoring.importance_score < self.min_importance_score:
            return False, f"Importance too low ({scoring.importance_score:.1f} < {self.min_importance_score})"

        # Category filter
        if category_filter and article.category:
            if article.category.lower() not in [c.lower() for c in category_filter]:
                return False, f"Category not in filter: {article.category}"

        # Source filter
        if source_filter and article.source:
            if article.source.lower() not in [s.lower() for s in source_filter]:
                return False, f"Source not in filter: {article.source}"

        # Tag filter
        if tag_filter and article.tags:
            tag_match = any(
                tag.lower() in [t.lower() for t in article.tags]
                for t in tag_filter
            )
            if not tag_match:
                return False, "No matching tags"

        return True, ""

    def create_recommendation(
        self,
        article: Article,
        importance_score: ImportanceScore,
        quality_score: float = 0.7,
        category_filter: Optional[List[str]] = None,
        source_filter: Optional[List[str]] = None,
        tag_filter: Optional[List[str]] = None,
    ) -> Optional[Recommendation]:
        """
        Create a recommendation from an article.

        Returns:
            Recommendation object or None if filtered out.
        """
        # Score the article
        scoring = self.score_article(article, importance_score, quality_score)

        # Check if should include
        include, reason = self.should_include_article(
            article,
            scoring,
            category_filter=category_filter,
            source_filter=source_filter,
            tag_filter=tag_filter,
        )

        if not include:
            logger.debug(f"Excluded {article.id}: {reason}")
            return None

        # Decide recommendation type
        rec_type = self.decide_recommendation_type(scoring)

        # Decide notification urgency
        urgency = self.decide_notification_urgency(
            rec_type,
            scoring.importance_score,
            importance_score.trending,
        )

        # Suggest delivery time
        delivery_time = self.suggest_delivery_time(urgency)

        # Generate summary snippet
        snippet = self._generate_snippet(article)

        # Get matched interests
        matched_interests = self.personalization.profile.dominant_interests[:5]

        # Create recommendation
        recommendation = Recommendation(
            article=article,
            recommendation_type=rec_type,
            combined_score=scoring.combined_score,
            scoring=scoring,
            personalization_boost=scoring.personalization_boost,
            matched_interests=matched_interests,
            notification_urgency=urgency,
            suggested_delivery_time=delivery_time,
            summary_snippet=snippet,
            feedback_tags=[],
        )

        return recommendation

    def rank_recommendations(
        self,
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """
        Rank recommendations by combined score and importance.

        Returns:
            Sorted recommendations (best first).
        """
        # Sort by: 1) recommendation type priority, 2) combined score, 3) recency
        type_priority = {
            RecommendationType.CRITICAL: 5,
            RecommendationType.FEATURED: 4,
            RecommendationType.RELEVANT: 3,
            RecommendationType.DISCOVER: 2,
            RecommendationType.CATCH_UP: 1,
        }

        sorted_recs = sorted(
            recommendations,
            key=lambda r: (
                -type_priority[r.recommendation_type],
                -r.combined_score,
                -r.scoring.recency_score,
            ),
        )

        return sorted_recs

    def suppress_duplicates(
        self,
        recommendations: List[Recommendation],
        window_hours: int = 24,
    ) -> List[Recommendation]:
        """
        Suppress recommendations of recently shown articles.

        Args:
            recommendations: Incoming recommendations.
            window_hours: How far back to check for recent recommendations.

        Returns:
            Deduplicated recommendations.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        # Get IDs of recent recommendations
        recent_ids = set(
            r.article.id
            for r in self.recent_recommendations
            if r.suggested_delivery_time and r.suggested_delivery_time > cutoff_time
        )

        # Filter out duplicates
        filtered = [r for r in recommendations if r.article.id not in recent_ids]

        # Add new recommendations to history
        self.recent_recommendations.extend(filtered)
        if len(self.recent_recommendations) > 100:
            self.recent_recommendations = self.recent_recommendations[-100:]

        return filtered

    def _generate_snippet(self, article: Article, max_length: int = 100) -> str:
        """Generate a short summary snippet from article summary."""
        if not article.summary:
            return article.title[:max_length]

        if len(article.summary) <= max_length:
            return article.summary

        # Find sentence break near max_length
        truncated = article.summary[:max_length]
        last_period = truncated.rfind(".")
        if last_period > 50:  # Only use period if reasonable position
            return truncated[:last_period + 1]

        return truncated + "…"

    def get_daily_recommendations(
        self,
        articles_with_scores: List[Tuple[Article, ImportanceScore, float]],
        max_recommendations: int = 10,
        category_filter: Optional[List[str]] = None,
        source_filter: Optional[List[str]] = None,
    ) -> List[Recommendation]:
        """
        Get daily recommendation set.

        Args:
            articles_with_scores: List of (article, importance_score, quality_score) tuples.
            max_recommendations: Maximum recommendations to return.
            category_filter: Optional category whitelist.
            source_filter: Optional source whitelist.

        Returns:
            Ranked, deduplicated recommendations.
        """
        recommendations = []

        # Create recommendations
        for article, importance_score, quality_score in articles_with_scores:
            rec = self.create_recommendation(
                article,
                importance_score,
                quality_score=quality_score,
                category_filter=category_filter,
                source_filter=source_filter,
            )
            if rec:
                recommendations.append(rec)

        # Rank recommendations
        ranked = self.rank_recommendations(recommendations)

        # Suppress duplicates
        deduplicated = self.suppress_duplicates(ranked)

        # Return top N
        return deduplicated[:max_recommendations]

    def record_feedback(
        self,
        recommendation: Recommendation,
        action: str,  # "read", "save", "skip", "dismiss"
        time_spent_seconds: Optional[int] = None,
    ) -> None:
        """
        Record user feedback on recommendation.

        Args:
            recommendation: The recommendation.
            action: User action taken.
            time_spent_seconds: Time user spent reading (if read).
        """
        feedback = {
            "article_id": recommendation.article.id,
            "recommendation_type": recommendation.recommendation_type.value,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "time_spent_seconds": time_spent_seconds,
            "combined_score": recommendation.combined_score,
        }

        self.feedback_history.append(feedback)

        # Pass to personalization engine
        if action == "read" and time_spent_seconds and time_spent_seconds > 30:
            from app.processors.personalization import InteractionType

            interaction_type = InteractionType.VIEW
            self.personalization.record_interaction(
                recommendation.article,
                interaction_type,
            )

        # Trim history
        if len(self.feedback_history) > 1000:
            self.feedback_history = self.feedback_history[-1000:]

    def get_statistics(self) -> Dict:
        """Generate decision engine statistics."""
        if not self.feedback_history:
            return {
                "recommendations_created": len(self.recent_recommendations),
                "total_feedback_recorded": 0,
            }

        actions = {}
        total_time = 0
        read_count = 0

        for feedback in self.feedback_history:
            action = feedback.get("action", "unknown")
            actions[action] = actions.get(action, 0) + 1

            if action == "read" and feedback.get("time_spent_seconds"):
                total_time += feedback["time_spent_seconds"]
                read_count += 1

        return {
            "recommendations_created": len(self.recent_recommendations),
            "total_feedback_recorded": len(self.feedback_history),
            "feedback_breakdown": actions,
            "average_read_time_seconds": (total_time / read_count) if read_count > 0 else 0,
            "read_through_rate": (actions.get("read", 0) / len(self.feedback_history))
            if self.feedback_history
            else 0,
        }


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)
    print("Decision Engine initialized")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
