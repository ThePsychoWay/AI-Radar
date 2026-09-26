"""
Collectors module — Data source integrations.
"""

from app.collectors.rss_collector import RSSCollector, Article
from app.collectors.github_collector import GitHubCollector
from app.collectors.hackernews_collector import HackerNewsCollector

__all__ = ["RSSCollector", "GitHubCollector", "HackerNewsCollector", "Article"]
