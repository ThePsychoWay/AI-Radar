"""
User Onboarding System.

Handles:
- User signup and registration
- Initial preference setup
- Delivery channel configuration
- Welcome digest
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from dataclasses import dataclass
from app.database import DatabaseManager, DeliveryChannel, User
from app.delivery import DeliveryManager, DeliveryPreferences, DeliveryJob

logger = logging.getLogger(__name__)


@dataclass
class OnboardingStep:
    """Single onboarding step."""
    step_id: str
    name: str
    description: str
    required: bool = True
    completed: bool = False


class OnboardingFlows:
    """Standard onboarding flows."""

    @staticmethod
    def quick_setup() -> list:
        """Quick 3-step setup."""
        return [
            OnboardingStep(
                step_id="1_email",
                name="Email Address",
                description="Where should we send your daily digest?",
                required=True,
            ),
            OnboardingStep(
                step_id="2_interests",
                name="Select Interests",
                description="Choose what topics you care about (AI, Machine Learning, Startups, etc)",
                required=True,
            ),
            OnboardingStep(
                step_id="3_confirm",
                name="Confirm",
                description="Review and confirm your settings",
                required=True,
            ),
        ]

    @staticmethod
    def full_setup() -> list:
        """Complete setup with all options."""
        return [
            OnboardingStep(
                step_id="1_profile",
                name="Profile Setup",
                description="Name, timezone, language preferences",
                required=True,
            ),
            OnboardingStep(
                step_id="2_channels",
                name="Delivery Channels",
                description="Email, Slack, webhooks - choose how to receive digests",
                required=True,
            ),
            OnboardingStep(
                step_id="3_interests",
                name="Content Interests",
                description="Select topics you want to follow",
                required=True,
            ),
            OnboardingStep(
                step_id="4_frequency",
                name="Digest Frequency",
                description="Daily, weekly, or custom schedule",
                required=True,
            ),
            OnboardingStep(
                step_id="5_advanced",
                name="Advanced Settings",
                description="Filters, importance thresholds, custom sources (optional)",
                required=False,
            ),
        ]


@dataclass
class OnboardingSession:
    """User onboarding session."""
    session_id: str
    user_id: Optional[str]
    email: str
    name: str = ""
    timezone: str = "UTC"
    digest_format: str = "email_html"
    
    # Channels
    email_enabled: bool = True
    slack_enabled: bool = False
    slack_channel: str = ""
    webhooks_enabled: bool = False
    
    # Preferences
    interests: list = None  # ["AI", "ML", "Startups"]
    digest_frequency: str = "daily"
    include_critical_only: bool = False
    max_articles: int = 50
    
    # Status
    created_at: datetime = None
    completed_at: Optional[datetime] = None
    completed: bool = False

    def __post_init__(self):
        """Initialize defaults."""
        if self.interests is None:
            self.interests = []
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class UserOnboarding:
    """Handle user onboarding."""

    def __init__(self, db: DatabaseManager):
        """Initialize with database."""
        self.db = db

    def create_session(self, email: str, name: str = "") -> OnboardingSession:
        """Create new onboarding session."""
        session = OnboardingSession(
            session_id=f"onboard_{uuid.uuid4().hex[:12]}",
            user_id=None,
            email=email,
            name=name,
        )

        logger.info(f"Created onboarding session: {session.session_id}")
        return session

    def register_user(self, session: OnboardingSession) -> Tuple[bool, User, str]:
        """Register user from onboarding session."""
        try:
            # Check if already exists
            existing = self.db.get_user_by_email(session.email)

            if existing:
                return False, None, "User already registered with this email"

            # Create user
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            user = self.db.create_user(
                user_id=user_id,
                email=session.email,
                name=session.name,
                timezone=session.timezone,
            )

            logger.info(f"Registered user: {user.email}")

            # Add delivery preferences
            if session.email_enabled:
                self.db.add_delivery_preference(
                    user_id=user_id,
                    channel=DeliveryChannel.EMAIL,
                    channel_address=session.email,
                    enabled=True,
                )
                logger.info(f"Added email delivery: {session.email}")

            if session.slack_enabled and session.slack_channel:
                self.db.add_delivery_preference(
                    user_id=user_id,
                    channel=DeliveryChannel.SLACK,
                    channel_address=session.slack_channel,
                    enabled=True,
                )
                logger.info(f"Added Slack delivery: {session.slack_channel}")

            if session.webhooks_enabled:
                # Webhook address would come from config
                pass

            # Update session
            session.user_id = user_id
            session.completed_at = datetime.now(timezone.utc)
            session.completed = True

            return True, user, "User registered successfully"

        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return False, None, str(e)

    def send_welcome_digest(self, user: User) -> Tuple[bool, str]:
        """Send welcome digest to new user."""
        try:
            logger.info(f"Sending welcome digest to {user.email}")

            # Get user preferences
            session = self.db.get_session()

            try:
                prefs = session.query(
                    self.db.Session.query.__self__.User.preferences
                ).filter(
                    self.db.Session.query.__self__.User.id == user.id
                ).all()

                # Create welcome message
                welcome_message = f"""
Welcome to AI RADAR!

Hello {user.name or user.email},

Your personalized AI intelligence digest is now active. 

You will receive daily digests at 8:00 AM (your timezone: {user.timezone}) 
containing curated articles from:
- Hacker News
- arXiv (AI/ML research)
- GitHub (trending AI/ML repos)
- HuggingFace (new models)
- RSS feeds

You can adjust your preferences anytime.

Start exploring: https://ai-radar.example.com

Best,
The AI RADAR Team
                """

                logger.info(f"✓ Welcome digest prepared for {user.email}")
                return True, "Welcome digest prepared"

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error sending welcome digest: {e}")
            return False, str(e)

    def get_onboarding_guide(self) -> str:
        """Get onboarding guide for users."""
        return """
# AI RADAR - Welcome Guide

## What is AI RADAR?

AI RADAR is your personal AI intelligence system. It:

✓ Monitors 5 authoritative sources:
  - Hacker News (tech trends)
  - arXiv (AI/ML research papers)
  - GitHub (trending repositories)
  - HuggingFace (new ML models)
  - Custom RSS feeds

✓ Deduplicates and ranks by importance
✓ Learns your interests over time
✓ Delivers a personalized daily digest
✓ Sends via Email, Slack, or webhooks

## Getting Started

### Step 1: Verify Your Email
We'll send you a verification link. Click it to confirm.

### Step 2: Choose Your Interests
Select from:
- Artificial Intelligence
- Machine Learning
- Large Language Models (LLMs)
- Generative AI
- Computer Vision
- NLP
- Reinforcement Learning
- Startups & Funding
- Research Papers
- Open Source Projects

### Step 3: Set Delivery Preferences
Choose how often you want digests (daily, weekly, custom)
and where to receive them (Email, Slack, webhooks).

### Step 4: Adjust Advanced Settings (Optional)
- Minimum importance threshold
- Maximum articles per digest
- Custom filters
- Read time preferences

## Quick Tips

📧 **Email Digests**: HTML-formatted with one-click reading
💬 **Slack**: Instant notifications for critical articles
🔗 **Webhooks**: Integrate with your own systems
👍 **Feedback**: Like/dislike articles to improve recommendations
🔔 **Notifications**: Critical articles trigger immediate alerts

## Dashboard

Visit https://ai-radar.example.com to:
- View your digest history
- Manage preferences
- Track your reading activity
- Adjust filters
- Customize sources

## Need Help?

- FAQ: https://ai-radar.example.com/help
- Email: support@ai-radar.example.com
- GitHub Issues: https://github.com/ThePsychoWay/AI-Radar/issues

Happy reading!
        """


class OnboardingEmailTemplates:
    """Email templates for onboarding."""

    @staticmethod
    def verification_email(user_name: str, verification_link: str) -> Tuple[str, str]:
        """Verification email."""
        subject = "Verify your AI RADAR account"

        body = f"""
        <html>
        <body>
        <h1>Welcome to AI RADAR!</h1>
        
        <p>Hi {user_name},</p>
        
        <p>Thank you for signing up. To activate your account, click the link below:</p>
        
        <p><a href="{verification_link}" style="padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;">
            Verify Email
        </a></p>
        
        <p>Or copy this link: {verification_link}</p>
        
        <p>This link expires in 24 hours.</p>
        
        <p>Best,<br/>
        The AI RADAR Team</p>
        </body>
        </html>
        """

        return subject, body

    @staticmethod
    def welcome_email(user_name: str, dashboard_link: str) -> Tuple[str, str]:
        """Welcome email after verification."""
        subject = "Welcome to AI RADAR - Your First Digest"

        body = f"""
        <html>
        <body>
        <h1>You're all set!</h1>
        
        <p>Hi {user_name},</p>
        
        <p>Your AI RADAR account is active and monitoring 5 sources for you:</p>
        
        <ul>
        <li>Hacker News</li>
        <li>arXiv Research</li>
        <li>GitHub Trends</li>
        <li>HuggingFace Models</li>
        <li>Custom RSS Feeds</li>
        </ul>
        
        <p>Your first digest will arrive at 8:00 AM (your timezone) with the latest AI/ML articles personalized for you.</p>
        
        <p><a href="{dashboard_link}" style="padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px;">
            Go to Dashboard
        </a></p>
        
        <p>You can adjust your preferences anytime from your dashboard.</p>
        
        <p>Best,<br/>
        The AI RADAR Team</p>
        </body>
        </html>
        """

        return subject, body


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)

    # Print guides
    print("=" * 70)
    print("ONBOARDING FLOWS")
    print("=" * 70)

    print("\n--- Quick Setup (3 steps) ---")
    for step in OnboardingFlows.quick_setup():
        print(f"{step.step_id}: {step.name} - {step.description}")

    print("\n--- Full Setup (5+ steps) ---")
    for step in OnboardingFlows.full_setup():
        print(f"{step.step_id}: {step.name} - {step.description}")

    # Example session
    print("\n" + "=" * 70)
    print("EXAMPLE ONBOARDING SESSION")
    print("=" * 70)

    session = OnboardingSession(
        session_id="onboard_test",
        user_id=None,
        email="user@example.com",
        name="Test User",
        timezone="Asia/Kolkata",
        email_enabled=True,
        interests=["AI", "ML", "Startups"],
    )

    print(f"\nSession: {session.session_id}")
    print(f"Email: {session.email}")
    print(f"Interests: {', '.join(session.interests)}")
    print(f"Digest Frequency: {session.digest_frequency}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
