from pydantic import BaseModel, Field, validator, field_validator
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
    title: Optional[str] = None
    is_archived: bool = False
    is_pinned: bool = False
    
class ChatSessionCreate(ChatSessionBase):
    is_incognito: bool = False
    first_message: Optional[str] = None

class ChatSessionUpdate(BaseModel):
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
    message: str = Field(..., min_length=1, max_length=4000)
    chat_id: Optional[int] = None
    data_source: str = DataSource.COMPANY_FAQS
    is_incognito: bool = False
    context_messages: Optional[int] = Field(10, ge=1, le=50)   
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)   

    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()
    
    @field_validator('data_source')
    @classmethod
    def validate_data_source(cls, v: str) -> str:
        valid_sources = [e.value for e in DataSource]
        if v not in valid_sources:
            raise ValueError(f'Invalid data source. Must be one of: {valid_sources}')
        return v
class ChatResponse(BaseModel):
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
    chats: List[ChatSession]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False

class ChatHistoryResponse(BaseModel):
    chat: ChatSession
    messages: List[ChatMessage]
    total_messages: int = 0
    has_more: bool = False

class UpdateChatRequest(BaseModel):

    title: Optional[str] = None
    is_archived: Optional[bool] = None
    is_pinned: Optional[bool] = None

class SearchChatsRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    include_archived: bool = False
    limit: int = Field(50, ge=1, le=100) 

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Search query cannot be empty')
        return v.strip()

class ChatModeStatus(BaseModel):
    """Response model for current chat mode status."""
    has_incognito_chats: bool = False
    incognito_chat_count: int = 0
    total_chats: int = 0
    active_incognito_sessions: List[int] = []


CreateChatRequest = ChatSessionCreate
Message = ChatMessage
MessageResponse = ChatMessage
ChatSessionResponse = ChatSession