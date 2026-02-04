"""Authentication utilities for Agent Hub."""

import secrets
from typing import Optional
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User

# Simple session store (in production, use Redis or database sessions)
sessions: dict[str, int] = {}

SECRET_KEY = secrets.token_hex(32)
SESSION_COOKIE_NAME = "session_id"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session(user_id: int) -> str:
    """Create a new session for a user."""
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = user_id
    return session_id


def get_user_id_from_session(session_id: Optional[str]) -> Optional[int]:
    """Get user ID from session ID."""
    if not session_id:
        return None
    return sessions.get(session_id)


def delete_session(session_id: str) -> None:
    """Delete a session."""
    sessions.pop(session_id, None)


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, username: str, password: str) -> User:
    """Create a new user."""
    password_hash = hash_password(password)
    user = User(username=username, password_hash=password_hash)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
