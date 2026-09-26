"""
Tests for Verification Engine.

Covers:
- Completeness checking
- Content quality assessment
- Freshness evaluation
- Source reliability assessment
- URL validity checking
- Duplicate risk calculation
- Batch verification
- Statistics generation
- Quality filtering
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.collectors.rss_collector import Article
from app.processors.verification import (
    VerificationEngine,
    VerificationScore,
    QualityLevel,
    SourceReliability,
)


@pytest.fixture
def sample_articles():
    """Create sample articles for testing."""
    return [
        # High quality article
        Article(
            source="arxiv",
            id="1",
            title="Machine Learning Breakthrough: New Algorithm Shows Promise",
            url="https://arxiv.org/abs/2024.01234",
            summary="This paper presents a novel deep learning approach that achieves state-of-the-art results on multiple benchmarks. The methodology combines transformer architectures with novel loss functions.",
            published_at=datetime.now(timezone.utc),
            author="Dr. Alice Smith",
            category="AI",
            tags=["machine-learning", "deep-learning"],
            metadata={"score": 100},
        ),
        # Incomplete article
        Article(
            source="blog",
            id="2",
            title="AI",
            url="",
            summary="",
            published_at=None,
            author="",
            category="",
            tags=[],
            metadata={},
        ),
        # Old article
        Article(
            source="news",
            id="3",
            title="2020 AI Predictions Were Right",
            url="https://example.com/old-article",
            summary="Looking back at our 2020 predictions, many of them came true.",
            published_at=datetime.now(timezone.utc) - timedelta(days=365),
            author="Bob",
            category="AI",
            tags=["review"],
            metadata={"score": 50},
        ),
        # Unknown source
        Article(
            source="random-blog",
            id="4",
            title="Amazing AI Discovery You Won't Believe",
            url="https://random-hash-123456.tk/ai-discovery",
            summary="Revolutionary AI found that will change everything forever.",
            published_at=datetime.now(timezone.utc),
            author="Unknown",
            category="AI",
            tags=[],
            metadata={},
        ),
        # Spam-like article
        Article(
            source="spam-site",
            id="5",
            title="Click here to earn money with AI now!",
            url="https://make-money-fast.ru/ai",
            summary="Make $5000/day with our AI system. Viagra and casino bonuses included!",
            published_at=datetime.now(timezone.utc),
            author="Spammer",
            category="AI",
            tags=[],
            metadata={},
        ),
    ]


class TestCompletenessCheck:
    """Tests for completeness assessment."""

    def test_complete_article(self, sample_articles):
        """Article with all fields should have high completeness."""
        engine = VerificationEngine()
        score = engine._check_completeness(sample_articles[0], [])
        assert score == 1.0

    def test_missing_title(self):
        """Missing title should reduce completeness."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="",
            url="https://example.com",
            summary="Test summary",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        issues = []
        score = engine._check_completeness(article, issues)
        assert score < 1.0
        assert any("title" in str(i).lower() for i in issues)

    def test_missing_url(self):
        """Missing URL should reduce completeness."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Test Title",
            url="",
            summary="Test summary",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        issues = []
        score = engine._check_completeness(article, issues)
        assert score < 1.0
        assert any("url" in str(i).lower() for i in issues)

    def test_missing_summary(self):
        """Missing summary should reduce completeness."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Test Title",
            url="https://example.com",
            summary="",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        issues = []
        score = engine._check_completeness(article, issues)
        assert score < 1.0

    def test_short_title(self):
        """Very short title should be flagged."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="AI",
            url="https://example.com",
            summary="Test summary content here",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        issues = []
        score = engine._check_completeness(article, issues)
        assert score < 1.0


class TestContentQuality:
    """Tests for content quality assessment."""

    def test_good_content_quality(self, sample_articles):
        """Well-written article should have high content quality."""
        engine = VerificationEngine()
        issues = []
        warnings = []
        score = engine._check_content_quality(sample_articles[0], issues, warnings)
        assert score > 0.7

    def test_spam_detection(self):
        """Spam patterns should be detected."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Make $5000 a day with Viagra",
            url="https://example.com",
            summary="Earn money from casino gambling now!",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        issues = []
        warnings = []
        score = engine._check_content_quality(article, issues, warnings)
        assert score < 0.6
        assert any("spam" in str(i).lower() for i in issues)

    def test_very_short_content(self):
        """Very short content should be flagged."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Title",
            url="https://example.com",
            summary="Short",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        issues = []
        warnings = []
        score = engine._check_content_quality(article, issues, warnings)
        assert score < 1.0

    def test_very_long_title(self):
        """Very long title should warn but pass."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="A" * 250,
            url="https://example.com",
            summary="Test summary with sufficient length to pass quality checks",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        issues = []
        warnings = []
        score = engine._check_content_quality(article, issues, warnings)
        assert len(warnings) > 0


class TestFreshnessCheck:
    """Tests for freshness assessment."""

    def test_very_fresh_article(self):
        """Today's article should be very fresh."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Today's News",
            url="https://example.com",
            summary="Published today",
            published_at=datetime.now(timezone.utc),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_freshness(article, warnings)
        assert score >= 0.95

    def test_week_old_article(self):
        """Week-old article should still be fresh."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Week Old Article",
            url="https://example.com",
            summary="Published a week ago",
            published_at=datetime.now(timezone.utc) - timedelta(days=7),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_freshness(article, warnings)
        assert 0.8 <= score < 1.0

    def test_month_old_article(self):
        """Month-old article should be moderately fresh."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Month Old Article",
            url="https://example.com",
            summary="Published a month ago",
            published_at=datetime.now(timezone.utc) - timedelta(days=30),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_freshness(article, warnings)
        assert 0.4 <= score < 0.8

    def test_very_old_article(self, sample_articles):
        """Year-old article should be stale."""
        engine = VerificationEngine()
        warnings = []
        score = engine._check_freshness(sample_articles[2], warnings)
        assert score < 0.4
        assert any("old" in str(w).lower() for w in warnings)

    def test_future_article(self):
        """Future-dated article should trigger warning."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Future Article",
            url="https://example.com",
            summary="Not yet published",
            published_at=datetime.now(timezone.utc) + timedelta(days=1),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_freshness(article, warnings)
        assert any("future" in str(w).lower() for w in warnings)

    def test_no_publication_date(self):
        """Article without date should get moderate score."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="No Date Article",
            url="https://example.com",
            summary="Unknown publication date",
            published_at=None,
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_freshness(article, warnings)
        assert score == 0.5


class TestSourceReliability:
    """Tests for source reliability assessment."""

    def test_highly_trusted_source(self):
        """ArXiv should be highly trusted."""
        engine = VerificationEngine()
        article = Article(
            source="arxiv",
            id="1",
            title="Research Paper",
            url="https://arxiv.org/abs/2024.01234",
            summary="Academic research paper",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score, trust_level = engine._assess_source_reliability(article, warnings)
        assert score >= 0.9
        assert trust_level == SourceReliability.HIGHLY_TRUSTED

    def test_trusted_source(self):
        """GitHub should be trusted."""
        engine = VerificationEngine()
        article = Article(
            source="github",
            id="1",
            title="Open Source Project",
            url="https://github.com/user/repo",
            summary="GitHub project",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score, trust_level = engine._assess_source_reliability(article, warnings)
        assert score >= 0.8
        assert trust_level == SourceReliability.TRUSTED

    def test_community_source(self):
        """HackerNews should be moderate trust."""
        engine = VerificationEngine()
        article = Article(
            source="hackernews",
            id="1",
            title="Discussion Topic",
            url="https://news.ycombinator.com/item?id=12345",
            summary="HN discussion",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score, trust_level = engine._assess_source_reliability(article, warnings)
        assert 0.6 <= score < 0.8
        assert trust_level == SourceReliability.MODERATE

    def test_suspicious_domain(self):
        """Random hash domain should be suspicious."""
        engine = VerificationEngine()
        article = Article(
            source="unknown",
            id="1",
            title="Article",
            url="https://random-hash-123456.tk/article",
            summary="Suspicious source",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score, trust_level = engine._assess_source_reliability(article, warnings)
        assert score < 0.3
        assert trust_level == SourceReliability.SUSPICIOUS
        assert any("suspicious" in str(w).lower() for w in warnings)

    def test_no_url_reliability(self):
        """Article without URL should have low reliability."""
        engine = VerificationEngine()
        article = Article(
            source="unknown",
            id="1",
            title="Article",
            url="",
            summary="No URL",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score, trust_level = engine._assess_source_reliability(article, warnings)
        assert score < 0.5
        assert trust_level == SourceReliability.UNVERIFIED


class TestURLValidity:
    """Tests for URL validity checking."""

    def test_valid_url(self):
        """Valid HTTPS URL should pass."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Article",
            url="https://example.com/path/to/article",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_url_validity(article, warnings)
        assert score > 0.8

    def test_missing_scheme(self):
        """URL without http/https should warn."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Article",
            url="example.com/article",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_url_validity(article, warnings)
        assert score < 0.8
        assert any("scheme" in str(w).lower() for w in warnings)

    def test_redirect_url(self):
        """Redirect URLs should warn."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Article",
            url="https://redirect.example.com/r?target=real-url",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_url_validity(article, warnings)
        assert score < 0.9
        assert any("redirect" in str(w).lower() for w in warnings)

    def test_empty_url(self):
        """Empty URL should get zero score."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Article",
            url="",
            summary="Test",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        warnings = []
        score = engine._check_url_validity(article, warnings)
        assert score == 0.0


class TestDuplicateRisk:
    """Tests for duplicate risk calculation."""

    def test_low_duplicate_risk(self, sample_articles):
        """Well-formed article should have low duplicate risk."""
        engine = VerificationEngine()
        risk = engine._calculate_duplicate_risk(sample_articles[0])
        assert risk < 0.3

    def test_generic_title_increases_risk(self):
        """Generic title should increase duplicate risk."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Update: New Features",
            url="https://example.com",
            summary="We have new features" * 10,
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        risk = engine._calculate_duplicate_risk(article)
        assert risk > 0.1

    def test_short_summary_increases_risk(self):
        """Very short summary should increase risk."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Test Article Title",
            url="https://example.com",
            summary="Brief",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        risk = engine._calculate_duplicate_risk(article)
        assert risk > 0.1


class TestVerifyArticle:
    """Tests for complete article verification."""

    def test_verify_high_quality_article(self, sample_articles):
        """High quality article should get EXCELLENT or GOOD rating."""
        engine = VerificationEngine()
        score = engine.verify_article(sample_articles[0])
        assert score.quality_level in [QualityLevel.EXCELLENT, QualityLevel.GOOD]
        assert score.overall_score > 0.7

    def test_verify_incomplete_article(self, sample_articles):
        """Incomplete article should get POOR or REJECTED rating."""
        engine = VerificationEngine()
        score = engine.verify_article(sample_articles[1])
        assert score.quality_level in [QualityLevel.POOR, QualityLevel.REJECTED]
        assert score.overall_score < 0.5

    def test_verify_spam_article(self, sample_articles):
        """Spam article should be low quality (ACCEPTABLE or below)."""
        engine = VerificationEngine()
        score = engine.verify_article(sample_articles[4])
        assert score.quality_level in [QualityLevel.ACCEPTABLE, QualityLevel.POOR, QualityLevel.REJECTED]
        assert score.overall_score < 0.7  # Below GOOD threshold
        assert any("spam" in str(i).lower() for i in score.issues)

    def test_verification_score_structure(self, sample_articles):
        """Verification score should have all required fields."""
        engine = VerificationEngine()
        score = engine.verify_article(sample_articles[0])

        assert isinstance(score, VerificationScore)
        assert score.article is not None
        assert 0 <= score.overall_score <= 1
        assert 0 <= score.completeness_score <= 1
        assert 0 <= score.content_quality_score <= 1
        assert 0 <= score.freshness_score <= 1
        assert 0 <= score.source_reliability_score <= 1
        assert 0 <= score.url_validity_score <= 1
        assert 0 <= score.duplicate_risk_score <= 1
        assert isinstance(score.issues, list)
        assert isinstance(score.warnings, list)


class TestBatchVerification:
    """Tests for batch verification."""

    def test_verify_batch(self, sample_articles):
        """Should verify multiple articles."""
        engine = VerificationEngine()
        scores = engine.verify_batch(sample_articles)
        assert len(scores) == len(sample_articles)
        assert all(isinstance(s, VerificationScore) for s in scores)

    def test_filter_by_quality(self, sample_articles):
        """Should filter articles by quality threshold."""
        engine = VerificationEngine(min_quality_threshold=0.6)
        passing, scores = engine.filter_by_quality(sample_articles, min_quality=0.6)
        
        assert len(passing) <= len(sample_articles)
        assert len(scores) == len(sample_articles)
        assert all(
            sample_articles.index(a) in [sample_articles.index(s.article) for s in scores if s.overall_score >= 0.6]
            for a in passing
        )


class TestStatistics:
    """Tests for verification statistics."""

    def test_statistics_structure(self, sample_articles):
        """Statistics should include all expected fields."""
        engine = VerificationEngine()
        scores = engine.verify_batch(sample_articles)
        stats = engine.get_statistics(scores)

        assert "total_articles" in stats
        assert "excellent" in stats
        assert "good" in stats
        assert "acceptable" in stats
        assert "poor" in stats
        assert "rejected" in stats
        assert "average_score" in stats
        assert "source_reliability_breakdown" in stats

    def test_statistics_counts(self, sample_articles):
        """Statistics counts should sum to total."""
        engine = VerificationEngine()
        scores = engine.verify_batch(sample_articles)
        stats = engine.get_statistics(scores)

        total = (
            stats["excellent"]
            + stats["good"]
            + stats["acceptable"]
            + stats["poor"]
            + stats["rejected"]
        )
        assert total == stats["total_articles"]

    def test_empty_statistics(self):
        """Statistics for empty list should return zeros."""
        engine = VerificationEngine()
        stats = engine.get_statistics([])
        assert stats["total_articles"] == 0
        assert stats["average_score"] == 0.0


class TestReportGeneration:
    """Tests for report generation."""

    def test_generate_report(self, sample_articles):
        """Should generate readable report."""
        engine = VerificationEngine()
        score = engine.verify_article(sample_articles[0])
        report = engine.generate_report(score)

        assert isinstance(report, str)
        assert "Quality Level" in report
        assert "Score" in report
        assert sample_articles[0].title[:60] in report

    def test_report_with_issues(self, sample_articles):
        """Report should include issues."""
        engine = VerificationEngine()
        score = engine.verify_article(sample_articles[1])  # Incomplete
        report = engine.generate_report(score)

        assert len(score.issues) > 0


class TestQualityThreshold:
    """Tests for quality threshold behavior."""

    def test_high_threshold(self, sample_articles):
        """High threshold should reject more articles."""
        engine_low = VerificationEngine(min_quality_threshold=0.3)
        engine_high = VerificationEngine(min_quality_threshold=0.8)

        low_passing, _ = engine_low.filter_by_quality(sample_articles, min_quality=0.3)
        high_passing, _ = engine_high.filter_by_quality(sample_articles, min_quality=0.8)

        assert len(high_passing) <= len(low_passing)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_article_with_none_values(self):
        """Should handle None values gracefully."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title=None,
            url=None,
            summary=None,
            published_at=None,
            author=None,
            category=None,
            tags=None,
            metadata=None,
        )
        # Should not crash and should return low quality
        score = engine.verify_article(article)
        assert isinstance(score, VerificationScore)
        assert score.quality_level in [QualityLevel.POOR, QualityLevel.REJECTED]
        assert score.overall_score < 0.5

    def test_very_long_content(self):
        """Should handle very long content."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Long Title Article",
            url="https://example.com",
            summary="A" * 100000,
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        score = engine.verify_article(article)
        assert isinstance(score, VerificationScore)

    def test_special_characters_in_content(self):
        """Should handle special characters."""
        engine = VerificationEngine()
        article = Article(
            source="test",
            id="1",
            title="Article with émojis 🚀 and spëcial çhars",
            url="https://example.com",
            summary="Content with émojis 🎉 and spëcial chars",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=[],
            metadata={},
        )
        score = engine.verify_article(article)
        assert isinstance(score, VerificationScore)


def test_integration_full_workflow(sample_articles):
    """Integration test: full verification workflow."""
    engine = VerificationEngine(
        min_quality_threshold=0.5,
        freshness_days=30,
    )

    # Verify batch
    scores = engine.verify_batch(sample_articles)
    assert len(scores) == len(sample_articles)

    # Get statistics
    stats = engine.get_statistics(scores)
    assert stats["total_articles"] > 0

    # Filter by quality
    passing, _ = engine.filter_by_quality(sample_articles, min_quality=0.6)
    assert len(passing) <= len(sample_articles)

    # Generate reports
    for score in scores[:3]:
        report = engine.generate_report(score)
        assert isinstance(report, str)
        assert len(report) > 0
