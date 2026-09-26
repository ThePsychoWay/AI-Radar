"""
Webhook Dispatch Service — Send data to custom webhooks.

Handles:
- HTTP/HTTPS POST requests
- Payload signing (HMAC-SHA256)
- Retry logic with exponential backoff
- Header customization
- Response validation
- Event categorization
"""

import logging
import json
import hmac
import hashlib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Type of webhook event."""
    DIGEST_GENERATED = "digest.generated"
    DIGEST_SENT = "digest.sent"
    ARTICLE_ADDED = "article.added"
    ARTICLE_RANKED = "article.ranked"
    COLLECTION_COMPLETE = "collection.complete"
    ERROR = "error"


class WebhookStatus(Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    SENT = "sent"
    RETRYING = "retrying"
    FAILED = "failed"
    SUCCESS = "success"


@dataclass
class WebhookConfig:
    """Webhook configuration."""

    url: str
    secret: str = ""  # For HMAC signing
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_backoff_seconds: int = 60  # Exponential backoff
    enabled: bool = True
    events: List[WebhookEventType] = field(default_factory=lambda: [
        WebhookEventType.DIGEST_GENERATED,
        WebhookEventType.COLLECTION_COMPLETE,
    ])

    def validate(self) -> bool:
        """Validate webhook configuration."""
        return bool(self.url and self.url.startswith(('http://', 'https://')))


@dataclass
class WebhookPayload:
    """Webhook event payload."""

    event_type: WebhookEventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "version": self.version,
        }


@dataclass
class WebhookDeliveryResult:
    """Result of webhook delivery attempt."""

    webhook_id: str
    event_type: WebhookEventType
    status: WebhookStatus
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    response_status_code: Optional[int] = None
    response_body: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None

    @property
    def is_success(self) -> bool:
        """Check if delivery succeeded."""
        return self.status == WebhookStatus.SUCCESS


class WebhookSigningService:
    """Sign webhook payloads with HMAC-SHA256."""

    @staticmethod
    def sign_payload(payload_json: str, secret: str) -> str:
        """
        Sign payload with HMAC-SHA256.

        Args:
            payload_json: JSON payload as string.
            secret: Secret key for signing.

        Returns:
            Hex-encoded HMAC signature.
        """
        signature = hmac.new(
            secret.encode(),
            payload_json.encode(),
            hashlib.sha256,
        ).hexdigest()

        return signature

    @staticmethod
    def verify_signature(
        payload_json: str,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify webhook signature."""
        expected_signature = WebhookSigningService.sign_payload(payload_json, secret)
        return hmac.compare_digest(expected_signature, signature)


class WebhookService:
    """Send events to webhooks."""

    def __init__(self):
        """Initialize webhook service."""
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.delivery_history: List[WebhookDeliveryResult] = []

    def register_webhook(
        self,
        webhook_id: str,
        config: WebhookConfig,
    ) -> bool:
        """Register webhook."""
        if not config.validate():
            logger.error(f"Invalid webhook configuration for {webhook_id}")
            return False

        self.webhooks[webhook_id] = config
        logger.info(f"Webhook registered: {webhook_id}")
        return True

    def unregister_webhook(self, webhook_id: str) -> bool:
        """Unregister webhook."""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            logger.info(f"Webhook unregistered: {webhook_id}")
            return True

        return False

    def send_event(
        self,
        webhook_id: str,
        payload: WebhookPayload,
    ) -> WebhookDeliveryResult:
        """
        Send event to specific webhook.

        Args:
            webhook_id: Webhook identifier.
            payload: Event payload.

        Returns:
            WebhookDeliveryResult.
        """
        config = self.webhooks.get(webhook_id)

        if not config:
            return WebhookDeliveryResult(
                webhook_id=webhook_id,
                event_type=payload.event_type,
                status=WebhookStatus.FAILED,
                error="Webhook not registered",
            )

        if not config.enabled:
            return WebhookDeliveryResult(
                webhook_id=webhook_id,
                event_type=payload.event_type,
                status=WebhookStatus.FAILED,
                error="Webhook disabled",
            )

        # Check if webhook listens to this event
        if payload.event_type not in config.events:
            return WebhookDeliveryResult(
                webhook_id=webhook_id,
                event_type=payload.event_type,
                status=WebhookStatus.PENDING,
                error="Event type not subscribed",
            )

        return self._send_with_retry(webhook_id, config, payload)

    def _send_with_retry(
        self,
        webhook_id: str,
        config: WebhookConfig,
        payload: WebhookPayload,
        retry_count: int = 0,
    ) -> WebhookDeliveryResult:
        """Send with retry logic."""
        result = WebhookDeliveryResult(
            webhook_id=webhook_id,
            event_type=payload.event_type,
            status=WebhookStatus.PENDING,
            retry_count=retry_count,
        )

        try:
            payload_json = json.dumps(payload.to_dict())

            headers = {
                "Content-Type": "application/json",
                **config.headers,
            }

            # Add signature if secret is configured
            if config.secret:
                signature = WebhookSigningService.sign_payload(payload_json, config.secret)
                headers["X-Webhook-Signature"] = f"sha256={signature}"

            response = requests.post(
                config.url,
                data=payload_json,
                headers=headers,
                timeout=config.timeout_seconds,
            )

            result.response_status_code = response.status_code
            result.response_body = response.text[:500]  # Store first 500 chars

            if response.status_code in (200, 201, 202, 204):
                result.status = WebhookStatus.SUCCESS
                logger.info(f"Webhook delivered: {webhook_id}")

            else:
                result.status = WebhookStatus.FAILED
                result.error = f"HTTP {response.status_code}"

                # Retry on 5xx errors
                if response.status_code >= 500 and retry_count < config.max_retries:
                    result.status = WebhookStatus.RETRYING
                    backoff_seconds = config.retry_backoff_seconds * (2 ** retry_count)
                    result.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                    logger.warning(
                        f"Webhook retrying {webhook_id} in {backoff_seconds}s "
                        f"(attempt {retry_count + 1}/{config.max_retries})"
                    )

        except requests.exceptions.Timeout:
            result.status = WebhookStatus.FAILED
            result.error = "Request timeout"
            logger.error(f"Webhook timeout: {webhook_id}")

        except requests.exceptions.RequestException as e:
            result.status = WebhookStatus.FAILED
            result.error = f"Request error: {str(e)}"
            logger.error(f"Webhook request error: {e}")

        except Exception as e:
            result.status = WebhookStatus.FAILED
            result.error = f"Unexpected error: {str(e)}"
            logger.error(f"Webhook error: {e}", exc_info=True)

        self.delivery_history.append(result)
        return result

    def broadcast_event(
        self,
        payload: WebhookPayload,
    ) -> List[WebhookDeliveryResult]:
        """
        Send event to all registered webhooks.

        Args:
            payload: Event payload.

        Returns:
            List of delivery results.
        """
        results = []

        for webhook_id, config in self.webhooks.items():
            result = self.send_event(webhook_id, payload)
            results.append(result)

        return results

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics."""
        if not self.delivery_history:
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
            }

        total = len(self.delivery_history)
        successful = sum(1 for r in self.delivery_history if r.status == WebhookStatus.SUCCESS)
        failed = sum(1 for r in self.delivery_history if r.status == WebhookStatus.FAILED)

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0.0,
        }


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)

    service = WebhookService()

    config = WebhookConfig(
        url="https://example.com/webhooks/ai-radar",
        secret="your-secret-key",
    )

    service.register_webhook("example", config)

    payload = WebhookPayload(
        event_type=WebhookEventType.DIGEST_GENERATED,
        data={
            "digest_id": "digest_123",
            "article_count": 50,
            "read_time_minutes": 10,
        },
    )

    result = service.send_event("example", payload)
    print(f"Webhook status: {result.status.value}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
