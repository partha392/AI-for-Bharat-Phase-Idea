"""
Voice processing components for the Bharat Voice Assistant.

This package contains all voice-related functionality including:
- Voice interface gateway for WebSocket audio streaming
- Audio quality assessment and enhancement
- Connection management for low-bandwidth scenarios
- Speech recognition and text-to-speech integration
- AWS Transcribe integration with Indian language models
"""

from .gateway import VoiceInterfaceGateway
from .audio_processor import AudioProcessor
from .connection_manager import ConnectionManager
from .speech_recognition import (
    SpeechRecognizer,
    RecognitionConfig,
    RecognitionResult,
    RecognitionMode,
    LanguageModel
)
from .text_to_speech import (
    TextToSpeechSynthesizer,
    SynthesisConfig,
    SynthesisResult,
    IndianVoice,
    VoiceGender,
    AudioFormat,
    SpeechRate,
    VoiceEngine
)
from .bandwidth_optimizer import (
    BandwidthOptimizer,
    CompressionLevel,
    ContentPriority,
    CompressionSettings,
    ProgressiveChunk,
    BandwidthProfile
)
from .audio_enhancements import (
    AudioEnhancementSystem,
    AdvancedNoiseCancellation,
    AutoVolumeClarity,
    ResponseTimeOptimizer,
    SpeakingPaceAdapter,
    AudioEnhancementConfig,
    SpeakingPaceProfile,
    NoiseType,
    AudioQuality
)

__all__ = [
    "VoiceInterfaceGateway",
    "AudioProcessor", 
    "ConnectionManager",
    "SpeechRecognizer",
    "RecognitionConfig",
    "RecognitionResult",
    "RecognitionMode",
    "LanguageModel",
    "TextToSpeechSynthesizer",
    "SynthesisConfig",
    "SynthesisResult",
    "IndianVoice",
    "VoiceGender",
    "AudioFormat",
    "SpeechRate",
    "VoiceEngine",
    "BandwidthOptimizer",
    "CompressionLevel",
    "ContentPriority",
    "CompressionSettings",
    "ProgressiveChunk",
    "BandwidthProfile",
    "AudioEnhancementSystem",
    "AdvancedNoiseCancellation",
    "AutoVolumeClarity",
    "ResponseTimeOptimizer",
    "SpeakingPaceAdapter",
    "AudioEnhancementConfig",
    "SpeakingPaceProfile",
    "NoiseType",
    "AudioQuality"
]