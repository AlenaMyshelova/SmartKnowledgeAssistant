import os
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, List

class Settings(BaseSettings):
    """
    Настройки приложения - все важные параметры в одном месте.
    Значения берутся из файла .env или переменных окружения.
    """
    
    # Информация о приложении
    PROJECT_NAME: str = "Smart Knowledge Assistant API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Настройки OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # База данных
    DATABASE_URL: str = "sqlite:///./data/assistant.db"
    
    # JWT настройки
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 дней в минутах
    
    # OAuth Settings
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    
    # URLs
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8001"
    
    # Debug
    DEBUG: bool = True
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
    ]
    
    @property
    def OAUTH_PROVIDERS(self) -> Dict[str, Dict[str, Any]]:
        """Динамически формируем список OAuth провайдеров на основе настроек"""
        providers = {}
        
        # Добавляем Google только если есть учетные данные
        if self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET:
            providers["google"] = {
                "client_id": self.GOOGLE_CLIENT_ID,
                "client_secret": self.GOOGLE_CLIENT_SECRET,
                "authorize_url": "https://accounts.google.com/o/oauth2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
                "scope": "openid email profile",
            }
        
        # Добавляем GitHub только если есть учетные данные
        if self.GITHUB_CLIENT_ID and self.GITHUB_CLIENT_SECRET:
            providers["github"] = {
                "client_id": self.GITHUB_CLIENT_ID,
                "client_secret": self.GITHUB_CLIENT_SECRET,
                "authorize_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "userinfo_url": "https://api.github.com/user",
                "scope": "read:user user:email",
            }
        
        return providers

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()