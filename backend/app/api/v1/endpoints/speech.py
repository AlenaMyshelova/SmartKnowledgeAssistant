import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from pydantic import BaseModel

from app.services.speech_service import speech_service
from app.dependencies import get_current_user_optional
from app.schemas.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class TranscriptionResponse(BaseModel):
    """Response model for audio transcription."""
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = Form(None, description="Language code (e.g., 'en', 'ru', 'es')"),
    prompt: Optional[str] = Form(None, description="Optional prompt to guide transcription"),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Transcribe audio file to text using OpenAI Whisper.
    
    Supports formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg, flac
    Maximum file size: 25MB
    
    Args:
        audio: Audio file to transcribe
        language: Optional language code for better accuracy
        prompt: Optional context prompt
        current_user: Optional authenticated user
        
    Returns:
        Transcribed text
    """
    try:
        # Log the request
        logger.info(f"Transcription request: file={audio.filename}, size={audio.size}, type={audio.content_type}")
        
        # Validate and transcribe audio
        transcribed_text = await speech_service.transcribe_audio(
            audio_file=audio,
            language=language,
            prompt=prompt
        )
        
        # Log success
        user_info = f"user={current_user.email}" if current_user else "anonymous"
        logger.info(f"Successfully transcribed audio for {user_info}: {len(transcribed_text)} characters")
        
        return TranscriptionResponse(
            text=transcribed_text,
            language=language
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during transcription: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )


@router.get("/languages")
async def get_supported_languages():
    """
    Get list of supported languages for transcription.
    
    Returns:
        List of supported language codes and names
    """
    # Whisper supports many languages, here are the most common ones
    languages = [
        {"code": "en", "name": "English"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
        {"code": "it", "name": "Italian"},
        {"code": "pt", "name": "Portuguese"},
        {"code": "ru", "name": "Russian"},
        {"code": "zh", "name": "Chinese"},
        {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"},
        {"code": "ar", "name": "Arabic"},
        {"code": "hi", "name": "Hindi"},
        {"code": "tr", "name": "Turkish"},
        {"code": "pl", "name": "Polish"},
        {"code": "nl", "name": "Dutch"},
        {"code": "sv", "name": "Swedish"},
        {"code": "da", "name": "Danish"},
        {"code": "no", "name": "Norwegian"},
        {"code": "fi", "name": "Finnish"},
        {"code": "uk", "name": "Ukrainian"},
    ]
    
    return {"languages": languages}


@router.get("/formats")
async def get_supported_formats():
    """
    Get list of supported audio formats.
    
    Returns:
        List of supported audio formats
    """
    formats = [
        {"format": "mp3", "mime_type": "audio/mpeg"},
        {"format": "wav", "mime_type": "audio/wav"},
        {"format": "webm", "mime_type": "audio/webm"},
        {"format": "ogg", "mime_type": "audio/ogg"},
        {"format": "m4a", "mime_type": "audio/m4a"},
        {"format": "flac", "mime_type": "audio/flac"},
    ]
    
    return {"formats": formats, "max_size_mb": 25}