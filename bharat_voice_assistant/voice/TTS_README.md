# AWS Polly Text-to-Speech Integration

This module provides comprehensive text-to-speech functionality for the Bharat Voice Assistant using AWS Polly with support for Indian voices, regional accents, and bandwidth optimization.

## Features

### 🎤 Indian Voice Support
- **Hindi**: Aditi (Standard/Neural), Kajal (Neural)
- **English (India)**: Raveena (Standard), Aria (Neural)
- **Regional Languages**: Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi
- **Regional Accents**: Optimized pronunciation for different Indian regions

### 🌐 Bandwidth Optimization
- **Dynamic Quality Adjustment**: Automatically adjusts audio quality based on connection speed
- **Compression Levels**: 
  - Excellent: 128 kbps, 22050 Hz
  - Good: 64 kbps, 16000 Hz
  - Medium: 32 kbps, 16000 Hz
  - Poor: 16 kbps, 8000 Hz
- **Format Support**: MP3, OGG Vorbis, PCM

### 🎯 SSML Enhancement
- **Pronunciation Hints**: Government terms and common phrases
- **Prosody Control**: Speech rate, volume, and emphasis
- **Language-Specific**: Hindi and Indian English optimizations

## Usage

### Basic Synthesis

```python
from bharat_voice_assistant.voice.text_to_speech import (
    TextToSpeechSynthesizer,
    SynthesisConfig,
    AudioFormat,
    SpeechRate
)

# Initialize synthesizer
synthesizer = TextToSpeechSynthesizer()

# Create configuration
config = SynthesisConfig(
    voice_id="Aditi",
    language_code="hi-IN",
    audio_format=AudioFormat.MP3,
    speech_rate=SpeechRate.MEDIUM
)

# Synthesize speech
text = "नमस्ते! मैं भारत वॉयस असिस्टेंट हूँ।"
result = await synthesizer.synthesize_speech(text, config)

# Save audio
with open("output.mp3", "wb") as f:
    f.write(result.audio_data)
```

### Automatic Configuration

```python
# Create optimized config for connection speed
config = synthesizer.create_synthesis_config(
    language="hi",
    connection_speed="poor",  # Automatically optimizes for bandwidth
    prefer_neural=True
)

result = await synthesizer.synthesize_speech(text, config, "poor")
```

### Voice Selection

```python
# Get best voice for language
voice = synthesizer.get_voice_for_language("ta", prefer_neural=True)
print(f"Selected: {voice.voice_id} - {voice.regional_accent}")

# List available voices
voices = synthesizer.get_available_voices("hi")
for voice in voices:
    print(f"{voice.voice_id}: {voice.language_name} ({voice.gender.value})")
```

### Testing Voices

```python
# Test specific voice
success = await synthesizer.test_voice_synthesis("Aditi", "hi-IN")
print(f"Voice test: {'PASSED' if success else 'FAILED'}")
```

## Configuration Classes

### SynthesisConfig
```python
@dataclass
class SynthesisConfig:
    voice_id: str                    # AWS Polly voice ID
    language_code: str               # Language code (e.g., "hi-IN")
    audio_format: AudioFormat        # Output format
    sample_rate: str                 # Sample rate ("8000", "16000", "22050")
    speech_rate: SpeechRate          # Speaking speed
    volume: str                      # Volume level
    engine: VoiceEngine              # Standard or Neural
    enable_ssml: bool                # Enable SSML markup
    compression_quality: int         # Compression bitrate
    max_characters: int              # Text length limit
```

### IndianVoice
```python
@dataclass
class IndianVoice:
    voice_id: str                    # Voice identifier
    language_code: str               # Language code
    language_name: str               # Human-readable language name
    gender: VoiceGender              # Male/Female
    engine: VoiceEngine              # Standard/Neural
    supports_neural: bool            # Neural engine support
    regional_accent: str             # Regional accent description
```

### SynthesisResult
```python
@dataclass
class SynthesisResult:
    audio_data: bytes                # Synthesized audio
    audio_format: str                # Format used
    sample_rate: int                 # Sample rate used
    duration_ms: int                 # Audio duration
    character_count: int             # Input text length
    processing_time_ms: int          # Synthesis time
    voice_id: str                    # Voice used
    language: str                    # Language used
    compressed_size: int             # Compressed audio size
    compression_ratio: float         # Compression ratio
```

## Supported Languages

| Language | Code | Voice | Neural | Regional Accent |
|----------|------|-------|--------|-----------------|
| Hindi | hi-IN | Aditi, Kajal | ✓ | Standard/Modern Hindi |
| English (India) | en-IN | Raveena, Aria | ✓ | Indian English |
| Tamil | ta-IN | Aditi | ✗ | Tamil |
| Telugu | te-IN | Aditi | ✗ | Telugu |
| Bengali | bn-IN | Aditi | ✗ | Bengali |
| Marathi | mr-IN | Aditi | ✗ | Marathi |
| Gujarati | gu-IN | Aditi | ✗ | Gujarati |
| Kannada | kn-IN | Aditi | ✗ | Kannada |
| Malayalam | ml-IN | Aditi | ✗ | Malayalam |
| Punjabi | pa-IN | Aditi | ✗ | Punjabi |

## Bandwidth Optimization

The system automatically adjusts audio quality based on connection speed:

### Connection Speed Mapping
- **Excellent/Good**: High quality (128-64 kbps, Neural voices)
- **Medium**: Medium quality (64 kbps, Standard/Neural)
- **Slow**: Low quality (32 kbps, Standard only)
- **Poor/Very Poor**: Minimal quality (16 kbps, 8kHz, Standard only)

### Compression Features
- **Automatic Format Selection**: MP3 for maximum compression
- **Sample Rate Adjustment**: Lower rates for poor connections
- **Bitrate Optimization**: Dynamic bitrate based on network conditions
- **Engine Selection**: Standard engine for poor connections to reduce processing

## SSML Enhancements

### Government Terms (Hindi)
```python
# Automatic pronunciation improvements for:
"सरकार" → Enhanced pronunciation with IPA phonemes
"योजना" → Proper scheme pronunciation
"आवेदन" → Application pronunciation
"शिकायत" → Complaint pronunciation
```

### Indian English Terms
```python
# Optimized pronunciation for:
"scheme" → Indian English pronunciation
"government" → Local pronunciation patterns
"application" → Regional accent adaptation
"grievance" → Proper Indian English pronunciation
```

### Prosody Control
```xml
<speak>
  <prosody rate="medium" volume="medium">
    Your text with controlled speech rate and volume
  </prosody>
</speak>
```

## Error Handling

The module provides comprehensive error handling:

```python
from bharat_voice_assistant.core.exceptions import TextToSpeechError

try:
    result = await synthesizer.synthesize_speech(text, config)
except TextToSpeechError as e:
    print(f"TTS Error: {e.error_code} - {e.message}")
    print(f"Context: {e.context}")
```

### Common Error Codes
- `EMPTY_TEXT`: No text provided for synthesis
- `TEXT_TOO_LONG`: Text exceeds character limit
- `NO_AUDIO_STREAM`: AWS Polly returned no audio
- `SYNTHESIS_FAILED`: General synthesis failure

## Integration with Voice Gateway

The TTS synthesizer is automatically integrated with the Voice Interface Gateway:

```python
# In gateway.py
self.tts_synthesizer = TextToSpeechSynthesizer()

# Automatic synthesis in responses
synthesis_config = self.tts_synthesizer.create_synthesis_config(
    language=language,
    connection_speed=connection_speed,
    prefer_neural=True
)

synthesis_result = await self.tts_synthesizer.synthesize_speech(
    response_text, synthesis_config, connection_speed
)
```

## Performance Considerations

### Optimization Tips
1. **Cache Configurations**: Reuse `SynthesisConfig` objects
2. **Batch Processing**: Process multiple texts in sequence
3. **Connection Awareness**: Always provide connection speed for optimization
4. **Voice Selection**: Use `get_voice_for_language()` for optimal voice selection

### Monitoring
- Processing time is tracked in `SynthesisResult.processing_time_ms`
- Compression ratios help monitor bandwidth savings
- Audio duration helps estimate playback time

## Testing

Run the comprehensive test suite:

```bash
# Unit tests
python -m pytest tests/test_text_to_speech.py -v

# Integration tests (requires AWS credentials)
python -m pytest tests/test_text_to_speech.py -m integration -v

# Demo script
python examples/polly_tts_demo.py
```

## Requirements

### AWS Configuration
- AWS credentials configured (IAM role, environment variables, or AWS CLI)
- AWS Polly service access
- S3 bucket for temporary audio storage (if needed)

### Dependencies
- `boto3` - AWS SDK
- `pydub` - Audio processing
- `asyncio` - Async support

### Optional Dependencies
- `ffmpeg` - For advanced audio processing (compression, format conversion)
- `numpy` - For audio analysis
- `scipy` - For audio processing

## Troubleshooting

### Common Issues

1. **AWS Credentials Not Found**
   ```
   Solution: Configure AWS credentials via IAM role, environment variables, or AWS CLI
   ```

2. **Voice Not Available**
   ```python
   # Check available voices
   voices = synthesizer.get_available_voices()
   print([v.voice_id for v in voices])
   ```

3. **Audio Quality Issues**
   ```python
   # Test different connection speeds
   for speed in ["excellent", "good", "medium", "slow", "poor"]:
       config = synthesizer.create_synthesis_config("hi", speed)
       # Test synthesis...
   ```

4. **SSML Errors**
   ```python
   # Disable SSML if having issues
   config.enable_ssml = False
   ```

### Debug Mode
Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('bharat_voice_assistant.voice.text_to_speech').setLevel(logging.DEBUG)
```

## Contributing

When adding new voices or languages:

1. Update `indian_voices` dictionary in `TextToSpeechSynthesizer`
2. Add language mapping in `default_voices`
3. Add pronunciation hints in `_add_*_pronunciation_hints` methods
4. Update test cases
5. Update this documentation

## License

This module is part of the Bharat Voice Assistant project and follows the same licensing terms.