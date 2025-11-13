from typing import Optional
import logging
from datetime import datetime

from app.database import db_manager
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    """
    Authentication and user management service.
    """
    
    def __init__(self):
        self.db = db_manager
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        try:
            user = self.db.get_user_by_id(user_id)
            if user:
                logger.debug(f"User {user_id} found")
            else:
                logger.warning(f"User {user_id} not found")
            return user
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        try:
            user = self.db.get_user_by_email(email)
            if user:
                logger.debug(f"User found by email: {email}")
            else:
                logger.warning(f"User not found by email: {email}")
            return user
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    async def get_user_by_oauth_id(
        self,
        provider: str,
        provider_id: str
    ) -> Optional[User]:
        """Get user by OAuth provider and ID."""
        try:
            return self.db.get_user_by_oauth_id(provider, provider_id)
        except Exception as e:
            logger.error(f"Error getting OAuth user: {e}")
            return None
    
    async def create_user(
        self,
        email: str,
        name: str,
        oauth_provider: str,
        oauth_id: str,
        avatar_url: Optional[str] = None
    ) -> Optional[User]:
        """Create new user."""
        try:
            user_data = {
                "email": email,
                "name": name,
                "avatar_url": avatar_url,
                "oauth_provider": oauth_provider,
                "oauth_id": oauth_id,
            }
            
            user = self.db.create_user(user_data)
            logger.info(f"Created new user: {email} (ID: {user.id})")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user {email}: {e}")
            return None
    
    async def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp."""
        try:
            success = self.db.update_last_login(user_id)
            if success:
                logger.debug(f"Updated last login for user {user_id}")
            return success
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}")
            return False
    
    async def get_or_create_oauth_user(
        self,
        provider: str,
        provider_id: str,
        email: str,
        name: str,
        avatar_url: Optional[str] = None
    ) -> Optional[User]:
        """
        Get existing OAuth user or create new one.
        Encapsulates the full OAuth user creation flow.
        """
        try:
            # Try to find existing user
            existing_user = await self.get_user_by_oauth_id(provider, provider_id)
            
            if existing_user:
                # Update last login
                await self.update_last_login(existing_user.id)
                logger.info(f"OAuth login: {email} (existing user {existing_user.id})")
                return existing_user
            
            # Create new user
            new_user = await self.create_user(
                email=email,
                name=name,
                oauth_provider=provider,
                oauth_id=provider_id,
                avatar_url=avatar_url
            )
            
            if new_user:
                logger.info(f"OAuth login: {email} (new user {new_user.id} created)")
            
            return new_user
            
        except Exception as e:
            logger.error(f"Error in get_or_create_oauth_user: {e}")
            return None


# Singleton instance
auth_service = AuthService()