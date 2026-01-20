from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any, List
from functools import cached_property

class Settings(BaseSettings):
    # Pydantic settings v2
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # App info
    PROJECT_NAME: str = "Smart Knowledge Assistant API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Data
    DATABASE_URL: str = "sqlite:///./data/assistant.db"
    COMPANY_FAQS_PATH: Optional[str] = None  # direct path to company FAQs file

    # JWT / Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60          
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30           

    # OAuth creds
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None

    # URLs
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"

    # Debug
    DEBUG: bool = True

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @cached_property
    def GOOGLE_REDIRECT_URI(self) -> str:
        return f"{self.BACKEND_URL}{self.API_V1_STR}/auth/google/callback"

    @cached_property
    def GITHUB_REDIRECT_URI(self) -> str:
        return f"{self.BACKEND_URL}{self.API_V1_STR}/auth/github/callback"

    @property
    def OAUTH_PROVIDERS(self) -> Dict[str, Dict[str, Any]]:
        providers: Dict[str, Dict[str, Any]] = {}

        if self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET:
            providers["google"] = {
                "client_id": self.GOOGLE_CLIENT_ID,
                "client_secret": self.GOOGLE_CLIENT_SECRET,
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
                "scope": "openid email profile",
                "redirect_uri": self.GOOGLE_REDIRECT_URI,
            }

        if self.GITHUB_CLIENT_ID and self.GITHUB_CLIENT_SECRET:
            providers["github"] = {
                "client_id": self.GITHUB_CLIENT_ID,
                "client_secret": self.GITHUB_CLIENT_SECRET,
                "authorize_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "userinfo_url": "https://api.github.com/user",
                "scope": "read:user user:email",
                "redirect_uri": self.GITHUB_REDIRECT_URI,
            }

        return providers
    

settings = Settings()