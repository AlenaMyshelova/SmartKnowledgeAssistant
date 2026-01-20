from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

from sqlalchemy import create_engine, text, func, case
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session, joinedload

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
        try:
            with self.get_session() as session:
                existing_user = session.query(SQLUser).filter_by(
                    oauth_provider=user_data.oauth_provider,
                    oauth_id=user_data.oauth_id
                ).first()
                
                if existing_user:
                    return self._sqlalchemy_user_to_pydantic(existing_user)
                
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
        

     
    def get_user_by_email(self, email: str) -> Optional[PydanticUser]:
        try:
            with self.get_session() as session:
                db_user = session.query(SQLUser).filter_by(
                    email=email,
                    is_active=True
                ).first()
                
                return self._sqlalchemy_user_to_pydantic(db_user) if db_user else None
                
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
        

    def update_last_login(self, user_id: int) -> bool:
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
        is_pinned: Optional[bool] = None,
        is_incognito: Optional[bool] = None,
    ) -> Optional[PydanticChatSession]:
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
                if is_incognito is not None:
                    chat.is_incognito = is_incognito    
                    
                chat.updated_at = datetime.utcnow()
                session.flush()
                session.refresh(chat)
                
                return self._sqlalchemy_session_to_pydantic(chat)
                
        except Exception as e:
            logger.error(f"Error updating chat {chat_id}: {e}")
            return None

    def delete_chat_session(self, chat_id: int) -> bool:
        try:
            with self.get_session() as session:
                chat = session.query(SQLChatSession).filter_by(id=chat_id).first()
                if chat:
                    session.delete(chat)  
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
        try:
            with self.get_session() as session:
                query = session.query(SQLChatSession).filter_by(user_id=user_id)
                
                if not include_archived:
                    query = query.filter_by(is_archived=False)

                query = query.options(joinedload(SQLChatSession.messages))
                
                db_sessions = (
                    query.order_by(
                        SQLChatSession.is_pinned.desc(),
                        SQLChatSession.updated_at.desc()
                    )
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                
                return [self._sqlalchemy_session_to_pydantic_with_loaded_messages(s) for s in db_sessions]
                
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            return []

    def get_chat_messages(
        self, 
        chat_id: int, 
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[PydanticMessage]:
        try:
            with self.get_session() as session:
                query = (
                        session.query(SQLChatMessage)
                        .filter_by(chat_id=chat_id)
                        .order_by(SQLChatMessage.created_at.asc())
                        .offset(offset)
                    )

                if limit is not None:
                        query = query.limit(limit)

                db_messages = query.all()
                
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
                    messages_query = messages_query.order_by(SQLChatMessage.created_at.desc())
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
        message_count = 0
        last_message = None
        
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
                message_count = 0   
        else:
            message_count = 0

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
    

    def _sqlalchemy_session_to_pydantic_with_loaded_messages(
        self, 
        db_session: SQLChatSession
    ) -> PydanticChatSession:
        messages = db_session.messages if db_session.messages else []
        message_count = len(messages)
        
        last_message = None
        if messages:
            last_msg = max(messages, key=lambda m: m.created_at)
            last_message = last_msg.content[:100]
            if len(last_msg.content) > 100:
                last_message += "..."
        
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
    
    def chat_belongs_to_user(self, chat_id: int, user_id: int) -> bool:
        try:
            with self.get_session() as session:
                exists = session.query(SQLChatSession).filter_by(
                    id=chat_id,
                    user_id=user_id
                ).first() is not None
                return exists
        except Exception as e:
            logger.error(f"Error checking chat ownership: {e}")
            return False
    
    def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        try:
            with self.get_session() as session:
                stats = session.query(
                    func.count(func.distinct(SQLChatSession.id)).label('total_chats'),
                    func.count(SQLChatMessage.id).label('total_messages'),
                    func.sum(case(
                        (SQLChatSession.is_archived == True, 1),
                        else_=0
                    )).label('archived_chats'),
                    func.sum(case(
                        (SQLChatSession.is_pinned == True, 1),
                        else_=0
                    )).label('pinned_chats')
                ).select_from(SQLChatSession).outerjoin(
                    SQLChatMessage,
                    SQLChatMessage.chat_id == SQLChatSession.id
                ).filter(
                    SQLChatSession.user_id == user_id
                ).first()
                
                total_chats = stats.total_chats or 0
                total_messages = stats.total_messages or 0
                
                return {
                    'total_chats': total_chats,
                    'total_messages': total_messages,
                    'archived_chats': stats.archived_chats or 0,
                    'pinned_chats': stats.pinned_chats or 0,
                    'average_messages_per_chat': (
                        total_messages / total_chats if total_chats > 0 else 0
                    )
                }
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {
                'total_chats': 0,
                'total_messages': 0,
                'archived_chats': 0,
                'pinned_chats': 0,
                'average_messages_per_chat': 0
            }

    def get_chat_session_by_id(self, 
                               chat_id: int, 
                               user_id: Optional[int] = None
                               ) -> Optional[PydanticChatSession]:

        try:
            with self.get_session() as session:
                query = session.query(SQLChatSession).filter_by(id=chat_id)
                
                if user_id is not None:
                    query = query.filter_by(user_id=user_id)
                
                db_session = query.first()
                
                if not db_session:
                    return None
                
                return self._sqlalchemy_session_to_pydantic(db_session, session)
                
        except Exception as e:
            logger.error(f"Error getting chat session {chat_id}: {e}")
            return None        



db_manager = DatabaseManager()

def init_db():
    """Initialize database."""
    logger.info("Database initialized via DatabaseManager")