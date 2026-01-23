"""
Pydantic schemas for Chat models - API validation and serialization.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DataSource(str, Enum):
    COMPANY_FAQS = "company_faqs"
    UPLOADED_FILES = "uploaded_files"
    GENERAL_KNOWLEDGE = "general_knowledge"


# =============================================================================
# Chat Session Schemas
# =============================================================================

class ChatSessionBase(BaseModel):
    """Base chat session schema."""
    title: Optional[str] = None
    is_archived: bool = False
    is_pinned: bool = False


class ChatSessionCreate(ChatSessionBase):
    """Schema for creating a new chat session."""
    is_incognito: bool = False
    first_message: Optional[str] = None


class ChatSessionUpdate(BaseModel):
    """Schema for updating chat session."""
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    is_pinned: Optional[bool] = None


class ChatSession(ChatSessionBase):
    """Full chat session schema for API responses."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_incognito: bool = False
    message_count: Optional[int] = 0
    last_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Message Schemas
# =============================================================================

class MessageBase(BaseModel):
    """Base message schema."""
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        validation_alias="message_metadata"  
    )
    
    @field_validator('metadata', mode='before')
    @classmethod
    def parse_metadata(cls, v):
        """Parse metadata from JSON string if needed."""
        if v is None:
            return {}
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v


class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    chat_id: Optional[int] = None


class ChatMessage(MessageBase):
    """Full message schema for API responses."""
    id: int
    chat_id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True  
    )


# =============================================================================
# API Request/Response Schemas
# =============================================================================

class ChatRequest(BaseModel):
    """Schema for chat API request."""
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
    """Schema for chat API response."""
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
    """Schema for paginated chat list response."""
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
    has_incognito_chats: bool = False
    incognito_chat_count: int = 0
    total_chats: int = 0
    active_incognito_sessions: List[int] = []


# =============================================================================
# Additional Response Schemas
# =============================================================================

class CreateSessionResponse(BaseModel):
    chat_id: int
    is_incognito: bool = False
    title: Optional[str] = None


class SearchChatsResponse(BaseModel):
    results: List[ChatSession]
    total: int


class MessageResponse(BaseModel):
    """Schema for simple message response."""
    message: str
    chat_id: Optional[int] = None


class ClearIncognitoResponse(BaseModel):
    status: str = "ok"
    cleared: int = 0


class SwitchModeResponse(BaseModel):
    status: str
    mode: str
    chat_id: Optional[int] = None


CreateChatRequest = ChatSessionCreate
Message = ChatMessage
ChatSessionResponse = ChatSession
