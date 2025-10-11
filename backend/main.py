from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

# Загружаем переменные из .env файла в самом начале
load_dotenv()

from app.vector_search import vector_search
from app.data_manager import DataManager
from app.database import init_db
from app.middleware.auth_middleware import AuthMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.auth.deps import get_current_user

# Инициализация менеджера данных
data_manager = DataManager()

# Создаем приложение FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ВАЖНО: Порядок middleware имеет значение!
# 1. Сначала CORS (должен быть первым)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Auth middleware
app.add_middleware(AuthMiddleware)

# Подключаем роутер API
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    """Выполняется при запуске приложения."""
    print(f"🚀 Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    
    # Инициализация базы данных
    print("📊 Initializing database...")
    try:
        init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        # В продакшене можно добавить exit(1) если БД критична
    
    # Проверяем векторный индекс FAQ
    print("🔍 Checking vector search indices...")
    try:
        data_manager._ensure_faq_index()
        print("✅ Vector search indices ready")
    except Exception as e:
        print(f"⚠️  Vector search initialization warning: {e}")
    
    # Проверяем OAuth настройки
    print("🔐 Checking OAuth configuration...")
    oauth_providers = settings.OAUTH_PROVIDERS
    if oauth_providers:
        print(f"✅ Available OAuth providers: {list(oauth_providers.keys())}")
    else:
        print("⚠️  No OAuth providers configured")
    
    print(f"🌐 Server starting on {settings.BACKEND_URL}")

@app.get("/")
def root():
    """
    Корневой эндпоинт - информация об API.
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "api": {
            "health": f"{settings.API_V1_STR}/system/health",
            "auth": f"{settings.API_V1_STR}/auth",
            "chat": f"{settings.API_V1_STR}/chat"
        }
    }

@app.get("/health")
def health_check():
    """
    Простая проверка здоровья приложения (публичный эндпоинт).
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "timestamp": "2024-01-01T00:00:00Z"  # В реальности используйте datetime.utcnow()
    }

# Защищенный эндпоинт для проверки аутентификации
@app.get(f"{settings.API_V1_STR}/auth-test")
def auth_test(current_user = Depends(get_current_user)):
    """
    Тестовый эндпоинт для проверки аутентификации.
    Требует действительный JWT токен.
    """
    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "is_active": current_user.is_active
        },
        "message": "Authentication successful"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8001, 
        reload=True,
        log_level="info"
    )