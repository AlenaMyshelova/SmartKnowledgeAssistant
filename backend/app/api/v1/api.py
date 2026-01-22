from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.api.v1.endpoints import auth, chat, data_sources, system, speech

api_router = APIRouter()

api_router.include_router(system.router, tags=["system"])
api_router.include_router(chat.router, tags=["chat"], prefix="/chat")  
api_router.include_router(data_sources.router, tags=["data-sources"], prefix="/data-sources") 
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])  
api_router.include_router(speech.router, prefix="/speech", tags=["speech"])  


@api_router.get("/login/{provider}")
async def redirect_login(provider: str):
    return RedirectResponse(f"/api/v1/auth/login/{provider}", status_code=307)

@api_router.get("/providers")
async def redirect_providers():
    return RedirectResponse("/api/v1/auth/providers", status_code=307)