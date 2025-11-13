from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request
from typing import Optional, Dict, Any, Union
import logging
from app.services.auth_service import auth_service 
from app.auth.jwt import decode_access_token, verify_token
from app.models.user import User, TokenData

logger = logging.getLogger(__name__)
# Schema OAuth2 for obtaining token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

# Schema Bearer for alternative token retrieval
security = HTTPBearer(auto_error=False)

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
    # Определяем токен из разных источников
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
    
    # Если нет токена, возвращаем None
    if not jwt_token:
        return None
    
    # Декодируем токен
    token_data = decode_access_token(jwt_token)
    if not token_data:
        return None
    
    # Получаем пользователя из базы данных
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
    Зависимость для получения текущего аутентифицированного пользователя.
    Выбрасывает исключение, если пользователь не аутентифицирован.
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
    Извлекает данные из токена без проверки пользователя в БД.
    Полезно для проверки прав доступа или получения метаданных из токена.
    """
    # Определяем токен из разных источников
    jwt_token = token or (credentials.credentials if credentials else None) or access_token or request.query_params.get("token")
    
    if not jwt_token:
        return None
    
    try:
        # Используем verify_token, который возвращает словарь с данными
        token_info = verify_token(jwt_token)
        return token_info
    except HTTPException:
        return None