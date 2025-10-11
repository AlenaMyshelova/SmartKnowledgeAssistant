from __future__ import annotations

from typing import Optional
from datetime import timedelta, datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.database import db_manager
from app.auth.deps import get_current_user
from app.auth.jwt import create_access_token, decode_access_token
from app.auth.oauth import get_oauth_provider
from app.models.user import User, UserCreate

router = APIRouter(tags=["auth"]) 

# Временные cookie-параметры для OAuth (state/redirect_uri)
OAUTH_TMP_COOKIE_MAX_AGE = 300  # 5 minutes


def _set_tmp_cookie(response: Response, key: str, value: str) -> None:
    """Устанавливает временную httpOnly-cookie для промежуточных шагов OAuth."""
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=OAUTH_TMP_COOKIE_MAX_AGE,
    )


def _del_tmp_cookie(response: Response, key: str) -> None:
    """Удаляет временную httpOnly-cookie."""
    response.delete_cookie(
        key=key,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
    )


@router.get("/login/{provider}")
async def login_oauth(
    provider: str,
    response: Response,
    redirect_uri: Optional[str] = None,
):
    """
    Инициализация OAuth-авторизации:
    - Проверяем, что провайдер настроен.
    - Генерируем state и сохраняем в httpOnly cookie.
    - Сохраняем желаемый redirect фронта в cookie.
    - Возвращаем URL авторизации (клиент делает redirect сам).
    """
    if provider not in settings.OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail="Провайдер не поддерживается")

    provider_cfg = settings.OAUTH_PROVIDERS[provider]
    provider_redirect_uri = provider_cfg["redirect_uri"]

    # 1) state в cookie
    state = secrets.token_urlsafe(32)
    _set_tmp_cookie(response, "oauth_state", state)

    # 2) конечный адрес возврата на фронт (куда редиректить после успешного входа)
    final_redirect = redirect_uri or f"{settings.FRONTEND_URL}/auth/callback"
    _set_tmp_cookie(response, "oauth_redirect", final_redirect)

    # 3) URL авторизации у провайдера
    oauth_provider = get_oauth_provider(provider)
    auth_url = oauth_provider.get_authorization_url(
        redirect_uri=provider_redirect_uri,
        state=state,
    )

    # Возвращаем JSON (фронтенд сам сделает window.location = auth_url)
    return {"auth_url": auth_url, "state": state}


@router.get("/{provider}/callback")
async def oauth_callback(
    request: Request,
    provider: str,
    code: str,
    state: Optional[str] = None,
):
    """
    Callback от провайдера:
    - Валидируем state (сверяем с cookie).
    - Обмениваем code на access_token у провайдера.
    - Получаем userinfo у провайдера.
    - Ищем/создаём пользователя в локальной БД.
    - Генерируем наш access JWT, кладём в httpOnly cookie и редиректим на фронт.
    """
    try:
        if provider not in settings.OAUTH_PROVIDERS:
            raise HTTPException(status_code=400, detail="Провайдер не поддерживается")

        cookie_state = request.cookies.get("oauth_state")
        if not state or not cookie_state or state != cookie_state:
            raise HTTPException(status_code=400, detail="Недействительный параметр state")

        frontend_redirect = request.cookies.get("oauth_redirect") or f"{settings.FRONTEND_URL}/auth/callback"

        provider_cfg = settings.OAUTH_PROVIDERS[provider]
        provider_redirect_uri = provider_cfg["redirect_uri"]

        oauth_provider = get_oauth_provider(provider)

        # Обмен кода на токен у провайдера
        access_token = await oauth_provider.exchange_code_for_token(
            code,
            redirect_uri=provider_redirect_uri,
        )

        # Получение профиля пользователя от провайдера
        user_info = await oauth_provider.get_user_info(access_token)
        # Ожидаемые ключи: provider_id, email, name, avatar_url?, provider_data?
        provider_id = user_info.get("provider_id")
        email = user_info.get("email")
        name = user_info.get("name")

        if not provider_id or not email:
            raise HTTPException(status_code=400, detail="Некорректные данные пользователя от провайдера")

        # Upsert пользователя
        existing_user = db_manager.get_user_by_oauth_id(provider, provider_id)
        if existing_user:
            db_manager.update_last_login(existing_user.id)
            user = existing_user
        else:
            user_data = UserCreate(
                email=email,
                name=name,
                avatar_url=user_info.get("avatar_url"),
                oauth_provider=provider,
                oauth_id=provider_id,
                provider_data=user_info.get("provider_data"),
            )
            user = db_manager.create_user(user_data)
            if not user:
                raise HTTPException(status_code=500, detail="Не удалось создать пользователя")

        # Генерируем наш access JWT (короткоживущий)
        payload = {"sub": str(user.id), "email": user.email, "name": user.name}
        jwt_token = create_access_token(
            data=payload,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        # Редиректим на фронт + ставим JWT в httpOnly cookie
        redirect_url = f"{frontend_redirect}?token={jwt_token}"
        resp = RedirectResponse(redirect_url)
        resp.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        # Чистим временные куки
        _del_tmp_cookie(resp, "oauth_state")
        _del_tmp_cookie(resp, "oauth_redirect")

        return resp

    except HTTPException:
        raise
    except Exception as e:
        # На фронт со смысловой ошибкой
        error_url = f"{settings.FRONTEND_URL}/login?error={str(e)}"
        return RedirectResponse(error_url)


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Возвращает данные текущего пользователя (по access JWT).
    """
    return current_user


@router.post("/logout")
async def logout(response: Response):
    """
    Выход: удаляем httpOnly-cookie с access JWT.
    """
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
    Обновляет access JWT (на текущем токене).
    В продакшене рекомендуется отдельный refresh-токен (httpOnly cookie) и ротация.
    """
    token: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Не удалось найти токен")

    token_data = decode_access_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Токен недействителен или истек срок действия")

    user = db_manager.get_user_by_id(int(token_data.sub))
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    new_payload = {"sub": str(user.id), "email": user.email, "name": user.name}
    new_token = create_access_token(
        data=new_payload,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    response.set_cookie(
        key="access_token",
        value=new_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_at": int((datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
    }


@router.get("/providers")
async def get_oauth_providers():
    """
    Возвращает список доступных и настроенных OAuth-провайдеров.
    """
    providers = []
    for name, cfg in settings.OAUTH_PROVIDERS.items():
        if cfg.get("client_id"):
            providers.append({"name": name, "display_name": name.title()})
    return {"providers": providers}