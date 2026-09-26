"""
Environment Configuration Management.

Handles:
- Environment variable validation
- Configuration loading from .env files
- Secrets management
- Multi-environment support (dev, staging, prod)
"""

import os
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Deployment environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class EmailConfig:
    """Email configuration."""
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    from_address: str
    from_name: str = "AI RADAR"

    @classmethod
    def from_env(cls) -> "EmailConfig":
        """Load from environment."""
        return cls(
            smtp_server=os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
            smtp_username=os.getenv("EMAIL_SMTP_USERNAME", ""),
            smtp_password=os.getenv("EMAIL_SMTP_PASSWORD", ""),
            from_address=os.getenv("EMAIL_FROM_ADDRESS", ""),
            from_name=os.getenv("EMAIL_FROM_NAME", "AI RADAR"),
        )

    def validate(self) -> bool:
        """Validate configuration."""
        if not all([self.smtp_server, self.smtp_username, self.smtp_password, self.from_address]):
            logger.error("Email configuration incomplete")
            return False
        return True


@dataclass
class SlackConfig:
    """Slack configuration."""
    webhook_url: str
    channel: str = "#general"

    @classmethod
    def from_env(cls) -> "SlackConfig":
        """Load from environment."""
        return cls(
            webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""),
            channel=os.getenv("SLACK_CHANNEL", "#general"),
        )

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.webhook_url or not self.webhook_url.startswith("https://hooks.slack.com"):
            logger.error("Invalid Slack webhook URL")
            return False
        return True


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load from environment."""
        env = os.getenv("ENVIRONMENT", "development")
        
        if env == "production":
            db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/ai_radar_prod")
        else:
            db_url = os.getenv("DATABASE_URL", "sqlite:///./ai_radar.db")

        return cls(
            url=db_url,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
        )

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.url:
            logger.error("Database URL not configured")
            return False
        return True


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    webhook_ids: Dict[str, str]  # webhook_id -> url
    secret: str

    @classmethod
    def from_env(cls) -> "WebhookConfig":
        """Load from environment."""
        webhook_urls = {}
        
        # Load webhook URLs from env (WEBHOOK_CUSTOM_URL, WEBHOOK_ANALYTICS_URL, etc)
        for key, value in os.environ.items():
            if key.startswith("WEBHOOK_") and key.endswith("_URL"):
                webhook_id = key.replace("WEBHOOK_", "").replace("_URL", "").lower()
                webhook_urls[webhook_id] = value

        return cls(
            webhook_ids=webhook_urls,
            secret=os.getenv("WEBHOOK_SECRET", ""),
        )

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.secret:
            logger.warning("Webhook secret not configured")
            return False
        return True


@dataclass
class XConfig:
    """X (Twitter) configuration."""
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str
    bearer_token: str

    @classmethod
    def from_env(cls) -> "XConfig":
        """Load from environment."""
        return cls(
            api_key=os.getenv("X_API_KEY", ""),
            api_secret=os.getenv("X_API_SECRET", ""),
            access_token=os.getenv("X_ACCESS_TOKEN", ""),
            access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET", ""),
            bearer_token=os.getenv("X_BEARER_TOKEN", ""),
        )

    def validate(self) -> bool:
        """Validate configuration."""
        if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            logger.warning("X (Twitter) configuration incomplete - X publishing disabled")
            return False
        return True


class Config:
    """Main configuration manager."""

    def __init__(self):
        """Initialize configuration."""
        # Load .env file
        load_dotenv()

        self.environment = Environment(os.getenv("ENVIRONMENT", "development"))
        self.debug = self.environment == Environment.DEVELOPMENT
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

        # Component configs
        self.email = EmailConfig.from_env()
        self.slack = SlackConfig.from_env()
        self.database = DatabaseConfig.from_env()
        self.webhooks = WebhookConfig.from_env()
        self.x = XConfig.from_env()

        # API configs
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8000"))
        self.api_workers = int(os.getenv("API_WORKERS", "4"))

        # Collection configs
        self.collection_interval_hours = int(os.getenv("COLLECTION_INTERVAL_HOURS", "6"))
        self.digest_schedule = os.getenv("DIGEST_SCHEDULE", "0 8 * * *")  # 8 AM UTC

        logger.info(f"Configuration loaded for {self.environment.value} environment")

    def validate_all(self) -> bool:
        """Validate all configurations."""
        configs = [
            ("Email", self.email),
            ("Database", self.database),
            ("Webhooks", self.webhooks),
            ("X (Twitter)", self.x),
        ]

        all_valid = True

        for name, config in configs:
            if not config.validate():
                logger.warning(f"{name} configuration invalid or incomplete")
                all_valid = False
            else:
                logger.info(f"✓ {name} configuration valid")

        return all_valid

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "environment": self.environment.value,
            "debug": self.debug,
            "email_configured": self.email.validate(),
            "database_configured": self.database.validate(),
            "webhooks_configured": len(self.webhooks.webhook_ids) > 0,
            "x_configured": self.x.validate(),
            "slack_configured": self.slack.validate(),
            "api_host": self.api_host,
            "api_port": self.api_port,
        }


# Global config instance
config = Config()


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)

    print("AI RADAR Configuration")
    print("=" * 50)

    for key, value in config.to_dict().items():
        print(f"{key}: {value}")

    print()
    print("Validation Results:")
    config.validate_all()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
