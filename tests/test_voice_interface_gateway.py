"""
Unit tests for the Voice Interface Gateway.

Tests the core functionality of the voice interface gateway including
WebSocket handling, audio processing, and connection management.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
import websockets
from websockets.exceptions import ConnectionClosed

from bharat_voice_assistant.voice.gateway import VoiceInterfaceGateway
from bharat_voice_assistant.voice.audio_processor import AudioProcessor
from bharat_voice_assistant.voice.connection_manager import ConnectionManager, ConnectionQuality


class TestVoiceInterfaceGateway:
    """Test cases for VoiceInterfaceGateway."""
    
    @pytest.fixture
    def gateway(self):
        """Create a VoiceInterfaceGateway instance for testing."""
        return VoiceInterfaceGateway(host="localhost", port=8001)
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket connection."""
        websocket = Mock()
        websocket.remote_address = ("127.0.0.1", 12345)
        websocket.closed = False
        websocket.send = AsyncMock()
        websocket.recv = AsyncMock()
        websocket.close = AsyncMock()
        return websocket
    
    def test_gateway_initialization(self, gateway):
        """Test gateway initialization."""
        assert gateway.host == "localhost"
        assert gateway.port == 8001
        assert isinstance(gateway.audio_processor, AudioProcessor)
        assert isinstance(gateway.connection_manager, ConnectionManager)
        assert gateway.server is None
        assert len(gateway.active_sessions) == 0
    
    @pytest.mark.asyncio
    async def test_start_and_stop_gateway(self, gateway):
        """Test starting and stopping the gateway."""
        with patch('websockets.serve') as mock_serve:
            mock_server = Mock()
            mock_server.close = Mock()
            mock_server.wait_closed = AsyncMock()
            
            # Make the mock_serve return an awaitable
            async def mock_serve_func(*args, **kwargs):
                return mock_server
            
            mock_serve.side_effect = mock_serve_func
            
            # Mock connection manager
            gateway.connection_manager.start = AsyncMock()
            gateway.connection_manager.stop = AsyncMock()
            
            # Test start
            await gateway.start()
            assert gateway.server == mock_server
            gateway.connection_manager.start.assert_called_once()
            
            # Test stop
            await gateway.stop()
            mock_server.close.assert_called_once()
            mock_server.wait_closed.assert_called_once()
            gateway.connection_manager.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_start_session(self, gateway, mock_websocket):
        """Test session start handling."""
        client_id = "test-client-123"
        
        # Mock connection manager
        gateway.connection_manager.send_audio_data = AsyncMock(return_value=True)
        
        message_data = {
            "type": "start_session",
            "config": {
                "language": "hi",
                "audio_format": "raw"
            }
        }
        
        await gateway._handle_start_session(client_id, message_data)
        
        # Check session was created
        assert client_id in gateway.active_sessions
        session = gateway.active_sessions[client_id]
        assert session["client_id"] == client_id
        assert session["language"] == "hi"
        assert session["audio_format"] == "raw"
        
        # Check response was sent
        gateway.connection_manager.send_audio_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_end_session(self, gateway, mock_websocket):
        """Test session end handling."""
        client_id = "test-client-123"
        
        # Create active session
        gateway.active_sessions[client_id] = {
            "client_id": client_id,
            "started_at": asyncio.get_event_loop().time() - 60,  # 1 minute ago
            "conversation_history": [{"test": "data"}]
        }
        
        # Mock connection manager
        gateway.connection_manager.send_audio_data = AsyncMock(return_value=True)
        
        message_data = {"type": "end_session"}
        
        await gateway._handle_end_session(client_id, message_data)
        
        # Check session was removed
        assert client_id not in gateway.active_sessions
        
        # Check response was sent
        gateway.connection_manager.send_audio_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_ping(self, gateway):
        """Test ping message handling."""
        client_id = "test-client-123"
        
        # Mock connection manager
        gateway.connection_manager.send_audio_data = AsyncMock(return_value=True)
        
        message_data = {
            "type": "ping",
            "timestamp": 1234567890.0
        }
        
        await gateway._handle_ping(client_id, message_data)
        
        # Check pong response was sent
        gateway.connection_manager.send_audio_data.assert_called_once()
        
        # Verify pong message content
        call_args = gateway.connection_manager.send_audio_data.call_args
        message_bytes = call_args[0][1]  # Second argument (audio_data)
        message_str = message_bytes.decode('utf-8')
        message_dict = json.loads(message_str)
        
        assert message_dict["type"] == "pong"
        assert message_dict["original_timestamp"] == 1234567890.0
    
    @pytest.mark.asyncio
    async def test_handle_audio_data(self, gateway):
        """Test audio data handling."""
        client_id = "test-client-123"
        
        # Create test audio data
        test_audio = b'\x00' * 1000  # 1000 bytes of silence
        
        # Mock audio processor
        gateway.audio_processor.assess_audio_quality = AsyncMock(return_value={
            "overall_score": 0.8,
            "quality_level": "good",
            "metrics": {"volume_level": 0.7, "noise_level": 0.2}
        })
        gateway.audio_processor.enhance_audio = AsyncMock(return_value=test_audio)
        
        # Mock speech recognizer
        from bharat_voice_assistant.voice.speech_recognition import RecognitionResult
        mock_recognition_result = RecognitionResult(
            transcript="नमस्ते मुझे सहायता चाहिए",
            confidence=0.9,
            language="hi-IN",
            alternatives=[],
            processing_time_ms=100,
            audio_quality_score=0.8,
            noise_level=0.2
        )
        gateway.speech_recognizer.recognize_speech = AsyncMock(return_value=mock_recognition_result)
        
        # Mock connection manager
        gateway.connection_manager.send_audio_data = AsyncMock(return_value=True)
        
        # Create active session
        gateway.active_sessions[client_id] = {
            "client_id": client_id,
            "language": "hi",
            "conversation_history": []
        }
        
        message_data = {
            "type": "audio_data",
            "audio_data": test_audio,
            "metadata": {"format": "raw"}
        }
        
        await gateway._handle_audio_data(client_id, message_data)
        
        # Check audio processing was called
        gateway.audio_processor.assess_audio_quality.assert_called_once_with(test_audio)
        
        # Check speech recognition was called
        gateway.speech_recognizer.recognize_speech.assert_called_once()
        
        # Check response was sent
        gateway.connection_manager.send_audio_data.assert_called_once()
        
        # Check conversation history was updated
        session = gateway.active_sessions[client_id]
        assert len(session["conversation_history"]) == 1
    
    @pytest.mark.asyncio
    async def test_process_voice_input_placeholder(self, gateway):
        """Test voice input processing with speech recognition."""
        client_id = "test-client-123"
        test_audio = b'\x00' * 1000
        quality_assessment = {
            "overall_score": 0.8,
            "quality_level": "good"
        }
        metadata = {"format": "raw"}
        
        # Mock speech recognizer
        from bharat_voice_assistant.voice.speech_recognition import RecognitionResult
        mock_recognition_result = RecognitionResult(
            transcript="नमस्ते मुझे सहायता चाहिए",
            confidence=0.9,
            language="hi-IN",
            alternatives=[],
            processing_time_ms=100,
            audio_quality_score=0.8,
            noise_level=0.2
        )
        gateway.speech_recognizer.recognize_speech = AsyncMock(return_value=mock_recognition_result)
        
        # Create active session
        gateway.active_sessions[client_id] = {
            "client_id": client_id,
            "language": "hi",
            "conversation_history": []
        }
        
        result = await gateway._process_voice_input(
            client_id, test_audio, quality_assessment, metadata
        )
        
        # Check result structure
        assert result is not None
        assert "recognized_text" in result
        assert "confidence" in result
        assert "language" in result
        assert "response_text" in result
        assert result["language"] == "hi"
        assert result["confidence"] == 0.9
        assert result["recognized_text"] == "नमस्ते मुझे सहायता चाहिए"
        assert result["needs_clarification"] == False  # High confidence
        
        # Check conversation history was updated
        session = gateway.active_sessions[client_id]
        assert len(session["conversation_history"]) == 1
    
    def test_get_server_stats(self, gateway):
        """Test server statistics generation."""
        # Create mock active connections
        gateway.connection_manager.get_active_connections = Mock(return_value=["client1", "client2"])
        gateway.connection_manager.get_connection_quality = Mock(side_effect=[
            ConnectionQuality.GOOD,
            ConnectionQuality.EXCELLENT
        ])
        
        # Create active sessions with conversation history
        gateway.active_sessions = {
            "client1": {"conversation_history": [{"test": 1}, {"test": 2}]},
            "client2": {"conversation_history": [{"test": 3}]}
        }
        
        # Mock the event loop time function
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_loop.time.return_value = 1234567890.0
            mock_get_loop.return_value = mock_loop
            
            stats = gateway.get_server_stats()
        
        # Check stats structure
        assert "active_connections" in stats
        assert "active_sessions" in stats
        assert "connection_quality_distribution" in stats
        assert "total_interactions" in stats
        
        # Check values
        assert stats["active_connections"] == 2
        assert stats["active_sessions"] == 2
        assert stats["total_interactions"] == 3
        assert stats["connection_quality_distribution"]["good"] == 1
        assert stats["connection_quality_distribution"]["excellent"] == 1
    
    @pytest.mark.asyncio
    async def test_send_error_response(self, gateway):
        """Test error response sending."""
        client_id = "test-client-123"
        
        # Mock connection manager
        gateway.connection_manager.send_audio_data = AsyncMock(return_value=True)
        
        await gateway._send_error_response(client_id, "TEST_ERROR", "Test error message")
        
        # Check error response was sent
        gateway.connection_manager.send_audio_data.assert_called_once()
        
        # Verify error message content
        call_args = gateway.connection_manager.send_audio_data.call_args
        message_bytes = call_args[0][1]  # Second argument (audio_data)
        message_str = message_bytes.decode('utf-8')
        message_dict = json.loads(message_str)
        
        assert message_dict["type"] == "error"
        assert message_dict["error_code"] == "TEST_ERROR"
        assert message_dict["error_message"] == "Test error message"
    
    @pytest.mark.asyncio
    async def test_handle_client_info(self, gateway):
        """Test client information handling."""
        client_id = "test-client-123"
        
        # Create active session
        gateway.active_sessions[client_id] = {
            "client_id": client_id,
            "language": "en"
        }
        
        # Mock connection manager
        gateway.connection_manager.send_audio_data = AsyncMock(return_value=True)
        
        message_data = {
            "type": "client_info",
            "info": {
                "language": "ta",
                "device_type": "mobile",
                "app_version": "1.0.0"
            }
        }
        
        await gateway._handle_client_info(client_id, message_data)
        
        # Check session was updated
        session = gateway.active_sessions[client_id]
        assert session["language"] == "ta"
        assert session["client_info"]["device_type"] == "mobile"
        assert session["client_info"]["app_version"] == "1.0.0"
        
        # Check acknowledgment was sent
        gateway.connection_manager.send_audio_data.assert_called_once()


class TestAudioProcessor:
    """Test cases for AudioProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create an AudioProcessor instance for testing."""
        return AudioProcessor()
    
    def test_processor_initialization(self, processor):
        """Test audio processor initialization."""
        assert processor.sample_rate == 16000
        assert processor.channels == 1
        assert processor.bit_depth == 16
        assert processor.min_quality_score == 0.3
        assert processor.good_quality_score == 0.7
    
    @pytest.mark.asyncio
    async def test_assess_audio_quality(self, processor):
        """Test audio quality assessment."""
        # Create test audio data (1 second of silence)
        test_audio = b'\x00' * (16000 * 2)  # 16kHz, 16-bit, 1 second
        
        assessment = await processor.assess_audio_quality(test_audio)
        
        # Check assessment structure
        assert "overall_score" in assessment
        assert "quality_level" in assessment
        assert "metrics" in assessment
        assert "recommendations" in assessment
        
        # Check metrics
        metrics = assessment["metrics"]
        assert "volume_level" in metrics
        assert "noise_level" in metrics
        assert "speech_energy_ratio" in metrics
        assert "dynamic_range" in metrics
        
        # Check quality level is valid
        assert assessment["quality_level"] in ["good", "acceptable", "poor"]
    
    @pytest.mark.asyncio
    async def test_enhance_audio(self, processor):
        """Test audio enhancement."""
        # Create test audio data
        test_audio = b'\x00' * (16000 * 2)
        
        # Create quality assessment
        quality_assessment = {
            "quality_level": "poor",
            "metrics": {
                "noise_level": 0.4,
                "volume_level": 0.3,
                "dynamic_range": 0.9,
                "low_freq_noise": 0.3
            }
        }
        
        enhanced_audio = await processor.enhance_audio(test_audio, quality_assessment)
        
        # Check that enhanced audio is returned
        assert isinstance(enhanced_audio, bytes)
        assert len(enhanced_audio) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires ffmpeg installation for audio compression")
    async def test_compress_audio(self, processor):
        """Test audio compression."""
        # Create test audio data
        test_audio = b'\x00' * (16000 * 2)  # 1 second of silence
        
        compressed_audio = await processor.compress_audio(test_audio, 64)
        
        # Check compression worked
        assert isinstance(compressed_audio, bytes)
        assert len(compressed_audio) > 0
        # Compressed audio should typically be smaller (though silence might not compress much)
    
    @pytest.mark.asyncio
    async def test_convert_format(self, processor):
        """Test audio format conversion."""
        # Create test audio data
        test_audio = b'\x00' * (16000 * 2)
        
        converted_audio = await processor.convert_format(test_audio, "raw", "raw")
        
        # Check conversion worked
        assert isinstance(converted_audio, bytes)
        assert len(converted_audio) > 0


class TestConnectionManager:
    """Test cases for ConnectionManager."""
    
    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance for testing."""
        return ConnectionManager()
    
    def test_manager_initialization(self, manager):
        """Test connection manager initialization."""
        assert len(manager.active_connections) == 0
        assert len(manager.connection_stats) == 0
        assert manager.max_connections == 1000
        assert manager.connection_timeout == 300
    
    @pytest.mark.asyncio
    async def test_start_and_stop_manager(self, manager):
        """Test starting and stopping the connection manager."""
        await manager.start()
        
        # Check background tasks were created
        assert manager.bandwidth_monitor_task is not None
        assert manager.cleanup_task is not None
        
        await manager.stop()
        
        # Check tasks were cancelled and connections cleared
        assert len(manager.active_connections) == 0
    
    def test_get_active_connections(self, manager):
        """Test getting active connections."""
        # Initially empty
        connections = manager.get_active_connections()
        assert connections == []
        
        # Add mock connection
        mock_websocket = Mock()
        manager.active_connections["test-client"] = Mock(websocket=mock_websocket)
        
        connections = manager.get_active_connections()
        assert connections == ["test-client"]
    
    def test_get_connection_quality(self, manager):
        """Test getting connection quality."""
        # Non-existent client
        quality = manager.get_connection_quality("non-existent")
        assert quality is None
        
        # Add mock connection with quality
        mock_connection = Mock()
        mock_connection.metrics.quality_level = ConnectionQuality.GOOD
        manager.active_connections["test-client"] = mock_connection
        
        quality = manager.get_connection_quality("test-client")
        assert quality == ConnectionQuality.GOOD