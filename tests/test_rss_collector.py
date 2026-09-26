"""
Unit tests for RSS Collector.

Tests cover:
- Fetching from RSS feeds
- Normalizing entries
- JSON output
- Error handling
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import tempfile

from app.collectors.rss_collector import RSSCollector, Article


class TestArticleModel:
    """Test Article dataclass."""

    def test_article_creation(self):
        """Test creating an Article."""
        article = Article(
            source="test",
            id="123",
            title="Test Article",
            url="https://example.com",
            summary="Test summary",
            published_at="2024-01-01T00:00:00",
        )
        assert article.source == "test"
        assert article.title == "Test Article"
        assert article.tags == []  # Should initialize to empty list

    def test_article_with_metadata(self):
        """Test Article with metadata."""
        article = Article(
            source="test",
            id="123",
            title="Test",
            url="https://example.com",
            summary="Summary",
            published_at="2024-01-01T00:00:00",
            tags=["ai", "research"],
            metadata={"key": "value"},
        )
        assert article.tags == ["ai", "research"]
        assert article.metadata == {"key": "value"}


class TestRSSCollectorInitialization:
    """Test RSSCollector initialization."""

    def test_default_initialization(self):
        """Test creating collector with defaults."""
        collector = RSSCollector()
        assert len(collector.feeds) > 0
        assert "hackernews" in collector.feeds
        assert "arxiv_ai" in collector.feeds

    def test_custom_feeds(self):
        """Test creating collector with custom feeds."""
        custom_feeds = {"test": "https://example.com/feed"}
        collector = RSSCollector(feeds=custom_feeds)
        assert collector.feeds == custom_feeds

    def test_timeout_setting(self):
        """Test timeout parameter."""
        collector = RSSCollector(timeout=5)
        assert collector.timeout == 5


class TestNormalizeEntry:
    """Test entry normalization."""

    def test_normalize_basic_entry(self):
        """Test normalizing a basic entry."""
        entry = {
            "title": "Test Article",
            "link": "https://example.com/article",
            "summary": "Test summary",
            "author": "John Doe",
            "published_parsed": (2024, 1, 15, 10, 30, 0, 0, 0, 0),
        }

        article = RSSCollector._normalize_entry(entry, "test_source")

        assert article.title == "Test Article"
        assert article.url == "https://example.com/article"
        assert article.author == "John Doe"
        assert article.source == "test_source"
        assert article.id is not None  # Should have hash-based ID

    def test_normalize_arxiv_entry(self):
        """Test normalization categorizes arxiv as 'paper'."""
        entry = {
            "title": "A Research Paper",
            "link": "https://arxiv.org/abs/2024.1234",
            "summary": "Research summary",
        }

        article = RSSCollector._normalize_entry(entry, "arxiv_ai")

        assert article.category == "paper"
        assert "research" in article.tags

    def test_normalize_hackernews_entry(self):
        """Test normalization categorizes HN as 'story'."""
        entry = {
            "title": "A Tech Story",
            "link": "https://example.com/story",
            "summary": "Story summary",
        }

        article = RSSCollector._normalize_entry(entry, "hackernews")

        assert article.category == "story"
        assert "news" in article.tags

    def test_normalize_missing_fields(self):
        """Test normalization handles missing fields."""
        entry = {
            "title": "Minimal Entry",
            # No link, summary, author, or dates
        }

        article = RSSCollector._normalize_entry(entry, "test")

        assert article.title == "Minimal Entry"
        assert article.url == ""
        assert article.summary == ""
        assert article.author is None
        assert article.published_at is not None  # Should use current time

    def test_clean_text_removes_html(self):
        """Test HTML tag removal."""
        dirty = "<p>Hello <b>world</b></p>"
        clean = RSSCollector._clean_text(dirty)
        assert "<" not in clean
        assert ">" not in clean
        assert "Hello world" in clean

    def test_clean_text_collapses_whitespace(self):
        """Test whitespace collapsing."""
        dirty = "Hello    world    test"
        clean = RSSCollector._clean_text(dirty)
        assert clean == "Hello world test"


class TestFetchFeed:
    """Test fetching individual feeds."""

    @patch("app.collectors.rss_collector.feedparser.parse")
    def test_fetch_single_feed(self, mock_parse):
        """Test fetching a single feed."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_entry = {
            "title": "Article 1",
            "link": "https://example.com/1",
            "summary": "Summary 1",
        }
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed

        collector = RSSCollector()
        articles = collector._fetch_feed("https://example.com/feed", "test")

        assert len(articles) == 1
        assert articles[0].title == "Article 1"

    @patch("app.collectors.rss_collector.feedparser.parse")
    def test_fetch_feed_with_multiple_entries(self, mock_parse):
        """Test fetching feed with multiple entries."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {"title": f"Article {i}", "link": f"https://example.com/{i}"}
            for i in range(5)
        ]
        mock_parse.return_value = mock_feed

        collector = RSSCollector()
        articles = collector._fetch_feed("https://example.com/feed", "test")

        assert len(articles) == 5

    @patch("app.collectors.rss_collector.feedparser.parse")
    def test_fetch_feed_limits_entries(self, mock_parse):
        """Test that feed fetch limits to 50 entries."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {"title": f"Article {i}", "link": f"https://example.com/{i}"}
            for i in range(100)
        ]
        mock_parse.return_value = mock_feed

        collector = RSSCollector()
        articles = collector._fetch_feed("https://example.com/feed", "test")

        assert len(articles) == 50  # Should be limited to 50

    @patch("app.collectors.rss_collector.feedparser.parse")
    def test_fetch_feed_handles_bad_entries(self, mock_parse):
        """Test that bad entries are skipped."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {"title": "Good Article", "link": "https://example.com/good"},
            {"title": "Bad Entry"},  # Missing URL
            {"title": "Another Good", "link": "https://example.com/good2"},
        ]
        mock_parse.return_value = mock_feed

        collector = RSSCollector()
        articles = collector._fetch_feed("https://example.com/feed", "test")

        # Should have 2 good articles, 1 bad skipped
        assert len(articles) >= 2


class TestFetchAll:
    """Test fetching from all feeds."""

    @patch("app.collectors.rss_collector.feedparser.parse")
    def test_fetch_all_feeds(self, mock_parse):
        """Test fetching from multiple feeds."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {"title": "Article 1", "link": "https://example.com/1"}
        ]
        mock_parse.return_value = mock_feed

        custom_feeds = {
            "feed1": "https://example.com/feed1",
            "feed2": "https://example.com/feed2",
        }
        collector = RSSCollector(feeds=custom_feeds)
        articles = collector.fetch_all()

        # 2 feeds × 1 article each = 2 articles
        assert len(articles) == 2
        assert mock_parse.call_count == 2


class TestJSONOutput:
    """Test JSON serialization."""

    def test_to_json_string(self):
        """Test converting articles to JSON string."""
        article = Article(
            source="test",
            id="123",
            title="Test",
            url="https://example.com",
            summary="Summary",
            published_at="2024-01-01T00:00:00",
        )

        collector = RSSCollector()
        collector.articles = [article]
        json_str = collector.to_json_string()

        # Should be valid JSON
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]["title"] == "Test"

    def test_save_to_json(self):
        """Test saving articles to JSON file."""
        article = Article(
            source="test",
            id="123",
            title="Test Article",
            url="https://example.com",
            summary="Summary",
            published_at="2024-01-01T00:00:00",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = RSSCollector()
            collector.articles = [article]
            filepath = collector.save_to_json(output_dir=tmpdir)

            # File should exist
            assert Path(filepath).exists()

            # Should contain valid JSON
            with open(filepath, "r") as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["title"] == "Test Article"

    def test_save_creates_directory(self):
        """Test that save_to_json creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "new" / "path"
            assert not nonexistent_dir.exists()

            collector = RSSCollector()
            collector.articles = []
            collector.save_to_json(output_dir=str(nonexistent_dir))

            assert nonexistent_dir.exists()


class TestIntegration:
    """Integration tests."""

    @patch("app.collectors.rss_collector.feedparser.parse")
    def test_full_pipeline(self, mock_parse):
        """Test full fetch, normalize, save pipeline."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {
                "title": "AI Breakthrough",
                "link": "https://example.com/ai",
                "summary": "Major AI news",
                "published_parsed": (2024, 1, 15, 10, 0, 0, 0, 0, 0),
            }
        ]
        mock_parse.return_value = mock_feed

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use custom feeds so we only mock one
            custom_feeds = {"test": "https://example.com/feed"}
            collector = RSSCollector(feeds=custom_feeds)
            articles = collector.fetch_all()
            filepath = collector.save_to_json(output_dir=tmpdir)

            assert len(articles) == 1
            assert Path(filepath).exists()

            with open(filepath) as f:
                data = json.load(f)
            assert data[0]["title"] == "AI Breakthrough"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
