"""
AWS Transcribe integration for speech recognition in the Bharat Voice Assistant.

This module provides speech-to-text functionality using AWS Transcribe with
custom language models for Indian languages, confidence scoring, and
noise-robust recognition for rural environments.
"""

import asyncio
import json
import uuid
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum
import boto3
from botocore.exceptions import ClientError

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import SpeechRecognitionError
from bharat_voice_assistant.core.aws_client import aws_clients, safe_aws_call

logger = get_logger(__name__)


class RecognitionMode(Enum):
    """Speech recognition modes for different scenarios."""
    REAL_TIME = "real_time"
    BATCH = "batch"
    STREAMING = "streaming"


class LanguageModel(Enum):
    """Custom language models for Indian languages."""
    HINDI_RURAL = "hindi_rural"
    HINDI_URBAN = "hindi_urban"
    ENGLISH_INDIAN = "english_indian"
    TAMIL_RURAL = "tamil_rural"
    TELUGU_RURAL = "telugu_rural"
    BENGALI_RURAL = "bengali_rural"
    MARATHI_RURAL = "marathi_rural"
    GUJARATI_RURAL = "gujarati_rural"
    KANNADA_RURAL = "kannada_rural"
    MALAYALAM_RURAL = "malayalam_rural"
    PUNJABI_RURAL = "punjabi_rural"


@dataclass
class RecognitionResult:
    """Result of speech recognition operation."""
    transcript: str
    confidence: float
    language: str
    alternatives: List[Dict[str, Any]]
    processing_time_ms: int
    audio_quality_score: float
    noise_level: float
    speaker_labels: Optional[List[Dict[str, Any]]] = None
    word_timestamps: Optional[List[Dict[str, Any]]] = None
    custom_vocabulary_matches: Optional[List[str]] = None


@dataclass
class RecognitionConfig:
    """Configuration for speech recognition."""
    language_code: str
    custom_language_model: Optional[LanguageModel] = None
    enable_speaker_identification: bool = False
    enable_word_timestamps: bool = True
    enable_automatic_punctuation: bool = True
    vocabulary_filter_method: str = "mask"  # mask, remove, tag
    custom_vocabulary_name: Optional[str] = None
    max_alternatives: int = 3
    confidence_threshold: float = 0.7
    noise_reduction_enabled: bool = True


class SpeechRecognizer:
    """
    AWS Transcribe-based speech recognition with Indian language support.
    """
    
    def __init__(self):
        """Initialize the speech recognizer."""
        self.transcribe_client = aws_clients.transcribe
        self.s3_client = aws_clients.s3
        
        # Language model mappings
        self.language_models = {
            LanguageModel.HINDI_RURAL: {
                "language_code": "hi-IN",
                "model_name": "bharat-hindi-rural-v1",
                "vocabulary": "hindi-government-terms"
            },
            LanguageModel.HINDI_URBAN: {
                "language_code": "hi-IN", 
                "model_name": "bharat-hindi-urban-v1",
                "vocabulary": "hindi-urban-terms"
            },
            LanguageModel.ENGLISH_INDIAN: {
                "language_code": "en-IN",
                "model_name": "bharat-english-indian-v1",
                "vocabulary": "indian-english-terms"
            },
            LanguageModel.TAMIL_RURAL: {
                "language_code": "ta-IN",
                "model_name": "bharat-tamil-rural-v1",
                "vocabulary": "tamil-government-terms"
            },
            LanguageModel.TELUGU_RURAL: {
                "language_code": "te-IN",
                "model_name": "bharat-telugu-rural-v1", 
                "vocabulary": "telugu-government-terms"
            },
            LanguageModel.BENGALI_RURAL: {
                "language_code": "bn-IN",
                "model_name": "bharat-bengali-rural-v1",
                "vocabulary": "bengali-government-terms"
            },
            LanguageModel.MARATHI_RURAL: {
                "language_code": "mr-IN",
                "model_name": "bharat-marathi-rural-v1",
                "vocabulary": "marathi-government-terms"
            },
            LanguageModel.GUJARATI_RURAL: {
                "language_code": "gu-IN",
                "model_name": "bharat-gujarati-rural-v1",
                "vocabulary": "gujarati-government-terms"
            },
            LanguageModel.KANNADA_RURAL: {
                "language_code": "kn-IN",
                "model_name": "bharat-kannada-rural-v1",
                "vocabulary": "kannada-government-terms"
            },
            LanguageModel.MALAYALAM_RURAL: {
                "language_code": "ml-IN",
                "model_name": "bharat-malayalam-rural-v1",
                "vocabulary": "malayalam-government-terms"
            },
            LanguageModel.PUNJABI_RURAL: {
                "language_code": "pa-IN",
                "model_name": "bharat-punjabi-rural-v1",
                "vocabulary": "punjabi-government-terms"
            }
        }
        
        # Noise-robust settings for rural environments
        self.rural_noise_settings = {
            "EnableChannelIdentification": True,
            "EnablePartialResultsStabilization": True,
            "VocabularyFilterMethod": "mask",
            "MaxSpeakerLabels": 2,
            "ShowAlternatives": True
        }
        
        # Enhanced rural noise settings for very poor conditions
        self.enhanced_rural_settings = {
            "EnableChannelIdentification": True,
            "EnablePartialResultsStabilization": True,
            "VocabularyFilterMethod": "mask",
            "MaxSpeakerLabels": 2,
            "ShowAlternatives": True,
            "MaxAlternatives": 5,  # More alternatives for uncertain recognition
            "EnableAutomaticPunctuation": True,
            "EnableRedaction": False  # Keep all content for government services
        }
        
        logger.info("SpeechRecognizer initialized with Indian language models")
    
    async def recognize_speech(self, audio_data: bytes, 
                             recognition_config: RecognitionConfig,
                             mode: RecognitionMode = RecognitionMode.REAL_TIME) -> RecognitionResult:
        """
        Recognize speech from audio data.
        
        Args:
            audio_data: Raw audio bytes
            recognition_config: Recognition configuration
            mode: Recognition mode (real-time, batch, streaming)
            
        Returns:
            RecognitionResult with transcript and metadata
        """
        start_time = time.time()
        
        try:
            if mode == RecognitionMode.STREAMING:
                result = await self._recognize_streaming(audio_data, recognition_config)
            elif mode == RecognitionMode.BATCH:
                result = await self._recognize_batch(audio_data, recognition_config)
            else:
                result = await self._recognize_real_time(audio_data, recognition_config)
            
            processing_time = int((time.time() - start_time) * 1000)
            result.processing_time_ms = processing_time
            
            # Apply confidence-based uncertainty handling
            result = await self._handle_uncertainty(result, recognition_config)
            
            logger.debug(f"Speech recognition completed in {processing_time}ms "
                        f"with confidence {result.confidence:.2f}")
            
            return result
            
        except SpeechRecognitionError:
            # Re-raise specific speech recognition errors without wrapping
            raise
        except Exception as e:
            logger.error(f"Speech recognition failed: {e}")
            raise SpeechRecognitionError(
                "Failed to recognize speech",
                error_code="SPEECH_RECOGNITION_FAILED",
                context={
                    "language": recognition_config.language_code,
                    "mode": mode.value,
                    "error": str(e)
                }
            )
    
    async def _recognize_real_time(self, audio_data: bytes, 
                                 recognition_config: RecognitionConfig) -> RecognitionResult:
        """Perform real-time speech recognition using AWS Transcribe."""
        try:
            # Upload audio to S3 for processing
            s3_key = f"temp-audio/{uuid.uuid4()}.wav"
            bucket_name = config.aws.s3_bucket_voice_data
            
            await self._upload_audio_to_s3(audio_data, bucket_name, s3_key)
            
            # Start transcription job
            job_name = f"transcribe-{uuid.uuid4()}"
            job_uri = f"s3://{bucket_name}/{s3_key}"
            
            transcription_params = self._build_transcription_params(recognition_config, job_uri)
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: safe_aws_call(
                    self.transcribe_client.start_transcription_job,
                    TranscriptionJobName=job_name,
                    **transcription_params
                )
            )
            
            # Wait for completion and get results
            result = await self._wait_for_transcription_completion(job_name)
            
            # Clean up temporary S3 object
            await self._cleanup_s3_object(bucket_name, s3_key)
            
            return result
            
        except Exception as e:
            logger.error(f"Real-time recognition failed: {e}")
            raise
    
    async def _recognize_streaming(self, audio_data: bytes,
                                 recognition_config: RecognitionConfig) -> RecognitionResult:
        """Perform streaming speech recognition."""
        try:
            # For streaming, we'll use the real-time approach with optimizations
            # In a full implementation, this would use AWS Transcribe Streaming
            logger.info("Using optimized real-time recognition for streaming mode")
            return await self._recognize_real_time(audio_data, recognition_config)
            
        except Exception as e:
            logger.error(f"Streaming recognition failed: {e}")
            raise
    
    async def _recognize_batch(self, audio_data: bytes,
                             recognition_config: RecognitionConfig) -> RecognitionResult:
        """Perform batch speech recognition for longer audio files."""
        try:
            # Similar to real-time but with different parameters for batch processing
            return await self._recognize_real_time(audio_data, recognition_config)
            
        except Exception as e:
            logger.error(f"Batch recognition failed: {e}")
            raise
    
    def _build_transcription_params(self, recognition_config: RecognitionConfig, 
                                  media_uri: str) -> Dict[str, Any]:
        """Build parameters for AWS Transcribe job."""
        params = {
            "Media": {"MediaFileUri": media_uri},
            "MediaFormat": "wav",
            "LanguageCode": recognition_config.language_code,
            "Settings": {
                "ShowSpeakerLabels": recognition_config.enable_speaker_identification,
                "MaxSpeakerLabels": 2 if recognition_config.enable_speaker_identification else None,
                "ShowAlternatives": True,
                "MaxAlternatives": recognition_config.max_alternatives,
                "VocabularyFilterMethod": recognition_config.vocabulary_filter_method
            }
        }
        
        # Add custom language model if specified
        if recognition_config.custom_language_model:
            model_info = self.language_models.get(recognition_config.custom_language_model)
            if model_info:
                params["ModelSettings"] = {
                    "LanguageModelName": model_info["model_name"]
                }
        
        # Add custom vocabulary if specified
        if recognition_config.custom_vocabulary_name:
            params["Settings"]["VocabularyName"] = recognition_config.custom_vocabulary_name
        
        # Add noise-robust settings for rural environments
        if recognition_config.noise_reduction_enabled:
            # Use enhanced settings for very poor audio quality
            if hasattr(recognition_config, 'audio_quality_level') and \
               recognition_config.audio_quality_level == "very_poor":
                params["Settings"].update(self.enhanced_rural_settings)
            else:
                params["Settings"].update(self.rural_noise_settings)
        
        # Enable automatic punctuation
        if recognition_config.enable_automatic_punctuation:
            params["Settings"]["EnableAutomaticPunctuation"] = True
        
        return params
    
    async def _wait_for_transcription_completion(self, job_name: str) -> RecognitionResult:
        """Wait for transcription job completion and parse results."""
        max_wait_time = 300  # 5 minutes
        poll_interval = 2  # 2 seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: safe_aws_call(
                        self.transcribe_client.get_transcription_job,
                        TranscriptionJobName=job_name
                    )
                )
                
                status = response["TranscriptionJob"]["TranscriptionJobStatus"]
                
                if status == "COMPLETED":
                    return await self._parse_transcription_results(response)
                elif status == "FAILED":
                    failure_reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
                    raise SpeechRecognitionError(
                        f"Transcription job failed: {failure_reason}",
                        error_code="TRANSCRIPTION_JOB_FAILED",
                        context={"job_name": job_name, "failure_reason": failure_reason}
                    )
                
                # Wait before next poll
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
                
            except Exception as e:
                logger.error(f"Error checking transcription job status: {e}")
                raise
        
        # Timeout reached
        raise SpeechRecognitionError(
            "Transcription job timed out",
            error_code="TRANSCRIPTION_TIMEOUT",
            context={"job_name": job_name, "max_wait_time": max_wait_time}
        )
    
    async def _parse_transcription_results(self, transcription_response: Dict[str, Any]) -> RecognitionResult:
        """Parse AWS Transcribe results into RecognitionResult."""
        try:
            job_details = transcription_response["TranscriptionJob"]
            transcript_uri = job_details["Transcript"]["TranscriptFileUri"]
            
            # Download and parse transcript JSON
            transcript_data = await self._download_transcript(transcript_uri)
            
            # Extract main transcript
            results = transcript_data.get("results", {})
            transcripts = results.get("transcripts", [])
            
            if not transcripts:
                raise SpeechRecognitionError(
                    "No transcript found in results",
                    error_code="NO_TRANSCRIPT_FOUND"
                )
            
            main_transcript = transcripts[0]["transcript"]
            
            # Extract alternatives
            alternatives = []
            items = results.get("items", [])
            
            for item in items:
                if "alternatives" in item:
                    for alt in item["alternatives"]:
                        alternatives.append({
                            "content": alt.get("content", ""),
                            "confidence": float(alt.get("confidence", 0.0))
                        })
            
            # Calculate overall confidence
            confidences = [alt["confidence"] for alt in alternatives if alt["confidence"] > 0]
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Extract word timestamps if available
            word_timestamps = []
            for item in items:
                if item.get("type") == "pronunciation":
                    word_timestamps.append({
                        "word": item.get("alternatives", [{}])[0].get("content", ""),
                        "start_time": float(item.get("start_time", 0)),
                        "end_time": float(item.get("end_time", 0)),
                        "confidence": float(item.get("alternatives", [{}])[0].get("confidence", 0))
                    })
            
            # Extract speaker labels if available
            speaker_labels = []
            if "speaker_labels" in results:
                segments = results["speaker_labels"].get("segments", [])
                for segment in segments:
                    speaker_labels.append({
                        "speaker_label": segment.get("speaker_label"),
                        "start_time": float(segment.get("start_time", 0)),
                        "end_time": float(segment.get("end_time", 0)),
                        "items": segment.get("items", [])
                    })
            
            # Estimate audio quality and noise level from confidence scores
            audio_quality_score = min(overall_confidence * 1.2, 1.0)  # Scale confidence to quality
            noise_level = max(0.0, 1.0 - overall_confidence)  # Inverse relationship
            
            return RecognitionResult(
                transcript=main_transcript,
                confidence=overall_confidence,
                language=job_details.get("LanguageCode", "unknown"),
                alternatives=alternatives,
                processing_time_ms=0,  # Will be set by caller
                audio_quality_score=audio_quality_score,
                noise_level=noise_level,
                speaker_labels=speaker_labels if speaker_labels else None,
                word_timestamps=word_timestamps if word_timestamps else None
            )
            
        except Exception as e:
            logger.error(f"Error parsing transcription results: {e}")
            raise SpeechRecognitionError(
                "Failed to parse transcription results",
                error_code="TRANSCRIPTION_PARSE_FAILED",
                context={"error": str(e)}
            )
    
    async def _download_transcript(self, transcript_uri: str) -> Dict[str, Any]:
        """Download transcript JSON from S3."""
        try:
            # Parse S3 URI
            if not transcript_uri.startswith("s3://"):
                raise ValueError("Invalid S3 URI format")
            
            uri_parts = transcript_uri[5:].split("/", 1)
            bucket_name = uri_parts[0]
            key = uri_parts[1]
            
            # Download transcript
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: safe_aws_call(
                    self.s3_client.get_object,
                    Bucket=bucket_name,
                    Key=key
                )
            )
            
            transcript_json = response["Body"].read().decode("utf-8")
            return json.loads(transcript_json)
            
        except Exception as e:
            logger.error(f"Error downloading transcript: {e}")
            raise
    
    async def _upload_audio_to_s3(self, audio_data: bytes, bucket_name: str, key: str):
        """Upload audio data to S3."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: safe_aws_call(
                    self.s3_client.put_object,
                    Bucket=bucket_name,
                    Key=key,
                    Body=audio_data,
                    ContentType="audio/wav"
                )
            )
            
        except Exception as e:
            logger.error(f"Error uploading audio to S3: {e}")
            raise
    
    async def _cleanup_s3_object(self, bucket_name: str, key: str):
        """Clean up temporary S3 object."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: safe_aws_call(
                    self.s3_client.delete_object,
                    Bucket=bucket_name,
                    Key=key
                )
            )
            
        except Exception as e:
            logger.warning(f"Failed to cleanup S3 object {key}: {e}")
    
    async def _handle_uncertainty(self, result: RecognitionResult, 
                                recognition_config: RecognitionConfig) -> RecognitionResult:
        """
        Handle uncertainty in recognition results based on confidence scores.
        
        This implements the requirement for confidence scoring and uncertainty handling.
        """
        try:
            # Check if confidence is below threshold
            if result.confidence < recognition_config.confidence_threshold:
                logger.info(f"Low confidence recognition: {result.confidence:.2f} < {recognition_config.confidence_threshold}")
                
                # Add uncertainty indicators to the result
                result.transcript = f"[UNCERTAIN: {result.confidence:.2f}] {result.transcript}"
                
                # If confidence is very low, suggest clarification
                if result.confidence < 0.5:
                    result.transcript = f"[NEEDS_CLARIFICATION] {result.transcript}"
                
                # For extremely low confidence, suggest alternative input method
                if result.confidence < 0.3:
                    result.transcript = f"[SUGGEST_TEXT_INPUT] {result.transcript}"
            
            # Handle noise-related uncertainty
            if result.noise_level > 0.6:
                logger.info(f"High noise level detected: {result.noise_level:.2f}")
                result.transcript = f"[NOISY_ENVIRONMENT] {result.transcript}"
                
                # For very high noise, suggest quieter environment
                if result.noise_level > 0.8:
                    result.transcript = f"[FIND_QUIET_PLACE] {result.transcript}"
            
            # Handle very short or empty transcripts
            if len(result.transcript.strip()) < 3:
                logger.info("Very short transcript detected, marking as uncertain")
                result.confidence = min(result.confidence, 0.3)
                result.transcript = f"[SHORT_UTTERANCE] {result.transcript}"
            
            # Handle rural-specific challenges
            result = await self._handle_rural_specific_challenges(result, recognition_config)
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling uncertainty: {e}")
            return result
    
    async def _handle_rural_specific_challenges(self, result: RecognitionResult,
                                              recognition_config: RecognitionConfig) -> RecognitionResult:
        """
        Handle specific challenges common in rural environments.
        
        This includes dialect variations, background sounds, and connectivity issues.
        """
        try:
            # Check for dialect-specific patterns that might need special handling
            if recognition_config.custom_language_model and "rural" in recognition_config.custom_language_model.value:
                # Apply rural-specific confidence adjustments
                if result.confidence < 0.8 and result.confidence > 0.6:
                    # Rural dialects might have slightly lower confidence but still be accurate
                    logger.debug("Applying rural dialect confidence adjustment")
                    result.confidence = min(result.confidence + 0.1, 1.0)
            
            # Handle common rural background sounds
            rural_noise_indicators = ["[NOISY_ENVIRONMENT]", "[FIND_QUIET_PLACE]"]
            if any(indicator in result.transcript for indicator in rural_noise_indicators):
                # Add rural-specific guidance
                result.transcript += " [RURAL_NOISE_GUIDANCE]"
            
            # Check for very fragmented speech (common with poor connectivity)
            # Only flag as fragmented if we have word timestamps and they show issues
            if result.word_timestamps and len(result.word_timestamps) > 2:
                avg_word_confidence = sum(
                    float(word.get("confidence", 0)) 
                    for word in result.word_timestamps
                ) / len(result.word_timestamps)
                
                # Only flag as fragmented if confidence is significantly lower than overall
                # and we have evidence of connectivity issues
                if (avg_word_confidence < 0.6 and 
                    result.confidence > 0.7 and 
                    result.noise_level > 0.4):
                    result.transcript = f"[FRAGMENTED_SPEECH] {result.transcript}"
                    logger.info("Fragmented speech pattern detected, likely due to connectivity")
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling rural-specific challenges: {e}")
            return result
    
    async def detect_language(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Detect the language of spoken audio.
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Dictionary with detected language and confidence
        """
        try:
            # Use AWS Transcribe's language identification
            s3_key = f"temp-audio-lang/{uuid.uuid4()}.wav"
            bucket_name = config.aws.s3_bucket_voice_data
            
            await self._upload_audio_to_s3(audio_data, bucket_name, s3_key)
            
            job_name = f"lang-detect-{uuid.uuid4()}"
            job_uri = f"s3://{bucket_name}/{s3_key}"
            
            # Start language identification job
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: safe_aws_call(
                    self.transcribe_client.start_transcription_job,
                    TranscriptionJobName=job_name,
                    Media={"MediaFileUri": job_uri},
                    MediaFormat="wav",
                    IdentifyLanguage=True,
                    LanguageOptions=list(config.voice.supported_languages.values())
                )
            )
            
            # Wait for completion
            result = await self._wait_for_language_detection_completion(job_name)
            
            # Clean up
            await self._cleanup_s3_object(bucket_name, s3_key)
            
            return result
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            raise SpeechRecognitionError(
                "Failed to detect language",
                error_code="LANGUAGE_DETECTION_FAILED",
                context={"error": str(e)}
            )
    
    async def _wait_for_language_detection_completion(self, job_name: str) -> Dict[str, Any]:
        """Wait for language detection job completion."""
        max_wait_time = 300
        poll_interval = 2
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: safe_aws_call(
                        self.transcribe_client.get_transcription_job,
                        TranscriptionJobName=job_name
                    )
                )
                
                status = response["TranscriptionJob"]["TranscriptionJobStatus"]
                
                if status == "COMPLETED":
                    job_details = response["TranscriptionJob"]
                    identified_language = job_details.get("IdentifiedLanguageScore")
                    
                    if identified_language:
                        return {
                            "language_code": identified_language.get("LanguageCode"),
                            "confidence": identified_language.get("Score", 0.0)
                        }
                    else:
                        return {"language_code": "unknown", "confidence": 0.0}
                        
                elif status == "FAILED":
                    failure_reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
                    raise SpeechRecognitionError(
                        f"Language detection job failed: {failure_reason}",
                        error_code="LANGUAGE_DETECTION_JOB_FAILED"
                    )
                
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
                
            except Exception as e:
                logger.error(f"Error checking language detection job: {e}")
                raise
        
        raise SpeechRecognitionError(
            "Language detection job timed out",
            error_code="LANGUAGE_DETECTION_TIMEOUT"
        )
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages."""
        return config.voice.supported_languages.copy()
    
    def get_custom_language_models(self) -> Dict[LanguageModel, Dict[str, str]]:
        """Get available custom language models."""
        return self.language_models.copy()
    
    async def optimize_for_network_conditions(self, recognition_config: RecognitionConfig,
                                            network_quality: str = "good") -> RecognitionConfig:
        """
        Optimize recognition configuration based on network conditions.
        
        This helps with rural environments where network connectivity may be poor.
        """
        try:
            optimized_config = RecognitionConfig(
                language_code=recognition_config.language_code,
                custom_language_model=recognition_config.custom_language_model,
                enable_speaker_identification=recognition_config.enable_speaker_identification,
                enable_word_timestamps=recognition_config.enable_word_timestamps,
                enable_automatic_punctuation=recognition_config.enable_automatic_punctuation,
                vocabulary_filter_method=recognition_config.vocabulary_filter_method,
                custom_vocabulary_name=recognition_config.custom_vocabulary_name,
                max_alternatives=recognition_config.max_alternatives,
                confidence_threshold=recognition_config.confidence_threshold,
                noise_reduction_enabled=recognition_config.noise_reduction_enabled
            )
            
            # Adjust settings based on network quality
            if network_quality in ["poor", "very_poor"]:
                # Reduce alternatives to save bandwidth
                optimized_config.max_alternatives = min(optimized_config.max_alternatives, 2)
                
                # Disable speaker identification to reduce processing
                optimized_config.enable_speaker_identification = False
                
                # Lower confidence threshold for poor network conditions
                optimized_config.confidence_threshold = max(0.6, optimized_config.confidence_threshold - 0.1)
                
                # Always enable noise reduction for poor network
                optimized_config.noise_reduction_enabled = True
                
                logger.info(f"Optimized recognition config for {network_quality} network conditions")
            
            return optimized_config
            
        except Exception as e:
            logger.error(f"Error optimizing for network conditions: {e}")
            return recognition_config