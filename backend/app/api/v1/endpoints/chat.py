"""
Chat endpoints with incognito mode for authenticated users.
"""
from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatListResponse,
    ChatHistoryResponse,
    CreateChatRequest,
    UpdateChatRequest,
    SearchChatsRequest,
    ChatModeStatus,
    ChatSession
)
from app.models.user import User
from app.auth.deps import get_current_user
from app.services.chat_service import chat_service
from app.services.chat_manager import chat_manager

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Send a message to the chat and get a response."""
    try:
        # Create new chat if needed - БЕЗ await
        if not request.chat_id:
            request.chat_id = chat_manager.create_chat(   
                user_id=current_user.id,
                first_message=request.message,
                is_incognito=request.is_incognito
            )
        
        # Add user message to history - БЕЗ await
        chat_manager.add_message(  
            chat_id=request.chat_id,
            role="user",
            content=request.message
        )
        
        # Get AI response - ОСТАВЛЯЕМ await (это async метод)
        response = await chat_service.get_response(  # ✅ await остается
            message=request.message,
            data_source=request.data_source,
            user_id=current_user.id
        )
        
        # Add assistant message to history - БЕЗ await
        message_id = chat_manager.add_message(  
            chat_id=request.chat_id,
            role="assistant",
            content=response["response"],
            metadata={"sources": response.get("sources")}
        )
        
        return ChatResponse(
            response=response["response"],
            chat_id=request.chat_id if not request.is_incognito else None,
            message_id=message_id,
            is_incognito=request.is_incognito,
            sources=response.get("sources")
        )
        
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=ChatListResponse)
async def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    include_archived: bool = False,
    include_incognito: bool = False,
    page: int = 1,
    page_size: int = 20
):
    """Get user's chat sessions."""
    try:
        # БЕЗ await
        result = chat_manager.get_user_chats(  
            user_id=current_user.id,
            include_archived=include_archived,
            include_incognito=include_incognito,
            page=page,
            page_size=page_size
        )
        
        return ChatListResponse(**result)
    except Exception as e:
        logger.error(f"Error fetching chat sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    limit: Optional[int] = None,
    offset: int = 0
):
    """Get chat history."""
    try:
        result = chat_manager.get_chat_history(
            chat_id=chat_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        # Добавляем user_id в данные чата и считаем количество сообщений
        chat_data = result["chat"]
        chat_data["user_id"] = current_user.id  # Добавляем user_id
        
        return ChatHistoryResponse(
            chat=ChatSession(**chat_data),
            messages=result["messages"],
            total_messages=len(result["messages"])
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions", response_model=dict)
async def create_chat_session(
    current_user: User = Depends(get_current_user),
    title: Optional[str] = None,
    is_incognito: bool = False
):
    """Create a new chat session."""
    try:
        # БЕЗ await
        chat_id = chat_manager.create_chat(  
            user_id=current_user.id,
            title=title,
            is_incognito=is_incognito
        )
        
        return {"chat_id": chat_id}
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mode/status", response_model=ChatModeStatus)
async def get_chat_mode_status(
    current_user: User = Depends(get_current_user)
):
    """Get chat mode status."""
    try:
        # БЕЗ await
        status = chat_manager.get_chat_mode_status(  
            user_id=current_user.id
        )
        
        return ChatModeStatus(**status)
    except Exception as e:
        logger.error(f"Error getting chat mode status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/incognito/clear")
async def clear_incognito_chats(
    current_user: User = Depends(get_current_user)
):
    """Clear all incognito chats for the current user."""
    try:
        # БЕЗ await
        cleared_count = chat_manager.clear_incognito_chats(  # ❌ убрали await
            user_id=current_user.id
        )
        
        return {"message": f"Cleared {cleared_count} incognito chats"}
    except Exception as e:
        logger.error(f"Error clearing incognito chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/sessions/{chat_id}")
async def update_chat_session(
    chat_id: int,
    request: UpdateChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Update chat session."""
    try:
        # БЕЗ await
        success = chat_manager.update_chat(  
            chat_id=chat_id,
            user_id=current_user.id,
            title=request.title,
            is_archived=request.is_archived
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return {"message": "Chat updated successfully"}
    except Exception as e:
        logger.error(f"Error updating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{chat_id}")
async def delete_chat_session(
    chat_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete chat session."""
    try:
        # БЕЗ await
        success = chat_manager.delete_chat(  # ❌ убрали await
            chat_id=chat_id,
            user_id=current_user.id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return {"message": "Chat deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search", response_model=list)
async def search_chats(
    request: SearchChatsRequest,
    current_user: User = Depends(get_current_user)
):
    """Search in user's chats."""
    try:
        # БЕЗ await
        results = chat_manager.search_chats(  
            user_id=current_user.id,
            query=request.query,
            include_archived=request.include_archived,
            limit=request.limit
        )
        
        return results
    except Exception as e:
        logger.error(f"Error searching chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))