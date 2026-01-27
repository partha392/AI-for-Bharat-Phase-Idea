"""
Data models for government scheme management.

This module defines the data structures and enums used throughout
the scheme management system.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from uuid import UUID, uuid4


class SchemeCategory(Enum):
    """Government scheme categories."""
    AGRICULTURE = "agriculture"
    EDUCATION = "education"
    HEALTH = "health"
    HOUSING = "housing"
    EMPLOYMENT = "employment"
    SOCIAL_SECURITY = "social_security"
    RURAL_DEVELOPMENT = "rural_development"
    WOMEN_EMPOWERMENT = "women_empowerment"
    DISABILITY = "disability"
    SENIOR_CITIZEN = "senior_citizen"
    FINANCIAL_INCLUSION = "financial_inclusion"


class SchemeStatus(Enum):
    """Scheme status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class DataSource(Enum):
    """Data source types for scheme information."""
    GOVERNMENT_API = "government_api"
    WEB_SCRAPING = "web_scraping"
    MANUAL_ENTRY = "manual_entry"
    THIRD_PARTY_API = "third_party_api"


@dataclass
class EligibilityCriteria:
    """Eligibility criteria for a government scheme."""
    income_limit: Optional[int] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    location_type: Optional[str] = None  # 'rural', 'urban', 'both'
    gender: Optional[str] = None
    caste_category: Optional[List[str]] = None
    education_level: Optional[str] = None
    employment_status: Optional[str] = None
    disability_status: Optional[bool] = None
    marital_status: Optional[str] = None
    family_size: Optional[int] = None
    land_ownership: Optional[str] = None
    housing_status: Optional[str] = None
    additional_criteria: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemeBenefits:
    """Benefits provided by a government scheme."""
    financial_assistance: Optional[int] = None
    subsidy_percentage: Optional[float] = None
    loan_amount: Optional[int] = None
    interest_rate: Optional[float] = None
    insurance_coverage: Optional[int] = None
    training_provided: bool = False
    equipment_provided: bool = False
    description: str = ""
    additional_benefits: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplicationProcess:
    """Application process details for a scheme."""
    steps: List[str] = field(default_factory=list)
    required_documents: List[str] = field(default_factory=list)
    application_fee: Optional[int] = None
    processing_time_days: Optional[int] = None
    application_mode: List[str] = field(default_factory=list)  # 'online', 'offline', 'both'
    contact_details: Dict[str, str] = field(default_factory=dict)
    help_resources: List[str] = field(default_factory=list)


@dataclass
class SchemeMetadata:
    """Metadata for scheme tracking and management."""
    data_source: DataSource
    source_url: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    verification_status: str = "pending"  # 'verified', 'pending', 'failed'
    version: int = 1
    change_log: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    popularity_score: float = 0.0
    success_rate: float = 0.0


@dataclass
class GovernmentScheme:
    """Complete government scheme information."""
    # Basic identification
    id: UUID = field(default_factory=uuid4)
    scheme_id: str = ""
    name: str = ""
    name_hi: Optional[str] = None
    name_regional: Dict[str, str] = field(default_factory=dict)
    
    # Administrative details
    department: str = ""
    ministry: Optional[str] = None
    category: SchemeCategory = SchemeCategory.SOCIAL_SECURITY
    subcategory: Optional[str] = None
    
    # Descriptive information
    description: str = ""
    description_hi: Optional[str] = None
    description_regional: Dict[str, str] = field(default_factory=dict)
    
    # Scheme details
    eligibility_criteria: EligibilityCriteria = field(default_factory=EligibilityCriteria)
    benefits: SchemeBenefits = field(default_factory=SchemeBenefits)
    application_process: ApplicationProcess = field(default_factory=ApplicationProcess)
    
    # Geographic targeting
    target_states: List[str] = field(default_factory=list)
    target_districts: List[str] = field(default_factory=list)
    
    # Status and lifecycle
    status: SchemeStatus = SchemeStatus.ACTIVE
    launch_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # Performance metrics
    budget_allocated: Optional[Decimal] = None
    beneficiaries_target: Optional[int] = None
    beneficiaries_current: int = 0
    average_processing_days: Optional[int] = None
    
    # Metadata
    metadata: SchemeMetadata = field(default_factory=lambda: SchemeMetadata(DataSource.MANUAL_ENTRY))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert scheme to dictionary format."""
        return {
            'id': str(self.id),
            'scheme_id': self.scheme_id,
            'name': self.name,
            'name_hi': self.name_hi,
            'name_regional': self.name_regional,
            'department': self.department,
            'ministry': self.ministry,
            'category': self.category.value,
            'subcategory': self.subcategory,
            'description': self.description,
            'description_hi': self.description_hi,
            'description_regional': self.description_regional,
            'eligibility_criteria': self.eligibility_criteria.__dict__,
            'benefits': self.benefits.__dict__,
            'application_process': self.application_process.__dict__,
            'target_states': self.target_states,
            'target_districts': self.target_districts,
            'status': self.status.value,
            'launch_date': self.launch_date.isoformat() if self.launch_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'budget_allocated': float(self.budget_allocated) if self.budget_allocated else None,
            'beneficiaries_target': self.beneficiaries_target,
            'beneficiaries_current': self.beneficiaries_current,
            'average_processing_days': self.average_processing_days,
            'metadata': {
                'data_source': self.metadata.data_source.value,
                'source_url': self.metadata.source_url,
                'last_verified_at': self.metadata.last_verified_at.isoformat() if self.metadata.last_verified_at else None,
                'verification_status': self.metadata.verification_status,
                'version': self.metadata.version,
                'change_log': self.metadata.change_log,
                'tags': self.metadata.tags,
                'popularity_score': self.metadata.popularity_score,
                'success_rate': self.metadata.success_rate
            },
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GovernmentScheme':
        """Create scheme from dictionary format."""
        # Parse dates
        launch_date = None
        if data.get('launch_date'):
            launch_date = datetime.fromisoformat(data['launch_date']).date()
            
        end_date = None
        if data.get('end_date'):
            end_date = datetime.fromisoformat(data['end_date']).date()
        
        # Parse metadata
        metadata_dict = data.get('metadata', {})
        metadata = SchemeMetadata(
            data_source=DataSource(metadata_dict.get('data_source', 'manual_entry')),
            source_url=metadata_dict.get('source_url'),
            last_verified_at=datetime.fromisoformat(metadata_dict['last_verified_at']) if metadata_dict.get('last_verified_at') else None,
            verification_status=metadata_dict.get('verification_status', 'pending'),
            version=metadata_dict.get('version', 1),
            change_log=metadata_dict.get('change_log', []),
            tags=metadata_dict.get('tags', []),
            popularity_score=metadata_dict.get('popularity_score', 0.0),
            success_rate=metadata_dict.get('success_rate', 0.0)
        )
        
        # Parse eligibility criteria
        eligibility_dict = data.get('eligibility_criteria', {})
        eligibility = EligibilityCriteria(**eligibility_dict)
        
        # Parse benefits
        benefits_dict = data.get('benefits', {})
        benefits = SchemeBenefits(**benefits_dict)
        
        # Parse application process
        process_dict = data.get('application_process', {})
        application_process = ApplicationProcess(**process_dict)
        
        return cls(
            id=UUID(data['id']) if data.get('id') else uuid4(),
            scheme_id=data.get('scheme_id', ''),
            name=data.get('name', ''),
            name_hi=data.get('name_hi'),
            name_regional=data.get('name_regional', {}),
            department=data.get('department', ''),
            ministry=data.get('ministry'),
            category=SchemeCategory(data.get('category', 'social_security')),
            subcategory=data.get('subcategory'),
            description=data.get('description', ''),
            description_hi=data.get('description_hi'),
            description_regional=data.get('description_regional', {}),
            eligibility_criteria=eligibility,
            benefits=benefits,
            application_process=application_process,
            target_states=data.get('target_states', []),
            target_districts=data.get('target_districts', []),
            status=SchemeStatus(data.get('status', 'active')),
            launch_date=launch_date,
            end_date=end_date,
            budget_allocated=Decimal(str(data['budget_allocated'])) if data.get('budget_allocated') else None,
            beneficiaries_target=data.get('beneficiaries_target'),
            beneficiaries_current=data.get('beneficiaries_current', 0),
            average_processing_days=data.get('average_processing_days'),
            metadata=metadata,
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now()
        )


@dataclass
class SchemeUpdateResult:
    """Result of a scheme update operation."""
    success: bool
    scheme_id: str
    changes_detected: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    previous_version: Optional[int] = None
    new_version: Optional[int] = None
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class IngestionResult:
    """Result of a scheme ingestion operation."""
    total_processed: int = 0
    successful_updates: int = 0
    failed_updates: int = 0
    new_schemes: int = 0
    updated_schemes: int = 0
    validation_errors: List[Dict[str, Any]] = field(default_factory=list)
    processing_time_seconds: float = 0.0
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)