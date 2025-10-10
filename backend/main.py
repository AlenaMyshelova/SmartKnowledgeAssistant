from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.vector_search import vector_search
from app.data_manager import DataManager

data_manager = DataManager()
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

@app.on_event("startup")
async def startup_event():
    # Проверяем наличие индекса FAQ
    print("Checking vector search indices...")
    
    # Убедимся, что индекс FAQ создан
    try:
        data_manager._ensure_faq_index()
    except Exception as e:
        print(f"Warning: Failed to initialize FAQ index: {e}")

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