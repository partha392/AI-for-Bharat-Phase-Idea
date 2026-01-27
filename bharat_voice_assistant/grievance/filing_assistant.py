"""
Conversational grievance filing assistant.

This module provides the main interface for conversational grievance filing,
integrating workflow management, validation, and voice guidance.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .models import GrievanceRecord, WorkflowStep, WorkflowState
from .workflow_manager import GrievanceWorkflowManager
from .validator import GrievanceValidator
from ..language.intent_classifier import ServiceIntent, IntentClassifier
from ..language.entity_extractor import EntityExtractor, Entity
from ..language.conversation_manager import ConversationManager, CulturalContext
from ..core.exceptions import GrievanceFilingError

logger = logging.getLogger(__name__)


class ConversationalFilingAssistant:
    """
    Main conversational assistant for grievance filing.
    
    Provides step-by-step guidance with voice instructions, conversational
    form filling with real-time validation, and information collection
    through prompts rather than forms.
    """
    
    def __init__(self, 
                 workflow_manager: Optional[GrievanceWorkflowManager] = None,
                 validator: Optional[GrievanceValidator] = None,
                 intent_classifier: Optional[IntentClassifier] = None,
                 entity_extractor: Optional[EntityExtractor] = None,
                 conversation_manager: Optional[ConversationManager] = None):
        """Initialize the conversational filing assistant."""
        self.workflow_manager = workflow_manager or GrievanceWorkflowManager()
        self.validator = validator or GrievanceValidator()
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.conversation_manager = conversation_manager or ConversationManager()
        
        # Active grievance sessions
        self._active_sessions: Dict[str, GrievanceRecord] = {}
        
        logger.info("ConversationalFilingAssistant initialized")
    
    def start_grievance_filing(self, session_id: str, language: str = 'hi') -> Dict[str, Any]:
        """
        Start a new grievance filing session.
        
        Args:
            session_id: Session identifier
            language: User's preferred language
            
        Returns:
            Dictionary with initial response and session information
        """
        try:
            # Start workflow
            grievance, workflow_response = self.workflow_manager.start_workflow(session_id, language)
            
            # Store in active sessions
            self._active_sessions[session_id] = grievance
            
            # Generate culturally adapted response
            cultural_response = self._adapt_response_culturally(
                workflow_response, language, CulturalContext.EMPATHETIC
            )
            
            logger.info("Started grievance filing session %s in language %s", session_id, language)
            
            return {
                'session_id': session_id,
                'language': language,
                'response': cultural_response,
                'workflow_status': self.workflow_manager.get_workflow_status(grievance),
                'voice_instructions': self._generate_voice_instructions(grievance, workflow_response),
                'started': True
            }
            
        except Exception as e:
            logger.error("Failed to start grievance filing for session %s: %s", session_id, str(e))
            raise GrievanceFilingError(f"Failed to start grievance filing: {str(e)}")
    
    def process_user_input(self, session_id: str, user_input: str, 
                          confidence: Optional[float] = None) -> Dict[str, Any]:
        """
        Process user input in the grievance filing conversation.
        
        Args:
            session_id: Session identifier
            user_input: User's voice/text input
            confidence: Optional confidence score from speech recognition
            
        Returns:
            Dictionary with response and updated session information
        """
        try:
            # Get active grievance session
            grievance = self._active_sessions.get(session_id)
            if not grievance:
                return self._handle_session_not_found(session_id)
            
            # Classify intent
            intent_result = self.intent_classifier.classify_intent(user_input, grievance.language)
            
            # Extract entities
            entity_result = self.entity_extractor.extract_entities(user_input, grievance.language)
            
            # Handle low confidence speech recognition
            if confidence is not None and confidence < 0.7:
                return self._handle_low_confidence_input(grievance, user_input, confidence)
            
            # Process with workflow manager
            updated_grievance, workflow_response = self.workflow_manager.process_user_input(
                grievance, user_input, intent_result.intent, entity_result.entities
            )
            
            # Update active session
            self._active_sessions[session_id] = updated_grievance
            
            # Generate conversational response
            conversational_response = self._generate_conversational_response(
                updated_grievance, workflow_response, intent_result, entity_result
            )
            
            # Perform real-time validation if needed
            validation_feedback = self._provide_real_time_validation(
                updated_grievance, workflow_response
            )
            
            logger.info("Processed input for session %s, step: %s", 
                       session_id, updated_grievance.workflow_progress.current_step.value)
            
            return {
                'session_id': session_id,
                'response': conversational_response,
                'workflow_status': self.workflow_manager.get_workflow_status(updated_grievance),
                'voice_instructions': self._generate_voice_instructions(updated_grievance, workflow_response),
                'validation_feedback': validation_feedback,
                'entities_extracted': [entity.__dict__ for entity in entity_result.entities],
                'intent_detected': intent_result.intent.value,
                'confidence': intent_result.confidence
            }
            
        except Exception as e:
            logger.error("Failed to process input for session %s: %s", session_id, str(e))
            return self._handle_processing_error(session_id, str(e))
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current status of a grievance filing session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session status information
        """
        grievance = self._active_sessions.get(session_id)
        if not grievance:
            return {'error': 'Session not found', 'session_id': session_id}
        
        workflow_status = self.workflow_manager.get_workflow_status(grievance)
        validation_result = self.validator.validate_grievance(grievance)
        
        return {
            'session_id': session_id,
            'language': grievance.language,
            'workflow_status': workflow_status,
            'validation_status': {
                'is_valid': validation_result.is_valid,
                'completion_percentage': validation_result.completion_percentage,
                'missing_fields': validation_result.missing_required_fields,
                'errors_count': len(validation_result.errors),
                'warnings_count': len(validation_result.warnings)
            },
            'grievance_summary': self._generate_grievance_summary(grievance),
            'created_at': grievance.created_at.isoformat(),
            'last_updated': grievance.updated_at.isoformat()
        }
    
    def provide_help(self, session_id: str, help_topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Provide contextual help during grievance filing.
        
        Args:
            session_id: Session identifier
            help_topic: Optional specific help topic
            
        Returns:
            Dictionary with help information
        """
        grievance = self._active_sessions.get(session_id)
        if not grievance:
            return self._handle_session_not_found(session_id)
        
        current_step = grievance.workflow_progress.current_step
        language = grievance.language
        
        help_content = self._get_contextual_help(current_step, language, help_topic)
        
        return {
            'session_id': session_id,
            'help_content': help_content,
            'current_step': current_step.value,
            'voice_instructions': help_content.get('voice_instructions', ''),
            'examples': help_content.get('examples', []),
            'tips': help_content.get('tips', [])
        }
    
    def restart_session(self, session_id: str) -> Dict[str, Any]:
        """
        Restart a grievance filing session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with restart confirmation
        """
        grievance = self._active_sessions.get(session_id)
        if not grievance:
            return self._handle_session_not_found(session_id)
        
        # Restart workflow
        language = grievance.language
        return self.start_grievance_filing(session_id, language)
    
    def end_session(self, session_id: str, save_draft: bool = True) -> Dict[str, Any]:
        """
        End a grievance filing session.
        
        Args:
            session_id: Session identifier
            save_draft: Whether to save as draft
            
        Returns:
            Dictionary with session end confirmation
        """
        grievance = self._active_sessions.get(session_id)
        if not grievance:
            return self._handle_session_not_found(session_id)
        
        # Remove from active sessions
        del self._active_sessions[session_id]
        
        language = grievance.language
        
        if language == 'hi':
            message = "आपका सत्र समाप्त हो गया है। धन्यवाद!"
            if save_draft:
                message += " आपका ड्राफ्ट सुरक्षित कर दिया गया है।"
        else:
            message = "Your session has ended. Thank you!"
            if save_draft:
                message += " Your draft has been saved."
        
        return {
            'session_id': session_id,
            'message': message,
            'ended': True,
            'draft_saved': save_draft,
            'completion_percentage': self.validator.validate_grievance(grievance).completion_percentage
        }
    
    def _adapt_response_culturally(self, workflow_response: Dict[str, Any], 
                                 language: str, cultural_context: CulturalContext) -> Dict[str, Any]:
        """Adapt workflow response for cultural context."""
        adapted_response = workflow_response.copy()
        
        # Add cultural elements based on language and context
        if language == 'hi':
            if cultural_context == CulturalContext.EMPATHETIC:
                # Add empathetic elements for Hindi
                message = adapted_response.get('message', '')
                if 'समस्या' in message:
                    adapted_response['cultural_prefix'] = 'मैं समझ सकता हूं कि आपको परेशानी हो रही है।'
                
                # Add respectful addressing
                adapted_response['honorific'] = 'जी'
        
        elif language == 'en':
            if cultural_context == CulturalContext.EMPATHETIC:
                message = adapted_response.get('message', '')
                if 'problem' in message.lower():
                    adapted_response['cultural_prefix'] = 'I understand this must be concerning for you.'
        
        return adapted_response
    
    def _generate_voice_instructions(self, grievance: GrievanceRecord, 
                                   workflow_response: Dict[str, Any]) -> Dict[str, Any]:
        """Generate voice-specific instructions for the current step."""
        current_step = grievance.workflow_progress.current_step
        language = grievance.language
        
        voice_instructions = {
            'hi': {
                WorkflowStep.PROBLEM_DESCRIPTION: {
                    'instruction': 'कृपया अपनी समस्या को स्पष्ट रूप से बोलें। आप धीरे-धीरे बोल सकते हैं।',
                    'tips': [
                        'समस्या का विस्तार से वर्णन करें',
                        'कब और कहाँ यह समस्या हुई, बताएं',
                        'यदि आवश्यक हो तो रुकें और सोचें'
                    ]
                },
                WorkflowStep.CONTACT_COLLECTION: {
                    'instruction': 'कृपया अपना फोन नंबर या ईमेल पता स्पष्ट रूप से बोलें।',
                    'tips': [
                        'नंबर को धीरे-धीरे बोलें',
                        'यदि गलती हो तो "दोबारा" कहें',
                        'ईमेल पता अक्षर-अक्षर बोल सकते हैं'
                    ]
                },
                WorkflowStep.CONFIRMATION: {
                    'instruction': 'कृपया "हाँ" या "नहीं" में उत्तर दें।',
                    'tips': [
                        '"हाँ" कहें यदि जानकारी सही है',
                        '"नहीं" कहें यदि कुछ बदलना है',
                        'आप "सबमिट करें" भी कह सकते हैं'
                    ]
                }
            },
            'en': {
                WorkflowStep.PROBLEM_DESCRIPTION: {
                    'instruction': 'Please describe your problem clearly. You can speak slowly.',
                    'tips': [
                        'Describe the problem in detail',
                        'Mention when and where it happened',
                        'Take your time to think if needed'
                    ]
                },
                WorkflowStep.CONTACT_COLLECTION: {
                    'instruction': 'Please speak your phone number or email address clearly.',
                    'tips': [
                        'Speak numbers slowly',
                        'Say "repeat" if you make a mistake',
                        'You can spell out email addresses'
                    ]
                },
                WorkflowStep.CONFIRMATION: {
                    'instruction': 'Please answer with "yes" or "no".',
                    'tips': [
                        'Say "yes" if information is correct',
                        'Say "no" if something needs to be changed',
                        'You can also say "submit"'
                    ]
                }
            }
        }
        
        lang_instructions = voice_instructions.get(language, voice_instructions['hi'])
        step_instructions = lang_instructions.get(current_step, {})
        
        return {
            'instruction': step_instructions.get('instruction', ''),
            'tips': step_instructions.get('tips', []),
            'current_step': current_step.value,
            'speech_guidance': {
                'speak_slowly': True,
                'pause_allowed': True,
                'repeat_allowed': True
            }
        }
    
    def _generate_conversational_response(self, grievance: GrievanceRecord,
                                        workflow_response: Dict[str, Any],
                                        intent_result: Any, entity_result: Any) -> Dict[str, Any]:
        """Generate natural conversational response."""
        base_response = workflow_response.copy()
        
        # Add conversational elements
        if workflow_response.get('collected_data'):
            collected_data = workflow_response['collected_data']
            acknowledgment = self._generate_acknowledgment(collected_data, grievance.language)
            base_response['acknowledgment'] = acknowledgment
        
        # Add encouragement for progress
        workflow_status = self.workflow_manager.get_workflow_status(grievance)
        if workflow_status['completion_percentage'] > 50:
            encouragement = self._generate_encouragement(grievance.language, workflow_status)
            base_response['encouragement'] = encouragement
        
        # Add next step preview
        if not workflow_response.get('completed'):
            next_step_preview = self._generate_next_step_preview(grievance)
            base_response['next_step_preview'] = next_step_preview
        
        return base_response
    
    def _provide_real_time_validation(self, grievance: GrievanceRecord,
                                    workflow_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide real-time validation feedback."""
        if workflow_response.get('errors'):
            errors = workflow_response['errors']
            return {
                'has_errors': True,
                'error_count': len(errors),
                'friendly_messages': [self._make_error_friendly(error, grievance.language) for error in errors],
                'suggestions': [error.suggestion for error in errors if error.suggestion]
            }
        
        # Validate current step data
        validation_result = self.validator.validate_grievance(grievance)
        if validation_result.warnings:
            return {
                'has_warnings': True,
                'warning_count': len(validation_result.warnings),
                'friendly_messages': [self._make_error_friendly(warning, grievance.language) 
                                    for warning in validation_result.warnings]
            }
        
        return None
    
    def _generate_acknowledgment(self, collected_data: Dict[str, Any], language: str) -> str:
        """Generate acknowledgment for collected data."""
        if not collected_data:
            return ""
        
        if language == 'hi':
            if 'problem_description' in collected_data:
                return "धन्यवाद, मैंने आपकी समस्या को समझ लिया है।"
            elif 'phone_number' in collected_data:
                return "बहुत अच्छा, आपका फोन नंबर मिल गया।"
            elif 'email' in collected_data:
                return "धन्यवाद, आपका ईमेल पता नोट कर लिया।"
            else:
                return "धन्यवाद, जानकारी मिल गई।"
        else:
            if 'problem_description' in collected_data:
                return "Thank you, I understand your problem."
            elif 'phone_number' in collected_data:
                return "Great, I have your phone number."
            elif 'email' in collected_data:
                return "Thank you, I have noted your email address."
            else:
                return "Thank you, information received."
    
    def _generate_encouragement(self, language: str, workflow_status: Dict[str, Any]) -> str:
        """Generate encouragement based on progress."""
        completion = workflow_status['completion_percentage']
        
        if language == 'hi':
            if completion > 80:
                return "बहुत अच्छा! आप लगभग पूरा कर चुके हैं।"
            elif completion > 50:
                return "अच्छा चल रहा है! आधे से ज्यादा काम हो गया।"
            else:
                return "बहुत अच्छे! आगे बढ़ते रहें।"
        else:
            if completion > 80:
                return "Excellent! You're almost done."
            elif completion > 50:
                return "Good progress! More than halfway there."
            else:
                return "Great! Keep going."
    
    def _generate_next_step_preview(self, grievance: GrievanceRecord) -> str:
        """Generate preview of next step."""
        current_step = grievance.workflow_progress.current_step
        language = grievance.language
        
        next_steps = {
            'hi': {
                WorkflowStep.PROBLEM_DESCRIPTION: "अगला: समस्या का प्रकार चुनना",
                WorkflowStep.CATEGORY_SELECTION: "अगला: संपर्क जानकारी",
                WorkflowStep.CONTACT_COLLECTION: "अगला: दस्तावेज़ की जानकारी",
                WorkflowStep.DOCUMENT_COLLECTION: "अगला: जानकारी की जांच",
                WorkflowStep.VALIDATION: "अगला: पुष्टि करना",
                WorkflowStep.CONFIRMATION: "अगला: शिकायत सबमिट करना"
            },
            'en': {
                WorkflowStep.PROBLEM_DESCRIPTION: "Next: Select problem category",
                WorkflowStep.CATEGORY_SELECTION: "Next: Contact information",
                WorkflowStep.CONTACT_COLLECTION: "Next: Document information",
                WorkflowStep.DOCUMENT_COLLECTION: "Next: Information validation",
                WorkflowStep.VALIDATION: "Next: Confirmation",
                WorkflowStep.CONFIRMATION: "Next: Submit grievance"
            }
        }
        
        lang_steps = next_steps.get(language, next_steps['hi'])
        return lang_steps.get(current_step, "")
    
    def _make_error_friendly(self, error: Any, language: str) -> str:
        """Make error messages more user-friendly."""
        if hasattr(error, 'message'):
            error_message = error.message
        else:
            error_message = str(error)
        
        # Make common errors more friendly
        friendly_mappings = {
            'hi': {
                'Invalid phone number format': 'फोन नंबर सही तरीके से नहीं लिखा गया। कृपया 10 अंकों का नंबर दें।',
                'Invalid email address format': 'ईमेल पता सही नहीं है। कृपया सही ईमेल पता दें।',
                'Problem description is too short': 'समस्या का विवरण बहुत छोटा है। कृपया विस्तार से बताएं।'
            },
            'en': {
                'Invalid phone number format': 'The phone number format is incorrect. Please provide a 10-digit number.',
                'Invalid email address format': 'The email address is not valid. Please provide a correct email.',
                'Problem description is too short': 'The problem description is too brief. Please provide more details.'
            }
        }
        
        lang_mappings = friendly_mappings.get(language, friendly_mappings['hi'])
        return lang_mappings.get(error_message, error_message)
    
    def _generate_grievance_summary(self, grievance: GrievanceRecord) -> Dict[str, Any]:
        """Generate a summary of the current grievance."""
        summary = {
            'has_problem_description': bool(grievance.details and grievance.details.problem_description),
            'has_contact_info': bool(grievance.contact_info),
            'has_documents': len(grievance.documents) > 0,
            'grievance_type': grievance.details.grievance_type.value if grievance.details else None,
            'priority': grievance.priority.value,
            'status': grievance.status.value
        }
        
        if grievance.details:
            summary['problem_length'] = len(grievance.details.problem_description) if grievance.details.problem_description else 0
            summary['has_location'] = bool(grievance.details.location)
        
        if grievance.contact_info:
            summary['has_phone'] = bool(grievance.contact_info.phone_number)
            summary['has_email'] = bool(grievance.contact_info.email)
            summary['has_address'] = bool(grievance.contact_info.address)
        
        return summary
    
    def _get_contextual_help(self, step: WorkflowStep, language: str, 
                           help_topic: Optional[str] = None) -> Dict[str, Any]:
        """Get contextual help for current step."""
        help_content = {
            'hi': {
                WorkflowStep.PROBLEM_DESCRIPTION: {
                    'title': 'समस्या का विवरण',
                    'description': 'अपनी समस्या को विस्तार से बताएं। जितनी अधिक जानकारी देंगे, उतनी बेहतर सहायता मिलेगी।',
                    'examples': [
                        'मेरा पेंशन 3 महीने से नहीं आया है',
                        'राशन कार्ड में गलत नाम लिखा है',
                        'जन्म प्रमाणपत्र के लिए आवेदन दिया था लेकिन अभी तक नहीं मिला'
                    ],
                    'tips': [
                        'समस्या कब शुरू हुई, बताएं',
                        'कहाँ की समस्या है, स्थान बताएं',
                        'पहले क्या कोशिश की है, बताएं'
                    ]
                },
                WorkflowStep.CONTACT_COLLECTION: {
                    'title': 'संपर्क जानकारी',
                    'description': 'आपसे संपर्क करने के लिए फोन नंबर या ईमेल पता चाहिए।',
                    'examples': [
                        '9876543210',
                        'user@example.com',
                        'दोनों फोन और ईमेल दे सकते हैं'
                    ],
                    'tips': [
                        'कम से कम एक संपर्क तरीका जरूरी है',
                        'फोन नंबर 10 अंकों का होना चाहिए',
                        'ईमेल पता सही तरीके से लिखें'
                    ]
                }
            },
            'en': {
                WorkflowStep.PROBLEM_DESCRIPTION: {
                    'title': 'Problem Description',
                    'description': 'Describe your problem in detail. The more information you provide, the better assistance you can receive.',
                    'examples': [
                        'My pension has not been received for 3 months',
                        'Wrong name is written on ration card',
                        'Applied for birth certificate but not received yet'
                    ],
                    'tips': [
                        'Mention when the problem started',
                        'Specify the location of the problem',
                        'Describe what you have tried before'
                    ]
                },
                WorkflowStep.CONTACT_COLLECTION: {
                    'title': 'Contact Information',
                    'description': 'We need your phone number or email address to contact you.',
                    'examples': [
                        '9876543210',
                        'user@example.com',
                        'You can provide both phone and email'
                    ],
                    'tips': [
                        'At least one contact method is required',
                        'Phone number should be 10 digits',
                        'Email address should be in correct format'
                    ]
                }
            }
        }
        
        lang_help = help_content.get(language, help_content['hi'])
        step_help = lang_help.get(step, {})
        
        return {
            'title': step_help.get('title', ''),
            'description': step_help.get('description', ''),
            'examples': step_help.get('examples', []),
            'tips': step_help.get('tips', []),
            'voice_instructions': f"यह है {step_help.get('title', '')} का चरण। {step_help.get('description', '')}" if language == 'hi' else f"This is the {step_help.get('title', '')} step. {step_help.get('description', '')}"
        }
    
    def _handle_session_not_found(self, session_id: str) -> Dict[str, Any]:
        """Handle case when session is not found."""
        return {
            'error': 'Session not found',
            'session_id': session_id,
            'message': 'कृपया नया सत्र शुरू करें।' if session_id.endswith('_hi') else 'Please start a new session.',
            'restart_needed': True
        }
    
    def _handle_low_confidence_input(self, grievance: GrievanceRecord, 
                                   user_input: str, confidence: float) -> Dict[str, Any]:
        """Handle low confidence speech recognition."""
        language = grievance.language
        
        if language == 'hi':
            message = f"क्षमा करें, मैं आपकी बात पूरी तरह समझ नहीं पाया (विश्वसनीयता: {confidence:.1%})। कृपया दोबारा कहें।"
        else:
            message = f"Sorry, I didn't fully understand what you said (confidence: {confidence:.1%}). Please repeat."
        
        return {
            'session_id': grievance.session_id,
            'message': message,
            'low_confidence': True,
            'confidence': confidence,
            'retry_needed': True,
            'voice_instructions': {
                'instruction': 'कृपया धीरे-धीरे और स्पष्ट रूप से बोलें' if language == 'hi' else 'Please speak slowly and clearly',
                'tips': [
                    'धीरे बोलें' if language == 'hi' else 'Speak slowly',
                    'शोर से दूर रहें' if language == 'hi' else 'Avoid background noise',
                    'माइक के पास बोलें' if language == 'hi' else 'Speak close to microphone'
                ]
            }
        }
    
    def _handle_processing_error(self, session_id: str, error_message: str) -> Dict[str, Any]:
        """Handle processing errors."""
        return {
            'session_id': session_id,
            'error': 'Processing failed',
            'message': 'क्षमा करें, तकनीकी समस्या हुई है। कृपया बाद में पुनः प्रयास करें।',
            'error_details': error_message,
            'retry_later': True
        }