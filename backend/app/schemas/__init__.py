"""
Pydantic schemas for API validation.
"""
from app.schemas.user import (
    UserBase, UserCreate, UserUpdate, UserInDB, User,
    TokenData, Token, OAuthProvider, OAuthProvidersResponse
    
)
from app.schemas.chat import (
    MessageRole, DataSource,
    ChatSessionBase, ChatSessionCreate, ChatSessionUpdate, ChatSession,
    MessageBase, MessageCreate, ChatMessage,
    ChatRequest, ChatResponse, ChatListResponse, ChatHistoryResponse,
    UpdateChatRequest, SearchChatsRequest, ChatModeStatus,
    CreateChatRequest, Message, MessageResponse, ChatSessionResponse
)

__all__ = [
    # User schemas
    "UserBase", "UserCreate", "UserUpdate", "UserInDB", "User",
    "TokenData", "Token", "OAuthProvider", "OAuthProvidersResponse",
    # Chat schemas
    "MessageRole", "DataSource",
    "ChatSessionBase", "ChatSessionCreate", "ChatSessionUpdate", "ChatSession",
    "MessageBase", "MessageCreate", "ChatMessage",
    "ChatRequest", "ChatResponse", "ChatListResponse", "ChatHistoryResponse",
    "UpdateChatRequest", "SearchChatsRequest", "ChatModeStatus",
    "CreateChatRequest", "Message", "MessageResponse", "ChatSessionResponse",
]
