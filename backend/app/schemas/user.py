"""
Pydantic schemas for User models - API validation and serialization.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    name: str
    is_active: bool = True
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    oauth_provider: str  # "google", "github"
    oauth_id: str  # User's unique ID from the provider
    provider_data: Optional[Dict[str, Any]] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None


class UserInDB(UserBase):
    """Schema for user stored in database."""
    id: int
    oauth_provider: str
    oauth_id: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class User(UserInDB):
    """Full user schema for API responses."""
    pass


class TokenData(BaseModel):
    """Schema for JWT token payload data."""
    sub: str  # User ID
    exp: datetime  # Expiration time
    name: str
    email: str
    is_active: bool = True


class Token(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    token_type: str = "bearer"
    expires_at: int  # Unix timestamp
    user: UserBase


class OAuthProvider(BaseModel):
    """Schema for OAuth provider info."""
    name: str  # Provider name (google, github)
    display_name: str  # Display name (Google, GitHub)
    icon: Optional[str] = None


class OAuthProvidersResponse(BaseModel):
    """Schema for list of available OAuth providers."""
    providers: List[OAuthProvider]


def sqlalchemy_to_pydantic(db_user) -> User:
    """Convert SQLAlchemy User model to Pydantic User schema."""
    return User(
        id=db_user.id,
        email=db_user.email,
        name=db_user.name,
        avatar_url=db_user.avatar_url,
        oauth_provider=db_user.oauth_provider,
        oauth_id=db_user.oauth_id,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        last_login=db_user.last_login
    )
