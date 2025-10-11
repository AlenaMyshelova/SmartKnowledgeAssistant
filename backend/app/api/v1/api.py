from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, data_sources, system

# Главный роутер API v1
api_router = APIRouter()

# Подключаем роутеры с разными тегами для документации
api_router.include_router(system.router, tags=["system"])
api_router.include_router(chat.router, tags=["chat"])  
api_router.include_router(data_sources.router, tags=["data-sources"])
api_router.include_router(auth.router, prefix="/auth")

@api_router.get("/login/{provider}")
async def redirect_login(provider: str):
    return RedirectResponse(f"/api/v1/auth/login/{provider}", status_code=307)

@api_router.get("/providers")
async def redirect_providers():
    return RedirectResponse("/api/v1/auth/providers", status_code=307)