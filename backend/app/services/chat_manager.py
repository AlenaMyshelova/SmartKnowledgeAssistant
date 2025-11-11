"""
Chat management service using SQLAlchemy ORM.
Supports incognito mode through in-memory storage.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.database import db_manager
from app.models.chat import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


class ChatManager:
    def __init__(self):
        # In-memory storage for incognito chats
        self.incognito_chats: Dict[int, Dict] = {}
        self.incognito_messages: Dict[int, List[Dict]] = {}
        self._incognito_counter = -1

    def create_chat(
        self,
        user_id: int,
        title: Optional[str] = None,
        first_message: Optional[str] = None,
        is_incognito: bool = False,
        tags: Optional[List[str]] = None
    ) -> int:
        """Create new chat session."""
        if is_incognito:
            # Incognito chat in memory
            chat_id = self._get_next_incognito_id()
            self.incognito_chats[chat_id] = {
                "id": chat_id,
                "user_id": user_id,
                "title": title or "Incognito Chat",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_incognito": True,
                "tags": tags or []
            }
            self.incognito_messages[chat_id] = []
            
            if first_message:
                self.add_message(chat_id, "user", first_message)
            
            return chat_id
        else:
            # Regular chat in database
            chat = db_manager.create_chat_session(user_id, title, is_incognito=False)
            if chat and first_message:
                db_manager.add_message_to_chat(chat.id, "user", first_message)
            
            return chat.id if chat else None

    def add_message(
        self, 
        chat_id: int, 
        role: str, 
        content: str,
        metadata: Optional[Dict] = None
    ) -> Optional[int]:
        """Add message to chat."""
        if chat_id < 0:
            # Incognito message
            if chat_id in self.incognito_messages:
                msg_id = -len(self.incognito_messages[chat_id]) - 1
                self.incognito_messages[chat_id].append({
                    "id": msg_id,
                    "role": role,
                    "content": content,
                    "metadata": metadata,
                    "created_at": datetime.utcnow()
                })
                
                # Update chat timestamp
                if chat_id in self.incognito_chats:
                    self.incognito_chats[chat_id]["updated_at"] = datetime.utcnow()
                
                return msg_id
            return None
        else:
            # Regular message
            msg = db_manager.add_message_to_chat(chat_id, role, content, metadata)
            return msg.id if msg else None

    def get_user_chats(
        self, 
        user_id: int,
        include_archived: bool = False,
        include_incognito: bool = True,
        include_pinned_only: bool = False,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updated_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get user's chat sessions."""
        offset = (page - 1) * page_size
        
        # Get database chats
        db_chats = db_manager.get_user_chat_sessions(
            user_id, 
            include_archived=include_archived,
            limit=page_size,
            offset=offset
        )
        
        chats = []
        for chat in db_chats:
            if include_pinned_only and not chat.is_pinned:
                continue
            chats.append(chat.dict())
        
        # Add incognito chats if requested
        if include_incognito:
            for chat_id, chat_data in self.incognito_chats.items():
                if chat_data["user_id"] == user_id:
                    chats.append(chat_data)
        
        # Sort
        reverse = sort_order == "desc"
        chats.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)
        
        return {
            "chats": chats[:page_size],
            "total": len(chats),
            "page": page,
            "page_size": page_size,
            "has_more": len(chats) > page_size
        }

    def get_chat_history(
        self,
        chat_id: int,
        user_id: int,
        limit: Optional[int] = None,
        offset: int = 0,
        order: str = "asc"
    ) -> Dict[str, Any]:
        """Get chat history with messages."""
        if chat_id < 0:
            # Incognito chat
            if chat_id not in self.incognito_chats:
                raise ValueError(f"Incognito chat {chat_id} not found")
            
            chat = self.incognito_chats[chat_id]
            if chat["user_id"] != user_id:
                raise ValueError("Access denied")
            
            messages = self.incognito_messages.get(chat_id, [])
            if order == "desc":
                messages = list(reversed(messages))
            
            if limit:
                messages = messages[offset:offset + limit]
            
            return {
                "chat": chat,
                "messages": messages,
                "total_messages": len(self.incognito_messages.get(chat_id, []))
            }
        else:
            # Database chat
            chat_sessions = db_manager.get_user_chat_sessions(user_id, limit=1, offset=0)
            chat = None
            for session in chat_sessions:
                if session.id == chat_id:
                    chat = session
                    break
            
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")
            
            messages = db_manager.get_chat_messages(chat_id, limit or 100, offset)
            
            if order == "desc":
                messages = list(reversed(messages))
            
            return {
                "chat": chat.dict(),
                "messages": [msg.dict() for msg in messages],
                "total_messages": chat.message_count
            }

    def update_chat(
        self,
        chat_id: int,
        user_id: int,
        title: Optional[str] = None,
        is_archived: Optional[bool] = None,
        is_pinned: Optional[bool] = None
    ) -> bool:
        """Update chat session."""
        if chat_id < 0:
            # Can't update incognito chats
            return False
        
        chat = db_manager.update_chat_session(
            chat_id,
            title=title,
            is_archived=is_archived,
            is_pinned=is_pinned
        )
        return chat is not None

    def delete_chat(
        self,
        chat_id: int,
        user_id: int,
        permanent: bool = False
    ) -> bool:
        """Delete chat session."""
        if chat_id < 0:
            # Delete incognito chat from memory
            if chat_id in self.incognito_chats:
                if self.incognito_chats[chat_id]["user_id"] == user_id:
                    del self.incognito_chats[chat_id]
                    del self.incognito_messages[chat_id]
                    return True
            return False
        else:
            if permanent:
                return db_manager.delete_chat_session(chat_id)
            else:
                # Soft delete (archive)
                chat = db_manager.update_chat_session(chat_id, is_archived=True)
                return chat is not None

    def search_chats(
        self,
        user_id: int,
        query: str,
        include_archived: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search user's chats."""
        return db_manager.search_chats(
            user_id,
            query,
            include_archived=include_archived,
            limit=limit
        )

    def verify_chat_owner(self, chat_id: int, user_id: int) -> bool:
        """Verify if user owns the chat."""
        if chat_id < 0:
            # Check incognito
            return (
                chat_id in self.incognito_chats and 
                self.incognito_chats[chat_id]["user_id"] == user_id
            )
        else:
            # Check database
            sessions = db_manager.get_user_chat_sessions(user_id)
            return any(s.id == chat_id for s in sessions)

    def clear_incognito_chats(self, user_id: int) -> int:
        """Clear all incognito chats for user."""
        cleared = 0
        to_delete = []
        
        for chat_id, chat in self.incognito_chats.items():
            if chat["user_id"] == user_id:
                to_delete.append(chat_id)
        
        for chat_id in to_delete:
            del self.incognito_chats[chat_id]
            del self.incognito_messages[chat_id]
            cleared += 1
        
        return cleared

    def get_chat_mode_status(self, user_id: int) -> Dict[str, Any]:
        """Get chat mode status for user."""
        # Count incognito chats
        incognito_count = sum(
            1 for chat in self.incognito_chats.values()
            if chat["user_id"] == user_id
        )
        
        # Count saved chats
        saved_chats = len(db_manager.get_user_chat_sessions(user_id, limit=100))
        
        # Count total messages
        total_messages = 0
        for chat in db_manager.get_user_chat_sessions(user_id, limit=100):
            total_messages += chat.message_count or 0
        
        return {
            "mode": "normal",
            "active_incognito_chats": incognito_count,
            "saved_chats": saved_chats,
            "total_messages": total_messages
        }

    def _get_next_incognito_id(self) -> int:
        """Get next incognito chat ID (negative)."""
        current = self._incognito_counter
        self._incognito_counter -= 1
        return current


# Global instance
chat_manager = ChatManager()