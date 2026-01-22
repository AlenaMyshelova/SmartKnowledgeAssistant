"""
Common dependencies for FastAPI endpoints.

This module consolidates all reusable dependencies used across the application.
Import dependencies from here in your endpoints.
"""
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request
from typing import Optional, Dict, Any
import logging

from app.core.security import decode_access_token
from app.schemas.user import User
from app.services.auth_service import auth_service

logger = logging.getLogger(__name__)

# =============================================================================
# Auth Schemes
# =============================================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)
security = HTTPBearer(auto_error=False)


# =============================================================================
# User Dependencies
# =============================================================================

async def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    access_token: Optional[str] = Cookie(None)
) -> Optional[User]:
    """
    Возвращает текущего пользователя или None, если пользователь не аутентифицирован.
    Проверяет токен из нескольких источников (заголовок, cookie, query параметр).
    """
    jwt_token = None
    
    # 1. Из стандартного Authorization: Bearer xxx
    if token:
        jwt_token = token
    # 2. Из HTTP Bearer схемы
    elif credentials:
        jwt_token = credentials.credentials
    # 3. Из cookie
    elif access_token:
        jwt_token = access_token
    # 4. Из query параметра (для SSE, WebSocket и т.д.)
    else:
        jwt_token = request.query_params.get("token")
    
    if not jwt_token:
        return None
    
    token_data = decode_access_token(jwt_token)
    if not token_data:
        return None
    
    try:
        if hasattr(token_data, 'sub') and token_data.sub:
            user = await auth_service.get_user_by_id(int(token_data.sub))
        elif hasattr(token_data, 'email') and token_data.email:
            user = await auth_service.get_user_by_email(token_data.email)
        else:
            return None
        
        if not user or not user.is_active:
            return None
        
        return user
    except Exception as e:
        logger.error(f"Error getting user from token: {e}")
        return None


async def get_current_user(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """
    Возвращает текущего аутентифицированного пользователя.
    Выбрасывает 401 если пользователь не аутентифицирован.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Проверяет, что пользователь активен.
    Используется для эндпоинтов, требующих активного пользователя.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The account is inactive"
        )
    return current_user


async def get_token_data(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    access_token: Optional[str] = Cookie(None)
) -> Optional[Dict[str, Any]]:
    """
    Извлекает данные токена из разных источников.
    Возвращает словарь с данными или None.
    """
    jwt_token = None
    
    if token:
        jwt_token = token
    elif credentials:
        jwt_token = credentials.credentials
    elif access_token:
        jwt_token = access_token
    else:
        jwt_token = request.query_params.get("token")
    
    if not jwt_token:
        return None
    
    token_data = decode_access_token(jwt_token)
    if not token_data:
        return None
    
    return {
        "sub": token_data.sub,
        "email": token_data.email,
        "name": token_data.name,
        "is_active": token_data.is_active
    }
