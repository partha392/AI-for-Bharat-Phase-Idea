"""
Main orchestrator for the Bharat Voice Assistant system.

This module coordinates all components and provides the main entry point
for voice interactions. It integrates:
- Voice processing with language understanding
- Scheme discovery with grievance filing
- Status tracking with notification system
- Privacy manager with all data handling components
- Accessibility features and user assistance
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
from datetime import datetime

from .logging import get_logger
from .exceptions import BharatVoiceAssistantError
from ..voice import (
    VoiceInterfaceGateway, AudioProcessor, SpeechRecognizer, 
    TextToSpeechSynthesizer, AudioEnhancementSystem, AudioEnhancementConfig
)
from ..language import (
    LanguageProcessor, ConversationManager, IntentClassifier,
    EntityExtractor, ContextManager
)
from ..schemes import (
    SchemeDiscoveryService, IntelligentSchemeMatcher, EligibilityAssessor, UserProfileManager
)
from ..grievance import (
    GrievanceWorkflowManager, ConversationalFilingAssistant
)
from ..integration import GovernmentIntegrationService
from ..privacy import PrivacyManager
from ..accessibility import (
    UserAssistanceSystem, SimpleCommunicationManager, 
    CommandPatternManager, AccessibleErrorHandler, MultiModalInterface
)


logger = get_logger(__name__)


class InteractionState(Enum):
    """States of user interaction."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    WAITING_FOR_INPUT = "waiting_for_input"
    ERROR = "error"
    COMPLETED = "completed"


class SessionType(Enum):
    """Types of user sessions."""
    SCHEME_DISCOVERY = "scheme_discovery"
    GRIEVANCE_FILING = "grievance_filing"
    STATUS_TRACKING = "status_tracking"
    GENERAL_INQUIRY = "general_inquiry"
    HELP_SESSION = "help_session"


@dataclass
class UserSession:
    """Represents a user interaction session."""
    session_id: str
    user_id: str
    session_type: SessionType
    state: InteractionState = InteractionState.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    user_profile: Dict[str, Any] = field(default_factory=dict)
    current_task: Optional[str] = None
    error_count: int = 0
    assistance_level: str = "standard"


@dataclass
class InteractionRequest:
    """Represents an incoming interaction request."""
    session_id: str
    user_id: str
    audio_data: Optional[bytes] = None
    text_input: Optional[str] = None
    input_type: str = "voice"
    language: str = "hindi"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InteractionResponse:
    """Represents a response to user interaction."""
    session_id: str
    response_text: str
    audio_response: Optional[bytes] = None
    response_type: str = "voice"
    language: str = "hindi"
    next_action: Optional[str] = None
    context_updates: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    processing_time: float = 0.0
    confidence: float = 1.0


class BharatVoiceOrchestrator:
    """Main orchestrator for the Bharat Voice Assistant system."""
    
    def __init__(self):
        """Initialize the orchestrator with all components."""
        self.logger = get_logger(__name__)
        
        # Initialize core components
        self._initialize_components()
        
        # Session management
        self._active_sessions: Dict[str, UserSession] = {}
        self._session_timeout = 600  # 10 minutes
        
        # Performance tracking
        self._interaction_count = 0
        self._total_processing_time = 0.0
        self._error_count = 0
        
        self.logger.info("Bharat Voice Orchestrator initialized successfully")
    
    def _initialize_components(self):
        """Initialize all system components."""
        try:
            # Voice processing components
            self.voice_gateway = VoiceInterfaceGateway()
            self.audio_processor = AudioProcessor()
            self.speech_recognizer = SpeechRecognizer()
            self.tts_synthesizer = TextToSpeechSynthesizer()
            self.audio_enhancer = AudioEnhancementSystem(AudioEnhancementConfig())
            
            # Language processing components
            self.language_processor = LanguageProcessor()
            self.conversation_manager = ConversationManager()
            self.intent_classifier = IntentClassifier()
            self.entity_extractor = EntityExtractor()
            self.context_tracker = ContextManager()
            
            # Business logic components
            self.user_profile_manager = UserProfileManager()
            self.scheme_discovery = SchemeDiscoveryService()
            self.scheme_matching = IntelligentSchemeMatcher()
            self.eligibility_assessment = EligibilityAssessor(self.user_profile_manager)
            self.grievance_workflow = GrievanceWorkflowManager()
            self.form_filler = ConversationalFilingAssistant()
            
            # Integration and privacy
            self.government_integration = GovernmentIntegrationService()
            self.privacy_manager = PrivacyManager()
            
            # Accessibility components
            self.user_assistance = UserAssistanceSystem()
            self.communication_manager = SimpleCommunicationManager()
            self.command_manager = CommandPatternManager()
            self.error_handler = AccessibleErrorHandler()
            self.multimodal_interface = MultiModalInterface()
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise BharatVoiceAssistantError(
                "System initialization failed",
                error_code="ORCHESTRATOR_INIT_FAILED",
                context={"error": str(e)}
            )
    
    async def process_interaction(self, request: InteractionRequest) -> InteractionResponse:
        """
        Process a user interaction request.
        
        Args:
            request: The interaction request
            
        Returns:
            Interaction response
        """
        start_time = time.time()
        
        try:
            # Get or create session
            session = await self._get_or_create_session(request)
            session.state = InteractionState.PROCESSING
            session.last_activity = datetime.now()
            
            # Process input based on type
            if request.input_type == "voice" and request.audio_data:
                response = await self._process_voice_interaction(request, session)
            elif request.input_type == "text" and request.text_input:
                response = await self._process_text_interaction(request, session)
            else:
                raise BharatVoiceAssistantError(
                    "Invalid input type or missing data",
                    error_code="INVALID_INPUT"
                )
            
            # Update session
            session.state = InteractionState.COMPLETED
            session.conversation_history.append({
                "timestamp": request.timestamp,
                "user_input": request.text_input or "voice_input",
                "response": response.response_text,
                "session_type": session.session_type.value
            })
            
            # Calculate processing time
            processing_time = time.time() - start_time
            response.processing_time = processing_time
            
            # Update performance metrics
            self._update_performance_metrics(processing_time, success=True)
            
            self.logger.info(f"Interaction processed successfully in {processing_time:.3f}s")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to process interaction: {e}")
            
            # Handle error with accessibility features
            error_response = await self._handle_interaction_error(e, request, session if 'session' in locals() else None)
            
            # Update performance metrics
            processing_time = time.time() - start_time
            error_response.processing_time = processing_time
            self._update_performance_metrics(processing_time, success=False)
            
            return error_response
    
    async def _process_voice_interaction(
        self, 
        request: InteractionRequest, 
        session: UserSession
    ) -> InteractionResponse:
        """Process voice-based interaction."""
        try:
            # Enhance audio quality
            enhancement_result = await self.audio_enhancer.enhance_audio(
                request.user_id,
                request.audio_data,
                sample_rate=16000
            )
            
            enhanced_audio = enhancement_result["enhanced_audio"]
            
            # Speech recognition
            recognition_result = await self.speech_recognizer.recognize_speech(
                enhanced_audio,
                language=request.language
            )
            
            if not recognition_result.success:
                return await self._handle_recognition_error(recognition_result, session)
            
            # Update request with recognized text
            request.text_input = recognition_result.transcript
            
            # Check for user assistance needs
            assistance_response = self.user_assistance.process_user_interaction(
                request.user_id,
                recognition_result.transcript,
                recognition_result.processing_time,
                self._create_assistance_context(session)
            )
            
            # Process the recognized text
            text_response = await self._process_text_interaction(request, session)
            
            # Apply speaking pace adaptation
            response_timing = self.audio_enhancer.get_user_response_timing(request.user_id)
            
            # Generate audio response
            audio_response = await self._generate_audio_response(
                text_response.response_text,
                request.language,
                response_timing
            )
            
            # Combine responses
            text_response.audio_response = audio_response
            text_response.response_type = "voice"
            
            # Add assistance if needed
            if assistance_response.get("assistance_needed"):
                text_response.suggestions.extend(assistance_response.get("suggestions", []))
                if assistance_response.get("help_content"):
                    text_response.response_text = (
                        assistance_response["help_content"] + " " + text_response.response_text
                    )
            
            return text_response
            
        except Exception as e:
            self.logger.error(f"Failed to process voice interaction: {e}")
            raise
    
    async def _process_text_interaction(
        self, 
        request: InteractionRequest, 
        session: UserSession
    ) -> InteractionResponse:
        """Process text-based interaction."""
        try:
            # Language processing
            language_result = await self.language_processor.process_text(
                request.text_input,
                language=request.language,
                context=session.context
            )
            
            # Intent classification
            intent_result = await self.intent_classifier.classify_intent(
                request.text_input,
                language=request.language
            )
            
            # Entity extraction
            entities = await self.entity_extractor.extract_entities(
                request.text_input,
                language=request.language
            )
            
            # Update conversation context
            self.context_tracker.update_context(
                session.session_id,
                {
                    "last_intent": intent_result.intent,
                    "entities": entities,
                    "language_result": language_result
                }
            )
            
            # Route to appropriate handler based on intent
            response = await self._route_intent(intent_result, entities, session, request)
            
            # Apply communication simplification
            simplified_response = self.communication_manager.generate_accessible_response(
                response.response_text,
                "success",
                self._get_communication_config(session.user_profile)
            )
            
            response.response_text = simplified_response
            
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to process text interaction: {e}")
            raise
    
    async def _route_intent(
        self, 
        intent_result, 
        entities: Dict[str, Any], 
        session: UserSession,
        request: InteractionRequest
    ) -> InteractionResponse:
        """Route request to appropriate handler based on intent."""
        try:
            intent = intent_result.intent
            
            if intent == "scheme_discovery":
                return await self._handle_scheme_discovery(entities, session, request)
            elif intent == "grievance_filing":
                return await self._handle_grievance_filing(entities, session, request)
            elif intent == "status_tracking":
                return await self._handle_status_tracking(entities, session, request)
            elif intent == "help_request":
                return await self._handle_help_request(entities, session, request)
            elif intent == "navigation":
                return await self._handle_navigation(entities, session, request)
            else:
                return await self._handle_general_inquiry(entities, session, request)
                
        except Exception as e:
            self.logger.error(f"Failed to route intent: {e}")
            raise
    
    async def _handle_scheme_discovery(
        self, 
        entities: Dict[str, Any], 
        session: UserSession,
        request: InteractionRequest
    ) -> InteractionResponse:
        """Handle scheme discovery requests."""
        try:
            session.session_type = SessionType.SCHEME_DISCOVERY
            session.current_task = "scheme_discovery"
            
            # Extract user requirements from entities
            user_requirements = self._extract_user_requirements(entities, session)
            
            # Find matching schemes
            matching_schemes = await self.scheme_matching.find_matching_schemes(
                user_requirements,
                session.user_profile
            )
            
            # Assess eligibility for top schemes
            eligible_schemes = []
            for scheme in matching_schemes[:5]:  # Check top 5 schemes
                eligibility = await self.eligibility_assessment.assess_eligibility(
                    scheme,
                    session.user_profile
                )
                if eligibility.is_eligible:
                    eligible_schemes.append({
                        "scheme": scheme,
                        "eligibility": eligibility
                    })
            
            # Generate response
            if eligible_schemes:
                response_text = self._format_scheme_response(eligible_schemes, request.language)
                next_action = "scheme_details"
            else:
                response_text = (
                    "आपके लिए कोई उपयुक्त योजना नहीं मिली। कृपया अपनी जानकारी दोबारा बताएं।" 
                    if request.language == "hindi" else
                    "No suitable schemes found for you. Please provide your information again."
                )
                next_action = "retry_scheme_search"
            
            return InteractionResponse(
                session_id=session.session_id,
                response_text=response_text,
                language=request.language,
                next_action=next_action,
                context_updates={"eligible_schemes": eligible_schemes}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle scheme discovery: {e}")
            raise
    
    async def _handle_grievance_filing(
        self, 
        entities: Dict[str, Any], 
        session: UserSession,
        request: InteractionRequest
    ) -> InteractionResponse:
        """Handle grievance filing requests."""
        try:
            session.session_type = SessionType.GRIEVANCE_FILING
            session.current_task = "grievance_filing"
            
            # Start or continue grievance filing workflow
            if "grievance_state" not in session.context:
                # Start new grievance
                workflow_state = await self.grievance_workflow.start_grievance_filing(
                    session.user_id,
                    entities
                )
                session.context["grievance_state"] = workflow_state
            else:
                # Continue existing grievance
                workflow_state = await self.grievance_workflow.continue_grievance_filing(
                    session.context["grievance_state"],
                    request.text_input,
                    entities
                )
                session.context["grievance_state"] = workflow_state
            
            # Generate appropriate response based on workflow state
            if workflow_state.is_complete:
                # Submit grievance through government integration
                submission_result = await self.government_integration.submit_grievance(
                    workflow_state.grievance_data
                )
                
                if submission_result.success:
                    response_text = (
                        f"आपकी शिकायत सफलतापूर्वक दर्ज हो गई है। आपका रेफरेंस नंबर: {submission_result.reference_number}"
                        if request.language == "hindi" else
                        f"Your complaint has been filed successfully. Your reference number: {submission_result.reference_number}"
                    )
                    next_action = "completed"
                else:
                    response_text = (
                        "शिकायत दर्ज करने में समस्या हुई है। कृपया बाद में कोशिश करें।"
                        if request.language == "hindi" else
                        "There was a problem filing your complaint. Please try again later."
                    )
                    next_action = "retry"
            else:
                # Continue with next step
                response_text = workflow_state.next_prompt
                next_action = "continue_grievance"
            
            return InteractionResponse(
                session_id=session.session_id,
                response_text=response_text,
                language=request.language,
                next_action=next_action,
                context_updates={"grievance_state": workflow_state}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle grievance filing: {e}")
            raise
    
    async def _handle_status_tracking(
        self, 
        entities: Dict[str, Any], 
        session: UserSession,
        request: InteractionRequest
    ) -> InteractionResponse:
        """Handle status tracking requests."""
        try:
            session.session_type = SessionType.STATUS_TRACKING
            session.current_task = "status_tracking"
            
            # Extract reference number from entities
            reference_number = entities.get("reference_number")
            
            if not reference_number:
                response_text = (
                    "कृपया अपना रेफरेंस नंबर बताएं।"
                    if request.language == "hindi" else
                    "Please provide your reference number."
                )
                next_action = "get_reference_number"
            else:
                # Check status through government integration
                status_result = await self.government_integration.check_status(reference_number)
                
                if status_result.success:
                    response_text = self._format_status_response(status_result, request.language)
                    next_action = "status_provided"
                else:
                    response_text = (
                        "इस रेफरेंस नंबर की कोई जानकारी नहीं मिली। कृपया नंबर चेक करें।"
                        if request.language == "hindi" else
                        "No information found for this reference number. Please check the number."
                    )
                    next_action = "retry_reference_number"
            
            return InteractionResponse(
                session_id=session.session_id,
                response_text=response_text,
                language=request.language,
                next_action=next_action
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle status tracking: {e}")
            raise
    
    async def _handle_help_request(
        self, 
        entities: Dict[str, Any], 
        session: UserSession,
        request: InteractionRequest
    ) -> InteractionResponse:
        """Handle help requests."""
        try:
            session.session_type = SessionType.HELP_SESSION
            session.current_task = "help"
            
            # Get available commands help
            help_text = self.command_manager.get_command_help(request.language)
            
            return InteractionResponse(
                session_id=session.session_id,
                response_text=help_text,
                language=request.language,
                next_action="help_provided"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle help request: {e}")
            raise
    
    async def _handle_navigation(
        self, 
        entities: Dict[str, Any], 
        session: UserSession,
        request: InteractionRequest
    ) -> InteractionResponse:
        """Handle navigation commands."""
        try:
            # Process navigation command
            command_result = self.command_manager.process_voice_command(
                request.text_input,
                request.language,
                session.context
            )
            
            if command_result["recognized"]:
                response_text = command_result["response_text"]
                next_action = command_result["next_action"]
            else:
                response_text = (
                    "मैं समझ नहीं पाया। कृपया फिर से कहें।"
                    if request.language == "hindi" else
                    "I didn't understand. Please say again."
                )
                next_action = "retry"
            
            return InteractionResponse(
                session_id=session.session_id,
                response_text=response_text,
                language=request.language,
                next_action=next_action,
                suggestions=command_result.get("suggestions", [])
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle navigation: {e}")
            raise
    
    async def _handle_general_inquiry(
        self, 
        entities: Dict[str, Any], 
        session: UserSession,
        request: InteractionRequest
    ) -> InteractionResponse:
        """Handle general inquiries."""
        try:
            session.session_type = SessionType.GENERAL_INQUIRY
            
            # Generate general response
            response_text = (
                "मैं आपकी मदद करने के लिए यहाँ हूँ। आप योजना खोजने, शिकायत दर्ज करने, या स्थिति जांचने के लिए कह सकते हैं।"
                if request.language == "hindi" else
                "I'm here to help you. You can ask me to find schemes, file complaints, or check status."
            )
            
            return InteractionResponse(
                session_id=session.session_id,
                response_text=response_text,
                language=request.language,
                next_action="general_help",
                suggestions=[
                    "योजना बताओ" if request.language == "hindi" else "Show schemes",
                    "शिकायत करनी है" if request.language == "hindi" else "File complaint",
                    "स्थिति जांचें" if request.language == "hindi" else "Check status"
                ]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle general inquiry: {e}")
            raise
    
    async def _get_or_create_session(self, request: InteractionRequest) -> UserSession:
        """Get existing session or create new one."""
        try:
            session_id = request.session_id
            
            if session_id in self._active_sessions:
                session = self._active_sessions[session_id]
                
                # Check if session has timed out
                time_since_activity = (datetime.now() - session.last_activity).total_seconds()
                if time_since_activity > self._session_timeout:
                    # Create new session
                    session = self._create_new_session(request)
                    self._active_sessions[session_id] = session
            else:
                # Create new session
                session = self._create_new_session(request)
                self._active_sessions[session_id] = session
            
            return session
            
        except Exception as e:
            self.logger.error(f"Failed to get or create session: {e}")
            raise
    
    def _create_new_session(self, request: InteractionRequest) -> UserSession:
        """Create a new user session."""
        return UserSession(
            session_id=request.session_id,
            user_id=request.user_id,
            session_type=SessionType.GENERAL_INQUIRY,
            user_profile=self._get_user_profile(request.user_id)
        )
    
    def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile (placeholder - would integrate with user management system)."""
        return {
            "user_id": user_id,
            "preferred_language": "hindi",
            "education_level": "basic",
            "location": "unknown",
            "age": 30,
            "device_type": "mobile"
        }
    
    async def _generate_audio_response(
        self, 
        text: str, 
        language: str,
        response_timing: Dict[str, float]
    ) -> bytes:
        """Generate audio response with appropriate timing."""
        try:
            # Apply response delay
            if response_timing.get("response_delay", 0) > 0:
                await asyncio.sleep(response_timing["response_delay"])
            
            # Generate speech
            synthesis_result = await self.tts_synthesizer.synthesize_speech(
                text,
                language=language,
                speech_rate=response_timing.get("speech_rate", 1.0)
            )
            
            return synthesis_result.audio_data
            
        except Exception as e:
            self.logger.error(f"Failed to generate audio response: {e}")
            return b""  # Return empty bytes on error
    
    async def _handle_interaction_error(
        self, 
        error: Exception, 
        request: InteractionRequest,
        session: Optional[UserSession]
    ) -> InteractionResponse:
        """Handle interaction errors with accessibility features."""
        try:
            # Create error context
            from ..accessibility.error_handling import ErrorContext
            
            error_context = ErrorContext(
                user_language=request.language,
                current_task=session.current_task if session else None,
                device_type=session.user_profile.get("device_type") if session else "mobile"
            )
            
            # Get user-friendly error explanation
            error_explanation = self.error_handler.handle_error(error, error_context)
            
            return InteractionResponse(
                session_id=request.session_id,
                response_text=error_explanation.simple_message,
                language=request.language,
                next_action="error_handled",
                suggestions=error_explanation.recovery_steps[:3]  # Limit to 3 suggestions
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle interaction error: {e}")
            # Fallback error response
            fallback_message = (
                "माफ करें, कुछ समस्या हुई है। कृपया फिर से कोशिश करें।"
                if request.language == "hindi" else
                "Sorry, there was a problem. Please try again."
            )
            
            return InteractionResponse(
                session_id=request.session_id,
                response_text=fallback_message,
                language=request.language,
                next_action="error"
            )
    
    def _update_performance_metrics(self, processing_time: float, success: bool):
        """Update system performance metrics."""
        self._interaction_count += 1
        self._total_processing_time += processing_time
        
        if not success:
            self._error_count += 1
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and performance metrics."""
        try:
            avg_processing_time = (
                self._total_processing_time / self._interaction_count 
                if self._interaction_count > 0 else 0
            )
            
            error_rate = (
                self._error_count / self._interaction_count 
                if self._interaction_count > 0 else 0
            )
            
            return {
                "status": "operational",
                "active_sessions": len(self._active_sessions),
                "total_interactions": self._interaction_count,
                "average_processing_time": avg_processing_time,
                "error_rate": error_rate,
                "components": {
                    "voice_processing": "operational",
                    "language_processing": "operational",
                    "scheme_discovery": "operational",
                    "grievance_filing": "operational",
                    "government_integration": "operational",
                    "privacy_manager": "operational",
                    "accessibility": "operational"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get system status: {e}")
            return {"status": "error", "error": str(e)}
    
    # Helper methods for formatting responses
    def _format_scheme_response(self, eligible_schemes: List[Dict], language: str) -> str:
        """Format scheme discovery response."""
        if language == "hindi":
            response = "आपके लिए ये योजनाएं उपलब्ध हैं:\n\n"
            for i, item in enumerate(eligible_schemes[:3], 1):
                scheme = item["scheme"]
                response += f"{i}. {scheme.name}\n   - {scheme.description[:100]}...\n"
        else:
            response = "These schemes are available for you:\n\n"
            for i, item in enumerate(eligible_schemes[:3], 1):
                scheme = item["scheme"]
                response += f"{i}. {scheme.name}\n   - {scheme.description[:100]}...\n"
        
        return response
    
    def _format_status_response(self, status_result, language: str) -> str:
        """Format status tracking response."""
        if language == "hindi":
            return f"आपकी शिकायत की स्थिति: {status_result.status}\nअपडेट: {status_result.last_update}"
        else:
            return f"Your complaint status: {status_result.status}\nLast update: {status_result.last_update}"
    
    def _extract_user_requirements(self, entities: Dict[str, Any], session: UserSession) -> Dict[str, Any]:
        """Extract user requirements from entities and session context."""
        requirements = {
            "age": session.user_profile.get("age"),
            "location": session.user_profile.get("location"),
            "occupation": entities.get("occupation"),
            "income": entities.get("income"),
            "category": entities.get("category"),
            "needs": entities.get("needs", [])
        }
        
        return {k: v for k, v in requirements.items() if v is not None}
    
    def _create_assistance_context(self, session: UserSession):
        """Create assistance context from session."""
        from ..accessibility.user_assistance import AssistanceContext
        
        return AssistanceContext(
            current_task=session.current_task,
            user_experience_level="beginner",  # Could be determined from session history
            language_preference=session.user_profile.get("preferred_language", "hindi"),
            education_level=session.user_profile.get("education_level", "basic")
        )
    
    def _get_communication_config(self, user_profile: Dict[str, Any]):
        """Get communication configuration from user profile."""
        from ..accessibility.simple_communication import CommunicationConfig, EducationLevel, CommunicationStyle
        
        education_level = EducationLevel.BASIC
        if user_profile.get("education_level") == "advanced":
            education_level = EducationLevel.ADVANCED
        elif user_profile.get("education_level") == "intermediate":
            education_level = EducationLevel.INTERMEDIATE
        
        return CommunicationConfig(
            education_level=education_level,
            preferred_language=user_profile.get("preferred_language", "hindi"),
            communication_style=CommunicationStyle.CONVERSATIONAL
        )