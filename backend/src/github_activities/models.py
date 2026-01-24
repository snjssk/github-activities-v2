"""SQLAlchemy models."""

from datetime import datetime, date
from typing import Optional
import json

from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Date,
    DateTime,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    Session,
)

from .config import settings


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User model for tracking GitHub users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    collect_from_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    activities: Mapped[list["Activity"]] = relationship(
        "Activity", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(username={self.username})>"


class Activity(Base):
    """Activity model for storing GitHub activities."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="activities")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "activity_type", "repository", "activity_date",
            name="uq_activity_per_day"
        ),
        Index("idx_activities_user_date", "user_id", "activity_date"),
        Index("idx_activities_type", "activity_type"),
    )

    @property
    def extra_data(self) -> Optional[dict]:
        """Parse metadata JSON."""
        if self.metadata_json:
            return json.loads(self.metadata_json)
        return None

    @extra_data.setter
    def extra_data(self, value: Optional[dict]) -> None:
        """Set metadata as JSON string."""
        if value is not None:
            self.metadata_json = json.dumps(value)
        else:
            self.metadata_json = None

    def __repr__(self) -> str:
        return f"<Activity(user_id={self.user_id}, type={self.activity_type}, date={self.activity_date})>"


# Activity types
ACTIVITY_TYPES = {
    "commit": "Commit",
    "pr_opened": "PR Opened",
    "pr_merged": "PR Merged",
    "review": "Code Review",
    "issue_opened": "Issue Opened",
    "issue_closed": "Issue Closed",
}


def get_engine():
    """Create database engine."""
    return create_engine(settings.database_url, echo=False)


def init_db() -> None:
    """Initialize database tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Create a new database session."""
    engine = get_engine()
    return Session(engine)
