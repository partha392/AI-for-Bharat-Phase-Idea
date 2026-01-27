"""
Workflow management for conversational grievance filing.

This module manages the step-by-step workflow for grievance filing,
including state transitions, progress tracking, and flow control.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

from .models import (
    GrievanceRecord, WorkflowStep, WorkflowState, WorkflowProgress,
    GrievanceDetails, ContactInformation, GrievanceType, GrievancePriority
)
from .validator import GrievanceValidator
from ..language.intent_classifier import ServiceIntent
from ..language.entity_extractor import Entity, EntityType
from ..core.exceptions import WorkflowError

logger = logging.getLogger(__name__)


class WorkflowTransition(Enum):
    """Possible workflow transitions."""
    NEXT = "next"
    BACK = "back"
    REPEAT = "repeat"
    SKIP = "skip"
    RESTART = "restart"
    COMPLETE = "complete"


class GrievanceWorkflowManager:
    """
    Manages the conversational workflow for grievance filing.
    
    Provides step-by-step guidance, state management, and progress tracking
    for the grievance filing process.
    """
    
    def __init__(self, validator: Optional[GrievanceValidator] = None):
        """Initialize the workflow manager."""
        self.validator = validator or GrievanceValidator()
        self._workflow_definitions = self._load_workflow_definitions()
        self._step_handlers = self._initialize_step_handlers()
        logger.info("GrievanceWorkflowManager initialized")
    
    def start_workflow(self, session_id: str, language: str = 'hi') -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """
        Start a new grievance filing workflow.
        
        Args:
            session_id: Session identifier
            language: User's preferred language
            
        Returns:
            Tuple of (grievance_record, workflow_response)
        """
        try:
            # Create new grievance record
            grievance = GrievanceRecord(
                session_id=session_id,
                language=language,
                workflow_progress=WorkflowProgress(
                    current_step=WorkflowStep.INITIAL,
                    current_state=WorkflowState.IN_PROGRESS
                )
            )
            
            # Generate initial response
            response = self._generate_step_response(grievance, WorkflowStep.INITIAL)
            
            # Update workflow progress
            self._update_workflow_progress(grievance, WorkflowStep.PROBLEM_DESCRIPTION, WorkflowState.WAITING_FOR_INPUT)
            
            logger.info("Started grievance workflow for session %s", session_id)
            
            return grievance, response
            
        except Exception as e:
            logger.error("Failed to start workflow for session %s: %s", session_id, str(e))
            raise WorkflowError(f"Failed to start workflow: {str(e)}")
    
    def process_user_input(self, grievance: GrievanceRecord, user_input: str, 
                          intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """
        Process user input and advance the workflow.
        
        Args:
            grievance: Current grievance record
            user_input: User's input text
            intent: Classified intent
            entities: Extracted entities
            
        Returns:
            Tuple of (updated_grievance_record, workflow_response)
        """
        try:
            current_step = grievance.workflow_progress.current_step
            
            # Handle the current step
            handler = self._step_handlers.get(current_step)
            if not handler:
                raise WorkflowError(f"No handler found for step: {current_step}")
            
            # Process the step
            updated_grievance, step_result = handler(grievance, user_input, intent, entities)
            
            # Determine next action based on step result
            next_action = self._determine_next_action(updated_grievance, step_result)
            
            # Execute the next action
            response = self._execute_workflow_action(updated_grievance, next_action, step_result)
            
            # Update step history
            self._add_to_step_history(updated_grievance, current_step, user_input, step_result)
            
            logger.info("Processed workflow step %s for session %s", 
                       current_step.value, grievance.session_id)
            
            return updated_grievance, response
            
        except Exception as e:
            logger.error("Failed to process workflow input for session %s: %s", 
                        grievance.session_id, str(e))
            
            # Return error response
            error_response = self._generate_error_response(grievance, str(e))
            return grievance, error_response
    
    def get_workflow_status(self, grievance: GrievanceRecord) -> Dict[str, Any]:
        """
        Get current workflow status and progress.
        
        Args:
            grievance: Grievance record
            
        Returns:
            Dictionary with workflow status information
        """
        progress = grievance.workflow_progress
        validation_result = self.validator.validate_grievance(grievance)
        
        return {
            'current_step': progress.current_step.value,
            'current_state': progress.current_state.value,
            'completed_steps': [step.value for step in progress.completed_steps],
            'completion_percentage': validation_result.completion_percentage,
            'missing_fields': validation_result.missing_required_fields,
            'is_ready_to_submit': validation_result.is_valid,
            'total_steps': len(WorkflowStep) - 1,  # Exclude COMPLETED
            'estimated_remaining_time': self._estimate_remaining_time(progress)
        }
    
    def _handle_initial_step(self, grievance: GrievanceRecord, user_input: str, 
                           intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """Handle the initial step of the workflow."""
        # This is just the welcome step, move to problem description
        return grievance, {
            'success': True,
            'next_step': WorkflowStep.PROBLEM_DESCRIPTION,
            'collected_data': {}
        }
    
    def _handle_problem_description_step(self, grievance: GrievanceRecord, user_input: str,
                                       intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """Handle problem description collection."""
        # Extract problem description from user input
        problem_description = user_input.strip()
        
        # Validate the description
        validation_errors = self.validator.validate_field('problem_description', problem_description)
        
        if validation_errors:
            return grievance, {
                'success': False,
                'errors': validation_errors,
                'retry_needed': True
            }
        
        # Create or update grievance details
        if not grievance.details:
            grievance.details = GrievanceDetails(
                problem_description=problem_description,
                grievance_type=GrievanceType.OTHER  # Will be determined in next step
            )
        else:
            grievance.details.problem_description = problem_description
        
        # Extract additional information from entities
        collected_data = {'problem_description': problem_description}
        
        for entity in entities:
            if entity.type == EntityType.LOCATION:
                grievance.details.location = entity.value
                collected_data['location'] = entity.value
            elif entity.type == EntityType.GOVERNMENT_SERVICE:
                grievance.details.affected_service = entity.value
                collected_data['affected_service'] = entity.value
            elif entity.type == EntityType.DATE:
                # This could be incident date
                collected_data['potential_incident_date'] = entity.value
        
        return grievance, {
            'success': True,
            'next_step': WorkflowStep.CATEGORY_SELECTION,
            'collected_data': collected_data
        }
    
    def _handle_category_selection_step(self, grievance: GrievanceRecord, user_input: str,
                                      intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """Handle grievance category selection."""
        # Try to determine category from user input and entities
        category = self._determine_grievance_category(user_input, entities, grievance.details)
        
        if category:
            grievance.details.grievance_type = category
            
            # Set priority based on category
            grievance.priority = self._determine_priority(category, grievance.details)
            
            return grievance, {
                'success': True,
                'next_step': WorkflowStep.CONTACT_COLLECTION,
                'collected_data': {
                    'grievance_type': category.value,
                    'priority': grievance.priority.value
                }
            }
        else:
            # Need to ask for clarification
            return grievance, {
                'success': False,
                'clarification_needed': True,
                'available_categories': [cat.value for cat in GrievanceType]
            }
    
    def _handle_contact_collection_step(self, grievance: GrievanceRecord, user_input: str,
                                      intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """Handle contact information collection."""
        # Initialize contact info if not exists
        if not grievance.contact_info:
            grievance.contact_info = ContactInformation(preferred_language=grievance.language)
        
        collected_data = {}
        
        # Extract contact information from entities
        for entity in entities:
            if entity.type == EntityType.PHONE_NUMBER:
                # Validate phone number
                validation_errors = self.validator.validate_field('phone_number', entity.value)
                if not validation_errors:
                    grievance.contact_info.phone_number = entity.normalized_value or entity.value
                    collected_data['phone_number'] = entity.value
                else:
                    return grievance, {
                        'success': False,
                        'errors': validation_errors,
                        'retry_needed': True
                    }
            
            elif entity.type == EntityType.EMAIL:
                # Validate email
                validation_errors = self.validator.validate_field('email', entity.value)
                if not validation_errors:
                    grievance.contact_info.email = entity.normalized_value or entity.value
                    collected_data['email'] = entity.value
                else:
                    return grievance, {
                        'success': False,
                        'errors': validation_errors,
                        'retry_needed': True
                    }
            
            elif entity.type == EntityType.ADDRESS:
                grievance.contact_info.address = entity.value
                collected_data['address'] = entity.value
        
        # Check if we have at least one contact method
        has_contact = (grievance.contact_info.phone_number or grievance.contact_info.email)
        
        if has_contact:
            return grievance, {
                'success': True,
                'next_step': WorkflowStep.DOCUMENT_COLLECTION,
                'collected_data': collected_data
            }
        else:
            return grievance, {
                'success': False,
                'missing_contact': True,
                'retry_needed': True
            }
    
    def _handle_document_collection_step(self, grievance: GrievanceRecord, user_input: str,
                                       intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """Handle document information collection."""
        # This is optional step - user can skip or provide document info
        user_input_lower = user_input.lower()
        
        # Check if user wants to skip documents
        skip_keywords = ['skip', 'no documents', 'none', 'छोड़ें', 'नहीं', 'कोई नहीं']
        if any(keyword in user_input_lower for keyword in skip_keywords):
            return grievance, {
                'success': True,
                'next_step': WorkflowStep.VALIDATION,
                'collected_data': {'documents_skipped': True}
            }
        
        # Extract document information from entities
        collected_data = {}
        
        for entity in entities:
            if entity.type == EntityType.DOCUMENT_TYPE:
                # Add document reference
                from .models import DocumentReference
                doc_ref = DocumentReference(
                    document_type=entity.value,
                    is_available=True  # Assume available if mentioned
                )
                grievance.documents.append(doc_ref)
                collected_data['document_added'] = entity.value
            
            elif entity.type == EntityType.REFERENCE_NUMBER:
                # This could be a document number
                if grievance.documents:
                    grievance.documents[-1].document_number = entity.value
                    collected_data['document_number'] = entity.value
        
        return grievance, {
            'success': True,
            'next_step': WorkflowStep.VALIDATION,
            'collected_data': collected_data
        }
    
    def _handle_validation_step(self, grievance: GrievanceRecord, user_input: str,
                              intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """Handle validation and confirmation."""
        # Validate the complete grievance
        validation_result = self.validator.validate_grievance(grievance)
        
        if validation_result.is_valid:
            return grievance, {
                'success': True,
                'next_step': WorkflowStep.CONFIRMATION,
                'validation_result': validation_result,
                'ready_to_submit': True
            }
        else:
            return grievance, {
                'success': False,
                'validation_result': validation_result,
                'corrections_needed': True
            }
    
    def _handle_confirmation_step(self, grievance: GrievanceRecord, user_input: str,
                                intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """Handle final confirmation."""
        user_input_lower = user_input.lower()
        
        # Check for confirmation keywords
        confirm_keywords = ['yes', 'confirm', 'submit', 'हाँ', 'जी हाँ', 'सबमिट', 'भेजें']
        cancel_keywords = ['no', 'cancel', 'नहीं', 'रद्द', 'बंद']
        
        if any(keyword in user_input_lower for keyword in confirm_keywords):
            return grievance, {
                'success': True,
                'next_step': WorkflowStep.SUBMISSION,
                'confirmed': True
            }
        elif any(keyword in user_input_lower for keyword in cancel_keywords):
            return grievance, {
                'success': False,
                'cancelled': True,
                'restart_needed': True
            }
        else:
            return grievance, {
                'success': False,
                'clarification_needed': True,
                'confirmation_required': True
            }
    
    def _handle_submission_step(self, grievance: GrievanceRecord, user_input: str,
                              intent: ServiceIntent, entities: List[Entity]) -> Tuple[GrievanceRecord, Dict[str, Any]]:
        """Handle grievance submission."""
        # Integrate with government systems
        try:
            # Import integration service
            from ..integration.integration_service import GovernmentIntegrationService
            from ..integration.config_loader import GovernmentPortalConfigLoader
            
            # Load integration configuration
            config_loader = GovernmentPortalConfigLoader()
            integration_config = config_loader.load_integration_config()
            
            # Submit to government systems
            async def submit_to_government():
                async with GovernmentIntegrationService(integration_config) as integration_service:
                    return await integration_service.submit_grievance(grievance)
            
            # Run async submission
            import asyncio
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, we need to use a different approach
                    # For now, fall back to simulation
                    raise RuntimeError("Event loop is running")
                else:
                    integration_result = loop.run_until_complete(submit_to_government())
            except RuntimeError:
                # Event loop is already running, use thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, submit_to_government())
                    integration_result = future.result(timeout=60)
            
            if integration_result.success:
                # Update grievance with integration result
                from .models import GrievanceSubmissionResult, GrievanceStatus
                
                submission_result = GrievanceSubmissionResult(
                    success=True,
                    reference_number=integration_result.reference_number,
                    submission_date=datetime.now(),
                    assigned_officer=integration_result.response_data.get("assigned_officer") if integration_result.response_data else None,
                    department=integration_result.response_data.get("department") if integration_result.response_data else None,
                    next_steps=[
                        "Your grievance has been submitted successfully to government portal",
                        f"Reference number: {integration_result.reference_number}",
                        "You will receive SMS/email confirmation shortly",
                        "Track status using reference number",
                        "Expected response within 15 working days"
                    ]
                )
                
                # Update grievance record
                grievance.reference_number = integration_result.reference_number
                grievance.government_reference = integration_result.reference_number
                grievance.submission_result = submission_result
                grievance.status = GrievanceStatus.SUBMITTED
                grievance.submitted_at = datetime.now()
                
                # Add integration metadata
                grievance.metadata.update({
                    "integration_portal": integration_result.portal_id,
                    "integration_status": integration_result.status.value if integration_result.status else None,
                    "submission_time": integration_result.execution_time
                })
                
                return grievance, {
                    'success': True,
                    'next_step': WorkflowStep.COMPLETED,
                    'submission_result': submission_result,
                    'completed': True,
                    'integration_result': integration_result.to_dict()
                }
            else:
                # Integration failed, but still create a local record
                logger.warning(f"Government integration failed: {integration_result.message}")
                
                from .models import GrievanceSubmissionResult, GrievanceStatus
                import uuid
                
                # Generate local reference number
                reference_number = f"LOCAL{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                
                submission_result = GrievanceSubmissionResult(
                    success=True,
                    reference_number=reference_number,
                    submission_date=datetime.now(),
                    next_steps=[
                        "Your grievance has been recorded locally",
                        f"Local reference number: {reference_number}",
                        "We will attempt to submit to government portal automatically",
                        "You will be notified once submitted successfully",
                        "Track status using reference number"
                    ]
                )
                
                # Update grievance record
                grievance.reference_number = reference_number
                grievance.submission_result = submission_result
                grievance.status = GrievanceStatus.SUBMITTED
                grievance.submitted_at = datetime.now()
                
                # Add integration failure metadata
                grievance.metadata.update({
                    "integration_failed": True,
                    "integration_error": integration_result.message,
                    "integration_error_code": integration_result.error_code,
                    "retry_queued": True
                })
                
                return grievance, {
                    'success': True,
                    'next_step': WorkflowStep.COMPLETED,
                    'submission_result': submission_result,
                    'completed': True,
                    'integration_warning': integration_result.message
                }
                
        except Exception as e:
            # Integration completely failed, fall back to local submission
            logger.error(f"Government integration error: {e}")
            
            from .models import GrievanceSubmissionResult, GrievanceStatus
            import uuid
            
            # Generate local reference number
            reference_number = f"LOCAL{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
            
            submission_result = GrievanceSubmissionResult(
                success=True,
                reference_number=reference_number,
                submission_date=datetime.now(),
                next_steps=[
                    "Your grievance has been recorded locally",
                    f"Local reference number: {reference_number}",
                    "Technical issue prevented immediate government submission",
                    "We will retry submission automatically",
                    "You will be notified once submitted successfully"
                ]
            )
            
            # Update grievance record
            grievance.reference_number = reference_number
            grievance.submission_result = submission_result
            grievance.status = GrievanceStatus.SUBMITTED
            grievance.submitted_at = datetime.now()
            
            # Add error metadata
            grievance.metadata.update({
                "integration_error": str(e),
                "fallback_submission": True,
                "retry_needed": True
            })
            
            return grievance, {
                'success': True,
                'next_step': WorkflowStep.COMPLETED,
                'submission_result': submission_result,
                'completed': True,
                'fallback_used': True
            }
    
    def _determine_grievance_category(self, user_input: str, entities: List[Entity], 
                                    details: Optional[GrievanceDetails]) -> Optional[GrievanceType]:
        """Determine grievance category from user input."""
        user_input_lower = user_input.lower()
        
        # Category keywords mapping
        category_keywords = {
            GrievanceType.PENSION_ISSUE: ['pension', 'पेंशन', 'retirement', 'सेवानिवृत्ति'],
            GrievanceType.RATION_CARD_ISSUE: ['ration', 'राशन', 'food', 'खाद्य'],
            GrievanceType.CERTIFICATE_DELAY: ['certificate', 'प्रमाणपत्र', 'document delay', 'दस्तावेज़'],
            GrievanceType.SUBSIDY_DELAY: ['subsidy', 'सब्सिडी', 'allowance', 'भत्ता'],
            GrievanceType.CORRUPTION_COMPLAINT: ['corruption', 'भ्रष्टाचार', 'bribe', 'रिश्वत'],
            GrievanceType.SERVICE_DENIAL: ['denied', 'refused', 'मना', 'इनकार'],
            GrievanceType.DOCUMENT_ISSUE: ['document', 'दस्तावेज़', 'paper', 'कागज़'],
            GrievanceType.SCHEME_RELATED: ['scheme', 'योजना', 'program', 'कार्यक्रम'],
            GrievanceType.INFRASTRUCTURE: ['road', 'water', 'electricity', 'सड़क', 'पानी', 'बिजली']
        }
        
        # Check for category keywords
        for category, keywords in category_keywords.items():
            if any(keyword in user_input_lower for keyword in keywords):
                return category
        
        # Check entities for government services
        for entity in entities:
            if entity.type == EntityType.GOVERNMENT_SERVICE:
                service_lower = entity.value.lower()
                for category, keywords in category_keywords.items():
                    if any(keyword in service_lower for keyword in keywords):
                        return category
        
        # Check problem description if available
        if details and details.problem_description:
            desc_lower = details.problem_description.lower()
            for category, keywords in category_keywords.items():
                if any(keyword in desc_lower for keyword in keywords):
                    return category
        
        return None
    
    def _determine_priority(self, category: GrievanceType, details: Optional[GrievanceDetails]) -> GrievancePriority:
        """Determine priority based on category and details."""
        # High priority categories
        high_priority_categories = [
            GrievanceType.CORRUPTION_COMPLAINT,
            GrievanceType.SERVICE_DENIAL
        ]
        
        if category in high_priority_categories:
            return GrievancePriority.HIGH
        
        # Check for urgency keywords in description
        if details and details.problem_description:
            urgency_keywords = ['urgent', 'emergency', 'immediate', 'तुरंत', 'आपातकाल']
            if any(keyword in details.problem_description.lower() for keyword in urgency_keywords):
                return GrievancePriority.HIGH
        
        return GrievancePriority.MEDIUM
    
    def _determine_next_action(self, grievance: GrievanceRecord, step_result: Dict[str, Any]) -> WorkflowTransition:
        """Determine the next workflow action based on step result."""
        if step_result.get('success'):
            if step_result.get('completed'):
                return WorkflowTransition.COMPLETE
            else:
                return WorkflowTransition.NEXT
        elif step_result.get('retry_needed') or step_result.get('clarification_needed'):
            return WorkflowTransition.REPEAT
        elif step_result.get('restart_needed'):
            return WorkflowTransition.RESTART
        else:
            return WorkflowTransition.REPEAT
    
    def _execute_workflow_action(self, grievance: GrievanceRecord, action: WorkflowTransition,
                               step_result: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the determined workflow action."""
        if action == WorkflowTransition.NEXT:
            next_step = step_result.get('next_step')
            if next_step:
                self._update_workflow_progress(grievance, next_step, WorkflowState.WAITING_FOR_INPUT)
                return self._generate_step_response(grievance, next_step, step_result)
        
        elif action == WorkflowTransition.COMPLETE:
            self._update_workflow_progress(grievance, WorkflowStep.COMPLETED, WorkflowState.COMPLETED)
            return self._generate_completion_response(grievance, step_result)
        
        elif action == WorkflowTransition.REPEAT:
            return self._generate_retry_response(grievance, step_result)
        
        elif action == WorkflowTransition.RESTART:
            return self._generate_restart_response(grievance)
        
        # Default fallback
        return self._generate_step_response(grievance, grievance.workflow_progress.current_step)
    
    def _generate_step_response(self, grievance: GrievanceRecord, step: WorkflowStep,
                              step_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate response for a workflow step."""
        language = grievance.language
        
        responses = {
            'hi': {
                WorkflowStep.INITIAL: {
                    'message': 'नमस्ते! मैं आपकी शिकायत दर्ज करने में सहायता करूंगा। कृपया अपनी समस्या का विस्तार से वर्णन करें।',
                    'prompt': 'अपनी समस्या बताएं:'
                },
                WorkflowStep.PROBLEM_DESCRIPTION: {
                    'message': 'कृपया अपनी समस्या का विस्तार से वर्णन करें। जितनी अधिक जानकारी आप देंगे, उतनी बेहतर सहायता मिल सकेगी।',
                    'prompt': 'समस्या का विवरण:'
                },
                WorkflowStep.CATEGORY_SELECTION: {
                    'message': 'धन्यवाद। अब मुझे बताएं कि यह किस प्रकार की समस्या है?',
                    'prompt': 'समस्या का प्रकार चुनें:'
                },
                WorkflowStep.CONTACT_COLLECTION: {
                    'message': 'अब मुझे आपकी संपर्क जानकारी चाहिए। कृपया अपना फोन नंबर या ईमेल पता बताएं।',
                    'prompt': 'संपर्क जानकारी:'
                },
                WorkflowStep.DOCUMENT_COLLECTION: {
                    'message': 'क्या आपके पास इस समस्या से संबंधित कोई दस्तावेज़ हैं? यदि हाँ, तो बताएं। यदि नहीं, तो "छोड़ें" कहें।',
                    'prompt': 'दस्तावेज़ की जानकारी:'
                },
                WorkflowStep.VALIDATION: {
                    'message': 'मैं आपकी जानकारी की जांच कर रहा हूं...',
                    'prompt': 'कृपया प्रतीक्षा करें...'
                },
                WorkflowStep.CONFIRMATION: {
                    'message': 'आपकी शिकायत तैयार है। क्या आप इसे सबमिट करना चाहते हैं?',
                    'prompt': 'पुष्टि करें (हाँ/नहीं):'
                },
                WorkflowStep.SUBMISSION: {
                    'message': 'आपकी शिकायत सबमिट की जा रही है...',
                    'prompt': 'कृपया प्रतीक्षा करें...'
                }
            },
            'en': {
                WorkflowStep.INITIAL: {
                    'message': 'Hello! I will help you file your grievance. Please describe your problem in detail.',
                    'prompt': 'Describe your problem:'
                },
                WorkflowStep.PROBLEM_DESCRIPTION: {
                    'message': 'Please describe your problem in detail. The more information you provide, the better assistance you can receive.',
                    'prompt': 'Problem description:'
                },
                WorkflowStep.CATEGORY_SELECTION: {
                    'message': 'Thank you. Now please tell me what type of problem this is?',
                    'prompt': 'Select problem category:'
                },
                WorkflowStep.CONTACT_COLLECTION: {
                    'message': 'Now I need your contact information. Please provide your phone number or email address.',
                    'prompt': 'Contact information:'
                },
                WorkflowStep.DOCUMENT_COLLECTION: {
                    'message': 'Do you have any documents related to this problem? If yes, please mention them. If no, say "skip".',
                    'prompt': 'Document information:'
                },
                WorkflowStep.VALIDATION: {
                    'message': 'I am validating your information...',
                    'prompt': 'Please wait...'
                },
                WorkflowStep.CONFIRMATION: {
                    'message': 'Your grievance is ready. Do you want to submit it?',
                    'prompt': 'Confirm (yes/no):'
                },
                WorkflowStep.SUBMISSION: {
                    'message': 'Your grievance is being submitted...',
                    'prompt': 'Please wait...'
                }
            }
        }
        
        lang_responses = responses.get(language, responses['hi'])
        step_response = lang_responses.get(step, lang_responses[WorkflowStep.INITIAL])
        
        response = {
            'message': step_response['message'],
            'prompt': step_response['prompt'],
            'step': step.value,
            'state': grievance.workflow_progress.current_state.value,
            'requires_input': step != WorkflowStep.VALIDATION and step != WorkflowStep.SUBMISSION,
            'success': True  # Add success field
        }
        
        # Add step-specific information
        if step_result:
            if step_result.get('available_categories'):
                response['options'] = step_result['available_categories']
            if step_result.get('collected_data'):
                response['collected_data'] = step_result['collected_data']
        
        return response
    
    def _generate_completion_response(self, grievance: GrievanceRecord, step_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate completion response."""
        language = grievance.language
        submission_result = step_result.get('submission_result')
        
        if language == 'hi':
            message = f"बधाई हो! आपकी शिकायत सफलतापूर्वक दर्ज हो गई है।\n"
            if submission_result and submission_result.reference_number:
                message += f"संदर्भ संख्या: {submission_result.reference_number}\n"
                message += "कृपया इस संख्या को सुरक्षित रखें।"
        else:
            message = f"Congratulations! Your grievance has been successfully submitted.\n"
            if submission_result and submission_result.reference_number:
                message += f"Reference Number: {submission_result.reference_number}\n"
                message += "Please keep this number safe for future reference."
        
        return {
            'message': message,
            'step': WorkflowStep.COMPLETED.value,
            'state': WorkflowState.COMPLETED.value,
            'completed': True,
            'reference_number': submission_result.reference_number if submission_result else None,
            'next_steps': submission_result.next_steps if submission_result else []
        }
    
    def _generate_retry_response(self, grievance: GrievanceRecord, step_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate retry response for errors."""
        language = grievance.language
        errors = step_result.get('errors', [])
        
        if language == 'hi':
            message = "क्षमा करें, कुछ जानकारी सही नहीं है। कृपया दोबारा प्रयास करें।"
        else:
            message = "Sorry, there's an issue with the information provided. Please try again."
        
        if errors:
            error_messages = [error.message for error in errors]
            if language == 'hi':
                message += f"\nसमस्या: {', '.join(error_messages)}"
            else:
                message += f"\nIssues: {', '.join(error_messages)}"
        
        return {
            'message': message,
            'step': grievance.workflow_progress.current_step.value,
            'state': WorkflowState.WAITING_FOR_INPUT.value,
            'errors': errors,
            'retry_needed': True
        }
    
    def _generate_restart_response(self, grievance: GrievanceRecord) -> Dict[str, Any]:
        """Generate restart response."""
        language = grievance.language
        
        if language == 'hi':
            message = "कोई बात नहीं। आइए फिर से शुरू करते हैं।"
        else:
            message = "No problem. Let's start over."
        
        # Reset workflow
        grievance.workflow_progress = WorkflowProgress(
            current_step=WorkflowStep.INITIAL,
            current_state=WorkflowState.IN_PROGRESS
        )
        
        return {
            'message': message,
            'step': WorkflowStep.INITIAL.value,
            'state': WorkflowState.IN_PROGRESS.value,
            'restarted': True
        }
    
    def _generate_error_response(self, grievance: GrievanceRecord, error_message: str) -> Dict[str, Any]:
        """Generate error response."""
        language = grievance.language
        
        if language == 'hi':
            message = "क्षमा करें, तकनीकी समस्या के कारण आपकी शिकायत दर्ज नहीं हो सकी। कृपया बाद में पुनः प्रयास करें।"
        else:
            message = "Sorry, due to a technical issue, your grievance could not be processed. Please try again later."
        
        return {
            'message': message,
            'step': grievance.workflow_progress.current_step.value,
            'state': WorkflowState.ERROR.value,
            'error': True,
            'error_message': error_message
        }
    
    def _update_workflow_progress(self, grievance: GrievanceRecord, step: WorkflowStep, state: WorkflowState):
        """Update workflow progress."""
        progress = grievance.workflow_progress
        
        # Add current step to completed steps if moving forward
        if progress.current_step not in progress.completed_steps and step != progress.current_step:
            progress.completed_steps.append(progress.current_step)
        
        # Update current step and state
        progress.current_step = step
        progress.current_state = state
        progress.last_updated = datetime.now()
    
    def _add_to_step_history(self, grievance: GrievanceRecord, step: WorkflowStep, 
                           user_input: str, step_result: Dict[str, Any]):
        """Add entry to step history."""
        history_entry = {
            'step': step.value,
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'success': step_result.get('success', False),
            'collected_data': step_result.get('collected_data', {})
        }
        
        grievance.workflow_progress.step_history.append(history_entry)
    
    def _estimate_remaining_time(self, progress: WorkflowProgress) -> int:
        """Estimate remaining time in minutes."""
        total_steps = len(WorkflowStep) - 1  # Exclude COMPLETED
        completed_steps = len(progress.completed_steps)
        remaining_steps = total_steps - completed_steps
        
        # Estimate 2-3 minutes per step
        return remaining_steps * 2
    
    def _initialize_step_handlers(self) -> Dict[WorkflowStep, callable]:
        """Initialize step handler mapping."""
        return {
            WorkflowStep.INITIAL: self._handle_initial_step,
            WorkflowStep.PROBLEM_DESCRIPTION: self._handle_problem_description_step,
            WorkflowStep.CATEGORY_SELECTION: self._handle_category_selection_step,
            WorkflowStep.CONTACT_COLLECTION: self._handle_contact_collection_step,
            WorkflowStep.DOCUMENT_COLLECTION: self._handle_document_collection_step,
            WorkflowStep.VALIDATION: self._handle_validation_step,
            WorkflowStep.CONFIRMATION: self._handle_confirmation_step,
            WorkflowStep.SUBMISSION: self._handle_submission_step
        }
    
    def _load_workflow_definitions(self) -> Dict[str, Any]:
        """Load workflow definitions."""
        # This could be loaded from configuration files
        return {
            'default_workflow': {
                'steps': [step.value for step in WorkflowStep],
                'required_fields': ['problem_description', 'contact_info'],
                'optional_fields': ['documents', 'location', 'incident_date']
            }
        }