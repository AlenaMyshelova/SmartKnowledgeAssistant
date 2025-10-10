from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Импортируем наши настройки и роутер
from app.core.config import settings
from app.api.v1.api import api_router

# Загружаем переменные из .env файла
load_dotenv()

# Создаем приложение FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,           # Название в документации
    version=settings.VERSION,              # Версия API
    openapi_url=f"{settings.API_V1_STR}/openapi.json",  # URL для OpenAPI схемы
    docs_url="/docs",                      # URL для Swagger UI
    redoc_url="/redoc"                     # URL для ReDoc
)

# Настройка CORS (Cross-Origin Resource Sharing)
# Позволяет React приложению обращаться к нашему API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # Список разрешенных доменов
    allow_credentials=True,
    allow_methods=["*"],    # Разрешить все HTTP методы (GET, POST, etc.)
    allow_headers=["*"],    # Разрешить все заголовки
)

# Подключаем наш роутер с префиксом /api/v1
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    """
    Корневой эндпоинт - приветственное сообщение.
    
    GET /
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",  # Ссылка на автодокументацию
        "health_check": f"{settings.API_V1_STR}/health"
    }

# Запуск сервера (если файл запускается напрямую)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)