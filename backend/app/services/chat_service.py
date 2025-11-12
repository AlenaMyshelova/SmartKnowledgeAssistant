from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from app.database import db_manager
from app.models.chat import ChatSession, ChatMessage, MessageCreate, ChatSessionCreate
from app.models.user import User
from app.data_manager import DataManager
from app.chat_utils import build_context_from_results
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

class ChatService:
    """
    ChatService using SQLAlchemy ORM + structured chat management.
    """
    def __init__(self):
        self.db = db_manager #connect to DB manager
        self.data_manager = DataManager() #Search in FAQ documents etc.
               # --- in-memory storage for incognito ---
        self._incognito_chats: Dict[int, Dict[str, Any]] = {}
        self._incognito_messages: Dict[int, List[Dict[str, Any]]] = {}
        self._incognito_id = -1

    def _new_incognito_id(self) -> int:
        cid = self._incognito_id
        self._incognito_id -= 1
        return cid

    @staticmethod
    def _is_incognito_chat_id(chat_id: int) -> bool:
        return chat_id < 0
    
    # ===========================================
    # CORE CHAT SESSION MANAGEMENT
    # ===========================================
    
    async def create_chat_session(
        self, 
        user_id: int, 
        title: Optional[str] = None,
        is_incognito: bool = False
    ) -> Optional[ChatSession]:
        """
        Create a new chat session.
        
        Args:
            user_id: ID of the user creating the chat
            title: Optional chat title
            is_incognito: Whether this is a private/incognito chat
            
        Returns:
            ChatSession object or None if creation failed
        """
        try:
            # Generate default title if none provided
            if not title:
                title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            if is_incognito:
               # True incognito: keep only in memory
                cid = self._new_incognito_id()
                now = datetime.utcnow()
                self._incognito_chats[cid] = {
                    "id": cid, "user_id": user_id, "title": title,
                    "created_at": now, "updated_at": now, "is_incognito": True
                }
                self._incognito_messages[cid] = []
                logger.info(f"Created incognito chat {cid} for user {user_id}")
                return ChatSession(
                    id=cid, user_id=user_id, title=title,
                    created_at=now, updated_at=now,
                    is_archived=False, is_pinned=False,
                    is_incognito=True, message_count=0, last_message=None
                )
            else:
                chat = self.db.create_chat_session(user_id, title, is_incognito=False)
                logger.info(f"Created chat session {chat.id} for user {user_id}")
                return chat
            
        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            return None
    
    async def get_user_chats(
        self, 
        user_id: int, 
        include_archived: bool = False,
        include_incognito: bool = True
    ) -> List[ChatSession]:
        """Get all chat sessions for a user."""
        try:
            chats = self.db.get_user_chat_sessions(
            user_id,
            include_archived=include_archived
            )
            if include_incognito:
                for cid, chat in self._incognito_chats.items():
                    if chat["user_id"] != user_id:
                        continue
                    msgs = self._incognito_messages.get(cid, [])
                    chats.append(ChatSession(
                        id=cid, user_id=user_id, title=chat["title"],
                        created_at=chat["created_at"], updated_at=chat["updated_at"],
                        is_archived=False, is_pinned=False, is_incognito=True,
                        message_count=len(msgs),
                        last_message=(msgs[-1]["content"][:100] if msgs else None)
                    ))
            return chats
        except Exception as e:
            logger.error(f"Error getting user chats: {e}")
            return []
    
    async def update_chat(
        self,
        chat_id: int,
        title: Optional[str] = None,
        is_archived: Optional[bool] = None,
        is_pinned: Optional[bool] = None,
        is_incognito: Optional[bool] = None
    ) -> Optional[ChatSession]:
        """Update chat session properties."""
        try:
            return self.db.update_chat_session(
                chat_id,
                title=title,
                is_archived=is_archived,
                is_pinned=is_pinned,
                is_incognito=is_incognito
            )
        except Exception as e:
            logger.error(f"Error updating chat {chat_id}: {e}")
            return None
    
    async def delete_chat(self, chat_id: int) -> bool:
        """Delete a chat session and all its messages."""
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
    
    # ===========================================
    # MESSAGE MANAGEMENT
    # ===========================================
    
    async def add_message(
        self,
        chat_id: int,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ChatMessage]:
        """Add a message to a chat session."""
        try:
            if self._is_incognito_chat_id(chat_id):
                if chat_id not in self._incognito_messages:
                    logger.error(f"Incognito chat {chat_id} not found")
                    return None
                mid = -len(self._incognito_messages[chat_id]) - 1
                created = datetime.utcnow()
                self._incognito_messages[chat_id].append({
                    "id": mid, "chat_id": chat_id, "role": role,
                    "content": content, "metadata": metadata or {},
                    "created_at": created
                })
                if chat_id in self._incognito_chats:
                    self._incognito_chats[chat_id]["updated_at"] = created
                return ChatMessage(
                    id=mid, chat_id=chat_id, role=role,
                    content=content, metadata=metadata or {}, created_at=created
                )
            else:
                return self.db.add_message_to_chat(chat_id, role, content, metadata)
        except Exception as e:
            logger.error(f"Error adding message to chat {chat_id}: {e}")
            return None
        
    async def get_chat_messages(
        self, 
        chat_id: int, 
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get messages from a chat session."""
        try:
            if self._is_incognito_chat_id(chat_id):
                msgs = self._incognito_messages.get(chat_id, [])
                if limit:
                    msgs = msgs[-limit:]
                return [ChatMessage(
                    id=m["id"], chat_id=m["chat_id"], role=m["role"],
                    content=m["content"], metadata=m.get("metadata") or {},
                    created_at=m["created_at"]
                ) for m in msgs]
            else:
                return self.db.get_chat_messages(chat_id, limit)
        except Exception as e:
            logger.error(f"Error getting messages for chat {chat_id}: {e}")
            return []
    
    # ===========================================
    # AI CONVERSATION PROCESSING
    # ===========================================
    
    async def process_user_message(
        self,
        chat_id: int,
        user_message: str,
        data_source: str = "company_faqs",
        context_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ChatMessage]:
        """
        Process a user message: save it, search for context, generate AI response.
        
        Args:
            chat_id: ID of the chat session
            user_message: The user's message
            data_source: Source to search for relevant data
            context_metadata: Additional metadata for the conversation
            
        Returns:
            The AI assistant's response message
        """
        try:
            # Step 1: Save user message
            user_msg_metadata = {
                "data_source": data_source,
                "timestamp": datetime.utcnow().isoformat(),
                **(context_metadata or {})
            }
            
            user_msg = await self.add_message(
                chat_id=chat_id,
                role="user",
                content=user_message,
                metadata=user_msg_metadata
            )
            
            if not user_msg:
                logger.error(f"Failed to save user message for chat {chat_id}")
                return None
            
            # Step 2: Search for relevant data
            relevant_data = self._search_relevant_data(user_message, data_source)
            
            # Step 3: Build context for AI
            context, scarcity_note = self._build_context(relevant_data)
            
            # Step 4: Generate AI response
          
            ai_response = await openai_service.generate_response(
                query=user_message,
                context=context,
                scarcity_note=scarcity_note
            )
            
            if not ai_response:
                ai_response = "Error occurred while generating response."
            
            # Step 5: Save AI response with metadata
            ai_msg_metadata = {
                "data_source": data_source,
                "context_sources": len(relevant_data),
                "has_context": bool(relevant_data),
                "scarcity_note": bool(scarcity_note),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            ai_msg = await self.add_message(
                chat_id=chat_id,
                role="assistant", 
                content=ai_response,
                metadata=ai_msg_metadata
            )
            
            logger.info(f"Processed message for chat {chat_id}: {len(user_message)} chars in, {len(ai_response)} chars out")
            return ai_msg
            
        except Exception as e:
            logger.error(f"Error processing user message for chat {chat_id}: {e}")
            return None
    
    async def get_response_with_sources(
        self, 
        chat_id: int,
        user_message: str, 
        data_source: str = "company_faqs"
    ) -> Dict[str, Any]:
        """
        Get AI response with formatted sources.
        
        Returns both the AI message and formatted source information.
        """
        try:
            # Process the message and get AI response
            ai_message = await self.process_user_message(
                chat_id=chat_id,
                user_message=user_message,
                data_source=data_source
            )
            
            if not ai_message:
                return {
                    "response": "Error occurred while processing your request.",
                    "sources": [],
                    "message_id": None
                }
            
            # Get relevant data for sources display
            relevant_data = self._search_relevant_data(user_message, data_source)
            
            # Format sources for display
            sources = [
                {
                    "title": data.get("title", f"Source {i+1}"),
                    "content": data.get("content", "")[:200] + ("..." if len(data.get("content", "")) > 200 else ""),
                    "metadata": data.get("metadata", {})
                }
                for i, data in enumerate(relevant_data)
            ]
            
            return {
                "response": ai_message.content,
                "sources": sources,
                "message_id": ai_message.id,
                "chat_id": chat_id
            }
            
        except Exception as e:
            logger.error(f"Error getting response with sources: {e}")
            return {
                "response": "Error occurred while processing your request.",
                "sources": [],
                "message_id": None
            }
    
    # ===========================================
    # CONVERSATION CONTEXT & DATA SEARCH
    # ===========================================
    
    def _search_relevant_data(self, message: str, data_source: str) -> List[Dict[str, Any]]:
        """Search for relevant data in the knowledge base."""
        logger.info(f"Searching in {data_source} for query: {message[:50]}...")
        
        try:
            if data_source == "company_faqs":
                return self.data_manager.search_faqs(message)
            # Add other data sources here as needed
            return []
        except Exception as e:
            logger.error(f"Error searching {data_source}: {e}")
            return []
    
    def _build_context(self, relevant_data: List[Dict[str, Any]]) -> tuple[str, str]:
        """Build AI context from search results."""
        try:
            return build_context_from_results(relevant_data)
        except Exception as e:
            logger.error(f"Error building context: {e}")
            return "", ""
    
    async def get_chat_context(self, chat_id: int, max_messages: int = 10) -> str:
        """
        Get conversation context from recent messages.
        Useful for maintaining conversation continuity.
        """
        try:
            messages = await self.get_chat_messages(chat_id, limit=max_messages)
            
            context_parts = []
            for msg in messages[-max_messages:]:  # Get recent messages
                role_prefix = "User" if msg.role == "user" else "Assistant"
                context_parts.append(f"{role_prefix}: {msg.content}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error building chat context: {e}")
            return ""
    
    # ===========================================
    # ANALYTICS & REPORTING
    # ===========================================
    
    async def get_chat_statistics(self, chat_id: int) -> Dict[str, Any]:
        """Get statistics for a specific chat."""
        try:
            messages = await self.get_chat_messages(chat_id)
            
            user_messages = [msg for msg in messages if msg.role == "user"]
            assistant_messages = [msg for msg in messages if msg.role == "assistant"]
            
            return {
                "total_messages": len(messages),
                "user_messages": len(user_messages),
                "assistant_messages": len(assistant_messages),
                "first_message_date": messages[0].created_at if messages else None,
                "last_message_date": messages[-1].created_at if messages else None,
                "average_user_message_length": sum(len(msg.content) for msg in user_messages) / len(user_messages) if user_messages else 0,
                "average_assistant_message_length": sum(len(msg.content) for msg in assistant_messages) / len(assistant_messages) if assistant_messages else 0
            }
        except Exception as e:
            logger.error(f"Error getting chat statistics: {e}")
            return {}
    
    async def get_user_chat_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get overall statistics for a user's chats."""
        try:
            chats = await self.get_user_chats(user_id, include_archived=True)
            
            total_messages = 0
            archived_count = 0
            pinned_count = 0
            incognito_count = 0
            
            for chat in chats:
                messages = await self.get_chat_messages(chat.id)
                total_messages += len(messages)
                
                if chat.is_archived:
                    archived_count += 1
                if chat.is_pinned:
                    pinned_count += 1
                if getattr(chat, 'is_incognito', False):
                    incognito_count += 1
            
            return {
                "total_chats": len(chats),
                "total_messages": total_messages,
                "archived_chats": archived_count,
                "pinned_chats": pinned_count,
                "incognito_chats": incognito_count,
                "average_messages_per_chat": total_messages / len(chats) if chats else 0
            }
        except Exception as e:
            logger.error(f"Error getting user chat statistics: {e}")
            return {}

# Create service instance
chat_service = ChatService()