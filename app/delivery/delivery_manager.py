"""
Delivery Manager — Orchestrate multi-channel digest delivery.

Handles:
- Channel selection and configuration
- Delivery preferences per user/channel
- Unified delivery interface
- Delivery tracking and logging
- Retry coordination
- Statistics aggregation
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from app.delivery.email_service import (
    SMTPEmailService,
    SMTPConfig,
    EmailMessage,
    EmailTemplateEngine,
    EmailStatus,
)
from app.delivery.slack_service import (
    SlackService,
    SlackConfig,
    SlackMessage,
    SlackMessageBuilder,
)
from app.delivery.webhook_service import (
    WebhookService,
    WebhookConfig,
    WebhookPayload,
    WebhookEventType,
)
from app.generators.digest_generator import DigestFormat, DigestMetadata, DigestSection

logger = logging.getLogger(__name__)


class DeliveryChannel(Enum):
    """Supported delivery channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


@dataclass
class DeliveryPreferences:
    """User delivery preferences."""

    user_id: str
    email_enabled: bool = True
    slack_enabled: bool = False
    webhook_enabled: bool = False
    email_frequency: str = "daily"  # daily, weekly, never
    slack_channel: Optional[str] = None
    webhook_ids: List[str] = field(default_factory=list)
    digest_format: str = "email_html"  # email_html, markdown, json
    include_critical_only: bool = False
    max_articles: int = 50
    unsubscribed_at: Optional[datetime] = None

    @property
    def is_subscribed(self) -> bool:
        """Check if user is subscribed to any channel."""
        return (
            self.email_enabled
            or self.slack_enabled
            or self.webhook_enabled
        ) and not self.unsubscribed_at


@dataclass
class DeliveryJob:
    """Delivery job for a digest."""

    job_id: str
    digest_id: str
    user_id: str
    channels: List[DeliveryChannel]
    preferences: DeliveryPreferences
    digest_title: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, in_progress, completed, failed


@dataclass
class DeliveryReport:
    """Report of delivery results."""

    job_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    channels_attempted: int = 0
    channels_succeeded: int = 0
    channels_failed: int = 0
    email_result: Optional[Any] = None
    slack_result: Optional[Any] = None
    webhook_results: List[Any] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.channels_attempted == 0:
            return 0.0

        return self.channels_succeeded / self.channels_attempted

    @property
    def all_succeeded(self) -> bool:
        """Check if all channels succeeded."""
        return self.channels_succeeded == self.channels_attempted


class DeliveryManager:
    """Orchestrate multi-channel delivery."""

    def __init__(self):
        """Initialize delivery manager."""
        self.email_service: Optional[SMTPEmailService] = None
        self.slack_service: Optional[SlackService] = None
        self.webhook_service = WebhookService()
        self.delivery_history: List[DeliveryReport] = []

    def configure_email(self, config: SMTPConfig) -> bool:
        """Configure email delivery."""
        self.email_service = SMTPEmailService(config)
        return self.email_service.validate_config()

    def configure_slack(self, config: SlackConfig) -> bool:
        """Configure Slack delivery."""
        self.slack_service = SlackService(config)
        return self.slack_service.validate_config()

    def register_webhook(self, webhook_id: str, config: WebhookConfig) -> bool:
        """Register webhook."""
        return self.webhook_service.register_webhook(webhook_id, config)

    def deliver_digest(
        self,
        digest: Dict[str, Any],
        email_addresses: Optional[List[str]] = None,
        slack_channel: Optional[str] = None,
        webhook_ids: Optional[List[str]] = None,
    ) -> DeliveryReport:
        """
        Deliver digest across specified channels.

        Args:
            digest: Digest to deliver.
            email_addresses: Email addresses to send to.
            slack_channel: Slack channel to post to.
            webhook_ids: Webhook IDs to send to.

        Returns:
            DeliveryReport.
        """
        job_id = f"delivery_{datetime.now(timezone.utc).timestamp()}"
        report = DeliveryReport(job_id=job_id)

        logger.info(f"Starting delivery job {job_id}")

        # Email delivery
        if email_addresses:
            report.channels_attempted += 1
            try:
                email_result = self._deliver_via_email(digest, email_addresses)
                report.email_result = email_result

                if all(r.status == EmailStatus.DELIVERED for r in email_result):
                    report.channels_succeeded += 1
                else:
                    report.channels_failed += 1
                    failed_emails = [r.to_address for r in email_result if r.status != EmailStatus.DELIVERED]
                    report.errors.append(f"Failed to deliver to: {', '.join(failed_emails)}")

            except Exception as e:
                report.channels_failed += 1
                report.errors.append(f"Email delivery error: {str(e)}")
                logger.error(f"Email delivery failed: {e}", exc_info=True)

        # Slack delivery
        if slack_channel:
            report.channels_attempted += 1
            try:
                slack_result = self._deliver_via_slack(digest, slack_channel)
                report.slack_result = slack_result

                if slack_result:
                    report.channels_succeeded += 1
                else:
                    report.channels_failed += 1
                    report.errors.append("Slack delivery failed")

            except Exception as e:
                report.channels_failed += 1
                report.errors.append(f"Slack delivery error: {str(e)}")
                logger.error(f"Slack delivery failed: {e}", exc_info=True)

        # Webhook delivery
        if webhook_ids:
            for webhook_id in webhook_ids:
                report.channels_attempted += 1
                try:
                    webhook_result = self._deliver_via_webhook(digest, webhook_id)
                    report.webhook_results.append(webhook_result)

                    if webhook_result:
                        report.channels_succeeded += 1
                    else:
                        report.channels_failed += 1

                except Exception as e:
                    report.channels_failed += 1
                    report.errors.append(f"Webhook {webhook_id} error: {str(e)}")
                    logger.error(f"Webhook delivery failed: {e}", exc_info=True)

        report.completed_at = datetime.now(timezone.utc)
        self.delivery_history.append(report)

        logger.info(
            f"Delivery job {job_id} completed: "
            f"{report.channels_succeeded}/{report.channels_attempted} channels succeeded"
        )

        return report

    def _deliver_via_email(self, digest: Dict[str, Any], email_addresses: List[str]) -> List[Any]:
        """Deliver via email."""
        if not self.email_service:
            raise ValueError("Email service not configured")

        results = []

        # Build email HTML
        email_html = self._build_email_html(digest)

        for email_address in email_addresses:
            digest_title = digest.get("title", "Your AI RADAR Digest")
            email = EmailMessage.create(
                subject=f"{digest_title}",
                to_address=email_address,
                html_content=email_html,
            )

            result = self.email_service.send(email)
            results.append(result)

        return results

    def _deliver_via_slack(self, digest: Dict[str, Any], channel: str) -> Optional[Any]:
        """Deliver via Slack."""
        if not self.slack_service:
            raise ValueError("Slack service not configured")

        # Build Slack message
        critical_count = digest.get("critical_count", 0)
        featured_count = digest.get("featured_count", 0)
        relevant_count = digest.get("relevant_count", 0)
        read_time = digest.get("read_time_minutes", 10)

        message = SlackMessageBuilder.build_digest_summary(
            critical_count=critical_count,
            featured_count=featured_count,
            relevant_count=relevant_count,
            read_time_minutes=read_time,
        )

        message.channel = channel

        result = self.slack_service.send(message)
        return result if result else None

    def _deliver_via_webhook(self, digest: Dict[str, Any], webhook_id: str) -> Optional[Any]:
        """Deliver via webhook."""
        payload = WebhookPayload(
            event_type=WebhookEventType.DIGEST_SENT,
            data={
                "digest_id": digest.get("id", "unknown"),
                "article_count": digest.get("article_count", 0),
                "read_time_minutes": digest.get("read_time_minutes", 10),
            },
        )

        result = self.webhook_service.send_event(webhook_id, payload)
        return result if result else None

    def _build_email_html(self, digest: Dict[str, Any]) -> str:
        """Build HTML email from digest."""
        # Extract sections from digest
        critical_html = digest.get("critical_html", "<p>No critical articles</p>")
        featured_html = digest.get("featured_html", "<p>No featured articles</p>")
        relevant_html = digest.get("relevant_html", "<p>No relevant articles</p>")
        discover_html = digest.get("discover_html", "")

        return EmailTemplateEngine.render_digest_email(
            digest_title=digest.get("title", "Your AI RADAR Digest"),
            critical_section=critical_html,
            featured_section=featured_html,
            relevant_section=relevant_html,
            discover_section=discover_html if discover_html else None,
            read_time_minutes=digest.get("read_time_minutes", 10),
        )

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get aggregated delivery statistics."""
        if not self.delivery_history:
            return {
                "total_jobs": 0,
                "successful_jobs": 0,
                "failed_jobs": 0,
                "channels_total": 0,
                "channels_succeeded": 0,
                "channels_failed": 0,
            }

        total_jobs = len(self.delivery_history)
        successful_jobs = sum(1 for r in self.delivery_history if r.all_succeeded)
        failed_jobs = sum(1 for r in self.delivery_history if not r.all_succeeded)

        channels_total = sum(r.channels_attempted for r in self.delivery_history)
        channels_succeeded = sum(r.channels_succeeded for r in self.delivery_history)
        channels_failed = sum(r.channels_failed for r in self.delivery_history)

        return {
            "total_jobs": total_jobs,
            "successful_jobs": successful_jobs,
            "failed_jobs": failed_jobs,
            "channels_total": channels_total,
            "channels_succeeded": channels_succeeded,
            "channels_failed": channels_failed,
            "channel_success_rate": channels_succeeded / channels_total if channels_total > 0 else 0.0,
            "job_success_rate": successful_jobs / total_jobs if total_jobs > 0 else 0.0,
        }


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)

    manager = DeliveryManager()

    # Configure email
    email_config = SMTPConfig(
        server="smtp.gmail.com",
        port=587,
        username="your-email@gmail.com",
        password="your-app-password",
        from_address="your-email@gmail.com",
    )
    manager.configure_email(email_config)

    print("✓ Delivery manager initialized")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
