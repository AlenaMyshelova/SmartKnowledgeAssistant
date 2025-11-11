from __future__ import annotations

import sqlite3
import pandas as pd
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
from app.models.database_models import Base, User as SQLUser, ChatSession as SQLChatSession, ChatMessage as SQLChatMessage, ChatLog as SQLChatLog
from app.models.user import UserCreate, User as PydanticUser, UserUpdate, sqlalchemy_to_pydantic
from app.models.chat import (
    ChatSession as PydanticChatSession, 
    ChatMessage as PydanticMessage,
    ChatSessionCreate,
    MessageCreate
)

# Set up logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Enhanced DatabaseManager with SQLAlchemy and Alembic support.
    Maintains backward compatibility with existing methods while adding new ORM-based functionality.
    """

    def __init__(self, db_path: str = "../data/assistant.db") -> None:
        # Calculate absolute path relative to this file
        base_dir = Path(__file__).resolve().parent
        self.db_path: Path = (base_dir / db_path).resolve()

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # SQLAlchemy setup
        self.db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            self.db_url,
            echo=False,  # Set to True for SQL debugging
            connect_args={"check_same_thread": False}  # Allow multiple threads
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Initialize database tables (legacy method for backward compatibility)
        self._init_legacy_database()
        
        # Check and apply migrations if available
        self._check_and_apply_migrations()

    @contextmanager
    def get_session(self) -> Session:
        """
        Get SQLAlchemy session with automatic cleanup and transaction management.
        """
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
        """
        Check and apply pending Alembic migrations if migration system is available.
        """
        try:
            # Import and initialize migration manager
            from app.database.migration_manager import initialize_migration_manager, get_migration_manager
            
            # Initialize if not already done
            if get_migration_manager() is None:
                initialize_migration_manager(self.db_url)
            
            migration_manager = get_migration_manager()
            if migration_manager and not migration_manager.is_database_up_to_date():
                logger.info("Database schema is outdated. Applying migrations...")
                migration_manager.upgrade_database()
                logger.info("Migrations applied successfully")
            else:
                logger.info("Database schema is up to date")
                
        except ImportError:
            logger.warning("Migration manager not available, skipping migration check")
        except Exception as e:
            logger.error(f"Migration check failed: {e}")
            # In development, we can continue without migrations
            # In production, you might want to raise the exception

    def _init_legacy_database(self) -> None:
        """
        Legacy database initialization for backward compatibility.
        Creates tables using raw SQL if they don't exist.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create users table (OAuth authentication)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    avatar_url TEXT,
                    oauth_provider TEXT NOT NULL,
                    oauth_id TEXT NOT NULL,
                    provider_data TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    UNIQUE(oauth_provider, oauth_id)
                )
                """)
                
                # Create chat sessions table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_archived BOOLEAN DEFAULT FALSE,
                    is_pinned BOOLEAN DEFAULT FALSE,
                    is_incognito BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """)

        
                
                # Create chat messages table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
                )
                """)
                # Add column rename for existing databases
                try:
                    cursor.execute("ALTER TABLE chat_messages RENAME COLUMN metadata TO message_metadata")
                    logger.info("Renamed metadata column to message_metadata in chat_messages table")
                except sqlite3.OperationalError:
                    # Column doesn't exist or already renamed
                    pass
                
                # Legacy chat logs table for backward compatibility
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    data_source TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Legacy tables for backward compatibility
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions_old (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    session_id TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages_old (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id INTEGER,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    data_source TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (session_id) REFERENCES chat_sessions_old (session_id)
                )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated ON chat_sessions(user_id, updated_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_timestamp ON chat_logs(timestamp)")
                
                conn.commit()
                logger.info("Legacy database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing legacy database: {e}")

    # ---------------------------
    # User Management (Enhanced with SQLAlchemy)
    # ---------------------------
    
    def create_user(self, user_data: UserCreate) -> Optional[PydanticUser]:
        """
        Create a new user using SQLAlchemy ORM.
        Returns existing user if OAuth provider + ID combination already exists.
        """
        try:
            with self.get_session() as session:
                # Check if user already exists
                existing_user = session.query(SQLUser).filter_by(
                    oauth_provider=user_data.oauth_provider,
                    oauth_id=user_data.oauth_id
                ).first()
                
                if existing_user:
                    return self._sqlalchemy_user_to_pydantic(existing_user)
                
                # Create new user
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
                session.flush()  # Get the ID without committing
                session.refresh(db_user)
                
                logger.info(f"Created new user: {user_data.email}")
                return self._sqlalchemy_user_to_pydantic(db_user)
                
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error creating user: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[PydanticUser]:
        """Get user by ID using SQLAlchemy ORM."""
        try:
            with self.get_session() as session:
                db_user = session.query(SQLUser).filter_by(
                    id=user_id, 
                    is_active=True
                ).first()
                
                return self._sqlalchemy_user_to_pydantic(db_user) if db_user else None
                
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    def get_user_by_oauth_id(self, provider: str, oauth_id: str) -> Optional[PydanticUser]:
        """Get user by OAuth provider and ID using SQLAlchemy ORM."""
        try:
            with self.get_session() as session:
                db_user = session.query(SQLUser).filter_by(
                    oauth_provider=provider,
                    oauth_id=oauth_id,
                    is_active=True
                ).first()
                
                return self._sqlalchemy_user_to_pydantic(db_user) if db_user else None
                
        except Exception as e:
            logger.error(f"Error getting user by OAuth ID {provider}:{oauth_id}: {e}")
            return None

    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp."""
        try:
            with self.get_session() as session:
                user = session.query(SQLUser).filter_by(id=user_id).first()
                if user:
                    user.last_login = datetime.utcnow()
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}")
            return False

    def update_user(self, user_id: int, update_data: UserUpdate) -> Optional[PydanticUser]:
        """Update user data using SQLAlchemy ORM."""
        try:
            with self.get_session() as session:
                user = session.query(SQLUser).filter_by(id=user_id).first()
                if not user:
                    return None
                
                # Update fields if provided
                if update_data.email is not None:
                    user.email = update_data.email
                if update_data.name is not None:
                    user.name = update_data.name
                if update_data.avatar_url is not None:
                    user.avatar_url = update_data.avatar_url
                if update_data.is_active is not None:
                    user.is_active = update_data.is_active
                
                session.flush()
                session.refresh(user)
                
                return self._sqlalchemy_user_to_pydantic(user)
                
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return None

    # ---------------------------
    # Chat Management (Enhanced with SQLAlchemy)
    # ---------------------------
    
    def create_chat_session(self, user_id: int, title: Optional[str] = None) -> Optional[PydanticChatSession]:
        """Create a new chat session using SQLAlchemy ORM."""
        try:
            with self.get_session() as session:
                db_session = SQLChatSession(
                    user_id=user_id,
                    title=title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                
                session.add(db_session)
                session.flush()
                session.refresh(db_session)
                
                logger.info(f"Created new chat session {db_session.id} for user {user_id}")
                return self._sqlalchemy_session_to_pydantic(db_session)
                
        except Exception as e:
            logger.error(f"Error creating chat session for user {user_id}: {e}")
            return None

    def add_message_to_chat(
        self, 
        chat_id: int, 
        role: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[PydanticMessage]:
        """Add a message to a chat session using SQLAlchemy ORM."""
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
                
                # Update chat session's updated_at timestamp
                session.query(SQLChatSession).filter_by(id=chat_id).update(
                    {"updated_at": datetime.utcnow()}
                )
                
                return self._sqlalchemy_message_to_pydantic(db_message)
                
        except Exception as e:
            logger.error(f"Error adding message to chat {chat_id}: {e}")
            return None

    def get_user_chat_sessions(
        self, 
        user_id: int, 
        limit: int = 20, 
        offset: int = 0, 
        include_archived: bool = False
    ) -> List[PydanticChatSession]:
        """Get user's chat sessions with pagination using SQLAlchemy ORM."""
        try:
            with self.get_session() as session:
                query = session.query(SQLChatSession).filter_by(user_id=user_id)
                
                if not include_archived:
                    query = query.filter_by(is_archived=False)
                
                db_sessions = (query
                             .order_by(SQLChatSession.updated_at.desc())
                             .offset(offset)
                             .limit(limit)
                             .all())
                
                return [self._sqlalchemy_session_to_pydantic(session) for session in db_sessions]
                
        except Exception as e:
            logger.error(f"Error getting chat sessions for user {user_id}: {e}")
            return []

    def get_chat_messages(self, chat_id: int, limit: int = 100) -> List[PydanticMessage]:
        """Get messages for a specific chat session."""
        try:
            with self.get_session() as session:
                db_messages = (session.query(SQLChatMessage)
                             .filter_by(chat_id=chat_id)
                             .order_by(SQLChatMessage.created_at.asc())
                             .limit(limit)
                             .all())
                
                return [self._sqlalchemy_message_to_pydantic(msg) for msg in db_messages]
                
        except Exception as e:
            logger.error(f"Error getting messages for chat {chat_id}: {e}")
            return []

    # ---------------------------
    # Legacy Methods (Backward Compatibility)
    # ---------------------------
    
    def log_chat(
        self,
        user_message: str,
        assistant_response: str,
        data_source: Optional[str] = None,
    ) -> None:
        """
        Legacy method: Add entry to chat_logs table for backward compatibility.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO chat_logs (user_message, assistant_response, data_source) VALUES (?, ?, ?)",
                    (user_message, assistant_response, data_source)
                )
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error logging chat (legacy): {e}")

    def create_chat_session_legacy(self, session_id: str, user_id: Optional[int] = None) -> bool:
        """Legacy method: Create chat session with string ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO chat_sessions_old (session_id, user_id) VALUES (?, ?)",
                    (session_id, user_id)
                )
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error creating legacy chat session: {e}")
            return False

    def add_chat_message_legacy(
        self,
        session_id: str,
        message_type: str,  # 'user' or 'assistant'
        content: str,
        user_id: Optional[int] = None,
        data_source: Optional[str] = None,
    ) -> bool:
        """Legacy method: Add message to legacy chat_messages table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO chat_messages_old 
                    (session_id, user_id, message_type, content, data_source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, user_id, message_type, content, data_source)
                )
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding legacy chat message: {e}")
            return False

    def get_chat_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Legacy method: Get messages for string-based session ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM chat_messages_old WHERE session_id = ? ORDER BY timestamp ASC",
                    conn,
                    params=(session_id,)
                )
                return df.to_dict("records")
                
        except Exception as e:
            logger.error(f"Error fetching legacy chat session messages: {e}")
            return []

    def get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Legacy method: Get recent entries from chat_logs table.
        Returns list of dictionaries for API compatibility.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM chat_logs ORDER BY timestamp DESC LIMIT ?",
                    conn,
                    params=(limit,)
                )
                return df.to_dict("records")
                
        except Exception as e:
            logger.error(f"Error fetching chat history: {e}")
            return []

    # ---------------------------
    # Utility Methods
    # ---------------------------
    
    def clear_history(self) -> None:
        """Clear all chat records (admin function)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM chat_logs")
                conn.execute("DELETE FROM chat_messages")
                conn.execute("DELETE FROM chat_messages_old")
                conn.commit()
                logger.info("Chat history cleared")
                
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")

    def count_records(self) -> int:
        """Count records in chat_logs table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM chat_logs")
                (count,) = cursor.fetchone()
                return int(count)
                
        except Exception as e:
            logger.error(f"Error counting records: {e}")
            return 0

    def get_database_stats(self) -> Dict[str, int]:
        """Get statistics about database tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                tables = ['users', 'chat_sessions', 'chat_messages', 'chat_logs']
                
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        (count,) = cursor.fetchone()
                        stats[table] = int(count)
                    except sqlite3.OperationalError:
                        stats[table] = 0  # Table doesn't exist
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    # ---------------------------
    # Helper Methods for Model Conversion
    # ---------------------------
    
    def _sqlalchemy_user_to_pydantic(self, db_user: SQLUser) -> PydanticUser:
        """Convert SQLAlchemy User model to Pydantic User model."""
        return sqlalchemy_to_pydantic(db_user)

    def _sqlalchemy_session_to_pydantic(self, db_session: SQLChatSession) -> PydanticChatSession:
        """Convert SQLAlchemy ChatSession model to Pydantic ChatSession model."""
        return PydanticChatSession(
            id=db_session.id,
            user_id=db_session.user_id,
            title=db_session.title,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            is_archived=db_session.is_archived,
            is_pinned=db_session.is_pinned,
            is_incognito=getattr(db_session, 'is_incognito', False) 
        )

    def _sqlalchemy_message_to_pydantic(self, db_message: SQLChatMessage) -> PydanticMessage:
        """Convert SQLAlchemy ChatMessage model to Pydantic Message model."""
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

    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """
        Safe datetime string parsing with multiple format support.
        """
        if not datetime_str:
            return None
            
        try:
            # Try different datetime formats
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            
            # Try ISO format
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            
        except Exception:
            logger.warning(f"Could not parse datetime string: {datetime_str}")
            return datetime.now()  # Fallback to current datetime


# Create global instance for use throughout the application
db_manager = DatabaseManager()


def init_db():
    """
    Initialize database on application startup (FastAPI compatibility).
    """
    try:
        # The database is already initialized in the constructor
        db_manager._init_legacy_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


# Legacy user repository for backward compatibility
class UserRepository:
    """
    Legacy user repository interface.
    Uses db_manager for actual database operations.
    """
    
    def create_user(self, user_data: UserCreate) -> Optional[PydanticUser]:
        """Create a new user."""
        return db_manager.create_user(user_data)
    
    def get_user_by_id(self, user_id: int) -> Optional[PydanticUser]:
        """Get user by ID."""
        return db_manager.get_user_by_id(user_id)
    
    def get_user_by_provider_id(self, provider: str, provider_id: str) -> Optional[PydanticUser]:
        """Get user by OAuth provider and ID."""
        return db_manager.get_user_by_oauth_id(provider, provider_id)
    
    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp."""
        return db_manager.update_last_login(user_id)


# Create global user repository instance
user_repository = UserRepository()