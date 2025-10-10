from fastapi import APIRouter

from app.api.v1.endpoints import chat, data_sources, system

# Главный роутер API v1
api_router = APIRouter()

# Подключаем роутеры с разными тегами для документации
api_router.include_router(system.router, tags=["system"])
api_router.include_router(chat.router, tags=["chat"])  
api_router.include_router(data_sources.router, tags=["data-sources"])