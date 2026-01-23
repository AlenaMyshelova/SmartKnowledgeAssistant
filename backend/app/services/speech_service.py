import io
import logging
from typing import Optional
import tempfile
import os

from openai import AsyncOpenAI
from fastapi import HTTPException, UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)


class SpeechService:
    """Service for speech-to-text conversion using OpenAI Whisper."""
    
    def __init__(self):
        """Initialize the speech service with OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "whisper-1"
        # Supported audio formats by Whisper API
        self.supported_formats = {
            "audio/mpeg": ".mp3",
            "audio/mp4": ".mp4",
            "audio/mpeg": ".mpeg",
            "audio/mpga": ".mpga",
            "audio/m4a": ".m4a",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/flac": ".flac",
        }
        self.max_file_size = 25 * 1024 * 1024
    
    async def transcribe_audio(
        self, 
        audio_file: UploadFile,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio file to text using OpenAI Whisper.
        
        Args:
            audio_file: The uploaded audio file
            language: Optional language code (e.g., 'en', 'es', 'ru')
            prompt: Optional prompt to guide the transcription
            
        Returns:
            Transcribed text
            
        Raises:
            HTTPException: If file is invalid or transcription fails
        """
        try:
            content_type = audio_file.content_type
            if content_type not in self.supported_formats:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported audio format: {content_type}. Supported formats: {', '.join(self.supported_formats.keys())}"
                )
            
            # Read file content
            audio_content = await audio_file.read()
            
            if len(audio_content) > self.max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is 25MB, got {len(audio_content) / 1024 / 1024:.2f}MB"
                )
            
            if len(audio_content) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Empty audio file"
                )
            
            # Create a temporary file with proper extension
            file_extension = self.supported_formats.get(content_type, ".mp3")
            
            with tempfile.NamedTemporaryFile(
                mode='wb',
                suffix=file_extension,
                delete=False
            ) as temp_file:
                temp_file.write(audio_content)
                temp_file_path = temp_file.name
            
            try:
                # Open the temporary file for reading
                with open(temp_file_path, 'rb') as audio_data:
                    # Prepare transcription parameters
                    transcription_params = {
                        "model": self.model,
                        "file": audio_data,
                    }
                    
                    if language:
                        transcription_params["language"] = language
                    
                    if prompt:
                        transcription_params["prompt"] = prompt
                    
                    # Call OpenAI Whisper API
                    logger.info(f"Transcribing audio file: {audio_file.filename}")
                    response = await self.client.audio.transcriptions.create(
                        **transcription_params
                    )
                    
                    # Extract text from response
                    transcribed_text = response.text
                    
                    if not transcribed_text:
                        raise HTTPException(
                            status_code=400,
                            detail="No speech detected in the audio"
                        )
                    
                    logger.info(f"Successfully transcribed audio: {len(transcribed_text)} characters")
                    return transcribed_text
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
                    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error during audio transcription: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to transcribe audio: {str(e)}"
            )
    
    async def validate_audio_file(self, audio_file: UploadFile) -> bool:
        
        if not audio_file:
            raise HTTPException(
                status_code=400,
                detail="No audio file provided"
            )
        
        if audio_file.content_type not in self.supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid audio format: {audio_file.content_type}"
            )
        
        return True


speech_service = SpeechService()