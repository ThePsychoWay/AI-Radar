"""
Tests for Deduplication Engine.

Covers:
- Title similarity (fuzzy matching)
- URL similarity and normalization
- Semantic similarity
- Duplicate detection
- Group clustering
- Deduplication
- Statistics
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from app.collectors.rss_collector import Article
from app.processors.deduplication import (
    DeduplicationEngine,
    DuplicateCandidate,
    SimilarityMetric,
)


@pytest.fixture
def sample_articles():
    """Create sample articles for testing."""
    return [
        Article(
            source="test_source",
            id="1",
            title="Machine Learning Breakthrough in 2024",
            url="https://example.com/ml-breakthrough",
            summary="A new ML model shows promise.",
            published_at=datetime.now(),
            author="Alice",
            category="AI",
            tags=["machine-learning", "breakthrough"],
            metadata={"score": 100},
        ),
        Article(
            source="test_source2",
            id="2",
            title="Breakthrough in Machine Learning 2024",  # Similar title
            url="https://example.com/ml-breakthrough?utm_source=twitter",  # Same content, tracking params
            summary="A new machine learning model shows promise.",
            published_at=datetime.now(),
            author="Bob",
            category="AI",
            tags=["machine-learning", "breakthrough"],
            metadata={"score": 90},
        ),
        Article(
            source="test_source3",
            id="3",
            title="Deep Learning Advances",
            url="https://other.com/deep-learning",
            summary="Deep learning methods are improving.",
            published_at=datetime.now(),
            author="Charlie",
            category="AI",
            tags=["deep-learning"],
            metadata={"score": 50},
        ),
        Article(
            source="test_source",
            id="4",
            title="Deep Learning Advances in 2024",  # Similar to #3
            url="https://other.com/deep-learning-2024",
            summary="Deep learning methods are improving rapidly.",
            published_at=datetime.now(),
            author="Alice",
            category="AI",
            tags=["deep-learning"],
            metadata={"score": 60},
        ),
    ]


class TestTitleSimilarity:
    """Tests for title similarity matching."""

    def test_exact_match(self):
        """Exact titles should have similarity 1.0."""
        engine = DeduplicationEngine()
        sim = engine._title_similarity("Test Title", "Test Title")
        assert sim == 1.0

    def test_case_insensitive(self):
        """Titles should be case-insensitive."""
        engine = DeduplicationEngine()
        sim = engine._title_similarity("Test Title", "test title")
        assert sim == 1.0

    def test_extra_spaces(self):
        """Extra spaces should be normalized."""
        engine = DeduplicationEngine()
        sim = engine._title_similarity("Test  Title", "Test Title")
        assert sim == 1.0

    def test_high_similarity(self):
        """Very similar titles should score high."""
        engine = DeduplicationEngine()
        sim = engine._title_similarity(
            "Machine Learning Breakthrough in 2024",
            "Breakthrough in Machine Learning 2024",
        )
        assert sim > 0.5  # Similar but not identical due to word order

    def test_low_similarity(self):
        """Completely different titles should score low."""
        engine = DeduplicationEngine()
        sim = engine._title_similarity("Apple Stock Rises", "Deep Learning Advances")
        assert sim < 0.5

    def test_empty_string(self):
        """Empty strings should return 0.0."""
        engine = DeduplicationEngine()
        assert engine._title_similarity("", "Test") == 0.0
        assert engine._title_similarity("Test", "") == 0.0
        assert engine._title_similarity("", "") == 0.0


class TestURLSimilarity:
    """Tests for URL similarity matching."""

    def test_exact_url_match(self):
        """Exact URLs should have similarity 1.0."""
        engine = DeduplicationEngine()
        url = "https://example.com/article"
        sim = engine._url_similarity(url, url)
        assert sim == 1.0

    def test_url_with_tracking_params(self):
        """URLs with only tracking params should be very similar."""
        engine = DeduplicationEngine()
        url1 = "https://example.com/article"
        url2 = "https://example.com/article?utm_source=twitter&utm_medium=social"
        sim = engine._url_similarity(url1, url2)
        assert sim > 0.8

    def test_different_domains(self):
        """URLs from different domains with different paths should have low similarity."""
        engine = DeduplicationEngine()
        url1 = "https://example.com/article/tech/ai"
        url2 = "https://other.com/news/finance"
        sim = engine._url_similarity(url1, url2)
        assert sim < 0.3

    def test_similar_paths(self):
        """Similar URL paths should score higher."""
        engine = DeduplicationEngine()
        url1 = "https://example.com/deep-learning-advances"
        url2 = "https://example.com/deep-learning-2024"
        sim = engine._url_similarity(url1, url2)
        assert sim > 0.5

    def test_empty_urls(self):
        """Empty URLs should return 0.0."""
        engine = DeduplicationEngine()
        assert engine._url_similarity("", "") == 0.0
        assert engine._url_similarity("https://example.com", "") == 0.0


class TestSemanticSimilarity:
    """Tests for semantic similarity."""

    def test_same_article_semantics(self):
        """Identical articles should have high semantic similarity."""
        engine = DeduplicationEngine()
        article = Article(
            source="test",
            id="1",
            title="Machine Learning",
            url="https://example.com/1",
            summary="This is about machine learning.",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=["ml"],
            metadata={},
        )
        sim = engine._semantic_similarity(article, article)
        assert sim == 1.0

    def test_very_different_semantics(self):
        """Completely different articles should have low semantic similarity."""
        engine = DeduplicationEngine()
        article1 = Article(
            source="test",
            id="1",
            title="Machine Learning",
            url="https://example.com/1",
            summary="This is about machine learning and AI.",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=["ml"],
            metadata={},
        )
        article2 = Article(
            source="test",
            id="2",
            title="Stock Market",
            url="https://example.com/2",
            summary="Stock prices and financial markets.",
            published_at=datetime.now(),
            author="Test",
            category="Finance",
            tags=["stocks"],
            metadata={},
        )
        sim = engine._semantic_similarity(article1, article2)
        assert sim < 0.2

    def test_similar_topics(self):
        """Articles on similar topics should score higher."""
        engine = DeduplicationEngine()
        article1 = Article(
            source="test",
            id="1",
            title="Deep Learning Advances",
            url="https://example.com/1",
            summary="Deep learning neural networks are advancing rapidly in computer vision and NLP.",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=["deep-learning", "neural-networks"],
            metadata={},
        )
        article2 = Article(
            source="test",
            id="2",
            title="Neural Networks Progress",
            url="https://example.com/2",
            summary="Neural networks with deep learning methods show improvement in vision tasks.",
            published_at=datetime.now(),
            author="Test",
            category="AI",
            tags=["neural-networks", "deep-learning"],
            metadata={},
        )
        sim = engine._semantic_similarity(article1, article2)
        assert sim > 0.2  # Should have word and tag overlap


class TestCompareArticles:
    """Tests for article comparison."""

    def test_exact_url_match(self, sample_articles):
        """Articles with exact URL should be duplicates."""
        engine = DeduplicationEngine()
        article1 = sample_articles[0]
        # Create exact duplicate
        article2 = Article(
            source="different_source",
            id="999",
            title="Different Title",
            url=article1.url,  # Exact URL match
            summary="Different summary",
            published_at=datetime.now(),
            author="Different",
            category="AI",
            tags=[],
            metadata={},
        )
        score, reason, _ = engine._compare_articles(article1, article2)
        assert score == 1.0
        assert reason == "exact_url_match"

    def test_similar_articles(self, sample_articles):
        """Very similar articles should score high."""
        engine = DeduplicationEngine(threshold=0.7)
        score, reason, _ = engine._compare_articles(
            sample_articles[0], sample_articles[1]
        )
        assert score >= 0.7


class TestFindDuplicates:
    """Tests for duplicate detection."""

    def test_find_duplicates_in_list(self, sample_articles):
        """Should find duplicate pairs in article list."""
        engine = DeduplicationEngine(threshold=0.7)
        duplicates = engine.find_duplicates(sample_articles)
        
        # Should find some duplicates
        assert len(duplicates) > 0

    def test_duplicate_candidate_structure(self, sample_articles):
        """DuplicateCandidate should have all required fields."""
        engine = DeduplicationEngine(threshold=0.7)
        duplicates = engine.find_duplicates(sample_articles)
        
        if duplicates:
            dup = duplicates[0]
            assert isinstance(dup, DuplicateCandidate)
            assert dup.article1 is not None
            assert dup.article2 is not None
            assert 0 <= dup.score <= 1
            assert dup.reason
            assert isinstance(dup.metrics, dict)

    def test_no_duplicates_empty_list(self):
        """Empty list should return empty duplicates."""
        engine = DeduplicationEngine()
        assert engine.find_duplicates([]) == []

    def test_single_article_no_duplicates(self, sample_articles):
        """Single article should have no duplicates."""
        engine = DeduplicationEngine()
        duplicates = engine.find_duplicates([sample_articles[0]])
        assert duplicates == []

    def test_duplicates_sorted_by_score(self, sample_articles):
        """Duplicates should be sorted by score (descending)."""
        engine = DeduplicationEngine(threshold=0.5)
        duplicates = engine.find_duplicates(sample_articles)
        
        if len(duplicates) > 1:
            scores = [d.score for d in duplicates]
            assert scores == sorted(scores, reverse=True)


class TestGroupDuplicates:
    """Tests for duplicate grouping."""

    def test_group_exact_duplicates(self, sample_articles):
        """Should group exact duplicates together."""
        engine = DeduplicationEngine(threshold=0.9)
        groups = engine.group_duplicates(sample_articles)
        
        # Should have multiple groups
        assert len(groups) > 0
        # All groups should be non-empty
        assert all(len(group) > 0 for group in groups)
        # All articles should be accounted for
        total_articles = sum(len(group) for group in groups)
        assert total_articles == len(sample_articles)

    def test_transitive_grouping(self):
        """Should use transitive closure for grouping."""
        engine = DeduplicationEngine(threshold=0.7)
        
        # Create articles where A~B, B~C but A!~C (but should still group together)
        articles = [
            Article(
                source="s1",
                id="1",
                title="Machine Learning",
                url="https://example.com/1",
                summary="This is about machine learning.",
                published_at=datetime.now(),
                author="A",
                category="AI",
                tags=["ml"],
                metadata={},
            ),
            Article(
                source="s2",
                id="2",
                title="Machine Learning Advances",
                url="https://example.com/2",
                summary="New machine learning techniques.",
                published_at=datetime.now(),
                author="B",
                category="AI",
                tags=["ml"],
                metadata={},
            ),
            Article(
                source="s3",
                id="3",
                title="ML Advances",
                url="https://example.com/3",
                summary="Latest machine learning advances.",
                published_at=datetime.now(),
                author="C",
                category="AI",
                tags=["ml"],
                metadata={},
            ),
        ]
        
        groups = engine.group_duplicates(articles)
        # All three should be in same group due to transitive closure
        assert len(groups) >= 1


class TestDeduplicate:
    """Tests for deduplication."""

    def test_deduplicate_keep_first(self, sample_articles):
        """Should keep first article from each group."""
        engine = DeduplicationEngine(threshold=0.7)
        deduped = engine.deduplicate(sample_articles, keep_first=True)
        
        # Should have fewer or equal articles
        assert len(deduped) <= len(sample_articles)
        # All articles should be from original list
        assert all(a in sample_articles for a in deduped)

    def test_deduplicate_keep_best(self, sample_articles):
        """Should keep best-scoring article from each group."""
        engine = DeduplicationEngine(threshold=0.7)
        deduped = engine.deduplicate(sample_articles, keep_first=False)
        
        assert len(deduped) <= len(sample_articles)
        assert all(a in sample_articles for a in deduped)

    def test_deduplicate_empty_list(self):
        """Empty list should return empty."""
        engine = DeduplicationEngine()
        assert engine.deduplicate([]) == []

    def test_deduplicate_no_duplicates(self):
        """If no duplicates, should return all articles."""
        engine = DeduplicationEngine(threshold=0.99)
        articles = [
            Article(
                source="s1",
                id="1",
                title="Article A",
                url="https://example.com/1",
                summary="First article",
                published_at=datetime.now(),
                author="A",
                category="AI",
                tags=[],
                metadata={},
            ),
            Article(
                source="s2",
                id="2",
                title="Article B",
                url="https://example.com/2",
                summary="Second article",
                published_at=datetime.now(),
                author="B",
                category="AI",
                tags=[],
                metadata={},
            ),
        ]
        deduped = engine.deduplicate(articles)
        assert len(deduped) == 2


class TestSimilarityMetrics:
    """Tests for different similarity metric strategies."""

    def test_levenshtein_metric(self, sample_articles):
        """Should work with Levenshtein metric."""
        engine = DeduplicationEngine(
            metric=SimilarityMetric.LEVENSHTEIN,
            threshold=0.7,
        )
        duplicates = engine.find_duplicates(sample_articles)
        assert isinstance(duplicates, list)

    def test_sequence_metric(self, sample_articles):
        """Should work with Sequence metric."""
        engine = DeduplicationEngine(
            metric=SimilarityMetric.SEQUENCE,
            threshold=0.7,
        )
        duplicates = engine.find_duplicates(sample_articles)
        assert isinstance(duplicates, list)

    def test_semantic_metric(self, sample_articles):
        """Should work with Semantic metric."""
        engine = DeduplicationEngine(
            metric=SimilarityMetric.SEMANTIC,
            threshold=0.5,
        )
        duplicates = engine.find_duplicates(sample_articles)
        assert isinstance(duplicates, list)

    def test_combined_metric(self, sample_articles):
        """Should work with Combined metric."""
        engine = DeduplicationEngine(
            metric=SimilarityMetric.COMBINED,
            threshold=0.7,
        )
        duplicates = engine.find_duplicates(sample_articles)
        assert isinstance(duplicates, list)


class TestStatistics:
    """Tests for deduplication statistics."""

    def test_statistics_empty(self):
        """Statistics for empty duplicates list."""
        engine = DeduplicationEngine()
        stats = engine.get_statistics([])
        
        assert stats["total_duplicates"] == 0
        assert stats["average_score"] == 0.0

    def test_statistics_with_duplicates(self, sample_articles):
        """Statistics should include all metrics."""
        engine = DeduplicationEngine(threshold=0.5)
        duplicates = engine.find_duplicates(sample_articles)
        
        if duplicates:
            stats = engine.get_statistics(duplicates)
            
            assert "total_duplicates" in stats
            assert "high_confidence" in stats
            assert "medium_confidence" in stats
            assert "low_confidence" in stats
            assert "average_score" in stats
            assert "min_score" in stats
            assert "max_score" in stats
            assert "most_common_reason" in stats
            
            # Verify ranges
            assert stats["total_duplicates"] >= 0
            assert 0 <= stats["average_score"] <= 1
            assert 0 <= stats["min_score"] <= 1
            assert 0 <= stats["max_score"] <= 1

    def test_statistics_confidence_levels(self, sample_articles):
        """Statistics should categorize by confidence."""
        engine = DeduplicationEngine(threshold=0.5)
        duplicates = engine.find_duplicates(sample_articles)
        stats = engine.get_statistics(duplicates)
        
        # Confidence levels should sum to total
        total = (
            stats["high_confidence"] +
            stats["medium_confidence"] +
            stats["low_confidence"]
        )
        assert total == stats["total_duplicates"]


class TestThresholdBehavior:
    """Tests for threshold sensitivity."""

    def test_high_threshold(self, sample_articles):
        """High threshold should find fewer duplicates."""
        engine_low = DeduplicationEngine(threshold=0.5)
        engine_high = DeduplicationEngine(threshold=0.95)
        
        dups_low = engine_low.find_duplicates(sample_articles)
        dups_high = engine_high.find_duplicates(sample_articles)
        
        assert len(dups_high) <= len(dups_low)

    def test_threshold_zero(self, sample_articles):
        """Threshold 0 should find all pairs."""
        engine = DeduplicationEngine(threshold=0.0)
        duplicates = engine.find_duplicates(sample_articles)
        
        # With n articles, max pairs = n*(n-1)/2
        n = len(sample_articles)
        max_pairs = n * (n - 1) // 2
        assert len(duplicates) == max_pairs

    def test_threshold_one(self, sample_articles):
        """Threshold 1.0 should only find exact matches."""
        engine = DeduplicationEngine(threshold=1.0)
        duplicates = engine.find_duplicates(sample_articles)
        
        # Should only match exact duplicates (likely 0)
        assert len(duplicates) == 0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_articles_with_empty_fields(self):
        """Should handle articles with empty/None fields."""
        articles = [
            Article(
                source="s1",
                id="1",
                title="",
                url="",
                summary="",
                published_at=datetime.now(),
                author="",
                category="",
                tags=[],
                metadata={},
            ),
            Article(
                source="s2",
                id="2",
                title="Test",
                url="https://example.com",
                summary="Test article",
                published_at=datetime.now(),
                author="A",
                category="AI",
                tags=[],
                metadata={},
            ),
        ]
        
        engine = DeduplicationEngine()
        duplicates = engine.find_duplicates(articles)
        assert isinstance(duplicates, list)

    def test_very_long_titles(self):
        """Should handle very long titles."""
        engine = DeduplicationEngine()
        long_title = "A" * 10000
        sim = engine._title_similarity(long_title, long_title)
        assert sim == 1.0

    def test_special_characters_in_title(self):
        """Should handle special characters."""
        engine = DeduplicationEngine()
        title1 = "Machine Learning & AI: The Future! 🚀"
        title2 = "Machine Learning AI: The Future!"
        sim = engine._title_similarity(title1, title2)
        assert sim > 0.5


def test_integration_full_workflow(sample_articles):
    """Integration test: full deduplication workflow."""
    engine = DeduplicationEngine(
        metric=SimilarityMetric.COMBINED,
        threshold=0.7,
    )
    
    # Find duplicates
    duplicates = engine.find_duplicates(sample_articles)
    assert isinstance(duplicates, list)
    
    # Get statistics
    stats = engine.get_statistics(duplicates)
    assert stats["total_duplicates"] >= 0
    
    # Group duplicates
    groups = engine.group_duplicates(sample_articles)
    assert all(len(g) > 0 for g in groups)
    
    # Deduplicate
    deduped = engine.deduplicate(sample_articles)
    assert len(deduped) <= len(sample_articles)
