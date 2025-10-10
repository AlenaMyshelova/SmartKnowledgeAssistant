from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """
    Настройки приложения - все важные параметры в одном месте.
    Значения берутся из файла .env или переменных окружения.
    """
    
    # Информация о приложении
    PROJECT_NAME: str = "Smart Knowledge Assistant API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"  # Префикс для всех API маршрутов
    
    # Настройки OpenAI
    OPENAI_API_KEY: str  # Будет браться из .env файла
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # База данных
    DATABASE_URL: str = "sqlite:///./data/assistant.db"
    
    # CORS - какие сайты могут обращаться к нашему API
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173"]  # React dev server
    
    class Config:
        env_file = ".env"  # Откуда брать переменные

# Создаем один экземпляр настроек для всего приложения
settings = Settings()