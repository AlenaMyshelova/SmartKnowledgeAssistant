from sqlalchemy import (
    Column, Integer, String, Text, Boolean, 
    DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

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
    
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('oauth_provider', 'oauth_id', name='uq_provider_oauth_id'),
        Index('ix_users_email', 'email'),
        Index('ix_users_oauth', 'oauth_provider', 'oauth_id'),
    )

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
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")
    

    __table_args__ = (
        Index('ix_chat_sessions_user_updated', 'user_id', 'updated_at'),
        Index('ix_chat_sessions_user_archived', 'user_id', 'is_archived'),
        Index('ix_chat_sessions_user_pinned', 'user_id', 'is_pinned'),
    )

class ChatMessage(Base):
    """Chat message model."""
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