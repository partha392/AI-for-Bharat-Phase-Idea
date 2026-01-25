"""
Connection management module for the Bharat Voice Assistant.

This module handles WebSocket connections, bandwidth detection,
connection quality monitoring, and adaptive streaming for low-bandwidth scenarios.
"""

import asyncio
import time
import json
from typing import Dict, Any, Optional, Set, List
from dataclasses import dataclass, asdict
from enum import Enum
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import ConnectionError, BandwidthError

logger = get_logger(__name__)


class ConnectionQuality(Enum):
    """Connection quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class ConnectionMetrics:
    """Connection quality metrics."""
    bandwidth_kbps: float
    latency_ms: float
    packet_loss_rate: float
    jitter_ms: float
    connection_stability: float
    quality_level: ConnectionQuality
    timestamp: float


@dataclass
class ClientConnection:
    """Represents a client WebSocket connection."""
    websocket: websockets.WebSocketServerProtocol
    client_id: str
    connected_at: float
    last_activity: float
    metrics: ConnectionMetrics
    preferred_language: str = "hi"
    audio_format: str = "raw"
    compression_enabled: bool = True


class ConnectionManager:
    """
    Manages WebSocket connections and adapts to network conditions.
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, ClientConnection] = {}
        self.connection_stats: Dict[str, List[ConnectionMetrics]] = {}
        self.bandwidth_monitor_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.max_connections = 1000
        self.connection_timeout = 300  # 5 minutes
        self.metrics_history_size = 100
        self.bandwidth_test_interval = 30  # seconds
        
        logger.info("ConnectionManager initialized")
    
    async def start(self):
        """Start the connection manager background tasks."""
        self.bandwidth_monitor_task = asyncio.create_task(self._monitor_bandwidth())
        self.cleanup_task = asyncio.create_task(self._cleanup_inactive_connections())
        logger.info("ConnectionManager started")
    
    async def stop(self):
        """Stop the connection manager and close all connections."""
        # Cancel background tasks
        if self.bandwidth_monitor_task:
            self.bandwidth_monitor_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # Close all active connections
        for client_id in list(self.active_connections.keys()):
            await self.disconnect_client(client_id)
        
        logger.info("ConnectionManager stopped")
    
    async def connect_client(self, websocket: websockets.WebSocketServerProtocol, 
                           client_id: str) -> bool:
        """
        Register a new client connection.
        
        Args:
            websocket: WebSocket connection
            client_id: Unique client identifier
            
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            # Check connection limits
            if len(self.active_connections) >= self.max_connections:
                logger.warning(f"Connection limit reached, rejecting client {client_id}")
                await websocket.close(code=1013, reason="Server overloaded")
                return False
            
            # Perform initial bandwidth assessment
            initial_metrics = await self._assess_connection_quality(websocket)
            
            # Create client connection record
            connection = ClientConnection(
                websocket=websocket,
                client_id=client_id,
                connected_at=time.time(),
                last_activity=time.time(),
                metrics=initial_metrics
            )
            
            # Store connection
            self.active_connections[client_id] = connection
            self.connection_stats[client_id] = [initial_metrics]
            
            # Send connection confirmation with quality info
            await self._send_connection_status(client_id, {
                "status": "connected",
                "quality": initial_metrics.quality_level.value,
                "bandwidth_kbps": initial_metrics.bandwidth_kbps,
                "recommended_settings": self._get_recommended_settings(initial_metrics)
            })
            
            logger.info(f"Client {client_id} connected with {initial_metrics.quality_level.value} quality")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting client {client_id}: {e}")
            return False
    
    async def disconnect_client(self, client_id: str):
        """
        Disconnect a client and clean up resources.
        
        Args:
            client_id: Client identifier to disconnect
        """
        try:
            if client_id in self.active_connections:
                connection = self.active_connections[client_id]
                
                # Close WebSocket connection
                if not connection.websocket.closed:
                    await connection.websocket.close()
                
                # Clean up records
                del self.active_connections[client_id]
                if client_id in self.connection_stats:
                    del self.connection_stats[client_id]
                
                logger.info(f"Client {client_id} disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting client {client_id}: {e}")
    
    async def send_audio_data(self, client_id: str, audio_data: bytes, 
                            metadata: Dict[str, Any] = None) -> bool:
        """
        Send audio data to a client with adaptive quality.
        
        Args:
            client_id: Target client identifier
            audio_data: Audio data to send
            metadata: Optional metadata about the audio
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if client_id not in self.active_connections:
                logger.warning(f"Client {client_id} not found for audio transmission")
                return False
            
            connection = self.active_connections[client_id]
            
            # Adapt audio quality based on connection
            adapted_data = await self._adapt_audio_for_connection(
                audio_data, connection.metrics, metadata
            )
            
            # Prepare message
            message = {
                "type": "audio_data",
                "data": adapted_data.hex(),  # Convert bytes to hex string
                "metadata": metadata or {},
                "timestamp": time.time()
            }
            
            # Send message
            await connection.websocket.send(json.dumps(message))
            
            # Update activity timestamp
            connection.last_activity = time.time()
            
            return True
            
        except ConnectionClosed:
            logger.info(f"Client {client_id} connection closed during audio transmission")
            await self.disconnect_client(client_id)
            return False
        except Exception as e:
            logger.error(f"Error sending audio to client {client_id}: {e}")
            return False
    
    async def receive_audio_data(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Receive audio data from a client.
        
        Args:
            client_id: Source client identifier
            
        Returns:
            Dictionary containing audio data and metadata, or None if error
        """
        try:
            if client_id not in self.active_connections:
                return None
            
            connection = self.active_connections[client_id]
            
            # Receive message with timeout
            message_str = await asyncio.wait_for(
                connection.websocket.recv(),
                timeout=30.0
            )
            
            # Parse message
            message = json.loads(message_str)
            
            # Update activity timestamp
            connection.last_activity = time.time()
            
            # Process audio data if present
            if message.get("type") == "audio_data" and "data" in message:
                # Convert hex string back to bytes
                audio_data = bytes.fromhex(message["data"])
                
                return {
                    "audio_data": audio_data,
                    "metadata": message.get("metadata", {}),
                    "timestamp": message.get("timestamp", time.time()),
                    "client_id": client_id
                }
            
            return message
            
        except asyncio.TimeoutError:
            logger.debug(f"Timeout receiving from client {client_id}")
            return None
        except ConnectionClosed:
            logger.info(f"Client {client_id} connection closed during receive")
            await self.disconnect_client(client_id)
            return None
        except Exception as e:
            logger.error(f"Error receiving from client {client_id}: {e}")
            return None
    
    def get_connection_quality(self, client_id: str) -> Optional[ConnectionQuality]:
        """
        Get current connection quality for a client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Connection quality level or None if client not found
        """
        if client_id in self.active_connections:
            return self.active_connections[client_id].metrics.quality_level
        return None
    
    def get_active_connections(self) -> List[str]:
        """Get list of active client IDs."""
        return list(self.active_connections.keys())
    
    def get_connection_stats(self, client_id: str) -> Optional[List[ConnectionMetrics]]:
        """
        Get connection statistics for a client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            List of connection metrics or None if client not found
        """
        return self.connection_stats.get(client_id)
    
    async def _assess_connection_quality(self, websocket: websockets.WebSocketServerProtocol) -> ConnectionMetrics:
        """Assess connection quality through bandwidth and latency tests."""
        try:
            # Simple bandwidth test - send test data and measure response time
            test_start = time.time()
            test_data = {"type": "bandwidth_test", "data": "x" * 1024, "timestamp": test_start}
            
            await websocket.send(json.dumps(test_data))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            
            test_end = time.time()
            latency_ms = (test_end - test_start) * 1000
            
            # Estimate bandwidth (very rough approximation)
            data_size_kb = len(json.dumps(test_data)) / 1024
            bandwidth_kbps = (data_size_kb * 8) / ((test_end - test_start) or 0.001)
            
            # Determine quality level based on metrics
            if bandwidth_kbps >= config.network.high_quality_threshold and latency_ms < 200:
                quality = ConnectionQuality.EXCELLENT
            elif bandwidth_kbps >= config.network.low_bandwidth_threshold and latency_ms < 500:
                quality = ConnectionQuality.GOOD
            elif bandwidth_kbps >= 32 and latency_ms < 1000:
                quality = ConnectionQuality.FAIR
            elif bandwidth_kbps >= 16:
                quality = ConnectionQuality.POOR
            else:
                quality = ConnectionQuality.CRITICAL
            
            return ConnectionMetrics(
                bandwidth_kbps=bandwidth_kbps,
                latency_ms=latency_ms,
                packet_loss_rate=0.0,  # Would need more sophisticated testing
                jitter_ms=0.0,  # Would need multiple measurements
                connection_stability=1.0,  # Initial assumption
                quality_level=quality,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.warning(f"Connection quality assessment failed: {e}")
            # Return conservative estimates
            return ConnectionMetrics(
                bandwidth_kbps=32.0,
                latency_ms=1000.0,
                packet_loss_rate=0.1,
                jitter_ms=100.0,
                connection_stability=0.5,
                quality_level=ConnectionQuality.POOR,
                timestamp=time.time()
            )
    
    async def _adapt_audio_for_connection(self, audio_data: bytes, 
                                        metrics: ConnectionMetrics,
                                        metadata: Dict[str, Any] = None) -> bytes:
        """Adapt audio quality based on connection metrics."""
        try:
            # Import here to avoid circular imports
            from .audio_processor import AudioProcessor
            
            processor = AudioProcessor()
            
            # Determine target bitrate based on connection quality
            if metrics.quality_level == ConnectionQuality.EXCELLENT:
                target_bitrate = 128
            elif metrics.quality_level == ConnectionQuality.GOOD:
                target_bitrate = 64
            elif metrics.quality_level == ConnectionQuality.FAIR:
                target_bitrate = 32
            elif metrics.quality_level == ConnectionQuality.POOR:
                target_bitrate = 24
            else:  # CRITICAL
                target_bitrate = 16
            
            # Apply compression if enabled and needed
            if metrics.bandwidth_kbps < config.network.high_quality_threshold:
                adapted_data = await processor.compress_audio(audio_data, target_bitrate)
            else:
                adapted_data = audio_data
            
            return adapted_data
            
        except Exception as e:
            logger.error(f"Error adapting audio for connection: {e}")
            return audio_data  # Return original on error
    
    def _get_recommended_settings(self, metrics: ConnectionMetrics) -> Dict[str, Any]:
        """Get recommended settings based on connection quality."""
        settings = {
            "audio_format": "mp3" if metrics.bandwidth_kbps < 64 else "raw",
            "compression_enabled": metrics.bandwidth_kbps < config.network.high_quality_threshold,
            "buffer_size": "large" if metrics.latency_ms > 500 else "normal",
            "quality_mode": "adaptive"
        }
        
        if metrics.quality_level in [ConnectionQuality.POOR, ConnectionQuality.CRITICAL]:
            settings.update({
                "text_fallback_enabled": True,
                "audio_chunk_size": "small",
                "retry_enabled": True
            })
        
        return settings
    
    async def _send_connection_status(self, client_id: str, status: Dict[str, Any]):
        """Send connection status message to client."""
        try:
            if client_id in self.active_connections:
                connection = self.active_connections[client_id]
                message = {
                    "type": "connection_status",
                    "status": status,
                    "timestamp": time.time()
                }
                await connection.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending connection status to {client_id}: {e}")
    
    async def _monitor_bandwidth(self):
        """Background task to monitor connection bandwidth."""
        while True:
            try:
                await asyncio.sleep(self.bandwidth_test_interval)
                
                # Test bandwidth for all active connections
                for client_id, connection in list(self.active_connections.items()):
                    try:
                        # Perform periodic quality assessment
                        new_metrics = await self._assess_connection_quality(connection.websocket)
                        
                        # Update connection metrics
                        connection.metrics = new_metrics
                        
                        # Store metrics history
                        if client_id in self.connection_stats:
                            self.connection_stats[client_id].append(new_metrics)
                            
                            # Limit history size
                            if len(self.connection_stats[client_id]) > self.metrics_history_size:
                                self.connection_stats[client_id] = \
                                    self.connection_stats[client_id][-self.metrics_history_size:]
                        
                        # Notify client of quality changes
                        await self._send_connection_status(client_id, {
                            "quality_update": True,
                            "quality": new_metrics.quality_level.value,
                            "bandwidth_kbps": new_metrics.bandwidth_kbps,
                            "latency_ms": new_metrics.latency_ms
                        })
                        
                    except Exception as e:
                        logger.error(f"Error monitoring bandwidth for client {client_id}: {e}")
                        # Remove problematic connection
                        await self.disconnect_client(client_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in bandwidth monitoring: {e}")
    
    async def _cleanup_inactive_connections(self):
        """Background task to clean up inactive connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = time.time()
                inactive_clients = []
                
                for client_id, connection in self.active_connections.items():
                    if current_time - connection.last_activity > self.connection_timeout:
                        inactive_clients.append(client_id)
                
                # Disconnect inactive clients
                for client_id in inactive_clients:
                    logger.info(f"Disconnecting inactive client {client_id}")
                    await self.disconnect_client(client_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")