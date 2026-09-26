"""
Collectors module — Data source integrations.
"""

from app.collectors.rss_collector import RSSCollector, Article
from app.collectors.github_collector import GitHubCollector

__all__ = ["RSSCollector", "GitHubCollector", "Article"]
