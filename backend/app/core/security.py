"""
Security utilities: JWT tokens, password hashing, etc.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import time

from fastapi import HTTPException, status
from jose import jwt, JWTError
from app.core.config import settings
from app.schemas.user import TokenData


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decodes JWT token and returns user data.
    Returns None in case of error (for application logic).
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        if datetime.fromtimestamp(payload["exp"]) < datetime.utcnow():
            return None
        
        token_data = TokenData(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"]),
            name=payload["name"],
            email=payload["email"],
            is_active=payload.get("is_active", True)
        )
        
        return token_data
    
    except Exception:
        return None


def verify_token(token: str) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return {"user_id": user_id, "payload": payload}
    except JWTError:
        raise credentials_exception


def get_token_expiration_timestamp() -> int:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return int(time.mktime(expire.timetuple()))
