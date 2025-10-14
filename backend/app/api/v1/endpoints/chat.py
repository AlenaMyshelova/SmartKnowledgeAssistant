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
        # Проверяем режим incognito
        if request.is_incognito:
            # Для incognito используем отрицательные ID
            if not request.chat_id or request.chat_id > 0:
                # Создаем новый incognito чат с отрицательным ID
                request.chat_id = chat_manager.create_chat(   
                    user_id=current_user.id,
                    title="Incognito Chat",
                    is_incognito=True  # Это создаст отрицательный ID
                )
            
            # Добавляем сообщение в память (НЕ в БД)
            chat_manager.add_message(  
                chat_id=request.chat_id,
                role="user",
                content=request.message
            )
            
            # Получаем ответ AI
            response = await chat_service.get_response(
                message=request.message,
                data_source=request.data_source,
                user_id=current_user.id
            )
            
            # Добавляем ответ в память (НЕ в БД)
            message_id = chat_manager.add_message(  
                chat_id=request.chat_id,
                role="assistant",
                content=response["response"],
                metadata={"sources": response.get("sources")}
            )
            
            return ChatResponse(
                response=response["response"],
                chat_id=request.chat_id,  # Возвращаем отрицательный ID
                message_id=message_id,
                is_incognito=True,
                sources=response.get("sources")
            )
        
        # Обычный режим - сохраняем в БД
        else:
            if not request.chat_id:
                request.chat_id = chat_manager.create_chat(   
                    user_id=current_user.id,
                    first_message=request.message,
                    is_incognito=False  # Обычный чат с положительным ID
                )
            
            # Сохраняем в БД
            chat_manager.add_message(  
                chat_id=request.chat_id,
                role="user",
                content=request.message
            )
            
            response = await chat_service.get_response(
                message=request.message,
                data_source=request.data_source,
                user_id=current_user.id
            )
            
            # Сохраняем в БД
            message_id = chat_manager.add_message(  
                chat_id=request.chat_id,
                role="assistant",
                content=response["response"],
                metadata={"sources": response.get("sources")}
            )
            
            return ChatResponse(
                response=response["response"],
                chat_id=request.chat_id,
                message_id=message_id,
                is_incognito=False,
                sources=response.get("sources")
            )
        
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=ChatListResponse)
async def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    include_archived: bool = False,
    include_incognito: bool = False,  # По умолчанию НЕ показываем incognito
    page: int = 1,
    page_size: int = 20
):
    """Get user's chat sessions."""
    try:
        result = chat_manager.get_user_chats(  
            user_id=current_user.id,
            include_archived=include_archived,
            include_incognito=include_incognito,  # Передаем флаг
            page=page,
            page_size=page_size
        )
        
        # Дополнительная фильтрация на всякий случай
        if not include_incognito:
            # Убираем чаты с отрицательными ID и флагом is_incognito
            result["chats"] = [
                chat for chat in result["chats"] 
                if chat.get("id", 0) > 0 and not chat.get("is_incognito", False)
            ]
        
        return ChatListResponse(**result)
    except Exception as e:
        logger.error(f"Error fetching chat sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/sessions/search")
async def search_chats_get(
        query: str,
        include_archived: bool = False,
        limit: int = 50,
        current_user: User = Depends(get_current_user)
    ):
        """Search in user's chat history via GET request."""
        try:
            logger.info(f"Searching for '{query}' for user {current_user.id}")
            
            results = chat_manager.search_chats(  
                user_id=current_user.id,
                query=query,
                include_archived=include_archived,
                limit=limit
            )
            
            # Фильтруем incognito чаты из результатов поиска
            filtered_results = [
                r for r in results 
                if r.get("id", 0) > 0 and not r.get("is_incognito", False)
            ]
            
            logger.info(f"Found {len(filtered_results)} results after filtering")
            
            return {"results": filtered_results}
        except Exception as e:
            logger.error(f"Error searching chats: {str(e)}")
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
        
        chat_data = result["chat"]
        chat_data["user_id"] = current_user.id
        
        # Проверяем, что это incognito чат
        if chat_id < 0:
            chat_data["is_incognito"] = True
        
        messages = []
        for msg in result["messages"]:
            msg["chat_id"] = chat_id
            messages.append(msg)
        
        return ChatHistoryResponse(
            chat=ChatSession(**chat_data),
            messages=messages,
            total_messages=len(messages)
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
        chat_id = chat_manager.create_chat(  
            user_id=current_user.id,
            title=title or ("Incognito Chat" if is_incognito else "New Chat"),
            is_incognito=is_incognito
        )
        
        return {"chat_id": chat_id, "is_incognito": is_incognito}
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mode/status", response_model=ChatModeStatus)
async def get_chat_mode_status(
    current_user: User = Depends(get_current_user)
):
    """Get chat mode status."""
    try:
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
        cleared_count = chat_manager.clear_incognito_chats(
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
        # Запрещаем обновление incognito чатов
        if chat_id < 0:
            raise HTTPException(
                status_code=400, 
                detail="Cannot update incognito chat - it's temporary"
            )
        
        success = chat_manager.update_chat(  
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
    """Delete chat session."""
    try:
        # Для incognito чатов - удаляем из памяти
        if chat_id < 0:
            chat_manager.clear_incognito_chats(user_id=current_user.id)
            return {"message": "Incognito chat cleared from memory"}
        
        # Для обычных чатов - удаляем из БД
        success = chat_manager.delete_chat(
            chat_id=chat_id,
            user_id=current_user.id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return {"message": "Chat deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_chats(
    request: SearchChatsRequest,
    current_user: User = Depends(get_current_user)
):
    """Search in user's chats."""
    try:
        results = chat_manager.search_chats(  
            user_id=current_user.id,
            query=request.query,
            include_archived=request.include_archived,
            limit=request.limit
        )
        
        # Фильтруем incognito чаты из результатов поиска
        # Они не должны появляться в поиске
        results = [
            r for r in results 
            if r.get("id", 0) > 0 and not r.get("is_incognito", False)
        ]
        
        return results
    except Exception as e:
        logger.error(f"Error searching chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
