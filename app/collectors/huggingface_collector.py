"""
Hugging Face Collector — Fetch trending ML models from Hugging Face Hub.

Uses official Hugging Face Hub API (no authentication required).
Searches: Models by task and trending status.
Output: Normalized Article objects (models as articles).
"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from dataclasses import asdict
from pathlib import Path
import hashlib
from urllib.parse import urlencode

import requests

from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)

# Hugging Face Hub API
HF_API_BASE = "https://huggingface.co/api"
MODELS_ENDPOINT = f"{HF_API_BASE}/models"


class HuggingFaceCollector:
    """Collect trending ML models from Hugging Face Hub."""

    # Model tasks to fetch
    TASKS = {
        "text-generation": "Text Generation",
        "image-classification": "Image Classification",
        "token-classification": "Token Classification",
        "question-answering": "Question Answering",
        "text-classification": "Text Classification",
        "summarization": "Summarization",
        "translation": "Machine Translation",
        "object-detection": "Object Detection",
        "image-to-text": "Image to Text",
        "text-to-image": "Text to Image",
    }

    def __init__(self, max_models_per_task: int = 30, max_total: int = 150, sort_by: str = "trending"):
        """
        Initialize Hugging Face collector.

        Args:
            max_models_per_task: Maximum models per task.
            max_total: Maximum total models to collect.
            sort_by: Sort order - "trending", "downloads", "likes", "created_at"
        """
        self.max_models_per_task = max_models_per_task
        self.max_total = max_total
        self.sort_by = sort_by
        self.articles: List[Article] = []
        self.session = requests.Session()

    def fetch_all(self) -> List[Article]:
        """
        Fetch models from all tasks.

        Returns:
            List of normalized Article objects.
        """
        self.articles = []
        seen_models = set()  # Track by model ID to avoid duplicates

        for task_code, task_name in self.TASKS.items():
            try:
                logger.info(f"Searching Hugging Face for {task_name}...")
                models = self._search_task(task_code, task_name, seen_models)

                for model in models:
                    model_id = model.metadata.get("hf_model_id")
                    if model_id not in seen_models:
                        seen_models.add(model_id)
                        self.articles.append(model)

                logger.info(f"✓ {task_code}: {len(models)} models added")

            except Exception as e:
                logger.error(f"✗ {task_code} search failed: {e}")

        # Limit to max_total
        self.articles = self.articles[: self.max_total]
        return self.articles

    def _search_task(self, task: str, task_name: str, seen_ids: set) -> List[Article]:
        """
        Search Hugging Face for models in a task.

        Args:
            task: Task name (e.g., "text-generation").
            task_name: Human-readable task name.
            seen_ids: Set of already-seen model IDs to skip.

        Returns:
            List of Article objects.
        """
        params = {
            "task": task,
            "limit": self.max_models_per_task,
            "full": True,  # Get full model details
        }

        # Add sort parameter
        if self.sort_by in ("trending", "downloads", "likes"):
            params["sort"] = self.sort_by
        elif self.sort_by == "created_at":
            params["sort"] = "created"

        try:
            url = MODELS_ENDPOINT
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to fetch from Hugging Face: {e}")
            raise

        articles = []
        models_list = data if isinstance(data, list) else []

        for model_data in models_list:
            try:
                model_id = model_data.get("id", "")
                if model_id in seen_ids:
                    continue

                article = self._normalize_model(model_data, task, task_name)
                if article:
                    articles.append(article)

            except Exception as e:
                logger.warning(f"Failed to normalize model: {e}")

        return articles

    @staticmethod
    def _normalize_model(model_data: dict, task: str, task_name: str) -> Optional[Article]:
        """
        Normalize a Hugging Face model to Article schema.

        Args:
            model_data: Model data from API.
            task: Task code.
            task_name: Human-readable task name.

        Returns:
            Normalized Article or None.
        """
        try:
            model_id = model_data.get("id", "")
            if not model_id:
                return None

            article_id = hashlib.sha256(model_id.encode()).hexdigest()[:12]

            # Model name and organization
            org_and_name = model_id.split("/")
            if len(org_and_name) == 2:
                org, name = org_and_name
            else:
                org = "unknown"
                name = model_id

            title = f"[{task.upper()}] {name}"

            # Description
            description = model_data.get("description", "")
            if not description:
                description = model_data.get("private", False) and "Private model" or "Hugging Face model"

            # Build summary with metrics
            downloads = model_data.get("downloads", 0)
            likes = model_data.get("likes", 0)
            created_at = model_data.get("created_at", "")

            summary_parts = [
                f"⬇️ {downloads:,} downloads" if downloads > 0 else "⬇️ 0 downloads",
                f"❤️ {likes} likes" if likes > 0 else "❤️ 0 likes",
            ]

            if model_data.get("gated"):
                summary_parts.append("🔐 Gated")

            summary = " | ".join(summary_parts)

            # Published date
            published_at = created_at
            if published_at and "T" in published_at:
                published_at = published_at.split("T")[0] + "T00:00:00"
            elif not published_at:
                published_at = datetime.now().isoformat()

            # Author
            author = org if org != "unknown" else None

            # Tags
            tags = [task, "huggingface", "model"]
            if model_data.get("gated"):
                tags.append("gated")
            if model_data.get("private"):
                tags.append("private")

            # Model card URL
            url = f"https://huggingface.co/{model_id}"

            # Get library/framework
            library = model_data.get("library_name", "")

            return Article(
                source="huggingface",
                id=article_id,
                title=title,
                url=url,
                summary=summary,
                published_at=published_at,
                author=author,
                category="ml-model",
                tags=tags,
                metadata={
                    "hf_model_id": model_id,
                    "hf_org": org,
                    "hf_name": name,
                    "downloads": downloads,
                    "likes": likes,
                    "task": task,
                    "task_name": task_name,
                    "library": library,
                    "gated": model_data.get("gated", False),
                    "private": model_data.get("private", False),
                    "created_at": created_at,
                    "description": description[:200],  # Truncate for metadata
                    "fetched_at": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            logger.warning(f"Failed to normalize model: {e}")
            return None

    def save_to_json(self, output_dir: str = "data/raw") -> str:
        """
        Save collected models to JSON file.

        Args:
            output_dir: Directory to save to.

        Returns:
            Path to saved file.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(output_dir) / f"huggingface_{timestamp}.json"

        # Convert articles to dicts
        articles_dict = [asdict(article) for article in self.articles]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(articles_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Saved {len(self.articles)} models to {filepath}")
        return str(filepath)

    def to_json_string(self) -> str:
        """Return models as JSON string."""
        articles_dict = [asdict(article) for article in self.articles]
        return json.dumps(articles_dict, indent=2, ensure_ascii=False)


def main():
    """CLI entry point."""
    import sys

    logging.basicConfig(level=logging.INFO)

    collector = HuggingFaceCollector()
    models = collector.fetch_all()

    print(f"\n{'='*60}")
    print(f"✓ Fetched {len(models)} models from Hugging Face")
    print(f"{'='*60}")

    # Save to file
    filepath = collector.save_to_json()

    # Print sample
    if models:
        print(f"\n🤖 Sample models:")
        for model in models[:5]:
            meta = model.metadata
            print(f"  • {model.title}")
            print(f"    ⬇️ {meta.get('downloads', 0):,} downloads | ❤️ {meta.get('likes', 0)} likes")
            print(f"    📚 {meta.get('library', 'unknown').title()}")
            print(f"    🔗 {model.url}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
