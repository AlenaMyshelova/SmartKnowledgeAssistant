"""
SQLAlchemy ORM models for Chat and Messages.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class ChatSession(Base):
    """Chat session model."""
    __tablename__ = 'chat_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    is_incognito = Column(Boolean, default=False)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="chat",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_chat_sessions_user_updated', 'user_id', 'updated_at'),
        Index('ix_chat_sessions_user_archived', 'user_id', 'is_archived'),
        Index('ix_chat_sessions_user_pinned', 'user_id', 'is_pinned'),
    )

    def __repr__(self):
        return f"<ChatSession(id={self.id}, user_id={self.user_id})>"


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    message_metadata = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

    chat = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index('ix_chat_messages_chat_id', 'chat_id'),
        Index('ix_chat_messages_chat_created', 'chat_id', 'created_at'),
        Index('ix_chat_messages_role', 'role'),
    )

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, chat_id={self.chat_id}, role='{self.role}')>"


class ChatLog(Base):
    """Legacy chat logs table for backward compatibility."""
    __tablename__ = 'chat_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    data_source = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_chat_logs_timestamp', 'timestamp'),
    )

    def __repr__(self):
        return f"<ChatLog(id={self.id})>"
