"""SQLAlchemy models for Agent Hub."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    api_config: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    agents: Mapped[list["Agent"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Agent(Base):
    """Agent model for registered A2A agents."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[Optional[str]] = mapped_column(String(50))
    skills: Mapped[Optional[dict]] = mapped_column(JSON)
    provider: Mapped[Optional[str]] = mapped_column(String(200))
    documentation_url: Mapped[Optional[str]] = mapped_column(String(500))

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship(back_populates="agents")

    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_health_check: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True)
