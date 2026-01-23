from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import re

from app.core.security import decode_access_token
from app.core.config import settings

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for checking JWT tokens on protected routes.
    """
    
    def __init__(self, app):
        super().__init__(app)

        self.public_paths = [
            r"^/$",
            r"^/docs.*$", 
            r"^/redoc.*$",
            r"^/openapi\.json$",
            r"^/api/v1/openapi\.json$",
            r"^/static/.*$",
            
            r"^/favicon\.ico$",
            r"^/robots\.txt$",
            r"^/\.well-known/.*$",
            # Health check endpoints
            r"^/health$",
            r"^/api/v1/health$",
            r"^/api/v1/system/health$",
            
            # Auth endpoints
            r"^/api/v1/auth/.*$",
            r"^/api/v1/login/.*$",     
            r"^/api/v1/providers$",   
            r"^/api/v1/auth/google/callback.*$", 

            # temporary public endpoints for testing
            r"^/api/v1/data-sources$",

            r"^/api/v1/speech/.*$",
        ]
   
        self.compiled_patterns = [re.compile(pattern) for pattern in self.public_paths]
    
    async def dispatch(self, request: Request, call_next):
        """ Dispatch method instead of __call__ for BaseHTTPMiddleware """
        path = request.url.path
        
        if settings.DEBUG:
            print(f" Auth middleware checking: {request.method} {path}")
        
        if request.method == "OPTIONS":
            if settings.DEBUG:
                print(f"CORS preflight request: {path}")
            return await call_next(request)
        
        if self._is_public_path(path):
            if settings.DEBUG:
                print(f"Public path allowed: {path}")
            return await call_next(request)
        
        token = self._get_token_from_request(request)
        
        if not token:
            if settings.DEBUG:
                print(f" No token for protected path: {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer", "Access-Control-Allow-Origin": "*"},
            )
        
        token_data = decode_access_token(token)
        if not token_data:
            if settings.DEBUG:
                print(f"Invalid token for path: {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer", "Access-Control-Allow-Origin": "*"},
            )
        
        if settings.DEBUG:
            print(f"Auth successful: {path} (User: {token_data.sub})")
        
      # Add user info to request state for downstream use
        request.state.user_id = token_data.sub
        if hasattr(token_data, 'email'):
            request.state.user_email = token_data.email
        if hasattr(token_data, 'name'):
            request.state.user_name = token_data.name
        
        return await call_next(request)
    
    def _is_public_path(self, path: str) -> bool:
        return any(pattern.match(path) for pattern in self.compiled_patterns)
    
    def _get_token_from_request(self, request: Request) -> str:
        """Extracts token from the request"""

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.replace("Bearer ", "")
        
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            return cookie_token
        
        query_token = request.query_params.get("token")
        if query_token:
            return query_token
        
        return None