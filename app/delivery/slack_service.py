"""
Slack Notification Service — Send digest summaries to Slack.

Handles:
- Webhook integration
- Message formatting
- Thread support
- Reaction emoji
- File uploads
- Channel/user targeting
"""

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import requests

logger = logging.getLogger(__name__)


class SlackMessageType(Enum):
    """Type of Slack message."""
    SUMMARY = "summary"  # Brief digest summary
    DETAILED = "detailed"  # Full digest with links
    ALERT = "alert"  # Critical articles alert
    THREAD = "thread"  # Multi-message thread


class SlackStatus(Enum):
    """Slack delivery status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class SlackConfig:
    """Slack webhook configuration."""

    webhook_url: str = ""
    channel: str = "#general"  # Default channel
    username: str = "AI RADAR"
    icon_emoji: str = ":radar:"
    thread_ts: Optional[str] = None  # Thread timestamp for replies
    unfurl_links: bool = False
    unfurl_media: bool = False

    def validate(self) -> bool:
        """Validate Slack configuration."""
        return bool(self.webhook_url and self.webhook_url.startswith("https://hooks.slack.com"))


@dataclass
class SlackMessage:
    """Slack message to send."""

    text: str
    message_type: SlackMessageType = SlackMessageType.SUMMARY
    channel: Optional[str] = None
    thread_ts: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    blocks: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_attachment(
        self,
        title: str,
        text: str,
        color: str = "#3498db",
        title_link: Optional[str] = None,
        fields: Optional[List[Dict]] = None,
    ) -> "SlackMessage":
        """Add attachment to message."""
        attachment = {
            "color": color,
            "title": title,
            "text": text,
        }

        if title_link:
            attachment["title_link"] = title_link

        if fields:
            attachment["fields"] = fields

        self.attachments.append(attachment)
        return self

    def add_section_block(self, text: str) -> "SlackMessage":
        """Add section block."""
        self.blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        })
        return self

    def add_divider_block(self) -> "SlackMessage":
        """Add divider block."""
        self.blocks.append({"type": "divider"})
        return self


@dataclass
class SlackDeliveryResult:
    """Result of Slack delivery attempt."""

    message_id: str
    status: SlackStatus
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    response_ts: Optional[str] = None  # Slack message timestamp
    channel: Optional[str] = None


class SlackService:
    """Send notifications to Slack."""

    def __init__(self, config: SlackConfig):
        """
        Initialize Slack service.

        Args:
            config: Slack webhook configuration.
        """
        self.config = config
        self.delivery_history: List[SlackDeliveryResult] = []

    def validate_config(self) -> bool:
        """Validate Slack configuration."""
        if not self.config.validate():
            logger.error("Invalid Slack configuration")
            return False

        return True

    def _build_payload(self, message: SlackMessage) -> Dict[str, Any]:
        """Build Slack API payload."""
        payload = {
            "text": message.text,
            "username": self.config.username,
            "icon_emoji": self.config.icon_emoji,
        }

        if message.channel or self.config.channel:
            payload["channel"] = message.channel or self.config.channel

        if message.thread_ts or self.config.thread_ts:
            payload["thread_ts"] = message.thread_ts or self.config.thread_ts

        if message.blocks:
            payload["blocks"] = message.blocks

        if message.attachments:
            payload["attachments"] = message.attachments

        payload["unfurl_links"] = self.config.unfurl_links
        payload["unfurl_media"] = self.config.unfurl_media

        return payload

    def send(self, message: SlackMessage) -> SlackDeliveryResult:
        """
        Send Slack message.

        Args:
            message: Slack message to send.

        Returns:
            SlackDeliveryResult with status.
        """
        if not self.validate_config():
            return SlackDeliveryResult(
                message_id=f"slack_{datetime.now(timezone.utc).timestamp()}",
                status=SlackStatus.FAILED,
                error="Invalid Slack configuration",
            )

        result = SlackDeliveryResult(
            message_id=f"slack_{datetime.now(timezone.utc).timestamp()}",
            status=SlackStatus.PENDING,
            channel=message.channel or self.config.channel,
        )

        try:
            payload = self._build_payload(message)

            response = requests.post(
                self.config.webhook_url,
                json=payload,
                timeout=10,
            )

            response.raise_for_status()

            result.status = SlackStatus.SENT
            logger.info(f"Slack message sent to {result.channel}")

        except requests.exceptions.RequestException as e:
            result.status = SlackStatus.FAILED
            result.error = f"Request error: {str(e)}"
            logger.error(f"Slack send error: {e}")

        except Exception as e:
            result.status = SlackStatus.FAILED
            result.error = f"Unexpected error: {str(e)}"
            logger.error(f"Slack error: {e}", exc_info=True)

        self.delivery_history.append(result)
        return result

    def send_batch(self, messages: List[SlackMessage]) -> List[SlackDeliveryResult]:
        """Send multiple Slack messages."""
        results = []

        for message in messages:
            result = self.send(message)
            results.append(result)

        return results

    def get_delivery_stats(self) -> Dict:
        """Get delivery statistics."""
        if not self.delivery_history:
            return {
                "total": 0,
                "sent": 0,
                "failed": 0,
                "success_rate": 0.0,
            }

        total = len(self.delivery_history)
        sent = sum(1 for r in self.delivery_history if r.status == SlackStatus.SENT)
        failed = sum(1 for r in self.delivery_history if r.status == SlackStatus.FAILED)

        return {
            "total": total,
            "sent": sent,
            "failed": failed,
            "success_rate": sent / total if total > 0 else 0.0,
        }


class SlackMessageBuilder:
    """Build formatted Slack messages from digest data."""

    @staticmethod
    def build_digest_summary(
        critical_count: int,
        featured_count: int,
        relevant_count: int,
        read_time_minutes: int = 10,
    ) -> SlackMessage:
        """Build digest summary message."""
        text = f"""🔔 Your AI RADAR Daily Digest
{critical_count} 🔥 critical • {featured_count} ⭐ featured • {relevant_count} 📖 relevant
Est. read time: {read_time_minutes} min"""

        message = SlackMessage(
            text=text,
            message_type=SlackMessageType.SUMMARY,
        )

        return message

    @staticmethod
    def build_critical_alert(
        title: str,
        source: str,
        url: str,
    ) -> SlackMessage:
        """Build critical article alert."""
        message = SlackMessage(
            text=f"🔥 CRITICAL: {title}",
            message_type=SlackMessageType.ALERT,
        )

        message.add_attachment(
            title=title,
            text=f"Source: {source}",
            color="#e74c3c",
            title_link=url,
        )

        return message

    @staticmethod
    def build_article_message(
        title: str,
        summary: str,
        url: str,
        source: str,
        author: Optional[str] = None,
        emoji: str = "📰",
    ) -> SlackMessage:
        """Build article notification message."""
        message = SlackMessage(
            text=f"{emoji} {title}",
        )

        fields = [
            {
                "title": "Source",
                "value": source,
                "short": True,
            },
        ]

        if author:
            fields.append({
                "title": "Author",
                "value": author,
                "short": True,
            })

        message.add_attachment(
            title=title,
            text=summary,
            title_link=url,
            fields=fields,
        )

        return message


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)

    config = SlackConfig(
        webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    )

    service = SlackService(config)

    message = SlackMessageBuilder.build_digest_summary(
        critical_count=2,
        featured_count=5,
        relevant_count=10,
    )

    result = service.send(message)
    print(f"Delivery status: {result.status.value}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
