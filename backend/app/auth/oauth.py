from __future__ import annotations

from typing import Dict, Any, Optional, List
import logging
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app.core.config import settings

# Настройка логирования
logger = logging.getLogger(__name__)

# Общий таймаут для HTTP-запросов к OAuth-провайдерам
HTTP_TIMEOUT = 15.0


class OAuthProvider:
    """Базовый класс для OAuth провайдеров."""

    def __init__(self, provider_config: Dict[str, Any]):
        self.config = provider_config
        self.client_id = provider_config.get("client_id")
        self.client_secret = provider_config.get("client_secret")
        self.name = "generic"  # Переопределяется в подклассах

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Формирование URL для авторизации.
        extra_params — для access_type=offline, prompt=consent, code_challenge и т.д.
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.config.get("scope"),
            "response_type": "code",
            "state": state,
        }
        if extra_params:
            params.update(extra_params)

        # urlencode по умолчанию кодирует пробел как '+', что приемлемо для OAuth
        return f"{self.config['authorize_url']}?{urlencode(params)}"

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
    ) -> str:
        """Exchange authorization code for access token."""
        print(f"[OAUTH] Exchanging code for token")
        print(f"[OAUTH] Provider: {self.name}")
        print(f"[OAUTH] Redirect URI: {redirect_uri}")
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        
        if code_verifier:
            data["code_verifier"] = code_verifier

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            try:
                resp = await client.post(
                    self.config["token_url"], 
                    data=data, 
                    headers=headers
                )
                print(f"[OAUTH] Token exchange response status: {resp.status_code}")
                
                if resp.status_code != 200:
                    print(f"[OAUTH ERROR] Token exchange failed")
                    print(f"[OAUTH ERROR] Response: {resp.text}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to exchange code for token: {resp.text}"
                    )
                    
            except httpx.RequestError as e:
                print(f"[OAUTH ERROR] Request failed: {e}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to connect to {self.name}"
                )

        token_data = resp.json()
        print(f"[OAUTH] Token data keys: {list(token_data.keys())}")
        
        access_token = token_data.get("access_token")
        if not access_token:
            print(f"[OAUTH ERROR] No access token in response")
            raise HTTPException(
                status_code=400,
                detail="No access token received"
            )
        
        print(f"[OAUTH] Successfully got access token")
        return access_token

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Получение информации о пользователе — реализуется в подклассах."""
        raise NotImplementedError


class GoogleOAuth(OAuthProvider):
    """Google OAuth провайдер."""

    def __init__(self, provider_config: Dict[str, Any]):
        super().__init__(provider_config)
        self.name = "google"

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Формирование URL для авторизации Google с параметром выбора аккаунта.
        """
        # Добавляем параметры специфичные для Google
        google_params = {
            "access_type": "offline",  # Для получения refresh token
            "prompt": "select_account",  # ВАЖНО: Всегда показывать страницу выбора аккаунта
            "include_granted_scopes": "true",  # Включить все разрешенные scope
        }
        
        # Если переданы дополнительные параметры, добавляем их
        if extra_params:
            google_params.update(extra_params)
            
        # Вызываем родительский метод с параметрами Google
        return super().get_authorization_url(redirect_uri, state, google_params)

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Получение информации о пользователе от Google.
        Используем v3 userinfo endpoint (OIDC совместимый).
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            try:
                resp = await client.get(self.config["userinfo_url"], headers=headers)
            except httpx.RequestError as e:
                logger.error("Request to Google failed: %s", e)
                raise HTTPException(status_code=502, detail="Failed to connect to Google")

        if resp.status_code != 200:
            logger.error("Failed to get user info from Google: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")

        user_data = resp.json()
        return {
            "provider_id": str(user_data.get("sub")),
            "email": user_data.get("email"),
            "name": user_data.get("name") or (user_data.get("email", "").split("@")[0]),
            "avatar_url": user_data.get("picture"),
            "provider": "google",
            "provider_data": user_data,
        }
class GitHubOAuth(OAuthProvider):
    """GitHub OAuth провайдер."""

    def __init__(self, provider_config: Dict[str, Any]):
        super().__init__(provider_config)
        self.name = "github"

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Получение информации о пользователе от GitHub.
        GitHub может не возвращать email в /user, поэтому дополнительно дергаем /user/emails.
        """
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            # Основной профиль
            try:
                user_resp = await client.get(self.config["userinfo_url"], headers=headers)
            except httpx.RequestError as e:
                logger.error("Request to GitHub (userinfo) failed: %s", e)
                raise HTTPException(status_code=502, detail="Failed to connect to GitHub")

            if user_resp.status_code != 200:
                logger.error("Failed to get user info from GitHub: %s %s", user_resp.status_code, user_resp.text)
                raise HTTPException(status_code=400, detail="Failed to get user info from GitHub")

            user_data = user_resp.json()
            email = user_data.get("email")

            # Email может быть приватным — берём из /user/emails
            if not email:
                try:
                    emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
                except httpx.RequestError as e:
                    logger.error("Request to GitHub (emails) failed: %s", e)
                    raise HTTPException(status_code=502, detail="Failed to connect to GitHub")

                if emails_resp.status_code == 200:
                    emails = emails_resp.json()
                    # Пытаемся найти primary verified
                    primary_verified = next(
                        (e for e in emails if e.get("primary") and e.get("verified")),
                        None,
                    )
                    if primary_verified:
                        email = primary_verified.get("email")
                    elif emails:
                        # Фоллбек — первый доступный
                        email = emails[0].get("email")

            return {
                "provider_id": str(user_data.get("id")),
                "email": email or f"{user_data.get('login')}@github.example.com",
                "name": user_data.get("name") or user_data.get("login"),
                "avatar_url": user_data.get("avatar_url"),
                "provider": "github",
                "provider_data": user_data,
            }


# ---- Реестр/фабрика провайдеров ----

def get_available_providers() -> List[Dict[str, str]]:
    """
    Возвращает список провайдеров, которые корректно сконфигурированы
    (есть client_id и client_secret).
    """
    providers: List[Dict[str, str]] = []
    for name, cfg in settings.OAUTH_PROVIDERS.items():
        if cfg.get("client_id") and cfg.get("client_secret"):
            providers.append({"name": name, "display_name": name.capitalize()})
    return providers


def get_oauth_provider(provider_name: str) -> OAuthProvider:
    """Фабрика: возвращает инстанс конкретного провайдера."""
    if provider_name not in settings.OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported OAuth provider: {provider_name}")

    provider_config = settings.OAUTH_PROVIDERS[provider_name]
    if not provider_config.get("client_id") or not provider_config.get("client_secret"):
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} is not properly configured")

    if provider_name == "google":
        return GoogleOAuth(provider_config)
    if provider_name == "github":
        return GitHubOAuth(provider_config)

    raise HTTPException(status_code=400, detail=f"Provider {provider_name} not implemented")
