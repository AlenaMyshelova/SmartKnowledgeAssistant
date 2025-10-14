"""
Chat-related data models with incognito mode support.
"""
 
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

 

class ChatMessage(BaseModel):
    """Model for a single chat message."""
    id: Optional[int] = None
    chat_id: int
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class ChatSession(BaseModel):
    """Model for a chat session."""
    id: Optional[int] = None
    user_id: int  # Always required since only authenticated users have access
    title: Optional[str] = "New Chat"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_archived: bool = False
    is_incognito: bool = False  # Flag for incognito mode (not saved to history)
    message_count: int = 0
    last_message: Optional[str] = None


class ChatRequest(BaseModel):
    """Request model for chat messages."""
    message: str
    chat_id: Optional[int] = None
    data_source: str = "company_faqs"
    is_incognito: bool = False  # User can choose incognito mode


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str
    chat_id: Optional[int] = None  # Optional for incognito mode
    message_id: Optional[int] = None  # Optional for incognito mode
    is_incognito: bool = False
    sources: Optional[List[Dict[str, Any]]] = None


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


class SearchChatsRequest(BaseModel):
    """Request model for searching chats."""
    query: str
    include_archived: bool = False
    limit: int = 50


class ChatModeStatus(BaseModel):
    """Response model for current chat mode status."""
    mode: str  # 'normal' or 'incognito'
    active_incognito_chats: int
    saved_chats: int