"""
Tests for Decision Engine.

Covers:
- Recommendation scoring
- Recommendation type classification
- Notification urgency calculation
- Delivery time scheduling
- Article filtering
- Duplicate suppression
- Feedback recording
- Statistics generation
- Full decision workflows
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.collectors.rss_collector import Article
from app.processors.importance import ImportanceScore, ImportanceLevel
from app.processors.personalization import PersonalizationEngine, InteractionType
from app.analyzers.decision_engine import (
    DecisionEngine,
    Recommendation,
    RecommendationType,
    NotificationUrgency,
    RecommendationScore,
)


@pytest.fixture
def personalization_engine():
    """Create a personalization engine with sample profile."""
    engine = PersonalizationEngine(user_id="test_user")

    # Build up some interests
    sample_article = Article(
        source="arxiv",
        id="1",
        title="Test",
        url="https://example.com",
        summary="Test",
        published_at=datetime.now(timezone.utc),
        author="Test",
        category="AI",
        tags=["deep-learning", "research"],
        metadata={},
    )

    for _ in range(3):
        engine.record_interaction(sample_article, InteractionType.LIKE)

    return engine


@pytest.fixture
def decision_engine(personalization_engine):
    """Create a decision engine with personalization."""
    return DecisionEngine(personalization_engine)


@pytest.fixture
def sample_importance_scores(sample_articles):
    """Create sample importance scores."""
    article = sample_articles[0]
    return {
        "critical": ImportanceScore(
            article=article,
            overall_score=9.5,
            importance_level=ImportanceLevel.CRITICAL,
            authority_score=0.9,
            engagement_score=0.8,
            recency_score=0.95,
            relevance_score=0.85,
            trend_score=0.9,
            citation_score=0.7,
            reasoning=["Very important"],
            trending=True,
            trending_velocity=5.0,
            matched_interests=[],
        ),
        "high": ImportanceScore(
            article=article,
            overall_score=7.5,
            importance_level=ImportanceLevel.HIGH,
            authority_score=0.8,
            engagement_score=0.7,
            recency_score=0.85,
            relevance_score=0.75,
            trend_score=0.7,
            citation_score=0.6,
            reasoning=["Important"],
            trending=False,
            trending_velocity=0.0,
            matched_interests=[],
        ),
        "moderate": ImportanceScore(
            article=article,
            overall_score=5.0,
            importance_level=ImportanceLevel.MODERATE,
            authority_score=0.6,
            engagement_score=0.5,
            recency_score=0.7,
            relevance_score=0.5,
            trend_score=0.5,
            citation_score=0.4,
            reasoning=["Moderate"],
            trending=False,
            trending_velocity=0.0,
            matched_interests=[],
        ),
        "low": ImportanceScore(
            article=article,
            overall_score=2.0,
            importance_level=ImportanceLevel.LOW,
            authority_score=0.4,
            engagement_score=0.3,
            recency_score=0.5,
            relevance_score=0.3,
            trend_score=0.2,
            citation_score=0.2,
            reasoning=["Low"],
            trending=False,
            trending_velocity=0.0,
            matched_interests=[],
        ),
    }


@pytest.fixture
def sample_articles():
    """Create sample articles."""
    return [
        Article(
            source="arxiv",
            id="1",
            title="Critical AI Research",
            url="https://arxiv.org/abs/1",
            summary="Breakthrough in AI research",
            published_at=datetime.now(timezone.utc),
            author="Alice",
            category="AI",
            tags=["deep-learning", "research"],
            metadata={},
        ),
        Article(
            source="github",
            id="2",
            title="Popular ML Library",
            url="https://github.com/ml-lib",
            summary="New machine learning library",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
            author="Bob",
            category="ML",
            tags=["machine-learning", "library"],
            metadata={},
        ),
        Article(
            source="medium",
            id="3",
            title="Web Development Tips",
            url="https://medium.com/web",
            summary="Tips for web development",
            published_at=datetime.now(timezone.utc) - timedelta(days=7),
            author="Charlie",
            category="WebDev",
            tags=["web", "javascript"],
            metadata={},
        ),
        Article(
            source="blog",
            id="4",
            title="Low Quality Post",
            url="https://example.com/low",
            summary="X",
            published_at=datetime.now(timezone.utc) - timedelta(days=30),
            author="Diana",
            category="Random",
            tags=[],
            metadata={},
        ),
    ]


class TestRecommendationScore:
    """Tests for RecommendationScore."""

    def test_creation(self):
        """RecommendationScore should initialize correctly."""
        score = RecommendationScore(
            article_id="1",
            combined_score=8.5,
            importance_score=9.0,
            personalization_boost=0.5,
            quality_score=0.8,
            recency_score=0.9,
            engagement_potential=0.7,
        )

        assert score.article_id == "1"
        assert score.combined_score == 8.5
        assert score.importance_score == 9.0


class TestDecisionEngine:
    """Tests for DecisionEngine."""

    def test_initialization(self, personalization_engine):
        """Engine should initialize correctly."""
        engine = DecisionEngine(personalization_engine)
        assert engine.personalization == personalization_engine
        assert engine.quality_threshold == 0.5
        assert engine.min_importance_score == 2.0

    def test_score_article_critical(self, decision_engine, sample_articles, sample_importance_scores):
        """Should score critical articles highly."""
        article = sample_articles[0]
        importance = sample_importance_scores["critical"]

        scoring = decision_engine.score_article(article, importance, quality_score=0.9)

        assert scoring.combined_score > 8.0
        assert scoring.importance_score == 9.5
        assert len(scoring.reasoning) > 0

    def test_score_article_low(self, decision_engine, sample_articles, sample_importance_scores):
        """Should score low importance articles appropriately."""
        article = sample_articles[3]
        importance = sample_importance_scores["low"]

        scoring = decision_engine.score_article(article, importance, quality_score=0.3)

        assert scoring.combined_score < 3.0
        assert scoring.importance_score == 2.0

    def test_recency_bonus(self, decision_engine, sample_articles, sample_importance_scores):
        """Fresh articles should get recency bonus."""
        article = sample_articles[0]  # Published now
        importance = sample_importance_scores["critical"]

        scoring = decision_engine.score_article(article, importance)

        assert scoring.recency_score == 1.0

    def test_recency_decay(self, decision_engine, sample_importance_scores):
        """Old articles should have reduced recency."""
        old_article = Article(
            source="old",
            id="old",
            title="Old",
            url="https://example.com/old",
            summary="Old",
            published_at=datetime.now(timezone.utc) - timedelta(days=30),
            author="Test",
            category="Test",
            tags=[],
            metadata={},
        )

        importance = sample_importance_scores["critical"]
        scoring = decision_engine.score_article(old_article, importance)

        assert scoring.recency_score < 0.5

    def test_decide_critical(self, decision_engine):
        """Should classify critical recommendations."""
        scoring = RecommendationScore(
            article_id="1",
            combined_score=10.0,
            importance_score=9.5,
            personalization_boost=0.5,
            quality_score=0.8,
            recency_score=0.9,
            engagement_potential=0.9,
        )

        rec_type = decision_engine.decide_recommendation_type(scoring)
        assert rec_type == RecommendationType.CRITICAL

    def test_decide_featured(self, decision_engine):
        """Should classify featured recommendations."""
        scoring = RecommendationScore(
            article_id="1",
            combined_score=8.0,
            importance_score=8.0,
            personalization_boost=0.3,
            quality_score=0.7,
            recency_score=0.8,
            engagement_potential=0.7,
        )

        rec_type = decision_engine.decide_recommendation_type(scoring)
        assert rec_type == RecommendationType.FEATURED

    def test_decide_relevant(self, decision_engine):
        """Should classify relevant recommendations."""
        scoring = RecommendationScore(
            article_id="1",
            combined_score=5.5,
            importance_score=5.5,
            personalization_boost=0.2,
            quality_score=0.6,
            recency_score=0.7,
            engagement_potential=0.5,
        )

        rec_type = decision_engine.decide_recommendation_type(scoring)
        assert rec_type == RecommendationType.RELEVANT

    def test_decide_discover(self, decision_engine):
        """Should classify discover recommendations."""
        scoring = RecommendationScore(
            article_id="1",
            combined_score=3.5,
            importance_score=3.5,
            personalization_boost=0.1,
            quality_score=0.5,
            recency_score=0.6,
            engagement_potential=0.3,
        )

        rec_type = decision_engine.decide_recommendation_type(scoring)
        assert rec_type == RecommendationType.DISCOVER

    def test_notification_urgency_critical(self, decision_engine):
        """Critical recommendations should be immediate."""
        urgency = decision_engine.decide_notification_urgency(
            RecommendationType.CRITICAL,
            importance=9.5,
            trending=True,
        )
        assert urgency == NotificationUrgency.IMMEDIATE

    def test_notification_urgency_high(self, decision_engine):
        """Featured recommendations should be high urgency."""
        urgency = decision_engine.decide_notification_urgency(
            RecommendationType.FEATURED,
            importance=8.0,
            trending=False,
        )
        assert urgency == NotificationUrgency.HIGH

    def test_notification_urgency_normal(self, decision_engine):
        """Relevant recommendations should be normal urgency."""
        urgency = decision_engine.decide_notification_urgency(
            RecommendationType.RELEVANT,
            importance=5.0,
            trending=False,
        )
        assert urgency == NotificationUrgency.NORMAL

    def test_delivery_time_immediate(self, decision_engine):
        """Immediate urgency should deliver in 5 minutes."""
        delivery = decision_engine.suggest_delivery_time(NotificationUrgency.IMMEDIATE)
        now = datetime.now(timezone.utc)
        time_diff = (delivery - now).total_seconds()

        assert 0 < time_diff <= 300  # Within 5 minutes

    def test_delivery_time_high(self, decision_engine):
        """High urgency should deliver within 2 hours."""
        delivery = decision_engine.suggest_delivery_time(NotificationUrgency.HIGH)
        now = datetime.now(timezone.utc)
        time_diff = (delivery - now).total_seconds()

        assert 0 < time_diff <= 7200  # Within 2 hours

    def test_delivery_time_low(self, decision_engine):
        """Low urgency should deliver in weekly digest."""
        delivery = decision_engine.suggest_delivery_time(NotificationUrgency.LOW)
        now = datetime.now(timezone.utc)
        time_diff = (delivery - now).total_seconds()

        assert time_diff > 86400 * 5  # More than 5 days

    def test_should_include_quality_threshold(self, decision_engine, sample_articles):
        """Should exclude low quality articles."""
        article = sample_articles[0]
        scoring = RecommendationScore(
            article_id=article.id,
            combined_score=5.0,
            importance_score=5.0,
            personalization_boost=0.2,
            quality_score=0.3,  # Below threshold
            recency_score=0.7,
            engagement_potential=0.5,
        )

        include, reason = decision_engine.should_include_article(article, scoring)
        assert not include
        assert "Quality" in reason

    def test_should_include_importance_threshold(self, decision_engine, sample_articles):
        """Should exclude low importance articles."""
        article = sample_articles[3]
        scoring = RecommendationScore(
            article_id=article.id,
            combined_score=1.5,
            importance_score=1.5,  # Below threshold
            personalization_boost=0.1,
            quality_score=0.7,
            recency_score=0.5,
            engagement_potential=0.2,
        )

        include, reason = decision_engine.should_include_article(article, scoring)
        assert not include
        assert "Importance" in reason

    def test_should_include_category_filter(self, decision_engine, sample_articles):
        """Should filter by category."""
        article = sample_articles[2]  # WebDev
        scoring = RecommendationScore(
            article_id=article.id,
            combined_score=5.0,
            importance_score=5.0,
            personalization_boost=0.2,
            quality_score=0.7,
            recency_score=0.7,
            engagement_potential=0.5,
        )

        # Include only AI
        include, reason = decision_engine.should_include_article(
            article,
            scoring,
            category_filter=["AI"],
        )
        assert not include
        assert "Category" in reason

    def test_should_include_source_filter(self, decision_engine, sample_articles):
        """Should filter by source."""
        article = sample_articles[2]  # Medium
        scoring = RecommendationScore(
            article_id=article.id,
            combined_score=5.0,
            importance_score=5.0,
            personalization_boost=0.2,
            quality_score=0.7,
            recency_score=0.7,
            engagement_potential=0.5,
        )

        # Include only arxiv
        include, reason = decision_engine.should_include_article(
            article,
            scoring,
            source_filter=["arxiv"],
        )
        assert not include
        assert "Source" in reason

    def test_create_recommendation(
        self,
        decision_engine,
        sample_articles,
        sample_importance_scores,
    ):
        """Should create valid recommendation."""
        article = sample_articles[0]
        importance = sample_importance_scores["critical"]

        rec = decision_engine.create_recommendation(
            article,
            importance,
            quality_score=0.8,
        )

        assert rec is not None
        assert rec.article == article
        # With importance 9.5 and personalization boost, should be FEATURED or CRITICAL
        assert rec.recommendation_type in [RecommendationType.CRITICAL, RecommendationType.FEATURED]
        assert rec.combined_score > 8.0

    def test_create_recommendation_filtered_out(
        self,
        decision_engine,
        sample_articles,
        sample_importance_scores,
    ):
        """Should return None for filtered articles."""
        article = sample_articles[3]  # Low quality
        importance = sample_importance_scores["low"]

        rec = decision_engine.create_recommendation(
            article,
            importance,
            quality_score=0.3,
        )

        assert rec is None

    def test_rank_recommendations(self, decision_engine):
        """Should rank recommendations by importance."""
        recs = []

        # Create 3 recommendations with different types
        for rec_type, score in [
            (RecommendationType.CRITICAL, 10.0),
            (RecommendationType.RELEVANT, 5.0),
            (RecommendationType.FEATURED, 8.0),
        ]:
            article = Article(
                source="test",
                id=rec_type.value,
                title=rec_type.value,
                url="https://example.com",
                summary="Test",
                published_at=datetime.now(timezone.utc),
                author="Test",
                category="Test",
                tags=[],
                metadata={},
            )

            rec = Recommendation(
                article=article,
                recommendation_type=rec_type,
                combined_score=score,
                scoring=RecommendationScore(
                    article_id=article.id,
                    combined_score=score,
                    importance_score=score,
                    personalization_boost=0.5,
                    quality_score=0.7,
                    recency_score=0.8,
                    engagement_potential=0.6,
                ),
                personalization_boost=0.5,
            )
            recs.append(rec)

        ranked = decision_engine.rank_recommendations(recs)

        # Should be: CRITICAL, FEATURED, RELEVANT
        assert ranked[0].recommendation_type == RecommendationType.CRITICAL
        assert ranked[1].recommendation_type == RecommendationType.FEATURED
        assert ranked[2].recommendation_type == RecommendationType.RELEVANT

    def test_suppress_duplicates(self, decision_engine):
        """Should suppress recently recommended articles."""
        now = datetime.now(timezone.utc)
        # Create 2 recommendations with delivery times
        recs = []
        for i in range(2):
            article = Article(
                source="test",
                id=str(i),
                title=f"Article {i}",
                url="https://example.com",
                summary="Test",
                published_at=datetime.now(timezone.utc),
                author="Test",
                category="Test",
                tags=[],
                metadata={},
            )

            rec = Recommendation(
                article=article,
                recommendation_type=RecommendationType.RELEVANT,
                combined_score=5.0,
                scoring=RecommendationScore(
                    article_id=article.id,
                    combined_score=5.0,
                    importance_score=5.0,
                    personalization_boost=0.2,
                    quality_score=0.7,
                    recency_score=0.7,
                    engagement_potential=0.5,
                ),
                personalization_boost=0.2,
                suggested_delivery_time=now + timedelta(hours=2),
            )
            recs.append(rec)

        # First call adds to history
        dedup1 = decision_engine.suppress_duplicates(recs)
        assert len(dedup1) == 2

        # Second call with same article should suppress (within 24 hour window)
        dedup2 = decision_engine.suppress_duplicates([recs[0]])
        assert len(dedup2) == 0  # First article was suppressed

    def test_record_feedback(self, decision_engine, sample_articles):
        """Should record feedback on recommendations."""
        article = sample_articles[0]
        rec = Recommendation(
            article=article,
            recommendation_type=RecommendationType.RELEVANT,
            combined_score=5.0,
            scoring=RecommendationScore(
                article_id=article.id,
                combined_score=5.0,
                importance_score=5.0,
                personalization_boost=0.2,
                quality_score=0.7,
                recency_score=0.7,
                engagement_potential=0.5,
            ),
            personalization_boost=0.2,
        )

        decision_engine.record_feedback(rec, "read", time_spent_seconds=60)

        assert len(decision_engine.feedback_history) == 1
        assert decision_engine.feedback_history[0]["action"] == "read"

    def test_get_statistics(self, decision_engine, sample_articles):
        """Should generate statistics."""
        article = sample_articles[0]
        rec = Recommendation(
            article=article,
            recommendation_type=RecommendationType.RELEVANT,
            combined_score=5.0,
            scoring=RecommendationScore(
                article_id=article.id,
                combined_score=5.0,
                importance_score=5.0,
                personalization_boost=0.2,
                quality_score=0.7,
                recency_score=0.7,
                engagement_potential=0.5,
            ),
            personalization_boost=0.2,
        )

        decision_engine.record_feedback(rec, "read", time_spent_seconds=120)
        decision_engine.record_feedback(rec, "skip")

        stats = decision_engine.get_statistics()

        assert "total_feedback_recorded" in stats
        assert stats["total_feedback_recorded"] == 2
        assert "read_through_rate" in stats

    def test_generate_snippet(self, decision_engine, sample_articles):
        """Should generate article snippets."""
        article = sample_articles[0]
        snippet = decision_engine._generate_snippet(article, max_length=30)

        assert len(snippet) <= 31  # 30 + "…"

    def test_get_daily_recommendations(
        self,
        decision_engine,
        sample_articles,
        sample_importance_scores,
    ):
        """Should get daily recommendations."""
        # Create tuples of (article, importance, quality)
        articles_with_scores = [
            (sample_articles[0], sample_importance_scores["critical"], 0.9),
            (sample_articles[1], sample_importance_scores["high"], 0.8),
            (sample_articles[2], sample_importance_scores["moderate"], 0.7),
        ]

        recs = decision_engine.get_daily_recommendations(
            articles_with_scores,
            max_recommendations=2,
        )

        assert len(recs) <= 2
        assert len(recs) > 0
        # Should be sorted by importance
        assert recs[0].combined_score >= recs[1].combined_score


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_importance(self, decision_engine, sample_articles):
        """Should handle zero importance scores."""
        article = sample_articles[0]
        importance = ImportanceScore(
            article=article,
            overall_score=0.0,
            importance_level=ImportanceLevel.MINIMAL,
            authority_score=0.0,
            engagement_score=0.0,
            recency_score=0.0,
            relevance_score=0.0,
            trend_score=0.0,
            citation_score=0.0,
            reasoning=[],
            trending=False,
            trending_velocity=0.0,
            matched_interests=[],
        )

        scoring = decision_engine.score_article(article, importance)
        assert scoring.importance_score == 0.0

    def test_max_recommendations(self, decision_engine, sample_articles, sample_importance_scores):
        """Should respect max recommendations limit."""
        articles_with_scores = [
            (article, sample_importance_scores["critical"], 0.8)
            for article in sample_articles
        ]

        recs = decision_engine.get_daily_recommendations(
            articles_with_scores,
            max_recommendations=1,
        )

        assert len(recs) <= 1

    def test_feedback_history_capping(self, decision_engine, sample_articles):
        """Feedback history should be capped at 1000."""
        article = sample_articles[0]
        rec = Recommendation(
            article=article,
            recommendation_type=RecommendationType.RELEVANT,
            combined_score=5.0,
            scoring=RecommendationScore(
                article_id=article.id,
                combined_score=5.0,
                importance_score=5.0,
                personalization_boost=0.2,
                quality_score=0.7,
                recency_score=0.7,
                engagement_potential=0.5,
            ),
            personalization_boost=0.2,
        )

        # Record 1500 feedbacks
        for i in range(1500):
            decision_engine.record_feedback(rec, "read")

        assert len(decision_engine.feedback_history) <= 1000


class TestIntegration:
    """Integration tests."""

    def test_full_decision_workflow(
        self,
        decision_engine,
        sample_articles,
        sample_importance_scores,
    ):
        """Full workflow: score → decide → rank → filter → feedback."""
        # Score articles
        article = sample_articles[0]
        importance = sample_importance_scores["critical"]
        scoring = decision_engine.score_article(article, importance, quality_score=0.8)

        # Create recommendation
        rec = decision_engine.create_recommendation(
            article,
            importance,
            quality_score=0.8,
        )

        assert rec is not None

        # Rank (single item)
        ranked = decision_engine.rank_recommendations([rec])
        assert len(ranked) == 1

        # Suppress duplicates
        dedup = decision_engine.suppress_duplicates(ranked)
        assert len(dedup) == 1

        # Record feedback
        decision_engine.record_feedback(rec, "read", time_spent_seconds=90)

        # Get statistics
        stats = decision_engine.get_statistics()
        assert stats["total_feedback_recorded"] == 1
