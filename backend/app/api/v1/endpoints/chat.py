from fastapi import APIRouter, HTTPException

from app.models.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

# Роутер для чат-эндпоинтов
router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def create_chat_message(request: ChatRequest):
    """
    Основной эндпоинт для чата с AI.
    
    POST /api/v1/chat
    Body: {"message": "Ваш вопрос", "data_source": "company_faqs"}
    """
    try:
        # Теперь вся логика инкапсулирована в сервисе
        response = await chat_service.process_chat_message(request)
        return response
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/chat/history")
def get_chat_history(limit: int = 20):
    """
    Получение истории чатов.
    
    GET /api/v1/chat/history?limit=20
    """
    try:
        history = chat_service.get_chat_history(limit)
        return {"history": history}
    except Exception as e:
        print(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat history")