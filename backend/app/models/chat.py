"""
Pydantic models for chat API endpoints.
These models are used for request/response validation with incognito mode support.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Base models
class ChatSessionBase(BaseModel):
    """Base model for chat sessions."""
    title: Optional[str] = None
    is_archived: bool = False
    is_pinned: bool = False

class ChatSessionCreate(ChatSessionBase):
    """Model for creating a new chat session."""
    user_id: int
    is_incognito: bool = False  # Support for incognito mode

class ChatSessionUpdate(BaseModel):
    """Model for updating chat sessions."""
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    is_pinned: Optional[bool] = None

class ChatSessionInDB(ChatSessionBase):
    """Model for chat sessions as stored in database."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_incognito: bool = False
    
    class Config:
        from_attributes = True

class ChatSession(ChatSessionInDB):
    """Full chat session model for API responses."""
    message_count: Optional[int] = None  # For API responses
    last_message: Optional[str] = None   # For API responses

# Message models
class MessageBase(BaseModel):
    """Base model for chat messages."""
    role: str = Field(..., regex="^(user|assistant)$")
    content: str
    metadata: Optional[Dict[str, Any]] = None

class MessageCreate(MessageBase):
    """Model for creating new messages."""
    chat_id: int

class MessageUpdate(BaseModel):
    """Model for updating messages."""
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MessageInDB(MessageBase):
    """Model for messages as stored in database."""
    id: int
    chat_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatMessage(MessageInDB):
    """Full message model for API responses."""
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, alias="created_at")

# Request/Response models for API endpoints
class ChatRequest(BaseModel):
    """Request model for sending chat messages."""
    message: str
    chat_id: Optional[int] = None
    data_source: str = "company_faqs"
    is_incognito: bool = False  # User can choose incognito mode

class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str
    chat_id: Optional[int] = None  # Optional for incognito mode
    message_id: Optional[int] = None  # Optional for incognito mode
    user_message_id: Optional[int] = None  # ID of user's message
    is_incognito: bool = False
    sources: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

class ChatListResponse(BaseModel):
    """Response model for chat list."""
    chats: List[ChatSession]
    total: int
    page: int
    page_size: int

class ChatHistoryResponse(BaseModel):
    """Response model for chat history."""
    chat: ChatSession
    messages: List[ChatMessage]
    total_messages: int = Field(0)

class CreateChatRequest(BaseModel):
    """Request model for creating a new chat."""
    title: Optional[str] = "New Chat"
    first_message: Optional[str] = None
    is_incognito: bool = False  # Option to create incognito chat

class UpdateChatRequest(BaseModel):
    """Request model for updating chat."""
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    is_pinned: Optional[bool] = None  # Added pinning support

class SearchChatsRequest(BaseModel):
    """Request model for searching chats."""
    query: str
    include_archived: bool = False
    limit: int = 50
    filters: Optional[Dict[str, Any]] = None  # For advanced filtering

class ChatModeStatus(BaseModel):
    """Response model for current chat mode status."""
    mode: str = "normal"  # 'normal' or 'incognito'
    active_incognito_chats: int
    saved_chats: int

# Compatibility aliases for existing code
Message = ChatMessage  # Alias for backward compatibility

class ChatSessionResponse(ChatSession):
    """Response model for single chat session with messages."""
    messages: List[ChatMessage] = []

class ChatSessionsListResponse(BaseModel):
    """Response model for chat sessions list."""
    sessions: List[ChatSession]
    total_count: int
    has_more: bool