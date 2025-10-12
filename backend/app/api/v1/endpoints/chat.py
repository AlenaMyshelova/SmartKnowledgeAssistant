"""
Chat endpoints with incognito mode for authenticated users.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatListResponse,
    ChatHistoryResponse,
    CreateChatRequest,
    UpdateChatRequest,
    SearchChatsRequest,
    ChatModeStatus
)
from app.models.user import User
from app.auth.deps import get_current_user
from app.services.chat_service import chat_service
from app.services.chat_manager import chat_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Send a message to the chat and get a response.
    Supports both normal and incognito modes.
    """
    try:
        # Create new chat if needed
        if not request.chat_id:
            request.chat_id = await chat_manager.create_chat(
                user_id=current_user.id,
                first_message=request.message,
                is_incognito=request.is_incognito
            )
        
        # Add user message to history (or memory for incognito)
        await chat_manager.add_message(
            chat_id=request.chat_id,
            role="user",
            content=request.message
        )
        
        # Get AI response
        response = await chat_service.get_response(
            message=request.message,
            data_source=request.data_source,
            user_id=current_user.id
        )
        
        # Add assistant message to history (or memory for incognito)
        message_id = await chat_manager.add_message(
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
    page: int = 1,
    page_size: int = 20,
    include_archived: bool = False,
    include_incognito: bool = False,
    current_user: User = Depends(get_current_user)
):
    """
    Get all chat sessions for the current user.
    By default, excludes incognito chats.
    """
    try:
        result = await chat_manager.get_user_chats(
            user_id=current_user.id,
            include_archived=include_archived,
            include_incognito=include_incognito,
            page=page,
            page_size=page_size
        )
        return ChatListResponse(**result)
        
    except Exception as e:
        logger.error(f"Error getting chat sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: int,
    limit: Optional[int] = None,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """
    Get chat history with all messages.
    Works for both normal and incognito chats.
    """
    try:
        result = await chat_manager.get_chat_history(
            chat_id=chat_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return ChatHistoryResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions", response_model=dict)
async def create_chat_session(
    request: CreateChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new chat session (normal or incognito).
    """
    try:
        chat_id = await chat_manager.create_chat(
            user_id=current_user.id,
            title=request.title,
            first_message=request.first_message,
            is_incognito=request.is_incognito
        )
        
        return {
            "chat_id": chat_id,
            "is_incognito": request.is_incognito,
            "message": f"{'Incognito' if request.is_incognito else 'Normal'} chat created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mode/status", response_model=ChatModeStatus)
async def get_chat_mode_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current chat mode status for the user.
    Shows number of active incognito chats and saved chats.
    """
    try:
        status = await chat_manager.get_chat_mode_status(current_user.id)
        
        # Determine current mode based on active chats
        mode = "incognito" if status['active_incognito_chats'] > 0 else "normal"
        
        return ChatModeStatus(
            mode=mode,
            active_incognito_chats=status['active_incognito_chats'],
            saved_chats=status['saved_chats']
        )
        
    except Exception as e:
        logger.error(f"Error getting chat mode status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/incognito/clear")
async def clear_incognito_chats(
    current_user: User = Depends(get_current_user)
):
    """
    Clear all incognito chats for the current user.
    This removes them from memory completely.
    """
    try:
        cleared_count = await chat_manager.clear_incognito_chats(current_user.id)
        
        return {
            "message": f"Successfully cleared {cleared_count} incognito chats",
            "cleared_count": cleared_count
        }
        
    except Exception as e:
        logger.error(f"Error clearing incognito chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{chat_id}")
async def update_chat_session(
    chat_id: int,
    request: UpdateChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update chat session (rename, archive, etc).
    Only works for normal chats, not incognito.
    """
    try:
        # Prevent updating incognito chats
        if chat_id < 0:
            raise HTTPException(
                status_code=403,
                detail="Cannot update incognito chats"
            )
        
        success = await chat_manager.update_chat(
            chat_id=chat_id,
            user_id=current_user.id,
            title=request.title,
            is_archived=request.is_archived
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        return {"message": "Chat updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{chat_id}")
async def delete_chat_session(
    chat_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a chat session and all its messages.
    For incognito chats, just removes from memory.
    """
    try:
        # Handle incognito chats differently
        if chat_id < 0:
            # Just remove from memory
            if chat_id in chat_manager.incognito_chats:
                if chat_manager.incognito_chats[chat_id]['user_id'] == current_user.id:
                    del chat_manager.incognito_chats[chat_id]
                    if chat_id in chat_manager.incognito_messages:
                        del chat_manager.incognito_messages[chat_id]
                    return {"message": "Incognito chat removed successfully"}
                else:
                    raise HTTPException(status_code=403, detail="Access denied")
            else:
                raise HTTPException(status_code=404, detail="Incognito chat not found")
        
        # Normal chat deletion
        success = await chat_manager.delete_chat(
            chat_id=chat_id,
            user_id=current_user.id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        return {"message": "Chat deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=list)
async def search_chats(
    request: SearchChatsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Search through user's saved chat history.
    Does not search in incognito chats.
    """
    try:
        results = await chat_manager.search_chats(
            user_id=current_user.id,
            query=request.query,
            include_archived=request.include_archived,
            limit=request.limit
        )
        return results
        
    except Exception as e:
        logger.error(f"Error searching chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))