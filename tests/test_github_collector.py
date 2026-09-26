"""
Unit tests for GitHub Collector.

Tests cover:
- Fetching from GitHub API
- Normalizing repos to Article schema
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

from app.collectors.github_collector import GitHubCollector, Article


class TestGitHubCollectorInitialization:
    """Test GitHubCollector initialization."""

    def test_default_initialization(self):
        """Test creating collector with defaults."""
        collector = GitHubCollector()
        assert len(collector.SEARCH_QUERIES) > 0
        assert "llm" in collector.SEARCH_QUERIES
        assert collector.per_page == 30
        assert collector.max_results == 100

    def test_custom_settings(self):
        """Test custom per_page and max_results."""
        collector = GitHubCollector(per_page=50, max_results=200)
        assert collector.per_page == 50
        assert collector.max_results == 200

    def test_per_page_capped_at_100(self):
        """Test that per_page is capped at 100."""
        collector = GitHubCollector(per_page=150)
        assert collector.per_page == 100


class TestNormalizeRepo:
    """Test repository normalization."""

    def test_normalize_basic_repo(self):
        """Test normalizing a basic repo."""
        repo = {
            "full_name": "anthropics/claude",
            "name": "claude",
            "html_url": "https://github.com/anthropics/claude",
            "description": "Claude AI model",
            "stargazers_count": 50000,
            "forks_count": 5000,
            "language": "Python",
            "open_issues_count": 100,
            "pushed_at": "2024-01-15T10:30:00Z",
            "created_at": "2023-01-01T00:00:00Z",
            "owner": {"login": "anthropics"},
            "topics": ["ai", "llm"],
        }

        article = GitHubCollector._normalize_repo(repo, "llm")

        assert article.source == "github"
        assert "claude" in article.title.lower()
        assert article.url == "https://github.com/anthropics/claude"
        assert article.category == "repository"
        assert article.author == "anthropics"
        assert "llm" in article.tags
        assert article.metadata["stars"] == 50000
        assert article.metadata["forks"] == 5000

    def test_normalize_repo_missing_fields(self):
        """Test normalization with missing fields."""
        repo = {
            "full_name": "user/repo",
            "name": "repo",
            "html_url": "https://github.com/user/repo",
        }

        article = GitHubCollector._normalize_repo(repo, "test")

        assert article.title is not None
        assert article.summary is not None
        assert article.metadata["stars"] == 0
        assert article.metadata["forks"] == 0
        assert article.metadata["language"] == ""

    def test_normalize_repo_with_topics(self):
        """Test that topics are included as tags."""
        repo = {
            "full_name": "user/repo",
            "name": "repo",
            "html_url": "https://github.com/user/repo",
            "topics": ["machine-learning", "nlp", "transformers"],
        }

        article = GitHubCollector._normalize_repo(repo, "ai")

        assert "machine-learning" in article.tags
        assert "nlp" in article.tags
        assert "transformers" in article.tags
        assert "ai" in article.tags  # Category should be included
        assert "github" in article.tags  # Source should be included

    def test_normalize_repo_duplicate_tags(self):
        """Test that duplicate tags are removed."""
        repo = {
            "full_name": "user/repo",
            "name": "repo",
            "html_url": "https://github.com/user/repo",
            "topics": ["ai", "ai", "github"],  # Duplicates
        }

        article = GitHubCollector._normalize_repo(repo, "ai")

        # Count occurrences
        ai_count = article.tags.count("ai")
        assert ai_count == 1  # Should only appear once

    def test_normalize_repo_summary_format(self):
        """Test that summary includes description, stars, and language."""
        repo = {
            "full_name": "user/repo",
            "name": "repo",
            "html_url": "https://github.com/user/repo",
            "description": "A great ML library",
            "stargazers_count": 10000,
            "language": "Rust",
        }

        article = GitHubCollector._normalize_repo(repo, "test")

        assert "A great ML library" in article.summary
        assert "10000" in article.summary
        assert "⭐" in article.summary
        assert "Rust" in article.summary


class TestSearchRepos:
    """Test searching for repos."""

    @patch("app.collectors.github_collector.requests.Session.get")
    def test_search_repos_success(self, mock_get):
        """Test successful repo search."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": "user/repo1",
                    "name": "repo1",
                    "html_url": "https://github.com/user/repo1",
                    "stargazers_count": 5000,
                    "language": "Python",
                }
            ]
        }
        mock_get.return_value = mock_response

        collector = GitHubCollector()
        repos = collector._search_repos("stars:>1000", "test")

        assert len(repos) == 1
        assert repos[0].title is not None
        mock_get.assert_called_once()

    @patch("app.collectors.github_collector.requests.Session.get")
    def test_search_repos_multiple_results(self, mock_get):
        """Test search with multiple results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": f"user/repo{i}",
                    "name": f"repo{i}",
                    "html_url": f"https://github.com/user/repo{i}",
                }
                for i in range(5)
            ]
        }
        mock_get.return_value = mock_response

        collector = GitHubCollector()
        repos = collector._search_repos("stars:>1000", "test")

        assert len(repos) == 5

    @patch("app.collectors.github_collector.requests.Session.get")
    def test_search_repos_api_error(self, mock_get):
        """Test handling of API errors."""
        import requests
        mock_get.side_effect = requests.RequestException("API Error")

        collector = GitHubCollector()
        with pytest.raises(requests.RequestException):
            collector._search_repos("stars:>1000", "test")

    @patch("app.collectors.github_collector.requests.Session.get")
    def test_search_repos_empty_results(self, mock_get):
        """Test search with no results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response

        collector = GitHubCollector()
        repos = collector._search_repos("stars:>999999999", "test")

        assert len(repos) == 0


class TestFetchAll:
    """Test fetching from all categories."""

    @patch("app.collectors.github_collector.requests.Session.get")
    def test_fetch_all_categories(self, mock_get):
        """Test fetching from multiple categories."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": "user/repo",
                    "name": "repo",
                    "html_url": "https://github.com/user/repo",
                }
            ]
        }
        mock_get.return_value = mock_response

        collector = GitHubCollector()
        repos = collector.fetch_all()

        # Should search multiple categories
        assert len(repos) >= 1
        assert mock_get.call_count >= len(collector.SEARCH_QUERIES)

    @patch("app.collectors.github_collector.requests.Session.get")
    def test_fetch_all_respects_max_results(self, mock_get):
        """Test that fetch_all respects max_results limit."""
        mock_response = MagicMock()
        # Return 30 results per query
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": f"user/repo_{j}",
                    "name": f"repo_{j}",
                    "html_url": f"https://github.com/user/repo_{j}",
                }
                for j in range(30)
            ]
        }
        mock_get.return_value = mock_response

        collector = GitHubCollector(max_results=50)
        repos = collector.fetch_all()

        assert len(repos) <= 50

    @patch("app.collectors.github_collector.requests.Session.get")
    def test_fetch_all_deduplicates(self, mock_get):
        """Test that duplicate repos are filtered."""
        # Return same repo multiple times
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": "user/repo",
                    "name": "repo",
                    "html_url": "https://github.com/user/repo",
                }
            ]
        }
        mock_get.return_value = mock_response

        collector = GitHubCollector()
        repos = collector.fetch_all()

        # Count repos with same full_name
        repo_names = [r.metadata["repo_full_name"] for r in repos]
        assert len(repo_names) == len(set(repo_names))  # All unique


class TestJSONOutput:
    """Test JSON serialization."""

    def test_to_json_string(self):
        """Test converting repos to JSON string."""
        repo_article = Article(
            source="github",
            id="123",
            title="Test Repo",
            url="https://github.com/user/repo",
            summary="Test repository",
            published_at="2024-01-01T00:00:00",
            category="repository",
            tags=["ai", "python"],
            metadata={"stars": 1000},
        )

        collector = GitHubCollector()
        collector.articles = [repo_article]
        json_str = collector.to_json_string()

        # Should be valid JSON
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]["title"] == "Test Repo"
        assert data[0]["metadata"]["stars"] == 1000

    def test_save_to_json(self):
        """Test saving repos to JSON file."""
        repo_article = Article(
            source="github",
            id="123",
            title="Test Repo",
            url="https://github.com/user/repo",
            summary="A test repository",
            published_at="2024-01-01T00:00:00",
            category="repository",
            metadata={"repo_full_name": "user/repo"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = GitHubCollector()
            collector.articles = [repo_article]
            filepath = collector.save_to_json(output_dir=tmpdir)

            # File should exist
            assert Path(filepath).exists()

            # Should contain valid JSON
            with open(filepath, "r") as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["title"] == "Test Repo"

    def test_save_creates_directory(self):
        """Test that save_to_json creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "new" / "path"
            assert not nonexistent_dir.exists()

            collector = GitHubCollector()
            collector.articles = []
            collector.save_to_json(output_dir=str(nonexistent_dir))

            assert nonexistent_dir.exists()


class TestIntegration:
    """Integration tests."""

    @patch("app.collectors.github_collector.requests.Session.get")
    def test_full_pipeline(self, mock_get):
        """Test full fetch, normalize, save pipeline."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": "anthropics/claude",
                    "name": "claude",
                    "html_url": "https://github.com/anthropics/claude",
                    "description": "Claude AI",
                    "stargazers_count": 50000,
                    "language": "Python",
                    "created_at": "2023-01-01T00:00:00Z",
                    "owner": {"login": "anthropics"},
                    "topics": ["ai", "llm"],
                }
            ]
        }
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = GitHubCollector()
            repos = collector.fetch_all()
            filepath = collector.save_to_json(output_dir=tmpdir)

            assert len(repos) >= 1
            assert Path(filepath).exists()

            with open(filepath) as f:
                data = json.load(f)
            assert data[0]["source"] == "github"
            assert "claude" in data[0]["title"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
