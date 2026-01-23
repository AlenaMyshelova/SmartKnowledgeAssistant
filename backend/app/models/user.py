from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base

class User(Base):
    """User model for OAuth authentication."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    avatar_url = Column(Text, nullable=True)
    oauth_provider = Column(String(50), nullable=False)
    oauth_id = Column(String(255), nullable=False)
    provider_data = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint('oauth_provider', 'oauth_id', name='uq_provider_oauth_id'),
        Index('ix_users_email', 'email'),
        Index('ix_users_oauth', 'oauth_provider', 'oauth_id'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"
