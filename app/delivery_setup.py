"""
Delivery Channels Configuration Setup.

Provides helpers to configure email, Slack, and webhooks for production.
"""

import logging
import json
from typing import Dict, Optional, Tuple
from app.config import Config
from app.delivery import (
    SMTPEmailService,
    SlackService,
    WebhookService,
)

logger = logging.getLogger(__name__)


class DeliveryChannelsSetup:
    """Setup and validation for delivery channels."""

    def __init__(self, config: Config):
        """Initialize with config."""
        self.config = config
        self.email_service = None
        self.slack_service = None
        self.webhook_service = None

    def setup_email(self) -> Tuple[bool, str]:
        """Setup and test email configuration."""
        logger.info("Setting up Email configuration...")

        try:
            if not self.config.email.validate():
                return False, "Email configuration invalid"

            self.email_service = SMTPEmailService(self.config.email)
            
            # Test connection
            if self.email_service.test_connection():
                logger.info("✓ Email service configured and tested")
                return True, "Email configured successfully"
            else:
                logger.error("✗ Email service test failed")
                return False, "Email test failed - check SMTP credentials"

        except Exception as e:
            logger.error(f"Email setup error: {e}")
            return False, str(e)

    def setup_slack(self) -> Tuple[bool, str]:
        """Setup and test Slack configuration."""
        logger.info("Setting up Slack configuration...")

        try:
            if not self.config.slack.validate():
                return False, "Slack configuration invalid (no webhook URL)"

            self.slack_service = SlackService(self.config.slack)

            # Test connection
            if self.slack_service.test_webhook():
                logger.info("✓ Slack service configured and tested")
                return True, "Slack configured successfully"
            else:
                logger.error("✗ Slack webhook test failed")
                return False, "Slack test failed - check webhook URL"

        except Exception as e:
            logger.error(f"Slack setup error: {e}")
            return False, str(e)

    def setup_webhooks(self) -> Tuple[bool, str]:
        """Setup webhook configuration."""
        logger.info("Setting up Webhook configuration...")

        try:
            if not self.config.webhooks.validate():
                return False, "Webhook configuration incomplete (no secret)"

            self.webhook_service = WebhookService(self.config.webhooks)

            webhook_count = len(self.config.webhooks.webhook_ids)
            logger.info(f"✓ Webhook service configured for {webhook_count} webhooks")
            return True, f"Webhooks configured for {webhook_count} endpoints"

        except Exception as e:
            logger.error(f"Webhook setup error: {e}")
            return False, str(e)

    def setup_all(self) -> Dict[str, Tuple[bool, str]]:
        """Setup all delivery channels."""
        logger.info("=" * 60)
        logger.info("Setting up Delivery Channels")
        logger.info("=" * 60)

        results = {
            "email": self.setup_email(),
            "slack": self.setup_slack(),
            "webhooks": self.setup_webhooks(),
        }

        logger.info("=" * 60)
        logger.info("Setup Summary:")
        logger.info("=" * 60)

        all_ok = True

        for channel, (success, message) in results.items():
            status = "✓" if success else "✗"
            logger.info(f"{status} {channel.upper()}: {message}")

            if not success:
                all_ok = False

        logger.info("=" * 60)

        return results


class DeliveryChannelsGuide:
    """Setup guides for each delivery channel."""

    @staticmethod
    def email_setup_guide() -> str:
        """Email setup guide."""
        return """
# Email Configuration Guide

## Using Gmail (Recommended for Testing)

1. Enable 2-Step Verification in your Google Account
   https://myaccount.google.com/security

2. Create an "App Password"
   https://myaccount.google.com/apppasswords

3. Configure environment variables:
   EMAIL_SMTP_SERVER=smtp.gmail.com
   EMAIL_SMTP_PORT=587
   EMAIL_SMTP_USERNAME=your-email@gmail.com
   EMAIL_SMTP_PASSWORD=<app-password-from-step-2>
   EMAIL_FROM_ADDRESS=your-email@gmail.com

## Using SendGrid (Recommended for Production)

1. Sign up at https://sendgrid.com

2. Create an API key with "Mail Send" permissions
   https://app.sendgrid.com/settings/api_keys

3. Configure environment variables:
   EMAIL_SMTP_SERVER=smtp.sendgrid.net
   EMAIL_SMTP_PORT=587
   EMAIL_SMTP_USERNAME=apikey
   EMAIL_SMTP_PASSWORD=<your-sendgrid-api-key>
   EMAIL_FROM_ADDRESS=noreply@yourdomain.com

## Using AWS SES

1. Sign up at https://aws.amazon.com/ses/

2. Verify sender email address (or entire domain)
   https://console.aws.amazon.com/ses/home

3. Create SMTP credentials:
   https://console.aws.amazon.com/ses/home#smtp-settings

4. Configure environment variables:
   EMAIL_SMTP_SERVER=email-smtp.<region>.amazonaws.com
   EMAIL_SMTP_PORT=587
   EMAIL_SMTP_USERNAME=<your-ses-smtp-username>
   EMAIL_SMTP_PASSWORD=<your-ses-smtp-password>
   EMAIL_FROM_ADDRESS=noreply@yourdomain.com

## Testing

python -m app.delivery.email_service
        """

    @staticmethod
    def slack_setup_guide() -> str:
        """Slack setup guide."""
        return """
# Slack Configuration Guide

## Create a Slack App

1. Go to https://api.slack.com/apps

2. Click "Create New App" → "From scratch"

3. Name: "AI RADAR"
   Workspace: Select your workspace

4. Go to "Incoming Webhooks"
   https://api.slack.com/apps/<app-id>/incoming-webhooks

5. Click "Add New Webhook to Workspace"

6. Select channel: #general (or create #ai-radar)

7. Copy the webhook URL (starts with https://hooks.slack.com/...)

8. Configure environment variable:
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../X...
   SLACK_CHANNEL=#ai-radar

## Permissions (Optional)

If you want more advanced features, add these scopes:
- chat:write
- channels:read
- users:read

## Testing

Send a test message:
curl -X POST -H 'Content-type: application/json' \\
  --data '{"text":"AI RADAR Test"}' \\
  <SLACK_WEBHOOK_URL>
        """

    @staticmethod
    def webhook_setup_guide() -> str:
        """Webhook setup guide."""
        return """
# Webhook Configuration Guide

## Overview

Webhooks allow you to receive real-time events from AI RADAR to your systems.

Events:
- digest.generated - New digest created
- digest.sent - Digest sent to user
- article.added - New article collected
- article.ranked - Article ranked by importance
- collection.complete - Collection run completed
- error - Error occurred

## Setup

1. Generate a webhook secret (random string):
   WEBHOOK_SECRET=your-random-secret-key

2. Register webhook endpoints:
   WEBHOOK_CUSTOM_URL=https://your-api.example.com/webhooks/ai-radar
   WEBHOOK_ANALYTICS_URL=https://analytics.example.com/events

3. AI RADAR will sign all requests with HMAC-SHA256

## Receiving Webhooks

1. Verify signature:

   import hmac
   import hashlib

   signature = request.headers.get('X-Webhook-Signature')
   secret = os.environ['WEBHOOK_SECRET']
   body = request.get_data()

   expected = hmac.new(
       secret.encode(),
       body,
       hashlib.sha256
   ).hexdigest()

   assert hmac.compare_digest(signature, expected)

2. Process event:

   {
     "event_type": "digest.sent",
     "timestamp": "2026-09-26T08:00:00Z",
     "user_id": "user_123",
     "digest_id": "digest_abc",
     "data": {...}
   }

## Testing

curl -X POST https://your-api.example.com/webhooks/ai-radar \\
  -H 'Content-Type: application/json' \\
  -H 'X-Webhook-Signature: <signature>' \\
  -d '{
    "event_type": "digest.sent",
    "timestamp": "2026-09-26T08:00:00Z",
    "user_id": "user_123",
    "digest_id": "digest_abc"
  }'
        """

    @staticmethod
    def print_all_guides():
        """Print all setup guides."""
        print("=" * 70)
        print("AI RADAR - DELIVERY CHANNELS SETUP GUIDES")
        print("=" * 70)
        print()

        print(DeliveryChannelsGuide.email_setup_guide())
        print()
        print(DeliveryChannelsGuide.slack_setup_guide())
        print()
        print(DeliveryChannelsGuide.webhook_setup_guide())


def main():
    """CLI for delivery channels setup."""
    import sys
    from app.config import config

    logging.basicConfig(level=logging.INFO)

    # Parse arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()

        if arg == "guides":
            DeliveryChannelsGuide.print_all_guides()
            return 0

        elif arg == "test":
            setup = DeliveryChannelsSetup(config)
            results = setup.setup_all()
            return 0 if all(success for success, _ in results.values()) else 1

        elif arg == "email":
            print(DeliveryChannelsGuide.email_setup_guide())
            return 0

        elif arg == "slack":
            print(DeliveryChannelsGuide.slack_setup_guide())
            return 0

        elif arg == "webhooks":
            print(DeliveryChannelsGuide.webhook_setup_guide())
            return 0

    else:
        print("Usage: python -m app.delivery_setup [guides|test|email|slack|webhooks]")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
