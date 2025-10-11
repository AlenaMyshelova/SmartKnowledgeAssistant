from __future__ import annotations

import sqlite3
import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.models.user import UserCreate, User, UserUpdate


class DatabaseManager:
    """
    Класс для управления SQLite-базой данных внутреннего ассистента.
    Управляет пользователями, сессиями и логами чатов.
    """

    def __init__(self, db_path: str = "../data/assistant.db") -> None:
        # Абсолютный путь к базе относительно этого файла
        base_dir = Path(__file__).resolve().parent
        self.db_path: Path = (base_dir / db_path).resolve()

        # Гарантируем существование каталога
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Инициализация таблицы
        self.init_database()

    # ---------------------------
    # Создание таблиц при запуске
    # ---------------------------
    def init_database(self) -> None:
        """Создание необходимых таблиц, если они отсутствуют."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Создаем таблицу пользователей (для OAuth)
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
                
                # Создаем таблицу сессий чата
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    session_id TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """)
                
                # Создаем таблицу для сообщений чата
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id INTEGER,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    data_source TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id)
                )
                """)
                
                # Совместимость с существующей структурой
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    data_source TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                conn.commit()
                
        except Exception as e:
            print(f"[DatabaseManager] Error initializing database: {e}")

    # ---------------------------
    # Управление пользователями
    # ---------------------------
    
    def create_user(self, user_data: UserCreate) -> Optional[User]:
        """Создание нового пользователя."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Проверяем, существует ли пользователь с такими oauth_provider и oauth_id
                existing_user = self.get_user_by_oauth_id(user_data.oauth_provider, user_data.oauth_id)
                if existing_user:
                    return existing_user
                
                cursor.execute("""
                INSERT INTO users (email, name, avatar_url, oauth_provider, oauth_id, provider_data)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_data.email,
                    user_data.name,
                    user_data.avatar_url,
                    user_data.oauth_provider,
                    user_data.oauth_id,
                    json.dumps(user_data.provider_data) if user_data.provider_data else None
                ))
                
                conn.commit()
                user_id = cursor.lastrowid
                
                return self.get_user_by_id(user_id)
                
        except sqlite3.IntegrityError as e:
            print(f"[DatabaseManager] Error creating user (integrity constraint): {e}")
            return None
        except Exception as e:
            print(f"[DatabaseManager] Error creating user: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT * FROM users WHERE id = ? AND is_active = TRUE",
                    (user_id,)
                ).fetchone()
                
                if row:
                    return User(
                        id=row["id"],
                        email=row["email"],
                        name=row["name"],
                        avatar_url=row["avatar_url"],
                        oauth_provider=row["oauth_provider"],
                        oauth_id=row["oauth_id"],
                        is_active=bool(row["is_active"]),
                        created_at=self._parse_datetime(row["created_at"]),
                        last_login=self._parse_datetime(row["last_login"]) if row["last_login"] else None
                    )
                return None
                
        except Exception as e:
            print(f"[DatabaseManager] Error getting user by ID: {e}")
            return None
    
    def get_user_by_oauth_id(self, provider: str, oauth_id: str) -> Optional[User]:
        """Получение пользователя по провайдеру и oauth_id."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT * FROM users WHERE oauth_provider = ? AND oauth_id = ? AND is_active = TRUE",
                    (provider, oauth_id)
                ).fetchone()
                
                if row:
                    return User(
                        id=row["id"],
                        email=row["email"],
                        name=row["name"],
                        avatar_url=row["avatar_url"],
                        oauth_provider=row["oauth_provider"],
                        oauth_id=row["oauth_id"],
                        is_active=bool(row["is_active"]),
                        created_at=self._parse_datetime(row["created_at"]),
                        last_login=self._parse_datetime(row["last_login"]) if row["last_login"] else None
                    )
                return None
                
        except Exception as e:
            print(f"[DatabaseManager] Error getting user by OAuth ID: {e}")
            return None
    
    def update_last_login(self, user_id: int) -> bool:
        """Обновление времени последнего входа."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                    (user_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"[DatabaseManager] Error updating last login: {e}")
            return False
    
    def update_user(self, user_id: int, update_data: UserUpdate) -> Optional[User]:
        """Обновление данных пользователя."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Создаем динамический SQL запрос на основе переданных полей
                update_fields = []
                values = []
                
                if update_data.email is not None:
                    update_fields.append("email = ?")
                    values.append(update_data.email)
                
                if update_data.name is not None:
                    update_fields.append("name = ?")
                    values.append(update_data.name)
                
                if update_data.avatar_url is not None:
                    update_fields.append("avatar_url = ?")
                    values.append(update_data.avatar_url)
                
                if update_data.is_active is not None:
                    update_fields.append("is_active = ?")
                    values.append(update_data.is_active)
                
                if not update_fields:
                    return self.get_user_by_id(user_id)  # Нечего обновлять
                
                # Добавляем ID пользователя в конец values
                values.append(user_id)
                
                # Строим и выполняем SQL запрос
                query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
                cursor.execute(query, values)
                conn.commit()
                
                # Возвращаем обновленного пользователя
                return self.get_user_by_id(user_id)
                
        except Exception as e:
            print(f"[DatabaseManager] Error updating user: {e}")
            return None
    
    # ---------------------------
    # Логирование чатов (старый способ)
    # ---------------------------
    def log_chat(
        self,
        user_message: str,
        assistant_response: str,
        data_source: Optional[str] = None,
    ) -> None:
        """Добавляет запись в таблицу chat_logs (для обратной совместимости)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO chat_logs (user_message, assistant_response, data_source)
                    VALUES (?, ?, ?)
                    """,
                    (user_message, assistant_response, data_source),
                )
                conn.commit()
        except Exception as e:
            print(f"[DatabaseManager] Error logging chat: {e}")
    
    # ---------------------------
    # Управление чатами (новый способ)
    # ---------------------------
    def create_chat_session(self, session_id: str, user_id: Optional[int] = None) -> bool:
        """Создание новой сессии чата."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id)
                    VALUES (?, ?)
                    """,
                    (session_id, user_id),
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"[DatabaseManager] Error creating chat session: {e}")
            return False
    
    def add_chat_message(
        self,
        session_id: str,
        message_type: str,  # 'user' or 'assistant'
        content: str,
        user_id: Optional[int] = None,
        data_source: Optional[str] = None,
    ) -> bool:
        """Добавление сообщения в сессию чата."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO chat_messages 
                    (session_id, user_id, message_type, content, data_source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, user_id, message_type, content, data_source),
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"[DatabaseManager] Error adding chat message: {e}")
            return False
    
    def get_chat_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Получение всех сообщений сессии чата."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(
                    """
                    SELECT * FROM chat_messages
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                    """,
                    conn,
                    params=(session_id,),
                )
                return df.to_dict("records")
        except Exception as e:
            print(f"[DatabaseManager] Error fetching chat session messages: {e}")
            return []
    
    def get_user_chat_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """Получение всех сессий пользователя."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(
                    """
                    SELECT * FROM chat_sessions
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    """,
                    conn,
                    params=(user_id,),
                )
                return df.to_dict("records")
        except Exception as e:
            print(f"[DatabaseManager] Error fetching user chat sessions: {e}")
            return []
    
    # ---------------------------
    # История чатов (старый способ)
    # ---------------------------
    def get_chat_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Возвращает последние N записей из таблицы chat_logs
        в виде списка словарей (удобно для API).
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM chat_logs ORDER BY timestamp DESC LIMIT ?",
                    conn,
                    params=(limit,),
                )
            return df.to_dict("records")
        except Exception as e:
            print(f"[DatabaseManager] Error fetching chat history: {e}")
            return []
    
    # ---------------------------
    # Вспомогательные методы
    # ---------------------------
    def clear_history(self) -> None:
        """Очистить все записи чатов (опционально для админ-панели)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM chat_logs")
                conn.execute("DELETE FROM chat_messages")
                conn.commit()
        except Exception as e:
            print(f"[DatabaseManager] Error clearing chat history: {e}")
    
    def count_records(self) -> int:
        """Подсчёт количества записей в журнале."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM chat_logs")
                (count,) = cursor.fetchone()
                return int(count)
        except Exception as e:
            print(f"[DatabaseManager] Error counting records: {e}")
            return 0
    
    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Безопасное преобразование строки в datetime."""
        if not datetime_str:
            return None
        try:
            # SQLite возвращает даты как строки в разных форматах
            # Пробуем разные форматы
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            
            # Если не получилось, пробуем с ISO форматом
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except Exception:
            return datetime.now()  # В крайнем случае, возвращаем текущую дату


# Создаем глобальный экземпляр для использования в приложении
db_manager = DatabaseManager()


# Функция для инициализации базы данных (для совместимости с FastAPI)
def init_db():
    """Инициализация базы данных при запуске приложения."""
    try:
        # Используем существующий экземпляр
        db_manager.init_database()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")


# Создаем глобальный экземпляр репозитория пользователей (для совместимости)
class UserRepository:
    """
    Репозиторий для работы с пользователями через единый интерфейс.
    Использует db_manager для фактических операций с базой данных.
    """
    
    def create_user(self, user_data: UserCreate) -> Optional[User]:
        """Создание нового пользователя."""
        return db_manager.create_user(user_data)
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID."""
        return db_manager.get_user_by_id(user_id)
    
    def get_user_by_provider_id(self, provider: str, provider_id: str) -> Optional[User]:
        """Получение пользователя по провайдеру и oauth_id."""
        return db_manager.get_user_by_oauth_id(provider, provider_id)
    
    def update_last_login(self, user_id: int) -> bool:
        """Обновление времени последнего входа."""
        return db_manager.update_last_login(user_id)


# Создаем глобальный экземпляр репозитория пользователей
user_repository = UserRepository()