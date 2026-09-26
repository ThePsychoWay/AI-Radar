"""
X (Twitter) Configuration — Platform-specific configuration and content generation.

Handles:
- Tweet recommendation generation (280 character limit)
- Thread creation for longer recommendations
- Media attachment handling
- API credentials configuration
- Scheduling preferences
- Tweet formatting and hashtags
- Rate limiting and quotas
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
import re

from app.analyzers.decision_engine import Recommendation, RecommendationType
from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)


class TweetType(Enum):
    """Type of tweet."""
    SINGLE = "single"  # Single tweet (fits 280 chars)
    THREAD = "thread"  # Multi-tweet thread
    THREAD_START = "thread_start"  # First tweet in thread
    THREAD_MIDDLE = "thread_middle"  # Middle tweet in thread
    THREAD_END = "thread_end"  # Last tweet in thread


class SchedulingFrequency(Enum):
    """Tweet scheduling frequency."""
    IMMEDIATE = "immediate"  # Send now
    MORNING = "morning"  # 8 AM user timezone
    AFTERNOON = "afternoon"  # 1 PM user timezone
    EVENING = "evening"  # 6 PM user timezone
    CUSTOM = "custom"  # Custom time


@dataclass
class XAPIConfig:
    """X API configuration."""

    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""
    bearer_token: str = ""
    user_id: str = ""
    handle: str = ""  # Twitter handle without @
    is_verified: bool = False
    rate_limit_tweets_per_day: int = 100
    rate_limit_characters_per_day: int = 10000

    def is_configured(self) -> bool:
        """Check if API is configured."""
        return bool(
            self.api_key
            and self.api_secret
            and self.access_token
            and self.access_token_secret
            and self.user_id
        )


@dataclass
class XPreferences:
    """User X preferences."""

    enabled: bool = True
    auto_tweet: bool = False  # Auto-share recommendations
    share_critical: bool = True
    share_featured: bool = True
    share_relevant: bool = False
    include_source: bool = True
    include_author: bool = True
    include_hashtags: bool = True
    custom_hashtags: List[str] = field(default_factory=list)  # Additional tags
    max_tweets_per_day: int = 5
    schedule_frequency: SchedulingFrequency = SchedulingFrequency.MORNING
    timezone: str = "UTC"
    include_link_preview: bool = True
    quote_tweet_mode: bool = False  # Quote the source tweet if available


@dataclass
class Tweet:
    """A tweet to be posted."""

    text: str
    tweet_type: TweetType = TweetType.SINGLE
    thread_id: Optional[str] = None  # For threading
    thread_position: int = 0  # Position in thread (0 = first)
    media_urls: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    mention_users: List[str] = field(default_factory=list)
    character_count: int = 0
    scheduled_time: Optional[datetime] = None
    article_id: Optional[str] = None  # Linked article
    recommendation_type: Optional[RecommendationType] = None

    def __post_init__(self):
        """Calculate character count."""
        self.character_count = len(self.text)


class XContentGenerator:
    """Generate X (Twitter) content from recommendations."""

    MAX_TWEET_LENGTH = 280
    HASHTAG_PATTERN = r"#[a-zA-Z0-9_]+"
    URL_PATTERN = r"https?://[^\s]+"

    def __init__(
        self,
        handle: str,
        preferences: Optional[XPreferences] = None,
    ):
        """
        Initialize X content generator.

        Args:
            handle: Twitter handle (without @).
            preferences: User X preferences.
        """
        self.handle = handle.lstrip("@")
        self.preferences = preferences or XPreferences()

    def _shorten_title(self, title: str, max_length: int = 50) -> str:
        """Shorten title to fit within character limit."""
        if len(title) <= max_length:
            return title

        # Find last space within limit
        truncated = title[:max_length]
        last_space = truncated.rfind(" ")

        if last_space > 20:  # Only use space if reasonable position
            return truncated[:last_space] + "…"

        return truncated + "…"

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            # Remove protocol
            domain = url.replace("https://", "").replace("http://", "")
            # Take first part before slash
            domain = domain.split("/")[0]
            # Remove www
            domain = domain.replace("www.", "")
            return domain
        except:
            return "source"

    def _calculate_url_length(self) -> int:
        """Calculate Twitter's URL length (always 23 characters)."""
        return 23

    def estimate_tweet_length(
        self,
        text: str,
        url: Optional[str] = None,
        media_count: int = 0,
    ) -> int:
        """
        Estimate tweet length with Twitter's counting rules.

        Args:
            text: Tweet text.
            url: URL (if included).
            media_count: Number of media attachments.

        Returns:
            Estimated character count.
        """
        # Count text
        length = len(text)

        # URLs count as 23 characters regardless of actual length
        url_match = re.search(self.URL_PATTERN, text)
        if url_match:
            length -= len(url_match.group())
            length += self._calculate_url_length()
        elif url:
            length += self._calculate_url_length()

        # Media: each attachment adds to the count (roughly 23 chars each)
        if media_count > 0:
            length += media_count * 23

        return length

    def generate_single_tweet(
        self,
        recommendation: Recommendation,
    ) -> Optional[Tweet]:
        """
        Generate single tweet from recommendation.

        Returns:
            Tweet object or None if cannot fit.
        """
        article = recommendation.article
        title = self._shorten_title(article.title, max_length=80)

        # Build tweet text
        parts = []

        # Lead
        if recommendation.recommendation_type == RecommendationType.CRITICAL:
            parts.append("🔥 MUST READ")
        elif recommendation.recommendation_type == RecommendationType.FEATURED:
            parts.append("⭐ Featured")

        # Title
        parts.append(f"{title}")

        # Source
        if self.preferences.include_source and article.source:
            parts.append(f"({self._extract_domain(article.url)})")

        # Author
        if self.preferences.include_author and article.author:
            parts.append(f"by {article.author}")

        # Combine base text
        base_text = " · ".join(parts)

        # Estimate length with URL
        estimated_length = self.estimate_tweet_length(
            base_text,
            url=article.url,
        )

        # Check if fits
        if estimated_length > self.MAX_TWEET_LENGTH:
            logger.debug(
                f"Tweet too long ({estimated_length} > {self.MAX_TWEET_LENGTH})"
            )
            return None

        # Add hashtags if room
        hashtags = []
        if self.preferences.include_hashtags:
            # Add custom hashtags
            hashtags.extend(self.preferences.custom_hashtags)

            # Add from tags
            if article.tags:
                for tag in article.tags[:3]:  # Limit to 3
                    tag_hash = f"#{tag.replace('-', '').replace(' ', '')}"
                    if len(tag_hash) <= 15:  # Reasonable hashtag length
                        hashtags.append(tag_hash)

        # Add URL
        full_text = f"{base_text}\n{article.url}"

        # Add hashtags if room
        if hashtags:
            hashtags_text = " ".join(hashtags)
            if (
                self.estimate_tweet_length(
                    f"{full_text}\n{hashtags_text}",
                ) <= self.MAX_TWEET_LENGTH
            ):
                full_text = f"{full_text}\n{hashtags_text}"

        return Tweet(
            text=full_text,
            tweet_type=TweetType.SINGLE,
            character_count=self.estimate_tweet_length(full_text),
            article_id=article.id,
            recommendation_type=recommendation.recommendation_type,
            hashtags=hashtags,
        )

    def generate_thread(
        self,
        recommendations: List[Recommendation],
        max_tweets: int = 5,
    ) -> List[Tweet]:
        """
        Generate thread from multiple recommendations.

        Args:
            recommendations: List of recommendations.
            max_tweets: Maximum tweets in thread.

        Returns:
            List of Tweet objects for thread.
        """
        tweets = []
        thread_id = f"thread_{datetime.now(timezone.utc).timestamp()}"

        # First tweet - intro
        critical_count = sum(
            1 for r in recommendations
            if r.recommendation_type == RecommendationType.CRITICAL
        )
        featured_count = sum(
            1 for r in recommendations
            if r.recommendation_type == RecommendationType.FEATURED
        )

        intro_text = f"📰 Your AI Radar Digest\n\n🔥 {critical_count} critical • ⭐ {featured_count} featured • {len(recommendations)} total\n\nThread →"

        intro_tweet = Tweet(
            text=intro_text,
            tweet_type=TweetType.THREAD_START,
            thread_id=thread_id,
            thread_position=0,
            character_count=len(intro_text),
        )
        tweets.append(intro_tweet)

        # Add recommendation tweets
        for i, rec in enumerate(recommendations[:max_tweets - 1]):
            article = rec.article
            title = self._shorten_title(article.title, max_length=100)

            # Build content tweet
            emoji = "🔥" if rec.recommendation_type == RecommendationType.CRITICAL else "⭐"

            content_text = f"{i + 1}/ {emoji} {title}\n\n{article.url}"

            if rec.article.author:
                content_text += f"\n— {rec.article.author}"

            tweet = Tweet(
                text=content_text,
                tweet_type=(
                    TweetType.THREAD_END
                    if i == len(recommendations[:max_tweets - 1]) - 1
                    else TweetType.THREAD_MIDDLE
                ),
                thread_id=thread_id,
                thread_position=i + 1,
                character_count=len(content_text),
                article_id=article.id,
                recommendation_type=rec.recommendation_type,
            )
            tweets.append(tweet)

        return tweets

    def filter_recommendations(
        self,
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """
        Filter recommendations based on X preferences.

        Returns:
            Filtered recommendations.
        """
        filtered = []

        for rec in recommendations:
            # Check type preference
            if rec.recommendation_type == RecommendationType.CRITICAL:
                if not self.preferences.share_critical:
                    continue
            elif rec.recommendation_type == RecommendationType.FEATURED:
                if not self.preferences.share_featured:
                    continue
            elif rec.recommendation_type == RecommendationType.RELEVANT:
                if not self.preferences.share_relevant:
                    continue
            else:
                # Don't share lower priority types
                continue

            filtered.append(rec)

        return filtered

    def schedule_tweets(
        self,
        tweets: List[Tweet],
        frequency: Optional[SchedulingFrequency] = None,
    ) -> List[Tweet]:
        """
        Schedule tweets for posting.

        Args:
            tweets: Tweets to schedule.
            frequency: Scheduling frequency (uses preferences if not provided).

        Returns:
            Tweets with scheduled_time set.
        """
        if frequency is None:
            frequency = self.preferences.schedule_frequency

        now = datetime.now(timezone.utc)

        for i, tweet in enumerate(tweets):
            if frequency == SchedulingFrequency.IMMEDIATE:
                # Stagger by 5 minutes
                tweet.scheduled_time = now + timedelta(minutes=i * 5)

            elif frequency == SchedulingFrequency.MORNING:
                # Schedule for 8 AM next day
                tomorrow_8am = (now + timedelta(days=1)).replace(
                    hour=8, minute=0, second=0, microsecond=0
                )
                tweet.scheduled_time = tomorrow_8am + timedelta(minutes=i * 15)

            elif frequency == SchedulingFrequency.AFTERNOON:
                # Schedule for 1 PM next day
                tomorrow_1pm = (now + timedelta(days=1)).replace(
                    hour=13, minute=0, second=0, microsecond=0
                )
                tweet.scheduled_time = tomorrow_1pm + timedelta(minutes=i * 15)

            elif frequency == SchedulingFrequency.EVENING:
                # Schedule for 6 PM next day
                tomorrow_6pm = (now + timedelta(days=1)).replace(
                    hour=18, minute=0, second=0, microsecond=0
                )
                tweet.scheduled_time = tomorrow_6pm + timedelta(minutes=i * 15)

        return tweets

    def get_statistics(self, tweets: List[Tweet]) -> Dict:
        """Generate statistics about tweets."""
        if not tweets:
            return {
                "total_tweets": 0,
                "total_characters": 0,
                "single_tweets": 0,
                "threads": 0,
            }

        threads = set(t.thread_id for t in tweets if t.thread_id)
        single = sum(1 for t in tweets if t.tweet_type == TweetType.SINGLE)

        return {
            "total_tweets": len(tweets),
            "total_characters": sum(t.character_count for t in tweets),
            "single_tweets": single,
            "threads": len(threads),
            "critical_count": sum(
                1 for t in tweets
                if t.recommendation_type == RecommendationType.CRITICAL
            ),
            "featured_count": sum(
                1 for t in tweets
                if t.recommendation_type == RecommendationType.FEATURED
            ),
            "average_length": sum(t.character_count for t in tweets) // len(tweets)
            if tweets
            else 0,
        }

    def preview_tweet(self, tweet: Tweet) -> str:
        """Generate a preview of the tweet."""
        preview = f"Tweet {tweet.tweet_type.value}"

        if tweet.thread_id:
            preview += f" (Part {tweet.thread_position + 1})"

        preview += f"\n{'=' * 40}\n"
        preview += tweet.text
        preview += f"\n{'=' * 40}\n"
        preview += f"Length: {tweet.character_count}/{self.MAX_TWEET_LENGTH}\n"

        if tweet.scheduled_time:
            preview += f"Scheduled: {tweet.scheduled_time.isoformat()}\n"

        return preview


class XConfigurationManager:
    """Manage X (Twitter) configuration and credentials."""

    def __init__(self, user_id: str):
        """
        Initialize configuration manager.

        Args:
            user_id: User identifier.
        """
        self.user_id = user_id
        self.api_config = XAPIConfig()
        self.preferences = XPreferences()
        self.content_generator: Optional[XContentGenerator] = None

    def configure_api(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
        bearer_token: str,
        user_id: str,
        handle: str,
    ) -> bool:
        """
        Configure API credentials.

        Returns:
            True if configuration valid.
        """
        self.api_config.api_key = api_key
        self.api_config.api_secret = api_secret
        self.api_config.access_token = access_token
        self.api_config.access_token_secret = access_token_secret
        self.api_config.bearer_token = bearer_token
        self.api_config.user_id = user_id
        self.api_config.handle = handle.lstrip("@")

        # Initialize content generator
        self.content_generator = XContentGenerator(
            handle=self.api_config.handle,
            preferences=self.preferences,
        )

        return self.api_config.is_configured()

    def set_preferences(
        self,
        auto_tweet: Optional[bool] = None,
        share_critical: Optional[bool] = None,
        share_featured: Optional[bool] = None,
        share_relevant: Optional[bool] = None,
        include_hashtags: Optional[bool] = None,
        custom_hashtags: Optional[List[str]] = None,
        max_tweets_per_day: Optional[int] = None,
        schedule_frequency: Optional[SchedulingFrequency] = None,
    ) -> None:
        """Update preferences."""
        if auto_tweet is not None:
            self.preferences.auto_tweet = auto_tweet
        if share_critical is not None:
            self.preferences.share_critical = share_critical
        if share_featured is not None:
            self.preferences.share_featured = share_featured
        if share_relevant is not None:
            self.preferences.share_relevant = share_relevant
        if include_hashtags is not None:
            self.preferences.include_hashtags = include_hashtags
        if custom_hashtags is not None:
            self.preferences.custom_hashtags = custom_hashtags
        if max_tweets_per_day is not None:
            self.preferences.max_tweets_per_day = max_tweets_per_day
        if schedule_frequency is not None:
            self.preferences.schedule_frequency = schedule_frequency

    def get_configuration(self) -> Dict:
        """Get current configuration."""
        return {
            "api_configured": self.api_config.is_configured(),
            "handle": self.api_config.handle,
            "auto_tweet": self.preferences.auto_tweet,
            "share_critical": self.preferences.share_critical,
            "share_featured": self.preferences.share_featured,
            "share_relevant": self.preferences.share_relevant,
            "max_tweets_per_day": self.preferences.max_tweets_per_day,
            "schedule_frequency": self.preferences.schedule_frequency.value,
            "custom_hashtags": self.preferences.custom_hashtags,
        }


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)
    print("X Configuration initialized")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
