from __future__ import annotations
from typing import Optional, Annotated
from datetime import timedelta, datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, status
from fastapi.responses import RedirectResponse
from app.services.auth_service import auth_service 
from app.core.config import settings
from app.dependencies import get_current_user
from app.core.security import create_access_token, decode_access_token
from app.auth.oauth import get_oauth_provider
from app.schemas.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["auth"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Not authenticated"},
    },
)

CurrentUser = Annotated[User, Depends(get_current_user)]

OAUTH_TMP_COOKIE_MAX_AGE = 300  # 5 minutes


def _set_tmp_cookie(response: Response, key: str, value: str) -> None:
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        # secure=not settings.DEBUG,
        secure=False, 
        samesite="lax",   
        max_age=OAUTH_TMP_COOKIE_MAX_AGE,
        path="/", 
        domain=None
    )


def _del_tmp_cookie(response: Response, key: str) -> None:
    response.delete_cookie(
        key=key,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
    )
@router.get("/test")
def auth_test(current_user: CurrentUser):
    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "is_active": current_user.is_active,
        },
        "message": "Authentication successful",
    }

@router.get("/login/{provider}")
async def login_oauth(
    provider: str,
    response: Response,
    redirect_uri: Optional[str] = None,
):
    """Initiate OAuth login with direct redirect."""
    
    if provider not in settings.OAUTH_PROVIDERS:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=Unknown%20provider"
        )

    provider_cfg = settings.OAUTH_PROVIDERS[provider]
    provider_redirect_uri = provider_cfg["redirect_uri"]

    # Generate a random state parameter for CSRF protection
    state = secrets.token_urlsafe(32)
    oauth_provider = get_oauth_provider(provider)
    auth_url = oauth_provider.get_authorization_url(
        redirect_uri=provider_redirect_uri,
        state=state,
    )
    
    resp = RedirectResponse(url=auth_url)
    _set_tmp_cookie(resp, "oauth_state", state)
    final_redirect = redirect_uri or f"{settings.FRONTEND_URL}/auth/callback"
    _set_tmp_cookie(resp, "oauth_redirect", final_redirect)
    return resp 


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    response: Response,
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
):
    
    logger.info(f"[OAUTH CALLBACK] Provider: {provider}")
    logger.info(f"[OAUTH CALLBACK] Code present: {bool(code)}")
    logger.info(f"[OAUTH CALLBACK] State present: {bool(state)}")
    logger.info(f"[OAUTH CALLBACK] Error: {error}")
    logger.info(f"[OAUTH CALLBACK] Cookies: {request.cookies}")
    
    if error:
        logger.warning(f"OAuth error from {provider}: {error}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={error}"
        )
    
    if not code or not state:
        error_msg = "Missing code or state parameter"
        logger.error(f"[OAUTH CALLBACK ERROR] {error_msg}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={error_msg}"
        )
    
    try:
        if provider not in settings.OAUTH_PROVIDERS:
            raise HTTPException(status_code=400, detail=" Unknown OAuth provider")

        cookie_state = request.cookies.get("oauth_state")
        logger.info(f"[OAUTH CALLBACK] Cookie state: {cookie_state[:10] + '...' if cookie_state else 'None'}")
        logger.info(f"[OAUTH CALLBACK] State match: {state == cookie_state}")
        
        if not state or not cookie_state or state != cookie_state:
            logger.error(f"[OAUTH CALLBACK ERROR] State mismatch!")
            logger.error(f"[OAUTH CALLBACK ERROR] Expected: {cookie_state}")
            logger.error(f"[OAUTH CALLBACK ERROR] Received: {state}")
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        frontend_redirect = request.cookies.get("oauth_redirect") or f"{settings.FRONTEND_URL}/auth/callback"

        provider_cfg = settings.OAUTH_PROVIDERS[provider]
        provider_redirect_uri = provider_cfg["redirect_uri"]

        oauth_provider = get_oauth_provider(provider)
        logger.info(f"[OAUTH CALLBACK] Starting token exchange...")
        logger.info(f"[OAUTH CALLBACK] Code: {code[:20]}...")
        logger.info(f"[OAUTH CALLBACK] Provider redirect URI: {provider_redirect_uri}")
       
        access_token = await oauth_provider.exchange_code_for_token(
            code,
            redirect_uri=provider_redirect_uri,
        )

        user_info = await oauth_provider.get_user_info(access_token)
        provider_id = user_info.get("provider_id")
        email = user_info.get("email")
        name = user_info.get("name")

        if not provider_id or not email:
            raise HTTPException(status_code=400, detail="Invalid user data from provider")

        user = await auth_service.get_or_create_oauth_user(
        provider=provider,
        provider_id=provider_id,
        email=email,
        name=name,
        avatar_url=user_info.get("avatar_url")
        )

        if not user:
            raise HTTPException(status_code=500, detail="Error creating or retrieving user")  

        # Generate access JWT (short-lived)
        payload = {"sub": str(user.id), "email": user.email, "name": user.name}
        jwt_token = create_access_token(
            data=payload,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        
        logger.info(f"[AUTH] User {user.email} authenticated successfully")
        logger.info(f"[AUTH] Redirecting to: {frontend_redirect}")
        
        # Redirect to frontend with JWT in httpOnly cookie
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

        _del_tmp_cookie(resp, "oauth_state")
        _del_tmp_cookie(resp, "oauth_redirect")

        return resp

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"[AUTH ERROR] OAuth callback failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        error_msg = "Authentication failed. Please try again."
        error_url = f"{settings.FRONTEND_URL}/login?error={error_msg}"
        return RedirectResponse(error_url)


@router.get("/me")
async def read_users_me(current_user: CurrentUser):
    """
    returns the current authenticated user.
    """
    return current_user


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
    )
    return {"message": "Successfully logged out"}


@router.post("/refresh-token")
async def refresh_token(request: Request, response: Response):
    """
    Refreshes the access JWT (using the current token).
    In production, a separate refresh token (httpOnly cookie) and rotation are recommended.
    """
    token: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Failed to find token")

    token_data = decode_access_token(token)
    if not token_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await auth_service.get_user_by_id(int(token_data.sub))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

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
    providers = []
    for name, cfg in settings.OAUTH_PROVIDERS.items():
        if cfg.get("client_id"):
            providers.append({"name": name, "display_name": name.title()})
    return {"providers": providers}