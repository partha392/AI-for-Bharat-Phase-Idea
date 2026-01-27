"""
API routes for grievance filing functionality.

This module provides REST API endpoints for the conversational
grievance filing system.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..grievance.filing_assistant import ConversationalFilingAssistant
from ..core.exceptions import GrievanceFilingError

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/grievance", tags=["grievance"])

# Initialize filing assistant
filing_assistant = ConversationalFilingAssistant()


class StartGrievanceRequest(BaseModel):
    """Request model for starting grievance filing."""
    session_id: str = Field(..., description="Session identifier")
    language: str = Field(default="hi", description="User's preferred language")


class ProcessInputRequest(BaseModel):
    """Request model for processing user input."""
    session_id: str = Field(..., description="Session identifier")
    user_input: str = Field(..., description="User's voice/text input")
    confidence: Optional[float] = Field(None, description="Speech recognition confidence")


class GrievanceResponse(BaseModel):
    """Response model for grievance operations."""
    success: bool
    session_id: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/start", response_model=GrievanceResponse)
async def start_grievance_filing(request: StartGrievanceRequest) -> GrievanceResponse:
    """
    Start a new grievance filing session.
    
    Args:
        request: Start grievance request
        
    Returns:
        GrievanceResponse with session information
    """
    try:
        result = filing_assistant.start_grievance_filing(
            session_id=request.session_id,
            language=request.language
        )
        
        return GrievanceResponse(
            success=True,
            session_id=request.session_id,
            message="Grievance filing session started successfully",
            data=result
        )
        
    except GrievanceFilingError as e:
        logger.error("Failed to start grievance filing: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error("Unexpected error starting grievance filing: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/process", response_model=GrievanceResponse)
async def process_user_input(request: ProcessInputRequest) -> GrievanceResponse:
    """
    Process user input in grievance filing conversation.
    
    Args:
        request: Process input request
        
    Returns:
        GrievanceResponse with conversation result
    """
    try:
        result = filing_assistant.process_user_input(
            session_id=request.session_id,
            user_input=request.user_input,
            confidence=request.confidence
        )
        
        return GrievanceResponse(
            success=True,
            session_id=request.session_id,
            message="Input processed successfully",
            data=result
        )
        
    except Exception as e:
        logger.error("Failed to process user input: %s", str(e))
        
        # Check if it's a session not found error
        if "Session not found" in str(e):
            raise HTTPException(status_code=404, detail="Session not found")
        
        raise HTTPException(status_code=500, detail="Failed to process input")


@router.get("/status/{session_id}", response_model=GrievanceResponse)
async def get_session_status(session_id: str) -> GrievanceResponse:
    """
    Get current status of a grievance filing session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        GrievanceResponse with session status
    """
    try:
        result = filing_assistant.get_session_status(session_id)
        
        if result.get('error'):
            raise HTTPException(status_code=404, detail=result['error'])
        
        return GrievanceResponse(
            success=True,
            session_id=session_id,
            message="Session status retrieved successfully",
            data=result
        )
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error("Failed to get session status: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to get session status")


@router.get("/help/{session_id}")
async def get_contextual_help(session_id: str, help_topic: Optional[str] = None) -> GrievanceResponse:
    """
    Get contextual help for grievance filing.
    
    Args:
        session_id: Session identifier
        help_topic: Optional specific help topic
        
    Returns:
        GrievanceResponse with help information
    """
    try:
        result = filing_assistant.provide_help(session_id, help_topic)
        
        if result.get('error'):
            raise HTTPException(status_code=404, detail=result['error'])
        
        return GrievanceResponse(
            success=True,
            session_id=session_id,
            message="Help information retrieved successfully",
            data=result
        )
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error("Failed to get help: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to get help information")


@router.post("/restart/{session_id}", response_model=GrievanceResponse)
async def restart_session(session_id: str) -> GrievanceResponse:
    """
    Restart a grievance filing session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        GrievanceResponse with restart confirmation
    """
    try:
        result = filing_assistant.restart_session(session_id)
        
        return GrievanceResponse(
            success=True,
            session_id=session_id,
            message="Session restarted successfully",
            data=result
        )
        
    except Exception as e:
        logger.error("Failed to restart session: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to restart session")


@router.delete("/end/{session_id}", response_model=GrievanceResponse)
async def end_session(session_id: str, save_draft: bool = True) -> GrievanceResponse:
    """
    End a grievance filing session.
    
    Args:
        session_id: Session identifier
        save_draft: Whether to save as draft
        
    Returns:
        GrievanceResponse with end confirmation
    """
    try:
        result = filing_assistant.end_session(session_id, save_draft)
        
        return GrievanceResponse(
            success=True,
            session_id=session_id,
            message="Session ended successfully",
            data=result
        )
        
    except Exception as e:
        logger.error("Failed to end session: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to end session")


# Health check endpoint
@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check for grievance filing service."""
    return {
        "status": "healthy",
        "service": "grievance_filing",
        "version": "1.0.0"
    }