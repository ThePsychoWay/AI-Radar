"""
Tests for Delivery Services.

Covers:
- Email delivery (SMTP, templates, validation)
- Slack notifications (message building, delivery)
- Webhook integration (signing, retry logic)
- Delivery manager orchestration
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from app.delivery.email_service import (
    SMTPConfig,
    SMTPEmailService,
    EmailMessage,
    EmailStatus,
    EmailTemplateEngine,
)
from app.delivery.slack_service import (
    SlackConfig,
    SlackService,
    SlackMessage,
    SlackMessageType,
    SlackStatus,
    SlackMessageBuilder,
)
from app.delivery.webhook_service import (
    WebhookConfig,
    WebhookService,
    WebhookPayload,
    WebhookEventType,
    WebhookStatus,
    WebhookSigningService,
)
from app.delivery.delivery_manager import (
    DeliveryManager,
    DeliveryPreferences,
    DeliveryChannel,
)


class TestSMTPConfig:
    """Tests for SMTP configuration."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = SMTPConfig()
        assert config.server == "smtp.gmail.com"
        assert config.port == 587
        assert config.use_tls

    def test_validate_valid(self):
        """Should validate valid config."""
        config = SMTPConfig(
            server="smtp.gmail.com",
            port=587,
            username="user@gmail.com",
            password="password",
            from_address="user@gmail.com",
        )
        assert config.validate()

    def test_validate_invalid(self):
        """Should reject invalid config."""
        config = SMTPConfig(username="user")
        assert not config.validate()


class TestEmailMessage:
    """Tests for email messages."""

    def test_create_simple(self):
        """Should create simple email."""
        email = EmailMessage.create(
            subject="Test",
            to_address="user@example.com",
            html_content="<h1>Test</h1>",
        )

        assert email.subject == "Test"
        assert email.to_address == "user@example.com"
        assert email.html_content == "<h1>Test</h1>"

    def test_add_recipient(self):
        """Should support CC/BCC."""
        email = EmailMessage.create(
            subject="Test",
            to_address="user@example.com",
            html_content="Test",
        )

        email.cc_addresses.append("cc@example.com")
        email.bcc_addresses.append("bcc@example.com")

        assert len(email.cc_addresses) == 1
        assert len(email.bcc_addresses) == 1

    def test_add_attachment(self):
        """Should add attachments."""
        email = EmailMessage.create(
            subject="Test",
            to_address="user@example.com",
            html_content="Test",
        )

        email.add_attachment("file.txt", b"content", "text/plain")

        assert len(email.attachments) == 1
        assert email.attachments[0][0] == "file.txt"

    def test_html_to_text_conversion(self):
        """Should convert HTML to text."""
        html = "<h1>Title</h1><p>Content</p>"
        text = EmailMessage._html_to_text(html)

        assert "Title" in text
        assert "Content" in text
        assert "<h1>" not in text


class TestSlackConfig:
    """Tests for Slack configuration."""

    def test_default_config(self):
        """Should have defaults."""
        config = SlackConfig()
        assert config.channel == "#general"
        assert config.username == "AI RADAR"

    def test_validate_valid(self):
        """Should validate valid config."""
        config = SlackConfig(webhook_url="https://hooks.slack.com/services/T00/B00/X00")
        assert config.validate()

    def test_validate_invalid(self):
        """Should reject invalid config."""
        config = SlackConfig(webhook_url="invalid")
        assert not config.validate()


class TestSlackMessage:
    """Tests for Slack messages."""

    def test_create_simple(self):
        """Should create simple message."""
        msg = SlackMessage(text="Hello Slack")
        assert msg.text == "Hello Slack"

    def test_add_attachment(self):
        """Should add attachment."""
        msg = SlackMessage(text="Test")
        msg.add_attachment(
            title="Article",
            text="Summary",
            title_link="https://example.com",
        )

        assert len(msg.attachments) == 1

    def test_add_blocks(self):
        """Should add section blocks."""
        msg = SlackMessage(text="Test")
        msg.add_section_block("*Bold* text")
        msg.add_divider_block()

        assert len(msg.blocks) == 2


class TestSlackMessageBuilder:
    """Tests for Slack message builder."""

    def test_build_digest_summary(self):
        """Should build summary message."""
        msg = SlackMessageBuilder.build_digest_summary(
            critical_count=2,
            featured_count=5,
            relevant_count=10,
        )

        assert msg.message_type == SlackMessageType.SUMMARY
        assert "2 🔥" in msg.text
        assert "5 ⭐" in msg.text

    def test_build_critical_alert(self):
        """Should build critical alert."""
        msg = SlackMessageBuilder.build_critical_alert(
            title="Breaking News",
            source="TechCrunch",
            url="https://techcrunch.com",
        )

        assert msg.message_type == SlackMessageType.ALERT
        assert "🔥" in msg.text


class TestWebhookSigningService:
    """Tests for webhook signing."""

    def test_sign_payload(self):
        """Should sign payload."""
        payload = '{"test": "data"}'
        secret = "secret123"

        signature = WebhookSigningService.sign_payload(payload, secret)

        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex is 64 chars

    def test_verify_signature(self):
        """Should verify valid signature."""
        payload = '{"test": "data"}'
        secret = "secret123"

        signature = WebhookSigningService.sign_payload(payload, secret)

        assert WebhookSigningService.verify_signature(payload, signature, secret)

    def test_verify_signature_invalid(self):
        """Should reject invalid signature."""
        payload = '{"test": "data"}'
        secret = "secret123"

        # Wrong signature
        assert not WebhookSigningService.verify_signature(payload, "invalid", secret)

        # Different payload
        assert not WebhookSigningService.verify_signature(
            '{"different": "data"}',
            WebhookSigningService.sign_payload(payload, secret),
            secret,
        )


class TestWebhookConfig:
    """Tests for webhook configuration."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = WebhookConfig(url="https://example.com/webhook")
        assert config.validate()
        assert config.timeout_seconds == 30

    def test_validate_invalid_url(self):
        """Should reject invalid URLs."""
        config = WebhookConfig(url="not-a-url")
        assert not config.validate()


class TestWebhookService:
    """Tests for webhook service."""

    def test_register_webhook(self):
        """Should register webhook."""
        service = WebhookService()
        config = WebhookConfig(url="https://example.com/webhook")

        assert service.register_webhook("test", config)
        assert "test" in service.webhooks

    def test_unregister_webhook(self):
        """Should unregister webhook."""
        service = WebhookService()
        config = WebhookConfig(url="https://example.com/webhook")

        service.register_webhook("test", config)
        assert service.unregister_webhook("test")
        assert "test" not in service.webhooks

    def test_send_event_not_registered(self):
        """Should fail for unregistered webhook."""
        service = WebhookService()
        payload = WebhookPayload(event_type=WebhookEventType.DIGEST_GENERATED)

        result = service.send_event("unknown", payload)

        assert result.status == WebhookStatus.FAILED

    @patch('requests.post')
    def test_send_event_success(self, mock_post):
        """Should send successful event."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        service = WebhookService()
        config = WebhookConfig(url="https://example.com/webhook")
        service.register_webhook("test", config)

        payload = WebhookPayload(event_type=WebhookEventType.DIGEST_GENERATED)
        result = service.send_event("test", payload)

        assert result.status == WebhookStatus.SUCCESS
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_send_event_failure(self, mock_post):
        """Should handle failed event."""
        mock_post.side_effect = Exception("Connection error")

        service = WebhookService()
        config = WebhookConfig(url="https://example.com/webhook")
        service.register_webhook("test", config)

        payload = WebhookPayload(event_type=WebhookEventType.DIGEST_GENERATED)
        result = service.send_event("test", payload)

        assert result.status == WebhookStatus.FAILED


class TestDeliveryPreferences:
    """Tests for delivery preferences."""

    def test_default_preferences(self):
        """Should have sensible defaults."""
        prefs = DeliveryPreferences(user_id="user123")

        assert prefs.user_id == "user123"
        assert prefs.email_enabled
        assert not prefs.slack_enabled

    def test_is_subscribed(self):
        """Should check subscription status."""
        prefs = DeliveryPreferences(user_id="user123")
        assert prefs.is_subscribed

        # Unsubscribed
        prefs.unsubscribed_at = datetime.now(timezone.utc)
        assert not prefs.is_subscribed

    def test_disabled_channels(self):
        """Should show unsubscribed when all disabled."""
        prefs = DeliveryPreferences(
            user_id="user123",
            email_enabled=False,
            slack_enabled=False,
            webhook_enabled=False,
        )
        assert not prefs.is_subscribed


class TestDeliveryManager:
    """Tests for delivery manager."""

    def test_initialization(self):
        """Should initialize correctly."""
        manager = DeliveryManager()

        assert manager.email_service is None
        assert manager.slack_service is None
        assert manager.webhook_service is not None

    def test_configure_email(self):
        """Should configure email."""
        manager = DeliveryManager()
        config = SMTPConfig(
            server="smtp.gmail.com",
            port=587,
            username="user@gmail.com",
            password="password",
            from_address="user@gmail.com",
        )

        assert manager.configure_email(config)
        assert manager.email_service is not None

    def test_configure_slack(self):
        """Should configure Slack."""
        manager = DeliveryManager()
        config = SlackConfig(webhook_url="https://hooks.slack.com/services/T00/B00/X00")

        assert manager.configure_slack(config)
        assert manager.slack_service is not None

    def test_register_webhook(self):
        """Should register webhook."""
        manager = DeliveryManager()
        config = WebhookConfig(url="https://example.com/webhook")

        assert manager.register_webhook("test", config)

    def test_get_delivery_stats(self):
        """Should get delivery statistics."""
        manager = DeliveryManager()

        stats = manager.get_delivery_stats()

        assert stats["total_jobs"] == 0
        assert stats["channels_total"] == 0


class TestIntegration:
    """Integration tests."""

    def test_email_workflow(self):
        """Test complete email workflow."""
        config = SMTPConfig(
            server="smtp.gmail.com",
            port=587,
            username="test@gmail.com",
            password="password",
            from_address="test@gmail.com",
        )

        service = SMTPEmailService(config)
        assert service.validate_config()

    def test_slack_workflow(self):
        """Test complete Slack workflow."""
        config = SlackConfig(webhook_url="https://hooks.slack.com/services/T00/B00/X00")

        service = SlackService(config)
        assert service.validate_config()

    def test_webhook_workflow(self):
        """Test complete webhook workflow."""
        service = WebhookService()
        config = WebhookConfig(url="https://example.com/webhook")

        assert service.register_webhook("test", config)
        assert "test" in service.webhooks
