"""
AWS Polly integration for text-to-speech synthesis in the Bharat Voice Assistant.

This module provides text-to-speech functionality using AWS Polly with
Indian voices, regional accents, audio compression for bandwidth optimization,
and dynamic quality adjustment based on connection speed.
"""

import asyncio
import io
import uuid
import time
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import boto3
from botocore.exceptions import ClientError
from pydub import AudioSegment

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import TextToSpeechError, handle_aws_error
from bharat_voice_assistant.core.aws_client import aws_clients, safe_aws_call

logger = get_logger(__name__)


class VoiceGender(Enum):
    """Voice gender options."""
    MALE = "Male"
    FEMALE = "Female"


class AudioFormat(Enum):
    """Supported audio output formats."""
    MP3 = "mp3"
    OGG_VORBIS = "ogg_vorbis"
    PCM = "pcm"


class SpeechRate(Enum):
    """Speech rate options."""
    X_SLOW = "x-slow"
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
    X_FAST = "x-fast"


class VoiceEngine(Enum):
    """AWS Polly voice engines."""
    STANDARD = "standard"
    NEURAL = "neural"


@dataclass
class IndianVoice:
    """Configuration for Indian voices in AWS Polly."""
    voice_id: str
    language_code: str
    language_name: str
    gender: VoiceGender
    engine: VoiceEngine
    supports_neural: bool = False
    regional_accent: Optional[str] = None


@dataclass
class SynthesisConfig:
    """Configuration for text-to-speech synthesis."""
    voice_id: str
    language_code: str
    audio_format: AudioFormat = AudioFormat.MP3
    sample_rate: str = "16000"
    speech_rate: SpeechRate = SpeechRate.MEDIUM
    volume: str = "medium"
    engine: VoiceEngine = VoiceEngine.STANDARD
    enable_ssml: bool = True
    compression_quality: Optional[int] = None  # For bandwidth optimization
    max_characters: int = 3000  # AWS Polly limit


@dataclass
class SynthesisResult:
    """Result of text-to-speech synthesis."""
    audio_data: bytes
    audio_format: str
    sample_rate: int
    duration_ms: int
    character_count: int
    processing_time_ms: int
    voice_id: str
    language: str
    compressed_size: Optional[int] = None
    compression_ratio: Optional[float] = None


class TextToSpeechSynthesizer:
    """
    AWS Polly-based text-to-speech synthesizer with Indian voice support.
    """
    
    def __init__(self):
        """Initialize the text-to-speech synthesizer."""
        self.polly_client = aws_clients.polly
        
        # Indian voices configuration
        self.indian_voices = {
            # Hindi voices
            "Aditi": IndianVoice(
                voice_id="Aditi",
                language_code="hi-IN",
                language_name="Hindi",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=True,
                regional_accent="Standard Hindi"
            ),
            "Kajal": IndianVoice(
                voice_id="Kajal",
                language_code="hi-IN", 
                language_name="Hindi",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.NEURAL,
                supports_neural=True,
                regional_accent="Modern Hindi"
            ),
            
            # English (Indian) voices
            "Raveena": IndianVoice(
                voice_id="Raveena",
                language_code="en-IN",
                language_name="English (India)",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Indian English"
            ),
            "Aria": IndianVoice(
                voice_id="Aria",
                language_code="en-IN",
                language_name="English (India)",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.NEURAL,
                supports_neural=True,
                regional_accent="Indian English"
            ),
            
            # Tamil voices (using closest available)
            "Aditi_Tamil": IndianVoice(
                voice_id="Aditi",  # Aditi supports multiple languages
                language_code="ta-IN",
                language_name="Tamil",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Tamil"
            ),
            
            # Telugu voices
            "Aditi_Telugu": IndianVoice(
                voice_id="Aditi",
                language_code="te-IN",
                language_name="Telugu",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Telugu"
            ),
            
            # Bengali voices
            "Aditi_Bengali": IndianVoice(
                voice_id="Aditi",
                language_code="bn-IN",
                language_name="Bengali",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Bengali"
            ),
            
            # Marathi voices
            "Aditi_Marathi": IndianVoice(
                voice_id="Aditi",
                language_code="mr-IN",
                language_name="Marathi",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Marathi"
            ),
            
            # Gujarati voices
            "Aditi_Gujarati": IndianVoice(
                voice_id="Aditi",
                language_code="gu-IN",
                language_name="Gujarati",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Gujarati"
            ),
            
            # Kannada voices
            "Aditi_Kannada": IndianVoice(
                voice_id="Aditi",
                language_code="kn-IN",
                language_name="Kannada",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Kannada"
            ),
            
            # Malayalam voices
            "Aditi_Malayalam": IndianVoice(
                voice_id="Aditi",
                language_code="ml-IN",
                language_name="Malayalam",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Malayalam"
            ),
            
            # Punjabi voices
            "Aditi_Punjabi": IndianVoice(
                voice_id="Aditi",
                language_code="pa-IN",
                language_name="Punjabi",
                gender=VoiceGender.FEMALE,
                engine=VoiceEngine.STANDARD,
                supports_neural=False,
                regional_accent="Punjabi"
            )
        }
        
        # Default voice mapping by language
        self.default_voices = {
            "hi": "Aditi",
            "en": "Raveena",
            "ta": "Aditi_Tamil",
            "te": "Aditi_Telugu",
            "bn": "Aditi_Bengali",
            "mr": "Aditi_Marathi",
            "gu": "Aditi_Gujarati",
            "kn": "Aditi_Kannada",
            "ml": "Aditi_Malayalam",
            "pa": "Aditi_Punjabi"
        }
        
        # Bandwidth optimization settings
        self.compression_settings = {
            "high_quality": {"bitrate": 128, "sample_rate": "22050"},
            "medium_quality": {"bitrate": 64, "sample_rate": "16000"},
            "low_quality": {"bitrate": 32, "sample_rate": "8000"},
            "very_low_quality": {"bitrate": 16, "sample_rate": "8000"}
        }
        
        logger.info("TextToSpeechSynthesizer initialized with Indian voices")
    
    async def synthesize_speech(self, text: str, synthesis_config: SynthesisConfig,
                              connection_speed: Optional[str] = None) -> SynthesisResult:
        """
        Synthesize speech from text using AWS Polly.
        
        Args:
            text: Text to synthesize
            synthesis_config: Synthesis configuration
            connection_speed: Connection speed for quality adjustment
            
        Returns:
            SynthesisResult with audio data and metadata
        """
        start_time = time.time()
        
        try:
            # Validate input
            if not text or not text.strip():
                raise TextToSpeechError(
                    "Empty text provided for synthesis",
                    error_code="EMPTY_TEXT"
                )
            
            if len(text) > synthesis_config.max_characters:
                raise TextToSpeechError(
                    f"Text too long: {len(text)} characters (max: {synthesis_config.max_characters})",
                    error_code="TEXT_TOO_LONG",
                    context={"character_count": len(text), "max_characters": synthesis_config.max_characters}
                )
            
            # Adjust quality based on connection speed
            adjusted_config = await self._adjust_quality_for_connection(
                synthesis_config, connection_speed
            )
            
            # Prepare text for synthesis (add SSML if enabled)
            processed_text = await self._prepare_text_for_synthesis(text, adjusted_config)
            
            # Perform synthesis
            audio_data = await self._synthesize_with_polly(processed_text, adjusted_config)
            
            # Apply compression if needed
            compressed_audio, compression_info = await self._apply_compression(
                audio_data, adjusted_config
            )
            
            # Calculate duration
            duration_ms = await self._calculate_audio_duration(compressed_audio, adjusted_config)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = SynthesisResult(
                audio_data=compressed_audio,
                audio_format=adjusted_config.audio_format.value,
                sample_rate=int(adjusted_config.sample_rate),
                duration_ms=duration_ms,
                character_count=len(text),
                processing_time_ms=processing_time,
                voice_id=adjusted_config.voice_id,
                language=adjusted_config.language_code,
                compressed_size=compression_info.get("compressed_size"),
                compression_ratio=compression_info.get("compression_ratio")
            )
            
            logger.debug(f"Speech synthesis completed in {processing_time}ms "
                        f"for {len(text)} characters")
            
            return result
            
        except TextToSpeechError:
            # Re-raise specific TTS errors without wrapping
            raise
        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            raise TextToSpeechError(
                "Failed to synthesize speech",
                error_code="SYNTHESIS_FAILED",
                context={
                    "text_length": len(text) if text else 0,
                    "voice_id": synthesis_config.voice_id,
                    "language": synthesis_config.language_code,
                    "error": str(e)
                }
            )
    
    async def _adjust_quality_for_connection(self, synthesis_config: SynthesisConfig,
                                           connection_speed: Optional[str]) -> SynthesisConfig:
        """
        Adjust synthesis quality based on connection speed.
        
        This implements dynamic quality adjustment for bandwidth optimization.
        """
        try:
            if not connection_speed:
                return synthesis_config
            
            # Create a copy of the config to modify
            adjusted_config = SynthesisConfig(
                voice_id=synthesis_config.voice_id,
                language_code=synthesis_config.language_code,
                audio_format=synthesis_config.audio_format,
                sample_rate=synthesis_config.sample_rate,
                speech_rate=synthesis_config.speech_rate,
                volume=synthesis_config.volume,
                engine=synthesis_config.engine,
                enable_ssml=synthesis_config.enable_ssml,
                compression_quality=synthesis_config.compression_quality,
                max_characters=synthesis_config.max_characters
            )
            
            # Adjust based on connection speed
            if connection_speed in ["very_poor", "poor"]:
                # Use lowest quality for poor connections
                settings = self.compression_settings["very_low_quality"]
                adjusted_config.audio_format = AudioFormat.MP3  # Most compressed
                adjusted_config.sample_rate = settings["sample_rate"]
                adjusted_config.compression_quality = settings["bitrate"]
                adjusted_config.engine = VoiceEngine.STANDARD  # Faster processing
                
                logger.info(f"Adjusted synthesis quality for {connection_speed} connection")
                
            elif connection_speed == "slow":
                # Use medium-low quality
                settings = self.compression_settings["low_quality"]
                adjusted_config.audio_format = AudioFormat.MP3
                adjusted_config.sample_rate = settings["sample_rate"]
                adjusted_config.compression_quality = settings["bitrate"]
                
            elif connection_speed == "medium":
                # Use medium quality
                settings = self.compression_settings["medium_quality"]
                adjusted_config.sample_rate = settings["sample_rate"]
                adjusted_config.compression_quality = settings["bitrate"]
                
            # For "good" or "excellent" connections, use original settings
            
            return adjusted_config
            
        except Exception as e:
            logger.warning(f"Failed to adjust quality for connection speed: {e}")
            return synthesis_config
    
    async def _prepare_text_for_synthesis(self, text: str, 
                                        synthesis_config: SynthesisConfig) -> str:
        """
        Prepare text for synthesis, adding SSML markup if enabled.
        """
        try:
            if not synthesis_config.enable_ssml:
                return text
            
            # Add SSML markup for better pronunciation and pacing
            ssml_text = f'<speak>'
            
            # Add prosody controls for speech rate and volume
            ssml_text += f'<prosody rate="{synthesis_config.speech_rate.value}" '
            ssml_text += f'volume="{synthesis_config.volume}">'
            
            # Add language-specific pronunciation hints
            if synthesis_config.language_code.startswith("hi"):
                # Add Hindi-specific SSML enhancements
                ssml_text += self._add_hindi_pronunciation_hints(text)
            elif synthesis_config.language_code.startswith("en-IN"):
                # Add Indian English pronunciation hints
                ssml_text += self._add_indian_english_hints(text)
            else:
                # For other Indian languages, use basic text
                ssml_text += text
            
            ssml_text += '</prosody></speak>'
            
            logger.debug("Added SSML markup for enhanced pronunciation")
            return ssml_text
            
        except Exception as e:
            logger.warning(f"Failed to prepare SSML text: {e}")
            return text
    
    def _add_hindi_pronunciation_hints(self, text: str) -> str:
        """Add Hindi-specific pronunciation hints."""
        # Common government terms that need proper pronunciation
        hindi_replacements = {
            "सरकार": '<phoneme alphabet="ipa" ph="sərkaːr">सरकार</phoneme>',
            "योजना": '<phoneme alphabet="ipa" ph="joːdʒnaː">योजना</phoneme>',
            "आवेदन": '<phoneme alphabet="ipa" ph="aːveːdən">आवेदन</phoneme>',
            "शिकायत": '<phoneme alphabet="ipa" ph="ʃɪkaːjət">शिकायत</phoneme>',
        }
        
        processed_text = text
        for original, replacement in hindi_replacements.items():
            processed_text = processed_text.replace(original, replacement)
        
        return processed_text
    
    def _add_indian_english_hints(self, text: str) -> str:
        """Add Indian English pronunciation hints."""
        # Common terms that need Indian English pronunciation
        english_replacements = {
            "scheme": '<phoneme alphabet="ipa" ph="skiːm">scheme</phoneme>',
            "government": '<phoneme alphabet="ipa" ph="ɡʌvərnmənt">government</phoneme>',
            "application": '<phoneme alphabet="ipa" ph="æplɪkeɪʃən">application</phoneme>',
            "grievance": '<phoneme alphabet="ipa" ph="ɡriːvəns">grievance</phoneme>',
        }
        
        processed_text = text
        for original, replacement in english_replacements.items():
            processed_text = processed_text.replace(original, replacement)
        
        return processed_text
    
    async def _synthesize_with_polly(self, text: str, 
                                   synthesis_config: SynthesisConfig) -> bytes:
        """Perform the actual synthesis using AWS Polly."""
        try:
            # Prepare Polly parameters
            polly_params = {
                "Text": text,
                "VoiceId": synthesis_config.voice_id,
                "OutputFormat": synthesis_config.audio_format.value,
                "SampleRate": synthesis_config.sample_rate,
                "Engine": synthesis_config.engine.value
            }
            
            # Add language code if different from voice default
            voice_info = self.indian_voices.get(synthesis_config.voice_id)
            if voice_info and voice_info.language_code != synthesis_config.language_code:
                polly_params["LanguageCode"] = synthesis_config.language_code
            
            # Add SSML text type if SSML is used
            if synthesis_config.enable_ssml and text.startswith('<speak>'):
                polly_params["TextType"] = "ssml"
            
            # Call AWS Polly
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: safe_aws_call(
                    self.polly_client.synthesize_speech,
                    **polly_params
                )
            )
            
            # Extract audio data
            audio_stream = response.get("AudioStream")
            if not audio_stream:
                raise TextToSpeechError(
                    "No audio stream returned from Polly",
                    error_code="NO_AUDIO_STREAM"
                )
            
            audio_data = audio_stream.read()
            
            logger.debug(f"Synthesized {len(audio_data)} bytes of audio data")
            return audio_data
            
        except Exception as e:
            logger.error(f"Polly synthesis failed: {e}")
            raise
    
    async def _apply_compression(self, audio_data: bytes, 
                               synthesis_config: SynthesisConfig) -> Tuple[bytes, Dict[str, Any]]:
        """
        Apply audio compression for bandwidth optimization.
        """
        try:
            original_size = len(audio_data)
            
            # If no compression quality specified, return original
            if not synthesis_config.compression_quality:
                return audio_data, {"compressed_size": original_size, "compression_ratio": 1.0}
            
            # Convert to AudioSegment for processing
            if synthesis_config.audio_format == AudioFormat.MP3:
                audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            elif synthesis_config.audio_format == AudioFormat.OGG_VORBIS:
                audio = AudioSegment.from_ogg(io.BytesIO(audio_data))
            else:
                # PCM format
                audio = AudioSegment.from_raw(
                    io.BytesIO(audio_data),
                    sample_width=2,
                    frame_rate=int(synthesis_config.sample_rate),
                    channels=1
                )
            
            # Apply compression
            compressed_buffer = io.BytesIO()
            
            # Export with specified compression quality
            export_params = {
                "format": "mp3",
                "bitrate": f"{synthesis_config.compression_quality}k",
                "parameters": ["-ac", "1"]  # Mono audio
            }
            
            audio.export(compressed_buffer, **export_params)
            compressed_data = compressed_buffer.getvalue()
            
            # Calculate compression ratio
            compressed_size = len(compressed_data)
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            
            compression_info = {
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio,
                "original_size": original_size,
                "bitrate": synthesis_config.compression_quality
            }
            
            logger.debug(f"Audio compressed: {original_size} -> {compressed_size} bytes "
                        f"(ratio: {compression_ratio:.2f}x)")
            
            return compressed_data, compression_info
            
        except Exception as e:
            logger.warning(f"Audio compression failed, returning original: {e}")
            return audio_data, {"compressed_size": len(audio_data), "compression_ratio": 1.0}
    
    async def _calculate_audio_duration(self, audio_data: bytes, 
                                      synthesis_config: SynthesisConfig) -> int:
        """Calculate audio duration in milliseconds."""
        try:
            # Convert to AudioSegment to get duration
            if synthesis_config.audio_format == AudioFormat.MP3:
                audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            elif synthesis_config.audio_format == AudioFormat.OGG_VORBIS:
                audio = AudioSegment.from_ogg(io.BytesIO(audio_data))
            else:
                # PCM format
                audio = AudioSegment.from_raw(
                    io.BytesIO(audio_data),
                    sample_width=2,
                    frame_rate=int(synthesis_config.sample_rate),
                    channels=1
                )
            
            return len(audio)  # Duration in milliseconds
            
        except Exception as e:
            logger.warning(f"Failed to calculate audio duration: {e}")
            # Estimate based on sample rate and data size
            try:
                sample_rate = int(synthesis_config.sample_rate)
                bytes_per_sample = 2  # 16-bit audio
                duration_seconds = len(audio_data) / (sample_rate * bytes_per_sample)
                return int(duration_seconds * 1000)
            except:
                return 0
    
    def get_voice_for_language(self, language_code: str, 
                             prefer_neural: bool = True) -> Optional[IndianVoice]:
        """
        Get the best voice for a given language.
        
        Args:
            language_code: Language code (e.g., 'hi', 'en', 'ta')
            prefer_neural: Whether to prefer neural voices when available
            
        Returns:
            IndianVoice configuration or None if not supported
        """
        try:
            # Get default voice for language
            default_voice_id = self.default_voices.get(language_code)
            if not default_voice_id:
                return None
            
            voice = self.indian_voices.get(default_voice_id)
            if not voice:
                return None
            
            # If neural is preferred and available, try to find neural version
            if prefer_neural and voice.supports_neural:
                # Look for neural version of the same voice
                for voice_id, voice_config in self.indian_voices.items():
                    if (voice_config.language_code == voice.language_code and
                        voice_config.engine == VoiceEngine.NEURAL):
                        return voice_config
            
            return voice
            
        except Exception as e:
            logger.error(f"Error getting voice for language {language_code}: {e}")
            return None
    
    def get_available_voices(self, language_code: Optional[str] = None) -> List[IndianVoice]:
        """
        Get list of available voices, optionally filtered by language.
        
        Args:
            language_code: Optional language code to filter by
            
        Returns:
            List of available IndianVoice configurations
        """
        try:
            voices = list(self.indian_voices.values())
            
            if language_code:
                # Filter by language
                voices = [
                    voice for voice in voices 
                    if voice.language_code.startswith(language_code)
                ]
            
            return voices
            
        except Exception as e:
            logger.error(f"Error getting available voices: {e}")
            return []
    
    async def test_voice_synthesis(self, voice_id: str, language_code: str) -> bool:
        """
        Test voice synthesis with a sample text.
        
        Args:
            voice_id: Voice ID to test
            language_code: Language code
            
        Returns:
            True if synthesis succeeds, False otherwise
        """
        try:
            test_texts = {
                "hi": "नमस्ते, यह एक परीक्षण है।",
                "en": "Hello, this is a test.",
                "ta": "வணக்கம், இது ஒரு சோதனை.",
                "te": "నమస్కారం, ఇది ఒక పరీక్ష.",
                "bn": "নমস্কার, এটি একটি পরীক্ষা।",
                "mr": "नमस्कार, ही एक चाचणी आहे.",
                "gu": "નમસ્તે, આ એક પરીક્ષણ છે.",
                "kn": "ನಮಸ್ಕಾರ, ಇದು ಒಂದು ಪರೀಕ್ಷೆ.",
                "ml": "നമസ്കാരം, ഇത് ഒരു പരീക്ഷണമാണ്.",
                "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਇਹ ਇੱਕ ਟੈਸਟ ਹੈ।"
            }
            
            # Get test text for language
            lang_prefix = language_code.split('-')[0]
            test_text = test_texts.get(lang_prefix, test_texts["en"])
            
            # Create test configuration
            test_config = SynthesisConfig(
                voice_id=voice_id,
                language_code=language_code,
                audio_format=AudioFormat.MP3,
                sample_rate="16000",
                speech_rate=SpeechRate.MEDIUM,
                enable_ssml=False
            )
            
            # Attempt synthesis
            result = await self.synthesize_speech(test_text, test_config)
            
            # Check if we got valid audio data
            success = result.audio_data and len(result.audio_data) > 0
            
            logger.info(f"Voice synthesis test for {voice_id} ({language_code}): "
                       f"{'SUCCESS' if success else 'FAILED'}")
            
            return success
            
        except Exception as e:
            logger.error(f"Voice synthesis test failed for {voice_id}: {e}")
            return False
    
    def create_synthesis_config(self, language: str, connection_speed: str = "medium",
                              prefer_neural: bool = True) -> SynthesisConfig:
        """
        Create a synthesis configuration for a given language and connection speed.
        
        Args:
            language: Language code (e.g., 'hi', 'en')
            connection_speed: Connection speed ('excellent', 'good', 'medium', 'slow', 'poor', 'very_poor')
            prefer_neural: Whether to prefer neural voices
            
        Returns:
            SynthesisConfig optimized for the given parameters
        """
        try:
            # Get best voice for language
            voice = self.get_voice_for_language(language, prefer_neural)
            if not voice:
                # Fallback to default Hindi voice
                voice = self.indian_voices["Aditi"]
                logger.warning(f"No voice found for language {language}, using default Hindi voice")
            
            # Determine quality settings based on connection speed
            if connection_speed in ["excellent", "good"]:
                audio_format = AudioFormat.MP3
                sample_rate = "22050"
                compression_quality = None  # No additional compression
                engine = VoiceEngine.NEURAL if voice.supports_neural else VoiceEngine.STANDARD
            elif connection_speed == "medium":
                audio_format = AudioFormat.MP3
                sample_rate = "16000"
                compression_quality = 64
                engine = VoiceEngine.NEURAL if voice.supports_neural else VoiceEngine.STANDARD
            elif connection_speed == "slow":
                audio_format = AudioFormat.MP3
                sample_rate = "16000"
                compression_quality = 32
                engine = VoiceEngine.STANDARD
            else:  # poor or very_poor
                audio_format = AudioFormat.MP3
                sample_rate = "8000"
                compression_quality = 16
                engine = VoiceEngine.STANDARD
            
            config = SynthesisConfig(
                voice_id=voice.voice_id,
                language_code=voice.language_code,
                audio_format=audio_format,
                sample_rate=sample_rate,
                speech_rate=SpeechRate.MEDIUM,
                volume="medium",
                engine=engine,
                enable_ssml=True,
                compression_quality=compression_quality
            )
            
            logger.debug(f"Created synthesis config for {language} with {connection_speed} connection")
            return config
            
        except Exception as e:
            logger.error(f"Error creating synthesis config: {e}")
            # Return default configuration
            return SynthesisConfig(
                voice_id="Aditi",
                language_code="hi-IN",
                audio_format=AudioFormat.MP3,
                sample_rate="16000"
            )