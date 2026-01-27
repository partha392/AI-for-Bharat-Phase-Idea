"""
Unit tests for the enhanced conversation management system.

Tests cultural adaptation, error recovery, and sophisticated flow management
for government service interactions across multiple Indian languages.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from bharat_voice_assistant.language.conversation_manager import (
    ConversationManager, CulturalContext, ErrorType, CulturalAdaptation,
    ErrorRecoveryStrategy, ConversationFlow
)
from bharat_voice_assistant.language.context_manager import (
    ContextManager, ConversationContext, ConversationTurn, ConversationState
)
from bharat_voice_assistant.language.intent_classifier import ServiceIntent
from bharat_voice_assistant.language.entity_extractor import EntityType, Entity
from bharat_voice_assistant.core.exceptions import ContextManagementError


class TestConversationManager:
    """Test cases for ConversationManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.context_manager = ContextManager()
        self.conversation_manager = ConversationManager(self.context_manager)
    
    def test_initialization(self):
        """Test conversation manager initialization."""
        assert self.conversation_manager.context_manager is not None
        assert hasattr(self.conversation_manager, '_cultural_settings')
        assert hasattr(self.conversation_manager, '_error_strategies')
        assert hasattr(self.conversation_manager, '_conversation_flows')
        assert hasattr(self.conversation_manager, '_cultural_templates')
    
    def test_manage_conversation_turn_new_session(self):
        """Test managing conversation turn for a new session."""
        session_id = "test_session_123"
        user_input = "I need pension information"
        intent = ServiceIntent.SCHEME_DISCOVERY
        entities = []
        language = "en"
        confidence = 0.8
        
        result = self.conversation_manager.manage_conversation_turn(
            session_id=session_id,
            user_input=user_input,
            intent=intent,
            entities=entities,
            language=language,
            confidence=confidence
        )
        
        assert 'response' in result
        assert 'state' in result
        assert 'cultural_context' in result
        assert result['state'] == ConversationState.SCHEME_DISCOVERY.value
        assert len(result['response']) > 0
        
        # Check that context was created
        context = self.context_manager.get_context(session_id)
        assert context is not None
        assert len(context.turns) == 1
    
    def test_cultural_context_determination_elderly_user(self):
        """Test cultural context determination for elderly users."""
        session_id = "test_session_elderly"
        
        # Create context with elderly user
        context = self.context_manager.create_context(session_id, language='hi')
        context.persistent_data['age'] = '70'
        
        # Create age entity
        age_entity = Mock()
        age_entity.type = EntityType.AGE
        age_entity.value = '70'
        
        cultural_context = self.conversation_manager._determine_cultural_context(
            ServiceIntent.SCHEME_DISCOVERY, [age_entity], context
        )
        
        assert cultural_context == CulturalContext.RESPECTFUL
    
    def test_cultural_context_determination_grievance(self):
        """Test cultural context determination for grievance filing."""
        session_id = "test_session_grievance"
        context = self.context_manager.create_context(session_id, language='hi')
        
        cultural_context = self.conversation_manager._determine_cultural_context(
            ServiceIntent.GRIEVANCE_FILING, [], context
        )
        
        assert cultural_context == CulturalContext.EMPATHETIC
    
    def test_error_detection_low_confidence(self):
        """Test error detection for low confidence intent classification."""
        session_id = "test_session_error"
        context = self.context_manager.create_context(session_id, language='hi')
        
        error_info = self.conversation_manager._detect_conversation_errors(
            "unclear input", ServiceIntent.UNKNOWN, 0.2, context
        )
        
        assert error_info is not None
        assert error_info['type'] == ErrorType.MISUNDERSTANDING
        assert error_info['severity'] == 'medium'
    
    def test_error_detection_repeated_unknown_intents(self):
        """Test error detection for repeated unknown intents."""
        session_id = "test_session_repeated"
        context = self.context_manager.create_context(session_id, language='hi')
        
        # Add multiple turns with unknown intents
        for i in range(3):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                timestamp=datetime.now(),
                user_input=f"unclear input {i}",
                language="hi",
                intent=ServiceIntent.UNKNOWN.value,
                entities={},
                system_response="I don't understand",
                confidence=0.1,
                state=ConversationState.INITIAL
            )
            context.turns.append(turn)
        
        error_info = self.conversation_manager._detect_conversation_errors(
            "another unclear input", ServiceIntent.UNKNOWN, 0.1, context
        )
        
        assert error_info is not None
        assert error_info['type'] == ErrorType.LANGUAGE_BARRIER
        assert error_info['severity'] == 'high'
    
    def test_error_recovery_handling(self):
        """Test error recovery handling."""
        session_id = "test_session_recovery"
        error_info = {
            'type': ErrorType.MISUNDERSTANDING,
            'severity': 'medium',
            'details': 'Low confidence'
        }
        cultural_context = CulturalContext.FORMAL
        language = 'hi'
        
        result = self.conversation_manager._handle_error_recovery(
            session_id, error_info, cultural_context, language
        )
        
        assert result['error_recovery'] is True
        assert result['requires_followup'] is True
        assert result['state'] == ConversationState.ERROR.value
        assert len(result['response']) > 0
        
        # Check that error recovery turn was added
        context = self.context_manager.get_context(session_id)
        assert context is not None
        assert len(context.turns) == 1
        assert context.turns[0].metadata['error_type'] == ErrorType.MISUNDERSTANDING.value
    
    def test_conversation_flow_management_scheme_discovery(self):
        """Test conversation flow management for scheme discovery."""
        session_id = "test_session_flow"
        context = self.context_manager.create_context(session_id, language='hi')
        
        # Create entities
        age_entity = Mock()
        age_entity.type = EntityType.AGE
        age_entity.value = '65'
        
        entities = [age_entity]
        
        flow_result = self.conversation_manager._manage_conversation_flow(
            session_id, ServiceIntent.SCHEME_DISCOVERY, entities, context
        )
        
        assert 'current_step' in flow_result
        assert 'required_info' in flow_result
        assert 'missing_info' in flow_result
        assert 'completion_status' in flow_result
        assert flow_result['current_step'] == 'service_identification'
    
    def test_conversation_flow_management_grievance_filing(self):
        """Test conversation flow management for grievance filing."""
        session_id = "test_session_grievance_flow"
        context = self.context_manager.create_context(session_id, language='hi')
        
        # Add problem description to persistent data
        context.persistent_data['problem_description'] = 'My pension is delayed'
        
        entities = []
        
        flow_result = self.conversation_manager._manage_conversation_flow(
            session_id, ServiceIntent.GRIEVANCE_FILING, entities, context
        )
        
        assert flow_result['current_step'] == 'contact_collection'
        assert 'problem_description' in flow_result['required_info']
    
    def test_cultural_response_generation_hindi_respectful(self):
        """Test cultural response generation in Hindi with respectful context."""
        session_id = "test_session_cultural"
        context = self.context_manager.create_context(session_id, language='hi')
        context.persistent_data['age'] = '70'
        
        cultural_context = CulturalContext.RESPECTFUL
        entities = []
        flow_result = {'current_step': 'initial', 'completion_status': 'not_started'}
        
        response = self.conversation_manager._generate_cultural_response(
            ServiceIntent.SCHEME_DISCOVERY, entities, context, cultural_context, 'hi', flow_result
        )
        
        assert len(response) > 0
        # Should contain respectful elements in Hindi
        assert any(word in response for word in ['आदरणीय', 'प्रणाम', 'सेवा'])
    
    def test_cultural_response_generation_english_formal(self):
        """Test cultural response generation in English with formal context."""
        session_id = "test_session_formal"
        context = self.context_manager.create_context(session_id, language='en')
        
        cultural_context = CulturalContext.FORMAL
        entities = []
        flow_result = {'current_step': 'initial', 'completion_status': 'not_started'}
        
        response = self.conversation_manager._generate_cultural_response(
            ServiceIntent.SCHEME_DISCOVERY, entities, context, cultural_context, 'en', flow_result
        )
        
        assert len(response) > 0
        # Should contain formal elements in English
        assert any(word in response.lower() for word in ['sir', 'madam', 'good day'])
    
    def test_cultural_adaptation_settings(self):
        """Test cultural adaptation settings retrieval."""
        context = self.context_manager.create_context("test", language='hi')
        context.persistent_data['age'] = '65'
        
        adaptation = self.conversation_manager._get_cultural_adaptation(
            'hi', CulturalContext.RESPECTFUL, context
        )
        
        assert isinstance(adaptation, CulturalAdaptation)
        assert adaptation.context == CulturalContext.RESPECTFUL
        assert adaptation.politeness_level == 5
        assert adaptation.formality_level == 4
        assert 'आदरणीय' in adaptation.honorifics.get('default', '')
    
    def test_honorific_selection_elderly_user(self):
        """Test appropriate honorific selection for elderly users."""
        context = self.context_manager.create_context("test", language='hi')
        context.persistent_data['age'] = '75'
        context.persistent_data['gender'] = 'male'
        
        adaptation = CulturalAdaptation(
            context=CulturalContext.RESPECTFUL,
            honorifics={
                'default': 'जी',
                'elder': 'आदरणीय',
                'male': 'श्रीमान',
                'elder_male': 'आदरणीय श्रीमान'
            }
        )
        
        honorific = self.conversation_manager._get_appropriate_honorific(adaptation, context)
        
        # Should prioritize elder honorific
        assert honorific in ['आदरणीय', 'आदरणीय श्रीमान', '']
    
    def test_politeness_marker_selection(self):
        """Test politeness marker selection based on adaptation level."""
        adaptation = CulturalAdaptation(
            context=CulturalContext.RESPECTFUL,
            politeness_level=5
        )
        
        marker_hi = self.conversation_manager._get_politeness_marker(adaptation, 'hi')
        marker_en = self.conversation_manager._get_politeness_marker(adaptation, 'en')
        
        assert marker_hi == 'कृपया करके'
        assert marker_en == 'kindly please'
    
    def test_missing_information_prompt_generation(self):
        """Test generation of prompts for missing information."""
        missing_info = ['phone_number', 'age']
        adaptation = CulturalAdaptation(context=CulturalContext.FORMAL)
        
        prompt_hi = self.conversation_manager._generate_missing_info_prompt(
            missing_info, adaptation, 'hi'
        )
        prompt_en = self.conversation_manager._generate_missing_info_prompt(
            missing_info, adaptation, 'en'
        )
        
        assert 'फोन नंबर' in prompt_hi
        assert 'आयु' in prompt_hi
        assert 'phone number' in prompt_en
        assert 'age' in prompt_en
    
    def test_incomplete_information_detection(self):
        """Test detection of incomplete information patterns."""
        context = self.context_manager.create_context("test", language='hi')
        
        # Test status tracking without reference number
        is_incomplete = self.conversation_manager._is_incomplete_information(
            "check my status", ServiceIntent.STATUS_TRACKING, context
        )
        assert is_incomplete is True
        
        # Test status tracking with reference number
        is_complete = self.conversation_manager._is_incomplete_information(
            "check status of REF123456", ServiceIntent.STATUS_TRACKING, context
        )
        assert is_complete is False
        
        # Test grievance filing with short description
        is_incomplete_grievance = self.conversation_manager._is_incomplete_information(
            "problem", ServiceIntent.GRIEVANCE_FILING, context
        )
        assert is_incomplete_grievance is True
    
    def test_persistent_data_extraction(self):
        """Test extraction of persistent data from entities."""
        # Create mock entities
        phone_entity = Mock()
        phone_entity.type = Mock()
        phone_entity.type.value = 'phone_number'
        phone_entity.value = '9876543210'
        
        name_entity = Mock()
        name_entity.type = Mock()
        name_entity.type.value = 'person_name'
        name_entity.value = 'John Doe'
        
        temp_entity = Mock()
        temp_entity.type = Mock()
        temp_entity.type.value = 'temporary_info'
        temp_entity.value = 'some value'
        
        entities = [phone_entity, name_entity, temp_entity]
        
        persistent_data = self.conversation_manager._extract_persistent_data(entities)
        
        assert 'phone_number' in persistent_data
        assert 'person_name' in persistent_data
        assert 'temporary_info' not in persistent_data  # Should not be persistent
        assert persistent_data['phone_number'] == '9876543210'
        assert persistent_data['person_name'] == 'John Doe'
    
    def test_temporary_data_extraction(self):
        """Test extraction of temporary data."""
        flow_result = {
            'current_step': 'information_gathering',
            'completion_status': 'in_progress',
            'requires_followup': True
        }
        
        temp_data = self.conversation_manager._extract_temporary_data(
            ServiceIntent.SCHEME_DISCOVERY, [], flow_result
        )
        
        assert temp_data['last_intent'] == ServiceIntent.SCHEME_DISCOVERY.value
        assert temp_data['last_flow_step'] == 'information_gathering'
        assert temp_data['completion_status'] == 'in_progress'
        assert temp_data['requires_followup'] is True
    
    def test_next_state_determination(self):
        """Test determination of next conversation state."""
        context = self.context_manager.create_context("test", language='hi')
        flow_result = {'completion_status': 'in_progress'}
        
        # Test scheme discovery state
        next_state = self.conversation_manager._determine_next_state(
            ServiceIntent.SCHEME_DISCOVERY, [], context, flow_result
        )
        assert next_state == ConversationState.SCHEME_DISCOVERY
        
        # Test completed flow
        flow_result['completion_status'] = 'completed'
        next_state = self.conversation_manager._determine_next_state(
            ServiceIntent.SCHEME_DISCOVERY, [], context, flow_result
        )
        assert next_state == ConversationState.COMPLETED
    
    def test_error_recovery_response_generation(self):
        """Test generation of error recovery responses."""
        error_info = {'details': 'Low confidence'}
        
        response_hi = self.conversation_manager._get_error_recovery_response(
            ErrorType.MISUNDERSTANDING, CulturalContext.RESPECTFUL, 'hi', error_info
        )
        response_en = self.conversation_manager._get_error_recovery_response(
            ErrorType.MISUNDERSTANDING, CulturalContext.FORMAL, 'en', error_info
        )
        
        assert len(response_hi) > 0
        assert len(response_en) > 0
        assert 'क्षमा' in response_hi or 'समझ' in response_hi
        assert 'apologize' in response_en.lower() or 'understand' in response_en.lower() or 'help' in response_en.lower()
    
    def test_fallback_response_generation(self):
        """Test fallback response generation."""
        response_hi = self.conversation_manager._get_fallback_response(
            ServiceIntent.SCHEME_DISCOVERY, 'hi', CulturalContext.FORMAL
        )
        response_en = self.conversation_manager._get_fallback_response(
            ServiceIntent.GRIEVANCE_FILING, 'en', CulturalContext.EMPATHETIC
        )
        
        assert len(response_hi) > 0
        assert len(response_en) > 0
        assert 'योजना' in response_hi or 'सहायता' in response_hi
        assert 'complaint' in response_en.lower() or 'assist' in response_en.lower()
    
    def test_critical_error_handling(self):
        """Test critical error handling."""
        result = self.conversation_manager._handle_critical_error(
            "test_session", "Database connection failed", 'hi'
        )
        
        assert result['error_recovery'] is True
        assert result['state'] == ConversationState.ERROR.value
        assert result['requires_followup'] is False
        assert result['completion_status'] == 'error'
        assert len(result['response']) > 0
        assert 'तकनीकी समस्या' in result['response'] or 'technical' in result['response'].lower()
    
    def test_conversation_flow_completion_criteria(self):
        """Test conversation flow completion criteria checking."""
        context = self.context_manager.create_context("test", language='hi')
        context.persistent_data.update({
            'age': '65',
            'government_service': 'pension'
        })
        
        # Add a turn with scheme_discovery intent to trigger completion logic
        turn = ConversationTurn(
            turn_id="test_turn",
            timestamp=datetime.now(),
            user_input="I need pension scheme",
            language="hi",
            intent="scheme_discovery",
            entities={'age': '65', 'government_service': 'pension'},
            system_response="Response",
            confidence=0.8,
            state=ConversationState.SCHEME_DISCOVERY
        )
        context.turns.append(turn)
        
        # Create mock entities
        age_entity = Mock()
        age_entity.type = Mock()
        age_entity.type.value = 'age'
        
        service_entity = Mock()
        service_entity.type = Mock()
        service_entity.type.value = 'government_service'
        
        entities = [age_entity, service_entity]
        
        flow = {
            'required_information': ['age', 'government_service'],
            'optional_information': ['income']
        }
        
        completion_status = self.conversation_manager._check_completion_criteria(
            entities, context, flow
        )
        
        assert completion_status == 'completed'
    
    def test_template_selection_scoring(self):
        """Test cultural template selection with scoring."""
        templates = [
            {
                'text': 'Formal response',
                'politeness_level': 5,
                'formality_level': 5,
                'requires': [],
                'flow_steps': ['initial']
            },
            {
                'text': 'Casual response',
                'politeness_level': 2,
                'formality_level': 2,
                'requires': ['age'],
                'flow_steps': ['information_gathering']
            }
        ]
        
        context = self.context_manager.create_context("test", language='hi')
        adaptation = CulturalAdaptation(
            context=CulturalContext.FORMAL,
            politeness_level=5,
            formality_level=5
        )
        flow_result = {'current_step': 'initial'}
        
        selected_template = self.conversation_manager._select_cultural_template(
            templates, [], context, flow_result, adaptation
        )
        
        # Should select the formal template due to better scoring
        assert selected_template['text'] == 'Formal response'
    
    def test_integration_with_context_manager(self):
        """Test integration with context manager."""
        session_id = "integration_test"
        
        # First conversation turn
        result1 = self.conversation_manager.manage_conversation_turn(
            session_id=session_id,
            user_input="I am 70 years old and need pension help",
            intent=ServiceIntent.SCHEME_DISCOVERY,
            entities=[],
            language='en',
            confidence=0.8
        )
        
        # Check that context was properly updated
        context = self.context_manager.get_context(session_id)
        assert context is not None
        assert len(context.turns) == 1
        assert context.current_state == ConversationState.SCHEME_DISCOVERY
        
        # Second conversation turn
        result2 = self.conversation_manager.manage_conversation_turn(
            session_id=session_id,
            user_input="What documents do I need?",
            intent=ServiceIntent.DOCUMENT_HELP,
            entities=[],
            language='en',
            confidence=0.9
        )
        
        # Check that context maintains history
        updated_context = self.context_manager.get_context(session_id)
        assert len(updated_context.turns) == 2
        # Document help goes to DOCUMENT_COLLECTION state, not COMPLETED
        assert updated_context.current_state == ConversationState.DOCUMENT_COLLECTION


class TestCulturalAdaptation:
    """Test cases for cultural adaptation functionality."""
    
    def test_cultural_context_enum(self):
        """Test cultural context enumeration."""
        assert CulturalContext.FORMAL.value == "formal"
        assert CulturalContext.RESPECTFUL.value == "respectful"
        assert CulturalContext.SUPPORTIVE.value == "supportive"
        assert CulturalContext.EMPATHETIC.value == "empathetic"
        assert CulturalContext.ENCOURAGING.value == "encouraging"
    
    def test_cultural_adaptation_dataclass(self):
        """Test cultural adaptation dataclass."""
        adaptation = CulturalAdaptation(
            context=CulturalContext.RESPECTFUL,
            honorifics={'default': 'Sir'},
            politeness_level=4,
            formality_level=3
        )
        
        assert adaptation.context == CulturalContext.RESPECTFUL
        assert adaptation.honorifics['default'] == 'Sir'
        assert adaptation.politeness_level == 4
        assert adaptation.formality_level == 3
        assert adaptation.age_appropriate is True
        assert adaptation.gender_neutral is True


class TestErrorRecovery:
    """Test cases for error recovery functionality."""
    
    def test_error_type_enum(self):
        """Test error type enumeration."""
        assert ErrorType.MISUNDERSTANDING.value == "misunderstanding"
        assert ErrorType.INCOMPLETE_INFO.value == "incomplete_info"
        assert ErrorType.TECHNICAL_ERROR.value == "technical_error"
        assert ErrorType.LANGUAGE_BARRIER.value == "language_barrier"
        assert ErrorType.CONTEXT_LOST.value == "context_lost"
        assert ErrorType.TIMEOUT.value == "timeout"
        assert ErrorType.INVALID_INPUT.value == "invalid_input"
    
    def test_error_recovery_strategy_dataclass(self):
        """Test error recovery strategy dataclass."""
        strategy = ErrorRecoveryStrategy(
            error_type=ErrorType.MISUNDERSTANDING,
            recovery_actions=['clarify', 'rephrase'],
            fallback_responses={'hi': 'समझ नहीं आया'},
            max_attempts=3,
            escalation_threshold=2
        )
        
        assert strategy.error_type == ErrorType.MISUNDERSTANDING
        assert 'clarify' in strategy.recovery_actions
        assert strategy.fallback_responses['hi'] == 'समझ नहीं आया'
        assert strategy.max_attempts == 3
        assert strategy.escalation_threshold == 2


if __name__ == "__main__":
    pytest.main([__file__])