from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

# SQLAlchemy imports
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Import models
from app.models.database_models import (
    Base, 
    User as SQLUser, 
    ChatSession as SQLChatSession, 
    ChatMessage as SQLChatMessage, 
    ChatLog as SQLChatLog
)
from app.models.user import UserCreate, User as PydanticUser, UserUpdate, sqlalchemy_to_pydantic
from app.models.chat import (
    ChatSession as PydanticChatSession, 
    ChatMessage as PydanticMessage,
    ChatSessionCreate,
    MessageCreate
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    DatabaseManager with SQLAlchemy and Alembic support.
    All operations use SQLAlchemy ORM.
    """

    def __init__(self, db_path: str = "./data/assistant.db") -> None:
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parent.parent  # app/ -> backend/
        
        self.db_path: Path = (backend_dir / db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # SQLAlchemy setup
        self.db_url = f"sqlite:///{self.db_path}"
        logger.info(f"Database path: {self.db_path}")

        self.engine = create_engine(
            self.db_url,
            echo=False,
            connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Apply migrations
        self._check_and_apply_migrations()

    @contextmanager
    def get_session(self) -> Session:
        """Get SQLAlchemy session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _check_and_apply_migrations(self) -> None:
        """Check and apply Alembic migrations."""
        try:
            from app.database.migration_manager import initialize_migration_manager, get_migration_manager
            
            if get_migration_manager() is None:
                initialize_migration_manager(self.db_url)
            
            migration_manager = get_migration_manager()
            if migration_manager and not migration_manager.is_database_up_to_date():
                logger.info("Applying pending migrations...")
                migration_manager.upgrade_database()
                logger.info("Migrations applied successfully")
                
        except ImportError:
            logger.warning("Migration manager not available, creating tables directly...")
            # Fallback: create tables using SQLAlchemy
            Base.metadata.create_all(bind=self.engine)
        except Exception as e:
            logger.error(f"Migration check failed: {e}")

    # ---------------------------
    # User Management
    # ---------------------------
    
    def create_user(self, user_data: UserCreate) -> Optional[PydanticUser]:
        """Create a new user."""
        try:
            with self.get_session() as session:
                # Check existing
                existing_user = session.query(SQLUser).filter_by(
                    oauth_provider=user_data.oauth_provider,
                    oauth_id=user_data.oauth_id
                ).first()
                
                if existing_user:
                    return self._sqlalchemy_user_to_pydantic(existing_user)
                
                # Create new
                db_user = SQLUser(
                    email=user_data.email,
                    name=user_data.name,
                    avatar_url=user_data.avatar_url,
                    oauth_provider=user_data.oauth_provider,
                    oauth_id=user_data.oauth_id,
                    provider_data=json.dumps(user_data.provider_data) if user_data.provider_data else None,
                    is_active=user_data.is_active
                )
                
                session.add(db_user)
                session.flush()
                session.refresh(db_user)
                
                logger.info(f"Created user: {user_data.email}")
                return self._sqlalchemy_user_to_pydantic(db_user)
                
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def get_user_by_id(self, user_id: int) -> Optional[PydanticUser]:
        """Get user by ID."""
        try:
            with self.get_session() as session:
                db_user = session.query(SQLUser).filter_by(
                    id=user_id, 
                    is_active=True
                ).first()
                
                return self._sqlalchemy_user_to_pydantic(db_user) if db_user else None
                
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    def get_user_by_oauth_id(self, provider: str, oauth_id: str) -> Optional[PydanticUser]:
        """Get user by OAuth credentials."""
        try:
            with self.get_session() as session:
                db_user = session.query(SQLUser).filter_by(
                    oauth_provider=provider,
                    oauth_id=oauth_id,
                    is_active=True
                ).first()
                
                return self._sqlalchemy_user_to_pydantic(db_user) if db_user else None
                
        except Exception as e:
            logger.error(f"Error getting user {provider}:{oauth_id}: {e}")
            return None

    def update_last_login(self, user_id: int) -> bool:
        """Update last login timestamp."""
        try:
            with self.get_session() as session:
                session.query(SQLUser).filter_by(id=user_id).update(
                    {"last_login": datetime.utcnow()}
                )
                return True
                
        except Exception as e:
            logger.error(f"Error updating last login: {e}")
            return False

    # ---------------------------
    # Chat Management
    # ---------------------------
    
    def create_chat_session(
        self, 
        user_id: int, 
        title: Optional[str] = None,
        is_incognito: bool = False
    ) -> Optional[PydanticChatSession]:
        """Create new chat session."""
        try:
            with self.get_session() as session:
                db_session = SQLChatSession(
                    user_id=user_id,
                    title=title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    is_incognito=is_incognito
                )
                
                session.add(db_session)
                session.flush()
                session.refresh(db_session)
                
                logger.info(f"Created chat session {db_session.id}")
                return self._sqlalchemy_session_to_pydantic(db_session)
                
        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            return None

    def update_chat_session(
        self,
        chat_id: int,
        title: Optional[str] = None,
        is_archived: Optional[bool] = None,
        is_pinned: Optional[bool] = None
    ) -> Optional[PydanticChatSession]:
        """Update chat session."""
        try:
            with self.get_session() as session:
                chat = session.query(SQLChatSession).filter_by(id=chat_id).first()
                if not chat:
                    return None
                
                if title is not None:
                    chat.title = title
                if is_archived is not None:
                    chat.is_archived = is_archived
                if is_pinned is not None:
                    chat.is_pinned = is_pinned
                    
                chat.updated_at = datetime.utcnow()
                session.flush()
                session.refresh(chat)
                
                return self._sqlalchemy_session_to_pydantic(chat)
                
        except Exception as e:
            logger.error(f"Error updating chat {chat_id}: {e}")
            return None

    def delete_chat_session(self, chat_id: int) -> bool:
        """Delete chat session and all messages."""
        try:
            with self.get_session() as session:
                chat = session.query(SQLChatSession).filter_by(id=chat_id).first()
                if chat:
                    session.delete(chat)  # CASCADE will delete messages
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error deleting chat {chat_id}: {e}")
            return False

    def add_message_to_chat(
        self, 
        chat_id: int, 
        role: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[PydanticMessage]:
        """Add message to chat."""
        try:
            with self.get_session() as session:
                db_message = SQLChatMessage(
                    chat_id=chat_id,
                    role=role,
                    content=content,
                    message_metadata=json.dumps(metadata) if metadata else None
                )
                
                session.add(db_message)
                session.flush()
                session.refresh(db_message)
                
                # Update chat's updated_at
                session.query(SQLChatSession).filter_by(id=chat_id).update(
                    {"updated_at": datetime.utcnow()}
                )
                
                return self._sqlalchemy_message_to_pydantic(db_message)
                
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return None

    def get_user_chat_sessions(
        self, 
        user_id: int,
        include_archived: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[PydanticChatSession]:
        """Get user's chat sessions."""
        try:
            with self.get_session() as session:
                query = session.query(SQLChatSession).filter_by(user_id=user_id)
                
                if not include_archived:
                    query = query.filter_by(is_archived=False)
                
                # Pinned first, then by updated_at
                db_sessions = (
                    query.order_by(
                        SQLChatSession.is_pinned.desc(),
                        SQLChatSession.updated_at.desc()
                    )
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                
                return [self._sqlalchemy_session_to_pydantic(s, session) for s in db_sessions]
                
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            return []

    def get_chat_messages(
        self, 
        chat_id: int, 
        limit: int = 100,
        offset: int = 0
    ) -> List[PydanticMessage]:
        """Get chat messages."""
        try:
            with self.get_session() as session:
                db_messages = (
                    session.query(SQLChatMessage)
                    .filter_by(chat_id=chat_id)
                    .order_by(SQLChatMessage.created_at.asc())
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                
                return [self._sqlalchemy_message_to_pydantic(msg) for msg in db_messages]
                
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return []

    def search_chats(
        self,
        user_id: int,
        query: str,
        include_archived: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search in user's chats."""
        try:
            with self.get_session() as session:
                # Search in titles
                chats_query = session.query(SQLChatSession).filter(
                    SQLChatSession.user_id == user_id,
                    SQLChatSession.title.contains(query)
                )
                
                if not include_archived:
                    chats_query = chats_query.filter_by(is_archived=False)
                
                results = []
                
                # Add matching chats
                for chat in chats_query.limit(limit).all():
                    results.append({
                        "id": chat.id,
                        "title": chat.title,
                        "updated_at": chat.updated_at,
                        "match_type": "title"
                    })
                
                # Search in messages if we need more results
                if len(results) < limit:
                    messages_query = (
                        session.query(SQLChatMessage)
                        .join(SQLChatSession)
                        .filter(
                            SQLChatSession.user_id == user_id,
                            SQLChatMessage.content.contains(query)
                        )
                    )
                    
                    if not include_archived:
                        messages_query = messages_query.filter(
                            SQLChatSession.is_archived == False
                        )
                    
                    seen_chats = {r["id"] for r in results}
                    
                    for msg in messages_query.limit(limit - len(results)).all():
                        if msg.chat_id not in seen_chats:
                            results.append({
                                "id": msg.chat.id,
                                "title": msg.chat.title,
                                "updated_at": msg.chat.updated_at,
                                "match_type": "message",
                                "matched_content": msg.content[:100]
                            })
                            seen_chats.add(msg.chat_id)
                
                return results[:limit]
                
        except Exception as e:
            logger.error(f"Error searching chats: {e}")
            return []

    # ---------------------------
    # Legacy Support (minimal)
    # ---------------------------
    
    def log_chat(
        self,
        user_message: str,
        assistant_response: str,
        data_source: Optional[str] = None,
    ) -> None:
        """Legacy: Add to chat_logs table."""
        try:
            with self.get_session() as session:
                log_entry = SQLChatLog(
                    user_message=user_message,
                    assistant_response=assistant_response,
                    data_source=data_source
                )
                session.add(log_entry)
                
        except Exception as e:
            logger.error(f"Error logging chat: {e}")

    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        try:
            with self.get_session() as session:
                stats = {
                    "users": session.query(SQLUser).count(),
                    "chat_sessions": session.query(SQLChatSession).count(),
                    "chat_messages": session.query(SQLChatMessage).count(),
                    "chat_logs": session.query(SQLChatLog).count(),
                }
                return stats
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    # ---------------------------
    # Helpers
    # ---------------------------
    
    def _sqlalchemy_user_to_pydantic(self, db_user: SQLUser) -> PydanticUser:
        """Convert SQLAlchemy User to Pydantic."""
        return sqlalchemy_to_pydantic(db_user)

    def _sqlalchemy_session_to_pydantic(self, db_session: SQLChatSession, session: Session = None) -> PydanticChatSession:
        """Convert SQLAlchemy ChatSession to Pydantic."""
    
        message_count = 0
        last_message = None
        
        # Если передана сессия, подсчитываем сообщения
        if session:
            try:
                message_count = session.query(SQLChatMessage).filter_by(
                    chat_id=db_session.id
                ).count()
                
                # Получаем последнее сообщение
                last_msg = (
                    session.query(SQLChatMessage)
                    .filter_by(chat_id=db_session.id)
                    .order_by(SQLChatMessage.created_at.desc())
                    .first()
                )
                
                if last_msg:
                    last_message = last_msg.content[:100]
                    if len(last_msg.content) > 100:
                        last_message += "..."
                        
            except Exception as e:
                logger.warning(f"Could not count messages for chat {db_session.id}: {e}")
                message_count = 1
        else:
        #  Если session не передана, ставим 1 чтобы показать чат  
             message_count = 1        

        return PydanticChatSession(
            id=db_session.id,
            user_id=db_session.user_id,
            title=db_session.title,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            is_archived=db_session.is_archived,
            is_pinned=db_session.is_pinned,
            is_incognito=db_session.is_incognito,
            message_count=message_count,
            last_message=last_message
        )
    
    def _sqlalchemy_message_to_pydantic(self, db_message: SQLChatMessage) -> PydanticMessage:
        """Convert SQLAlchemy ChatMessage to Pydantic."""
        metadata = None
        if db_message.message_metadata:
            try:
                metadata = json.loads(db_message.message_metadata)
            except json.JSONDecodeError:
                metadata = None

        return PydanticMessage(
            id=db_message.id,
            chat_id=db_message.chat_id,
            role=db_message.role,
            content=db_message.content,
            metadata=metadata,
            created_at=db_message.created_at
        )


# Global instance
db_manager = DatabaseManager()

def init_db():
    """Initialize database."""
    logger.info("Database initialized via DatabaseManager")