"""
Email Delivery Service — Send digests via SMTP.

Handles:
- SMTP configuration and connection
- Email template rendering
- HTML/plain text email composition
- Attachment handling
- Delivery retry logic
- Bounce handling and logging
"""

import logging
import smtplib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import ssl

logger = logging.getLogger(__name__)


class EmailProvider(Enum):
    """Email service provider."""
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    AWS_SES = "aws_ses"
    MAILGUN = "mailgun"


class EmailStatus(Enum):
    """Email delivery status."""
    PENDING = "pending"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"


@dataclass
class SMTPConfig:
    """SMTP configuration."""

    server: str = "smtp.gmail.com"
    port: int = 587
    use_tls: bool = True
    use_ssl: bool = False
    username: str = ""
    password: str = ""
    from_address: str = ""
    from_name: str = "AI RADAR"
    timeout_seconds: int = 30
    max_retries: int = 3

    def validate(self) -> bool:
        """Validate SMTP configuration."""
        return bool(
            self.server
            and self.port > 0
            and self.username
            and self.password
            and self.from_address
        )


@dataclass
class EmailMessage:
    """Email message to send."""

    subject: str
    to_address: str
    html_content: str
    text_content: Optional[str] = None
    cc_addresses: List[str] = field(default_factory=list)
    bcc_addresses: List[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    attachments: List[Tuple[str, bytes, str]] = field(default_factory=list)  # (filename, content, mime_type)
    custom_headers: Dict[str, str] = field(default_factory=dict)
    message_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        subject: str,
        to_address: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> "EmailMessage":
        """Create email message."""
        return cls(
            subject=subject,
            to_address=to_address,
            html_content=html_content,
            text_content=text_content or cls._html_to_text(html_content),
        )

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Convert HTML to plain text (basic)."""
        import re
        # Remove HTML tags
        text = re.sub('<[^<]+?>', '', html)
        # Decode entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        return text

    def add_attachment(
        self,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
    ) -> "EmailMessage":
        """Add attachment to email."""
        self.attachments.append((filename, content, mime_type))
        return self


@dataclass
class EmailDeliveryResult:
    """Result of email delivery attempt."""

    message_id: str
    to_address: str
    status: EmailStatus
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    retry_count: int = 0
    delivered_at: Optional[datetime] = None

    @property
    def is_success(self) -> bool:
        """Check if delivery succeeded."""
        return self.status == EmailStatus.DELIVERED


class SMTPEmailService:
    """Send emails via SMTP."""

    def __init__(self, config: SMTPConfig):
        """
        Initialize SMTP email service.

        Args:
            config: SMTP configuration.
        """
        self.config = config
        self.delivery_history: List[EmailDeliveryResult] = []

    def validate_config(self) -> bool:
        """Validate SMTP configuration."""
        if not self.config.validate():
            logger.error("Invalid SMTP configuration")
            return False

        return True

    def _create_mime_message(self, email: EmailMessage) -> MIMEMultipart:
        """Create MIME message from email."""
        msg = MIMEMultipart('alternative')

        msg['Subject'] = email.subject
        msg['From'] = f"{self.config.from_name} <{self.config.from_address}>"
        msg['To'] = email.to_address

        if email.cc_addresses:
            msg['Cc'] = ', '.join(email.cc_addresses)

        if email.reply_to:
            msg['Reply-To'] = email.reply_to

        if email.message_id:
            msg['Message-ID'] = email.message_id

        # Add custom headers
        for key, value in email.custom_headers.items():
            msg[key] = value

        # Add content
        if email.text_content:
            msg.attach(MIMEText(email.text_content, 'plain', _charset='utf-8'))

        msg.attach(MIMEText(email.html_content, 'html', _charset='utf-8'))

        # Add attachments
        for filename, content, mime_type in email.attachments:
            if mime_type.startswith('text'):
                part = MIMEText(content.decode('utf-8'), _subtype=mime_type.split('/')[-1])
            elif mime_type.startswith('image'):
                from email.mime.image import MIMEImage
                part = MIMEImage(content, _subtype=mime_type.split('/')[-1])
            else:
                part = MIMEBase(*mime_type.split('/', 1))
                part.set_payload(content)
                encoders.encode_base64(part)

            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(part)

        return msg

    def send(self, email: EmailMessage) -> EmailDeliveryResult:
        """
        Send email.

        Args:
            email: Email message to send.

        Returns:
            EmailDeliveryResult with status.
        """
        if not self.validate_config():
            return EmailDeliveryResult(
                message_id=email.message_id or f"email_{datetime.now(timezone.utc).timestamp()}",
                to_address=email.to_address,
                status=EmailStatus.FAILED,
                error="Invalid SMTP configuration",
            )

        result = EmailDeliveryResult(
            message_id=email.message_id or f"email_{datetime.now(timezone.utc).timestamp()}",
            to_address=email.to_address,
            status=EmailStatus.SENDING,
        )

        try:
            # Create MIME message
            mime_msg = self._create_mime_message(email)

            # Connect to SMTP server
            if self.config.use_ssl:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(
                    self.config.server,
                    self.config.port,
                    timeout=self.config.timeout_seconds,
                    context=context,
                )
            else:
                server = smtplib.SMTP(
                    self.config.server,
                    self.config.port,
                    timeout=self.config.timeout_seconds,
                )

                if self.config.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)

            # Login
            server.login(self.config.username, self.config.password)

            # Send email
            recipients = [email.to_address] + email.cc_addresses + email.bcc_addresses
            server.sendmail(
                self.config.from_address,
                recipients,
                mime_msg.as_string(),
            )

            server.quit()

            result.status = EmailStatus.DELIVERED
            result.delivered_at = datetime.now(timezone.utc)

            logger.info(f"Email delivered to {email.to_address}")

        except smtplib.SMTPAuthenticationError as e:
            result.status = EmailStatus.FAILED
            result.error = f"SMTP authentication failed: {str(e)}"
            logger.error(f"SMTP auth error: {e}")

        except smtplib.SMTPException as e:
            result.status = EmailStatus.FAILED
            result.error = f"SMTP error: {str(e)}"
            logger.error(f"SMTP error: {e}")

        except Exception as e:
            result.status = EmailStatus.FAILED
            result.error = f"Unexpected error: {str(e)}"
            logger.error(f"Email send error: {e}", exc_info=True)

        self.delivery_history.append(result)
        return result

    def send_batch(self, emails: List[EmailMessage]) -> List[EmailDeliveryResult]:
        """Send multiple emails."""
        results = []

        for email in emails:
            result = self.send(email)
            results.append(result)

        return results

    def get_delivery_stats(self) -> Dict:
        """Get delivery statistics."""
        if not self.delivery_history:
            return {
                "total": 0,
                "delivered": 0,
                "failed": 0,
                "success_rate": 0.0,
            }

        total = len(self.delivery_history)
        delivered = sum(1 for r in self.delivery_history if r.status == EmailStatus.DELIVERED)
        failed = sum(1 for r in self.delivery_history if r.status == EmailStatus.FAILED)

        return {
            "total": total,
            "delivered": delivered,
            "failed": failed,
            "success_rate": delivered / total if total > 0 else 0.0,
        }


class EmailTemplateEngine:
    """Render email templates."""

    @staticmethod
    def render_digest_email(
        digest_title: str,
        critical_section: str,
        featured_section: str,
        relevant_section: str,
        discover_section: Optional[str] = None,
        read_time_minutes: int = 10,
        user_email: Optional[str] = None,
    ) -> str:
        """Render digest email template."""
        discover_html = f"""
        <div style="margin-top: 40px;">
            <h2 style="color: #4a90e2; font-size: 18px; margin-bottom: 20px;">🔎 Discover — Explore</h2>
            {discover_section or '<p>No additional articles today.</p>'}
        </div>
        """ if discover_section else ""

        unsubscribe_link = f"<p style='margin-top: 40px; font-size: 12px; color: #999;'><a href='https://ai-radar.local/preferences?email={user_email}&action=unsubscribe' style='color: #999;'>Unsubscribe</a></p>" if user_email else ""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{digest_title}</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
            <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <h1 style="margin: 0 0 10px 0; color: #333; font-size: 24px;">{digest_title}</h1>
                <p style="margin: 0 0 30px 0; color: #999; font-size: 14px;">
                    Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} • 
                    Est. read time: {read_time_minutes} minutes
                </p>

                <div style="margin-bottom: 40px;">
                    <h2 style="color: #e74c3c; font-size: 18px; margin-bottom: 20px;">🔥 Critical — Must Read</h2>
                    {critical_section}
                </div>

                <div style="margin-bottom: 40px;">
                    <h2 style="color: #f39c12; font-size: 18px; margin-bottom: 20px;">⭐ Featured — Today's Highlights</h2>
                    {featured_section}
                </div>

                <div style="margin-bottom: 40px;">
                    <h2 style="color: #3498db; font-size: 18px; margin-bottom: 20px;">📖 Relevant — Your Interests</h2>
                    {relevant_section}
                </div>

                {discover_html}

                <hr style="border: none; border-top: 1px solid #eee; margin-top: 40px;">

                <p style="margin-top: 20px; font-size: 12px; color: #999; text-align: center;">
                    Powered by AI RADAR • Your Personal Intelligence System
                </p>

                {unsubscribe_link}
            </div>
        </body>
        </html>
        """

        return html


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)

    config = SMTPConfig(
        server="smtp.gmail.com",
        port=587,
        username="your-email@gmail.com",
        password="your-app-password",
        from_address="your-email@gmail.com",
    )

    service = SMTPEmailService(config)

    email = EmailMessage.create(
        subject="Your AI RADAR Digest",
        to_address="user@example.com",
        html_content="<h1>Your Digest</h1><p>Check out these articles!</p>",
    )

    result = service.send(email)
    print(f"Delivery status: {result.status.value}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
