from __future__ import annotations

import sqlite3
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional


class DatabaseManager:
    """
    Класс для управления SQLite-базой данных внутреннего ассистента.
    Хранит логи чатов (вопрос, ответ, источник, timestamp).
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
    # Создание таблицы при запуске
    # ---------------------------
    def init_database(self) -> None:
        """Создание таблицы chat_logs, если она отсутствует."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_message TEXT NOT NULL,
                        assistant_response TEXT NOT NULL,
                        data_source TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()
        except Exception as e:
            print(f"[DatabaseManager] Error initializing database: {e}")

    # ---------------------------
    # Логирование
    # ---------------------------
    def log_chat(
        self,
        user_message: str,
        assistant_response: str,
        data_source: Optional[str] = None,
    ) -> None:
        """Добавляет запись в таблицу chat_logs."""
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
    # История чатов
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
        """Очистить все записи (опционально для админ-панели)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM chat_logs")
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