"""
Chat endpoints using SQLAlchemy with database.py manager.
Supports incognito mode through temporary in-memory storage.
"""
from typing import Optional, List, Dict, Any
import logging
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks

from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatListResponse,
    ChatHistoryResponse,
    ChatSessionCreate,
    UpdateChatRequest,
    SearchChatsRequest,
    ChatModeStatus,
    ChatSession,
    ChatMessage
)
from app.models.user import User
from app.auth.deps import get_current_user
from app.database import db_manager  # ✅ Используем глобальный экземпляр
from app.services.openai_service import OpenAIService
from app.services.data_service import DataService

router = APIRouter()
logger = logging.getLogger(__name__)

# Services
openai_service = OpenAIService()
data_service = DataService()

 

# In-memory storage for incognito chats (negative IDs)
INCOGNITO_CHATS: Dict[int, Dict] = {}
INCOGNITO_COUNTER = -1

def get_next_incognito_id() -> int:
    """Get next negative ID for incognito chat."""
    global INCOGNITO_COUNTER
    current = INCOGNITO_COUNTER
    INCOGNITO_COUNTER -= 1
    return current

# ===========================
# Message Endpoints
# ===========================

@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Send a message and get AI response.
    Supports both regular (SQLAlchemy) and incognito (in-memory) modes.
    """
    try:
        start_time = time.time()
        
        # Handle incognito mode (in-memory only)
        if request.is_incognito:
            # Create or get incognito chat ID
            if not request.chat_id or request.chat_id > 0:
                request.chat_id = get_next_incognito_id()
                # Store in memory
                INCOGNITO_CHATS[request.chat_id] = {
                    "id": request.chat_id,
                    "user_id": current_user.id,
                    "title": "Incognito Chat",
                    "messages": [],
                    "created_at": datetime.utcnow()
                }
            
            # Check if incognito chat exists
            if request.chat_id not in INCOGNITO_CHATS:
                raise HTTPException(status_code=404, detail="Incognito chat not found")
            
            # Verify ownership
            if INCOGNITO_CHATS[request.chat_id]["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Add user message to memory
            user_msg = {
                "id": len(INCOGNITO_CHATS[request.chat_id]["messages"]) + 1,
                "role": "user",
                "content": request.message,
                "created_at": datetime.utcnow()
            }
            INCOGNITO_CHATS[request.chat_id]["messages"].append(user_msg)
            
            # Get context for AI
            context_messages = INCOGNITO_CHATS[request.chat_id]["messages"][-request.context_messages:]
            
            # Get AI response
            ai_response = await openai_service.get_chat_response(
                messages=[{"role": m["role"], "content": m["content"]} for m in context_messages],
                temperature=request.temperature
            )
            
            # Get sources if using data source
            sources = []
            if request.data_source != "general_knowledge":
                sources = await data_service.search_similar(
                    query=request.message,
                    data_source=request.data_source,
                    top_k=3
                )
            
            # Add assistant message to memory
            assistant_msg = {
                "id": len(INCOGNITO_CHATS[request.chat_id]["messages"]) + 1,
                "role": "assistant",
                "content": ai_response["content"],
                "created_at": datetime.utcnow(),
                "metadata": {
                    "sources": sources,
                    "tokens": ai_response.get("tokens_used")
                }
            }
            INCOGNITO_CHATS[request.chat_id]["messages"].append(assistant_msg)
            
            processing_time = time.time() - start_time
            
            return ChatResponse(
                response=ai_response["content"],
                chat_id=request.chat_id,
                message_id=assistant_msg["id"],
                user_message_id=user_msg["id"],
                is_incognito=True,
                sources=sources,
                tokens_used=ai_response.get("tokens_used"),
                processing_time=processing_time,
                metadata={"model": ai_response.get("model")}
            )
        
        # Regular mode - save to database using db_manager
        else:
            # Create chat if needed
            if not request.chat_id:
                # ✅ Используем db_manager напрямую без параметра db
                chat = db_manager.create_chat_session(
                    user_id=current_user.id,
                    title=f"Chat about: {request.message[:50]}...",
                    is_incognito=False
                )
                if not chat:
                    raise HTTPException(status_code=500, detail="Failed to create chat")
                request.chat_id = chat.id
            else:
                # ✅ Verify chat exists and user owns it
                sessions = db_manager.get_user_chat_sessions(
                    user_id=current_user.id,
                    limit=1000
                )
                if not any(s.id == request.chat_id for s in sessions):
                    raise HTTPException(status_code=403, detail="Access denied or chat not found")
            
            # ✅ Save user message to database
            user_msg = db_manager.add_message_to_chat(
                chat_id=request.chat_id,
                role="user",
                content=request.message
            )
            
            # ✅ Get context messages from database  
            context_messages = db_manager.get_chat_messages(
                chat_id=request.chat_id,
                limit=request.context_messages
            )
            
            # Prepare messages for AI
            messages_for_ai = [
                {"role": msg.role, "content": msg.content}
                for msg in context_messages
            ]
            
            # Get AI response
            ai_response = await openai_service.get_chat_response(
                messages=messages_for_ai,
                temperature=request.temperature
            )
            
            # Get sources if needed
            sources = []
            if request.data_source != "general_knowledge":
                sources = await data_service.search_similar(
                    query=request.message,
                    data_source=request.data_source,
                    top_k=3
                )
            
            # ✅ Save assistant response to database
            assistant_msg = db_manager.add_message_to_chat(
                chat_id=request.chat_id,
                role="assistant",
                content=ai_response["content"],
                metadata={
                    "sources": sources,
                    "tokens": ai_response.get("tokens_used"),
                    "model": ai_response.get("model")
                }
            )
            
            processing_time = time.time() - start_time
            
            # ✅ Log chat for statistics (if method exists)
            if not request.is_incognito:
                db_manager.log_chat(
                    user_message=request.message,
                    assistant_response=ai_response["content"],
                    data_source=request.data_source
                )
            
            return ChatResponse(
                response=ai_response["content"],
                chat_id=request.chat_id,
                message_id=assistant_msg.id if assistant_msg else None,
                user_message_id=user_msg.id if user_msg else None,
                is_incognito=False,
                sources=sources,
                tokens_used=ai_response.get("tokens_used"),
                processing_time=processing_time,
                metadata={
                    "model": ai_response.get("model"),
                    "temperature": request.temperature
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ===========================
# Session Management
# ===========================

@router.get("/sessions", response_model=ChatListResponse)
async def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    include_archived: bool = Query(False),
    include_incognito: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Get user's chat sessions from database.
    Optionally include incognito sessions from memory.
    """
    try:
        # ✅ Get regular chats from database
        db_chats = db_manager.get_user_chat_sessions(
            user_id=current_user.id,
            include_archived=include_archived,
            limit=page_size,
            offset=(page - 1) * page_size
        )
        
        # Convert to response format
        chats = []
        for db_chat in db_chats:
            chats.append(db_chat.dict() if hasattr(db_chat, 'dict') else db_chat)
        
        # Add incognito chats from memory if requested
        if include_incognito:
            user_incognito_chats = [
                chat for chat in INCOGNITO_CHATS.values()
                if chat["user_id"] == current_user.id
            ]
            
            for inc_chat in user_incognito_chats:
                last_msg = inc_chat["messages"][-1]["content"] if inc_chat["messages"] else None
                chat_dict = {
                    "id": inc_chat["id"],
                    "user_id": inc_chat["user_id"],
                    "title": inc_chat["title"],
                    "is_archived": False,
                    "is_pinned": False,
                    "created_at": inc_chat["created_at"],
                    "updated_at": inc_chat["created_at"],
                    "is_incognito": True,
                    "message_count": len(inc_chat["messages"]),
                    "last_message": last_msg
                }
                chats.append(chat_dict)
        
        # Calculate total
        total = len(db_chats)
        if include_incognito:
            total += len([c for c in INCOGNITO_CHATS.values() if c["user_id"] == current_user.id])
        
        return ChatListResponse(
            chats=chats,
            total=total,
            page=page,
            page_size=page_size,
            has_more=total > page * page_size
        )
        
    except Exception as e:
        logger.error(f"Error fetching chat sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Get chat history with messages.
    Works for both regular (database) and incognito (memory) chats.
    """
    try:
        # Handle incognito chats (negative IDs)
        if chat_id < 0:
            if chat_id not in INCOGNITO_CHATS:
                raise HTTPException(status_code=404, detail="Incognito chat not found")
            
            inc_chat = INCOGNITO_CHATS[chat_id]
            if inc_chat["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Convert to response format
            chat = ChatSession(
                id=inc_chat["id"],
                user_id=inc_chat["user_id"],
                title=inc_chat["title"],
                is_archived=False,
                is_pinned=False,
                created_at=inc_chat["created_at"],
                updated_at=inc_chat["created_at"],
                is_incognito=True,
                message_count=len(inc_chat["messages"])
            )
            
            # Get messages with pagination
            messages = inc_chat["messages"][offset:offset + limit if limit else None]
            
            chat_messages = [
                ChatMessage(
                    id=msg["id"],
                    chat_id=chat_id,
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                    metadata=msg.get("metadata", {})
                )
                for msg in messages
            ]
            
            return ChatHistoryResponse(
                chat=chat,
                messages=chat_messages,
                total_messages=len(inc_chat["messages"]),
                has_more=len(inc_chat["messages"]) > (offset + len(messages))
            )
        
        # Handle regular database chats
        else:
            # ✅ Verify ownership
            sessions = db_manager.get_user_chat_sessions(
                user_id=current_user.id,
                limit=1000
            )
            
            chat_session = None
            for session in sessions:
                if session.id == chat_id:
                    chat_session = session
                    break
            
            if not chat_session:
                raise HTTPException(status_code=404, detail="Chat not found or access denied")
            
            # ✅ Get messages from database
            db_messages = db_manager.get_chat_messages(
                chat_id=chat_id,
                limit=limit or 100,
                offset=offset
            )
            
            # Convert to Pydantic models
            chat = ChatSession(
                id=chat_session.id,
                user_id=chat_session.user_id,
                title=chat_session.title or f"Chat {chat_session.id}",
                is_archived=chat_session.is_archived,
                is_pinned=chat_session.is_pinned,
                created_at=chat_session.created_at,
                updated_at=chat_session.updated_at,
                is_incognito=False,
                message_count=chat_session.message_count or len(db_messages)
            )
            
            messages = []
            for msg in db_messages:
                messages.append(ChatMessage(
                    id=msg.id,
                    chat_id=msg.chat_id,
                    role=msg.role,
                    content=msg.content,
                    created_at=msg.created_at,
                    metadata=msg.metadata or {}
                ))
            
            return ChatHistoryResponse(
                chat=chat,
                messages=messages,
                total_messages=chat_session.message_count or len(db_messages),
                has_more=len(db_messages) == (limit or 100)
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions", response_model=dict)
async def create_chat_session(
    request: ChatSessionCreate = None,
    current_user: User = Depends(get_current_user)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Create a new chat session.
    """
    try:
        if not request:
            request = ChatSessionCreate()
        
        # Handle incognito chat creation
        if request.is_incognito:
            chat_id = get_next_incognito_id()
            INCOGNITO_CHATS[chat_id] = {
                "id": chat_id,
                "user_id": current_user.id,
                "title": request.title or "Incognito Chat",
                "messages": [],
                "created_at": datetime.utcnow()
            }
            
            # Add first message if provided
            if request.first_message:
                INCOGNITO_CHATS[chat_id]["messages"].append({
                    "id": 1,
                    "role": "user",
                    "content": request.first_message,
                    "created_at": datetime.utcnow()
                })
            
            return {
                "chat_id": chat_id,
                "is_incognito": True,
                "title": INCOGNITO_CHATS[chat_id]["title"]
            }
        
        # ✅ Create regular database chat
        else:
            chat = db_manager.create_chat_session(
                user_id=current_user.id,
                title=request.title,
                is_incognito=False
            )
            
            if not chat:
                raise HTTPException(status_code=500, detail="Failed to create chat")
            
            # Add first message if provided
            if request.first_message:
                db_manager.add_message_to_chat(
                    chat_id=chat.id,
                    role="user",
                    content=request.first_message
                )
            
            return {
                "chat_id": chat.id,
                "is_incognito": False,
                "title": chat.title or f"Chat {chat.id}"
            }
        
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/sessions/{chat_id}")
async def update_chat_session(
    chat_id: int,
    request: UpdateChatRequest,
    current_user: User = Depends(get_current_user)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Update chat session properties.
    """
    try:
        # Prevent updating incognito chats
        if chat_id < 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot update incognito chat - it's temporary"
            )
        
        # ✅ Verify ownership
        sessions = db_manager.get_user_chat_sessions(
            user_id=current_user.id,
            limit=1000
        )
        
        if not any(s.id == chat_id for s in sessions):
            raise HTTPException(status_code=404, detail="Chat not found or access denied")
        
        # ✅ Update chat
        updated_chat = db_manager.update_chat_session(
            chat_id=chat_id,
            title=request.title,
            is_archived=request.is_archived,
            is_pinned=request.is_pinned
        )
        
        if not updated_chat:
            raise HTTPException(status_code=500, detail="Failed to update chat")
        
        return {"message": "Chat updated successfully", "chat_id": chat_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{chat_id}")
async def delete_chat_session(
    chat_id: int,
    current_user: User = Depends(get_current_user)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Delete chat session.
    """
    try:
        # Handle incognito chat deletion
        if chat_id < 0:
            if chat_id not in INCOGNITO_CHATS:
                raise HTTPException(status_code=404, detail="Incognito chat not found")
            
            if INCOGNITO_CHATS[chat_id]["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
            
            del INCOGNITO_CHATS[chat_id]
            return {"message": "Incognito chat cleared from memory"}
        
        # ✅ Handle regular database chat deletion
        else:
            sessions = db_manager.get_user_chat_sessions(
                user_id=current_user.id,
                limit=1000
            )
            
            if not any(s.id == chat_id for s in sessions):
                raise HTTPException(status_code=404, detail="Chat not found or access denied")
            
            # Delete from database
            success = db_manager.delete_chat_session(chat_id)
            
            if not success:
                raise HTTPException(status_code=500, detail="Failed to delete chat")
            
            return {"message": "Chat deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ===========================
# Search & Discovery
# ===========================

@router.get("/sessions/search")
async def search_chats(
    query: str = Query(..., min_length=1, max_length=200),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Search in user's chat history.
    """
    try:
        # ✅ Search in database chats
        db_results = db_manager.search_chats(
            user_id=current_user.id,
            query=query,
            include_archived=include_archived,
            limit=limit
        )
        
        return {"results": db_results, "total": len(db_results)}
        
    except Exception as e:
        logger.error(f"Error searching chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search_chats_advanced(
    request: SearchChatsRequest,
    current_user: User = Depends(get_current_user)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Advanced search in user's chats.
    """
    try:
        # ✅ Search in database
        results = db_manager.search_chats(
            user_id=current_user.id,
            query=request.query,
            include_archived=request.include_archived,
            limit=request.limit
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error searching chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ===========================
# Incognito Mode Management
# ===========================

@router.get("/mode/status", response_model=ChatModeStatus)
async def get_chat_mode_status(
    current_user: User = Depends(get_current_user)
    # ✅ Убрали db: Session = Depends(get_db)
):
    """
    Get current chat mode status and statistics.
    """
    try:
        # ✅ Get regular chats count from database
        sessions = db_manager.get_user_chat_sessions(
            user_id=current_user.id,
            include_archived=True,
            limit=1000
        )
        total_chats = len(sessions)
        
        # Get incognito chats from memory
        user_incognito_chats = [
            chat for chat in INCOGNITO_CHATS.values()
            if chat["user_id"] == current_user.id
        ]
        
        incognito_chat_ids = [chat["id"] for chat in user_incognito_chats]
        
        return ChatModeStatus(
            has_incognito_chats=len(user_incognito_chats) > 0,
            incognito_chat_count=len(user_incognito_chats),
            total_chats=total_chats,
            active_incognito_sessions=incognito_chat_ids
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
    """
    try:
        # Find and remove user's incognito chats from memory
        user_incognito_ids = [
            chat_id for chat_id, chat in INCOGNITO_CHATS.items()
            if chat["user_id"] == current_user.id
        ]
        
        for chat_id in user_incognito_ids:
            del INCOGNITO_CHATS[chat_id]
        
        return {
            "message": f"Cleared {len(user_incognito_ids)} incognito chat(s)",
            "cleared_count": len(user_incognito_ids)
        }
        
    except Exception as e:
        logger.error(f"Error clearing incognito chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))