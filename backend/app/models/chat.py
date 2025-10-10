from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ChatRequest(BaseModel):
    """
    Модель для запроса к чату.
    Описывает какие данные должен прислать клиент.
    
    Пример:
    {
        "message": "Как работает ваша компания?",
        "data_source": "company_faqs"
    }
    """
    message: str                    # Сообщение пользователя (обязательно)
    data_source: str = "company_faqs"  # Источник данных (по умолчанию FAQ)

class ChatResponse(BaseModel):
    """
    Модель для ответа чата.
    Описывает какие данные мы отправим клиенту обратно.
    
    Пример:
    {
        "response": "Наша компания работает в сфере...",
        "relevant_data": [{"Question": "...", "Answer": "..."}],
        "data_source": "company_faqs"
    }
    """
    response: str                           # Ответ от AI
    relevant_data: List[Dict[str, Any]]     # Найденные данные из базы
    data_source: str                        # Какой источник использовался

class ChatHistoryItem(BaseModel):
    """
    Модель для одного элемента истории чата.
    Используется при получении истории разговоров.
    """
    id: int
    user_message: str
    assistant_response: str
    data_source: Optional[str]
    timestamp: str

class DataSourceInfo(BaseModel):
    """
    Информация об источнике данных.
    Показывает какие данные доступны в системе.
    """
    name: str
    records_count: int
    columns: List[str]

class HealthResponse(BaseModel):
    """
    Ответ от health check эндпоинта.
    """
    status: str
    message: str
    version: str

class CategoryResponse(BaseModel):
    """
    Список доступных категорий FAQ.
    """
    categories: List[str]