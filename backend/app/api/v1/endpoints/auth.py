from typing import Dict, Any, Optional
from datetime import timedelta, datetime
import secrets
import base64

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse

from app.database import db_manager  # Используем db_manager вместо SQLAlchemy
from app.auth.oauth import get_oauth_provider
from app.auth.jwt import create_access_token
from app.auth.deps import get_current_user
from app.models.user import User, UserCreate, Token
from app.core.config import settings
from app.auth.jwt import decode_access_token

router = APIRouter()

# Хранилище для состояний OAuth (в продакшене используйте Redis)
oauth_states = {}

@router.get("/login/{provider}")
async def login_oauth(provider: str, redirect_uri: Optional[str] = None):
    """
    Инициирует процесс аутентификации OAuth.
    """
    try:
        # Проверяем, поддерживается ли провайдер
        if provider not in settings.OAUTH_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Провайдер {provider} не поддерживается"
            )
        
        # Генерируем уникальный state для защиты от CSRF
        state = secrets.token_urlsafe(32)
        
        # Если передан redirect_uri, сохраняем его в state
        if redirect_uri:
            oauth_states[state] = {
                "provider": provider,
                "redirect_uri": redirect_uri
            }
        else:
            oauth_states[state] = {
                "provider": provider,
                "redirect_uri": f"{settings.FRONTEND_URL}/auth/callback"
            }
        
        # Получаем URL авторизации
        oauth_provider = get_oauth_provider(provider)
        auth_url = oauth_provider.get_authorization_url(
            redirect_uri=f"{settings.BACKEND_URL}/api/v1/auth/{provider}/callback",
            state=state
        )
        
        # Возвращаем URL для перенаправления (клиент сам выполнит редирект)
        return {"auth_url": auth_url, "state": state}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка авторизации: {str(e)}"
        )


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: Optional[str] = None,
):
    """
    Обработка callback от провайдера OAuth.
    """
    try:
        # Проверяем state и получаем сохраненные данные
        if not state or state not in oauth_states:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недействительный параметр state"
            )
        
        # Получаем данные state и удаляем запись
        state_data = oauth_states.pop(state)
        
        if state_data["provider"] != provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Несоответствие провайдера"
            )
        
        # Проверяем поддержку провайдера
        oauth_provider = get_oauth_provider(provider)
        
        # Обмен кода на токен
        access_token = await oauth_provider.exchange_code_for_token(
            code, 
            redirect_uri=f"{settings.BACKEND_URL}/api/v1/auth/{provider}/callback"
        )
        
        # Получение информации о пользователе
        user_info = await oauth_provider.get_user_info(access_token)
        
        # Поиск или создание пользователя
        existing_user = db_manager.get_user_by_oauth_id(provider, user_info["provider_id"])
        
        if existing_user:
            # Обновляем время последнего входа
            db_manager.update_last_login(existing_user.id)
            user = existing_user
        else:
            # Создаем нового пользователя
            user_data = UserCreate(
                email=user_info["email"],
                name=user_info["name"],
                avatar_url=user_info.get("avatar_url"),
                oauth_provider=provider,
                oauth_id=user_info["provider_id"],
                provider_data=user_info.get("provider_data")
            )
            user = db_manager.create_user(user_data)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось создать пользователя"
                )
        
        # Создаем JWT токен
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "name": user.name
        }
        jwt_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        # Получаем URL для перенаправления
        redirect_url = state_data.get("redirect_uri") or f"{settings.FRONTEND_URL}/auth/callback"
        redirect_url = f"{redirect_url}?token={jwt_token}"
        
        # Создаем ответ с перенаправлением
        response = RedirectResponse(redirect_url)
        
        # Устанавливаем токен в cookie для дополнительной безопасности
        response.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,
            secure=not settings.DEBUG,  # True в продакшене
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        # Перенаправляем на страницу входа с сообщением об ошибке
        error_url = f"{settings.FRONTEND_URL}/login?error={str(e)}"
        return RedirectResponse(error_url)


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Получение информации о текущем пользователе.
    """
    return current_user


@router.post("/logout")
async def logout(response: Response):
    """
    Выход пользователя из системы.
    """
    # Удаляем токен из cookie
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
    )
    
    return {"message": "Вы успешно вышли из системы"}

@router.post("/refresh-token")
async def refresh_token(request: Request, response: Response):
    """
    Обновляет JWT токен с использованием существующего токена
    """
    # Получаем текущий токен
    token = None
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # Проверяем cookie
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось найти токен"
        )
    
    # Декодируем текущий токен
    token_data = decode_access_token(token)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен недействителен или истек срок действия"
        )
    
    # Получаем пользователя
    user = db_manager.get_user_by_id(int(token_data.sub))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден"
        )
    
    # Создаем новый токен
    new_token_data = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name
    }
    new_token = create_access_token(
        data=new_token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Устанавливаем токен в cookie
    response.set_cookie(
        key="access_token",
        value=new_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_at": int((datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())
    }

@router.get("/providers")
async def get_oauth_providers():
    """
    Получение списка доступных OAuth провайдеров.
    """
    providers = []
    for provider_name, config in settings.OAUTH_PROVIDERS.items():
        if config.get("client_id"):  # Показываем только настроенные провайдеры
            providers.append({
                "name": provider_name,
                "display_name": provider_name.title()
            })
    
    return {"providers": providers}