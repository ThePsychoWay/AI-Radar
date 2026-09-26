"""
Database Models — User preferences, subscriptions, and delivery tracking.

Uses SQLAlchemy for ORM.
"""

import logging
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Float,
    Text,
    ForeignKey,
    Enum,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class SubscriptionStatus(PyEnum):
    """Subscription status."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class DeliveryChannel(PyEnum):
    """Delivery channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


class User(Base):
    """User model."""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)
    timezone = Column(String, default="UTC")
    
    # Subscription
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    subscribed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    unsubscribed_at = Column(DateTime, nullable=True)
    
    # Preferences
    digest_frequency = Column(String, default="daily")  # daily, weekly, never
    digest_format = Column(String, default="email_html")
    include_critical_only = Column(Boolean, default=False)
    max_articles = Column(Integer, default=50)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_digest_sent_at = Column(DateTime, nullable=True)
    
    # Relationships
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    deliveries = relationship("DeliveryLog", back_populates="user", cascade="all, delete-orphan")

    def is_subscribed(self) -> bool:
        """Check if user is subscribed."""
        return self.subscription_status == SubscriptionStatus.ACTIVE and not self.unsubscribed_at

    def __repr__(self):
        return f"<User {self.email}>"


class UserPreference(Base):
    """User delivery preferences per channel."""
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(Enum(DeliveryChannel), nullable=False)
    
    # Channel-specific config
    enabled = Column(Boolean, default=True)
    channel_address = Column(String)  # email, Slack channel, webhook URL
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship
    user = relationship("User", back_populates="preferences")

    def __repr__(self):
        return f"<UserPreference {self.user_id}:{self.channel.value}>"


class DeliveryLog(Base):
    """Log of sent digests."""
    __tablename__ = "delivery_logs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(Enum(DeliveryChannel), nullable=False)
    
    # Delivery info
    digest_id = Column(String, index=True)
    status = Column(String, default="sent")  # sent, failed, bounced
    error_message = Column(Text, nullable=True)
    
    # Engagement tracking
    opened_at = Column(DateTime, nullable=True)
    click_count = Column(Integer, default=0)
    
    # Metadata
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    user = relationship("User", back_populates="deliveries")

    def __repr__(self):
        return f"<DeliveryLog {self.id}>"


class ArticleInteraction(Base):
    """Track user interactions with articles."""
    __tablename__ = "article_interactions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    article_id = Column(String, nullable=False, index=True)
    
    # Interaction type
    interaction_type = Column(String)  # view, save, like, share, dislike, skip
    interaction_value = Column(Float, default=1.0)  # weight for recommendation
    
    # Metadata
    interacted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<ArticleInteraction {self.user_id}:{self.article_id}>"


class DatabaseManager:
    """Manage database operations."""

    def __init__(self, database_url: str, echo: bool = False):
        """Initialize database manager."""
        self.engine = create_engine(database_url, echo=echo)
        self.Session = sessionmaker(bind=self.engine)

        logger.info(f"Database initialized: {database_url}")

    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(self.engine)
        logger.info("✓ Database tables created")

    def drop_tables(self):
        """Drop all tables (careful!)."""
        Base.metadata.drop_all(self.engine)
        logger.warning("✓ Database tables dropped")

    def get_session(self):
        """Get database session."""
        return self.Session()

    def create_user(
        self,
        user_id: str,
        email: str,
        name: str = "",
        timezone: str = "UTC",
    ) -> User:
        """Create new user."""
        session = self.get_session()

        try:
            user = User(
                id=user_id,
                email=email,
                name=name,
                timezone=timezone,
            )

            session.add(user)
            session.commit()

            logger.info(f"Created user: {email}")
            return user

        except Exception as e:
            session.rollback()
            logger.error(f"Error creating user: {e}")
            raise

        finally:
            session.close()

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        session = self.get_session()

        try:
            return session.query(User).filter(User.id == user_id).first()
        finally:
            session.close()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        session = self.get_session()

        try:
            return session.query(User).filter(User.email == email).first()
        finally:
            session.close()

    def add_delivery_preference(
        self,
        user_id: str,
        channel: DeliveryChannel,
        channel_address: str,
        enabled: bool = True,
    ) -> UserPreference:
        """Add delivery preference for user."""
        session = self.get_session()

        try:
            pref_id = f"{user_id}_{channel.value}"
            pref = UserPreference(
                id=pref_id,
                user_id=user_id,
                channel=channel,
                channel_address=channel_address,
                enabled=enabled,
            )

            session.add(pref)
            session.commit()

            logger.info(f"Added preference for {user_id}: {channel.value}")
            return pref

        except Exception as e:
            session.rollback()
            logger.error(f"Error adding preference: {e}")
            raise

        finally:
            session.close()

    def log_delivery(
        self,
        delivery_id: str,
        user_id: str,
        channel: DeliveryChannel,
        digest_id: str,
        status: str = "sent",
        error_message: Optional[str] = None,
    ) -> DeliveryLog:
        """Log digest delivery."""
        session = self.get_session()

        try:
            log_entry = DeliveryLog(
                id=delivery_id,
                user_id=user_id,
                channel=channel,
                digest_id=digest_id,
                status=status,
                error_message=error_message,
            )

            session.add(log_entry)
            session.commit()

            logger.info(f"Logged delivery: {delivery_id}")
            return log_entry

        except Exception as e:
            session.rollback()
            logger.error(f"Error logging delivery: {e}")
            raise

        finally:
            session.close()

    def record_interaction(
        self,
        interaction_id: str,
        user_id: str,
        article_id: str,
        interaction_type: str,
        value: float = 1.0,
    ) -> ArticleInteraction:
        """Record user interaction with article."""
        session = self.get_session()

        try:
            interaction = ArticleInteraction(
                id=interaction_id,
                user_id=user_id,
                article_id=article_id,
                interaction_type=interaction_type,
                interaction_value=value,
            )

            session.add(interaction)
            session.commit()

            logger.info(f"Recorded interaction: {interaction_type} for {article_id}")
            return interaction

        except Exception as e:
            session.rollback()
            logger.error(f"Error recording interaction: {e}")
            raise

        finally:
            session.close()

    def get_subscribed_users(self) -> List[User]:
        """Get all subscribed users."""
        session = self.get_session()

        try:
            return session.query(User).filter(
                User.subscription_status == SubscriptionStatus.ACTIVE,
                User.unsubscribed_at == None,
            ).all()
        finally:
            session.close()


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)

    # Initialize with SQLite
    db = DatabaseManager("sqlite:///./ai_radar.db")

    # Create tables
    db.create_tables()

    # Create test user
    user = db.create_user(
        user_id="user_123",
        email="user@example.com",
        name="Test User",
        timezone="Asia/Kolkata",
    )

    logger.info(f"Created user: {user}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
