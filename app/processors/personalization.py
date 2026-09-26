"""
Personalization Engine — User preference learning and interest evolution.

Learns from:
- Article interactions (views, saves, likes, shares)
- Engagement patterns
- Interest evolution over time
- Content quality feedback
- Source preferences
- Category preferences
- Topic drift detection
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import json

from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)


class PreferenceLevel(Enum):
    """Interest preference intensity."""
    STRONG = "strong"  # 0.8-1.0, core interest
    MODERATE = "moderate"  # 0.5-0.79, regular interest
    WEAK = "weak"  # 0.2-0.49, occasional interest
    MINIMAL = "minimal"  # 0.0-0.19, rare/no interest


class InteractionType(Enum):
    """Types of user interactions."""
    VIEW = "view"  # Viewed article
    SAVE = "save"  # Saved/bookmarked
    LIKE = "like"  # Liked/upvoted
    SHARE = "share"  # Shared article
    DISLIKE = "dislike"  # Disliked/downvoted
    SKIP = "skip"  # Skipped/dismissed


@dataclass
class InterestProfile:
    """User's interest in a specific topic."""

    interest: str  # Topic/keyword
    strength: float  # 0-1, current strength
    confidence: float  # 0-1, certainty of interest
    first_seen: datetime  # When first detected
    last_updated: datetime  # When last interacted
    interaction_count: int = 0  # Times engaged
    positive_interactions: int = 0  # Views, likes, saves
    negative_interactions: int = 0  # Dislikes, skips
    related_topics: List[str] = field(default_factory=list)  # Co-occurring interests
    trend: str = "stable"  # up, down, stable

    def update_strength(self, interaction_type: InteractionType) -> None:
        """Update interest strength based on interaction."""
        self.last_updated = datetime.now(timezone.utc)
        self.interaction_count += 1

        # Count interactions first
        if interaction_type in [
            InteractionType.VIEW,
            InteractionType.LIKE,
            InteractionType.SAVE,
            InteractionType.SHARE,
        ]:
            self.positive_interactions += 1
        elif interaction_type in [InteractionType.DISLIKE, InteractionType.SKIP]:
            self.negative_interactions += 1

        weight = 0.05  # How much each interaction changes strength

        if interaction_type == InteractionType.VIEW:
            weight *= 1.0
        elif interaction_type == InteractionType.LIKE:
            weight *= 2.0
        elif interaction_type == InteractionType.SAVE:
            weight *= 2.5
        elif interaction_type == InteractionType.SHARE:
            weight *= 3.0
        elif interaction_type == InteractionType.DISLIKE:
            weight *= -1.5
        elif interaction_type == InteractionType.SKIP:
            weight *= -1.0

        self.strength = max(0.0, min(1.0, self.strength + weight))
        self.confidence = min(1.0, self.confidence + 0.02)

    def decay(self, days_inactive: int) -> None:
        """Decay interest strength over time."""
        # Linear decay: 1% per day after 30 days
        if days_inactive > 30:
            decay_amount = (days_inactive - 30) * 0.01
            self.strength = max(0.0, self.strength - decay_amount)
            self.confidence *= 0.95  # Slight confidence decay


@dataclass
class UserProfile:
    """Complete user preference profile."""

    user_id: str
    created_at: datetime
    interests: Dict[str, InterestProfile] = field(default_factory=dict)
    category_preferences: Dict[str, float] = field(default_factory=dict)  # Category -> strength
    source_preferences: Dict[str, float] = field(default_factory=dict)  # Source -> trust/strength
    content_length_preference: str = "balanced"  # short, balanced, long
    update_frequency_preference: str = "daily"  # hourly, daily, weekly
    total_interactions: int = 0
    interaction_history: List[Dict] = field(default_factory=list)  # Last 1000 interactions
    topic_drift_detected: bool = False
    dominant_interests: List[str] = field(default_factory=list)  # Top interests

    def get_preference_level(self, interest: str) -> PreferenceLevel:
        """Get preference level for an interest."""
        if interest not in self.interests:
            return PreferenceLevel.MINIMAL

        strength = self.interests[interest].strength

        if strength >= 0.8:
            return PreferenceLevel.STRONG
        elif strength >= 0.5:
            return PreferenceLevel.MODERATE
        elif strength >= 0.2:
            return PreferenceLevel.WEAK
        else:
            return PreferenceLevel.MINIMAL


class PersonalizationEngine:
    """User personalization and preference learning."""

    def __init__(
        self,
        user_id: str,
        decay_days: int = 30,
        drift_threshold: float = 0.4,
    ):
        """
        Initialize personalization engine.

        Args:
            user_id: Unique user identifier.
            decay_days: Days before interest strength decays.
            drift_threshold: Threshold for topic drift detection.
        """
        self.user_id = user_id
        self.decay_days = decay_days
        self.drift_threshold = drift_threshold

        self.profile = UserProfile(user_id=user_id, created_at=datetime.now(timezone.utc))

        # Tracking
        self.session_start = datetime.now(timezone.utc)
        self.interaction_queue = []  # Buffer for batch updates

    def record_interaction(
        self,
        article: Article,
        interaction_type: InteractionType,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record user interaction with article.

        Args:
            article: Article interacted with.
            interaction_type: Type of interaction.
            timestamp: When interaction occurred (default: now).
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Extract interests from article
        interests = set()
        interests.update(article.tags or [])

        # Add category
        if article.category:
            interests.add(article.category.lower())

        # Add source
        if article.source:
            interests.add(f"source:{article.source.lower()}")

        # Update interests
        for interest in interests:
            if interest not in self.profile.interests:
                self.profile.interests[interest] = InterestProfile(
                    interest=interest,
                    strength=0.3,  # Start moderate
                    confidence=0.3,
                    first_seen=timestamp,
                    last_updated=timestamp,
                )
                # Call update_strength on new interests too
                self.profile.interests[interest].update_strength(interaction_type)
            else:
                self.profile.interests[interest].update_strength(interaction_type)

        # Update category preference
        if article.category:
            category = article.category.lower()
            if category not in self.profile.category_preferences:
                self.profile.category_preferences[category] = 0.5
            else:
                # Increase if positive, decrease if negative
                delta = 0.05 if interaction_type in [
                    InteractionType.LIKE,
                    InteractionType.SAVE,
                ] else -0.02
                self.profile.category_preferences[category] = max(
                    0.0,
                    min(1.0, self.profile.category_preferences[category] + delta),
                )

        # Update source preference
        if article.source:
            source = article.source.lower()
            if source not in self.profile.source_preferences:
                self.profile.source_preferences[source] = 0.5
            else:
                delta = 0.05 if interaction_type != InteractionType.SKIP else -0.05
                self.profile.source_preferences[source] = max(
                    0.0,
                    min(1.0, self.profile.source_preferences[source] + delta),
                )

        # Record history (keep last 1000)
        self.profile.interaction_history.append(
            {
                "article_id": article.id,
                "interaction_type": interaction_type.value,
                "timestamp": timestamp.isoformat(),
                "interests_matched": list(interests),
            }
        )
        if len(self.profile.interaction_history) > 1000:
            self.profile.interaction_history = self.profile.interaction_history[-1000:]

        self.profile.total_interactions += 1

    def update_dominant_interests(self, top_n: int = 10) -> List[str]:
        """
        Update list of dominant interests.

        Returns:
            Top N interests by strength.
        """
        sorted_interests = sorted(
            self.profile.interests.items(),
            key=lambda x: x[1].strength * x[1].confidence,
            reverse=True,
        )

        self.profile.dominant_interests = [
            interest for interest, _ in sorted_interests[:top_n]
        ]

        return self.profile.dominant_interests

    def apply_decay(self) -> None:
        """Apply interest decay based on time since last update."""
        now = datetime.now(timezone.utc)

        for interest in self.profile.interests.values():
            days_inactive = (now - interest.last_updated).days
            interest.decay(days_inactive)

            # Update trend based on positive vs negative interactions
            if interest.interaction_count == 0:
                interest.trend = "stable"
            elif interest.positive_interactions > interest.negative_interactions * 1.5:
                interest.trend = "up"
            elif interest.negative_interactions > interest.positive_interactions * 1.5:
                interest.trend = "down"
            else:
                interest.trend = "stable"

    def detect_topic_drift(self, window_days: int = 30) -> Tuple[bool, Dict]:
        """
        Detect significant shift in user interests.

        Returns:
            (drift_detected, details_dict)
        """
        if len(self.profile.interaction_history) < 10:
            return False, {}

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=window_days)

        recent_interactions = [
            i for i in self.profile.interaction_history
            if datetime.fromisoformat(i["timestamp"]) >= cutoff
        ]

        if not recent_interactions:
            return False, {}

        # Calculate topic shift in recent interactions
        recent_topics = defaultdict(int)
        for interaction in recent_interactions:
            for topic in interaction.get("interests_matched", []):
                recent_topics[topic] += 1

        # Get all topics from before cutoff window
        older_interactions = [
            i for i in self.profile.interaction_history
            if datetime.fromisoformat(i["timestamp"]) < cutoff
        ]

        old_topics = set()
        for interaction in older_interactions:
            for topic in interaction.get("interests_matched", []):
                old_topics.add(topic)

        # Recalculate to include all recent topics
        all_recent_topics = set(recent_topics.keys())
        
        # New topics: appeared recently but not in old history
        new_topics = all_recent_topics - old_topics
        
        # Lost topics: were in old history but not recently
        lost_topics = old_topics - all_recent_topics

        # Check for significant shift (ratio of change)
        total_old = len(old_topics) if old_topics else 1
        total_recent = len(all_recent_topics)
        
        shift_ratio = (len(new_topics) + len(lost_topics)) / (total_old + total_recent)
        drift_detected = shift_ratio > self.drift_threshold

        self.profile.topic_drift_detected = drift_detected

        return drift_detected, {
            "drift_score": shift_ratio,
            "new_topics": list(new_topics)[:10],
            "lost_topics": list(lost_topics)[:10],
            "old_topics": list(old_topics)[:10],
            "recent_topics": list(all_recent_topics)[:10],
            "dominant_recent_topics": [
                t for t, _ in sorted(recent_topics.items(), key=lambda x: x[1], reverse=True)[:5]
            ],
        }

    def get_personalized_boost(self, article: Article) -> float:
        """
        Calculate personalization boost for article (0-1 additive).

        Args:
            article: Article to score.

        Returns:
            Boost value (0-1) to add to importance score.
        """
        boost = 0.0

        # Tag matches
        if article.tags:
            for tag in article.tags:
                tag_lower = tag.lower()
                if tag_lower in self.profile.interests:
                    interest = self.profile.interests[tag_lower]
                    weight = interest.strength * interest.confidence
                    boost += weight * 0.3  # Max 0.3 from tags

        # Category preference
        if article.category:
            category = article.category.lower()
            if category in self.profile.category_preferences:
                boost += self.profile.category_preferences[category] * 0.2  # Max 0.2

        # Source preference
        if article.source:
            source = article.source.lower()
            if source in self.profile.source_preferences:
                boost += self.profile.source_preferences[source] * 0.15  # Max 0.15

        return min(1.0, boost)

    def get_content_recommendations(self, articles: List[Article], top_n: int = 5) -> List[Article]:
        """
        Get personalized content recommendations.

        Args:
            articles: Pool of articles to recommend from.
            top_n: Number of recommendations to return.

        Returns:
            Top N articles ranked by personalization fit.
        """
        # Score articles by personalization fit
        scored = []

        for article in articles:
            score = 0.0

            # Tag matches
            if article.tags:
                for tag in article.tags:
                    tag_lower = tag.lower()
                    if tag_lower in self.profile.interests:
                        interest = self.profile.interests[tag_lower]
                        score += interest.strength * interest.confidence

            # Category match
            if article.category:
                category = article.category.lower()
                if category in self.profile.category_preferences:
                    score += self.profile.category_preferences[category] * 2

            # Source preference
            if article.source:
                source = article.source.lower()
                if source in self.profile.source_preferences:
                    score += self.profile.source_preferences[source] * 1.5

            scored.append((article, score))

        # Sort and return top N
        scored.sort(key=lambda x: x[1], reverse=True)
        return [article for article, _ in scored[:top_n]]

    def get_statistics(self) -> Dict:
        """Generate statistics about user profile."""
        self.apply_decay()
        self.update_dominant_interests()

        strong_interests = [
            i for i in self.profile.interests.values()
            if i.strength >= 0.8
        ]
        moderate_interests = [
            i for i in self.profile.interests.values()
            if 0.5 <= i.strength < 0.8
        ]
        weak_interests = [
            i for i in self.profile.interests.values()
            if 0.2 <= i.strength < 0.5
        ]

        return {
            "user_id": self.user_id,
            "total_interests": len(self.profile.interests),
            "strong_interests": len(strong_interests),
            "moderate_interests": len(moderate_interests),
            "weak_interests": len(weak_interests),
            "total_interactions": self.profile.total_interactions,
            "positive_interactions": sum(
                i.positive_interactions for i in self.profile.interests.values()
            ),
            "negative_interactions": sum(
                i.negative_interactions for i in self.profile.interests.values()
            ),
            "dominant_interests": self.profile.dominant_interests[:10],
            "favorite_categories": sorted(
                self.profile.category_preferences.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5],
            "favorite_sources": sorted(
                self.profile.source_preferences.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5],
            "topic_drift_detected": self.profile.topic_drift_detected,
            "profile_age_days": (datetime.now(timezone.utc) - self.profile.created_at).days,
        }

    def export_profile(self) -> str:
        """Export profile as JSON."""
        self.apply_decay()
        self.update_dominant_interests()

        interests_data = {
            name: {
                "strength": profile.strength,
                "confidence": profile.confidence,
                "interaction_count": profile.interaction_count,
                "trend": profile.trend,
            }
            for name, profile in self.profile.interests.items()
        }

        export = {
            "user_id": self.user_id,
            "created_at": self.profile.created_at.isoformat(),
            "interests": interests_data,
            "category_preferences": self.profile.category_preferences,
            "source_preferences": self.profile.source_preferences,
            "total_interactions": self.profile.total_interactions,
            "dominant_interests": self.profile.dominant_interests,
        }

        return json.dumps(export, indent=2)

    def import_profile(self, profile_json: str) -> None:
        """Import profile from JSON."""
        data = json.loads(profile_json)

        self.profile.interests = {}
        for interest_name, interest_data in data.get("interests", {}).items():
            self.profile.interests[interest_name] = InterestProfile(
                interest=interest_name,
                strength=interest_data.get("strength", 0.5),
                confidence=interest_data.get("confidence", 0.5),
                first_seen=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc),
                interaction_count=interest_data.get("interaction_count", 0),
                trend=interest_data.get("trend", "stable"),
            )

        self.profile.category_preferences = data.get("category_preferences", {})
        self.profile.source_preferences = data.get("source_preferences", {})
        self.profile.total_interactions = data.get("total_interactions", 0)


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)
    print("Personalization Engine initialized")
    print("Interaction types: view, save, like, share, dislike, skip")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
