from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import re

from app.auth.jwt import decode_access_token
from app.core.config import settings

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки JWT токенов в защищенных маршрутах.
    """
    
    def __init__(self, app):
        super().__init__(app)
        # Пути, которые не требуют аутентификации
        self.public_paths = [
            r"^/$",  # Root
            r"^/docs.*$",  # Swagger docs
            r"^/redoc.*$",  # ReDoc
            r"^/openapi\.json$",  # OpenAPI schema
            r"^/api/v1/openapi\.json$",  
            r"^/static/.*$",  # Static files
            r"^/api/v1/auth/.*$",  # All auth endpoints
            r"^/api/v1/system/health$",  # Health check
            # Можете добавить другие публичные пути
        ]
        # Компилируем регулярные выражения
        self.compiled_patterns = [re.compile(pattern) for pattern in self.public_paths]
    
    async def dispatch(self, request: Request, call_next):
        """Метод dispatch вместо __call__ для BaseHTTPMiddleware"""
        path = request.url.path
        
        # Проверяем, является ли путь публичным
        if self._is_public_path(path):
            return await call_next(request)
        
        # Получаем токен
        token = self._get_token_from_request(request)
        
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Проверяем токен
        token_data = decode_access_token(token)
        if not token_data:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Добавляем информацию о пользователе в request
        request.state.user_id = token_data.sub
        if hasattr(token_data, 'email'):
            request.state.user_email = token_data.email
        if hasattr(token_data, 'name'):
            request.state.user_name = token_data.name
        
        return await call_next(request)
    
    def _is_public_path(self, path: str) -> bool:
        """Проверяет, является ли путь публичным"""
        return any(pattern.match(path) for pattern in self.compiled_patterns)
    
    def _get_token_from_request(self, request: Request) -> str:
        """Извлекает токен из запроса"""
        # 1. Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.replace("Bearer ", "")
        
        # 2. Cookie
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            return cookie_token
        
        # 3. Query parameter
        query_token = request.query_params.get("token")
        if query_token:
            return query_token
        
        return None