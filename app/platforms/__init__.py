"""
Platforms module — Platform-specific integrations (Twitter/X, etc).

Exports:
- X/Twitter: Tweet generation, threading, scheduling
"""

from app.platforms.x_config import (
    XContentGenerator,
    XConfigurationManager,
    XAPIConfig,
    XPreferences,
    Tweet,
    TweetType,
    SchedulingFrequency,
)

__all__ = [
    "XContentGenerator",
    "XConfigurationManager",
    "XAPIConfig",
    "XPreferences",
    "Tweet",
    "TweetType",
    "SchedulingFrequency",
]
