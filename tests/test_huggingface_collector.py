"""
Unit tests for Hugging Face Collector.

Tests cover:
- Fetching from Hugging Face API
- Normalizing models to Article schema
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

from app.collectors.huggingface_collector import HuggingFaceCollector, Article


class TestHuggingFaceCollectorInitialization:
    """Test HuggingFaceCollector initialization."""

    def test_default_initialization(self):
        """Test creating collector with defaults."""
        collector = HuggingFaceCollector()
        assert len(collector.TASKS) >= 5
        assert "text-generation" in collector.TASKS
        assert "image-classification" in collector.TASKS
        assert collector.max_models_per_task == 30
        assert collector.max_total == 150
        assert collector.sort_by == "trending"

    def test_custom_settings(self):
        """Test custom parameters."""
        collector = HuggingFaceCollector(
            max_models_per_task=50, max_total=200, sort_by="downloads"
        )
        assert collector.max_models_per_task == 50
        assert collector.max_total == 200
        assert collector.sort_by == "downloads"

    def test_sort_by_options(self):
        """Test different sort options."""
        for sort_option in ["trending", "downloads", "likes", "created_at"]:
            collector = HuggingFaceCollector(sort_by=sort_option)
            assert collector.sort_by == sort_option


class TestNormalizeModel:
    """Test model normalization."""

    def test_normalize_basic_model(self):
        """Test normalizing a basic model."""
        model_data = {
            "id": "openai/gpt2",
            "description": "GPT-2 model from OpenAI",
            "downloads": 1000000,
            "likes": 5000,
            "created_at": "2019-02-14T00:00:00Z",
            "library_name": "transformers",
            "gated": False,
            "private": False,
        }

        article = HuggingFaceCollector._normalize_model(
            model_data, "text-generation", "Text Generation"
        )

        assert article.source == "huggingface"
        assert "gpt2" in article.title.lower()
        assert article.author == "openai"
        assert article.category == "ml-model"
        assert "text-generation" in article.tags
        assert "huggingface" in article.tags
        assert article.metadata["downloads"] == 1000000
        assert article.metadata["likes"] == 5000
        assert article.metadata["hf_model_id"] == "openai/gpt2"

    def test_normalize_model_missing_fields(self):
        """Test normalization with missing fields."""
        model_data = {
            "id": "user/model",
        }

        article = HuggingFaceCollector._normalize_model(
            model_data, "text-generation", "Text Generation"
        )

        assert article is not None
        assert article.title is not None
        assert article.metadata["downloads"] == 0
        assert article.metadata["likes"] == 0

    def test_normalize_model_gated(self):
        """Test normalization of gated model."""
        model_data = {
            "id": "meta-llama/Llama-2-70b",
            "description": "Llama 2 70B",
            "downloads": 100000,
            "likes": 2000,
            "created_at": "2023-07-18T00:00:00Z",
            "gated": True,
            "private": False,
        }

        article = HuggingFaceCollector._normalize_model(
            model_data, "text-generation", "Text Generation"
        )

        assert "gated" in article.tags
        assert article.metadata["gated"] is True
        assert "🔐 Gated" in article.summary

    def test_normalize_model_private(self):
        """Test normalization of private model."""
        model_data = {
            "id": "user/private-model",
            "private": True,
        }

        article = HuggingFaceCollector._normalize_model(
            model_data, "text-generation", "Text Generation"
        )

        assert "private" in article.tags
        assert article.metadata["private"] is True

    def test_normalize_model_summary_format(self):
        """Test that summary includes downloads, likes, and gating info."""
        model_data = {
            "id": "openai/gpt2",
            "downloads": 1000000,
            "likes": 5000,
            "gated": True,
        }

        article = HuggingFaceCollector._normalize_model(
            model_data, "text-generation", "Text Generation"
        )

        assert "1,000,000" in article.summary or "1000000" in article.summary
        assert "⬇️" in article.summary
        assert "❤️" in article.summary
        assert "🔐 Gated" in article.summary

    def test_normalize_model_invalid_id(self):
        """Test that models without ID are skipped."""
        model_data = {
            "description": "Model without ID",
        }

        article = HuggingFaceCollector._normalize_model(
            model_data, "text-generation", "Text Generation"
        )

        assert article is None

    def test_normalize_model_url_generation(self):
        """Test that model URL is correctly generated."""
        model_data = {
            "id": "meta-llama/Llama-2-70b-hf",
        }

        article = HuggingFaceCollector._normalize_model(
            model_data, "text-generation", "Text Generation"
        )

        assert article.url == "https://huggingface.co/meta-llama/Llama-2-70b-hf"


class TestSearchTask:
    """Test searching a task."""

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_search_task_success(self, mock_get):
        """Test successful task search."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "model1/name1",
                "description": "Model 1",
                "downloads": 100,
                "likes": 10,
            },
            {
                "id": "model2/name2",
                "description": "Model 2",
                "downloads": 200,
                "likes": 20,
            },
        ]
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector()
        models = collector._search_task("text-generation", "Text Generation", set())

        assert len(models) == 2
        assert models[0].author == "model1"
        assert models[1].author == "model2"

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_search_task_skips_seen_ids(self, mock_get):
        """Test that already-seen models are skipped."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "model1/name1",
                "description": "Model 1",
            },
        ]
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector()
        seen = {"model1/name1"}
        models = collector._search_task("text-generation", "Text Generation", seen)

        assert len(models) == 0

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_search_task_api_error(self, mock_get):
        """Test handling of API errors."""
        import requests

        mock_get.side_effect = requests.RequestException("API Error")

        collector = HuggingFaceCollector()
        with pytest.raises(requests.RequestException):
            collector._search_task("text-generation", "Text Generation", set())

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_search_task_respects_max(self, mock_get):
        """Test that max_models_per_task parameter is used."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector(max_models_per_task=50)
        collector._search_task("text-generation", "Text Generation", set())

        # Check that limit parameter was set
        call_args = mock_get.call_args
        assert call_args[1]["params"]["limit"] == 50


class TestFetchAll:
    """Test fetching all tasks."""

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_fetch_all_multiple_tasks(self, mock_get):
        """Test fetching from multiple tasks."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "model/name",
                "description": "Test model",
            }
        ]
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector()
        models = collector.fetch_all()

        # Should search multiple tasks
        assert len(models) >= 1
        assert mock_get.call_count >= len(collector.TASKS)

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_fetch_all_respects_max_total(self, mock_get):
        """Test that max_total limit is respected."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": f"model{i}/name{i}",
                "description": f"Model {i}",
            }
            for i in range(50)
        ]
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector(max_total=50)
        models = collector.fetch_all()

        assert len(models) <= 50

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_fetch_all_deduplicates(self, mock_get):
        """Test that duplicate models are filtered."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "model/name",
                "description": "Test model",
            }
        ]
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector()
        models = collector.fetch_all()

        # Count models with same ID
        model_ids = [m.metadata["hf_model_id"] for m in models]
        assert len(model_ids) == len(set(model_ids))  # All unique


class TestSortOptions:
    """Test different sorting options."""

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_sort_by_trending(self, mock_get):
        """Test sort by trending."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector(sort_by="trending")
        collector._search_task("text-generation", "Text Generation", set())

        call_args = mock_get.call_args
        assert call_args[1]["params"]["sort"] == "trending"

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_sort_by_downloads(self, mock_get):
        """Test sort by downloads."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector(sort_by="downloads")
        collector._search_task("text-generation", "Text Generation", set())

        call_args = mock_get.call_args
        assert call_args[1]["params"]["sort"] == "downloads"

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_sort_by_created_at(self, mock_get):
        """Test sort by created_at."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        collector = HuggingFaceCollector(sort_by="created_at")
        collector._search_task("text-generation", "Text Generation", set())

        call_args = mock_get.call_args
        assert call_args[1]["params"]["sort"] == "created"


class TestJSONOutput:
    """Test JSON serialization."""

    def test_to_json_string(self):
        """Test converting models to JSON string."""
        model_article = Article(
            source="huggingface",
            id="123",
            title="[TEXT-GENERATION] GPT-2",
            url="https://huggingface.co/openai/gpt2",
            summary="⬇️ 1,000,000 downloads | ❤️ 5,000 likes",
            published_at="2019-02-14T00:00:00",
            category="ml-model",
            tags=["text-generation", "huggingface"],
            metadata={
                "hf_model_id": "openai/gpt2",
                "downloads": 1000000,
                "likes": 5000,
            },
        )

        collector = HuggingFaceCollector()
        collector.articles = [model_article]
        json_str = collector.to_json_string()

        # Should be valid JSON
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]["title"] == "[TEXT-GENERATION] GPT-2"
        assert data[0]["metadata"]["downloads"] == 1000000

    def test_save_to_json(self):
        """Test saving models to JSON file."""
        model_article = Article(
            source="huggingface",
            id="123",
            title="Test Model",
            url="https://huggingface.co/user/model",
            summary="⬇️ 100 downloads",
            published_at="2024-01-01T00:00:00",
            category="ml-model",
            metadata={"hf_model_id": "user/model"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = HuggingFaceCollector()
            collector.articles = [model_article]
            filepath = collector.save_to_json(output_dir=tmpdir)

            # File should exist
            assert Path(filepath).exists()

            # Should contain valid JSON
            with open(filepath, "r") as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["title"] == "Test Model"

    def test_save_creates_directory(self):
        """Test that save_to_json creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "new" / "path"
            assert not nonexistent_dir.exists()

            collector = HuggingFaceCollector()
            collector.articles = []
            collector.save_to_json(output_dir=str(nonexistent_dir))

            assert nonexistent_dir.exists()


class TestIntegration:
    """Integration tests."""

    @patch("app.collectors.huggingface_collector.requests.Session.get")
    def test_full_pipeline(self, mock_get):
        """Test full fetch, normalize, save pipeline."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "openai/gpt2",
                "description": "GPT-2 model from OpenAI",
                "downloads": 1000000,
                "likes": 5000,
                "created_at": "2019-02-14T00:00:00Z",
                "library_name": "transformers",
                "gated": False,
                "private": False,
            }
        ]
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = HuggingFaceCollector()
            models = collector.fetch_all()
            filepath = collector.save_to_json(output_dir=tmpdir)

            assert len(models) >= 1
            assert Path(filepath).exists()

            with open(filepath) as f:
                data = json.load(f)
            assert data[0]["source"] == "huggingface"
            assert "gpt2" in data[0]["title"].lower()
            assert "openai" in data[0]["author"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
