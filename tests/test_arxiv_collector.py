"""
Unit tests for arXiv Collector.

Tests cover:
- Fetching from arXiv API
- Normalizing papers to Article schema
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

from app.collectors.arxiv_collector import ArxivCollector, Article


class TestArxivCollectorInitialization:
    """Test ArxivCollector initialization."""

    def test_default_initialization(self):
        """Test creating collector with defaults."""
        collector = ArxivCollector()
        assert len(collector.CATEGORIES) >= 5
        assert "cs.AI" in collector.CATEGORIES
        assert "cs.LG" in collector.CATEGORIES
        assert collector.max_papers_per_category == 30
        assert collector.max_total == 150
        assert collector.days_back == 7

    def test_custom_settings(self):
        """Test custom parameters."""
        collector = ArxivCollector(
            max_papers_per_category=50, max_total=200, days_back=14
        )
        assert collector.max_papers_per_category == 50
        assert collector.max_total == 200
        assert collector.days_back == 14


class TestExtractArxivId:
    """Test arXiv ID extraction."""

    def test_extract_id_from_abs_url(self):
        """Test extracting ID from /abs/ URL."""
        url = "http://arxiv.org/abs/2401.01234"
        arxiv_id = ArxivCollector._extract_arxiv_id(url)
        assert arxiv_id == "2401.01234"

    def test_extract_id_plain(self):
        """Test extracting plain arXiv ID."""
        arxiv_id = ArxivCollector._extract_arxiv_id("2401.01234")
        assert arxiv_id == "2401.01234"

    def test_extract_id_with_version(self):
        """Test extracting ID with version suffix."""
        url = "http://arxiv.org/abs/2401.01234v2"
        arxiv_id = ArxivCollector._extract_arxiv_id(url)
        assert arxiv_id == "2401.01234v2"


class TestNormalizePaper:
    """Test paper normalization."""

    def test_normalize_basic_paper(self):
        """Test normalizing a basic paper entry."""
        entry = {
            "id": "http://arxiv.org/abs/2401.01234v1",
            "title": "Attention Is All You Need",
            "summary": "This paper introduces the Transformer architecture.",
            "published": "2017-06-12T00:00:00Z",
            "authors": [
                {"name": "Ashish Vaswani"},
                {"name": "Noam Shazeer"},
                {"name": "Parmar Arun"},
            ],
            "categories": [{"term": "cs.LG"}, {"term": "cs.AI"}],
        }

        article = ArxivCollector._normalize_paper(entry, "cs.LG", "Machine Learning")

        assert article.source == "arxiv"
        assert article.title == "Attention Is All You Need"
        assert "Transformer" in article.summary
        assert article.author == "Ashish Vaswani"
        assert article.category == "research-paper"
        assert "arxiv" in article.tags
        assert "cs.LG" in article.tags
        assert article.metadata["arxiv_id"] == "2401.01234v1"
        assert len(article.metadata["authors"]) == 3

    def test_normalize_paper_missing_fields(self):
        """Test normalization with missing fields."""
        entry = {
            "id": "http://arxiv.org/abs/2401.01234v1",
            "title": "Test Paper",
            "published": "2024-01-12T00:00:00Z",
        }

        article = ArxivCollector._normalize_paper(entry, "cs.AI", "Artificial Intelligence")

        assert article.title == "Test Paper"
        assert article.summary == ""
        assert article.author is None
        assert article.metadata["authors"] == []

    def test_normalize_paper_multiple_authors(self):
        """Test author formatting with multiple authors."""
        entry = {
            "id": "http://arxiv.org/abs/2401.01234v1",
            "title": "Test",
            "published": "2024-01-12T00:00:00Z",
            "authors": [
                {"name": f"Author {i}"} for i in range(5)
            ],
        }

        article = ArxivCollector._normalize_paper(entry, "cs.LG", "Machine Learning")

        # Should show first 3 + count of remaining
        assert "Author 0" in article.metadata["authors_formatted"]
        assert "+2 more" in article.metadata["authors_formatted"]
        assert len(article.metadata["authors"]) == 5

    def test_normalize_paper_categories_in_tags(self):
        """Test that categories are included in tags."""
        entry = {
            "id": "http://arxiv.org/abs/2401.01234v1",
            "title": "Test",
            "published": "2024-01-12T00:00:00Z",
            "categories": [{"term": "cs.LG"}, {"term": "stat.ML"}, {"term": "cs.AI"}],
        }

        article = ArxivCollector._normalize_paper(entry, "cs.LG", "Machine Learning")

        assert "cs.LG" in article.tags
        assert "stat.ML" in article.tags
        assert "cs.AI" in article.tags

    def test_normalize_paper_pdf_url(self):
        """Test PDF URL generation."""
        entry = {
            "id": "http://arxiv.org/abs/2401.01234v1",
            "title": "Test",
            "published": "2024-01-12T00:00:00Z",
        }

        article = ArxivCollector._normalize_paper(entry, "cs.LG", "Machine Learning")

        assert "pdf" in article.metadata["pdf_url"]
        assert "2401.01234" in article.metadata["pdf_url"]

    def test_normalize_paper_date_format(self):
        """Test date conversion to ISO format."""
        entry = {
            "id": "http://arxiv.org/abs/2401.01234v1",
            "title": "Test",
            "published": "2024-01-12T14:30:00Z",
        }

        article = ArxivCollector._normalize_paper(entry, "cs.LG", "Machine Learning")

        # Should convert to YYYY-MM-DD format
        assert article.published_at.startswith("2024-01-12")


class TestSearchCategory:
    """Test searching a category."""

    @patch("app.collectors.arxiv_collector.requests.Session.get")
    def test_search_category_success(self, mock_get):
        """Test successful category search."""
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2401.01234v1</id>
        <title>Test Paper 1</title>
        <summary>Test summary</summary>
        <published>2024-01-12T00:00:00Z</published>
        <author><name>Author One</name></author>
    </entry>
    <entry>
        <id>http://arxiv.org/abs/2401.01235v1</id>
        <title>Test Paper 2</title>
        <summary>Another summary</summary>
        <published>2024-01-12T00:00:00Z</published>
        <author><name>Author Two</name></author>
    </entry>
</feed>"""
        mock_get.return_value = mock_response

        collector = ArxivCollector()
        papers = collector._search_category("cs.LG", "Machine Learning", set())

        assert len(papers) == 2
        assert papers[0].title == "Test Paper 1"
        assert papers[1].title == "Test Paper 2"

    @patch("app.collectors.arxiv_collector.requests.Session.get")
    def test_search_category_skips_seen_ids(self, mock_get):
        """Test that already-seen papers are skipped."""
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2401.01234v1</id>
        <title>Test Paper 1</title>
        <summary>Test</summary>
        <published>2024-01-12T00:00:00Z</published>
    </entry>
</feed>"""
        mock_get.return_value = mock_response

        collector = ArxivCollector()
        seen = {"2401.01234v1"}
        papers = collector._search_category("cs.LG", "Machine Learning", seen)

        # Should skip the seen paper
        assert len(papers) == 0

    @patch("app.collectors.arxiv_collector.requests.Session.get")
    def test_search_category_respects_max(self, mock_get):
        """Test that search query respects max_papers_per_category."""
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2401.01234v1</id>
        <title>Test Paper</title>
        <summary>Summary</summary>
        <published>2024-01-12T00:00:00Z</published>
    </entry>
</feed>"""
        mock_get.return_value = mock_response

        collector = ArxivCollector(max_papers_per_category=20)
        papers = collector._search_category("cs.LG", "Machine Learning", set())

        # Check that the search query was made with max_results=20
        call_args = mock_get.call_args
        assert "max_results=20" in call_args[0][0] or call_args[1].get("params", {}).get("max_results") == 20

    @patch("app.collectors.arxiv_collector.requests.Session.get")
    def test_search_category_api_error(self, mock_get):
        """Test handling of API errors."""
        import requests

        mock_get.side_effect = requests.RequestException("API Error")

        collector = ArxivCollector()
        with pytest.raises(requests.RequestException):
            collector._search_category("cs.LG", "Machine Learning", set())


class TestFetchAll:
    """Test fetching all categories."""

    @patch("app.collectors.arxiv_collector.requests.Session.get")
    def test_fetch_all_multiple_categories(self, mock_get):
        """Test fetching from multiple categories."""
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2401.01234v1</id>
        <title>Test Paper</title>
        <summary>Test</summary>
        <published>2024-01-12T00:00:00Z</published>
    </entry>
</feed>"""
        mock_get.return_value = mock_response

        collector = ArxivCollector()
        papers = collector.fetch_all()

        # Should search multiple categories
        assert len(papers) >= 1
        assert mock_get.call_count >= len(collector.CATEGORIES)

    @patch("app.collectors.arxiv_collector.requests.Session.get")
    def test_fetch_all_respects_max_total(self, mock_get):
        """Test that max_total limit is respected."""
        entries = "\n".join([
            f"""<entry>
        <id>http://arxiv.org/abs/2401.{i:05d}v1</id>
        <title>Paper {i}</title>
        <summary>Summary</summary>
        <published>2024-01-12T00:00:00Z</published>
    </entry>"""
            for i in range(1, 51)
        ])

        mock_response = MagicMock()
        mock_response.content = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
{entries}
</feed>""".encode()
        mock_get.return_value = mock_response

        collector = ArxivCollector(max_total=50)
        papers = collector.fetch_all()

        assert len(papers) <= 50

    @patch("app.collectors.arxiv_collector.requests.Session.get")
    def test_fetch_all_deduplicates(self, mock_get):
        """Test that duplicate papers are filtered."""
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2401.01234v1</id>
        <title>Test Paper</title>
        <summary>Test</summary>
        <published>2024-01-12T00:00:00Z</published>
    </entry>
</feed>"""
        mock_get.return_value = mock_response

        collector = ArxivCollector()
        papers = collector.fetch_all()

        # Count papers with same ID
        paper_ids = [p.metadata["arxiv_id"] for p in papers]
        assert len(paper_ids) == len(set(paper_ids))  # All unique


class TestJSONOutput:
    """Test JSON serialization."""

    def test_to_json_string(self):
        """Test converting papers to JSON string."""
        paper_article = Article(
            source="arxiv",
            id="123",
            title="Attention Is All You Need",
            url="http://arxiv.org/abs/1706.03762",
            summary="The Transformer architecture",
            published_at="2017-06-12T00:00:00",
            category="research-paper",
            tags=["cs.LG", "arxiv"],
            metadata={
                "arxiv_id": "1706.03762",
                "authors": ["Ashish Vaswani"],
                "category_name": "Machine Learning",
            },
        )

        collector = ArxivCollector()
        collector.articles = [paper_article]
        json_str = collector.to_json_string()

        # Should be valid JSON
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]["title"] == "Attention Is All You Need"
        assert data[0]["metadata"]["arxiv_id"] == "1706.03762"

    def test_save_to_json(self):
        """Test saving papers to JSON file."""
        paper_article = Article(
            source="arxiv",
            id="123",
            title="Test Paper",
            url="http://arxiv.org/abs/2401.01234",
            summary="Test summary",
            published_at="2024-01-12T00:00:00",
            category="research-paper",
            metadata={"arxiv_id": "2401.01234"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = ArxivCollector()
            collector.articles = [paper_article]
            filepath = collector.save_to_json(output_dir=tmpdir)

            # File should exist
            assert Path(filepath).exists()

            # Should contain valid JSON
            with open(filepath, "r") as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["title"] == "Test Paper"

    def test_save_creates_directory(self):
        """Test that save_to_json creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "new" / "path"
            assert not nonexistent_dir.exists()

            collector = ArxivCollector()
            collector.articles = []
            collector.save_to_json(output_dir=str(nonexistent_dir))

            assert nonexistent_dir.exists()


class TestIntegration:
    """Integration tests."""

    @patch("app.collectors.arxiv_collector.requests.Session.get")
    def test_full_pipeline(self, mock_get):
        """Test full fetch, normalize, save pipeline."""
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/1706.03762v5</id>
        <title>Attention Is All You Need</title>
        <summary>The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.</summary>
        <published>2017-06-12T17:58:41Z</published>
        <author><name>Ashish Vaswani</name></author>
        <author><name>Noam Shazeer</name></author>
        <category term="cs.LG"/>
        <category term="cs.AI"/>
    </entry>
</feed>"""
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = ArxivCollector()
            papers = collector.fetch_all()
            filepath = collector.save_to_json(output_dir=tmpdir)

            assert len(papers) >= 1
            assert Path(filepath).exists()

            with open(filepath) as f:
                data = json.load(f)
            assert data[0]["source"] == "arxiv"
            assert "Attention" in data[0]["title"]
            assert "Vaswani" in data[0]["author"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
