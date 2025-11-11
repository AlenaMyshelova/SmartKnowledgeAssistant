from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from app.database import db_manager
from app.models.chat import ChatSession, ChatMessage, MessageCreate, ChatSessionCreate
from app.models.user import User
from app.data_manager import DataManager
from app.chat_utils import build_context_from_results

logger = logging.getLogger(__name__)

class ChatService:
    """
    Modern ChatService using SQLAlchemy ORM + structured chat management.
    Replaces legacy dictionary-based approach with typed models.
    """
    
    def __init__(self):
        self.db = db_manager
        self.data_manager = DataManager()
    
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
            
            # Create chat session
            chat = self.db.create_chat_session(user_id, title)
            
            # Update incognito status if needed
            if chat and is_incognito:
                chat = self.db.update_chat_session(chat.id, is_incognito=True)
            
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
            return self.db.get_user_chat_sessions(
                user_id, 
                include_archived=include_archived
            )
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
        
        This replaces the old process_chat_message method but works with chat sessions.
        
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
            from app.services.openai_service import openai_service
            ai_response = await openai_service.generate_response(
                query=user_message,
                context=context,
                scarcity_note=scarcity_note
            )
            
            if not ai_response:
                ai_response = "I'm sorry, I encountered an error processing your request."
            
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
        Get AI response with formatted sources (replaces old get_response method).
        
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
                    "response": "I'm sorry, I encountered an error processing your request.",
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
                "response": "I'm sorry, I encountered an error processing your request.",
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