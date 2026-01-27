"""
Data models for grievance management system.

This module defines the data structures used for grievance filing,
tracking, and management across the system.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from uuid import UUID, uuid4


class GrievanceType(Enum):
    """Types of grievances that can be filed."""
    PENSION_ISSUE = "pension_issue"
    RATION_CARD_ISSUE = "ration_card_issue"
    CERTIFICATE_DELAY = "certificate_delay"
    SUBSIDY_DELAY = "subsidy_delay"
    CORRUPTION_COMPLAINT = "corruption_complaint"
    SERVICE_DENIAL = "service_denial"
    DOCUMENT_ISSUE = "document_issue"
    SCHEME_RELATED = "scheme_related"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


class GrievancePriority(Enum):
    """Priority levels for grievances."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class GrievanceStatus(Enum):
    """Status of grievance processing."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    UNDER_REVIEW = "under_review"
    INVESTIGATING = "investigating"
    PENDING_DOCUMENTS = "pending_documents"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"


class WorkflowStep(Enum):
    """Steps in the grievance filing workflow."""
    INITIAL = "initial"
    PROBLEM_DESCRIPTION = "problem_description"
    CATEGORY_SELECTION = "category_selection"
    CONTACT_COLLECTION = "contact_collection"
    DOCUMENT_COLLECTION = "document_collection"
    VALIDATION = "validation"
    CONFIRMATION = "confirmation"
    SUBMISSION = "submission"
    COMPLETED = "completed"


class WorkflowState(Enum):
    """States of the workflow process."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_INPUT = "waiting_for_input"
    VALIDATING = "validating"
    READY_TO_SUBMIT = "ready_to_submit"
    SUBMITTING = "submitting"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ContactInformation:
    """Contact information for grievance filing."""
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    preferred_contact_method: str = "phone"  # phone, email, sms
    preferred_language: str = "hi"


@dataclass
class DocumentReference:
    """Reference to a document related to the grievance."""
    document_type: str
    document_number: Optional[str] = None
    issuing_authority: Optional[str] = None
    issue_date: Optional[date] = None
    is_required: bool = False
    is_available: bool = False
    file_path: Optional[str] = None


@dataclass
class GrievanceDetails:
    """Detailed information about the grievance."""
    problem_description: str
    grievance_type: GrievanceType
    affected_service: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    incident_date: Optional[date] = None
    previous_complaint_reference: Optional[str] = None
    expected_resolution: Optional[str] = None
    urgency_reason: Optional[str] = None


@dataclass
class ValidationError:
    """Validation error information."""
    field: str
    message: str
    severity: str = "error"  # error, warning, info
    suggestion: Optional[str] = None


@dataclass
class GrievanceValidationResult:
    """Result of grievance validation."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    missing_required_fields: List[str] = field(default_factory=list)
    completion_percentage: float = 0.0


@dataclass
class GrievanceSubmissionResult:
    """Result of grievance submission."""
    success: bool
    reference_number: Optional[str] = None
    submission_date: Optional[datetime] = None
    expected_resolution_date: Optional[date] = None
    assigned_officer: Optional[str] = None
    department: Optional[str] = None
    error_message: Optional[str] = None
    next_steps: List[str] = field(default_factory=list)


@dataclass
class WorkflowProgress:
    """Progress tracking for grievance workflow."""
    current_step: WorkflowStep
    current_state: WorkflowState
    completed_steps: List[WorkflowStep] = field(default_factory=list)
    required_information: List[str] = field(default_factory=list)
    collected_information: Dict[str, Any] = field(default_factory=dict)
    validation_results: Optional[GrievanceValidationResult] = None
    step_history: List[Dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class GrievanceRecord:
    """Complete grievance record."""
    # Basic identification
    id: UUID = field(default_factory=uuid4)
    reference_number: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Grievance information
    details: Optional[GrievanceDetails] = None
    contact_info: Optional[ContactInformation] = None
    documents: List[DocumentReference] = field(default_factory=list)
    
    # Status and workflow
    status: GrievanceStatus = GrievanceStatus.DRAFT
    priority: GrievancePriority = GrievancePriority.MEDIUM
    workflow_progress: Optional[WorkflowProgress] = None
    
    # Submission and tracking
    submission_result: Optional[GrievanceSubmissionResult] = None
    government_reference: Optional[str] = None
    assigned_department: Optional[str] = None
    assigned_officer: Optional[str] = None
    
    # Timeline
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Metadata
    language: str = "hi"
    source_channel: str = "voice"  # voice, web, mobile
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert grievance record to dictionary format."""
        return {
            'id': str(self.id),
            'reference_number': self.reference_number,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'details': self.details.__dict__ if self.details else None,
            'contact_info': self.contact_info.__dict__ if self.contact_info else None,
            'documents': [doc.__dict__ for doc in self.documents],
            'status': self.status.value,
            'priority': self.priority.value,
            'workflow_progress': self.workflow_progress.__dict__ if self.workflow_progress else None,
            'submission_result': self.submission_result.__dict__ if self.submission_result else None,
            'government_reference': self.government_reference,
            'assigned_department': self.assigned_department,
            'assigned_officer': self.assigned_officer,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'language': self.language,
            'source_channel': self.source_channel,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GrievanceRecord':
        """Create grievance record from dictionary format."""
        # Parse details
        details = None
        if data.get('details'):
            details_dict = data['details']
            details = GrievanceDetails(
                problem_description=details_dict.get('problem_description', ''),
                grievance_type=GrievanceType(details_dict.get('grievance_type', 'other')),
                affected_service=details_dict.get('affected_service'),
                department=details_dict.get('department'),
                location=details_dict.get('location'),
                incident_date=datetime.fromisoformat(details_dict['incident_date']).date() if details_dict.get('incident_date') else None,
                previous_complaint_reference=details_dict.get('previous_complaint_reference'),
                expected_resolution=details_dict.get('expected_resolution'),
                urgency_reason=details_dict.get('urgency_reason')
            )
        
        # Parse contact info
        contact_info = None
        if data.get('contact_info'):
            contact_dict = data['contact_info']
            contact_info = ContactInformation(**contact_dict)
        
        # Parse documents
        documents = []
        for doc_dict in data.get('documents', []):
            doc = DocumentReference(
                document_type=doc_dict['document_type'],
                document_number=doc_dict.get('document_number'),
                issuing_authority=doc_dict.get('issuing_authority'),
                issue_date=datetime.fromisoformat(doc_dict['issue_date']).date() if doc_dict.get('issue_date') else None,
                is_required=doc_dict.get('is_required', False),
                is_available=doc_dict.get('is_available', False),
                file_path=doc_dict.get('file_path')
            )
            documents.append(doc)
        
        # Parse workflow progress
        workflow_progress = None
        if data.get('workflow_progress'):
            progress_dict = data['workflow_progress']
            workflow_progress = WorkflowProgress(
                current_step=WorkflowStep(progress_dict.get('current_step', 'initial')),
                current_state=WorkflowState(progress_dict.get('current_state', 'not_started')),
                completed_steps=[WorkflowStep(step) for step in progress_dict.get('completed_steps', [])],
                required_information=progress_dict.get('required_information', []),
                collected_information=progress_dict.get('collected_information', {}),
                validation_results=None,  # Would need to parse this too
                step_history=progress_dict.get('step_history', []),
                started_at=datetime.fromisoformat(progress_dict['started_at']) if progress_dict.get('started_at') else datetime.now(),
                last_updated=datetime.fromisoformat(progress_dict['last_updated']) if progress_dict.get('last_updated') else datetime.now()
            )
        
        # Parse submission result
        submission_result = None
        if data.get('submission_result'):
            result_dict = data['submission_result']
            submission_result = GrievanceSubmissionResult(**result_dict)
        
        return cls(
            id=UUID(data['id']) if data.get('id') else uuid4(),
            reference_number=data.get('reference_number'),
            user_id=data.get('user_id'),
            session_id=data.get('session_id'),
            details=details,
            contact_info=contact_info,
            documents=documents,
            status=GrievanceStatus(data.get('status', 'draft')),
            priority=GrievancePriority(data.get('priority', 'medium')),
            workflow_progress=workflow_progress,
            submission_result=submission_result,
            government_reference=data.get('government_reference'),
            assigned_department=data.get('assigned_department'),
            assigned_officer=data.get('assigned_officer'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now(),
            submitted_at=datetime.fromisoformat(data['submitted_at']) if data.get('submitted_at') else None,
            resolved_at=datetime.fromisoformat(data['resolved_at']) if data.get('resolved_at') else None,
            language=data.get('language', 'hi'),
            source_channel=data.get('source_channel', 'voice'),
            metadata=data.get('metadata', {})
        )