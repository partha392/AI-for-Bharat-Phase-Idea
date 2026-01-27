"""
Main language processing orchestrator.

This module provides the main LanguageProcessor class that orchestrates
intent classification, entity extraction, and context management for
multilingual natural language understanding in government service interactions.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import uuid

from .intent_classifier import IntentClassifier, IntentResult, ServiceIntent
from .entity_extractor import EntityExtractor, EntityExtractionResult, Entity
from .context_manager import ContextManager, ConversationContext, ConversationTurn, ConversationState
from .conversation_manager import ConversationManager
from ..core.exceptions import LanguageProcessingError
from ..core.config import config

logger = logging.getLogger(__name__)


@dataclass
class LanguageProcessingResult:
    """Complete result of language processing."""
    session_id: str
    turn_id: str
    intent: ServiceIntent
    entities: List[Entity]
    language: str
    confidence: float
    context_summary: Dict[str, Any]
    response_text: str
    next_state: ConversationState
    processing_time: float
    metadata: Dict[str, Any]


class LanguageProcessor:
    """
    Main language processing orchestrator.
    
    Coordinates intent classification, entity extraction, and context management
    to provide comprehensive natural language understanding for government
    service interactions across multiple Indian languages.
    """
    
    def __init__(self):
        """Initialize the language processor."""
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.context_manager = ContextManager()
        self.conversation_manager = ConversationManager(self.context_manager)
        
        # Response templates by language and intent
        self._response_templates = self._load_response_templates()
        
        logger.info("LanguageProcessor initialized with multilingual support and conversation management")
    
    def process_input(self, text: str, session_id: str, 
                     language: Optional[str] = None,
                     user_id: Optional[str] = None) -> LanguageProcessingResult:
        """
        Process user input through the complete NLU pipeline with enhanced conversation management.
        
        Args:
            text: User input text
            session_id: Session identifier
            language: Optional language code (auto-detected if not provided)
            user_id: Optional user identifier
            
        Returns:
            LanguageProcessingResult with complete processing results
            
        Raises:
            LanguageProcessingError: If processing fails
        """
        start_time = datetime.now()
        turn_id = str(uuid.uuid4())
        
        try:
            # Get or create conversation context
            context = self.context_manager.get_context(session_id)
            if not context:
                detected_language = language or self._detect_language_simple(text)
                context = self.context_manager.create_context(
                    session_id=session_id,
                    user_id=user_id,
                    language=detected_language
                )
            
            # Classify intent
            intent_result = self.intent_classifier.classify_intent(text, context.language)
            
            # Extract entities
            entity_result = self.entity_extractor.extract_entities(text, context.language)
            
            # Use enhanced conversation management
            conversation_result = self.conversation_manager.manage_conversation_turn(
                session_id=session_id,
                user_input=text,
                intent=intent_result.intent,
                entities=entity_result.entities,
                language=context.language,
                confidence=intent_result.confidence
            )
            
            # Get updated context
            updated_context = self.context_manager.get_context(session_id)
            context_summary = self.context_manager.get_context_summary(session_id)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = LanguageProcessingResult(
                session_id=session_id,
                turn_id=turn_id,
                intent=intent_result.intent,
                entities=entity_result.entities,
                language=context.language,
                confidence=intent_result.confidence,
                context_summary=context_summary,
                response_text=conversation_result['response'],
                next_state=ConversationState(conversation_result['state']),
                processing_time=processing_time,
                metadata={
                    'intent_confidence': intent_result.confidence,
                    'entity_count': len(entity_result.entities),
                    'turn_count': len(updated_context.turns) if updated_context else 0,
                    'context_age': context_summary.get("time_since_update", 0),
                    'cultural_context': conversation_result.get('cultural_context'),
                    'error_recovery': conversation_result.get('error_recovery', False),
                    'requires_followup': conversation_result.get('requires_followup', False),
                    'completion_status': conversation_result.get('completion_status', 'in_progress')
                }
            )
            
            logger.info("Processed input for session %s: intent=%s, entities=%d, confidence=%.2f, cultural_context=%s",
                       session_id, intent_result.intent.value, len(entity_result.entities), 
                       intent_result.confidence, conversation_result.get('cultural_context'))
            
            return result
            
        except Exception as e:
            logger.error("Language processing failed for session %s: %s", session_id, str(e))
            raise LanguageProcessingError(f"Failed to process input: {str(e)}")
    
    def get_conversation_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Get conversation context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ConversationContext if found, None otherwise
        """
        return self.context_manager.get_context(session_id)
    
    def end_conversation(self, session_id: str) -> bool:
        """
        End a conversation session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        return self.context_manager.end_conversation(session_id)
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get list of supported languages.
        
        Returns:
            Dictionary mapping language codes to language names
        """
        return self.intent_classifier.SUPPORTED_LANGUAGES.copy()
    
    def _detect_language_simple(self, text: str) -> str:
        """Simple language detection fallback."""
        # Use the intent classifier's language detection
        return self.intent_classifier._detect_language(text)
    
    def _determine_next_state(self, intent: ServiceIntent, 
                            current_state: ConversationState,
                            entities: List[Entity]) -> ConversationState:
        """
        Determine the next conversation state based on intent and context.
        
        Args:
            intent: Classified intent
            current_state: Current conversation state
            entities: Extracted entities
            
        Returns:
            Next conversation state
        """
        # State transition logic based on intent
        if intent == ServiceIntent.SCHEME_DISCOVERY:
            return ConversationState.SCHEME_DISCOVERY
        elif intent == ServiceIntent.GRIEVANCE_FILING:
            return ConversationState.GRIEVANCE_FILING
        elif intent == ServiceIntent.STATUS_TRACKING:
            return ConversationState.STATUS_TRACKING
        elif intent == ServiceIntent.DOCUMENT_HELP:
            return ConversationState.DOCUMENT_COLLECTION
        elif intent in [ServiceIntent.ELIGIBILITY_CHECK, ServiceIntent.APPLICATION_HELP]:
            return ConversationState.SCHEME_DISCOVERY
        elif intent == ServiceIntent.GENERAL_INQUIRY:
            # Stay in current state or go to initial if no current state
            return current_state if current_state != ConversationState.INITIAL else ConversationState.INITIAL
        else:
            # Unknown intent - stay in current state or go to initial
            return current_state if current_state != ConversationState.INITIAL else ConversationState.INITIAL
    
    def _generate_response(self, intent_result: IntentResult, 
                         entities: List[Entity],
                         context: ConversationContext,
                         next_state: ConversationState) -> str:
        """
        Generate appropriate response based on intent, entities, and context.
        
        Args:
            intent_result: Intent classification result
            entities: Extracted entities
            context: Conversation context
            next_state: Next conversation state
            
        Returns:
            Generated response text
        """
        language = context.language
        intent = intent_result.intent
        
        # Get response templates for the language
        templates = self._response_templates.get(language, self._response_templates['hi'])
        intent_templates = templates.get(intent.value, templates.get('default', []))
        
        if not intent_templates:
            # Fallback response
            return self._get_fallback_response(language, intent)
        
        # Select appropriate template based on context and entities
        template = self._select_response_template(intent_templates, entities, context, next_state)
        
        # Fill template with entity values
        response = self._fill_response_template(template, entities, context)
        
        return response
    
    def _select_response_template(self, templates: List[Dict[str, Any]], 
                                entities: List[Entity],
                                context: ConversationContext,
                                next_state: ConversationState) -> Dict[str, Any]:
        """Select the most appropriate response template."""
        if not templates:
            return {"text": "मैं आपकी सहायता करने के लिए यहाँ हूँ।", "requires": []}
        
        # Simple selection - could be enhanced with more sophisticated logic
        for template in templates:
            required_entities = template.get("requires", [])
            if not required_entities:
                return template
            
            # Check if required entities are present
            entity_types = [entity.type.value for entity in entities]
            if all(req in entity_types for req in required_entities):
                return template
        
        # Return first template if no specific match
        return templates[0]
    
    def _fill_response_template(self, template: Dict[str, Any], 
                              entities: List[Entity],
                              context: ConversationContext) -> str:
        """Fill response template with actual values."""
        response_text = template.get("text", "")
        
        # Create entity value map
        entity_values = {}
        for entity in entities:
            entity_values[entity.type.value] = entity.normalized_value or entity.value
        
        # Add context values
        entity_values["user_name"] = context.persistent_data.get("user_name", "")
        entity_values["turn_count"] = str(len(context.turns))
        
        # Simple template filling (could be enhanced with proper templating engine)
        try:
            return response_text.format(**entity_values)
        except KeyError:
            # If template filling fails, return template as-is
            return response_text
    
    def _get_fallback_response(self, language: str, intent: ServiceIntent) -> str:
        """Get fallback response when no template is available."""
        fallback_responses = {
            'hi': {
                ServiceIntent.SCHEME_DISCOVERY: "मैं आपके लिए उपयुक्त सरकारी योजनाएं खोजने में मदद कर सकता हूं।",
                ServiceIntent.GRIEVANCE_FILING: "मैं आपकी शिकायत दर्ज करने में सहायता करूंगा।",
                ServiceIntent.STATUS_TRACKING: "मैं आपके आवेदन की स्थिति की जांच करने में मदद करूंगा।",
                ServiceIntent.DOCUMENT_HELP: "मैं आवश्यक दस्तावेजों के बारे में जानकारी दे सकता हूं।",
                ServiceIntent.ELIGIBILITY_CHECK: "मैं आपकी पात्रता की जांच करने में मदद करूंगा।",
                ServiceIntent.APPLICATION_HELP: "मैं आवेदन प्रक्रिया में आपकी सहायता करूंगा।",
                ServiceIntent.GENERAL_INQUIRY: "मैं सरकारी सेवाओं के बारे में आपके प्रश्नों का उत्तर दे सकता हूं।",
                ServiceIntent.UNKNOWN: "मुझे खुशी होगी यदि आप अपनी आवश्यकता को और स्पष्ट रूप से बता सकें।"
            },
            'en': {
                ServiceIntent.SCHEME_DISCOVERY: "I can help you find suitable government schemes.",
                ServiceIntent.GRIEVANCE_FILING: "I will assist you in filing your complaint.",
                ServiceIntent.STATUS_TRACKING: "I can help you check the status of your application.",
                ServiceIntent.DOCUMENT_HELP: "I can provide information about required documents.",
                ServiceIntent.ELIGIBILITY_CHECK: "I will help you check your eligibility.",
                ServiceIntent.APPLICATION_HELP: "I will assist you with the application process.",
                ServiceIntent.GENERAL_INQUIRY: "I can answer your questions about government services.",
                ServiceIntent.UNKNOWN: "I would be happy to help if you could clarify your requirement."
            }
        }
        
        lang_responses = fallback_responses.get(language, fallback_responses['hi'])
        return lang_responses.get(intent, lang_responses[ServiceIntent.UNKNOWN])
    
    def _extract_persistent_data(self, entities: List[Entity]) -> Dict[str, Any]:
        """Extract data that should persist across conversation turns."""
        persistent_data = {}
        
        for entity in entities:
            if entity.type.value in ['person_name', 'phone_number', 'email', 'reference_number']:
                persistent_data[entity.type.value] = entity.normalized_value or entity.value
        
        return persistent_data
    
    def _extract_temporary_data(self, intent_result: IntentResult, 
                              entities: List[Entity]) -> Dict[str, Any]:
        """Extract temporary data for current context."""
        temporary_data = {
            "last_intent": intent_result.intent.value,
            "last_confidence": intent_result.confidence,
            "last_entities": [entity.type.value for entity in entities]
        }
        
        # Add specific temporary data based on intent
        if intent_result.intent == ServiceIntent.STATUS_TRACKING:
            ref_entities = [e for e in entities if e.type.value == 'reference_number']
            if ref_entities:
                temporary_data["tracking_reference"] = ref_entities[0].normalized_value
        
        return temporary_data
    
    def _load_response_templates(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Load response templates for different languages and intents."""
        return {
            'hi': {
                'scheme_discovery': [
                    {
                        "text": "मैं आपके लिए उपयुक्त सरकारी योजनाएं खोज रहा हूं। कृपया अपनी आवश्यकता बताएं।",
                        "requires": []
                    },
                    {
                        "text": "आपकी आवश्यकता के अनुसार, मैं {government_service} से संबंधित योजनाएं खोज सकता हूं।",
                        "requires": ["government_service"]
                    }
                ],
                'grievance_filing': [
                    {
                        "text": "मैं आपकी शिकायत दर्ज करने में सहायता करूंगा। कृपया अपनी समस्या विस्तार से बताएं।",
                        "requires": []
                    }
                ],
                'status_tracking': [
                    {
                        "text": "कृपया अपना संदर्भ नंबर बताएं ताकि मैं आपके आवेदन की स्थिति की जांच कर सकूं।",
                        "requires": []
                    },
                    {
                        "text": "मैं संदर्भ नंबर {reference_number} की स्थिति की जांच कर रहा हूं।",
                        "requires": ["reference_number"]
                    }
                ],
                'document_help': [
                    {
                        "text": "मैं आवश्यक दस्तावेजों की जानकारी दे सकता हूं। आप किस सेवा के लिए दस्तावेज चाहते हैं?",
                        "requires": []
                    }
                ],
                'eligibility_check': [
                    {
                        "text": "मैं आपकी पात्रता की जांच करने में मदद करूंगा। कृपया अपनी जानकारी साझा करें।",
                        "requires": []
                    }
                ],
                'application_help': [
                    {
                        "text": "मैं आवेदन प्रक्रिया में आपकी सहायता करूंगा। आप किस योजना के लिए आवेदन करना चाहते हैं?",
                        "requires": []
                    }
                ],
                'general_inquiry': [
                    {
                        "text": "मैं सरकारी सेवाओं के बारे में आपके प्रश्नों का उत्तर दे सकता हूं। आप क्या जानना चाहते हैं?",
                        "requires": []
                    }
                ],
                'default': [
                    {
                        "text": "मैं आपकी सहायता करने के लिए यहाँ हूँ। कृपया बताएं कि आप क्या चाहते हैं।",
                        "requires": []
                    }
                ]
            },
            'en': {
                'scheme_discovery': [
                    {
                        "text": "I'm searching for suitable government schemes for you. Please tell me your requirements.",
                        "requires": []
                    },
                    {
                        "text": "Based on your needs, I can find schemes related to {government_service}.",
                        "requires": ["government_service"]
                    }
                ],
                'grievance_filing': [
                    {
                        "text": "I will help you file your complaint. Please describe your problem in detail.",
                        "requires": []
                    }
                ],
                'status_tracking': [
                    {
                        "text": "Please provide your reference number so I can check your application status.",
                        "requires": []
                    },
                    {
                        "text": "I'm checking the status of reference number {reference_number}.",
                        "requires": ["reference_number"]
                    }
                ],
                'document_help': [
                    {
                        "text": "I can provide information about required documents. Which service do you need documents for?",
                        "requires": []
                    }
                ],
                'eligibility_check': [
                    {
                        "text": "I will help you check your eligibility. Please share your information.",
                        "requires": []
                    }
                ],
                'application_help': [
                    {
                        "text": "I will assist you with the application process. Which scheme do you want to apply for?",
                        "requires": []
                    }
                ],
                'general_inquiry': [
                    {
                        "text": "I can answer your questions about government services. What would you like to know?",
                        "requires": []
                    }
                ],
                'default': [
                    {
                        "text": "I'm here to help you. Please tell me what you need.",
                        "requires": []
                    }
                ]
            }
        }