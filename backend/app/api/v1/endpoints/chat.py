from typing import Optional
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.chat_service import chat_service
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatListResponse,
    ChatHistoryResponse,
    ChatSessionCreate,
    UpdateChatRequest,
    SearchChatsRequest,
    ChatSession,
    ChatMessage,
)
from app.models.user import User
from app.auth.deps import get_current_user
from app.database import db_manager  # только для поиска (persisted)

router = APIRouter(tags=["chat"])

logger = logging.getLogger(__name__)


# ===========================
# Message
# ===========================
@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Отправка сообщения:
    - если chat_id отсутствует → создаём чат (incognito или обычный) в ChatService
    - сохраняем user/assistant сообщения (incognito — в памяти)
    - возвращаем ответ + источники
    """
    try:
        start = time.time()

        # Создать чат при необходимости
        chat_id = request.chat_id
        if not chat_id:
            session = await chat_service.create_chat_session(
                user_id=current_user.id,
                title=(request.message[:50] + ("..." if len(request.message) > 50 else "")),
                is_incognito=bool(request.is_incognito),
            )
            if not session:
                raise HTTPException(status_code=500, detail="Failed to create chat")
            chat_id = session.id

        # Проверка владельца
        owns = await chat_service.verify_chat_owner(chat_id, current_user.id)
        if not owns:
            raise HTTPException(status_code=404, detail="Chat not found or access denied")

        # Получить ответ + источники
        result = await chat_service.get_response_with_sources(
            chat_id=chat_id,
            user_message=request.message,
            data_source=request.data_source or "company_faqs",
        )

        return ChatResponse(
            response=result["response"],
            chat_id=result["chat_id"],
            message_id=result["message_id"],
            user_message_id=None,  # при желании можно вернуть из ChatService
            is_incognito=(result["chat_id"] < 0),
            sources=result["sources"],
            processing_time=time.time() - start,
            metadata={"temperature": request.temperature},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /chat/send")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================
# Sessions
# ===========================

@router.post("/sessions", response_model=dict)
async def create_chat_session(
    request: ChatSessionCreate | None = None,
    current_user: User = Depends(get_current_user),
):
    """Создать новый чат (incognito или обычный)."""
    try:
        request = request or ChatSessionCreate()
        session = await chat_service.create_chat_session(
            user_id=current_user.id,
            title=request.title,
            is_incognito=bool(request.is_incognito),
        )
        if not session:
            raise HTTPException(status_code=500, detail="Failed to create chat")

        # если передан first_message — сразу прогоняем через пайплайн
        if request.first_message:
            await chat_service.get_response_with_sources(
                chat_id=session.id,
                user_message=request.first_message,
                data_source="company_faqs",
            )

        return {"chat_id": session.id, "is_incognito": session.is_incognito, "title": session.title}
    except Exception as e:
        logger.exception("Error creating chat session")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/sessions/search")
async def search_chats(
    query: str = Query(..., min_length=1, max_length=200),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Поиск по истории пользовательских чатов (в БД)."""
    try:
        db_results = db_manager.search_chats(
            user_id=current_user.id,
            query=query,
            include_archived=include_archived,
            limit=limit,
        )
        return {"results": db_results, "total": len(db_results)}
    except Exception as e:
        logger.exception("Error searching chats")
        raise HTTPException(status_code=500, detail=str(e)) 
      
@router.get("/sessions", response_model=ChatListResponse)
async def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    include_archived: bool = Query(False),
    include_incognito: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Список чатов пользователя (по умолчанию без incognito)."""
    try:
        chats = await chat_service.get_user_chats(
            user_id=current_user.id,
            include_archived=include_archived,
            include_incognito=include_incognito,
        )
        # простая пагинация по списку
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
        raise HTTPException(status_code=500, detail=str(e))





@router.get("/sessions/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """История сообщений для любого чата (incognito + persisted)."""
    try:
        owns = await chat_service.verify_chat_owner(chat_id, current_user.id)
        if not owns:
            raise HTTPException(status_code=404, detail="Chat not found or access denied")

        messages = await chat_service.get_chat_messages(chat_id, limit=limit, offset=offset)

        # Построим ChatSession «на лету» (берём из объединённого списка)
        chats = await chat_service.get_user_chats(current_user.id, include_archived=True, include_incognito=True)
        chat_meta = next((c for c in chats if c.id == chat_id), None)
        if not chat_meta:
            raise HTTPException(status_code=404, detail="Chat not found")

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
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{chat_id}")
async def update_chat_session(
    chat_id: int,
    request: UpdateChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Обновить свойства обычного чата (incognito — запрещено)."""
    try:
        if chat_id < 0:
            raise HTTPException(status_code=400, detail="Cannot update incognito chat")

        owns = await chat_service.verify_chat_owner(chat_id, current_user.id)
        if not owns:
            raise HTTPException(status_code=404, detail="Chat not found or access denied")

        updated = await chat_service.update_chat(
            chat_id=chat_id,
            title=request.title,
            is_archived=request.is_archived,
            is_pinned=request.is_pinned,
        )
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update chat")
        return {"message": "Chat updated successfully", "chat_id": chat_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating chat session")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{chat_id}")
async def delete_chat_session(
    chat_id: int,
    current_user: User = Depends(get_current_user),
):
    """Удалить чат (incognito стирается из памяти, обычный — из БД)."""
    try:
        owns = await chat_service.verify_chat_owner(chat_id, current_user.id)
        if not owns:
            raise HTTPException(status_code=404, detail="Chat not found or access denied")

        ok = await chat_service.delete_chat(chat_id)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to delete chat")
        return {"message": "Chat deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting chat session")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================
# Search (только по persisted)
# ===========================



 


# ===========================
# Incognito management
# ===========================
@router.delete("/incognito/clear")
async def clear_incognito(
    user: User = Depends(get_current_user),
):
    """Очистить ВСЕ инкогнито-чаты пользователя из памяти."""
    cleared = chat_service.clear_incognito_chats(user.id)
    return {"status": "ok", "cleared": cleared}


@router.post("/mode")
async def switch_mode(payload: dict, user: User = Depends(get_current_user)):
    """
    Переключить режим пользователя:
    - to_incognito=True → просто отмечаем режим
    - to_incognito=False → мгновенно чистим все инкогнито-чаты
    """
    to_incognito = bool(payload.get("to_incognito"))
    return await chat_service.switch_user_mode(user.id, to_incognito)
