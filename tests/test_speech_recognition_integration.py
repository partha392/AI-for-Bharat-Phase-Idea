"""
Integration tests for AWS Transcribe speech recognition.

These tests demonstrate the complete integration of AWS Transcribe with
the Bharat Voice Assistant, including custom language models, confidence
scoring, and noise-robust recognition.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from bharat_voice_assistant.voice.speech_recognition import (
    SpeechRecognizer,
    RecognitionConfig,
    RecognitionMode,
    LanguageModel
)
from bharat_voice_assistant.voice.gateway import VoiceInterfaceGateway


class TestSpeechRecognitionIntegration:
    """Integration tests for speech recognition with voice gateway."""
    
    @pytest.fixture
    def mock_aws_clients(self):
        """Mock AWS clients for integration testing."""
        with patch('bharat_voice_assistant.voice.speech_recognition.aws_clients') as mock_clients:
            # Mock S3 client
            mock_s3 = Mock()
            mock_s3.put_object = AsyncMock()
            mock_s3.get_object = Mock()
            mock_s3.delete_object = AsyncMock()
            mock_clients.s3 = mock_s3
            
            # Mock Transcribe client
            mock_transcribe = Mock()
            mock_transcribe.start_transcription_job = Mock()
            mock_transcribe.get_transcription_job = Mock()
            mock_clients.transcribe = mock_transcribe
            
            yield mock_clients
    
    @pytest.fixture
    def speech_recognizer(self, mock_aws_clients):
        """Create a speech recognizer with mocked AWS clients."""
        return SpeechRecognizer()
    
    @pytest.fixture
    def voice_gateway(self):
        """Create a voice gateway for integration testing."""
        with patch('bharat_voice_assistant.voice.speech_recognition.aws_clients'):
            gateway = VoiceInterfaceGateway()
            # Mock the speech recognizer to avoid AWS calls
            gateway.speech_recognizer = Mock()
            return gateway
    
    @pytest.mark.asyncio
    async def test_hindi_rural_recognition(self, speech_recognizer, mock_aws_clients):
        """Test Hindi rural speech recognition with custom language model."""
        # Setup mock responses
        transcription_response = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "COMPLETED",
                "LanguageCode": "hi-IN",
                "Transcript": {
                    "TranscriptFileUri": "s3://test-bucket/transcript.json"
                }
            }
        }
        
        transcript_data = {
            "results": {
                "transcripts": [
                    {"transcript": "मुझे राशन कार्ड बनवाना है"}
                ],
                "items": [
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "मुझे", "confidence": "0.92"}
                        ],
                        "start_time": "0.0",
                        "end_time": "0.4"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "राशन", "confidence": "0.88"}
                        ],
                        "start_time": "0.5",
                        "end_time": "0.9"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "कार्ड", "confidence": "0.90"}
                        ],
                        "start_time": "1.0",
                        "end_time": "1.3"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "बनवाना", "confidence": "0.85"}
                        ],
                        "start_time": "1.4",
                        "end_time": "1.8"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "है", "confidence": "0.93"}
                        ],
                        "start_time": "1.9",
                        "end_time": "2.1"
                    }
                ]
            }
        }
        
        # Mock AWS calls
        mock_aws_clients.transcribe.start_transcription_job.return_value = transcription_response
        mock_aws_clients.transcribe.get_transcription_job.return_value = transcription_response
        
        import json
        mock_s3_response = Mock()
        mock_s3_response.read.return_value = json.dumps(transcript_data).encode('utf-8')
        mock_aws_clients.s3.get_object.return_value = {"Body": mock_s3_response}
        
        # Create recognition config for Hindi rural
        config = RecognitionConfig(
            language_code="hi-IN",
            custom_language_model=LanguageModel.HINDI_RURAL,
            confidence_threshold=0.7,
            noise_reduction_enabled=True
        )
        
        # Test audio data
        audio_data = b"fake_hindi_rural_audio_data" * 50
        
        # Perform recognition
        result = await speech_recognizer.recognize_speech(
            audio_data, config, RecognitionMode.REAL_TIME
        )
        
        # Verify results
        assert result.transcript == "मुझे राशन कार्ड बनवाना है"
        assert result.language == "hi-IN"
        assert result.confidence > 0.8
        assert len(result.word_timestamps) == 5
        
        # Verify custom language model was used
        call_args = mock_aws_clients.transcribe.start_transcription_job.call_args[1]
        assert "ModelSettings" in call_args
        assert call_args["ModelSettings"]["LanguageModelName"] == "bharat-hindi-rural-v1"
        
        # Verify noise reduction settings were applied
        assert call_args["Settings"]["EnableChannelIdentification"] == True
        assert call_args["Settings"]["EnablePartialResultsStabilization"] == True
    
    @pytest.mark.asyncio
    async def test_low_confidence_handling(self, speech_recognizer, mock_aws_clients):
        """Test handling of low confidence recognition results."""
        # Setup mock responses with low confidence
        transcription_response = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "COMPLETED",
                "LanguageCode": "hi-IN",
                "Transcript": {
                    "TranscriptFileUri": "s3://test-bucket/transcript.json"
                }
            }
        }
        
        transcript_data = {
            "results": {
                "transcripts": [
                    {"transcript": "unclear speech"}
                ],
                "items": [
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "unclear", "confidence": "0.4"}
                        ],
                        "start_time": "0.0",
                        "end_time": "0.5"
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [
                            {"content": "speech", "confidence": "0.3"}
                        ],
                        "start_time": "0.6",
                        "end_time": "1.0"
                    }
                ]
            }
        }
        
        # Mock AWS calls
        mock_aws_clients.transcribe.start_transcription_job.return_value = transcription_response
        mock_aws_clients.transcribe.get_transcription_job.return_value = transcription_response
        
        import json
        mock_s3_response = Mock()
        mock_s3_response.read.return_value = json.dumps(transcript_data).encode('utf-8')
        mock_aws_clients.s3.get_object.return_value = {"Body": mock_s3_response}
        
        # Create recognition config
        config = RecognitionConfig(
            language_code="hi-IN",
            confidence_threshold=0.7,
            noise_reduction_enabled=True
        )
        
        # Test audio data
        audio_data = b"fake_unclear_audio_data" * 50
        
        # Perform recognition
        result = await speech_recognizer.recognize_speech(
            audio_data, config, RecognitionMode.REAL_TIME
        )
        
        # Verify uncertainty handling
        assert result.confidence < 0.7
        assert "[UNCERTAIN:" in result.transcript or "[NEEDS_CLARIFICATION]" in result.transcript
    
    @pytest.mark.asyncio
    async def test_voice_gateway_integration(self, voice_gateway):
        """Test integration between voice gateway and speech recognition."""
        from bharat_voice_assistant.voice.speech_recognition import RecognitionResult
        
        # Mock speech recognition result
        mock_result = RecognitionResult(
            transcript="मुझे पेंशन योजना की जानकारी चाहिए",
            confidence=0.92,
            language="hi-IN",
            alternatives=[],
            processing_time_ms=150,
            audio_quality_score=0.85,
            noise_level=0.15
        )
        
        voice_gateway.speech_recognizer.recognize_speech = AsyncMock(return_value=mock_result)
        
        # Create test session
        client_id = "test-client-integration"
        voice_gateway.active_sessions[client_id] = {
            "client_id": client_id,
            "language": "hi",
            "conversation_history": [],
            "client_info": {"location_type": "rural"}
        }
        
        # Test audio processing
        test_audio = b"fake_pension_query_audio" * 100
        quality_assessment = {
            "overall_score": 0.85,
            "quality_level": "good",
            "metrics": {"volume_level": 0.8, "noise_level": 0.15}
        }
        metadata = {"format": "raw"}
        
        # Process voice input
        result = await voice_gateway._process_voice_input(
            client_id, test_audio, quality_assessment, metadata
        )
        
        # Verify integration results
        assert result is not None
        assert result["recognized_text"] == "मुझे पेंशन योजना की जानकारी चाहिए"
        assert result["confidence"] == 0.92
        assert result["language"] == "hi"
        assert result["needs_clarification"] == False
        assert result["processing_time_ms"] == 150
        
        # Verify speech recognizer was called with correct config
        voice_gateway.speech_recognizer.recognize_speech.assert_called_once()
        call_args = voice_gateway.speech_recognizer.recognize_speech.call_args
        
        # Check that rural language model was selected
        recognition_config = call_args[0][1]  # Second argument
        assert recognition_config.custom_language_model == LanguageModel.HINDI_RURAL
        assert recognition_config.noise_reduction_enabled == True
        
        # Verify conversation history was updated
        session = voice_gateway.active_sessions[client_id]
        assert len(session["conversation_history"]) == 1
        history_entry = session["conversation_history"][0]
        assert history_entry["recognized_text"] == "मुझे पेंशन योजना की जानकारी चाहिए"
        assert history_entry["confidence"] == 0.92
        assert history_entry["needs_clarification"] == False
    
    @pytest.mark.asyncio
    async def test_language_model_selection(self, voice_gateway):
        """Test automatic language model selection based on user context."""
        from bharat_voice_assistant.voice.speech_recognition import RecognitionResult
        
        # Mock speech recognition result
        mock_result = RecognitionResult(
            transcript="test transcript",
            confidence=0.9,
            language="hi-IN",
            alternatives=[],
            processing_time_ms=100,
            audio_quality_score=0.8,
            noise_level=0.2
        )
        
        voice_gateway.speech_recognizer.recognize_speech = AsyncMock(return_value=mock_result)
        voice_gateway.speech_recognizer.optimize_for_network_conditions = AsyncMock(
            side_effect=lambda config, quality: config  # Return config unchanged
        )
        
        # Test rural user - should select rural model
        client_id_rural = "rural-client"
        voice_gateway.active_sessions[client_id_rural] = {
            "client_id": client_id_rural,
            "language": "hi",
            "conversation_history": [],
            "client_info": {"location_type": "rural", "network_quality": "poor"}
        }
        
        await voice_gateway._process_voice_input(
            client_id_rural, b"test_audio", {"quality_level": "good"}, {}
        )
        
        # Verify rural model was selected
        call_args = voice_gateway.speech_recognizer.recognize_speech.call_args
        recognition_config = call_args[0][1]
        assert recognition_config.custom_language_model == LanguageModel.HINDI_RURAL
        
        # Test urban user - should select urban model
        voice_gateway.speech_recognizer.recognize_speech.reset_mock()
        
        client_id_urban = "urban-client"
        voice_gateway.active_sessions[client_id_urban] = {
            "client_id": client_id_urban,
            "language": "hi",
            "conversation_history": [],
            "client_info": {"location_type": "urban", "network_quality": "good"}
        }
        
        await voice_gateway._process_voice_input(
            client_id_urban, b"test_audio", {"quality_level": "good"}, {}
        )
        
        # Verify urban model was selected
        call_args = voice_gateway.speech_recognizer.recognize_speech.call_args
        recognition_config = call_args[0][1]
        assert recognition_config.custom_language_model == LanguageModel.HINDI_URBAN
    
    def test_supported_languages_coverage(self, speech_recognizer):
        """Test that all required Indian languages are supported."""
        supported_languages = speech_recognizer.get_supported_languages()
        custom_models = speech_recognizer.get_custom_language_models()
        
        # Verify all required languages are supported
        required_languages = {
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
        
        for lang_code, aws_code in required_languages.items():
            assert lang_code in supported_languages
            assert supported_languages[lang_code] == aws_code
        
        # Verify custom models exist for all languages
        model_languages = set()
        for model_info in custom_models.values():
            model_languages.add(model_info["language_code"])
        
        for aws_code in required_languages.values():
            assert aws_code in model_languages
        
        # Verify rural-specific models exist
        rural_models = [
            LanguageModel.HINDI_RURAL,
            LanguageModel.TAMIL_RURAL,
            LanguageModel.TELUGU_RURAL,
            LanguageModel.BENGALI_RURAL,
            LanguageModel.MARATHI_RURAL,
            LanguageModel.GUJARATI_RURAL,
            LanguageModel.KANNADA_RURAL,
            LanguageModel.MALAYALAM_RURAL,
            LanguageModel.PUNJABI_RURAL
        ]
        
        for model in rural_models:
            assert model in custom_models
            assert "rural" in custom_models[model]["model_name"]
            assert "government-terms" in custom_models[model]["vocabulary"]