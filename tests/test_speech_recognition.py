"""
Unit tests for the speech recognition module.

Tests AWS Transcribe integration, confidence scoring, uncertainty handling,
and noise-robust recognition for rural environments.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from bharat_voice_assistant.voice.speech_recognition import (
    SpeechRecognizer,
    RecognitionConfig,
    RecognitionResult,
    RecognitionMode,
    LanguageModel
)
from bharat_voice_assistant.core.exceptions import SpeechRecognitionError


class TestSpeechRecognizer:
    """Test cases for the SpeechRecognizer class."""
    
    @pytest.fixture
    def speech_recognizer(self):
        """Create a SpeechRecognizer instance for testing."""
        with patch('bharat_voice_assistant.voice.speech_recognition.aws_clients'):
            recognizer = SpeechRecognizer()
            recognizer.transcribe_client = Mock()
            recognizer.s3_client = Mock()
            return recognizer
    
    @pytest.fixture
    def sample_audio_data(self):
        """Sample audio data for testing."""
        return b"fake_audio_data_for_testing" * 100
    
    @pytest.fixture
    def recognition_config(self):
        """Sample recognition configuration."""
        return RecognitionConfig(
            language_code="hi-IN",
            custom_language_model=LanguageModel.HINDI_RURAL,
            confidence_threshold=0.7,
            noise_reduction_enabled=True
        )
    
    @pytest.fixture
    def mock_transcription_response(self):
        """Mock AWS Transcribe response."""
        return {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "COMPLETED",
                "LanguageCode": "hi-IN",
                "Transcript": {
                    "TranscriptFileUri": "s3://test-bucket/transcript.json"
                }
            }
        }
    
    @pytest.fixture
    def mock_transcript_data(self):
        """Mock transcript JSON data."""
        return {
            "results": {
                "transcripts": [
                    {"transcript": "नमस्ते मुझे सरकारी योजना की जानकारी चाहिए"}
                ],
                "items": [
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "नमस्ते", "confidence": "0.95"}
                        ],
                        "start_time": "0.0",
                        "end_time": "0.5"
                    },
                    {
                        "type": "pronunciation", 
                        "alternatives": [
                            {"content": "मुझे", "confidence": "0.92"}
                        ],
                        "start_time": "0.6",
                        "end_time": "0.9"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "सरकारी", "confidence": "0.88"}
                        ],
                        "start_time": "1.0",
                        "end_time": "1.4"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "योजना", "confidence": "0.90"}
                        ],
                        "start_time": "1.5",
                        "end_time": "1.9"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "की", "confidence": "0.85"}
                        ],
                        "start_time": "2.0",
                        "end_time": "2.1"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "जानकारी", "confidence": "0.87"}
                        ],
                        "start_time": "2.2",
                        "end_time": "2.8"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "चाहिए", "confidence": "0.91"}
                        ],
                        "start_time": "2.9",
                        "end_time": "3.3"
                    }
                ]
            }
        }
    
    @pytest.mark.asyncio
    async def test_recognize_speech_success(self, speech_recognizer, sample_audio_data, 
                                          recognition_config, mock_transcription_response,
                                          mock_transcript_data):
        """Test successful speech recognition."""
        # Mock S3 upload
        speech_recognizer.s3_client.put_object = AsyncMock()
        
        # Mock transcription job start
        speech_recognizer.transcribe_client.start_transcription_job = Mock(
            return_value=mock_transcription_response
        )
        
        # Mock transcription job status check
        speech_recognizer.transcribe_client.get_transcription_job = Mock(
            return_value=mock_transcription_response
        )
        
        # Mock S3 transcript download
        mock_s3_response = Mock()
        mock_s3_response.read.return_value = json.dumps(mock_transcript_data).encode('utf-8')
        speech_recognizer.s3_client.get_object = Mock(
            return_value={"Body": mock_s3_response}
        )
        
        # Mock S3 cleanup
        speech_recognizer.s3_client.delete_object = AsyncMock()
        
        # Test recognition
        result = await speech_recognizer.recognize_speech(
            sample_audio_data, recognition_config, RecognitionMode.REAL_TIME
        )
        
        # Verify result
        assert isinstance(result, RecognitionResult)
        assert result.transcript == "नमस्ते मुझे सरकारी योजना की जानकारी चाहिए"
        assert result.confidence > 0.8
        assert result.language == "hi-IN"
        assert len(result.alternatives) > 0
        assert result.processing_time_ms > 0
        assert result.word_timestamps is not None
        assert len(result.word_timestamps) == 7  # Number of words
    
    @pytest.mark.asyncio
    async def test_recognize_speech_low_confidence(self, speech_recognizer, sample_audio_data,
                                                 recognition_config, mock_transcription_response):
        """Test speech recognition with low confidence handling."""
        # Create low confidence transcript data
        low_confidence_data = {
            "results": {
                "transcripts": [
                    {"transcript": "unclear speech"}
                ],
                "items": [
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "unclear", "confidence": "0.3"}
                        ],
                        "start_time": "0.0",
                        "end_time": "0.5"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "speech", "confidence": "0.4"}
                        ],
                        "start_time": "0.6",
                        "end_time": "1.0"
                    }
                ]
            }
        }
        
        # Mock the calls
        speech_recognizer.s3_client.put_object = AsyncMock()
        speech_recognizer.transcribe_client.start_transcription_job = Mock(
            return_value=mock_transcription_response
        )
        speech_recognizer.transcribe_client.get_transcription_job = Mock(
            return_value=mock_transcription_response
        )
        
        mock_s3_response = Mock()
        mock_s3_response.read.return_value = json.dumps(low_confidence_data).encode('utf-8')
        speech_recognizer.s3_client.get_object = Mock(
            return_value={"Body": mock_s3_response}
        )
        speech_recognizer.s3_client.delete_object = AsyncMock()
        
        # Test recognition
        result = await speech_recognizer.recognize_speech(
            sample_audio_data, recognition_config, RecognitionMode.REAL_TIME
        )
        
        # Verify uncertainty handling
        assert result.confidence < recognition_config.confidence_threshold
        assert "[UNCERTAIN:" in result.transcript or "[NEEDS_CLARIFICATION]" in result.transcript
    
    @pytest.mark.asyncio
    async def test_recognize_speech_with_noise(self, speech_recognizer, sample_audio_data,
                                             recognition_config, mock_transcription_response,
                                             mock_transcript_data):
        """Test speech recognition with noise handling."""
        # Mock high noise scenario
        speech_recognizer.s3_client.put_object = AsyncMock()
        speech_recognizer.transcribe_client.start_transcription_job = Mock(
            return_value=mock_transcription_response
        )
        speech_recognizer.transcribe_client.get_transcription_job = Mock(
            return_value=mock_transcription_response
        )
        
        mock_s3_response = Mock()
        mock_s3_response.read.return_value = json.dumps(mock_transcript_data).encode('utf-8')
        speech_recognizer.s3_client.get_object = Mock(
            return_value={"Body": mock_s3_response}
        )
        speech_recognizer.s3_client.delete_object = AsyncMock()
        
        # Enable noise reduction in config
        recognition_config.noise_reduction_enabled = True
        
        result = await speech_recognizer.recognize_speech(
            sample_audio_data, recognition_config, RecognitionMode.REAL_TIME
        )
        
        # Verify noise handling
        assert isinstance(result, RecognitionResult)
        # Check that rural noise settings were applied
        speech_recognizer.transcribe_client.start_transcription_job.assert_called_once()
        call_args = speech_recognizer.transcribe_client.start_transcription_job.call_args[1]
        assert call_args["Settings"]["EnableChannelIdentification"] == True
        assert call_args["Settings"]["EnablePartialResultsStabilization"] == True
    
    @pytest.mark.asyncio
    async def test_language_detection(self, speech_recognizer, sample_audio_data):
        """Test language detection functionality."""
        # Mock language detection response
        lang_detection_response = {
            "TranscriptionJob": {
                "TranscriptionJobName": "lang-detect-job",
                "TranscriptionJobStatus": "COMPLETED",
                "IdentifiedLanguageScore": {
                    "LanguageCode": "hi-IN",
                    "Score": 0.95
                }
            }
        }
        
        speech_recognizer.s3_client.put_object = AsyncMock()
        speech_recognizer.transcribe_client.start_transcription_job = Mock(
            return_value=lang_detection_response
        )
        speech_recognizer.transcribe_client.get_transcription_job = Mock(
            return_value=lang_detection_response
        )
        speech_recognizer.s3_client.delete_object = AsyncMock()
        
        result = await speech_recognizer.detect_language(sample_audio_data)
        
        assert result["language_code"] == "hi-IN"
        assert result["confidence"] == 0.95
    
    @pytest.mark.asyncio
    async def test_transcription_job_failure(self, speech_recognizer, sample_audio_data,
                                           recognition_config):
        """Test handling of transcription job failures."""
        failure_response = {
            "TranscriptionJob": {
                "TranscriptionJobName": "failed-job",
                "TranscriptionJobStatus": "FAILED",
                "FailureReason": "Audio quality too poor"
            }
        }
        
        speech_recognizer.s3_client.put_object = AsyncMock()
        speech_recognizer.transcribe_client.start_transcription_job = Mock(
            return_value=failure_response
        )
        speech_recognizer.transcribe_client.get_transcription_job = Mock(
            return_value=failure_response
        )
        
        with pytest.raises(SpeechRecognitionError) as exc_info:
            await speech_recognizer.recognize_speech(
                sample_audio_data, recognition_config, RecognitionMode.REAL_TIME
            )
        
        assert exc_info.value.error_code == "TRANSCRIPTION_JOB_FAILED"
        assert "Audio quality too poor" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_transcription_timeout(self, speech_recognizer, sample_audio_data,
                                       recognition_config):
        """Test handling of transcription job timeouts."""
        # Mock job that never completes
        in_progress_response = {
            "TranscriptionJob": {
                "TranscriptionJobName": "timeout-job",
                "TranscriptionJobStatus": "IN_PROGRESS"
            }
        }
        
        speech_recognizer.s3_client.put_object = AsyncMock()
        speech_recognizer.transcribe_client.start_transcription_job = Mock(
            return_value=in_progress_response
        )
        speech_recognizer.transcribe_client.get_transcription_job = Mock(
            return_value=in_progress_response
        )
        
        # Patch the timeout to be very short for testing
        with patch.object(speech_recognizer, '_wait_for_transcription_completion') as mock_wait:
            mock_wait.side_effect = SpeechRecognitionError(
                "Transcription job timed out",
                error_code="TRANSCRIPTION_TIMEOUT"
            )
            
            with pytest.raises(SpeechRecognitionError) as exc_info:
                await speech_recognizer.recognize_speech(
                    sample_audio_data, recognition_config, RecognitionMode.REAL_TIME
                )
            
            assert exc_info.value.error_code == "TRANSCRIPTION_TIMEOUT"
    
    def test_language_model_selection(self, speech_recognizer):
        """Test custom language model selection."""
        # Test Hindi rural model
        models = speech_recognizer.get_custom_language_models()
        
        assert LanguageModel.HINDI_RURAL in models
        assert models[LanguageModel.HINDI_RURAL]["language_code"] == "hi-IN"
        assert models[LanguageModel.HINDI_RURAL]["model_name"] == "bharat-hindi-rural-v1"
        
        # Test all supported languages have models
        expected_languages = ["hi-IN", "en-IN", "ta-IN", "te-IN", "bn-IN", 
                            "mr-IN", "gu-IN", "kn-IN", "ml-IN", "pa-IN"]
        
        model_languages = [model["language_code"] for model in models.values()]
        
        for lang in expected_languages:
            assert lang in model_languages
    
    def test_supported_languages(self, speech_recognizer):
        """Test supported languages list."""
        languages = speech_recognizer.get_supported_languages()
        
        # Check that all required Indian languages are supported
        expected_languages = {
            "hi": "hi-IN",  # Hindi
            "en": "en-IN",  # English (India)
            "ta": "ta-IN",  # Tamil
            "te": "te-IN",  # Telugu
            "bn": "bn-IN",  # Bengali
            "mr": "mr-IN",  # Marathi
            "gu": "gu-IN",  # Gujarati
            "kn": "kn-IN",  # Kannada
            "ml": "ml-IN",  # Malayalam
            "pa": "pa-IN",  # Punjabi
        }
        
        for lang_code, aws_code in expected_languages.items():
            assert lang_code in languages
            assert languages[lang_code] == aws_code
    
    @pytest.mark.asyncio
    async def test_network_optimization(self, speech_recognizer):
        """Test network condition optimization."""
        # Test with good network conditions
        base_config = RecognitionConfig(
            language_code="hi-IN",
            custom_language_model=LanguageModel.HINDI_RURAL,
            max_alternatives=5,
            confidence_threshold=0.7,
            enable_speaker_identification=True,
            noise_reduction_enabled=False
        )
        
        # Test good network - should not change much
        good_config = await speech_recognizer.optimize_for_network_conditions(
            base_config, "good"
        )
        assert good_config.max_alternatives == 5
        assert good_config.confidence_threshold == 0.7
        assert good_config.enable_speaker_identification == True
        assert good_config.noise_reduction_enabled == False
        
        # Test poor network - should optimize settings
        poor_config = await speech_recognizer.optimize_for_network_conditions(
            base_config, "poor"
        )
        assert poor_config.max_alternatives <= 2  # Reduced for bandwidth
        assert poor_config.confidence_threshold == 0.6  # Lowered threshold
        assert poor_config.enable_speaker_identification == False  # Disabled
        assert poor_config.noise_reduction_enabled == True  # Enabled
        
        # Test very poor network - should optimize even more
        very_poor_config = await speech_recognizer.optimize_for_network_conditions(
            base_config, "very_poor"
        )
        assert very_poor_config.max_alternatives <= 2
        assert very_poor_config.confidence_threshold == 0.6
        assert very_poor_config.enable_speaker_identification == False
        assert very_poor_config.noise_reduction_enabled == True
    
    def test_recognition_config_validation(self):
        """Test recognition configuration validation."""
        # Test valid config
        config = RecognitionConfig(
            language_code="hi-IN",
            custom_language_model=LanguageModel.HINDI_RURAL,
            confidence_threshold=0.7
        )
        
        assert config.language_code == "hi-IN"
        assert config.custom_language_model == LanguageModel.HINDI_RURAL
        assert config.confidence_threshold == 0.7
        assert config.noise_reduction_enabled == True  # Default
        assert config.enable_word_timestamps == True  # Default
        assert config.max_alternatives == 3  # Default
    
    @pytest.mark.asyncio
    async def test_streaming_mode(self, speech_recognizer, sample_audio_data, recognition_config):
        """Test streaming recognition mode."""
        # Mock the real-time recognition since streaming falls back to it
        with patch.object(speech_recognizer, '_recognize_real_time') as mock_real_time:
            mock_result = RecognitionResult(
                transcript="test transcript",
                confidence=0.9,
                language="hi-IN",
                alternatives=[],
                processing_time_ms=100,
                audio_quality_score=0.8,
                noise_level=0.2
            )
            mock_real_time.return_value = mock_result
            
            result = await speech_recognizer.recognize_speech(
                sample_audio_data, recognition_config, RecognitionMode.STREAMING
            )
            
            assert result.transcript == "test transcript"
            mock_real_time.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_mode(self, speech_recognizer, sample_audio_data, recognition_config):
        """Test batch recognition mode."""
        # Mock the real-time recognition since batch uses similar approach
        with patch.object(speech_recognizer, '_recognize_real_time') as mock_real_time:
            mock_result = RecognitionResult(
                transcript="batch test transcript",
                confidence=0.85,
                language="hi-IN",
                alternatives=[],
                processing_time_ms=200,
                audio_quality_score=0.9,
                noise_level=0.1
            )
            mock_real_time.return_value = mock_result
            
            result = await speech_recognizer.recognize_speech(
                sample_audio_data, recognition_config, RecognitionMode.BATCH
            )
            
            assert result.transcript == "batch test transcript"
            mock_real_time.assert_called_once()


class TestRecognitionResult:
    """Test cases for RecognitionResult data class."""
    
    def test_recognition_result_creation(self):
        """Test creating a RecognitionResult instance."""
        result = RecognitionResult(
            transcript="test transcript",
            confidence=0.95,
            language="hi-IN",
            alternatives=[{"content": "alternative", "confidence": 0.8}],
            processing_time_ms=150,
            audio_quality_score=0.9,
            noise_level=0.1,
            word_timestamps=[{"word": "test", "start_time": 0.0, "end_time": 0.5}]
        )
        
        assert result.transcript == "test transcript"
        assert result.confidence == 0.95
        assert result.language == "hi-IN"
        assert len(result.alternatives) == 1
        assert result.processing_time_ms == 150
        assert result.audio_quality_score == 0.9
        assert result.noise_level == 0.1
        assert len(result.word_timestamps) == 1


class TestRecognitionConfig:
    """Test cases for RecognitionConfig data class."""
    
    def test_recognition_config_defaults(self):
        """Test RecognitionConfig default values."""
        config = RecognitionConfig(language_code="hi-IN")
        
        assert config.language_code == "hi-IN"
        assert config.custom_language_model is None
        assert config.enable_speaker_identification == False
        assert config.enable_word_timestamps == True
        assert config.enable_automatic_punctuation == True
        assert config.vocabulary_filter_method == "mask"
        assert config.custom_vocabulary_name is None
        assert config.max_alternatives == 3
        assert config.confidence_threshold == 0.7
        assert config.noise_reduction_enabled == True
    
    def test_recognition_config_custom_values(self):
        """Test RecognitionConfig with custom values."""
        config = RecognitionConfig(
            language_code="ta-IN",
            custom_language_model=LanguageModel.TAMIL_RURAL,
            enable_speaker_identification=True,
            confidence_threshold=0.8,
            max_alternatives=5,
            noise_reduction_enabled=False
        )
        
        assert config.language_code == "ta-IN"
        assert config.custom_language_model == LanguageModel.TAMIL_RURAL
        assert config.enable_speaker_identification == True
        assert config.confidence_threshold == 0.8
        assert config.max_alternatives == 5
        assert config.noise_reduction_enabled == False


class TestLanguageModel:
    """Test cases for LanguageModel enum."""
    
    def test_language_model_values(self):
        """Test LanguageModel enum values."""
        assert LanguageModel.HINDI_RURAL.value == "hindi_rural"
        assert LanguageModel.HINDI_URBAN.value == "hindi_urban"
        assert LanguageModel.ENGLISH_INDIAN.value == "english_indian"
        assert LanguageModel.TAMIL_RURAL.value == "tamil_rural"
        assert LanguageModel.TELUGU_RURAL.value == "telugu_rural"
        assert LanguageModel.BENGALI_RURAL.value == "bengali_rural"
        assert LanguageModel.MARATHI_RURAL.value == "marathi_rural"
        assert LanguageModel.GUJARATI_RURAL.value == "gujarati_rural"
        assert LanguageModel.KANNADA_RURAL.value == "kannada_rural"
        assert LanguageModel.MALAYALAM_RURAL.value == "malayalam_rural"
        assert LanguageModel.PUNJABI_RURAL.value == "punjabi_rural"
    
    def test_language_model_count(self):
        """Test that all expected language models are present."""
        models = list(LanguageModel)
        assert len(models) == 11  # 10 regional languages + English Indian


class TestRecognitionMode:
    """Test cases for RecognitionMode enum."""
    
    def test_recognition_mode_values(self):
        """Test RecognitionMode enum values."""
        assert RecognitionMode.REAL_TIME.value == "real_time"
        assert RecognitionMode.BATCH.value == "batch"
        assert RecognitionMode.STREAMING.value == "streaming"
    
    def test_recognition_mode_count(self):
        """Test that all expected recognition modes are present."""
        modes = list(RecognitionMode)
        assert len(modes) == 3