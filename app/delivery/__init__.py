"""
Delivery module — Multi-channel digest delivery.

Exports:
- Email: SMTP email delivery with templates
- Slack: Slack notifications and message building
- Webhooks: Custom webhook integration with signing
- DeliveryManager: Orchestrate multi-channel delivery
"""

from app.delivery.email_service import (
    SMTPEmailService,
    SMTPConfig,
    EmailMessage,
    EmailStatus,
    EmailTemplateEngine,
)

from app.delivery.slack_service import (
    SlackService,
    SlackConfig,
    SlackMessage,
    SlackMessageType,
    SlackMessageBuilder,
)

from app.delivery.webhook_service import (
    WebhookService,
    WebhookConfig,
    WebhookPayload,
    WebhookEventType,
    WebhookSigningService,
)

from app.delivery.delivery_manager import (
    DeliveryManager,
    DeliveryPreferences,
    DeliveryChannel,
    DeliveryJob,
    DeliveryReport,
)

__all__ = [
    "SMTPEmailService",
    "SMTPConfig",
    "EmailMessage",
    "EmailStatus",
    "EmailTemplateEngine",
    "SlackService",
    "SlackConfig",
    "SlackMessage",
    "SlackMessageType",
    "SlackMessageBuilder",
    "WebhookService",
    "WebhookConfig",
    "WebhookPayload",
    "WebhookEventType",
    "WebhookSigningService",
    "DeliveryManager",
    "DeliveryPreferences",
    "DeliveryChannel",
    "DeliveryJob",
    "DeliveryReport",
]
