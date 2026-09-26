"""
Tests for X (Twitter) Configuration.

Covers:
- API configuration
- User preferences
- Tweet generation (single and thread)
- Content filtering
- Scheduling
- Character counting
- Preview generation
- Configuration management
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.collectors.rss_collector import Article
from app.processors.importance import ImportanceScore, ImportanceLevel
from app.analyzers.decision_engine import (
    Recommendation,
    RecommendationType,
    NotificationUrgency,
    RecommendationScore,
)
from app.platforms.x_config import (
    XContentGenerator,
    XConfigurationManager,
    XAPIConfig,
    XPreferences,
    Tweet,
    TweetType,
    SchedulingFrequency,
)


@pytest.fixture
def sample_articles():
    """Create sample articles."""
    now = datetime.now(timezone.utc)
    return [
        Article(
            source="arxiv",
            id="1",
            title="Critical Breakthrough in AI Research",
            url="https://arxiv.org/abs/2024.1000",
            summary="Major breakthrough announcement",
            published_at=now,
            author="Alice Smith",
            category="AI",
            tags=["deep-learning", "breakthrough"],
            metadata={},
        ),
        Article(
            source="github",
            id="2",
            title="New ML Library Released on GitHub",
            url="https://github.com/ml-lib",
            summary="Fast library for machine learning",
            published_at=now - timedelta(hours=2),
            author="Bob Jones",
            category="ML",
            tags=["python", "library"],
            metadata={},
        ),
    ]


@pytest.fixture
def sample_recommendations(sample_articles):
    """Create sample recommendations."""
    recs = []

    for i, article in enumerate(sample_articles):
        scoring = RecommendationScore(
            article_id=article.id,
            combined_score=9.0 - (i * 2),
            importance_score=9.0 - (i * 2),
            personalization_boost=0.4,
            quality_score=0.8,
            recency_score=0.9,
            engagement_potential=0.8,
        )

        rec = Recommendation(
            article=article,
            recommendation_type=(
                RecommendationType.CRITICAL
                if i == 0
                else RecommendationType.FEATURED
            ),
            combined_score=scoring.combined_score,
            scoring=scoring,
            personalization_boost=0.4,
            matched_interests=["AI", "ML"],
        )
        recs.append(rec)

    return recs


@pytest.fixture
def x_generator():
    """Create X content generator."""
    return XContentGenerator(handle="ai_radar")


@pytest.fixture
def x_config_manager():
    """Create X configuration manager."""
    return XConfigurationManager(user_id="user123")


class TestXAPIConfig:
    """Tests for XAPIConfig."""

    def test_creation(self):
        """XAPIConfig should initialize correctly."""
        config = XAPIConfig()
        assert not config.is_configured()

    def test_is_configured_true(self):
        """Should report configured when all fields set."""
        config = XAPIConfig(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret",
            user_id="123",
        )
        assert config.is_configured()

    def test_is_configured_false(self):
        """Should report not configured when missing fields."""
        config = XAPIConfig(
            api_key="key",
            api_secret="secret",
            user_id="123",
        )
        assert not config.is_configured()


class TestXPreferences:
    """Tests for XPreferences."""

    def test_default_preferences(self):
        """XPreferences should have sensible defaults."""
        prefs = XPreferences()
        assert prefs.enabled
        assert not prefs.auto_tweet
        assert prefs.share_critical
        assert prefs.max_tweets_per_day == 5

    def test_custom_hashtags(self):
        """Should support custom hashtags."""
        prefs = XPreferences(
            custom_hashtags=["#AI", "#ML"],
        )
        assert "#AI" in prefs.custom_hashtags


class TestXContentGenerator:
    """Tests for XContentGenerator."""

    def test_initialization(self, x_generator):
        """Generator should initialize correctly."""
        assert x_generator.handle == "ai_radar"
        assert x_generator.MAX_TWEET_LENGTH == 280

    def test_shorten_title_short(self, x_generator):
        """Short titles should pass through."""
        title = "Short Title"
        shortened = x_generator._shorten_title(title, max_length=50)
        assert shortened == title

    def test_shorten_title_long(self, x_generator):
        """Long titles should be truncated."""
        title = "This is a very long title that definitely exceeds the maximum length we want"
        shortened = x_generator._shorten_title(title, max_length=30)
        assert len(shortened) <= 31  # 30 + ellipsis
        assert shortened.endswith("…")

    def test_extract_domain(self, x_generator):
        """Should extract domain from URL."""
        url = "https://www.arxiv.org/abs/2024.1000"
        domain = x_generator._extract_domain(url)
        assert "arxiv" in domain

    def test_estimate_tweet_length_simple(self, x_generator):
        """Should estimate tweet length."""
        text = "Hello world"
        length = x_generator.estimate_tweet_length(text)
        assert length == 11

    def test_estimate_tweet_length_with_url(self, x_generator):
        """URLs should count as 23 characters."""
        text = "Check this out https://example.com/very/long/url/that/is/longer/than/23"
        length = x_generator.estimate_tweet_length(text)
        # Text without URL + 23 for URL
        assert length == len(text) - len("https://example.com/very/long/url/that/is/longer/than/23") + 23

    def test_generate_single_tweet(self, x_generator, sample_recommendations):
        """Should generate single tweet."""
        rec = sample_recommendations[0]
        tweet = x_generator.generate_single_tweet(rec)

        assert tweet is not None
        assert tweet.article_id == rec.article.id
        assert tweet.tweet_type == TweetType.SINGLE
        assert tweet.character_count <= x_generator.MAX_TWEET_LENGTH

    def test_single_tweet_has_url(self, x_generator, sample_recommendations):
        """Single tweet should include article URL."""
        rec = sample_recommendations[0]
        tweet = x_generator.generate_single_tweet(rec)

        assert tweet is not None
        assert rec.article.url in tweet.text

    def test_single_tweet_with_hashtags(self, x_generator, sample_recommendations):
        """Single tweet should include hashtags if configured."""
        x_generator.preferences.include_hashtags = True
        x_generator.preferences.custom_hashtags = ["#AI"]

        rec = sample_recommendations[0]
        tweet = x_generator.generate_single_tweet(rec)

        assert tweet is not None
        assert len(tweet.hashtags) > 0

    def test_generate_thread(self, x_generator, sample_recommendations):
        """Should generate thread from recommendations."""
        tweets = x_generator.generate_thread(sample_recommendations, max_tweets=3)

        assert len(tweets) > 0
        assert tweets[0].tweet_type == TweetType.THREAD_START
        assert all(t.thread_id == tweets[0].thread_id for t in tweets)

    def test_thread_numbering(self, x_generator, sample_recommendations):
        """Thread tweets should have proper numbering."""
        tweets = x_generator.generate_thread(sample_recommendations, max_tweets=3)

        for i, tweet in enumerate(tweets):
            assert tweet.thread_position == i

    def test_thread_length_limit(self, x_generator, sample_recommendations):
        """Thread should respect max_tweets limit."""
        tweets = x_generator.generate_thread(sample_recommendations, max_tweets=2)
        # Should be intro + 1 recommendation
        assert len(tweets) <= 2

    def test_filter_critical_only(self, x_generator, sample_recommendations):
        """Should filter by recommendation type."""
        x_generator.preferences.share_critical = True
        x_generator.preferences.share_featured = False
        x_generator.preferences.share_relevant = False

        filtered = x_generator.filter_recommendations(sample_recommendations)

        # Should only have critical
        assert len(filtered) == 1
        assert filtered[0].recommendation_type == RecommendationType.CRITICAL

    def test_filter_multiple_types(self, x_generator, sample_recommendations):
        """Should filter multiple types."""
        x_generator.preferences.share_critical = True
        x_generator.preferences.share_featured = True
        x_generator.preferences.share_relevant = False

        filtered = x_generator.filter_recommendations(sample_recommendations)

        assert len(filtered) == 2

    def test_schedule_immediate(self, x_generator, sample_recommendations):
        """Should schedule immediate tweets with stagger."""
        tweet_list = [
            x_generator.generate_single_tweet(sample_recommendations[0]),
            x_generator.generate_single_tweet(sample_recommendations[1]),
        ]
        tweet_list = [t for t in tweet_list if t is not None]

        scheduled = x_generator.schedule_tweets(
            tweet_list,
            frequency=SchedulingFrequency.IMMEDIATE,
        )

        # All should have times
        assert all(t.scheduled_time for t in scheduled)

        # Second should be after first
        if len(scheduled) > 1:
            assert scheduled[1].scheduled_time > scheduled[0].scheduled_time

    def test_schedule_morning(self, x_generator, sample_recommendations):
        """Should schedule for morning."""
        tweet_list = [
            x_generator.generate_single_tweet(sample_recommendations[0]),
        ]
        tweet_list = [t for t in tweet_list if t is not None]

        scheduled = x_generator.schedule_tweets(
            tweet_list,
            frequency=SchedulingFrequency.MORNING,
        )

        assert scheduled[0].scheduled_time is not None
        assert scheduled[0].scheduled_time.hour == 8

    def test_schedule_afternoon(self, x_generator, sample_recommendations):
        """Should schedule for afternoon."""
        tweet_list = [
            x_generator.generate_single_tweet(sample_recommendations[0]),
        ]
        tweet_list = [t for t in tweet_list if t is not None]

        scheduled = x_generator.schedule_tweets(
            tweet_list,
            frequency=SchedulingFrequency.AFTERNOON,
        )

        assert scheduled[0].scheduled_time is not None
        assert scheduled[0].scheduled_time.hour == 13

    def test_get_statistics(self, x_generator, sample_recommendations):
        """Should generate statistics."""
        tweets = x_generator.generate_thread(sample_recommendations, max_tweets=3)

        stats = x_generator.get_statistics(tweets)

        assert stats["total_tweets"] == len(tweets)
        assert stats["total_characters"] > 0
        assert stats["threads"] == 1

    def test_statistics_empty(self, x_generator):
        """Statistics for empty list."""
        stats = x_generator.get_statistics([])

        assert stats["total_tweets"] == 0
        assert stats["single_tweets"] == 0

    def test_preview_tweet(self, x_generator, sample_recommendations):
        """Should generate tweet preview."""
        tweet = x_generator.generate_single_tweet(sample_recommendations[0])

        preview = x_generator.preview_tweet(tweet)

        assert "Tweet" in preview
        assert tweet.text in preview
        assert f"Length: {tweet.character_count}" in preview


class TestTweet:
    """Tests for Tweet."""

    def test_creation(self):
        """Tweet should initialize correctly."""
        tweet = Tweet(
            text="Hello Twitter",
            tweet_type=TweetType.SINGLE,
        )

        assert tweet.text == "Hello Twitter"
        assert tweet.character_count == 13

    def test_tweet_type_enum(self):
        """Tweet types should be valid."""
        types = [
            TweetType.SINGLE,
            TweetType.THREAD,
            TweetType.THREAD_START,
            TweetType.THREAD_MIDDLE,
            TweetType.THREAD_END,
        ]

        assert len(types) == 5

    def test_tweet_with_hashtags(self):
        """Tweet should support hashtags."""
        tweet = Tweet(
            text="Great article #AI #ML",
            hashtags=["#AI", "#ML"],
        )

        assert len(tweet.hashtags) == 2


class TestXConfigurationManager:
    """Tests for XConfigurationManager."""

    def test_initialization(self, x_config_manager):
        """Manager should initialize correctly."""
        assert x_config_manager.user_id == "user123"
        assert not x_config_manager.api_config.is_configured()

    def test_configure_api(self, x_config_manager):
        """Should configure API."""
        success = x_config_manager.configure_api(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret",
            bearer_token="bearer",
            user_id="123",
            handle="ai_radar",
        )

        assert success
        assert x_config_manager.api_config.is_configured()
        assert x_config_manager.content_generator is not None

    def test_set_preferences(self, x_config_manager):
        """Should set preferences."""
        x_config_manager.set_preferences(
            auto_tweet=True,
            share_critical=True,
            share_featured=False,
            max_tweets_per_day=10,
        )

        assert x_config_manager.preferences.auto_tweet
        assert x_config_manager.preferences.share_critical
        assert not x_config_manager.preferences.share_featured
        assert x_config_manager.preferences.max_tweets_per_day == 10

    def test_get_configuration(self, x_config_manager):
        """Should get configuration."""
        x_config_manager.configure_api(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret",
            bearer_token="bearer",
            user_id="123",
            handle="ai_radar",
        )

        config = x_config_manager.get_configuration()

        assert config["api_configured"]
        assert config["handle"] == "ai_radar"
        assert "auto_tweet" in config


class TestEdgeCases:
    """Tests for edge cases."""

    def test_tweet_too_long(self, x_generator, sample_articles):
        """Should handle articles that don't fit in tweet."""
        article = Article(
            source="test",
            id="1",
            title="This is an extremely long title that contains many words and will definitely exceed the maximum allowed length for a tweet when combined with other required elements like source and author information",
            url="https://example.com/very/long/url",
            summary="Test",
            published_at=datetime.now(timezone.utc),
            author="Test Author",
            category="Test",
            tags=[],
            metadata={},
        )

        scoring = RecommendationScore(
            article_id=article.id,
            combined_score=5.0,
            importance_score=5.0,
            personalization_boost=0.2,
            quality_score=0.7,
            recency_score=0.7,
            engagement_potential=0.5,
        )

        rec = Recommendation(
            article=article,
            recommendation_type=RecommendationType.FEATURED,
            combined_score=5.0,
            scoring=scoring,
            personalization_boost=0.2,
        )

        # May return None if too long
        tweet = x_generator.generate_single_tweet(rec)
        # Either fits or returns None - both acceptable

    def test_article_no_author(self, x_generator):
        """Should handle articles without author."""
        article = Article(
            source="test",
            id="1",
            title="Test Article",
            url="https://example.com",
            summary="Test",
            published_at=datetime.now(timezone.utc),
            author=None,
            category="Test",
            tags=[],
            metadata={},
        )

        scoring = RecommendationScore(
            article_id=article.id,
            combined_score=5.0,
            importance_score=5.0,
            personalization_boost=0.2,
            quality_score=0.7,
            recency_score=0.7,
            engagement_potential=0.5,
        )

        rec = Recommendation(
            article=article,
            recommendation_type=RecommendationType.FEATURED,
            combined_score=5.0,
            scoring=scoring,
            personalization_boost=0.2,
        )

        tweet = x_generator.generate_single_tweet(rec)
        assert tweet is not None

    def test_empty_thread(self, x_generator):
        """Should handle empty recommendation list."""
        tweets = x_generator.generate_thread([], max_tweets=5)
        assert len(tweets) == 1  # Just intro tweet
        assert tweets[0].tweet_type == TweetType.THREAD_START

    def test_handle_with_at_symbol(self):
        """Should strip @ from handle."""
        gen = XContentGenerator(handle="@ai_radar")
        assert gen.handle == "ai_radar"


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self, x_config_manager, sample_recommendations):
        """Full workflow: configure → set prefs → generate tweets."""
        # Configure
        x_config_manager.configure_api(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret",
            bearer_token="bearer",
            user_id="123",
            handle="ai_radar",
        )

        # Set preferences
        x_config_manager.set_preferences(
            share_critical=True,
            share_featured=True,
            include_hashtags=True,
        )

        # Generate content
        generator = x_config_manager.content_generator
        assert generator is not None

        tweets = generator.generate_thread(sample_recommendations, max_tweets=3)
        assert len(tweets) > 0

        # Schedule
        scheduled = generator.schedule_tweets(tweets)
        assert all(t.scheduled_time for t in scheduled)

        # Get stats
        stats = generator.get_statistics(scheduled)
        assert stats["total_tweets"] > 0

    def test_single_vs_thread(self, x_generator, sample_recommendations):
        """Should handle single and thread generation."""
        # Single tweet
        single = x_generator.generate_single_tweet(sample_recommendations[0])
        assert single is not None
        assert single.tweet_type == TweetType.SINGLE

        # Thread
        thread = x_generator.generate_thread(sample_recommendations, max_tweets=3)
        assert len(thread) > 1
        assert thread[0].tweet_type == TweetType.THREAD_START
