"""
Tests for Importance Ranking Engine.

Covers:
- Authority scoring
- Engagement scoring
- Recency scoring with decay
- Relevance scoring and interest matching
- Trend detection and velocity
- Citation scoring
- Batch ranking and sorting
- Statistics generation
- Filtering by importance level
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.collectors.rss_collector import Article
from app.processors.importance import (
    ImportanceRankingEngine,
    ImportanceScore,
    ImportanceLevel,
)


@pytest.fixture
def sample_articles():
    """Create sample articles for testing."""
    return [
        # High quality, recent, high engagement
        Article(
            source="arxiv",
            id="1",
            title="Breakthrough: New Deep Learning Algorithm Achieves State-of-the-Art",
            url="https://arxiv.org/abs/2024.01234",
            summary="A novel approach combining transformers with attention mechanisms shows unprecedented results on multiple benchmarks.",
            published_at=datetime.now(timezone.utc),
            author="Dr. Alice Smith",
            category="AI",
            tags=["deep-learning", "neural-networks", "breakthrough"],
            metadata={"score": 500, "citations": 50},
        ),
        # Older article, low engagement
        Article(
            source="blog",
            id="2",
            title="Machine Learning Basics",
            url="https://example.com/ml-basics",
            summary="Introduction to machine learning concepts for beginners.",
            published_at=datetime.now(timezone.utc) - timedelta(days=180),
            author="Bob",
            category="AI",
            tags=["machine-learning", "tutorial"],
            metadata={"score": 10},
        ),
        # Very recent, trending
        Article(
            source="hackernews",
            id="3",
            title="OpenAI Releases New Model",
            url="https://news.ycombinator.com/item?id=39134",
            summary="OpenAI announced a new language model with improved capabilities.",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
            author="Sam Altman",
            category="AI",
            tags=["openai", "language-model", "breaking"],
            metadata={"score": 300, "views": 50000},
        ),
        # GitHub high stars
        Article(
            source="github",
            id="4",
            title="Revolutionary Python Library for ML",
            url="https://github.com/user/ml-lib",
            summary="A lightweight, fast machine learning library written in pure Python.",
            published_at=datetime.now(timezone.utc) - timedelta(days=30),
            author="Developer",
            category="AI",
            tags=["python", "library", "open-source"],
            metadata={"stars": 50000, "forks": 5000},
        ),
        # Low engagement, old
        Article(
            source="blog",
            id="5",
            title="Random Article",
            url="https://example.com/random",
            summary="A random article about unrelated topics.",
            published_at=datetime.now(timezone.utc) - timedelta(days=365),
            author="Unknown",
            category="Other",
            tags=["random"],
            metadata={},
        ),
    ]


class TestAuthorityScore:
    """Tests for authority scoring."""

    def test_high_authority_source(self, sample_articles):
        """ArXiv should have high authority."""
        engine = ImportanceRankingEngine()
        score = engine._calculate_authority_score(
            sample_articles[0], verification_score=0.9, reasoning=[]
        )
        assert score > 8.0

    def test_with_verification_score(self):
        """Verification score should map to authority."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="unknown",
            id="1",
            title="Test",
            url="https://example.com",
            summary="Test article",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        reasoning = []
        score = engine._calculate_authority_score(article, verification_score=0.8, reasoning=reasoning)
        assert score > 7.0

    def test_academic_author(self):
        """Authors with PhD/Prof titles should score higher."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="blog",
            id="1",
            title="Research",
            url="https://example.com",
            summary="Research article",
            published_at=datetime.now(),
            author="Dr. Jane Smith PhD",
            category="AI",
            tags=[],
            metadata={},
        )
        reasoning = []
        score = engine._calculate_authority_score(article, verification_score=None, reasoning=reasoning)
        assert any("Academic" in r for r in reasoning)

    def test_unknown_source_low_authority(self):
        """Unknown source should have baseline authority."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="random-blog",
            id="1",
            title="Article",
            url="https://example.com",
            summary="Random article",
            published_at=datetime.now(),
            author="Someone",
            category="AI",
            tags=[],
            metadata={},
        )
        score = engine._calculate_authority_score(article, verification_score=None, reasoning=[])
        assert 4.0 <= score < 7.0


class TestEngagementScore:
    """Tests for engagement scoring."""

    def test_high_hn_score(self):
        """High HN score should increase engagement."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="hackernews",
            id="1",
            title="Test",
            url="https://example.com",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        engagement = {"score": 1000}
        reasoning = []
        score = engine._calculate_engagement_score(article, engagement, reasoning)
        assert score >= 6.0

    def test_high_github_stars(self):
        """High GitHub stars should increase engagement."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="github",
            id="1",
            title="Test",
            url="https://example.com",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        engagement = {"stars": 10000}
        reasoning = []
        score = engine._calculate_engagement_score(article, engagement, reasoning)
        assert score >= 6.0

    def test_high_views(self):
        """High view count should increase engagement."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="blog",
            id="1",
            title="Test",
            url="https://example.com",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        engagement = {"views": 500000}
        reasoning = []
        score = engine._calculate_engagement_score(article, engagement, reasoning)
        assert score >= 5.0  # Views alone give 3.0 baseline + 2.0 for high views

    def test_no_engagement(self):
        """Article with no engagement should have baseline."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="blog",
            id="1",
            title="Test",
            url="https://example.com",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        score = engine._calculate_engagement_score(article, None, [])
        assert 3.0 <= score <= 5.0


class TestRecencyScore:
    """Tests for recency scoring with decay."""

    def test_today_article(self):
        """Article published today should have maximum recency."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="news",
            id="1",
            title="Today",
            url="https://example.com",
            summary="Today's news",
            published_at=datetime.now(timezone.utc),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        reasoning = []
        score = engine._calculate_recency_score(article, reasoning)
        assert score == 10.0

    def test_week_old_article(self):
        """Week-old article should have good recency."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="news",
            id="1",
            title="Week Old",
            url="https://example.com",
            summary="From a week ago",
            published_at=datetime.now(timezone.utc) - timedelta(days=7),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        reasoning = []
        score = engine._calculate_recency_score(article, reasoning)
        assert 6.0 <= score < 8.0

    def test_month_old_article(self):
        """Month-old article should have moderate recency."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="news",
            id="1",
            title="Month Old",
            url="https://example.com",
            summary="From a month ago",
            published_at=datetime.now(timezone.utc) - timedelta(days=30),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        reasoning = []
        score = engine._calculate_recency_score(article, reasoning)
        assert 3.0 <= score < 7.0  # Adjusted range

    def test_year_old_article(self, sample_articles):
        """Year-old article should have low recency."""
        engine = ImportanceRankingEngine()
        reasoning = []
        score = engine._calculate_recency_score(sample_articles[4], reasoning)  # Random Article is 1 year old
        assert score < 4.0

    def test_no_date(self):
        """Article without date should get baseline."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="news",
            id="1",
            title="No Date",
            url="https://example.com",
            summary="No date",
            published_at=None,
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        score = engine._calculate_recency_score(article, [])
        assert score == 5.0


class TestRelevanceScore:
    """Tests for relevance scoring and interest matching."""

    def test_no_user_interests(self):
        """Without user interests, should get baseline."""
        engine = ImportanceRankingEngine(user_interests=[])
        article = Article(
            source="test",
            id="1",
            title="Machine Learning",
            url="https://example.com",
            summary="ML article",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=["ml"],
            metadata={},
        )
        score, matched = engine._calculate_relevance_score(article, [])
        assert score == 5.0
        assert len(matched) == 0

    def test_tag_match(self):
        """Matching tag should increase relevance."""
        engine = ImportanceRankingEngine(user_interests=["machine-learning"])
        article = Article(
            source="test",
            id="1",
            title="ML Article",
            url="https://example.com",
            summary="About machine learning",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=["machine-learning", "ai"],
            metadata={},
        )
        score, matched = engine._calculate_relevance_score(article, [])
        assert score > 6.0
        assert "machine-learning" in matched

    def test_title_match(self):
        """Matching title should increase relevance."""
        engine = ImportanceRankingEngine(user_interests=["deep learning"])
        article = Article(
            source="test",
            id="1",
            title="Deep Learning Breakthrough",
            url="https://example.com",
            summary="New research",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        score, matched = engine._calculate_relevance_score(article, [])
        assert score > 5.5
        assert any("deep learning" in m.lower() for m in matched)

    def test_content_match(self):
        """Matching in content should increase relevance."""
        engine = ImportanceRankingEngine(user_interests=["transformers"])
        article = Article(
            source="test",
            id="1",
            title="Article",
            url="https://example.com",
            summary="Discussing transformers and attention mechanisms",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        score, matched = engine._calculate_relevance_score(article, [])
        assert score > 5.0

    def test_multiple_interests_match(self):
        """Multiple interest matches should compound."""
        engine = ImportanceRankingEngine(
            user_interests=["machine-learning", "deep-learning", "neural-networks"]
        )
        article = Article(
            source="test",
            id="1",
            title="Deep Learning with Neural Networks",
            url="https://example.com",
            summary="Machine learning research",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=["machine-learning", "deep-learning", "neural-networks"],
            metadata={},
        )
        score, matched = engine._calculate_relevance_score(article, [])
        assert score > 8.0
        assert len(matched) >= 2


class TestTrendScore:
    """Tests for trend detection and velocity."""

    def test_rapidly_trending(self):
        """Rapidly trending article should have high trend score."""
        engine = ImportanceRankingEngine()
        trending_data = {"velocity": 20.0, "trend_direction": "up", "mentions_per_day": 500}
        reasoning = []
        score, trending, velocity = engine._calculate_trend_score(trending_data, reasoning)
        assert score > 8.0
        assert trending is True
        assert velocity == 20.0

    def test_slowly_trending(self):
        """Slowly trending article should have moderate trend score."""
        engine = ImportanceRankingEngine()
        trending_data = {"velocity": 2.0, "trend_direction": "up", "mentions_per_day": 50}
        reasoning = []
        score, trending, velocity = engine._calculate_trend_score(trending_data, reasoning)
        assert 4.0 <= score < 7.0
        assert trending is True

    def test_downtrending(self):
        """Downtrending article should have low trend score."""
        engine = ImportanceRankingEngine()
        trending_data = {"velocity": -5.0, "trend_direction": "down", "mentions_per_day": 10}
        reasoning = []
        score, trending, velocity = engine._calculate_trend_score(trending_data, reasoning)
        assert score < 5.0

    def test_no_trend_data(self):
        """Without trend data, should get baseline."""
        engine = ImportanceRankingEngine()
        score, trending, velocity = engine._calculate_trend_score(None, [])
        assert score == 4.0
        assert trending is False


class TestCitationScore:
    """Tests for citation scoring."""

    def test_highly_cited(self):
        """Highly cited article should have high citation score."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="arxiv",
            id="1",
            title="Classic Paper",
            url="https://example.com",
            summary="Influential research",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={"citations": 500},
        )
        reasoning = []
        score = engine._calculate_citation_score(article, reasoning)
        assert score > 6.0

    def test_well_referenced(self):
        """Well-referenced article should have high citation score."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="blog",
            id="1",
            title="Guide",
            url="https://example.com",
            summary="Reference guide",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={"backlinks": 500},
        )
        reasoning = []
        score = engine._calculate_citation_score(article, reasoning)
        assert score > 5.0

    def test_no_citations(self):
        """Article without citations should have baseline."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="blog",
            id="1",
            title="Article",
            url="https://example.com",
            summary="New article",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        score = engine._calculate_citation_score(article, [])
        assert score == 4.0


class TestRankArticle:
    """Tests for complete article ranking."""

    def test_rank_high_quality_article(self, sample_articles):
        """High quality article should get high importance."""
        engine = ImportanceRankingEngine()
        score = engine.rank_article(
            sample_articles[0],
            verification_score=0.95,
            engagement_metrics={"score": 500},
        )
        assert score.importance_level in [ImportanceLevel.CRITICAL, ImportanceLevel.VERY_HIGH, ImportanceLevel.HIGH]
        assert score.overall_score > 6.0

    def test_rank_old_low_engagement(self, sample_articles):
        """Old article with low engagement should have low importance."""
        engine = ImportanceRankingEngine()
        score = engine.rank_article(sample_articles[1])
        assert score.importance_level in [
            ImportanceLevel.MINIMAL,
            ImportanceLevel.LOW,
            ImportanceLevel.MODERATE,
        ]
        assert score.overall_score < 6.0

    def test_ranking_includes_all_components(self, sample_articles):
        """Ranking should include all component scores."""
        engine = ImportanceRankingEngine()
        score = engine.rank_article(sample_articles[0])
        
        assert 0 <= score.authority_score <= 10
        assert 0 <= score.engagement_score <= 10
        assert 0 <= score.recency_score <= 10
        assert 0 <= score.relevance_score <= 10
        assert 0 <= score.trend_score <= 10
        assert 0 <= score.citation_score <= 10

    def test_importance_level_determination(self):
        """Importance level should map to score ranges."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="test",
            id="1",
            title="Test",
            url="https://example.com",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        
        # Mock high scores to get VERY_HIGH or above
        score = engine.rank_article(
            article,
            verification_score=1.0,
            engagement_metrics={"score": 10000, "stars": 100000},
            trending_data={"velocity": 50, "trend_direction": "up"},
        )
        assert score.overall_score >= 7.5
        assert score.importance_level in [ImportanceLevel.CRITICAL, ImportanceLevel.VERY_HIGH]


class TestBatchRanking:
    """Tests for batch ranking operations."""

    def test_rank_batch(self, sample_articles):
        """Should rank multiple articles."""
        engine = ImportanceRankingEngine()
        scores = engine.rank_batch(sample_articles)
        assert len(scores) == len(sample_articles)
        assert all(isinstance(s, ImportanceScore) for s in scores)

    def test_rank_and_sort(self, sample_articles):
        """Should rank and sort by importance."""
        engine = ImportanceRankingEngine()
        scores = engine.rank_and_sort(sample_articles, descending=True)
        
        # Verify sorting (descending)
        for i in range(len(scores) - 1):
            assert scores[i].overall_score >= scores[i + 1].overall_score

    def test_rank_and_sort_ascending(self, sample_articles):
        """Should sort in ascending order if specified."""
        engine = ImportanceRankingEngine()
        scores = engine.rank_and_sort(sample_articles, descending=False)
        
        # Verify sorting (ascending)
        for i in range(len(scores) - 1):
            assert scores[i].overall_score <= scores[i + 1].overall_score

    def test_filter_by_importance(self, sample_articles):
        """Should filter by minimum importance level."""
        engine = ImportanceRankingEngine()
        filtered, scores = engine.filter_by_importance(
            sample_articles,
            min_importance=ImportanceLevel.HIGH,
        )
        
        assert len(filtered) <= len(sample_articles)
        assert len(scores) == len(sample_articles)


class TestStatistics:
    """Tests for ranking statistics."""

    def test_statistics_structure(self, sample_articles):
        """Statistics should have all required fields."""
        engine = ImportanceRankingEngine()
        scores = engine.rank_batch(sample_articles)
        stats = engine.get_statistics(scores)
        
        assert "total_articles" in stats
        assert "critical" in stats
        assert "very_high" in stats
        assert "high" in stats
        assert "average_score" in stats
        assert "trending_articles" in stats

    def test_statistics_counts_sum(self, sample_articles):
        """Level counts should sum to total."""
        engine = ImportanceRankingEngine()
        scores = engine.rank_batch(sample_articles)
        stats = engine.get_statistics(scores)
        
        total = (
            stats["critical"]
            + stats["very_high"]
            + stats["high"]
            + stats["moderate"]
            + stats["low"]
            + stats["minimal"]
        )
        assert total == stats["total_articles"]

    def test_empty_statistics(self):
        """Statistics for empty list should return zeros."""
        engine = ImportanceRankingEngine()
        stats = engine.get_statistics([])
        assert stats["total_articles"] == 0
        assert stats["average_score"] == 0.0


class TestReportGeneration:
    """Tests for report generation."""

    def test_generate_report(self, sample_articles):
        """Should generate readable report."""
        engine = ImportanceRankingEngine()
        score = engine.rank_article(sample_articles[0])
        report = engine.generate_report(score)
        
        assert isinstance(report, str)
        assert "Importance Level" in report
        assert "Score" in report

    def test_report_includes_reasoning(self, sample_articles):
        """Report should include reasoning."""
        engine = ImportanceRankingEngine(user_interests=["deep-learning"])
        score = engine.rank_article(sample_articles[0])
        report = engine.generate_report(score)
        
        if score.reasoning:
            # Reasoning should be in report
            assert any(r in report for r in score.reasoning[:5])


class TestWeightConfiguration:
    """Tests for weight configuration."""

    def test_custom_weights(self, sample_articles):
        """Should respect custom weight configuration."""
        # High relevance weight
        engine = ImportanceRankingEngine(
            relevance_weight=0.5,
            engagement_weight=0.15,
            recency_weight=0.15,
            source_authority_weight=0.1,
            trend_weight=0.05,
            citation_weight=0.05,
            user_interests=["deep-learning"],
        )
        score = engine.rank_article(sample_articles[0])
        assert isinstance(score, ImportanceScore)

    def test_edge_weights(self):
        """Should handle extreme weight distributions."""
        engine = ImportanceRankingEngine(
            relevance_weight=0.9,
            engagement_weight=0.05,
            recency_weight=0.025,
            source_authority_weight=0.025,
            trend_weight=0.0,
            citation_weight=0.0,
        )
        article = Article(
            source="test",
            id="1",
            title="Test",
            url="https://example.com",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        score = engine.rank_article(article)
        assert isinstance(score, ImportanceScore)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_article_with_minimal_data(self):
        """Should handle article with minimal data."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="test",
            id="1",
            title="T",
            url="https://example.com",
            summary="S",
            published_at=None,
            author="",
            category="",
            tags=[],
            metadata=None,
        )
        score = engine.rank_article(article)
        assert isinstance(score, ImportanceScore)

    def test_very_high_engagement_metrics(self):
        """Should handle very large engagement numbers."""
        engine = ImportanceRankingEngine()
        article = Article(
            source="viral",
            id="1",
            title="Viral Article",
            url="https://example.com",
            summary="Very viral",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        engagement = {"views": 100000000, "score": 50000}
        score = engine.rank_article(article, engagement_metrics=engagement)
        assert score.engagement_score <= 10.0  # Should cap at 10


def test_integration_full_ranking_workflow(sample_articles):
    """Integration test: full ranking workflow."""
    engine = ImportanceRankingEngine(
        user_interests=["machine-learning", "deep-learning", "ai"],
    )

    # Rank batch
    scores = engine.rank_batch(sample_articles)
    assert len(scores) == len(sample_articles)

    # Sort by importance
    sorted_scores = engine.rank_and_sort(sample_articles, descending=True)
    assert sorted_scores[0].overall_score >= sorted_scores[-1].overall_score

    # Get statistics
    stats = engine.get_statistics(scores)
    assert stats["total_articles"] > 0

    # Filter by importance
    filtered, _ = engine.filter_by_importance(
        sample_articles,
        min_importance=ImportanceLevel.MODERATE,
    )
    assert len(filtered) <= len(sample_articles)

    # Generate reports
    for score in scores[:3]:
        report = engine.generate_report(score)
        assert isinstance(report, str)
        assert len(report) > 0
