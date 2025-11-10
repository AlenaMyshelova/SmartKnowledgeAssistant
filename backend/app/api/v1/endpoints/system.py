from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()

@router.get("/health")
def health_check():
    """
    Check the health status of the API.
    
    GET /api/v1/health
    """
    return {
        "status": "ok", 
        "message": "Smart Knowledge Assistant API is running",
        "version": settings.VERSION,
        "model": settings.OPENAI_MODEL
    }

@router.get("/info")
def get_api_info():
    """
    Information about the API.
    
    GET /api/v1/info
    """
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_version": "v1",
        "endpoints": {
            "chat": "/api/v1/chat",
            "health": "/api/v1/health", 
            "categories": "/api/v1/categories",
            "data_sources": "/api/v1/data-sources"
        }
    }