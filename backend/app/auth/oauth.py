from typing import Dict, Any, Optional, List
import httpx
from urllib.parse import urlencode
from fastapi import HTTPException
from app.core.config import settings
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

class OAuthProvider:
    """Базовый класс для OAuth провайдеров"""
    
    def __init__(self, provider_config: Dict[str, Any]):
        self.config = provider_config
        self.client_id = provider_config.get("client_id")
        self.client_secret = provider_config.get("client_secret")
        self.name = "generic"  # Будет переопределено в подклассах
    
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Формирование URL для авторизации"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.config.get("scope"),
            "response_type": "code",
            "state": state,
        }
        
        return f"{self.config['authorize_url']}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Обмен авторизационного кода на access token"""
        async with httpx.AsyncClient() as client:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            
            headers = {"Accept": "application/json"}
            
            try:
                response = await client.post(
                    self.config["token_url"],
                    data=data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"OAuth token exchange failed for {self.name}: {response.text}")
                    raise HTTPException(status_code=400, detail=f"Failed to exchange code for token: {response.status_code}")
                
                token_data = response.json()
                return token_data.get("access_token")
            
            except httpx.RequestError as e:
                logger.error(f"OAuth token exchange request failed: {e}")
                raise HTTPException(status_code=500, detail="Failed to connect to OAuth provider")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Получение информации о пользователе"""
        raise NotImplementedError

class GoogleOAuth(OAuthProvider):
    """Google OAuth провайдер"""
    
    def __init__(self, provider_config: Dict[str, Any]):
        super().__init__(provider_config)
        self.name = "google"
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Получение информации о пользователе от Google"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.config["userinfo_url"],
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to get user info from Google: {response.text}")
                    raise HTTPException(status_code=400, detail="Failed to get user info from Google")
                
                user_data = response.json()
                
                return {
                    "provider_id": str(user_data.get("sub")),
                    "email": user_data.get("email"),
                    "name": user_data.get("name", user_data.get("email", "").split("@")[0]),
                    "avatar_url": user_data.get("picture"),
                    "provider": "google",
                    "provider_data": user_data
                }
            
            except httpx.RequestError as e:
                logger.error(f"Request to Google failed: {e}")
                raise HTTPException(status_code=500, detail="Failed to connect to Google")

class GitHubOAuth(OAuthProvider):
    """GitHub OAuth провайдер"""
    
    def __init__(self, provider_config: Dict[str, Any]):
        super().__init__(provider_config)
        self.name = "github"
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Получение информации о пользователе от GitHub"""
        async with httpx.AsyncClient() as client:
            try:
                # Получаем основную информацию о пользователе
                user_response = await client.get(
                    self.config["userinfo_url"],
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if user_response.status_code != 200:
                    logger.error(f"Failed to get user info from GitHub: {user_response.text}")
                    raise HTTPException(status_code=400, detail="Failed to get user info from GitHub")
                
                user_data = user_response.json()
                
                # Получаем email (может быть приватным)
                email = user_data.get("email")
                
                if not email:
                    email_response = await client.get(
                        "https://api.github.com/user/emails",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    
                    if email_response.status_code == 200:
                        emails = email_response.json()
                        for email_info in emails:
                            if email_info.get("verified") and email_info.get("primary"):
                                email = email_info.get("email")
                                break
                        if not email and emails:
                            # Если нет подтвержденного основного, берем первый
                            email = emails[0].get("email")
                
                return {
                    "provider_id": str(user_data.get("id")),
                    "email": email or f"{user_data.get('login')}@github.example.com",
                    "name": user_data.get("name") or user_data.get("login"),
                    "avatar_url": user_data.get("avatar_url"),
                    "provider": "github",
                    "provider_data": user_data
                }
            
            except httpx.RequestError as e:
                logger.error(f"Request to GitHub failed: {e}")
                raise HTTPException(status_code=500, detail="Failed to connect to GitHub")

# Добавьте другие провайдеры здесь при необходимости

def get_available_providers() -> List[Dict[str, str]]:
    """
    Получение списка настроенных провайдеров OAuth
    """
    providers = []
    for name, config in settings.OAUTH_PROVIDERS.items():
        if config.get("client_id") and config.get("client_secret"):
            providers.append({
                "name": name,
                "display_name": name.capitalize()
            })
    return providers

def get_oauth_provider(provider_name: str) -> OAuthProvider:
    """Получение OAuth провайдера по названию"""
    if provider_name not in settings.OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported OAuth provider: {provider_name}")
    
    provider_config = settings.OAUTH_PROVIDERS[provider_name]
    
    if not provider_config.get("client_id") or not provider_config.get("client_secret"):
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} is not properly configured")
    
    if provider_name == "google":
        return GoogleOAuth(provider_config)
    elif provider_name == "github":
        return GitHubOAuth(provider_config)
    else:
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} not implemented")