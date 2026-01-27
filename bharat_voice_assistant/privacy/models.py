"""
Data models for privacy management.

This module defines the data structures used for consent management,
data retention policies, and encryption metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid


class ConsentType(Enum):
    """Types of consent that can be collected."""
    VOICE_RECORDING = "voice_recording"
    DATA_PROCESSING = "data_processing"
    DATA_STORAGE = "data_storage"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    THIRD_PARTY_SHARING = "third_party_sharing"


class ConsentStatus(Enum):
    """Status of consent."""
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class DataType(Enum):
    """Types of data that can be managed."""
    VOICE_RECORDING = "voice_recording"
    PERSONAL_INFO = "personal_info"
    CONVERSATION_HISTORY = "conversation_history"
    USER_PREFERENCES = "user_preferences"
    ANALYTICS_DATA = "analytics_data"
    LOG_DATA = "log_data"


@dataclass
class ConsentRecord:
    """Record of user consent for data usage."""
    
    consent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    consent_type: ConsentType = ConsentType.DATA_PROCESSING
    status: ConsentStatus = ConsentStatus.DENIED
    granted_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    purpose: str = ""
    data_types: List[DataType] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if consent is currently valid."""
        if self.status != ConsentStatus.GRANTED:
            return False
        
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        
        return True
    
    def is_expired(self) -> bool:
        """Check if consent has expired."""
        return self.expires_at and datetime.utcnow() > self.expires_at


@dataclass
class DataRetentionPolicy:
    """Policy for data retention and deletion."""
    
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: DataType = DataType.VOICE_RECORDING
    retention_period_hours: int = 24  # Default 24 hours for voice recordings
    auto_delete: bool = True
    requires_consent: bool = True
    deletion_method: str = "secure_delete"  # secure_delete, anonymize, archive
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_deletion_date(self, created_at: datetime) -> datetime:
        """Calculate when data should be deleted."""
        return created_at + timedelta(hours=self.retention_period_hours)
    
    def should_delete(self, created_at: datetime) -> bool:
        """Check if data should be deleted based on retention policy."""
        if not self.auto_delete:
            return False
        
        return datetime.utcnow() >= self.get_deletion_date(created_at)


@dataclass
class EncryptionMetadata:
    """Metadata for encrypted data."""
    
    encryption_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    algorithm: str = "AES-256-GCM"
    key_id: str = ""
    iv: bytes = b""
    tag: bytes = b""
    encrypted_at: datetime = field(default_factory=datetime.utcnow)
    data_type: DataType = DataType.VOICE_RECORDING
    original_size: int = 0
    encrypted_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataDeletionRequest:
    """Request for user data deletion."""
    
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    requested_at: datetime = field(default_factory=datetime.utcnow)
    data_types: List[DataType] = field(default_factory=list)
    reason: str = ""
    status: str = "pending"  # pending, in_progress, completed, failed
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_deadline(self) -> datetime:
        """Get the deadline for completing the deletion request (30 days)."""
        return self.requested_at + timedelta(days=30)
    
    def is_overdue(self) -> bool:
        """Check if the deletion request is overdue."""
        return datetime.utcnow() > self.get_deadline()


@dataclass
class PrivacyAuditLog:
    """Audit log entry for privacy-related operations."""
    
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    operation: str = ""  # consent_granted, consent_withdrawn, data_encrypted, data_deleted
    data_type: Optional[DataType] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None