from typing import Optional, Annotated
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.services.chat_service import chat_service
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatListResponse,
    ChatHistoryResponse,
    ChatSessionCreate,
    UpdateChatRequest,
    SearchChatsRequest,
    ChatSession,
    ChatMessage,
    CreateSessionResponse,
    SearchChatsResponse,
    MessageResponse,
    ClearIncognitoResponse,
    SwitchModeResponse,
)
from app.schemas.user import User
from app.dependencies import get_current_user


router = APIRouter(
    tags=["chat"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Not authenticated"},
        status.HTTP_404_NOT_FOUND: {"description": "Chat not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)
logger = logging.getLogger(__name__)

# Type alias для Annotated Dependency (FastAPI Best Practice)
CurrentUser = Annotated[User, Depends(get_current_user)]


# ===========================
# Message
# ===========================

@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: CurrentUser,
):
    """
    Отправка сообщения:
    - если chat_id отсутствует → создаём чат (incognito или обычный) в ChatService
    - сохраняем user/assistant сообщения (incognito — в памяти)
    - возвращаем ответ + источники
    """
    try:
        start = time.time()
        chat_id = request.chat_id
        if not chat_id:
            session = await chat_service.create_chat_session(
                user_id=current_user.id,
                title=(request.message[:50] + ("..." if len(request.message) > 50 else "")),
                is_incognito=bool(request.is_incognito),
            )
            if not session:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create chat session")
            chat_id = session.id

        owns = await chat_service.verify_chat_owner(chat_id, current_user.id)
        if not owns:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")
        result = await chat_service.get_response_with_sources(
            chat_id=chat_id,
            user_message=request.message,
            data_source=request.data_source or "company_faqs",
        )

        return ChatResponse(
            response=result["response"],
            chat_id=result["chat_id"],
            message_id=result["message_id"],
            user_message_id=None,  
            is_incognito=(result["chat_id"] < 0),
            sources=result["sources"],
            processing_time=time.time() - start,
            metadata={"temperature": request.temperature},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /chat/send")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ===========================
# Sessions
# ===========================

@router.post("/sessions", response_model=CreateSessionResponse)
async def create_chat_session(
    current_user: CurrentUser,
    request: ChatSessionCreate | None = None,
):
    try:
        request = request or ChatSessionCreate()
        session = await chat_service.create_chat_session(
            user_id=current_user.id,
            title=request.title,
            is_incognito=bool(request.is_incognito),
        )
        if not session:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create chat session")

        if request.first_message:
            await chat_service.get_response_with_sources(
                chat_id=session.id,
                user_message=request.first_message,
                data_source="company_faqs",
            )

        return CreateSessionResponse(chat_id=session.id, is_incognito=session.is_incognito, title=session.title)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating chat session")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
@router.get("/sessions/search")
async def search_chats(
    current_user: CurrentUser,
    query: str = Query(..., min_length=1, max_length=200),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    """Search user's chats by query in titles and messages."""
    try:
        results = await chat_service.search_user_chats(
            user_id=current_user.id,
            query=query,
            include_archived=include_archived,
            limit=limit,
        )
        # Возвращаем как есть - результаты поиска с match_type
        return {"results": results, "total": len(results)}
    except Exception as e:
        logger.exception("Error searching chats")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) 
      
@router.get("/sessions", response_model=ChatListResponse)
async def get_chat_sessions(
    current_user: CurrentUser,
    include_archived: bool = Query(False),
    include_incognito: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        chats = await chat_service.get_user_chats(
            user_id=current_user.id,
            include_archived=include_archived,
            include_incognito=include_incognito,
        )
        start = (page - 1) * page_size
        end = start + page_size
        total = len(chats)
        return ChatListResponse(
            chats=chats[start:end],
            total=total,
            page=page,
            page_size=page_size,
            has_more=end < total,
        )
    except Exception as e:
        logger.exception("Error fetching chat sessions")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    

@router.get("/sessions/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: int,
    current_user: CurrentUser,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    try:
        owns = await chat_service.verify_chat_owner(chat_id, current_user.id)
        if not owns:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")
        
        messages = await chat_service.get_chat_messages(chat_id, limit=limit, offset=offset)
        chat_meta = await chat_service.get_chat_session(chat_id, current_user.id)
        if not chat_meta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

        return ChatHistoryResponse(
            chat=chat_meta,
            messages=messages,
            total_messages=chat_meta.message_count if chat_meta.message_count is not None else len(messages),
            has_more=(False if not limit else len(messages) == limit),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching chat history")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.patch("/sessions/{chat_id}", response_model=MessageResponse)
async def update_chat_session(
    chat_id: int,
    request: UpdateChatRequest,
    current_user: CurrentUser,
):
    try:
        if chat_id < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update incognito chat")

        owns = await chat_service.verify_chat_owner(chat_id, current_user.id)
        if not owns:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

        updated = await chat_service.update_chat(
            chat_id=chat_id,
            title=request.title,
            is_archived=request.is_archived,
            is_pinned=request.is_pinned,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update chat")
        return MessageResponse(message="Chat updated successfully", chat_id=chat_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating chat session")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/sessions/{chat_id}", response_model=MessageResponse)
async def delete_chat_session(
    chat_id: int,
    current_user: CurrentUser,
):
    try:
        owns = await chat_service.verify_chat_owner(chat_id, current_user.id)
        if not owns:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

        ok = await chat_service.delete_chat(chat_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chat")
        return MessageResponse(message="Chat deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting chat session")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



# ===========================
# Incognito management
# ===========================
@router.delete("/incognito/clear", response_model=ClearIncognitoResponse)
async def clear_incognito(
    user: CurrentUser,
):
    """Очистить все incognito чаты пользователя."""
    cleared = chat_service.clear_incognito_chats(user.id)
    return ClearIncognitoResponse(status="ok", cleared=cleared)


@router.post("/mode", response_model=SwitchModeResponse)
async def switch_mode(
    payload: dict,
    user: CurrentUser,
):
    """Переключить режим чата (обычный/incognito)."""
    to_incognito = bool(payload.get("to_incognito"))
    result = await chat_service.switch_user_mode(user.id, to_incognito)
    return SwitchModeResponse(**result)
