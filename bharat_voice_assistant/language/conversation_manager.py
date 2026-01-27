"""
Enhanced conversation management system for Bharat Voice Assistant.

This module provides advanced conversation management capabilities including
cultural adaptation, error recovery, and sophisticated flow management
for government service interactions across multiple Indian languages.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
import re

from .context_manager import ContextManager, ConversationContext, ConversationTurn, ConversationState
from .intent_classifier import ServiceIntent
from .entity_extractor import EntityType
from ..core.exceptions import ContextManagementError, LanguageProcessingError
from ..core.config import config

logger = logging.getLogger(__name__)


class CulturalContext(Enum):
    """Cultural context for response adaptation."""
    FORMAL = "formal"           # Government/official interactions
    RESPECTFUL = "respectful"   # Elder/authority interactions
    SUPPORTIVE = "supportive"   # Help/guidance interactions
    EMPATHETIC = "empathetic"   # Problem/grievance interactions
    ENCOURAGING = "encouraging" # Application/process interactions


class ErrorType(Enum):
    """Types of conversation errors that need recovery."""
    MISUNDERSTANDING = "misunderstanding"
    INCOMPLETE_INFO = "incomplete_info"
    TECHNICAL_ERROR = "technical_error"
    LANGUAGE_BARRIER = "language_barrier"
    CONTEXT_LOST = "context_lost"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"


@dataclass
class CulturalAdaptation:
    """Cultural adaptation settings for responses."""
    context: CulturalContext
    honorifics: Dict[str, str] = field(default_factory=dict)
    politeness_level: int = 3  # 1-5 scale
    formality_level: int = 3   # 1-5 scale
    regional_preferences: Dict[str, Any] = field(default_factory=dict)
    age_appropriate: bool = True
    gender_neutral: bool = True


@dataclass
class ErrorRecoveryStrategy:
    """Strategy for recovering from conversation errors."""
    error_type: ErrorType
    recovery_actions: List[str]
    fallback_responses: Dict[str, str]
    max_attempts: int = 3
    escalation_threshold: int = 2


@dataclass
class ConversationFlow:
    """Conversation flow definition."""
    current_step: str
    required_information: List[str]
    optional_information: List[str]
    next_possible_steps: List[str]
    completion_criteria: Dict[str, Any]
    validation_rules: Dict[str, Any]


class ConversationManager:
    """
    Enhanced conversation management system.
    
    Provides sophisticated conversation flow management, cultural adaptation,
    and error recovery for government service interactions.
    """
    
    def __init__(self, context_manager: Optional[ContextManager] = None):
        """Initialize the conversation manager."""
        self.context_manager = context_manager or ContextManager()
        
        # Cultural adaptation settings by language and region
        self._cultural_settings = self._load_cultural_settings()
        
        # Error recovery strategies
        self._error_strategies = self._load_error_recovery_strategies()
        
        # Conversation flow definitions
        self._conversation_flows = self._load_conversation_flows()
        
        # Response templates with cultural variations
        self._cultural_templates = self._load_cultural_templates()
        
        logger.info("ConversationManager initialized with cultural adaptation")
    
    def manage_conversation_turn(self, session_id: str, user_input: str,
                               intent: ServiceIntent, entities: List[Any],
                               language: str, confidence: float) -> Dict[str, Any]:
        """
        Manage a complete conversation turn with cultural adaptation and error recovery.
        
        Args:
            session_id: Session identifier
            user_input: User's input text
            intent: Classified intent
            entities: Extracted entities
            language: Conversation language
            confidence: Intent classification confidence
            
        Returns:
            Dictionary containing response and conversation state
        """
        try:
            # Get or create conversation context
            context = self.context_manager.get_context(session_id)
            if not context:
                context = self.context_manager.create_context(session_id, language=language)
            
            # Determine cultural context
            cultural_context = self._determine_cultural_context(intent, entities, context)
            
            # Check for errors and apply recovery if needed
            error_info = self._detect_conversation_errors(user_input, intent, confidence, context)
            if error_info:
                return self._handle_error_recovery(session_id, error_info, cultural_context, language)
            
            # Manage conversation flow
            flow_result = self._manage_conversation_flow(session_id, intent, entities, context)
            
            # Generate culturally adapted response
            response = self._generate_cultural_response(
                intent, entities, context, cultural_context, language, flow_result
            )
            
            # Update conversation state
            next_state = self._determine_next_state(intent, entities, context, flow_result)
            
            # Create conversation turn
            turn = ConversationTurn(
                turn_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                user_input=user_input,
                language=language,
                intent=intent.value,
                entities={entity.type.value if hasattr(entity, 'type') else str(entity): 
                         getattr(entity, 'value', str(entity)) for entity in entities},
                system_response=response,
                confidence=confidence,
                state=next_state,
                metadata={
                    'cultural_context': cultural_context.value,
                    'flow_step': flow_result.get('current_step'),
                    'error_recovery': False
                }
            )
            
            # Update context
            self.context_manager.update_context(
                session_id=session_id,
                turn=turn,
                new_state=next_state,
                persistent_data=self._extract_persistent_data(entities),
                temporary_data=self._extract_temporary_data(intent, entities, flow_result)
            )
            
            return {
                'response': response,
                'state': next_state.value,
                'cultural_context': cultural_context.value,
                'flow_info': flow_result,
                'requires_followup': flow_result.get('requires_followup', False),
                'completion_status': flow_result.get('completion_status', 'in_progress')
            }
            
        except Exception as e:
            logger.error("Conversation management failed for session %s: %s", session_id, str(e))
            return self._handle_critical_error(session_id, str(e), language)
    
    def _determine_cultural_context(self, intent: ServiceIntent, entities: List[Any],
                                  context: ConversationContext) -> CulturalContext:
        """Determine appropriate cultural context for the interaction."""
        # Check for age indicators for respectful tone
        age_entities = [e for e in entities if hasattr(e, 'type') and e.type == EntityType.AGE]
        if age_entities:
            try:
                # Extract numeric age from the value
                age_str = age_entities[0].value
                # Handle cases like "65 years", "65", etc.
                age_num = int(''.join(filter(str.isdigit, age_str)))
                if age_num >= 60:
                    return CulturalContext.RESPECTFUL
            except (ValueError, AttributeError):
                pass
        
        # Check persistent data for age
        user_age = context.persistent_data.get('age')
        if user_age:
            try:
                age_num = int(''.join(filter(str.isdigit, str(user_age))))
                if age_num >= 60:
                    return CulturalContext.RESPECTFUL
            except (ValueError, TypeError):
                pass
        
        # Determine context based on intent
        if intent == ServiceIntent.GRIEVANCE_FILING:
            return CulturalContext.EMPATHETIC
        elif intent in [ServiceIntent.SCHEME_DISCOVERY, ServiceIntent.APPLICATION_HELP]:
            return CulturalContext.ENCOURAGING
        elif intent == ServiceIntent.STATUS_TRACKING:
            return CulturalContext.SUPPORTIVE
        else:
            return CulturalContext.FORMAL
    
    def _detect_conversation_errors(self, user_input: str, intent: ServiceIntent,
                                  confidence: float, context: ConversationContext) -> Optional[Dict[str, Any]]:
        """Detect various types of conversation errors."""
        errors = []
        
        # Check for repeated unknown intents first (higher priority)
        recent_turns = context.turns[-3:] if len(context.turns) >= 3 else context.turns
        unknown_count = sum(1 for turn in recent_turns if turn.intent == ServiceIntent.UNKNOWN.value)
        if unknown_count >= 2:
            errors.append({
                'type': ErrorType.LANGUAGE_BARRIER,
                'severity': 'high',
                'details': f'Multiple unknown intents: {unknown_count}'
            })
        
        # Low confidence indicates misunderstanding
        elif confidence < 0.4:
            errors.append({
                'type': ErrorType.MISUNDERSTANDING,
                'severity': 'medium',
                'details': f'Low intent confidence: {confidence:.2f}'
            })
        
        # Check for context timeout
        if context.turns and (datetime.now() - context.last_updated).total_seconds() > 300:  # 5 minutes
            errors.append({
                'type': ErrorType.TIMEOUT,
                'severity': 'medium',
                'details': 'Long pause in conversation'
            })
        
        # Check for incomplete information patterns
        if self._is_incomplete_information(user_input, intent, context):
            errors.append({
                'type': ErrorType.INCOMPLETE_INFO,
                'severity': 'low',
                'details': 'Missing required information'
            })
        
        return errors[0] if errors else None  # Return most severe error
    
    def _is_incomplete_information(self, user_input: str, intent: ServiceIntent,
                                 context: ConversationContext) -> bool:
        """Check if the user input lacks required information."""
        # Check based on current conversation state and intent
        if intent == ServiceIntent.STATUS_TRACKING:
            # Should have reference number
            ref_pattern = r'[A-Z]{2,4}\d{4,8}'
            if not re.search(ref_pattern, user_input.upper()):
                return True
        
        if intent == ServiceIntent.GRIEVANCE_FILING:
            # Should have some description of the problem
            if len(user_input.strip()) < 10:
                return True
        
        return False
    
    def _handle_error_recovery(self, session_id: str, error_info: Dict[str, Any],
                             cultural_context: CulturalContext, language: str) -> Dict[str, Any]:
        """Handle error recovery with appropriate strategies."""
        error_type = error_info['type']
        strategy = self._error_strategies.get(error_type)
        
        if not strategy:
            return self._handle_critical_error(session_id, "Unknown error type", language)
        
        # Get or create context for error recovery
        context = self.context_manager.get_context(session_id)
        if not context:
            context = self.context_manager.create_context(session_id, language=language)
        
        # Get culturally appropriate error response
        response = self._get_error_recovery_response(error_type, cultural_context, language, error_info)
        
        # Create error recovery turn
        turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            user_input="[ERROR_RECOVERY]",
            language=language,
            intent="error_recovery",
            entities={},
            system_response=response,
            confidence=1.0,
            state=ConversationState.ERROR,
            metadata={
                'error_type': error_type.value,
                'error_details': error_info,
                'recovery_attempt': True
            }
        )
        
        # Update context
        self.context_manager.update_context(
            session_id=session_id,
            turn=turn,
            temporary_data={'error_recovery_active': True, 'error_type': error_type.value}
        )
        
        return {
            'response': response,
            'state': ConversationState.ERROR.value,
            'cultural_context': cultural_context.value,
            'error_recovery': True,
            'requires_followup': True,
            'completion_status': 'error_recovery'
        }
    
    def _manage_conversation_flow(self, session_id: str, intent: ServiceIntent,
                                entities: List[Any], context: ConversationContext) -> Dict[str, Any]:
        """Manage conversation flow based on intent and current state."""
        current_state = context.current_state
        flow_key = f"{current_state.value}_{intent.value}"
        
        # Get flow definition
        flow = self._conversation_flows.get(flow_key, self._conversation_flows.get('default'))
        
        # Extract required information
        required_info = self._check_required_information(entities, flow, context)
        
        # Determine next step
        next_step = self._determine_next_flow_step(intent, entities, required_info, flow)
        
        # Check completion criteria
        completion_status = self._check_completion_criteria(entities, context, flow)
        
        return {
            'current_step': next_step,
            'required_info': required_info,
            'missing_info': [info for info in flow.get('required_information', []) 
                           if info not in required_info],
            'completion_status': completion_status,
            'requires_followup': completion_status != 'completed',
            'flow_definition': flow
        }
    
    def _generate_cultural_response(self, intent: ServiceIntent, entities: List[Any],
                                  context: ConversationContext, cultural_context: CulturalContext,
                                  language: str, flow_result: Dict[str, Any]) -> str:
        """Generate culturally adapted response."""
        # Get cultural adaptation settings
        adaptation = self._get_cultural_adaptation(language, cultural_context, context)
        
        # Get base response template
        template_key = f"{intent.value}_{cultural_context.value}"
        templates = self._cultural_templates.get(language, {}).get(template_key, 
                   self._cultural_templates.get(language, {}).get(intent.value, []))
        
        if not templates:
            return self._get_fallback_response(intent, language, cultural_context)
        
        # Select appropriate template
        template = self._select_cultural_template(templates, entities, context, flow_result, adaptation)
        
        # Fill template with cultural adaptations
        response = self._fill_cultural_template(template, entities, context, adaptation, flow_result)
        
        return response
    
    def _get_cultural_adaptation(self, language: str, cultural_context: CulturalContext,
                               context: ConversationContext) -> CulturalAdaptation:
        """Get cultural adaptation settings for the current context."""
        settings = self._cultural_settings.get(language, {}).get(cultural_context.value, {})
        
        # Determine user characteristics for adaptation
        user_age = context.persistent_data.get('age')
        user_gender = context.persistent_data.get('gender')
        
        # Adjust politeness and formality based on context
        politeness_level = 3
        formality_level = 3
        
        if cultural_context == CulturalContext.RESPECTFUL:
            politeness_level = 5
            formality_level = 4
        elif cultural_context == CulturalContext.EMPATHETIC:
            politeness_level = 4
            formality_level = 2
        elif cultural_context == CulturalContext.FORMAL:
            politeness_level = 3
            formality_level = 5
        
        # Get appropriate honorifics
        honorifics = settings.get('honorifics', {})
        if user_age:
            try:
                age_num = int(''.join(filter(str.isdigit, str(user_age))))
                if age_num >= 60:
                    honorifics.update(settings.get('elder_honorifics', {}))
            except (ValueError, TypeError):
                pass
        
        return CulturalAdaptation(
            context=cultural_context,
            honorifics=honorifics,
            politeness_level=politeness_level,
            formality_level=formality_level,
            regional_preferences=settings.get('regional_preferences', {}),
            age_appropriate=True,
            gender_neutral=user_gender is None
        )
    
    def _select_cultural_template(self, templates: List[Dict[str, Any]], entities: List[Any],
                                context: ConversationContext, flow_result: Dict[str, Any],
                                adaptation: CulturalAdaptation) -> Dict[str, Any]:
        """Select the most appropriate cultural template."""
        # Score templates based on cultural fit
        scored_templates = []
        
        for template in templates:
            score = 0
            
            # Check politeness level match
            template_politeness = template.get('politeness_level', 3)
            if abs(template_politeness - adaptation.politeness_level) <= 1:
                score += 2
            
            # Check formality level match
            template_formality = template.get('formality_level', 3)
            if abs(template_formality - adaptation.formality_level) <= 1:
                score += 2
            
            # Check if template supports required entities
            required_entities = template.get('requires', [])
            entity_types = [getattr(e, 'type', str(e)) for e in entities]
            if all(req in entity_types for req in required_entities):
                score += 3
            
            # Check flow step compatibility
            template_steps = template.get('flow_steps', [])
            current_step = flow_result.get('current_step', '')
            if not template_steps or current_step in template_steps:
                score += 1
            
            scored_templates.append((score, template))
        
        # Return highest scoring template
        if scored_templates:
            scored_templates.sort(key=lambda x: x[0], reverse=True)
            return scored_templates[0][1]
        
        # Fallback to first template
        return templates[0] if templates else {}
    
    def _fill_cultural_template(self, template: Dict[str, Any], entities: List[Any],
                              context: ConversationContext, adaptation: CulturalAdaptation,
                              flow_result: Dict[str, Any]) -> str:
        """Fill template with cultural adaptations and entity values."""
        response_text = template.get('text', '')
        
        # Create entity value map
        entity_values = {}
        for entity in entities:
            if hasattr(entity, 'type') and hasattr(entity, 'value'):
                entity_values[entity.type.value] = entity.value
        
        # Add cultural elements
        entity_values.update({
            'honorific': self._get_appropriate_honorific(adaptation, context),
            'politeness_marker': self._get_politeness_marker(adaptation, context.language),
            'cultural_greeting': self._get_cultural_greeting(adaptation, context.language),
            'user_name': context.persistent_data.get('user_name', ''),
            'completion_status': flow_result.get('completion_status', ''),
            'next_step': flow_result.get('current_step', '')
        })
        
        # Add missing information prompts
        missing_info = flow_result.get('missing_info', [])
        if missing_info:
            entity_values['missing_info_prompt'] = self._generate_missing_info_prompt(
                missing_info, adaptation, context.language
            )
        
        # Fill template
        try:
            return response_text.format(**entity_values)
        except KeyError as e:
            logger.warning("Template filling failed for key %s, using fallback", str(e))
            return response_text
    
    def _get_appropriate_honorific(self, adaptation: CulturalAdaptation,
                                 context: ConversationContext) -> str:
        """Get appropriate honorific based on cultural context."""
        honorifics = adaptation.honorifics
        
        # Check user characteristics
        user_age = context.persistent_data.get('age')
        user_gender = context.persistent_data.get('gender')
        
        if user_age:
            try:
                age_num = int(''.join(filter(str.isdigit, str(user_age))))
                if age_num >= 60:
                    return honorifics.get('elder', honorifics.get('default', ''))
            except (ValueError, TypeError):
                pass
        
        if user_gender == 'male':
            return honorifics.get('male', honorifics.get('default', ''))
        elif user_gender == 'female':
            return honorifics.get('female', honorifics.get('default', ''))
        else:
            return honorifics.get('neutral', honorifics.get('default', ''))
    
    def _get_politeness_marker(self, adaptation: CulturalAdaptation, language: str) -> str:
        """Get appropriate politeness marker for the language."""
        markers = {
            'hi': {
                1: '', 2: 'कृपया', 3: 'कृपया', 4: 'कृपया', 5: 'कृपया करके'
            },
            'en': {
                1: '', 2: 'please', 3: 'please', 4: 'kindly', 5: 'kindly please'
            }
        }
        
        lang_markers = markers.get(language, markers['hi'])
        return lang_markers.get(adaptation.politeness_level, 'कृपया')
    
    def _get_cultural_greeting(self, adaptation: CulturalAdaptation, language: str) -> str:
        """Get culturally appropriate greeting."""
        greetings = {
            'hi': {
                CulturalContext.FORMAL: 'नमस्कार',
                CulturalContext.RESPECTFUL: 'प्रणाम',
                CulturalContext.SUPPORTIVE: 'नमस्ते',
                CulturalContext.EMPATHETIC: 'नमस्ते',
                CulturalContext.ENCOURAGING: 'नमस्ते'
            },
            'en': {
                CulturalContext.FORMAL: 'Good day',
                CulturalContext.RESPECTFUL: 'Respected Sir/Madam',
                CulturalContext.SUPPORTIVE: 'Hello',
                CulturalContext.EMPATHETIC: 'Hello',
                CulturalContext.ENCOURAGING: 'Hello'
            }
        }
        
        lang_greetings = greetings.get(language, greetings['hi'])
        return lang_greetings.get(adaptation.context, 'नमस्ते')
    
    def _generate_missing_info_prompt(self, missing_info: List[str],
                                    adaptation: CulturalAdaptation, language: str) -> str:
        """Generate prompt for missing information."""
        prompts = {
            'hi': {
                'phone_number': 'कृपया अपना फोन नंबर बताएं',
                'reference_number': 'कृपया अपना संदर्भ नंबर बताएं',
                'age': 'कृपया अपनी आयु बताएं',
                'address': 'कृपया अपना पता बताएं',
                'problem_description': 'कृपया अपनी समस्या का विवरण दें'
            },
            'en': {
                'phone_number': 'Please provide your phone number',
                'reference_number': 'Please provide your reference number',
                'age': 'Please provide your age',
                'address': 'Please provide your address',
                'problem_description': 'Please describe your problem'
            }
        }
        
        lang_prompts = prompts.get(language, prompts['hi'])
        missing_prompts = [lang_prompts.get(info, f'Please provide {info}') for info in missing_info]
        
        if language == 'hi':
            return ' और '.join(missing_prompts)
        else:
            return ' and '.join(missing_prompts)
    
    def _check_required_information(self, entities: List[Any], flow: Dict[str, Any],
                                  context: ConversationContext) -> Dict[str, Any]:
        """Check what required information is available."""
        required_info = {}
        
        # Check entities
        for entity in entities:
            if hasattr(entity, 'type') and hasattr(entity, 'value'):
                required_info[entity.type.value] = entity.value
        
        # Check persistent data
        required_info.update(context.persistent_data)
        
        return required_info
    
    def _determine_next_flow_step(self, intent: ServiceIntent, entities: List[Any],
                                required_info: Dict[str, Any], flow: Dict[str, Any]) -> str:
        """Determine the next step in the conversation flow."""
        # Simple flow logic - can be enhanced
        if intent == ServiceIntent.SCHEME_DISCOVERY:
            if 'age' in required_info and 'government_service' in required_info:
                return 'eligibility_check'
            elif 'age' in required_info:
                return 'service_identification'
            else:
                return 'information_gathering'
        
        elif intent == ServiceIntent.GRIEVANCE_FILING:
            if 'problem_description' in required_info and 'phone_number' in required_info:
                return 'grievance_submission'
            elif 'problem_description' in required_info:
                return 'contact_collection'
            else:
                return 'problem_description'
        
        elif intent == ServiceIntent.STATUS_TRACKING:
            if 'reference_number' in required_info:
                return 'status_lookup'
            else:
                return 'reference_collection'
        
        return 'initial'
    
    def _check_completion_criteria(self, entities: List[Any], context: ConversationContext,
                                 flow: Dict[str, Any]) -> str:
        """Check if conversation flow completion criteria are met."""
        # Simple completion logic - can be enhanced
        required_fields = flow.get('required_information', [])
        available_info = set(context.persistent_data.keys())
        
        # Add current entities
        for entity in entities:
            if hasattr(entity, 'type'):
                available_info.add(entity.type.value)
        
        # Only mark as completed if all required fields are present AND
        # we have sufficient information for the specific intent
        if required_fields and all(field in available_info for field in required_fields):
            # Additional checks for specific intents
            if len(context.turns) > 0:
                last_intent = context.turns[-1].intent
                if last_intent == 'scheme_discovery':
                    # Need both age and service type to be completed
                    if 'age' in available_info and 'government_service' in available_info:
                        return 'completed'
                elif last_intent == 'status_tracking':
                    # Need reference number to be completed
                    if 'reference_number' in available_info:
                        return 'completed'
                elif last_intent == 'grievance_filing':
                    # Need problem description and contact info
                    if 'problem_description' in available_info and 'phone_number' in available_info:
                        return 'completed'
        
        if len(available_info.intersection(required_fields)) > 0:
            return 'in_progress'
        else:
            return 'not_started'
    
    def _determine_next_state(self, intent: ServiceIntent, entities: List[Any],
                            context: ConversationContext, flow_result: Dict[str, Any]) -> ConversationState:
        """Determine the next conversation state."""
        completion_status = flow_result.get('completion_status', 'in_progress')
        
        # Only mark as completed if we have all required information
        if completion_status == 'completed':
            return ConversationState.COMPLETED
        
        # State based on intent
        state_mapping = {
            ServiceIntent.SCHEME_DISCOVERY: ConversationState.SCHEME_DISCOVERY,
            ServiceIntent.GRIEVANCE_FILING: ConversationState.GRIEVANCE_FILING,
            ServiceIntent.STATUS_TRACKING: ConversationState.STATUS_TRACKING,
            ServiceIntent.DOCUMENT_HELP: ConversationState.DOCUMENT_COLLECTION,
            ServiceIntent.APPLICATION_HELP: ConversationState.SCHEME_DISCOVERY,
            ServiceIntent.ELIGIBILITY_CHECK: ConversationState.SCHEME_DISCOVERY
        }
        
        return state_mapping.get(intent, ConversationState.INITIAL)
    
    def _extract_persistent_data(self, entities: List[Any]) -> Dict[str, Any]:
        """Extract data that should persist across conversation turns."""
        persistent_data = {}
        
        persistent_types = ['person_name', 'phone_number', 'email', 'reference_number', 'age', 'address']
        
        for entity in entities:
            if hasattr(entity, 'type') and hasattr(entity, 'value'):
                if entity.type.value in persistent_types:
                    persistent_data[entity.type.value] = entity.value
        
        return persistent_data
    
    def _extract_temporary_data(self, intent: ServiceIntent, entities: List[Any],
                              flow_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract temporary data for current context."""
        return {
            'last_intent': intent.value,
            'last_flow_step': flow_result.get('current_step'),
            'completion_status': flow_result.get('completion_status'),
            'requires_followup': flow_result.get('requires_followup', False)
        }
    
    def _get_error_recovery_response(self, error_type: ErrorType, cultural_context: CulturalContext,
                                   language: str, error_info: Dict[str, Any]) -> str:
        """Get culturally appropriate error recovery response."""
        responses = {
            'hi': {
                ErrorType.MISUNDERSTANDING: [
                    "क्षमा करें, मैं आपकी बात पूरी तरह समझ नहीं पाया। कृपया अपनी आवश्यकता को और स्पष्ट रूप से बताएं।",
                    "मुझे खुशी होगी यदि आप अपनी बात को दूसरे तरीके से कह सकें।"
                ],
                ErrorType.INCOMPLETE_INFO: [
                    "आपकी सहायता के लिए मुझे कुछ और जानकारी चाहिए। कृपया विस्तार से बताएं।",
                    "कृपया अपनी आवश्यकता के बारे में और जानकारी दें।"
                ],
                ErrorType.LANGUAGE_BARRIER: [
                    "मैं आपकी भाषा को बेहतर तरीके से समझने की कोशिश कर रहा हूं। कृपया सरल शब्दों में बताएं।",
                    "कृपया अपनी बात को आसान शब्दों में कहें।"
                ],
                ErrorType.TIMEOUT: [
                    "क्या आप अभी भी वहां हैं? मैं आपकी सहायता के लिए तैयार हूं।",
                    "कृपया बताएं कि आप क्या चाहते हैं।"
                ]
            },
            'en': {
                ErrorType.MISUNDERSTANDING: [
                    "I apologize, I didn't fully understand your request. Could you please clarify what you need?",
                    "I would be happy to help if you could rephrase your request."
                ],
                ErrorType.INCOMPLETE_INFO: [
                    "I need some additional information to assist you better. Please provide more details.",
                    "Could you please provide more information about your requirement?"
                ],
                ErrorType.LANGUAGE_BARRIER: [
                    "I'm trying to better understand your language. Please use simple words.",
                    "Could you please express your request in simpler terms?"
                ],
                ErrorType.TIMEOUT: [
                    "Are you still there? I'm ready to help you.",
                    "Please let me know what you need assistance with."
                ]
            }
        }
        
        lang_responses = responses.get(language, responses['hi'])
        error_responses = lang_responses.get(error_type, lang_responses[ErrorType.MISUNDERSTANDING])
        
        # Select response based on cultural context
        if cultural_context == CulturalContext.RESPECTFUL:
            return error_responses[0]  # More formal response
        else:
            return error_responses[-1]  # More casual response
    
    def _get_fallback_response(self, intent: ServiceIntent, language: str,
                             cultural_context: CulturalContext) -> str:
        """Get fallback response when no template is available."""
        fallbacks = {
            'hi': {
                ServiceIntent.SCHEME_DISCOVERY: "मैं आपके लिए उपयुक्त सरकारी योजनाएं खोजने में मदद करूंगा।",
                ServiceIntent.GRIEVANCE_FILING: "मैं आपकी शिकायत दर्ज करने में सहायता करूंगा।",
                ServiceIntent.STATUS_TRACKING: "मैं आपके आवेदन की स्थिति की जांच करने में मदद करूंगा।"
            },
            'en': {
                ServiceIntent.SCHEME_DISCOVERY: "I will help you find suitable government schemes.",
                ServiceIntent.GRIEVANCE_FILING: "I will assist you in filing your complaint.",
                ServiceIntent.STATUS_TRACKING: "I will help you check your application status."
            }
        }
        
        lang_fallbacks = fallbacks.get(language, fallbacks['hi'])
        return lang_fallbacks.get(intent, "मैं आपकी सहायता करने के लिए यहाँ हूँ।")
    
    def _handle_critical_error(self, session_id: str, error_message: str, language: str) -> Dict[str, Any]:
        """Handle critical errors that prevent normal conversation flow."""
        error_responses = {
            'hi': "क्षमा करें, तकनीकी समस्या के कारण मैं आपकी सहायता नहीं कर पा रहा। कृपया बाद में पुनः प्रयास करें।",
            'en': "I apologize, I'm unable to assist due to a technical issue. Please try again later."
        }
        
        response = error_responses.get(language, error_responses['hi'])
        
        return {
            'response': response,
            'state': ConversationState.ERROR.value,
            'cultural_context': CulturalContext.FORMAL.value,
            'error_recovery': True,
            'requires_followup': False,
            'completion_status': 'error'
        }
    
    def _load_cultural_settings(self) -> Dict[str, Dict[str, Any]]:
        """Load cultural adaptation settings for different languages and contexts."""
        return {
            'hi': {
                'formal': {
                    'honorifics': {
                        'default': 'जी',
                        'elder': 'आदरणीय',
                        'male': 'श्रीमान',
                        'female': 'श्रीमती',
                        'neutral': 'जी'
                    },
                    'elder_honorifics': {
                        'default': 'आदरणीय',
                        'male': 'आदरणीय श्रीमान',
                        'female': 'आदरणीय श्रीमती'
                    }
                },
                'respectful': {
                    'honorifics': {
                        'default': 'आदरणीय',
                        'elder': 'पूज्य',
                        'male': 'आदरणीय श्रीमान',
                        'female': 'आदरणीय श्रीमती',
                        'neutral': 'आदरणीय'
                    }
                },
                'supportive': {
                    'honorifics': {
                        'default': 'जी',
                        'elder': 'आदरणीय',
                        'male': 'भाई साहब',
                        'female': 'बहन जी',
                        'neutral': 'जी'
                    }
                },
                'empathetic': {
                    'honorifics': {
                        'default': 'जी',
                        'elder': 'आदरणीय',
                        'male': 'भाई',
                        'female': 'बहन',
                        'neutral': 'जी'
                    }
                },
                'encouraging': {
                    'honorifics': {
                        'default': 'जी',
                        'elder': 'आदरणीय',
                        'male': 'भाई साहब',
                        'female': 'बहन जी',
                        'neutral': 'जी'
                    }
                }
            },
            'en': {
                'formal': {
                    'honorifics': {
                        'default': 'Sir/Madam',
                        'elder': 'Respected Sir/Madam',
                        'male': 'Sir',
                        'female': 'Madam',
                        'neutral': 'Sir/Madam'
                    }
                },
                'respectful': {
                    'honorifics': {
                        'default': 'Respected Sir/Madam',
                        'elder': 'Respected Sir/Madam',
                        'male': 'Respected Sir',
                        'female': 'Respected Madam',
                        'neutral': 'Respected Sir/Madam'
                    }
                },
                'supportive': {
                    'honorifics': {
                        'default': '',
                        'elder': 'Sir/Madam',
                        'male': '',
                        'female': '',
                        'neutral': ''
                    }
                },
                'empathetic': {
                    'honorifics': {
                        'default': '',
                        'elder': 'Sir/Madam',
                        'male': '',
                        'female': '',
                        'neutral': ''
                    }
                },
                'encouraging': {
                    'honorifics': {
                        'default': '',
                        'elder': 'Sir/Madam',
                        'male': '',
                        'female': '',
                        'neutral': ''
                    }
                }
            }
        }
    
    def _load_error_recovery_strategies(self) -> Dict[ErrorType, ErrorRecoveryStrategy]:
        """Load error recovery strategies."""
        return {
            ErrorType.MISUNDERSTANDING: ErrorRecoveryStrategy(
                error_type=ErrorType.MISUNDERSTANDING,
                recovery_actions=['clarify_request', 'provide_examples', 'simplify_language'],
                fallback_responses={},
                max_attempts=3,
                escalation_threshold=2
            ),
            ErrorType.INCOMPLETE_INFO: ErrorRecoveryStrategy(
                error_type=ErrorType.INCOMPLETE_INFO,
                recovery_actions=['request_specific_info', 'provide_guidance'],
                fallback_responses={},
                max_attempts=2,
                escalation_threshold=1
            ),
            ErrorType.LANGUAGE_BARRIER: ErrorRecoveryStrategy(
                error_type=ErrorType.LANGUAGE_BARRIER,
                recovery_actions=['switch_language', 'use_simple_words', 'provide_examples'],
                fallback_responses={},
                max_attempts=3,
                escalation_threshold=2
            ),
            ErrorType.TIMEOUT: ErrorRecoveryStrategy(
                error_type=ErrorType.TIMEOUT,
                recovery_actions=['check_availability', 'summarize_progress'],
                fallback_responses={},
                max_attempts=1,
                escalation_threshold=1
            )
        }
    
    def _load_conversation_flows(self) -> Dict[str, Dict[str, Any]]:
        """Load conversation flow definitions."""
        return {
            'initial_scheme_discovery': {
                'required_information': ['age', 'government_service'],
                'optional_information': ['income', 'location', 'family_size'],
                'steps': ['information_gathering', 'service_identification', 'eligibility_check', 'recommendation']
            },
            'initial_grievance_filing': {
                'required_information': ['problem_description', 'phone_number'],
                'optional_information': ['email', 'address', 'reference_number'],
                'steps': ['problem_description', 'contact_collection', 'grievance_submission', 'confirmation']
            },
            'initial_status_tracking': {
                'required_information': ['reference_number'],
                'optional_information': ['phone_number'],
                'steps': ['reference_collection', 'status_lookup', 'status_explanation']
            },
            'default': {
                'required_information': [],
                'optional_information': [],
                'steps': ['initial', 'information_gathering', 'processing', 'completion']
            }
        }
    
    def _load_cultural_templates(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Load cultural response templates."""
        return {
            'hi': {
                'scheme_discovery_formal': [
                    {
                        'text': "{cultural_greeting} {honorific}, मैं आपके लिए उपयुक्त सरकारी योजनाओं की खोज करूंगा। {politeness_marker} अपनी आवश्यकता बताएं।",
                        'politeness_level': 4,
                        'formality_level': 5,
                        'requires': [],
                        'flow_steps': ['initial', 'information_gathering']
                    }
                ],
                'scheme_discovery_respectful': [
                    {
                        'text': "{cultural_greeting} {honorific}, आपकी सेवा में मैं उपस्थित हूं। {politeness_marker} बताएं कि आपको किस प्रकार की सरकारी योजना चाहिए।",
                        'politeness_level': 5,
                        'formality_level': 4,
                        'requires': [],
                        'flow_steps': ['initial', 'information_gathering']
                    }
                ],
                'scheme_discovery_encouraging': [
                    {
                        'text': "{cultural_greeting} {honorific}, मैं आपको सही योजना खोजने में मदद करूंगा। {politeness_marker} अपनी स्थिति के बारे में बताएं।",
                        'politeness_level': 3,
                        'formality_level': 2,
                        'requires': [],
                        'flow_steps': ['initial', 'information_gathering']
                    }
                ],
                'grievance_filing_empathetic': [
                    {
                        'text': "{cultural_greeting} {honorific}, मैं समझ सकता हूं कि आपको परेशानी हो रही है। {politeness_marker} अपनी समस्या विस्तार से बताएं ताकि मैं आपकी सहायता कर सकूं।",
                        'politeness_level': 4,
                        'formality_level': 2,
                        'requires': [],
                        'flow_steps': ['initial', 'problem_description']
                    }
                ],
                'grievance_filing': [
                    {
                        'text': "मैं आपकी शिकायत दर्ज करने में सहायता करूंगा। {politeness_marker} अपनी समस्या विस्तार से बताएं।",
                        'politeness_level': 3,
                        'formality_level': 3,
                        'requires': [],
                        'flow_steps': ['initial', 'problem_description']
                    }
                ],
                'status_tracking_supportive': [
                    {
                        'text': "{cultural_greeting} {honorific}, मैं आपके आवेदन की स्थिति की जांच करूंगा। {politeness_marker} अपना संदर्भ नंबर बताएं।",
                        'politeness_level': 3,
                        'formality_level': 3,
                        'requires': [],
                        'flow_steps': ['initial', 'reference_collection']
                    }
                ]
            },
            'en': {
                'scheme_discovery_formal': [
                    {
                        'text': "{cultural_greeting} {honorific}, I will help you find suitable government schemes. {politeness_marker} tell me your requirements.",
                        'politeness_level': 4,
                        'formality_level': 5,
                        'requires': [],
                        'flow_steps': ['initial', 'information_gathering']
                    }
                ],
                'scheme_discovery_respectful': [
                    {
                        'text': "{cultural_greeting} {honorific}, I am here to serve you. {politeness_marker} tell me what type of government scheme you need.",
                        'politeness_level': 5,
                        'formality_level': 4,
                        'requires': [],
                        'flow_steps': ['initial', 'information_gathering']
                    }
                ],
                'scheme_discovery_encouraging': [
                    {
                        'text': "{cultural_greeting} {honorific}, I will help you find the right scheme. {politeness_marker} tell me about your situation.",
                        'politeness_level': 3,
                        'formality_level': 2,
                        'requires': [],
                        'flow_steps': ['initial', 'information_gathering']
                    }
                ],
                'grievance_filing_empathetic': [
                    {
                        'text': "{cultural_greeting} {honorific}, I understand you are facing some difficulties. {politeness_marker} describe your problem in detail so I can assist you.",
                        'politeness_level': 4,
                        'formality_level': 2,
                        'requires': [],
                        'flow_steps': ['initial', 'problem_description']
                    }
                ],
                'grievance_filing': [
                    {
                        'text': "I will assist you in filing your complaint. {politeness_marker} describe your problem in detail.",
                        'politeness_level': 3,
                        'formality_level': 3,
                        'requires': [],
                        'flow_steps': ['initial', 'problem_description']
                    }
                ],
                'status_tracking_supportive': [
                    {
                        'text': "{cultural_greeting} {honorific}, I will check your application status. {politeness_marker} provide your reference number.",
                        'politeness_level': 3,
                        'formality_level': 3,
                        'requires': [],
                        'flow_steps': ['initial', 'reference_collection']
                    }
                ]
            }
        }