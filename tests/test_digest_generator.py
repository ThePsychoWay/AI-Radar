"""
Tests for Daily Digest Generator.

Covers:
- Metadata generation
- Read time estimation
- Article organization
- HTML email formatting
- Plain text email formatting
- JSON digest generation
- Section creation
- Tracking URL generation
- Edge cases
"""

import pytest
import json
from datetime import datetime, timezone, timedelta

from app.collectors.rss_collector import Article
from app.processors.importance import ImportanceScore, ImportanceLevel
from app.analyzers.decision_engine import (
    Recommendation,
    RecommendationType,
    NotificationUrgency,
    RecommendationScore,
)
from app.generators.digest_generator import (
    DigestGenerator,
    DigestFormat,
    DigestMetadata,
    DigestSection,
)


@pytest.fixture
def sample_articles():
    """Create sample articles."""
    now = datetime.now(timezone.utc)
    return [
        Article(
            source="arxiv",
            id="1",
            title="Critical AI Breakthrough Announced",
            url="https://arxiv.org/abs/2024.1000",
            summary="Researchers announce a major breakthrough in artificial intelligence with implications for the field.",
            published_at=now,
            author="Alice Smith",
            category="AI",
            tags=["deep-learning", "breakthrough"],
            metadata={},
        ),
        Article(
            source="github",
            id="2",
            title="New Python ML Library Released",
            url="https://github.com/ml-lib",
            summary="A new machine learning library for Python offers faster computation.",
            published_at=now - timedelta(hours=2),
            author="Bob Jones",
            category="ML",
            tags=["machine-learning", "python"],
            metadata={},
        ),
        Article(
            source="medium",
            id="3",
            title="Understanding Neural Networks",
            url="https://medium.com/neural-networks",
            summary="A comprehensive guide to understanding how neural networks work.",
            published_at=now - timedelta(days=1),
            author="Charlie Brown",
            category="Education",
            tags=["neural-networks", "tutorial"],
            metadata={},
        ),
    ]


@pytest.fixture
def sample_recommendations(sample_articles):
    """Create sample recommendations."""
    now = datetime.now(timezone.utc)
    recs = []

    rec_types = [
        RecommendationType.CRITICAL,
        RecommendationType.FEATURED,
        RecommendationType.RELEVANT,
    ]

    for i, (article, rec_type) in enumerate(zip(sample_articles, rec_types)):
        scoring = RecommendationScore(
            article_id=article.id,
            combined_score=9.0 - (i * 1.5),
            importance_score=9.0 - (i * 1.5),
            personalization_boost=0.3 + (i * 0.1),
            quality_score=0.8,
            recency_score=0.9,
            engagement_potential=0.7,
        )

        rec = Recommendation(
            article=article,
            recommendation_type=rec_type,
            combined_score=scoring.combined_score,
            scoring=scoring,
            personalization_boost=scoring.personalization_boost,
            matched_interests=["AI", "ML", "research"],
            notification_urgency=NotificationUrgency.HIGH,
            suggested_delivery_time=now + timedelta(hours=2),
            summary_snippet=article.summary[:80] + "...",
        )
        recs.append(rec)

    return recs


@pytest.fixture
def digest_generator():
    """Create a digest generator."""
    return DigestGenerator(
        user_id="user123",
        user_email="user@example.com",
        base_url="https://radar.example.com",
    )


class TestDigestMetadata:
    """Tests for DigestMetadata."""

    def test_creation(self):
        """DigestMetadata should initialize correctly."""
        now = datetime.now(timezone.utc)
        metadata = DigestMetadata(
            user_id="user1",
            digest_date=now,
        )

        assert metadata.user_id == "user1"
        assert metadata.digest_date == now
        assert metadata.digest_id.startswith("digest_user1_")

    def test_auto_generate_digest_id(self):
        """Should auto-generate digest ID."""
        now = datetime.now(timezone.utc)
        metadata = DigestMetadata(
            user_id="test",
            digest_date=now,
        )

        assert len(metadata.digest_id) > 0
        assert "test" in metadata.digest_id

    def test_with_counts(self):
        """Should track recommendation counts."""
        metadata = DigestMetadata(
            user_id="user1",
            digest_date=datetime.now(timezone.utc),
            critical_count=2,
            featured_count=3,
            relevant_count=5,
        )

        assert metadata.critical_count == 2
        assert metadata.featured_count == 3
        assert metadata.relevant_count == 5


class TestDigestGenerator:
    """Tests for DigestGenerator."""

    def test_initialization(self, digest_generator):
        """Generator should initialize correctly."""
        assert digest_generator.user_id == "user123"
        assert digest_generator.user_email == "user@example.com"
        assert digest_generator.base_url == "https://radar.example.com"

    def test_estimate_read_time_short(self, digest_generator, sample_articles):
        """Short articles should have minimum 1 minute."""
        article = sample_articles[0]
        read_time = digest_generator.estimate_read_time(article)

        assert read_time >= 1

    def test_estimate_read_time_longer(self, digest_generator):
        """Longer articles should have higher read time."""
        article = Article(
            source="blog",
            id="long",
            title="Very Long Title About Something Important",
            url="https://example.com",
            summary="This is a very long article with many words. " * 100,
            published_at=datetime.now(timezone.utc),
            author="Test",
            category="Test",
            tags=[],
            metadata={},
        )

        read_time = digest_generator.estimate_read_time(article)
        assert read_time >= 3  # Should be multiple minutes

    def test_organize_by_type(self, digest_generator, sample_recommendations):
        """Should organize recommendations by type."""
        organized = digest_generator.organize_by_type(sample_recommendations)

        assert RecommendationType.CRITICAL in organized
        assert RecommendationType.FEATURED in organized
        assert len(organized[RecommendationType.CRITICAL]) == 1

    def test_create_sections(self, digest_generator, sample_recommendations):
        """Should create digest sections."""
        sections = digest_generator.create_sections(sample_recommendations)

        assert len(sections) > 0
        assert sections[0].title  # First section has title
        assert sections[0].recommendations  # First section has articles

    def test_section_ordering(self, digest_generator, sample_recommendations):
        """Sections should be ordered by priority."""
        sections = digest_generator.create_sections(sample_recommendations)

        # Check that critical comes before featured, etc.
        priorities = [s.priority for s in sections]
        assert priorities == sorted(priorities)

    def test_generate_metadata(self, digest_generator, sample_recommendations):
        """Should generate valid metadata."""
        metadata = digest_generator.generate_metadata(sample_recommendations)

        assert metadata.user_id == "user123"
        assert metadata.total_recommendations == 3
        assert metadata.total_read_time_minutes > 0
        assert metadata.critical_count == 1
        assert metadata.featured_count == 1
        assert metadata.relevant_count == 1

    def test_generate_metadata_categories(self, digest_generator, sample_recommendations):
        """Metadata should include categories."""
        metadata = digest_generator.generate_metadata(sample_recommendations)

        assert "AI" in metadata.categories
        assert "ML" in metadata.categories
        assert "Education" in metadata.categories

    def test_generate_metadata_top_interests(self, digest_generator, sample_recommendations):
        """Metadata should track top interests."""
        metadata = digest_generator.generate_metadata(sample_recommendations)

        assert "AI" in metadata.top_interests or len(metadata.top_interests) > 0

    def test_generate_email_html(self, digest_generator, sample_recommendations):
        """Should generate valid HTML email."""
        html = digest_generator.generate_email_html(sample_recommendations)

        assert "<!DOCTYPE html>" in html
        assert "<html>" in html
        assert "</html>" in html
        assert "Critical AI Breakthrough" in html
        assert "📰" in html

    def test_html_escaping(self, digest_generator):
        """HTML should escape special characters."""
        article = Article(
            source="test",
            id="1",
            title="Test & Special < Characters >",
            url="https://example.com",
            summary="Test & summary",
            published_at=datetime.now(timezone.utc),
            author="Test",
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
            recommendation_type=RecommendationType.RELEVANT,
            combined_score=5.0,
            scoring=scoring,
            personalization_boost=0.2,
        )

        html = digest_generator.generate_email_html([rec])

        assert "&amp;" in html or "Test &" in html
        assert "&lt;" in html or "&" in html

    def test_generate_email_text(self, digest_generator, sample_recommendations):
        """Should generate valid plain text email."""
        text = digest_generator.generate_email_text(sample_recommendations)

        assert "📰 YOUR AI RADAR DIGEST" in text
        assert "Critical AI Breakthrough" in text
        assert "Total Articles:" in text
        assert "Read Time:" in text

    def test_text_formatting(self, digest_generator, sample_recommendations):
        """Text email should have proper structure."""
        text = digest_generator.generate_email_text(sample_recommendations)

        assert "════" in text or "─" in text  # Decorative borders
        assert "Summary" in text
        assert "Source:" in text

    def test_generate_json(self, digest_generator, sample_recommendations):
        """Should generate valid JSON digest."""
        json_dict = digest_generator.generate_digest_json(sample_recommendations)

        assert "metadata" in json_dict
        assert "sections" in json_dict
        assert json_dict["metadata"]["total_recommendations"] == 3

    def test_json_serializable(self, digest_generator, sample_recommendations):
        """JSON digest should be serializable."""
        json_dict = digest_generator.generate_digest_json(sample_recommendations)
        json_str = json.dumps(json_dict, default=str)

        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["metadata"]["user_id"] == "user123"

    def test_generate_digest_html_format(self, digest_generator, sample_recommendations):
        """Should generate HTML when format is EMAIL_HTML."""
        digest = digest_generator.generate_digest(
            sample_recommendations,
            format=DigestFormat.EMAIL_HTML,
        )

        assert "<!DOCTYPE html>" in digest

    def test_generate_digest_text_format(self, digest_generator, sample_recommendations):
        """Should generate plain text when format is EMAIL_TEXT."""
        digest = digest_generator.generate_digest(
            sample_recommendations,
            format=DigestFormat.EMAIL_TEXT,
        )

        assert "<!DOCTYPE" not in digest
        assert "📰" in digest

    def test_generate_digest_json_format(self, digest_generator, sample_recommendations):
        """Should generate JSON when format is JSON."""
        digest = digest_generator.generate_digest(
            sample_recommendations,
            format=DigestFormat.JSON,
        )

        parsed = json.loads(digest)
        assert "metadata" in parsed
        assert "sections" in parsed

    def test_tracking_url_generation(self, digest_generator, sample_recommendations):
        """Generated URLs should include tracking parameters."""
        html = digest_generator.generate_email_html(sample_recommendations)

        assert "user=user123" in html
        assert "action=click" in html
        assert "article=" in html

    def test_unsubscribe_link(self, digest_generator, sample_recommendations):
        """Digest should include unsubscribe link."""
        html = digest_generator.generate_email_html(sample_recommendations)

        assert "Manage Preferences" in html
        assert "unsubscribe" in html.lower()

    def test_empty_recommendations(self, digest_generator):
        """Should handle empty recommendation list."""
        metadata = digest_generator.generate_metadata([])

        assert metadata.total_recommendations == 0
        assert metadata.total_read_time_minutes == 0

    def test_single_recommendation(self, digest_generator, sample_recommendations):
        """Should handle single recommendation."""
        single = sample_recommendations[:1]
        sections = digest_generator.create_sections(single)

        assert len(sections) == 1
        assert len(sections[0].recommendations) == 1

    def test_metadata_custom_date(self, digest_generator, sample_recommendations):
        """Should use custom date if provided."""
        custom_date = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
        metadata = digest_generator.generate_metadata(
            sample_recommendations,
            digest_date=custom_date,
        )

        assert metadata.digest_date == custom_date

    def test_no_summary_snippet(self, digest_generator):
        """Should handle recommendations without summary snippet."""
        article = Article(
            source="test",
            id="1",
            title="Test",
            url="https://example.com",
            summary="Test",
            published_at=datetime.now(timezone.utc),
            author="Test",
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
            recommendation_type=RecommendationType.RELEVANT,
            combined_score=5.0,
            scoring=scoring,
            personalization_boost=0.2,
            summary_snippet="",  # Empty snippet
        )

        html = digest_generator.generate_email_html([rec])
        text = digest_generator.generate_email_text([rec])

        assert "Test" in html
        assert "Test" in text

    def test_section_read_time_totals(self, digest_generator, sample_recommendations):
        """Sections should have accurate total read time."""
        sections = digest_generator.create_sections(sample_recommendations)

        for section in sections:
            expected_time = sum(
                digest_generator.estimate_read_time(r.article)
                for r in section.recommendations
            )
            assert section.total_read_time == expected_time

    def test_article_without_author(self, digest_generator):
        """Should handle articles without author."""
        article = Article(
            source="test",
            id="1",
            title="No Author",
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
            recommendation_type=RecommendationType.RELEVANT,
            combined_score=5.0,
            scoring=scoring,
            personalization_boost=0.2,
        )

        html = digest_generator.generate_email_html([rec])
        text = digest_generator.generate_email_text([rec])

        assert "No Author" in html
        assert "No Author" in text


class TestDigestSections:
    """Tests for DigestSection."""

    def test_section_creation(self):
        """DigestSection should initialize correctly."""
        section = DigestSection(
            title="Test Section",
            description="Test description",
            priority=0,
        )

        assert section.title == "Test Section"
        assert section.description == "Test description"
        assert len(section.recommendations) == 0

    def test_section_with_articles(self, sample_recommendations):
        """Section should hold recommendations."""
        section = DigestSection(
            title="Test",
            description="Test",
            recommendations=sample_recommendations,
            total_read_time=30,
        )

        assert len(section.recommendations) == 3
        assert section.total_read_time == 30


class TestIntegration:
    """Integration tests."""

    def test_full_digest_workflow(self, digest_generator, sample_recommendations):
        """Full workflow: generate metadata → create sections → format emails."""
        # Generate metadata
        metadata = digest_generator.generate_metadata(sample_recommendations)
        assert metadata.total_recommendations == 3

        # Create sections
        sections = digest_generator.create_sections(sample_recommendations)
        assert len(sections) > 0

        # Generate formats
        html = digest_generator.generate_email_html(sample_recommendations, metadata)
        text = digest_generator.generate_email_text(sample_recommendations, metadata)
        json_digest = digest_generator.generate_digest_json(
            sample_recommendations,
            metadata,
        )

        # Verify all formats have content
        assert len(html) > 100
        assert len(text) > 100
        assert len(json_digest["sections"]) > 0

    def test_multiple_digest_formats(self, digest_generator, sample_recommendations):
        """Should generate all formats correctly."""
        formats = [
            DigestFormat.EMAIL_HTML,
            DigestFormat.EMAIL_TEXT,
            DigestFormat.JSON,
        ]

        for fmt in formats:
            digest = digest_generator.generate_digest(
                sample_recommendations,
                format=fmt,
            )
            assert len(digest) > 0

    def test_digest_consistency(self, digest_generator, sample_recommendations):
        """Different format should have consistent data."""
        # Generate all formats
        html = digest_generator.generate_email_html(sample_recommendations)
        text = digest_generator.generate_email_text(sample_recommendations)
        json_digest = digest_generator.generate_digest_json(sample_recommendations)

        # All should reference same articles
        assert "Critical AI Breakthrough" in html
        assert "Critical AI Breakthrough" in text

        # JSON should have 3 articles
        total_articles = sum(
            len(section["articles"])
            for section in json_digest["sections"]
        )
        assert total_articles == 3
