"""
Chat management service with incognito mode for authenticated users.
"""

import json
import logging
import sqlite3
import shutil
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager

from app.models.chat import ChatSession, ChatMessage

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "assistant.db"


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class ChatManager:
    """Service for managing chat sessions with incognito mode."""
    
    def __init__(self):
        """Initialize chat manager and ensure database tables exist."""
        self._backup_database()  # Create backup before any migrations
        self._migrate_tables()  # Migrate existing tables
        self._ensure_tables()
        # Store incognito chats in memory (not persisted)
        self.incognito_chats: Dict[int, Dict[str, Any]] = {}
        self.incognito_messages: Dict[int, List[Dict[str, Any]]] = {}
        self.incognito_counter = 0
    
    def _backup_database(self):
        """Create a backup of the database before migration."""
        if DB_PATH.exists():
            backup_path = DB_PATH.parent / f"assistant_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            try:
                shutil.copy2(DB_PATH, backup_path)
                logger.info(f"Database backed up to {backup_path}")
            except Exception as e:
                logger.warning(f"Could not create backup: {e}")
    
    def _migrate_tables(self):
        """Migrate existing tables to new structure."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Check and migrate chat_sessions table
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='chat_sessions'
                """)
                
                if cursor.fetchone():
                    # Get current table structure
                    cursor.execute("PRAGMA table_info(chat_sessions)")
                    columns = cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    # If it's the old structure with session_id, migrate data
                    if 'session_id' in column_names and 'title' not in column_names:
                        logger.info("Migrating old chat_sessions table...")
                        
                        # Create new table with correct structure
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS chat_sessions_new (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id INTEGER NOT NULL,
                                title TEXT DEFAULT 'New Chat',
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                is_archived BOOLEAN DEFAULT 0,
                                is_incognito BOOLEAN DEFAULT 0,
                                message_count INTEGER DEFAULT 0,
                                last_message TEXT,
                                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                            )
                        """)
                        
                        # Migrate data from old table
                        cursor.execute("""
                            INSERT INTO chat_sessions_new (id, user_id, created_at)
                            SELECT id, user_id, created_at 
                            FROM chat_sessions
                            WHERE user_id IS NOT NULL
                        """)
                        
                        # Rename tables
                        cursor.execute("DROP TABLE chat_sessions")
                        cursor.execute("ALTER TABLE chat_sessions_new RENAME TO chat_sessions")
                        
                        logger.info("Successfully migrated chat_sessions table")
                    
                    # Add missing columns to existing table
                    else:
                        columns_to_add = [
                            ("is_incognito", "BOOLEAN DEFAULT 0"),
                            ("is_archived", "BOOLEAN DEFAULT 0"),
                            ("message_count", "INTEGER DEFAULT 0"),
                            ("last_message", "TEXT"),
                            ("title", "TEXT DEFAULT 'New Chat'"),
                            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                        ]
                        
                        for column_name, column_def in columns_to_add:
                            if column_name not in column_names:
                                try:
                                    cursor.execute(f"""
                                        ALTER TABLE chat_sessions 
                                        ADD COLUMN {column_name} {column_def}
                                    """)
                                    logger.info(f"Added column {column_name} to chat_sessions")
                                except sqlite3.OperationalError as e:
                                    logger.debug(f"Column {column_name} already exists or error: {e}")
                
                # Check and migrate chat_messages table
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='chat_messages'
                """)
                
                if cursor.fetchone():
                    cursor.execute("PRAGMA table_info(chat_messages)")
                    columns = cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    # If it's the old structure, migrate data
                    if 'session_id' in column_names and 'chat_id' not in column_names:
                        logger.info("Migrating old chat_messages table...")
                        
                        # Create new table
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS chat_messages_new (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                chat_id INTEGER NOT NULL,
                                role TEXT NOT NULL,
                                content TEXT NOT NULL,
                                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                metadata TEXT,
                                FOREIGN KEY (chat_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                            )
                        """)
                        
                        # Try to migrate data if possible
                        # This assumes we can map session_id to chat_id somehow
                        # If not possible, just create empty new table
                        try:
                            cursor.execute("""
                                INSERT INTO chat_messages_new (role, content, timestamp, metadata)
                                SELECT 
                                    CASE 
                                        WHEN message_type = 'user' THEN 'user'
                                        WHEN message_type = 'assistant' THEN 'assistant'
                                        ELSE message_type
                                    END as role,
                                    content,
                                    timestamp,
                                    data_source as metadata
                                FROM chat_messages
                                WHERE content IS NOT NULL
                            """)
                            logger.info("Migrated messages from old table")
                        except Exception as e:
                            logger.warning(f"Could not migrate messages: {e}")
                        
                        # Rename tables
                        cursor.execute("DROP TABLE chat_messages")
                        cursor.execute("ALTER TABLE chat_messages_new RENAME TO chat_messages")
                        
                        logger.info("Successfully migrated chat_messages table")
                    
                    # Add missing columns if needed
                    else:
                        columns_to_add = [
                            ("metadata", "TEXT"),
                            ("role", "TEXT")
                        ]
                        
                        for column_name, column_def in columns_to_add:
                            if column_name not in column_names:
                                try:
                                    cursor.execute(f"""
                                        ALTER TABLE chat_messages 
                                        ADD COLUMN {column_name} {column_def}
                                    """)
                                    logger.info(f"Added column {column_name} to chat_messages")
                                except sqlite3.OperationalError as e:
                                    logger.debug(f"Column {column_name} already exists or error: {e}")
                
                conn.commit()
                logger.info("Database migration completed successfully")
                
            except Exception as e:
                logger.error(f"Error during migration: {e}")
                conn.rollback()
                raise
    
    def _ensure_tables(self):
        """Ensure required database tables exist with correct structure."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT DEFAULT 'New Chat',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_archived BOOLEAN DEFAULT 0,
                    is_incognito BOOLEAN DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    last_message TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (chat_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes (with proper error handling)
            indexes = [
                ("idx_chat_sessions_user_id", "chat_sessions(user_id)"),
                ("idx_chat_sessions_incognito", "chat_sessions(is_incognito)"),
                ("idx_chat_messages_chat_id", "chat_messages(chat_id)")
            ]
            
            for index_name, index_def in indexes:
                try:
                    cursor.execute(f'''
                        CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}
                    ''')
                except sqlite3.OperationalError as e:
                    logger.debug(f"Index {index_name} already exists or error: {e}")
            
            conn.commit()
            logger.info("Database tables verified/created successfully")
    
    # ... rest of the ChatManager class remains the same ...
    
    async def create_incognito_chat(
        self, 
        user_id: int,
        title: Optional[str] = None,
        first_message: Optional[str] = None
    ) -> int:
        """
        Create an incognito chat session (stored in memory only).
        
        Args:
            user_id: ID of the authenticated user
            title: Optional title for the chat
            first_message: Optional first message to generate title
            
        Returns:
            ID of the created incognito chat session
        """
        # Generate temporary ID for incognito chat
        self.incognito_counter += 1
        chat_id = -self.incognito_counter  # Negative IDs for incognito chats
        
        # Auto-generate title if needed
        if not title and first_message:
            title = self._generate_title_from_message(first_message)
        elif not title:
            title = "Incognito Chat"
        
        # Store in memory
        self.incognito_chats[chat_id] = {
            'id': chat_id,
            'user_id': user_id,
            'title': title,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'is_archived': False,
            'is_incognito': True,
            'message_count': 0,
            'last_message': None
        }
        
        self.incognito_messages[chat_id] = []
        
        logger.info(f"Created incognito chat {chat_id} for user {user_id}")
        return chat_id
    
    # ... rest of the methods remain the same ...
    
    def _generate_title_from_message(self, message: str, max_length: int = 50) -> str:
        """
        Generate a chat title from the first message.
        
        Args:
            message: First message content
            max_length: Maximum length of the title
            
        Returns:
            Generated title
        """
        # Clean and truncate message
        title = message.strip().replace('\n', ' ')
        
        if len(title) > max_length:
            title = title[:max_length-3] + '...'
        
        return title or "New Chat"


# Create singleton instance
chat_manager = ChatManager()