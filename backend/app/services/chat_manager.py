"""
Chat management service with incognito mode for authenticated users.
"""
from __future__ import annotations

import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Database path (…/backend/data/assistant.db)
DB_PATH = (Path(__file__).resolve().parents[2] / "data" / "assistant.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # гарантируем наличие каталога


def _connect() -> sqlite3.Connection:
    """Создаём соединение с включёнными внешними ключами."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class ChatManager:
    def __init__(self):
        self.db_path = str(DB_PATH)
        self.incognito_chats: dict[int, dict] = {}
        self.incognito_messages: dict[int, list[dict]] = {}
        self._init_db()

    # -------- schema --------
    def _init_db(self):
        """Создание таблиц и миграции недостающих колонок."""
        with _connect() as conn:
            cur = conn.cursor()

            # Таблицы (если нет — создаём)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    title       TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_archived BOOLEAN   DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id    INTEGER NOT NULL,
                    role       TEXT    NOT NULL,
                    content    TEXT    NOT NULL,
                    metadata   TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                )
            """)

            # Миграции недостающих колонок
            self._add_column_if_missing(cur, "chat_sessions", "created_at",
                                        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            self._add_column_if_missing(cur, "chat_sessions", "updated_at",
                                        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            self._add_column_if_missing(cur, "chat_sessions", "is_archived",
                                        "is_archived BOOLEAN DEFAULT 0")
            self._add_column_if_missing(cur, "chat_messages", "created_at",
                                        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

            # Индексы (idempotent через IF NOT EXISTS с уникальным именем индекса)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated ON chat_sessions(user_id, updated_at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id_id ON chat_messages(chat_id, id)")

            conn.commit()

    @staticmethod
    def _add_column_if_missing(cur: sqlite3.Cursor, table: str, col: str, ddl: str):
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if col not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            logger.info("Added column %s to %s", col, table)

    # -------- utils --------
    @staticmethod
    def _now_iso() -> str:
        # UTC в ISO-8601 с Z
        return datetime.now(timezone.utc).isoformat()

    # -------- public API --------
    def create_chat(
        self,
        user_id: int,
        first_message: Optional[str] = None,
        title: Optional[str] = None,
        is_incognito: bool = False,
    ) -> int:
        """Create a new chat session."""
        if is_incognito:
            chat_id = -len(self.incognito_chats) - 1
            now = self._now_iso()
            self.incognito_chats[chat_id] = {
                "user_id": user_id,
                "title": title or "Incognito Chat",
                "created_at": now,
                "updated_at": now,
            }
            self.incognito_messages[chat_id] = []
            logger.info("Created incognito chat %s for user %s", chat_id, user_id)
            return chat_id

        if not title and first_message:
            title = first_message[:50] + ("..." if len(first_message) > 50 else "")

        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_sessions (user_id, title, created_at, updated_at) "
                "VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (user_id, title or "New Chat"),
            )
            chat_id = cur.lastrowid
            conn.commit()
        logger.info("Created chat %s for user %s", chat_id, user_id)
        return chat_id

    def add_message(self, chat_id: int, role: str, content: str, metadata: dict | None = None) -> int:
        """Add a message to chat."""
        if chat_id < 0:
            # Incognito: всё в памяти
            messages = self.incognito_messages.setdefault(chat_id, [])
            message_id = -len(messages) - 1
            now = self._now_iso()
            messages.append({
                "id": message_id,
                "role": role,
                "content": content,
                "metadata": metadata,
                "created_at": now,      # единый ключ времени
            })
            if chat_id in self.incognito_chats:
                self.incognito_chats[chat_id]["updated_at"] = now
            return message_id

        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_messages (chat_id, role, content, metadata, created_at) "
                "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (chat_id, role, content, json.dumps(metadata) if metadata else None),
            )
            mid = cur.lastrowid
            cur.execute("UPDATE chat_sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (chat_id,))
            conn.commit()
            return mid

    def get_user_chats(
        self,
        user_id: int,
        include_archived: bool = False,
        include_incognito: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Get user's chat sessions (list)."""
        chats: list[dict] = []
        with _connect() as conn:
            cur = conn.cursor()
            q = """
                SELECT 
                    cs.id,
                    cs.title,
                    cs.created_at,
                    cs.updated_at,
                    cs.is_archived,
                    COUNT(cm.id) AS message_count,
                    (SELECT content FROM chat_messages 
                     WHERE chat_id = cs.id 
                     ORDER BY id DESC LIMIT 1) AS last_message
                FROM chat_sessions cs
                LEFT JOIN chat_messages cm ON cs.id = cm.chat_id
                WHERE cs.user_id = ?
            """
            params = [user_id]
            if not include_archived:
                q += " AND (cs.is_archived = 0 OR cs.is_archived IS NULL)"
            q += " GROUP BY cs.id ORDER BY cs.updated_at DESC LIMIT ? OFFSET ?"
            params += [page_size, (page - 1) * page_size]
            cur.execute(q, params)
            for row in cur.fetchall():
                chats.append({
                    "id": row["id"],
                    "title": row["title"] or "New Chat",
                    "user_id": user_id,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "is_archived": bool(row["is_archived"]) if row["is_archived"] is not None else False,
                    "is_incognito": False,
                    "is_pinned": False,
                    "message_count": row["message_count"],
                    "last_message": (row["last_message"][:100] if row["last_message"] else None),
                })

            # Счётчик total — учитываем include_archived
            if include_archived:
                cur.execute("SELECT COUNT(*) AS total FROM chat_sessions WHERE user_id=?", (user_id,))
            else:
                cur.execute(
                    "SELECT COUNT(*) AS total FROM chat_sessions WHERE user_id=? AND (is_archived = 0 OR is_archived IS NULL)",
                    (user_id,),
                )
            total = cur.fetchone()["total"]

        if include_incognito:
            for cid, data in self.incognito_chats.items():
                if data["user_id"] == user_id:
                    msgs = self.incognito_messages.get(cid, [])
                    chats.append({
                        "id": cid,
                        "title": data["title"],
                        "user_id": user_id,
                        "created_at": data["created_at"],
                        "updated_at": data["updated_at"],
                        "is_archived": False,
                        "is_incognito": True,
                        "is_pinned": False,
                        "message_count": len(msgs),
                        "last_message": (msgs[-1]["content"][:100] if msgs else None),
                    })

        return {"chats": chats, "total": total, "page": page, "page_size": page_size}

    def get_chat_history(self, chat_id: int, user_id: int, limit: int | None = None, offset: int = 0) -> dict:
        """Get chat history with messages."""
        if chat_id < 0:
            chat = self.incognito_chats.get(chat_id)
            if not chat or chat["user_id"] != user_id:
                raise ValueError("Chat not found")
            msgs = self.incognito_messages.get(chat_id, [])
            if limit:
                msgs = msgs[offset: offset + limit]
            return {
                "chat": {
                    "id": chat_id,
                    "user_id": user_id, 
                    "title": chat["title"],
                    "created_at": chat["created_at"],
                    "updated_at": chat["updated_at"],
                    "is_incognito": True,
                },
                "messages": msgs,
            }

        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id=? AND user_id=?",
                (chat_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Chat not found")

            chat_info = {
                "id": row["id"],
                "user_id": user_id, 
                "title": row["title"] or "New Chat",
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "is_incognito": False,
            }

            q = """
                SELECT id, role, content, metadata, created_at
                FROM chat_messages
                WHERE chat_id = ?
                ORDER BY id ASC
            """
            params = [chat_id]
            if limit:
                q += " LIMIT ? OFFSET ?"
                params += [limit, offset]
            cur.execute(q, params)
            messages = [{
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "metadata": (json.loads(r["metadata"]) if r["metadata"] else None),
                "created_at": r["created_at"],
            } for r in cur.fetchall()]

        return {"chat": chat_info, "messages": messages}

    def update_chat(self, chat_id: int, user_id: int, title: str | None = None, is_archived: bool | None = None) -> bool:
        """Update chat session."""
        if chat_id < 0:
            chat = self.incognito_chats.get(chat_id)
            if chat and chat["user_id"] == user_id and title is not None:
                chat["title"] = title
                chat["updated_at"] = self._now_iso()
                return True
            return False

        with _connect() as conn:
            cur = conn.cursor()
            sets, params = [], []
            if title is not None:
                sets.append("title = ?"); params.append(title)
            if is_archived is not None:
                sets.append("is_archived = ?"); params.append(int(is_archived))
            if not sets:
                return False
            sets.append("updated_at = CURRENT_TIMESTAMP")
            q = f"UPDATE chat_sessions SET {', '.join(sets)} WHERE id = ? AND user_id = ?"
            params.extend([chat_id, user_id])   
            cur.execute(q, params)
            success = cur.rowcount > 0
            conn.commit()
            return success


    def delete_chat(self, chat_id: int, user_id: int) -> bool:
        """Delete chat session."""
        if chat_id < 0:
            chat = self.incognito_chats.get(chat_id)
            if chat and chat["user_id"] == user_id:
                del self.incognito_chats[chat_id]
                if chat_id in self.incognito_messages:
                    del self.incognito_messages[chat_id]
                return True
            return False

        with _connect() as conn:
            cur = conn.cursor()
            # Сначала удаляем сообщения
            cur.execute("DELETE FROM chat_messages WHERE chat_id = ?", (chat_id,))
            # Затем удаляем чат
            cur.execute("DELETE FROM chat_sessions WHERE id = ? AND user_id = ?", (chat_id, user_id))
            success = cur.rowcount > 0
            conn.commit()
            return success

    
def search_chats(self, user_id: int, query: str, include_archived: bool = False, limit: int = 50) -> list:
    """Search in user's chats - case insensitive."""
    with _connect() as conn:
        cur = conn.cursor()
        
        # Логирование для отладки
        logger.info(f"Searching for '{query}' for user {user_id}")
        
        # Используем LOWER для case-insensitive поиска
        base_query = """
            SELECT DISTINCT 
                cs.id, 
                cs.title, 
                cs.created_at, 
                cs.updated_at,
                cs.is_archived,
                COUNT(DISTINCT cm.id) as message_count
            FROM chat_sessions cs
            LEFT JOIN chat_messages cm ON cs.id = cm.chat_id
            WHERE cs.user_id = ? 
            AND (
                LOWER(cs.title) LIKE LOWER(?) 
                OR LOWER(cm.content) LIKE LOWER(?)
            )
        """
        
        if not include_archived:
            base_query += " AND (cs.is_archived = 0 OR cs.is_archived IS NULL)"
        
        base_query += " GROUP BY cs.id ORDER BY cs.updated_at DESC LIMIT ?"
        
        search_pattern = f"%{query}%"
        cur.execute(base_query, (user_id, search_pattern, search_pattern, limit))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "id": row["id"],
                "title": row["title"] or "New Chat",
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "is_archived": bool(row["is_archived"]) if row["is_archived"] is not None else False,
                "is_incognito": False,  # Обычные чаты никогда не incognito
                "message_count": row["message_count"]
            })
        
        logger.info(f"Found {len(results)} results for query '{query}'")
        return results

    def get_chat_mode_status(self, user_id: int) -> dict:
        """Get chat mode status."""
        active_incognito = sum(1 for chat in self.incognito_chats.values() if chat["user_id"] == user_id)
        
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM chat_sessions WHERE user_id = ?", (user_id,))
            saved_chats = cur.fetchone()[0]
        
        return {
            "active_incognito_chats": active_incognito,
            "saved_chats": saved_chats
        }

    def clear_incognito_chats(self, user_id: int) -> int:
        """Clear all incognito chats for user."""
        count = 0
        chats_to_delete = []
        
        for chat_id, chat_data in self.incognito_chats.items():
            if chat_data["user_id"] == user_id:
                chats_to_delete.append(chat_id)
                count += 1
        
        for chat_id in chats_to_delete:
            del self.incognito_chats[chat_id]
            if chat_id in self.incognito_messages:
                del self.incognito_messages[chat_id]
        
        return count
chat_manager = ChatManager()