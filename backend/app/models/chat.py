"""
Pydantic models for chat API endpoints.
These models work with SQLAlchemy models from database_models.py
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Enums for validation
class MessageRole(str, Enum):
    """Message role enum."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class DataSource(str, Enum):
    """Data source enum."""
    COMPANY_FAQS = "company_faqs"
    UPLOADED_FILES = "uploaded_files"
    GENERAL_KNOWLEDGE = "general_knowledge"

# Base models for chat sessions
class ChatSessionBase(BaseModel):
    """Base model for chat sessions."""
    title: Optional[str] = None
    is_archived: bool = False
    is_pinned: bool = False
    
class ChatSessionCreate(ChatSessionBase):
    """Model for creating a new chat session."""
    is_incognito: bool = False
    first_message: Optional[str] = None

class ChatSessionUpdate(BaseModel):
    """Model for updating chat sessions."""
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    is_pinned: Optional[bool] = None

class ChatSession(ChatSessionBase):
    """Full chat session model for API responses."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_incognito: bool = False
    message_count: Optional[int] = 0
    last_message: Optional[str] = None
    
    class Config:
        from_attributes = True
 

# Message models
class MessageBase(BaseModel):
    """Base model for chat messages."""
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = {}

class MessageCreate(MessageBase):
    """Model for creating new messages."""
    chat_id: Optional[int] = None

class ChatMessage(MessageBase):
    """Full message model for API responses."""
    id: int
    chat_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
        

# Request/Response models for API endpoints
class ChatRequest(BaseModel):
    """Request model for sending chat messages."""
    message: str = Field(..., min_length=1, max_length=4000)
    chat_id: Optional[int] = None
    data_source: str = DataSource.COMPANY_FAQS
    is_incognito: bool = False
    context_messages: Optional[int] = 10
    temperature: Optional[float] = 0.7

class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str
    chat_id: int
    message_id: Optional[int] = None
    user_message_id: Optional[int] = None
    is_incognito: bool = False
    sources: Optional[List[Dict[str, Any]]] = []
    metadata: Optional[Dict[str, Any]] = {}
    tokens_used: Optional[int] = None
    processing_time: Optional[float] = None

class ChatListResponse(BaseModel):
    """Response model for chat list."""
    chats: List[ChatSession]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False

class ChatHistoryResponse(BaseModel):
    """Response model for chat history."""
    chat: ChatSession
    messages: List[ChatMessage]
    total_messages: int = 0
    has_more: bool = False

class UpdateChatRequest(BaseModel):
    """Request model for updating chat."""
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    is_pinned: Optional[bool] = None

class SearchChatsRequest(BaseModel):
    """Request model for searching chats."""
    query: str = Field(..., min_length=1, max_length=200)
    include_archived: bool = False
    limit: int = 50

class ChatModeStatus(BaseModel):
    """Response model for current chat mode status."""
    has_incognito_chats: bool = False
    incognito_chat_count: int = 0
    total_chats: int = 0
    active_incognito_sessions: List[int] = []

# Compatibility aliases
CreateChatRequest = ChatSessionCreate
Message = ChatMessage
MessageResponse = ChatMessage
ChatSessionResponse = ChatSession