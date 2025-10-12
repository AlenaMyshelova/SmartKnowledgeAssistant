from typing import List, Dict, Any

from app.models.chat import ChatRequest, ChatResponse
from app.services.openai_service import openai_service
from app.data_manager import DataManager
from app.database import DatabaseManager
from app.chat_utils import build_context_from_results
import logging
logger = logging.getLogger(__name__)
class ChatService:
    """
    Сервис для обработки чат сообщений.
    Координирует работу между поиском данных, AI и логированием.
    """
    
    def __init__(self):
        self.data_manager = DataManager()
        self.db_manager = DatabaseManager()
        
    async def get_response(self, message: str, data_source: str = "company_faqs", user_id: int = None) -> Dict[str, Any]:
        """Get AI response for a message."""
        try:
            # Используем существующий метод поиска
            relevant_data = self._search_relevant_data(message, data_source)
            
            # Формируем контекст
            context, scarcity_note = self._build_context(relevant_data)
            
            # Generate response from OpenAI (используем правильный метод)
            response = await openai_service.generate_response(
                query=message,
                context=context,
                scarcity_note=scarcity_note
            )
            
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
                "response": response,
                "sources": sources
            }
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "response": "I'm sorry, I encountered an error processing your request.",
                "sources": []
            }   

    
    async def process_chat_message(self, request: ChatRequest) -> ChatResponse:
        """
        Полная обработка сообщения пользователя.
        
        Процесс:
        1. Поиск релевантных данных в базе знаний
        2. Формирование контекста для AI
        3. Генерация ответа через OpenAI
        4. Логирование в базу данных
        5. Возврат структурированного ответа
        
        Args:
            request: Запрос пользователя (сообщение + источник данных)
            
        Returns:
            ChatResponse: Ответ AI + найденные данные + метаинформация
        """
        try:
            # Шаг 1: Поиск релевантных данных
            relevant_data = self._search_relevant_data(request.message, request.data_source)
            
            # Шаг 2: Формирование контекста для AI
            context, scarcity_note = self._build_context(relevant_data)
            
            # Шаг 3: Генерация ответа через OpenAI
            ai_response = await openai_service.generate_response(
                query=request.message,
                context=context,
                scarcity_note=scarcity_note
            )
            
            # Шаг 4: Логирование в БД
            self._log_conversation(request.message, ai_response, request.data_source)
            
            # Шаг 5: Возврат результата
            return ChatResponse(
                response=ai_response,
                relevant_data=relevant_data,
                data_source=request.data_source
            )
            
        except Exception as e:
            print(f"Chat service error: {e}")
            raise Exception(f"Failed to process chat message: {str(e)}")
    
    def _search_relevant_data(self, message: str, data_source: str) -> List[Dict[str, Any]]:
        logger.info(f"Searching in {data_source} for query: {message[:50]}...")
        """Поиск релевантных данных в базе знаний."""
        if data_source == "company_faqs":
            return self.data_manager.search_faqs(message)
        # В будущем можно добавить другие источники данных
        return []
    
    def _build_context(self, relevant_data: List[Dict[str, Any]]) -> tuple[str, str]:
        """Формирование контекста для AI из найденных данных."""
        return build_context_from_results(relevant_data)
    
    def _log_conversation(self, user_message: str, ai_response: str, data_source: str):
        """Логирование разговора в базу данных."""
        try:
            self.db_manager.log_chat(
                user_message=user_message,
                assistant_response=ai_response,
                data_source=data_source
            )
        except Exception as e:
            print(f"Failed to log conversation: {e}")
            # Не прерываем выполнение если логирование не удалось
    
    def get_chat_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получение истории чатов."""
        return self.db_manager.get_chat_history(limit)

# Создаем единственный экземпляр сервиса
chat_service = ChatService()