"""
Voice API routes for the Bharat Voice Assistant.

This module provides REST API endpoints for voice gateway management
and integration with the WebSocket voice interface.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import asyncio

from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.voice import VoiceInterfaceGateway

logger = get_logger(__name__)

# Global voice gateway instance
voice_gateway: Optional[VoiceInterfaceGateway] = None

# Create router
router = APIRouter(prefix="/voice", tags=["voice"])


async def get_voice_gateway() -> VoiceInterfaceGateway:
    """Get or create the voice gateway instance."""
    global voice_gateway
    
    if voice_gateway is None:
        voice_gateway = VoiceInterfaceGateway()
        await voice_gateway.start()
    
    return voice_gateway


@router.on_event("startup")
async def startup_voice_gateway():
    """Initialize voice gateway on startup."""
    try:
        await get_voice_gateway()
        logger.info("Voice gateway initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize voice gateway: {e}")


@router.on_event("shutdown")
async def shutdown_voice_gateway():
    """Shutdown voice gateway on application shutdown."""
    global voice_gateway
    
    if voice_gateway:
        try:
            await voice_gateway.stop()
            voice_gateway = None
            logger.info("Voice gateway shutdown successfully")
        except Exception as e:
            logger.error(f"Error shutting down voice gateway: {e}")


@router.get("/status")
async def get_voice_gateway_status() -> Dict[str, Any]:
    """
    Get voice gateway status and statistics.
    
    Returns:
        Dictionary containing gateway status and statistics
    """
    try:
        gateway = await get_voice_gateway()
        stats = gateway.get_server_stats()
        
        return {
            "status": "running",
            "websocket_endpoint": f"ws://{gateway.host}:{gateway.port}",
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting voice gateway status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get gateway status")


@router.get("/connections")
async def get_active_connections() -> Dict[str, Any]:
    """
    Get information about active voice connections.
    
    Returns:
        Dictionary containing active connection information
    """
    try:
        gateway = await get_voice_gateway()
        active_connections = gateway.connection_manager.get_active_connections()
        
        connection_details = []
        for client_id in active_connections:
            quality = gateway.connection_manager.get_connection_quality(client_id)
            stats = gateway.connection_manager.get_connection_stats(client_id)
            
            connection_info = {
                "client_id": client_id,
                "quality": quality.value if quality else "unknown",
                "metrics_count": len(stats) if stats else 0
            }
            
            # Add latest metrics if available
            if stats and len(stats) > 0:
                latest_metrics = stats[-1]
                connection_info.update({
                    "bandwidth_kbps": latest_metrics.bandwidth_kbps,
                    "latency_ms": latest_metrics.latency_ms,
                    "last_updated": latest_metrics.timestamp
                })
            
            connection_details.append(connection_info)
        
        return {
            "total_connections": len(active_connections),
            "connections": connection_details
        }
        
    except Exception as e:
        logger.error(f"Error getting active connections: {e}")
        raise HTTPException(status_code=500, detail="Failed to get connection information")


@router.get("/connections/{client_id}/stats")
async def get_connection_stats(client_id: str) -> Dict[str, Any]:
    """
    Get detailed statistics for a specific connection.
    
    Args:
        client_id: Client identifier
        
    Returns:
        Dictionary containing connection statistics
    """
    try:
        gateway = await get_voice_gateway()
        stats = gateway.connection_manager.get_connection_stats(client_id)
        
        if not stats:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Calculate summary statistics
        if len(stats) > 0:
            latest = stats[-1]
            avg_bandwidth = sum(s.bandwidth_kbps for s in stats) / len(stats)
            avg_latency = sum(s.latency_ms for s in stats) / len(stats)
            
            quality_distribution = {}
            for stat in stats:
                quality = stat.quality_level.value
                quality_distribution[quality] = quality_distribution.get(quality, 0) + 1
        else:
            latest = None
            avg_bandwidth = 0
            avg_latency = 0
            quality_distribution = {}
        
        return {
            "client_id": client_id,
            "total_measurements": len(stats),
            "current_metrics": {
                "bandwidth_kbps": latest.bandwidth_kbps if latest else 0,
                "latency_ms": latest.latency_ms if latest else 0,
                "quality": latest.quality_level.value if latest else "unknown",
                "timestamp": latest.timestamp if latest else 0
            },
            "average_metrics": {
                "bandwidth_kbps": avg_bandwidth,
                "latency_ms": avg_latency
            },
            "quality_distribution": quality_distribution
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connection stats for {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get connection statistics")


@router.post("/test-audio-processing")
async def test_audio_processing() -> Dict[str, Any]:
    """
    Test audio processing capabilities.
    
    Returns:
        Dictionary containing test results
    """
    try:
        gateway = await get_voice_gateway()
        
        # Generate test audio data (silence)
        test_audio = b'\x00' * 16000 * 2  # 1 second of 16-bit silence at 16kHz
        
        # Test audio quality assessment
        quality_assessment = await gateway.audio_processor.assess_audio_quality(test_audio)
        
        # Test audio enhancement
        enhanced_audio = await gateway.audio_processor.enhance_audio(test_audio, quality_assessment)
        
        # Test audio compression
        compressed_audio = await gateway.audio_processor.compress_audio(test_audio, 64)
        
        return {
            "test_status": "success",
            "original_size": len(test_audio),
            "enhanced_size": len(enhanced_audio),
            "compressed_size": len(compressed_audio),
            "compression_ratio": len(test_audio) / len(compressed_audio) if len(compressed_audio) > 0 else 1,
            "quality_assessment": quality_assessment
        }
        
    except Exception as e:
        logger.error(f"Error testing audio processing: {e}")
        raise HTTPException(status_code=500, detail="Audio processing test failed")


@router.post("/restart")
async def restart_voice_gateway(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """
    Restart the voice gateway.
    
    Returns:
        Status message
    """
    try:
        async def restart_task():
            global voice_gateway
            
            # Stop current gateway
            if voice_gateway:
                await voice_gateway.stop()
                voice_gateway = None
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Start new gateway
            await get_voice_gateway()
        
        background_tasks.add_task(restart_task)
        
        return {"status": "Voice gateway restart initiated"}
        
    except Exception as e:
        logger.error(f"Error restarting voice gateway: {e}")
        raise HTTPException(status_code=500, detail="Failed to restart voice gateway")


@router.get("/health")
async def voice_gateway_health() -> Dict[str, Any]:
    """
    Health check for voice gateway.
    
    Returns:
        Health status information
    """
    try:
        gateway = await get_voice_gateway()
        
        # Basic health checks
        health_status = {
            "gateway_running": gateway.server is not None,
            "connection_manager_active": len(gateway.connection_manager.get_active_connections()) >= 0,
            "audio_processor_ready": gateway.audio_processor is not None
        }
        
        overall_healthy = all(health_status.values())
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "checks": health_status,
            "active_connections": len(gateway.connection_manager.get_active_connections()),
            "active_sessions": len(gateway.active_sessions)
        }
        
    except Exception as e:
        logger.error(f"Error checking voice gateway health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }