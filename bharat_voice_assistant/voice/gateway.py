"""
Voice Interface Gateway for the Bharat Voice Assistant.

This module provides the main WebSocket server for real-time audio streaming,
integrating audio processing, connection management, and voice recognition/synthesis.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, Optional, Callable
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import VoiceGatewayError
from .audio_processor import AudioProcessor
from .connection_manager import ConnectionManager
from .speech_recognition import SpeechRecognizer, RecognitionConfig, RecognitionMode, LanguageModel
from .text_to_speech import TextToSpeechSynthesizer, SynthesisConfig

logger = get_logger(__name__)


class VoiceInterfaceGateway:
    """
    Main voice interface gateway that handles WebSocket connections
    and coordinates audio processing for the Bharat Voice Assistant.
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        """
        Initialize the voice interface gateway.
        
        Args:
            host: Host address to bind the WebSocket server
            port: Port number for the WebSocket server
        """
        self.host = host
        self.port = port
        self.server = None
        
        # Initialize components
        self.audio_processor = AudioProcessor()
        self.connection_manager = ConnectionManager()
        self.speech_recognizer = SpeechRecognizer()
        self.tts_synthesizer = TextToSpeechSynthesizer()
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {
            "audio_data": self._handle_audio_data,
            "start_session": self._handle_start_session,
            "end_session": self._handle_end_session,
            "ping": self._handle_ping,
            "client_info": self._handle_client_info
        }
        
        # Session management
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"VoiceInterfaceGateway initialized on {host}:{port}")
    
    async def start(self):
        """Start the voice interface gateway server."""
        try:
            # Start connection manager
            await self.connection_manager.start()
            
            # Start WebSocket server
            self.server = await websockets.serve(
                self._handle_client_connection,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                compression=None  # Disable compression for audio data
            )
            
            logger.info(f"Voice Interface Gateway started on ws://{self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start Voice Interface Gateway: {e}")
            raise VoiceGatewayError(
                "Failed to start voice gateway server",
                error_code="GATEWAY_START_FAILED",
                context={"host": self.host, "port": self.port, "error": str(e)}
            )
    
    async def stop(self):
        """Stop the voice interface gateway server."""
        try:
            # Stop WebSocket server
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            # Stop connection manager
            await self.connection_manager.stop()
            
            # Clear active sessions
            self.active_sessions.clear()
            
            logger.info("Voice Interface Gateway stopped")
            
        except Exception as e:
            logger.error(f"Error stopping Voice Interface Gateway: {e}")
    
    async def _handle_client_connection(self, websocket, path):
        """Handle new client WebSocket connection."""
        client_id = str(uuid.uuid4())
        logger.info(f"New client connection: {client_id} from {websocket.remote_address}")
        
        try:
            # Register client with connection manager
            connected = await self.connection_manager.connect_client(websocket, client_id)
            
            if not connected:
                logger.warning(f"Failed to register client {client_id}")
                return
            
            # Handle client messages
            await self._client_message_loop(client_id)
            
        except ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Clean up client connection
            await self.connection_manager.disconnect_client(client_id)
            if client_id in self.active_sessions:
                del self.active_sessions[client_id]
    
    async def _client_message_loop(self, client_id: str):
        """Main message processing loop for a client."""
        while True:
            try:
                # Receive message from client
                message_data = await self.connection_manager.receive_audio_data(client_id)
                
                if message_data is None:
                    # Connection closed or timeout
                    break
                
                # Process message based on type
                message_type = message_data.get("type", "unknown")
                
                if message_type in self.message_handlers:
                    await self.message_handlers[message_type](client_id, message_data)
                else:
                    logger.warning(f"Unknown message type from client {client_id}: {message_type}")
                
            except Exception as e:
                logger.error(f"Error processing message from client {client_id}: {e}")
                break
    
    async def _handle_audio_data(self, client_id: str, message_data: Dict[str, Any]):
        """Handle incoming audio data from client."""
        try:
            audio_data = message_data.get("audio_data")
            metadata = message_data.get("metadata", {})
            
            if not audio_data:
                logger.warning(f"No audio data received from client {client_id}")
                return
            
            # Assess audio quality
            quality_assessment = await self.audio_processor.assess_audio_quality(audio_data)
            
            # Enhance audio if needed
            if quality_assessment["quality_level"] in ["poor", "acceptable"]:
                enhanced_audio = await self.audio_processor.enhance_audio(
                    audio_data, quality_assessment
                )
            else:
                enhanced_audio = audio_data
            
            # Process the audio (this would integrate with speech recognition)
            processed_result = await self._process_voice_input(
                client_id, enhanced_audio, quality_assessment, metadata
            )
            
            # Send response back to client
            if processed_result:
                await self._send_voice_response(client_id, processed_result)
            
        except Exception as e:
            logger.error(f"Error handling audio data from client {client_id}: {e}")
            await self._send_error_response(client_id, "AUDIO_PROCESSING_ERROR", str(e))
    
    async def _handle_start_session(self, client_id: str, message_data: Dict[str, Any]):
        """Handle session start request."""
        try:
            session_config = message_data.get("config", {})
            
            # Create session
            session = {
                "client_id": client_id,
                "started_at": asyncio.get_event_loop().time(),
                "language": session_config.get("language", "hi"),
                "audio_format": session_config.get("audio_format", "raw"),
                "context": {},
                "conversation_history": []
            }
            
            self.active_sessions[client_id] = session
            
            # Send session confirmation
            response = {
                "type": "session_started",
                "session_id": client_id,
                "config": session_config,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self._send_message(client_id, response)
            
            logger.info(f"Session started for client {client_id}")
            
        except Exception as e:
            logger.error(f"Error starting session for client {client_id}: {e}")
            await self._send_error_response(client_id, "SESSION_START_ERROR", str(e))
    
    async def _handle_end_session(self, client_id: str, message_data: Dict[str, Any]):
        """Handle session end request."""
        try:
            if client_id in self.active_sessions:
                session = self.active_sessions[client_id]
                session_duration = asyncio.get_event_loop().time() - session["started_at"]
                
                # Send session summary
                response = {
                    "type": "session_ended",
                    "session_id": client_id,
                    "duration_seconds": session_duration,
                    "interactions_count": len(session.get("conversation_history", [])),
                    "timestamp": asyncio.get_event_loop().time()
                }
                
                await self._send_message(client_id, response)
                
                # Clean up session
                del self.active_sessions[client_id]
                
                logger.info(f"Session ended for client {client_id} (duration: {session_duration:.1f}s)")
            
        except Exception as e:
            logger.error(f"Error ending session for client {client_id}: {e}")
    
    async def _handle_ping(self, client_id: str, message_data: Dict[str, Any]):
        """Handle ping message."""
        try:
            response = {
                "type": "pong",
                "timestamp": asyncio.get_event_loop().time(),
                "original_timestamp": message_data.get("timestamp")
            }
            
            await self._send_message(client_id, response)
            
        except Exception as e:
            logger.error(f"Error handling ping from client {client_id}: {e}")
    
    async def _handle_client_info(self, client_id: str, message_data: Dict[str, Any]):
        """Handle client information update."""
        try:
            client_info = message_data.get("info", {})
            
            # Update session with client info
            if client_id in self.active_sessions:
                session = self.active_sessions[client_id]
                session["client_info"] = client_info
                
                # Update preferred language if provided
                if "language" in client_info:
                    session["language"] = client_info["language"]
            
            # Send acknowledgment
            response = {
                "type": "client_info_received",
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self._send_message(client_id, response)
            
            logger.debug(f"Client info updated for {client_id}: {client_info}")
            
        except Exception as e:
            logger.error(f"Error handling client info from {client_id}: {e}")
    
    async def _process_voice_input(self, client_id: str, audio_data: bytes,
                                 quality_assessment: Dict[str, Any],
                                 metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process voice input and generate response.
        
        This integrates with AWS Transcribe for speech recognition
        and handles confidence scoring and uncertainty.
        """
        try:
            # Get session context
            session = self.active_sessions.get(client_id, {})
            language = session.get("language", "hi")
            
            # Map language to AWS Transcribe language code
            language_code = config.voice.supported_languages.get(language, "hi-IN")
            
            # Determine appropriate language model based on language and context
            custom_model = self._select_language_model(language, session.get("client_info", {}))
            
            # Determine if noise reduction should be enabled
            # Always enable for rural environments or poor audio quality
            client_info = session.get("client_info", {})
            is_rural = client_info.get("location_type") == "rural" or \
                      client_info.get("network_quality") == "poor"
            poor_audio_quality = quality_assessment.get("quality_level") in ["poor", "acceptable"]
            
            # Create recognition configuration
            recognition_config = RecognitionConfig(
                language_code=language_code,
                custom_language_model=custom_model,
                enable_speaker_identification=False,
                enable_word_timestamps=True,
                enable_automatic_punctuation=True,
                confidence_threshold=config.voice.recognition_confidence_threshold,
                noise_reduction_enabled=is_rural or poor_audio_quality
            )
            
            # Optimize for network conditions if needed
            network_quality = client_info.get("network_quality", "good")
            if network_quality in ["poor", "very_poor"]:
                recognition_config = await self.speech_recognizer.optimize_for_network_conditions(
                    recognition_config, network_quality
                )
            
            # Perform speech recognition
            recognition_result = await self.speech_recognizer.recognize_speech(
                audio_data, recognition_config, RecognitionMode.REAL_TIME
            )
            
            # Check if we need to request clarification due to low confidence
            needs_clarification = recognition_result.confidence < config.voice.recognition_confidence_threshold
            
            # Generate appropriate response based on recognition results
            if needs_clarification:
                response_text = self._generate_clarification_request(language, recognition_result)
            else:
                # Process the recognized text (placeholder for NLP integration)
                response_text = self._generate_response_for_recognized_text(
                    recognition_result.transcript, language, session
                )
            
            result = {
                "recognized_text": recognition_result.transcript,
                "confidence": recognition_result.confidence,
                "language": language,
                "response_text": response_text,
                "audio_quality": quality_assessment["quality_level"],
                "processing_time_ms": recognition_result.processing_time_ms,
                "needs_clarification": needs_clarification,
                "noise_level": recognition_result.noise_level,
                "alternatives": recognition_result.alternatives[:3],  # Top 3 alternatives
                "word_timestamps": recognition_result.word_timestamps
            }
            
            # Update conversation history
            if client_id in self.active_sessions:
                self.active_sessions[client_id]["conversation_history"].append({
                    "timestamp": asyncio.get_event_loop().time(),
                    "input_quality": quality_assessment,
                    "recognized_text": recognition_result.transcript,
                    "confidence": recognition_result.confidence,
                    "response_text": response_text,
                    "needs_clarification": needs_clarification
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing voice input for client {client_id}: {e}")
            return None
    
    def _select_language_model(self, language: str, client_info: Dict[str, Any]) -> Optional[LanguageModel]:
        """
        Select appropriate custom language model based on language and user context.
        
        This implements the requirement for custom language models for Indian languages.
        """
        try:
            # Check if user is from rural area (based on client info)
            is_rural = client_info.get("location_type") == "rural" or \
                      client_info.get("network_quality") == "poor"
            
            # Map language to appropriate model
            language_model_map = {
                "hi": LanguageModel.HINDI_RURAL if is_rural else LanguageModel.HINDI_URBAN,
                "en": LanguageModel.ENGLISH_INDIAN,
                "ta": LanguageModel.TAMIL_RURAL,
                "te": LanguageModel.TELUGU_RURAL,
                "bn": LanguageModel.BENGALI_RURAL,
                "mr": LanguageModel.MARATHI_RURAL,
                "gu": LanguageModel.GUJARATI_RURAL,
                "kn": LanguageModel.KANNADA_RURAL,
                "ml": LanguageModel.MALAYALAM_RURAL,
                "pa": LanguageModel.PUNJABI_RURAL
            }
            
            selected_model = language_model_map.get(language)
            
            if selected_model:
                logger.debug(f"Selected language model: {selected_model.value} for language: {language}")
            
            return selected_model
            
        except Exception as e:
            logger.warning(f"Error selecting language model: {e}")
            return None
    
    def _generate_clarification_request(self, language: str, recognition_result) -> str:
        """
        Generate clarification request in user's language when confidence is low.
        
        This implements the requirement for uncertainty handling.
        """
        clarification_messages = {
            "hi": "मुझे आपकी बात स्पष्ट रूप से समझ नहीं आई। कृपया दोबारा कहें।",
            "en": "I didn't understand you clearly. Please repeat what you said.",
            "ta": "உங்கள் பேச்சு தெளிவாக புரியவில்லை. தயவுசெய்து மீண்டும் சொல்லுங்கள்.",
            "te": "మీ మాట స్పష్టంగా అర్థం కాలేదు. దయచేసి మళ్లీ చెప్పండి.",
            "bn": "আমি আপনার কথা স্পষ্ট বুঝতে পারিনি। দয়া করে আবার বলুন।",
            "mr": "मला तुमचे म्हणणे स्पष्टपणे समजले नाही. कृपया पुन्हा सांगा.",
            "gu": "મને તમારી વાત સ્પષ્ટ રીતે સમજાઈ નથી. કૃપા કરીને ફરીથી કહો.",
            "kn": "ನಿಮ್ಮ ಮಾತು ಸ್ಪಷ್ಟವಾಗಿ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ.",
            "ml": "നിങ്ങളുടെ വാക്കുകൾ വ്യക്തമായി മനസ്സിലായില്ല. ദയവായി വീണ്ടും പറയുക.",
            "pa": "ਮੈਨੂੰ ਤੁਹਾਡੀ ਗੱਲ ਸਪੱਸ਼ਟ ਰੂਪ ਵਿੱਚ ਸਮਝ ਨਹੀਂ ਆਈ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਕਹੋ।"
        }
        
        # Add noise-specific clarification if high noise detected
        if recognition_result.noise_level > 0.6:
            noise_messages = {
                "hi": "आसपास बहुत शोर है। कृपया शांत जगह से बात करें।",
                "en": "There's too much background noise. Please speak from a quieter place.",
                "ta": "சுற்றிலும் அதிக சத்தம் உள்ளது. அமைதியான இடத்திலிருந்து பேசுங்கள்.",
                "te": "చుట్టూ చాలా శబ్దం ఉంది. దయచేసి నిశ్శబ్ద ప్రదేశం నుండి మాట్లాడండి.",
                "bn": "চারপাশে অনেক শব্দ আছে। দয়া করে শান্ত জায়গা থেকে কথা বলুন।",
                "mr": "आजूबाजूला खूप आवाज आहे. कृपया शांत ठिकाणाहून बोला.",
                "gu": "આસપાસ ઘણો અવાજ છે. કૃપા કરીને શાંત જગ્યાએથી બોલો.",
                "kn": "ಸುತ್ತಲೂ ತುಂಬಾ ಶಬ್ದವಿದೆ. ದಯವಿಟ್ಟು ಶಾಂತ ಸ್ಥಳದಿಂದ ಮಾತನಾಡಿ.",
                "ml": "ചുറ്റും വളരെ ശബ്ദമുണ്ട്. ദയവായി ശാന്തമായ സ്ഥലത്തുനിന്ന് സംസാരിക്കുക.",
                "pa": "ਆਲੇ-ਦੁਆਲੇ ਬਹੁਤ ਸ਼ੋਰ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਸ਼ਾਂਤ ਜਗ੍ਹਾ ਤੋਂ ਬੋਲੋ।"
            }
            return noise_messages.get(language, noise_messages["en"])
        
        return clarification_messages.get(language, clarification_messages["en"])
    
    def _generate_response_for_recognized_text(self, text: str, language: str, 
                                             session: Dict[str, Any]) -> str:
        """
        Generate response for successfully recognized text.
        
        This is a placeholder for integration with NLP and scheme discovery components.
        """
        # Placeholder responses acknowledging successful recognition
        acknowledgment_messages = {
            "hi": f"मैं समझ गया: '{text}'. मैं आपकी मदद कैसे कर सकता हूँ?",
            "en": f"I understood: '{text}'. How can I help you?",
            "ta": f"நான் புரிந்துகொண்டேன்: '{text}'. நான் உங்களுக்கு எப்படி உதவ முடியும்?",
            "te": f"నేను అర్థం చేసుకున్నాను: '{text}'. నేను మీకు ఎలా సహాయం చేయగలను?",
            "bn": f"আমি বুঝেছি: '{text}'। আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
            "mr": f"मला समजले: '{text}'. मी तुम्हाला कशी मदत करू शकतो?",
            "gu": f"મને સમજાયું: '{text}'. હું તમારી કેવી રીતે મદદ કરી શકું?",
            "kn": f"ನನಗೆ ಅರ್ಥವಾಯಿತು: '{text}'. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
            "ml": f"എനിക്ക് മനസ്സിലായി: '{text}'. എനിക്ക് നിങ്ങളെ എങ്ങനെ സഹായിക്കാം?",
            "pa": f"ਮੈਨੂੰ ਸਮਝ ਆ ਗਿਆ: '{text}'। ਮੈਂ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ?"
        }
        
        return acknowledgment_messages.get(language, acknowledgment_messages["en"])
    
    async def _send_voice_response(self, client_id: str, processing_result: Dict[str, Any]):
        """Send voice response to client with synthesized audio."""
        try:
            response_text = processing_result.get("response_text", "")
            language = processing_result.get("language", "hi")
            
            if not response_text:
                logger.warning(f"No response text to synthesize for client {client_id}")
                return
            
            # Get session context for connection quality
            session = self.active_sessions.get(client_id, {})
            client_info = session.get("client_info", {})
            connection_speed = client_info.get("network_quality", "medium")
            
            # Create synthesis configuration optimized for connection speed
            synthesis_config = self.tts_synthesizer.create_synthesis_config(
                language=language,
                connection_speed=connection_speed,
                prefer_neural=True
            )
            
            # Synthesize speech
            synthesis_result = await self.tts_synthesizer.synthesize_speech(
                response_text, synthesis_config, connection_speed
            )
            
            # Prepare response with both text and audio
            response = {
                "type": "voice_response",
                "text": response_text,
                "language": language,
                "confidence": processing_result.get("confidence", 0.0),
                "audio_quality": processing_result.get("audio_quality", "unknown"),
                "processing_time_ms": processing_result.get("processing_time_ms", 0),
                "timestamp": asyncio.get_event_loop().time(),
                
                # Audio synthesis information
                "audio_data": synthesis_result.audio_data.hex(),  # Convert bytes to hex string
                "audio_format": synthesis_result.audio_format,
                "audio_duration_ms": synthesis_result.duration_ms,
                "voice_id": synthesis_result.voice_id,
                "synthesis_time_ms": synthesis_result.processing_time_ms,
                "compression_ratio": synthesis_result.compression_ratio,
                "audio_size_bytes": len(synthesis_result.audio_data)
            }
            
            await self._send_message(client_id, response)
            
            logger.debug(f"Sent voice response to client {client_id}: "
                        f"{len(response_text)} chars, {len(synthesis_result.audio_data)} bytes audio")
            
        except Exception as e:
            logger.error(f"Error sending voice response to client {client_id}: {e}")
            # Send text-only response as fallback
            await self._send_text_fallback_response(client_id, processing_result)
    
    async def _send_text_fallback_response(self, client_id: str, processing_result: Dict[str, Any]):
        """Send text-only response as fallback when TTS fails."""
        try:
            response_text = processing_result.get("response_text", "")
            
            response = {
                "type": "voice_response",
                "text": response_text,
                "language": processing_result.get("language", "hi"),
                "confidence": processing_result.get("confidence", 0.0),
                "audio_quality": processing_result.get("audio_quality", "unknown"),
                "processing_time_ms": processing_result.get("processing_time_ms", 0),
                "timestamp": asyncio.get_event_loop().time(),
                "fallback_mode": True,
                "fallback_reason": "TTS synthesis failed"
            }
            
            await self._send_message(client_id, response)
            
        except Exception as e:
            logger.error(f"Error sending text fallback response to client {client_id}: {e}")
    
    async def _send_error_response(self, client_id: str, error_code: str, error_message: str):
        """Send error response to client."""
        try:
            response = {
                "type": "error",
                "error_code": error_code,
                "error_message": error_message,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self._send_message(client_id, response)
            
        except Exception as e:
            logger.error(f"Error sending error response to client {client_id}: {e}")
    
    async def _send_message(self, client_id: str, message: Dict[str, Any]):
        """Send message to client."""
        try:
            # Convert message to JSON and send via connection manager
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            
            success = await self.connection_manager.send_audio_data(
                client_id, message_bytes, {"content_type": "application/json"}
            )
            
            if not success:
                logger.warning(f"Failed to send message to client {client_id}")
            
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        active_connections = self.connection_manager.get_active_connections()
        
        stats = {
            "active_connections": len(active_connections),
            "active_sessions": len(self.active_sessions),
            "server_uptime": asyncio.get_event_loop().time(),
            "connection_quality_distribution": {},
            "total_interactions": sum(
                len(session.get("conversation_history", []))
                for session in self.active_sessions.values()
            )
        }
        
        # Calculate connection quality distribution
        quality_counts = {}
        for client_id in active_connections:
            quality = self.connection_manager.get_connection_quality(client_id)
            if quality:
                quality_name = quality.value
                quality_counts[quality_name] = quality_counts.get(quality_name, 0) + 1
        
        stats["connection_quality_distribution"] = quality_counts
        
        return stats