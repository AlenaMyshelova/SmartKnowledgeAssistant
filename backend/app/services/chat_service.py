from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from app.models.chat import ChatSession, ChatMessage
from app.data_manager import DataManager
from app.chat_utils import build_context_from_results
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


class ChatService:
    """
    ChatService using SQLAlchemy ORM + structured chat management.
    - Persisted chats → через DatabaseManager
    - Incognito → in-memory (отрицательные chat_id)
    """

    def __init__(self):
        self.db = db_manager
        self.data_manager = DataManager()

        # --- in-memory storage for incognito ---
        self._incognito_chats: Dict[int, Dict[str, Any]] = {}
        self._incognito_messages: Dict[int, List[Dict[str, Any]]] = {}
        self._incognito_id = -1

    # ========== helpers (incognito id / checks) ==========
    def _new_incognito_id(self) -> int:
        cid = self._incognito_id
        self._incognito_id -= 1
        return cid

    @staticmethod
    def _is_incognito_chat_id(chat_id: int) -> bool:
        return chat_id < 0

    # ========== core chat management ==========
    async def create_chat_session(
        self,
        user_id: int,
        title: Optional[str] = None,
        is_incognito: bool = False,
    ) -> Optional[ChatSession]:
        try:
            if not title:
                title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            if is_incognito:
                # for incognito chats, create in-memory
                cid = self._new_incognito_id()
                now = datetime.utcnow()
                self._incognito_chats[cid] = {
                    "id": cid,
                    "user_id": user_id,
                    "title": title,
                    "created_at": now,
                    "updated_at": now,
                    "is_incognito": True,
                }
                self._incognito_messages[cid] = []
                logger.info(f"Created incognito chat {cid} for user {user_id}")
                return ChatSession(
                    id=cid,
                    user_id=user_id,
                    title=title,
                    created_at=now,
                    updated_at=now,
                    is_archived=False,
                    is_pinned=False,
                    is_incognito=True,
                    message_count=0,
                    last_message=None,
                )
            else:
                chat = self.db.create_chat_session(user_id, title, is_incognito=False)
                if chat:
                    logger.info(f"Created chat session {chat.id} for user {user_id}")
                return chat

        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            return None

    async def get_user_chats(
        self,
        user_id: int,
        include_archived: bool = False,
        include_incognito: bool = True,
    ) -> List[ChatSession]:
        try:
            chats = self.db.get_user_chat_sessions(
                user_id,
                include_archived=include_archived,
            )
            if include_incognito:
                for cid, chat in self._incognito_chats.items():
                    if chat["user_id"] != user_id:
                        continue
                    msgs = self._incognito_messages.get(cid, [])
                    chats.append(
                        ChatSession(
                            id=cid,
                            user_id=user_id,
                            title=chat["title"],
                            created_at=chat["created_at"],
                            updated_at=chat["updated_at"],
                            is_archived=False,
                            is_pinned=False,
                            is_incognito=True,
                            message_count=len(msgs),
                            last_message=(msgs[-1]["content"][:100] if msgs else None),
                        )
                    )
            return chats
        except Exception as e:
            logger.error(f"Error getting user chats: {e}")
            return []
    async def search_user_chats(
            self,
            user_id: int,
            query: str,
            include_archived: bool = False,
            limit: int = 50
        ) -> List[Dict[str, Any]]:
            """Search in user's persisted chats (title + content)."""
            try:
                return self.db.search_chats(
                    user_id=user_id,
                    query=query,
                    include_archived=include_archived,
                    limit=limit
                )
            except Exception as e:
                logger.error(f"Error searching chats: {e}")
                return []    

    async def update_chat(
        self,
        chat_id: int,
        title: Optional[str] = None,
        is_archived: Optional[bool] = None,
        is_pinned: Optional[bool] = None,
        is_incognito: Optional[bool] = None,
    ) -> Optional[ChatSession]:
        """Incognito can not be updated."""
        try:
            if self._is_incognito_chat_id(chat_id):
                logger.warning("Attempt to update incognito chat ignored")
                return None
            return self.db.update_chat_session(
                chat_id,
                title=title,
                is_archived=is_archived,
                is_pinned=is_pinned,
                is_incognito=is_incognito,
            )
        except Exception as e:
            logger.error(f"Error updating chat {chat_id}: {e}")
            return None

    async def delete_chat(self, chat_id: int) -> bool:
        try:
            if self._is_incognito_chat_id(chat_id):
                self._incognito_chats.pop(chat_id, None)
                self._incognito_messages.pop(chat_id, None)
                logger.info(f"Deleted incognito chat {chat_id}")
                return True
            success = self.db.delete_chat_session(chat_id)
            if success:
                logger.info(f"Deleted chat session {chat_id}")
            return success
        except Exception as e:
            logger.error(f"Error deleting chat {chat_id}: {e}")
            return False

    def clear_incognito_chats(self, user_id: int) -> int:
        """Clear all incognito chats for a user."""
        to_delete = [cid for cid, ch in self._incognito_chats.items() if ch["user_id"] == user_id]
        for cid in to_delete:
            self._incognito_chats.pop(cid, None)
            self._incognito_messages.pop(cid, None)

        logger.info(f"Cleared {len(to_delete)} incognito chats for user {user_id}")    
        return len(to_delete)

    async def switch_user_mode(self, user_id: int, to_incognito: bool) -> Dict[str, Any]:
        """Switch user mode between incognito and normal."""
        if not to_incognito:
            cleared = self.clear_incognito_chats(user_id)
            logger.info(f"[mode-switch] cleared {cleared} incognito chats for user {user_id}")
            return {"mode": "normal", "cleared": cleared}
        return {"mode": "incognito", "cleared": 0}

    async def verify_chat_owner(self, chat_id: int, user_id: int) -> bool:
        """Verify user owns the chat."""
        if self._is_incognito_chat_id(chat_id):
            ch = self._incognito_chats.get(chat_id)
            return bool(ch and ch["user_id"] == user_id)
         
        return self.db.chat_belongs_to_user(chat_id, user_id)

    async def get_chat_session(
        self, 
        chat_id: int, 
        user_id: Optional[int] = None
    ) -> Optional[ChatSession]:
        """Get chat session by ID (optimized)."""
        try:
                # Incognito
                if self._is_incognito_chat_id(chat_id):
                    ch = self._incognito_chats.get(chat_id)
                    if not ch:
                        return None
                    
                    if user_id is not None and ch["user_id"] != user_id:
                        return None
                    
                    msgs = self._incognito_messages.get(chat_id, [])
                    return ChatSession(
                        id=chat_id,
                        user_id=ch["user_id"],
                        title=ch["title"],
                        created_at=ch["created_at"],
                        updated_at=ch["updated_at"],
                        is_archived=False,
                        is_pinned=False,
                        is_incognito=True,
                        message_count=len(msgs),
                        last_message=(msgs[-1]["content"][:100] if msgs else None),
                    )
                # Persisted
                return self.db.get_chat_session_by_id(chat_id, user_id)
                
        except Exception as e:
                logger.error(f"Error getting chat session {chat_id}: {e}")
                return None

    # ========== messages ==========
    async def add_message(
        self,
        chat_id: int,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ChatMessage]:
        try:
            if self._is_incognito_chat_id(chat_id):
                if chat_id not in self._incognito_messages:
                    logger.error(f"Incognito chat {chat_id} not found")
                    return None
                mid = -len(self._incognito_messages[chat_id]) - 1
                created = datetime.utcnow()
                self._incognito_messages[chat_id].append(
                    {
                        "id": mid,
                        "chat_id": chat_id,
                        "role": role,
                        "content": content,
                        "metadata": metadata or {},
                        "created_at": created,
                    }
                )
                if chat_id in self._incognito_chats:
                    self._incognito_chats[chat_id]["updated_at"] = created
                return ChatMessage(
                    id=mid,
                    chat_id=chat_id,
                    role=role,
                    content=content,
                    metadata=metadata or {},
                    created_at=created,
                )
            else:
                return self.db.add_message_to_chat(chat_id, role, content, metadata)
        except Exception as e:
            logger.error(f"Error adding message to chat {chat_id}: {e}")
            return None

    async def get_chat_messages(
        self,
        chat_id: int,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[ChatMessage]:
        try:
            if self._is_incognito_chat_id(chat_id):
                msgs = self._incognito_messages.get(chat_id, [])
                if offset:
                    msgs = msgs[offset:]
                if limit:
                    msgs = msgs[:limit]
                return [
                    ChatMessage(
                        id=m["id"],
                        chat_id=m["chat_id"],
                        role=m["role"],
                        content=m["content"],
                        metadata=m.get("metadata") or {},
                        created_at=m["created_at"],
                    )
                    for m in msgs
                ]
            else:
                return self.db.get_chat_messages(chat_id, limit or 100, offset)
        except Exception as e:
            logger.error(f"Error getting messages for chat {chat_id}: {e}")
            return []

    # ========== AI pipeline ==========
    async def process_user_message(
        self,
        chat_id: int,
        user_message: str,
        data_source: str = "company_faqs",
        context_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ChatMessage]:
        try:
            # user message
            user_msg_metadata = {
                "data_source": data_source,
                "timestamp": datetime.utcnow().isoformat(),
                **(context_metadata or {}),
            }
            user_msg = await self.add_message(
                chat_id=chat_id, role="user", content=user_message, metadata=user_msg_metadata
            )
            if not user_msg:
                logger.error(f"Failed to save user message for chat {chat_id}")
                return None

            # search
            relevant_data = self._search_relevant_data(user_message, data_source)
            context, scarcity_note = self._build_context(relevant_data)

            # LLM
            ai_response = await openai_service.generate_response(
                query=user_message, 
                context=context, 
                scarcity_note=scarcity_note
            )
            if not ai_response:
                ai_response = "Error occurred while generating response."

            # assistant message
            ai_msg_metadata = {
                "data_source": data_source,
                "context_sources": len(relevant_data),
                "has_context": bool(relevant_data),
                "scarcity_note": bool(scarcity_note),
                "timestamp": datetime.utcnow().isoformat(),
            }
            ai_msg = await self.add_message(
                chat_id=chat_id, role="assistant", content=ai_response, metadata=ai_msg_metadata
            )
            return ai_msg

        except Exception as e:
            logger.error(f"Error processing user message for chat {chat_id}: {e}")
            return None

    async def get_response_with_sources(
        self,
        chat_id: int,
        user_message: str,
        data_source: str = "company_faqs",
    ) -> Dict[str, Any]:
        try:
            ai_message = await self.process_user_message(
                chat_id=chat_id, user_message=user_message, data_source=data_source
            )
            if not ai_message:
                return {"response": "Error occurred while processing your request.", 
                        "sources": [], 
                        "message_id": None,
                        "chat_id": chat_id
                        }

            relevant_data = self._search_relevant_data(user_message, data_source)
            sources = [
                {
                    "title": data.get("title", f"Source {i+1}"),
                    "content": data.get("content", "")[:200]
                    + ("..." if len(data.get("content", "")) > 200 else ""),
                    "metadata": data.get("metadata", {}),
                }
                for i, data in enumerate(relevant_data)
            ]

            return {
                "response": ai_message.content,
                "sources": sources,
                "message_id": ai_message.id,
                "chat_id": chat_id,
            }
        except Exception as e:
            logger.error(f"Error getting response with sources: {e}")
            return {"response": "Error occurred while processing your request.", 
                    "sources": [], 
                    "message_id": None,
                    "chat_id": chat_id
            }

    # ========== context & search utils ==========
    def _search_relevant_data(self, message: str, data_source: str) -> List[Dict[str, Any]]:
        logger.info(f"Searching in {data_source} for query: {message[:50]}...")
        try:
            if data_source == "company_faqs":
                return self.data_manager.search_faqs(message)
            return []
        except Exception as e:
            logger.error(f"Error searching {data_source}: {e}")
            return []

    def _build_context(self, relevant_data: List[Dict[str, Any]]) -> tuple[str, str]:
        try:
            return build_context_from_results(relevant_data)
        except Exception as e:
            logger.error(f"Error building context: {e}")
            return "", ""

    async def get_chat_context(self, chat_id: int, max_messages: int = 10) -> str:
        try:
            messages = await self.get_chat_messages(chat_id, limit=max_messages)
            parts = []
            for msg in messages[-max_messages:]:
                role_prefix = "User" if msg.role == "user" else "Assistant"
                parts.append(f"{role_prefix}: {msg.content}")
            return "\n".join(parts)
        except Exception as e:
            logger.error(f"Error building chat context: {e}")
            return ""

    # ========== analytics ==========
    async def get_chat_statistics(self, chat_id: int) -> Dict[str, Any]:
        try:
            messages = await self.get_chat_messages(chat_id)
            user_messages = [m for m in messages if m.role == "user"]
            assistant_messages = [m for m in messages if m.role == "assistant"]
            return {
                "total_messages": len(messages),
                "user_messages": len(user_messages),
                "assistant_messages": len(assistant_messages),
                "first_message_date": messages[0].created_at if messages else None,
                "last_message_date": messages[-1].created_at if messages else None,
                "average_user_message_length": (sum(len(m.content) for m in user_messages) / len(user_messages)) if user_messages else 0,
                "average_assistant_message_length": (sum(len(m.content) for m in assistant_messages) / len(assistant_messages)) if assistant_messages else 0,
            }
        except Exception as e:
            logger.error(f"Error getting chat statistics: {e}")
            return {}

    async def get_user_chat_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get aggregated statistics for all user's chats."""
        try:
            stats = self.db.get_user_statistics(user_id)
            # Add incognito count
            incognito = sum(
                1 for ch in self._incognito_chats.values()
                if ch["user_id"] == user_id
            )
            stats["incognito_chats"] = incognito
            
            return stats
            
        except Exception as e:
            logger.error(f" Error getting user chat statistics: {e}")
            return {}


# Singleton
chat_service = ChatService()