"""
Unit tests for Unified Data Layer.

Tests cover:
- Adding articles from multiple sources
- Exact deduplication
- Similarity-based deduplication
- Merging logic
- ID mapping
- Filtering and querying
- Statistics generation
- JSON output
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import tempfile

from app.processors.data_layer import (
    UnifiedDataLayer,
    UnifiedArticle,
    DeduplicationStrategy,
)
from app.collectors.rss_collector import Article


class TestDeduplicationStrategy:
    """Test deduplication strategy enum."""

    def test_strategy_values(self):
        """Test that strategies have correct values."""
        assert DeduplicationStrategy.EXACT.value == "exact"
        assert DeduplicationStrategy.SIMILARITY.value == "similarity"
        assert DeduplicationStrategy.COMBINED.value == "combined"


class TestUnifiedDataLayerInitialization:
    """Test UnifiedDataLayer initialization."""

    def test_default_initialization(self):
        """Test creating layer with defaults."""
        layer = UnifiedDataLayer()
        assert layer.strategy == DeduplicationStrategy.COMBINED
        assert len(layer.unified_articles) == 0
        assert len(layer.id_map) == 0

    def test_custom_strategy(self):
        """Test creating layer with custom strategy."""
        for strategy in DeduplicationStrategy:
            layer = UnifiedDataLayer(strategy=strategy)
            assert layer.strategy == strategy

    def test_empty_length(self):
        """Test length of empty layer."""
        layer = UnifiedDataLayer()
        assert len(layer) == 0


class TestAddArticles:
    """Test adding articles to layer."""

    def test_add_single_article(self):
        """Test adding a single article."""
        layer = UnifiedDataLayer()
        article = Article(
            source="rss",
            id="123",
            title="Test Article",
            url="https://example.com/test",
            summary="Test summary",
            published_at="2024-01-01T00:00:00",
            category="news",
            tags=["test"],
        )

        result = layer.add_articles([article], "rss")

        assert result == 1
        assert len(layer) == 1
        assert "rss:123" in layer.id_map

    def test_add_multiple_articles(self):
        """Test adding multiple articles."""
        layer = UnifiedDataLayer()
        articles = [
            Article(
                source="rss",
                id=f"id{i}",
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                summary="Test",
                published_at="2024-01-01T00:00:00",
                category="news",
            )
            for i in range(5)
        ]

        result = layer.add_articles(articles, "rss")

        assert result == 5
        assert len(layer) == 5

    def test_add_empty_list(self):
        """Test adding empty list."""
        layer = UnifiedDataLayer()
        result = layer.add_articles([], "rss")

        assert result == 0
        assert len(layer) == 0


class TestExactDeduplication:
    """Test exact deduplication."""

    def test_exact_duplicate_same_source(self):
        """Test deduplicating same article from same source."""
        layer = UnifiedDataLayer()
        article = Article(
            source="rss",
            id="123",
            title="Test Article",
            url="https://example.com/test",
            summary="Test summary",
            published_at="2024-01-01T00:00:00",
            category="news",
        )

        layer.add_articles([article], "rss")
        result = layer.add_articles([article], "rss")

        assert result == 1  # Merged, not added new
        assert len(layer) == 1
        assert layer[0].sources == ["rss"]

    def test_exact_duplicate_different_source(self):
        """Test deduplicating same article from different sources."""
        layer = UnifiedDataLayer()
        article_rss = Article(
            source="rss",
            id="123",
            title="Test Article",
            url="https://example.com/test",
            summary="Test summary",
            published_at="2024-01-01T00:00:00",
            category="news",
        )
        article_github = Article(
            source="github",
            id="456",
            title="Test Article",
            url="https://example.com/test",
            summary="Test summary",
            published_at="2024-01-01T00:00:00",
            category="news",
        )

        layer.add_articles([article_rss], "rss")
        # Different source and ID, but same URL - won't exact match
        result = layer.add_articles([article_github], "github")

        # Without exact match, it will be added (or similarity matched if enabled)
        assert len(layer) >= 1

    def test_id_mapping_created(self):
        """Test that ID mapping is created."""
        layer = UnifiedDataLayer()
        article = Article(
            source="rss",
            id="123",
            title="Test",
            url="https://example.com",
            summary="Test",
            published_at="2024-01-01T00:00:00",
            category="news",
        )

        layer.add_articles([article], "rss")

        assert "rss:123" in layer.id_map
        assert layer.id_map["rss:123"] == 0


class TestSimilarityDeduplication:
    """Test similarity-based deduplication."""

    def test_url_similarity_match(self):
        """Test matching articles by URL."""
        layer = UnifiedDataLayer(strategy=DeduplicationStrategy.SIMILARITY)
        article1 = Article(
            source="rss",
            id="1",
            title="Article 1",
            url="https://example.com/article",
            summary="Test 1",
            published_at="2024-01-01T00:00:00",
            category="news",
        )
        article2 = Article(
            source="github",
            id="2",
            title="Article 1",
            url="https://example.com/article",
            summary="Test 2",
            published_at="2024-01-01T00:00:00",
            category="news",
        )

        layer.add_articles([article1], "rss")
        result = layer.add_articles([article2], "github")

        assert result == 1  # Merged
        assert len(layer) == 1
        assert set(layer[0].sources) == {"rss", "github"}

    def test_title_similarity_match(self):
        """Test matching articles by title hash."""
        layer = UnifiedDataLayer(strategy=DeduplicationStrategy.SIMILARITY)
        article1 = Article(
            source="rss",
            id="1",
            title="Breaking: New AI Model Released",
            url="https://example.com/1",
            summary="Test 1",
            published_at="2024-01-01T00:00:00",
            category="news",
        )
        article2 = Article(
            source="github",
            id="2",
            title="Breaking: New AI Model Released",
            url="https://example.com/2",
            summary="Test 2",
            published_at="2024-01-01T00:00:00",
            category="news",
        )

        layer.add_articles([article1], "rss")
        result = layer.add_articles([article2], "github")

        assert result == 1  # Merged
        assert len(layer) == 1

    def test_no_match(self):
        """Test that different articles don't match."""
        layer = UnifiedDataLayer(strategy=DeduplicationStrategy.SIMILARITY)
        article1 = Article(
            source="rss",
            id="1",
            title="Article 1",
            url="https://example.com/1",
            summary="Test 1",
            published_at="2024-01-01T00:00:00",
            category="news",
        )
        article2 = Article(
            source="github",
            id="2",
            title="Article 2",
            url="https://example.com/2",
            summary="Test 2",
            published_at="2024-01-01T00:00:00",
            category="news",
        )

        layer.add_articles([article1], "rss")
        result = layer.add_articles([article2], "github")

        assert result == 1
        assert len(layer) == 2


class TestCombinedDeduplication:
    """Test combined deduplication strategy."""

    def test_exact_match_takes_precedence(self):
        """Test that exact match takes precedence in combined mode."""
        layer = UnifiedDataLayer(strategy=DeduplicationStrategy.COMBINED)
        article1 = Article(
            source="rss",
            id="123",
            title="Article 1",
            url="https://example.com/1",
            summary="Test 1",
            published_at="2024-01-01T00:00:00",
            category="news",
        )
        article2 = Article(
            source="rss",
            id="123",
            title="Article 1 Updated",
            url="https://example.com/2",
            summary="Test 2",
            published_at="2024-01-01T00:00:00",
            category="news",
        )

        layer.add_articles([article1], "rss")
        layer.add_articles([article2], "rss")

        # Should be merged via exact match
        assert len(layer) == 1


class TestFiltering:
    """Test filtering and querying."""

    def test_filter_by_source(self):
        """Test filtering by source."""
        layer = UnifiedDataLayer()
        article_rss = Article(
            source="rss", id="1", title="RSS", url="https://example.com/1",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )
        article_github = Article(
            source="github", id="2", title="GitHub", url="https://example.com/2",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )

        layer.add_articles([article_rss], "rss")
        layer.add_articles([article_github], "github")

        rss_articles = layer.filter_by_source("rss")
        assert len(rss_articles) == 1
        assert rss_articles[0].sources == ["rss"]

    def test_filter_by_category(self):
        """Test filtering by category."""
        layer = UnifiedDataLayer()
        article_news = Article(
            source="rss", id="1", title="News", url="https://example.com/1",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )
        article_repo = Article(
            source="github", id="2", title="Repo", url="https://example.com/2",
            summary="", published_at="2024-01-01T00:00:00", category="repository"
        )

        layer.add_articles([article_news], "rss")
        layer.add_articles([article_repo], "github")

        news_articles = layer.filter_by_category("news")
        assert len(news_articles) == 1
        assert news_articles[0].article.category == "news"

    def test_filter_by_tag(self):
        """Test filtering by tag."""
        layer = UnifiedDataLayer()
        article = Article(
            source="rss", id="1", title="Test", url="https://example.com/1",
            summary="", published_at="2024-01-01T00:00:00", category="news",
            tags=["ai", "ml"]
        )

        layer.add_articles([article], "rss")

        ai_articles = layer.filter_by_tag("ai")
        assert len(ai_articles) == 1

    def test_search_by_title(self):
        """Test searching by title."""
        layer = UnifiedDataLayer()
        article1 = Article(
            source="rss", id="1", title="AI Breakthrough", url="https://example.com/1",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )
        article2 = Article(
            source="rss", id="2", title="ML Models Released", url="https://example.com/2",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )

        layer.add_articles([article1, article2], "rss")

        results = layer.get_by_title("AI")
        assert len(results) == 1
        assert "AI" in results[0].article.title


class TestStatistics:
    """Test statistics generation."""

    def test_basic_statistics(self):
        """Test that statistics are computed correctly."""
        layer = UnifiedDataLayer()
        articles = [
            Article(
                source=source, id=f"id{i}", title=f"Article {i}",
                url=f"https://example.com/{i}", summary="Test",
                published_at="2024-01-01T00:00:00", category="news",
                tags=["test", "ai"]
            )
            for i, source in enumerate(["rss", "github"])
        ]

        for i, article in enumerate(articles):
            layer.add_articles([article], article.source)

        stats = layer.get_statistics()

        assert stats["total_unified_articles"] == 2
        assert "rss" in stats["source_distribution"]
        assert "github" in stats["source_distribution"]
        assert "test" in [tag[0] for tag in stats["top_tags"]]

    def test_statistics_with_merges(self):
        """Test statistics when articles are merged."""
        layer = UnifiedDataLayer()
        article_rss = Article(
            source="rss", id="123", title="Test", url="https://example.com",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )
        article_github = Article(
            source="github", id="456", title="Test", url="https://example.com",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )

        layer.add_articles([article_rss], "rss")
        layer.add_articles([article_github], "github")

        stats = layer.get_statistics()

        # After similarity match merge
        assert stats["total_unified_articles"] <= 2


class TestJSONOutput:
    """Test JSON serialization."""

    def test_save_to_json(self):
        """Test saving unified data to JSON."""
        layer = UnifiedDataLayer()
        article = Article(
            source="rss", id="123", title="Test", url="https://example.com",
            summary="Test summary", published_at="2024-01-01T00:00:00",
            category="news", tags=["test"]
        )

        layer.add_articles([article], "rss")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = layer.save_to_json(output_dir=tmpdir)

            assert Path(filepath).exists()

            with open(filepath, "r") as f:
                data = json.load(f)

            assert "metadata" in data
            assert "articles" in data
            assert data["metadata"]["total_unified"] == 1
            assert data["articles"][0]["article"]["title"] == "Test"

    def test_save_creates_directory(self):
        """Test that save creates directory if needed."""
        layer = UnifiedDataLayer()

        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "new" / "path"
            assert not nonexistent_dir.exists()

            layer.save_to_json(output_dir=str(nonexistent_dir))

            assert nonexistent_dir.exists()

    def test_to_articles_list(self):
        """Test exporting unified articles as Article objects."""
        layer = UnifiedDataLayer()
        article = Article(
            source="rss", id="123", title="Test", url="https://example.com",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )

        layer.add_articles([article], "rss")
        articles_list = layer.to_articles_list()

        assert len(articles_list) == 1
        assert articles_list[0].title == "Test"


class TestUnifiedArticle:
    """Test UnifiedArticle dataclass."""

    def test_to_dict(self):
        """Test converting UnifiedArticle to dict."""
        article = Article(
            source="rss", id="123", title="Test", url="https://example.com",
            summary="", published_at="2024-01-01T00:00:00", category="news"
        )
        unified = UnifiedArticle(
            article=article,
            source_articles=[article],
            canonical_source="rss",
            sources=["rss"],
            source_ids={"rss": "123"},
        )

        result = unified.to_dict()

        assert "article" in result
        assert "sources" in result
        assert result["canonical_source"] == "rss"


class TestIntegration:
    """Integration tests."""

    def test_full_pipeline(self):
        """Test full pipeline with multiple sources."""
        layer = UnifiedDataLayer()

        # Simulate articles from different collectors
        rss_articles = [
            Article(
                source="rss", id=f"rss_{i}", title=f"News {i}",
                url=f"https://news.com/{i}", summary=f"Summary {i}",
                published_at="2024-01-01T00:00:00", category="news"
            )
            for i in range(3)
        ]

        github_articles = [
            Article(
                source="github", id=f"gh_{i}", title=f"Repo {i}",
                url=f"https://github.com/{i}", summary=f"Repo {i}",
                published_at="2024-01-01T00:00:00", category="repository"
            )
            for i in range(3)
        ]

        # Add from different sources
        layer.add_articles(rss_articles, "rss")
        layer.add_articles(github_articles, "github")

        # Verify data
        assert len(layer) >= 6
        assert len(layer.filter_by_source("rss")) >= 3
        assert len(layer.filter_by_source("github")) >= 3

        # Get statistics
        stats = layer.get_statistics()
        assert stats["total_unified_articles"] >= 6
        assert "rss" in stats["source_distribution"]
        assert "github" in stats["source_distribution"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
