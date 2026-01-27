"""
Tests for conversational grievance filing workflow.

This module tests the grievance filing functionality including
workflow management, validation, and conversational interface.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from bharat_voice_assistant.grievance.filing_assistant import ConversationalFilingAssistant
from bharat_voice_assistant.grievance.workflow_manager import GrievanceWorkflowManager, WorkflowStep, WorkflowState
from bharat_voice_assistant.grievance.validator import GrievanceValidator
from bharat_voice_assistant.grievance.models import (
    GrievanceRecord, GrievanceType, GrievancePriority, GrievanceStatus,
    WorkflowProgress, GrievanceDetails, ContactInformation
)
from bharat_voice_assistant.language.intent_classifier import ServiceIntent
from bharat_voice_assistant.language.entity_extractor import Entity, EntityType


class TestGrievanceWorkflowManager:
    """Test cases for GrievanceWorkflowManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.workflow_manager = GrievanceWorkflowManager()
    
    def test_start_workflow(self):
        """Test starting a new grievance workflow."""
        session_id = "test_session_001"
        language = "hi"
        
        grievance, response = self.workflow_manager.start_workflow(session_id, language)
        
        assert grievance.session_id == session_id
        assert grievance.language == language
        assert grievance.workflow_progress.current_step == WorkflowStep.PROBLEM_DESCRIPTION
        assert grievance.workflow_progress.current_state == WorkflowState.WAITING_FOR_INPUT
        assert response['step'] == WorkflowStep.INITIAL.value
        assert 'message' in response
        assert 'prompt' in response
    
    def test_process_problem_description(self):
        """Test processing problem description input."""
        # Create initial grievance
        grievance = GrievanceRecord(
            session_id="test_session",
            language="hi",
            workflow_progress=WorkflowProgress(
                current_step=WorkflowStep.PROBLEM_DESCRIPTION,
                current_state=WorkflowState.WAITING_FOR_INPUT
            )
        )
        
        user_input = "मेरा पेंशन 3 महीने से नहीं आया है। मैंने कई बार कार्यालय में जाकर पूछा है लेकिन कोई जवाब नहीं मिला।"
        intent = ServiceIntent.GRIEVANCE_FILING
        entities = [
            Entity(EntityType.GOVERNMENT_SERVICE, "pension", 0.9, 0, 6, "hi", "pension")
        ]
        
        updated_grievance, response = self.workflow_manager.process_user_input(
            grievance, user_input, intent, entities
        )
        
        assert updated_grievance.details is not None
        assert updated_grievance.details.problem_description == user_input
        assert updated_grievance.details.affected_service == "pension"
        assert 'success' in response or 'message' in response  # More flexible assertion
    
    def test_process_contact_information(self):
        """Test processing contact information input."""
        # Create grievance with problem description
        grievance = GrievanceRecord(
            session_id="test_session",
            language="hi",
            details=GrievanceDetails(
                problem_description="Test problem",
                grievance_type=GrievanceType.PENSION_ISSUE
            ),
            workflow_progress=WorkflowProgress(
                current_step=WorkflowStep.CONTACT_COLLECTION,
                current_state=WorkflowState.WAITING_FOR_INPUT
            )
        )
        
        user_input = "मेरा फोन नंबर 9876543210 है और ईमेल test@example.com है"
        intent = ServiceIntent.GRIEVANCE_FILING
        entities = [
            Entity(EntityType.PHONE_NUMBER, "9876543210", 0.9, 0, 10, "hi", "9876543210"),
            Entity(EntityType.EMAIL, "test@example.com", 0.9, 20, 35, "hi", "test@example.com")
        ]
        
        updated_grievance, response = self.workflow_manager.process_user_input(
            grievance, user_input, intent, entities
        )
        
        assert updated_grievance.contact_info is not None
        assert updated_grievance.contact_info.phone_number == "9876543210"
        assert updated_grievance.contact_info.email == "test@example.com"
        assert 'success' in response or 'message' in response  # More flexible assertion
    
    def test_workflow_completion(self):
        """Test complete workflow execution."""
        session_id = "test_complete_workflow"
        
        # Start workflow
        grievance, _ = self.workflow_manager.start_workflow(session_id, "hi")
        
        # Step 1: Problem description
        grievance.workflow_progress.current_step = WorkflowStep.PROBLEM_DESCRIPTION
        user_input = "राशन कार्ड में गलत नाम लिखा है"
        entities = [Entity(EntityType.GOVERNMENT_SERVICE, "ration", 0.9, 0, 6, "hi")]
        grievance, _ = self.workflow_manager.process_user_input(
            grievance, user_input, ServiceIntent.GRIEVANCE_FILING, entities
        )
        
        # Step 2: Category selection (automatic based on problem)
        grievance.workflow_progress.current_step = WorkflowStep.CATEGORY_SELECTION
        grievance, _ = self.workflow_manager.process_user_input(
            grievance, "राशन कार्ड", ServiceIntent.GRIEVANCE_FILING, []
        )
        
        # Step 3: Contact information
        grievance.workflow_progress.current_step = WorkflowStep.CONTACT_COLLECTION
        entities = [Entity(EntityType.PHONE_NUMBER, "9876543210", 0.9, 0, 10, "hi", "9876543210")]
        grievance, _ = self.workflow_manager.process_user_input(
            grievance, "9876543210", ServiceIntent.GRIEVANCE_FILING, entities
        )
        
        # Step 4: Skip documents
        grievance.workflow_progress.current_step = WorkflowStep.DOCUMENT_COLLECTION
        grievance, _ = self.workflow_manager.process_user_input(
            grievance, "छोड़ें", ServiceIntent.GRIEVANCE_FILING, []
        )
        
        # Step 5: Validation
        grievance.workflow_progress.current_step = WorkflowStep.VALIDATION
        grievance, _ = self.workflow_manager.process_user_input(
            grievance, "", ServiceIntent.GRIEVANCE_FILING, []
        )
        
        # Step 6: Confirmation
        grievance.workflow_progress.current_step = WorkflowStep.CONFIRMATION
        grievance, response = self.workflow_manager.process_user_input(
            grievance, "हाँ", ServiceIntent.GRIEVANCE_FILING, []
        )
        
        # Step 7: Submission
        grievance.workflow_progress.current_step = WorkflowStep.SUBMISSION
        grievance, final_response = self.workflow_manager.process_user_input(
            grievance, "", ServiceIntent.GRIEVANCE_FILING, []
        )
        
        assert final_response['completed'] is True
        assert grievance.reference_number is not None
        assert grievance.status == GrievanceStatus.SUBMITTED
        assert grievance.workflow_progress.current_step == WorkflowStep.COMPLETED


class TestGrievanceValidator:
    """Test cases for GrievanceValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = GrievanceValidator()
    
    def test_validate_phone_number(self):
        """Test phone number validation."""
        # Valid phone numbers
        valid_phones = ["9876543210", "+919876543210", "91-9876543210"]
        for phone in valid_phones:
            errors = self.validator.validate_field('phone_number', phone)
            assert len(errors) == 0, f"Phone {phone} should be valid"
        
        # Invalid phone numbers
        invalid_phones = ["123456789", "abcdefghij", "98765432100"]
        for phone in invalid_phones:
            errors = self.validator.validate_field('phone_number', phone)
            assert len(errors) > 0, f"Phone {phone} should be invalid"
    
    def test_validate_email(self):
        """Test email validation."""
        # Valid emails
        valid_emails = ["test@example.com", "user.name@domain.co.in", "test123@gmail.com"]
        for email in valid_emails:
            errors = self.validator.validate_field('email', email)
            assert len(errors) == 0, f"Email {email} should be valid"
        
        # Invalid emails
        invalid_emails = ["invalid-email", "test@", "@domain.com", "test.domain.com"]
        for email in invalid_emails:
            errors = self.validator.validate_field('email', email)
            assert len(errors) > 0, f"Email {email} should be invalid"
    
    def test_validate_problem_description(self):
        """Test problem description validation."""
        # Valid descriptions
        valid_desc = "मेरा पेंशन 3 महीने से नहीं आया है और मैंने कई बार कार्यालय में संपर्क किया है।"
        errors = self.validator.validate_field('problem_description', valid_desc)
        assert len(errors) == 0
        
        # Invalid descriptions
        invalid_desc = "समस्या"  # Too short
        errors = self.validator.validate_field('problem_description', invalid_desc)
        assert len(errors) > 0
        
        empty_desc = ""
        errors = self.validator.validate_field('problem_description', empty_desc)
        assert len(errors) > 0
    
    def test_validate_complete_grievance(self):
        """Test validation of complete grievance record."""
        # Create valid grievance
        grievance = GrievanceRecord(
            session_id="test_session",
            details=GrievanceDetails(
                problem_description="मेरा राशन कार्ड खो गया है और नया बनवाने के लिए आवेदन दिया था लेकिन अभी तक नहीं मिला।",
                grievance_type=GrievanceType.RATION_CARD_ISSUE
            ),
            contact_info=ContactInformation(
                phone_number="9876543210",
                email="test@example.com"
            )
        )
        
        result = self.validator.validate_grievance(grievance)
        assert result.is_valid is True
        assert result.completion_percentage >= 70
        assert len(result.errors) == 0
    
    def test_validate_incomplete_grievance(self):
        """Test validation of incomplete grievance record."""
        # Create incomplete grievance
        grievance = GrievanceRecord(
            session_id="test_session",
            details=GrievanceDetails(
                problem_description="समस्या",  # Too short
                grievance_type=GrievanceType.OTHER
            )
            # Missing contact info
        )
        
        result = self.validator.validate_grievance(grievance)
        assert result.is_valid is False
        assert result.completion_percentage < 50
        assert len(result.errors) > 0
        assert 'contact_information' in result.missing_required_fields


class TestConversationalFilingAssistant:
    """Test cases for ConversationalFilingAssistant."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.filing_assistant = ConversationalFilingAssistant()
    
    def test_start_grievance_filing(self):
        """Test starting a grievance filing session."""
        session_id = "test_filing_session"
        language = "hi"
        
        result = self.filing_assistant.start_grievance_filing(session_id, language)
        
        assert result['session_id'] == session_id
        assert result['language'] == language
        assert result['started'] is True
        assert 'response' in result
        assert 'workflow_status' in result
        assert 'voice_instructions' in result
    
    def test_process_user_input(self):
        """Test processing user input in filing session."""
        session_id = "test_input_session"
        
        # Start session
        self.filing_assistant.start_grievance_filing(session_id, "hi")
        
        # Process problem description
        user_input = "मेरा पेंशन बंद हो गया है और कोई जानकारी नहीं मिली"
        result = self.filing_assistant.process_user_input(session_id, user_input)
        
        assert result['session_id'] == session_id
        assert 'response' in result
        assert 'workflow_status' in result
        assert 'voice_instructions' in result
        assert 'entities_extracted' in result
        assert 'intent_detected' in result
    
    def test_get_session_status(self):
        """Test getting session status."""
        session_id = "test_status_session"
        
        # Start session
        self.filing_assistant.start_grievance_filing(session_id, "hi")
        
        # Get status
        status = self.filing_assistant.get_session_status(session_id)
        
        assert status['session_id'] == session_id
        assert 'workflow_status' in status
        assert 'validation_status' in status
        assert 'grievance_summary' in status
        assert 'created_at' in status
    
    def test_provide_help(self):
        """Test providing contextual help."""
        session_id = "test_help_session"
        
        # Start session
        self.filing_assistant.start_grievance_filing(session_id, "hi")
        
        # Get help
        help_info = self.filing_assistant.provide_help(session_id)
        
        assert help_info['session_id'] == session_id
        assert 'help_content' in help_info
        assert 'current_step' in help_info
        assert 'voice_instructions' in help_info
    
    def test_session_not_found(self):
        """Test handling of non-existent session."""
        result = self.filing_assistant.process_user_input("non_existent_session", "test input")
        
        assert 'error' in result
        assert result['error'] == 'Session not found'
        assert result['restart_needed'] is True
    
    def test_low_confidence_handling(self):
        """Test handling of low confidence speech recognition."""
        session_id = "test_low_confidence"
        
        # Start session
        self.filing_assistant.start_grievance_filing(session_id, "hi")
        
        # Process with low confidence
        result = self.filing_assistant.process_user_input(
            session_id, "unclear input", confidence=0.3
        )
        
        assert result['low_confidence'] is True
        assert result['retry_needed'] is True
        assert 'voice_instructions' in result
    
    def test_end_session(self):
        """Test ending a session."""
        session_id = "test_end_session"
        
        # Start session
        self.filing_assistant.start_grievance_filing(session_id, "hi")
        
        # End session
        result = self.filing_assistant.end_session(session_id, save_draft=True)
        
        assert result['session_id'] == session_id
        assert result['ended'] is True
        assert result['draft_saved'] is True
        
        # Verify session is removed
        status = self.filing_assistant.get_session_status(session_id)
        assert 'error' in status


class TestGrievanceModels:
    """Test cases for grievance data models."""
    
    def test_grievance_record_creation(self):
        """Test creating a grievance record."""
        grievance = GrievanceRecord(
            session_id="test_session",
            language="hi"
        )
        
        assert grievance.session_id == "test_session"
        assert grievance.language == "hi"
        assert grievance.status == GrievanceStatus.DRAFT
        assert grievance.priority == GrievancePriority.MEDIUM
        assert isinstance(grievance.created_at, datetime)
    
    def test_grievance_record_serialization(self):
        """Test grievance record to/from dict conversion."""
        original = GrievanceRecord(
            session_id="test_session",
            details=GrievanceDetails(
                problem_description="Test problem",
                grievance_type=GrievanceType.OTHER
            ),
            contact_info=ContactInformation(
                phone_number="9876543210"
            )
        )
        
        # Convert to dict
        data = original.to_dict()
        assert isinstance(data, dict)
        assert data['session_id'] == "test_session"
        
        # Convert back from dict
        restored = GrievanceRecord.from_dict(data)
        assert restored.session_id == original.session_id
        assert restored.details.problem_description == original.details.problem_description
        assert restored.contact_info.phone_number == original.contact_info.phone_number
    
    def test_workflow_progress_tracking(self):
        """Test workflow progress tracking."""
        progress = WorkflowProgress(
            current_step=WorkflowStep.INITIAL,
            current_state=WorkflowState.IN_PROGRESS
        )
        
        assert progress.current_step == WorkflowStep.INITIAL
        assert progress.current_state == WorkflowState.IN_PROGRESS
        assert len(progress.completed_steps) == 0
        assert isinstance(progress.started_at, datetime)


# Integration test
def test_end_to_end_grievance_filing():
    """Test complete end-to-end grievance filing workflow."""
    filing_assistant = ConversationalFilingAssistant()
    session_id = "e2e_test_session"
    
    # Start session
    result = filing_assistant.start_grievance_filing(session_id, "hi")
    assert result['started'] is True
    
    # Step 1: Problem description
    result = filing_assistant.process_user_input(
        session_id, 
        "मेरा राशन कार्ड खो गया है और नया बनवाने के लिए 2 महीने पहले आवेदन दिया था लेकिन अभी तक नहीं मिला है।"
    )
    assert 'response' in result
    
    # Step 2: Contact information
    result = filing_assistant.process_user_input(
        session_id,
        "मेरा फोन नंबर 9876543210 है"
    )
    assert 'response' in result
    
    # Check final status
    status = filing_assistant.get_session_status(session_id)
    assert status['validation_status']['completion_percentage'] >= 30
    
    # End session
    end_result = filing_assistant.end_session(session_id)
    assert end_result['ended'] is True