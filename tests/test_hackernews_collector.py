"""
Unit tests for Hacker News Collector.

Tests cover:
- Fetching from HN API
- Normalizing stories to Article schema
- JSON output
- Error handling
- Duplicate detection
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import tempfile

from app.collectors.hackernews_collector import HackerNewsCollector, Article


class TestHackerNewsCollectorInitialization:
    """Test HackerNewsCollector initialization."""

    def test_default_initialization(self):
        """Test creating collector with defaults."""
        collector = HackerNewsCollector()
        assert len(collector.STORY_TYPES) == 3
        assert "top" in collector.STORY_TYPES
        assert "best" in collector.STORY_TYPES
        assert "new" in collector.STORY_TYPES
        assert collector.max_stories_per_type == 30
        assert collector.max_total == 100

    def test_custom_settings(self):
        """Test custom max_stories_per_type and max_total."""
        collector = HackerNewsCollector(max_stories_per_type=50, max_total=200)
        assert collector.max_stories_per_type == 50
        assert collector.max_total == 200


class TestNormalizeStory:
    """Test story normalization."""

    def test_normalize_basic_story(self):
        """Test normalizing a basic story."""
        story = {
            "id": 12345,
            "type": "story",
            "title": "Breaking: New AI Model Outperforms GPT-4",
            "url": "https://example.com/ai-model",
            "score": 850,
            "descendants": 120,
            "by": "alice",
            "time": 1694505600,  # 2023-09-12
        }

        article = HackerNewsCollector._normalize_story(story, "top")

        assert article.source == "hacker-news"
        assert article.title == "Breaking: New AI Model Outperforms GPT-4"
        assert article.url == "https://example.com/ai-model"
        assert article.category == "news"
        assert article.author == "alice"
        assert "top" in article.tags
        assert "hacker-news" in article.tags
        assert article.metadata["score"] == 850
        assert article.metadata["descendants"] == 120
        assert article.metadata["hn_story_id"] == 12345

    def test_normalize_story_missing_fields(self):
        """Test normalization with missing fields."""
        story = {
            "id": 12345,
            "type": "story",
            "title": "Test Story",
            "time": 1694505600,
        }

        article = HackerNewsCollector._normalize_story(story, "top")

        assert article.title == "Test Story"
        assert article.summary is not None
        assert article.metadata["score"] == 0
        assert article.metadata["descendants"] == 0
        assert article.metadata["original_url"] == ""

    def test_normalize_story_no_url_fallback_to_hn_comments(self):
        """Test that missing URL falls back to HN comments link."""
        story = {
            "id": 12345,
            "type": "story",
            "title": "Show HN: My Project",
            "score": 500,
            "time": 1694505600,
        }

        article = HackerNewsCollector._normalize_story(story, "top")

        assert "news.ycombinator.com/item?id=12345" in article.url

    def test_normalize_story_summary_format(self):
        """Test that summary includes score, comments, and domain."""
        story = {
            "id": 12345,
            "type": "story",
            "title": "Test",
            "url": "https://example.com/article",
            "score": 500,
            "descendants": 75,
            "time": 1694505600,
        }

        article = HackerNewsCollector._normalize_story(story, "top")

        assert "500" in article.summary
        assert "⬆️" in article.summary
        assert "75" in article.summary
        assert "💬" in article.summary
        assert "example.com" in article.summary

    def test_normalize_job_story(self):
        """Test normalizing a job posting."""
        story = {
            "id": 12345,
            "type": "job",
            "title": "Hiring: Senior ML Engineer at OpenAI",
            "url": "https://openai.com/jobs",
            "score": 250,
            "descendants": 45,
            "time": 1694505600,
        }

        article = HackerNewsCollector._normalize_story(story, "top")

        assert "job" in article.tags
        assert article.metadata["story_type"] == "job"

    def test_normalize_story_invalid_timestamp(self):
        """Test handling of invalid timestamp."""
        story = {
            "id": 12345,
            "type": "story",
            "title": "Test",
            "time": 9999999999999,  # Invalid
        }

        article = HackerNewsCollector._normalize_story(story, "top")

        # Should use current time fallback
        assert article.published_at is not None
        assert "T" in article.published_at  # ISO format

    def test_normalize_story_duplicate_tags_removed(self):
        """Test that duplicate tags don't appear."""
        story = {
            "id": 12345,
            "type": "story",
            "title": "Test",
            "time": 1694505600,
        }

        article = HackerNewsCollector._normalize_story(story, "top")

        # Count tags
        assert article.tags.count("top") == 1
        assert article.tags.count("hacker-news") == 1


class TestFetchAndNormalizeStory:
    """Test fetching individual stories."""

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_and_normalize_story_success(self, mock_get):
        """Test successful story fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 12345,
            "type": "story",
            "title": "Test Story",
            "url": "https://example.com",
            "score": 100,
            "descendants": 10,
            "by": "user",
            "time": 1694505600,
        }
        mock_get.return_value = mock_response

        collector = HackerNewsCollector()
        article = collector._fetch_and_normalize_story(12345, "top")

        assert article is not None
        assert article.title == "Test Story"

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_story_deleted(self, mock_get):
        """Test handling of deleted stories."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 12345,
            "type": "story",
            "deleted": True,
        }
        mock_get.return_value = mock_response

        collector = HackerNewsCollector()
        article = collector._fetch_and_normalize_story(12345, "top")

        assert article is None

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_story_dead(self, mock_get):
        """Test handling of dead stories."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 12345,
            "type": "story",
            "dead": True,
        }
        mock_get.return_value = mock_response

        collector = HackerNewsCollector()
        article = collector._fetch_and_normalize_story(12345, "top")

        assert article is None

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_story_wrong_type(self, mock_get):
        """Test filtering of comment/poll types."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 12345,
            "type": "comment",  # Not a story or job
            "text": "This is a comment",
        }
        mock_get.return_value = mock_response

        collector = HackerNewsCollector()
        article = collector._fetch_and_normalize_story(12345, "top")

        assert article is None

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_story_api_error(self, mock_get):
        """Test handling of API errors."""
        import requests

        mock_get.side_effect = requests.RequestException("API Error")

        collector = HackerNewsCollector()
        article = collector._fetch_and_normalize_story(12345, "top")

        assert article is None


class TestFetchStories:
    """Test fetching story lists."""

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_stories_success(self, mock_get):
        """Test successful story list fetch."""
        # First call returns list of IDs, subsequent calls return story data
        story_id_response = MagicMock()
        story_id_response.json.return_value = [12345, 12346, 12347]

        story_response = MagicMock()
        story_response.json.return_value = {
            "id": 12345,
            "type": "story",
            "title": "Test",
            "score": 100,
            "descendants": 10,
            "by": "user",
            "time": 1694505600,
        }

        mock_get.side_effect = [story_id_response, story_response, story_response, story_response]

        collector = HackerNewsCollector()
        stories = collector._fetch_stories(
            "https://hacker-news.firebaseio.com/v0/topstories.json", "top", set()
        )

        assert len(stories) == 3

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_stories_respects_max_per_type(self, mock_get):
        """Test that max_stories_per_type is respected."""
        story_id_response = MagicMock()
        story_id_response.json.return_value = list(range(100, 150))  # 50 IDs

        story_response = MagicMock()
        story_response.json.return_value = {
            "id": 100,
            "type": "story",
            "title": "Test",
            "score": 100,
            "descendants": 10,
            "by": "user",
            "time": 1694505600,
        }

        mock_get.side_effect = [story_id_response] + [story_response] * 50

        collector = HackerNewsCollector(max_stories_per_type=30)
        stories = collector._fetch_stories(
            "https://hacker-news.firebaseio.com/v0/topstories.json", "top", set()
        )

        assert len(stories) <= 30

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_stories_skips_seen_ids(self, mock_get):
        """Test that already-seen IDs are skipped."""
        story_id_response = MagicMock()
        story_id_response.json.return_value = [100, 101, 102]

        story_response = MagicMock()
        story_response.json.return_value = {
            "id": 100,
            "type": "story",
            "title": "Test",
            "score": 100,
            "descendants": 10,
            "by": "user",
            "time": 1694505600,
        }

        mock_get.side_effect = [story_id_response, story_response, story_response]

        collector = HackerNewsCollector()
        seen = {100}  # 100 already seen
        stories = collector._fetch_stories(
            "https://hacker-news.firebaseio.com/v0/topstories.json", "top", seen
        )

        # Should skip ID 100
        assert len(stories) == 2


class TestFetchAll:
    """Test fetching all story types."""

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_all_multiple_types(self, mock_get):
        """Test fetching from multiple story types."""
        story_id_response = MagicMock()
        story_id_response.json.return_value = [12345, 12346, 12347]

        story_response = MagicMock()
        story_response.json.return_value = {
            "id": 12345,
            "type": "story",
            "title": "Test",
            "score": 100,
            "descendants": 10,
            "by": "user",
            "time": 1694505600,
        }

        # Setup enough responses: 3 story ID fetches + 9 story fetches (3 per type)
        mock_get.side_effect = (
            [story_id_response, story_response] * 15
        )

        collector = HackerNewsCollector()
        stories = collector.fetch_all()

        # Should fetch from 3 types (top, best, new)
        assert len(stories) >= 1

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_all_respects_max_total(self, mock_get):
        """Test that max_total limit is respected."""
        story_id_response = MagicMock()
        story_id_response.json.return_value = [100, 101, 102, 103, 104, 105]

        story_response = MagicMock()
        story_response.json.return_value = {
            "id": 100,
            "type": "story",
            "title": "Test",
            "score": 100,
            "descendants": 10,
            "by": "user",
            "time": 1694505600,
        }

        # 3 calls for story IDs + many for individual stories
        mock_get.side_effect = (
            [story_id_response] * 3 + [story_response] * 100
        )

        collector = HackerNewsCollector(max_total=50)
        stories = collector.fetch_all()

        assert len(stories) <= 50

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_fetch_all_deduplicates(self, mock_get):
        """Test that duplicate stories are filtered."""
        story_id_response = MagicMock()
        story_id_response.json.return_value = [12345, 12345, 12345]  # Same ID

        story_response = MagicMock()
        story_response.json.return_value = {
            "id": 12345,
            "type": "story",
            "title": "Test",
            "score": 100,
            "descendants": 10,
            "by": "user",
            "time": 1694505600,
        }

        mock_get.side_effect = (
            [story_id_response] * 3 + [story_response] * 100
        )

        collector = HackerNewsCollector()
        stories = collector.fetch_all()

        # Count stories with same ID
        story_ids = [s.metadata["hn_story_id"] for s in stories]
        assert len(story_ids) == len(set(story_ids))  # All unique


class TestJSONOutput:
    """Test JSON serialization."""

    def test_to_json_string(self):
        """Test converting stories to JSON string."""
        story_article = Article(
            source="hacker-news",
            id="123",
            title="Breaking News on AI",
            url="https://news.ycombinator.com/item?id=12345",
            summary="⬆️ 500 points | 💬 45 comments",
            published_at="2024-01-01T00:00:00",
            category="news",
            tags=["top", "hacker-news"],
            metadata={"hn_story_id": 12345, "score": 500},
        )

        collector = HackerNewsCollector()
        collector.articles = [story_article]
        json_str = collector.to_json_string()

        # Should be valid JSON
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]["title"] == "Breaking News on AI"
        assert data[0]["metadata"]["score"] == 500

    def test_save_to_json(self):
        """Test saving stories to JSON file."""
        story_article = Article(
            source="hacker-news",
            id="123",
            title="Breaking News",
            url="https://news.ycombinator.com/item?id=12345",
            summary="⬆️ 500 points | 💬 45 comments",
            published_at="2024-01-01T00:00:00",
            category="news",
            metadata={"hn_story_id": 12345},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = HackerNewsCollector()
            collector.articles = [story_article]
            filepath = collector.save_to_json(output_dir=tmpdir)

            # File should exist
            assert Path(filepath).exists()

            # Should contain valid JSON
            with open(filepath, "r") as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["title"] == "Breaking News"

    def test_save_creates_directory(self):
        """Test that save_to_json creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "new" / "path"
            assert not nonexistent_dir.exists()

            collector = HackerNewsCollector()
            collector.articles = []
            collector.save_to_json(output_dir=str(nonexistent_dir))

            assert nonexistent_dir.exists()


class TestIntegration:
    """Integration tests."""

    @patch("app.collectors.hackernews_collector.requests.Session.get")
    def test_full_pipeline(self, mock_get):
        """Test full fetch, normalize, save pipeline."""
        story_id_response = MagicMock()
        story_id_response.json.return_value = [12345]

        story_response = MagicMock()
        story_response.json.return_value = {
            "id": 12345,
            "type": "story",
            "title": "AI Research Breakthrough",
            "url": "https://example.com/ai",
            "score": 850,
            "descendants": 120,
            "by": "researcher",
            "time": 1694505600,
        }

        mock_get.side_effect = (
            [story_id_response, story_response] * 3 + [story_response] * 10
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = HackerNewsCollector()
            stories = collector.fetch_all()
            filepath = collector.save_to_json(output_dir=tmpdir)

            assert len(stories) >= 1
            assert Path(filepath).exists()

            with open(filepath) as f:
                data = json.load(f)
            assert data[0]["source"] == "hacker-news"
            assert "Breakthrough" in data[0]["title"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
