"""
Main application entry point for the Bharat Voice Assistant.

This module provides the main application interface and API endpoints
for the voice assistant system.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from .core.orchestrator import (
    BharatVoiceOrchestrator, InteractionRequest, InteractionResponse,
    SessionType, InteractionState
)
from .core.logging import get_logger
from .core.exceptions import BharatVoiceAssistantError


logger = get_logger(__name__)


# Pydantic models for API
class TextInteractionRequest(BaseModel):
    """Request model for text-based interactions."""
    user_id: str
    session_id: Optional[str] = None
    text_input: str
    language: str = "hindi"
    metadata: Dict[str, Any] = {}


class InteractionResponseModel(BaseModel):
    """Response model for interactions."""
    session_id: str
    response_text: str
    response_type: str
    language: str
    next_action: Optional[str]
    suggestions: list = []
    processing_time: float
    confidence: float
    timestamp: datetime


class SystemStatusModel(BaseModel):
    """Model for system status response."""
    status: str
    active_sessions: int
    total_interactions: int
    average_processing_time: float
    error_rate: float
    components: Dict[str, str]


# Initialize FastAPI app
app = FastAPI(
    title="Bharat Voice Assistant API",
    description="Multilingual voice-first AI system for government services",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize orchestrator
orchestrator = BharatVoiceOrchestrator()


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting Bharat Voice Assistant API")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down Bharat Voice Assistant API")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Bharat Voice Assistant API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        status = orchestrator.get_system_status()
        return {"status": "healthy", "details": status}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="System unhealthy")


@app.get("/status", response_model=SystemStatusModel)
async def get_system_status():
    """Get detailed system status."""
    try:
        status = orchestrator.get_system_status()
        return SystemStatusModel(**status)
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/interact/text", response_model=InteractionResponseModel)
async def text_interaction(request: TextInteractionRequest):
    """Handle text-based interaction."""
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Create interaction request
        interaction_request = InteractionRequest(
            session_id=session_id,
            user_id=request.user_id,
            text_input=request.text_input,
            input_type="text",
            language=request.language,
            metadata=request.metadata
        )
        
        # Process interaction
        response = await orchestrator.process_interaction(interaction_request)
        
        # Convert to response model
        return InteractionResponseModel(
            session_id=response.session_id,
            response_text=response.response_text,
            response_type=response.response_type,
            language=response.language,
            next_action=response.next_action,
            suggestions=response.suggestions,
            processing_time=response.processing_time,
            confidence=response.confidence,
            timestamp=response.timestamp
        )
        
    except BharatVoiceAssistantError as e:
        logger.error(f"Bharat Voice error in text interaction: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in text interaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/interact/voice")
async def voice_interaction(
    user_id: str = Form(...),
    language: str = Form(default="hindi"),
    session_id: Optional[str] = Form(default=None),
    audio_file: UploadFile = File(...)
):
    """Handle voice-based interaction."""
    try:
        # Validate audio file
        if not audio_file.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="Invalid audio file format")
        
        # Read audio data
        audio_data = await audio_file.read()
        
        # Generate session ID if not provided
        session_id = session_id or str(uuid.uuid4())
        
        # Create interaction request
        interaction_request = InteractionRequest(
            session_id=session_id,
            user_id=user_id,
            audio_data=audio_data,
            input_type="voice",
            language=language
        )
        
        # Process interaction
        response = await orchestrator.process_interaction(interaction_request)
        
        # Return response (audio response would be handled separately in production)
        return {
            "session_id": response.session_id,
            "response_text": response.response_text,
            "response_type": response.response_type,
            "language": response.language,
            "next_action": response.next_action,
            "suggestions": response.suggestions,
            "processing_time": response.processing_time,
            "confidence": response.confidence,
            "timestamp": response.timestamp.isoformat(),
            "has_audio_response": response.audio_response is not None
        }
        
    except BharatVoiceAssistantError as e:
        logger.error(f"Bharat Voice error in voice interaction: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in voice interaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/interact/voice/{session_id}/audio")
async def get_audio_response(session_id: str):
    """Get audio response for a session (placeholder endpoint)."""
    # In a production system, this would retrieve the audio response
    # from a cache or storage system
    raise HTTPException(status_code=501, detail="Audio response endpoint not implemented")


@app.post("/session/create")
async def create_session(user_id: str, language: str = "hindi"):
    """Create a new user session."""
    try:
        session_id = str(uuid.uuid4())
        
        # Create a dummy interaction to initialize the session
        interaction_request = InteractionRequest(
            session_id=session_id,
            user_id=user_id,
            text_input="नमस्ते" if language == "hindi" else "Hello",
            input_type="text",
            language=language
        )
        
        # Process to create session
        response = await orchestrator.process_interaction(interaction_request)
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "language": language,
            "created_at": datetime.now().isoformat(),
            "initial_response": response.response_text
        }
        
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@app.delete("/session/{session_id}")
async def end_session(session_id: str):
    """End a user session."""
    try:
        # In a production system, this would clean up session data
        return {"message": f"Session {session_id} ended successfully"}
        
    except Exception as e:
        logger.error(f"Failed to end session: {e}")
        raise HTTPException(status_code=500, detail="Failed to end session")


@app.get("/schemes/search")
async def search_schemes(
    user_id: str,
    age: Optional[int] = None,
    location: Optional[str] = None,
    occupation: Optional[str] = None,
    language: str = "hindi"
):
    """Search for government schemes based on user criteria."""
    try:
        # Create a scheme discovery interaction
        session_id = str(uuid.uuid4())
        
        # Build search query
        search_text = "योजना बताओ" if language == "hindi" else "show schemes"
        if age:
            search_text += f" उम्र {age}" if language == "hindi" else f" age {age}"
        if occupation:
            search_text += f" {occupation}"
        if location:
            search_text += f" {location}"
        
        interaction_request = InteractionRequest(
            session_id=session_id,
            user_id=user_id,
            text_input=search_text,
            input_type="text",
            language=language
        )
        
        response = await orchestrator.process_interaction(interaction_request)
        
        return {
            "schemes": response.response_text,
            "suggestions": response.suggestions,
            "language": language
        }
        
    except Exception as e:
        logger.error(f"Failed to search schemes: {e}")
        raise HTTPException(status_code=500, detail="Failed to search schemes")


@app.post("/grievance/file")
async def file_grievance(
    user_id: str,
    complaint_text: str,
    language: str = "hindi",
    category: Optional[str] = None
):
    """File a new grievance."""
    try:
        session_id = str(uuid.uuid4())
        
        # Create grievance filing interaction
        grievance_text = f"शिकायत करनी है: {complaint_text}" if language == "hindi" else f"file complaint: {complaint_text}"
        if category:
            grievance_text += f" category: {category}"
        
        interaction_request = InteractionRequest(
            session_id=session_id,
            user_id=user_id,
            text_input=grievance_text,
            input_type="text",
            language=language
        )
        
        response = await orchestrator.process_interaction(interaction_request)
        
        return {
            "message": response.response_text,
            "next_action": response.next_action,
            "session_id": session_id,
            "language": language
        }
        
    except Exception as e:
        logger.error(f"Failed to file grievance: {e}")
        raise HTTPException(status_code=500, detail="Failed to file grievance")


@app.get("/grievance/status/{reference_number}")
async def check_grievance_status(reference_number: str, language: str = "hindi"):
    """Check status of a grievance."""
    try:
        session_id = str(uuid.uuid4())
        user_id = "anonymous"  # For status checks, user ID might not be required
        
        # Create status check interaction
        status_text = f"स्थिति जांचें {reference_number}" if language == "hindi" else f"check status {reference_number}"
        
        interaction_request = InteractionRequest(
            session_id=session_id,
            user_id=user_id,
            text_input=status_text,
            input_type="text",
            language=language
        )
        
        response = await orchestrator.process_interaction(interaction_request)
        
        return {
            "status": response.response_text,
            "reference_number": reference_number,
            "language": language
        }
        
    except Exception as e:
        logger.error(f"Failed to check grievance status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check status")


@app.get("/help")
async def get_help(language: str = "hindi"):
    """Get help information."""
    try:
        session_id = str(uuid.uuid4())
        user_id = "anonymous"
        
        help_text = "मदद चाहिए" if language == "hindi" else "help"
        
        interaction_request = InteractionRequest(
            session_id=session_id,
            user_id=user_id,
            text_input=help_text,
            input_type="text",
            language=language
        )
        
        response = await orchestrator.process_interaction(interaction_request)
        
        return {
            "help": response.response_text,
            "suggestions": response.suggestions,
            "language": language
        }
        
    except Exception as e:
        logger.error(f"Failed to get help: {e}")
        raise HTTPException(status_code=500, detail="Failed to get help")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Run the application server."""
    uvicorn.run(
        "bharat_voice_assistant.app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )


if __name__ == "__main__":
    run_server(debug=True)