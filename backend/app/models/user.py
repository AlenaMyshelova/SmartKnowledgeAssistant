from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: str
    is_active: bool = True
    avatar_url: Optional[str] = None  # Добавлено для аватара из OAuth

class UserCreate(UserBase):
    # Для OAuth аутентификации
    oauth_provider: str  # "google", "github"
    oauth_id: str  # ID пользователя у провайдера
    provider_data: Optional[Dict[str, Any]] = None  # Дополнительные данные от провайдера

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None  # Добавлено

class UserInDB(UserBase):
    id: int
    oauth_provider: str
    oauth_id: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        orm_mode = True  # Для совместимости с SQLAlchemy
        from_attributes = True  # Для Pydantic v2

class User(UserInDB):
    pass  # Наследуем все от UserInDB

class TokenData(BaseModel):
    sub: str  # ID пользователя
    exp: datetime  # Время истечения токена
    name: str  # Имя пользователя
    email: str  # Email пользователя
    is_active: bool = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int  # Unix timestamp
    user: UserBase

# Дополнительно для OAuth - информация о провайдере
class OAuthProvider(BaseModel):
    name: str  # Название провайдера (google, github)
    display_name: str  # Отображаемое название (Google, GitHub)
    icon: Optional[str] = None  # URL иконки (опционально)

class OAuthProvidersResponse(BaseModel):
    providers: List[OAuthProvider]