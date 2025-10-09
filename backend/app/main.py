from __future__ import annotations
import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openai import OpenAI

from .database import DatabaseManager
from .data_manager import DataManager
from .chat_utils import build_context_from_results  # вспомогательная функция

# Загружаем переменные окружения из backend/.env
load_dotenv()

# --- Инициализация приложения и зависимостей ---
app = FastAPI(title="Smart Knowledge Assistant API")

# Источники данных / БД
db_manager = DatabaseManager()
data_manager = DataManager()

# OpenAI-клиент (ключ берётся из OPENAI_API_KEY)
client = OpenAI()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Разрешаем запросы с фронтенда (Vite React на 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic-модели ---
class ChatRequest(BaseModel):
    message: str
    data_source: str = "company_faqs"  # на будущее: выбрать другой источник

class ChatResponse(BaseModel):
    response: str
    relevant_data: List[Dict[str, Any]]
    data_source: str


@app.get("/api/data-sources")
def get_data_sources():
    """Получение доступных источников данных"""
    return data_manager.get_all_data_sources()

@app.get("/api/categories")
def get_categories():
    """Получение всех категорий FAQ"""
    return {"categories": data_manager.get_all_categories()}

@app.get("/api/chat-history")
def get_chat_history(limit: int = 20):
    """Получение истории чатов"""
    return db_manager.get_chat_history(limit)

@app.get("/api/faqs/{category}")
def get_faqs_by_category(category: str):
    """Получение FAQ по категории"""
    return {"faqs": data_manager.get_faq_by_category(category)}

# --- Основной чат-эндпоинт на Responses API ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Основной endpoint для чата (Responses API).
    1) Ищем релевантные записи в локальном источнике (FAQ CSV).
    2) Готовим контекст (консолидируем Q/A сниппеты).
    3) Отдаём в OpenAI Responses API вместе с системной ролью.
    4) Возвращаем ответ ассистента + список найденных сниппетов.
    """
    try:
        # 1) Локальный поиск по FAQ
        relevant_data = data_manager.search_faqs(request.message)

        # 2) Формируем контекст и заметку о нехватке данных (если нужно)
        context, scarcity_note = build_context_from_results(relevant_data)

        # 3) Подготовка сообщений для Responses API
        # System: правила поведения ассистента.
        # User: контекст + вопрос пользователя (+ scarcity_note при отсутствии сниппетов).
        system_prompt = (
            "You are a Smart Knowledge Assistant for TechNova company. "
            "Use the provided company information (if any) as the primary source. "
            "If there isn't enough relevant company information, you may use general knowledge, "
            "but explicitly mention that you're doing so. "
            "Be helpful, professional, concise, and list any used snippets."
        )
        user_prompt = f"{context}\nUser question: {request.message}{scarcity_note}"

        # 4) Вызов Responses API
        resp = client.responses.create(
            model=MODEL_NAME,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_output_tokens=500,
        )

        # Responses API возвращает итоговый текст здесь:
        assistant_response = resp.output_text

        # 5) Логирование в SQLite
        db_manager.log_chat(
            user_message=request.message,
            assistant_response=assistant_response,
            data_source=request.data_source,
        )

        # 6) Ответ клиенту
        return ChatResponse(
            response=assistant_response,
            relevant_data=relevant_data,
            data_source=request.data_source,
        )

    except Exception as e:
        # Для продакшена замените detail на нейтральное сообщение и логируйте e во внутренний лог
        raise HTTPException(status_code=500, detail=str(e))