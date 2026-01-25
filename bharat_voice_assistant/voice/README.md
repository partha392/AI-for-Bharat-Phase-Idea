# Voice Interface Gateway

The Voice Interface Gateway is the core component of the Bharat Voice Assistant that handles real-time audio streaming, processing, and WebSocket connections for voice-first interactions.

## Overview

This module implements:

- **WebSocket Server**: Real-time audio streaming with client connection management
- **Audio Processing**: Quality assessment, enhancement, compression, and format conversion
- **Connection Management**: Bandwidth detection, quality monitoring, and adaptive streaming
- **Session Management**: Multi-turn conversation handling with context preservation

## Components

### VoiceInterfaceGateway

The main gateway class that coordinates all voice processing operations.

**Key Features:**
- WebSocket server for real-time audio streaming
- Message routing and session management
- Integration with audio processing and connection management
- RESTful API endpoints for monitoring and control

**Usage:**
```python
from bharat_voice_assistant.voice import VoiceInterfaceGateway

# Create and start the gateway
gateway = VoiceInterfaceGateway(host="0.0.0.0", port=8001)
await gateway.start()

# Gateway is now ready to accept WebSocket connections
# at ws://0.0.0.0:8001
```

### AudioProcessor

Handles all audio processing operations including quality assessment and enhancement.

**Key Features:**
- Audio quality assessment with multiple metrics
- Noise reduction and audio enhancement
- Audio compression for bandwidth optimization
- Format conversion between different audio formats

**Usage:**
```python
from bharat_voice_assistant.voice.audio_processor import AudioProcessor

processor = AudioProcessor()

# Assess audio quality
quality = await processor.assess_audio_quality(audio_bytes)

# Enhance audio based on quality assessment
enhanced_audio = await processor.enhance_audio(audio_bytes, quality)

# Compress audio for low-bandwidth connections
compressed_audio = await processor.compress_audio(audio_bytes, target_bitrate=64)
```

### ConnectionManager

Manages WebSocket connections and adapts to varying network conditions.

**Key Features:**
- Connection quality monitoring and bandwidth detection
- Adaptive audio streaming based on network conditions
- Connection lifecycle management
- Quality metrics collection and analysis

**Usage:**
```python
from bharat_voice_assistant.voice.connection_manager import ConnectionManager

manager = ConnectionManager()
await manager.start()

# Connect a client
success = await manager.connect_client(websocket, client_id)

# Send audio data with adaptive quality
await manager.send_audio_data(client_id, audio_bytes, metadata)
```

## WebSocket Protocol

The gateway uses a JSON-based message protocol over WebSocket connections.

### Message Types

#### Client to Server Messages

**Start Session:**
```json
{
  "type": "start_session",
  "config": {
    "language": "hi",
    "audio_format": "raw"
  }
}
```

**Audio Data:**
```json
{
  "type": "audio_data",
  "data": "hex_encoded_audio_bytes",
  "metadata": {
    "format": "raw",
    "sample_rate": 16000
  }
}
```

**Client Info:**
```json
{
  "type": "client_info",
  "info": {
    "language": "hi",
    "device_type": "mobile",
    "app_version": "1.0.0"
  }
}
```

**Ping:**
```json
{
  "type": "ping",
  "timestamp": 1234567890.0
}
```

**End Session:**
```json
{
  "type": "end_session"
}
```

#### Server to Client Messages

**Session Started:**
```json
{
  "type": "session_started",
  "session_id": "client-uuid",
  "config": {...},
  "timestamp": 1234567890.0
}
```

**Voice Response:**
```json
{
  "type": "voice_response",
  "text": "Response text",
  "language": "hi",
  "confidence": 0.85,
  "audio_quality": "good",
  "timestamp": 1234567890.0
}
```

**Connection Status:**
```json
{
  "type": "connection_status",
  "status": {
    "quality": "good",
    "bandwidth_kbps": 128.5,
    "recommended_settings": {...}
  },
  "timestamp": 1234567890.0
}
```

**Error:**
```json
{
  "type": "error",
  "error_code": "AUDIO_PROCESSING_ERROR",
  "error_message": "Failed to process audio",
  "timestamp": 1234567890.0
}
```

## Audio Quality Assessment

The audio processor evaluates multiple quality metrics:

- **Volume Level**: RMS energy level of the audio signal
- **Noise Level**: Estimated background noise relative to signal
- **Speech Energy Ratio**: Energy in speech frequency range (300-3400Hz)
- **Dynamic Range**: Difference between loudest and quietest parts
- **Low Frequency Noise**: Energy below 100Hz (typically unwanted)
- **Clipping Ratio**: Percentage of samples that are clipped

Quality levels are classified as:
- **Good**: Overall score ≥ 0.7
- **Acceptable**: Overall score ≥ 0.3
- **Poor**: Overall score < 0.3

## Connection Quality Management

The connection manager monitors and adapts to network conditions:

### Quality Levels

- **Excellent**: >256 kbps, <200ms latency
- **Good**: >64 kbps, <500ms latency  
- **Fair**: >32 kbps, <1000ms latency
- **Poor**: >16 kbps, any latency
- **Critical**: <16 kbps

### Adaptive Streaming

Audio quality is automatically adjusted based on connection:

- **Excellent/Good**: High-quality uncompressed audio
- **Fair**: 64 kbps compressed audio
- **Poor**: 32 kbps compressed audio
- **Critical**: 16 kbps compressed audio with text fallback

## API Endpoints

The voice gateway provides REST API endpoints for monitoring and control:

- `GET /voice/status` - Gateway status and statistics
- `GET /voice/connections` - Active connection information
- `GET /voice/connections/{client_id}/stats` - Detailed connection statistics
- `POST /voice/test-audio-processing` - Test audio processing capabilities
- `POST /voice/restart` - Restart the voice gateway
- `GET /voice/health` - Health check endpoint

## Configuration

The voice gateway uses configuration from `bharat_voice_assistant.core.config`:

```python
# Voice processing settings
recognition_confidence_threshold = 0.7
max_recognition_attempts = 3
noise_reduction_enabled = True

# Network settings
low_bandwidth_threshold = 64  # kbps
high_quality_threshold = 256  # kbps
connection_timeout = 30  # seconds

# Audio settings
sample_rate = 16000  # Hz
channels = 1  # Mono
bit_depth = 16  # bits
```

## Error Handling

The gateway implements comprehensive error handling:

- **VoiceGatewayError**: Gateway startup/shutdown failures
- **AudioProcessingError**: Audio processing failures
- **ConnectionError**: WebSocket connection issues
- **BandwidthError**: Network bandwidth limitations

All errors include detailed context for debugging and monitoring.

## Testing

Run the test suite:

```bash
python -m pytest tests/test_voice_interface_gateway.py -v
```

Run the demonstration:

```bash
python examples/voice_gateway_demo.py
```

## Requirements

- Python 3.8+
- WebSockets library for real-time communication
- PyDub for audio processing
- NumPy and SciPy for signal processing
- Optional: FFmpeg for audio compression (MP3 encoding)

## Integration

The voice gateway integrates with:

- **AWS Transcribe**: Speech recognition (future implementation)
- **AWS Polly**: Text-to-speech synthesis (future implementation)
- **Language Processing Engine**: Intent recognition and NLP
- **Scheme Discovery Engine**: Government scheme matching
- **Grievance Management System**: Complaint filing and tracking

## Performance

The gateway is designed for high performance:

- Supports 1000+ concurrent connections
- Sub-second audio processing latency
- Adaptive quality based on network conditions
- Efficient memory usage with streaming processing
- Background monitoring and cleanup tasks

## Security

Security features include:

- WebSocket connection validation
- Rate limiting and connection limits
- Audio data encryption (when configured)
- Session timeout and cleanup
- Input validation and sanitization