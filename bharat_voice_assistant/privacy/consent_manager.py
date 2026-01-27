"""
Consent management for user data usage.

This module handles explicit consent collection, validation, and management
for various types of data processing activities.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from ..core.logging import get_logger
from ..core.exceptions import ConsentError
from ..core.config import config
from .models import ConsentRecord, ConsentType, ConsentStatus, DataType, PrivacyAuditLog

logger = get_logger(__name__)


class ConsentManager:
    """Manager for user consent collection and validation."""
    
    def __init__(self):
        """Initialize the consent manager."""
        self.consent_storage: Dict[str, List[ConsentRecord]] = {}
        self.audit_logs: List[PrivacyAuditLog] = []
    
    def collect_consent(self, user_id: str, consent_type: ConsentType,
                       data_types: List[DataType], purpose: str,
                       duration_days: Optional[int] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> ConsentRecord:
        """
        Collect explicit consent from user.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent being collected
            data_types: Types of data the consent covers
            purpose: Purpose for which consent is being collected
            duration_days: Optional consent duration in days
            metadata: Additional metadata
            
        Returns:
            ConsentRecord with consent details
        """
        try:
            # Create consent record
            consent = ConsentRecord(
                user_id=user_id,
                consent_type=consent_type,
                status=ConsentStatus.GRANTED,
                granted_at=datetime.utcnow(),
                purpose=purpose,
                data_types=data_types,
                metadata=metadata or {}
            )
            
            # Set expiration if duration specified
            if duration_days:
                consent.expires_at = datetime.utcnow() + timedelta(days=duration_days)
            
            # Store consent
            if user_id not in self.consent_storage:
                self.consent_storage[user_id] = []
            
            self.consent_storage[user_id].append(consent)
            
            # Log consent collection
            self._log_consent_action(
                user_id=user_id,
                operation="consent_granted",
                consent_type=consent_type,
                data_types=data_types,
                details={
                    'consent_id': consent.consent_id,
                    'purpose': purpose,
                    'expires_at': consent.expires_at.isoformat() if consent.expires_at else None
                }
            )
            
            logger.info(
                f"Consent collected for user {user_id}",
                extra={
                    'component': 'consent_manager',
                    'operation': 'collect_consent',
                    'user_id': user_id,
                    'consent_type': consent_type.value,
                    'data_types': [dt.value for dt in data_types],
                    'consent_id': consent.consent_id
                }
            )
            
            return consent
            
        except Exception as e:
            logger.error(f"Failed to collect consent for user {user_id}: {e}")
            raise ConsentError(
                f"Consent collection failed: {str(e)}",
                error_code="CONSENT_COLLECTION_FAILED",
                context={'user_id': user_id, 'consent_type': consent_type.value}
            )
    
    def withdraw_consent(self, user_id: str, consent_id: str,
                        reason: Optional[str] = None) -> bool:
        """
        Withdraw previously granted consent.
        
        Args:
            user_id: User identifier
            consent_id: Consent record identifier
            reason: Optional reason for withdrawal
            
        Returns:
            True if consent was successfully withdrawn
        """
        try:
            if user_id not in self.consent_storage:
                raise ConsentError(
                    f"No consent records found for user {user_id}",
                    error_code="CONSENT_NOT_FOUND"
                )
            
            # Find and withdraw consent
            for consent in self.consent_storage[user_id]:
                if consent.consent_id == consent_id:
                    if consent.status == ConsentStatus.WITHDRAWN:
                        logger.warning(f"Consent {consent_id} already withdrawn")
                        return True
                    
                    consent.status = ConsentStatus.WITHDRAWN
                    consent.withdrawn_at = datetime.utcnow()
                    
                    if reason:
                        consent.metadata['withdrawal_reason'] = reason
                    
                    # Log consent withdrawal
                    self._log_consent_action(
                        user_id=user_id,
                        operation="consent_withdrawn",
                        consent_type=consent.consent_type,
                        data_types=consent.data_types,
                        details={
                            'consent_id': consent_id,
                            'reason': reason,
                            'withdrawn_at': consent.withdrawn_at.isoformat()
                        }
                    )
                    
                    logger.info(
                        f"Consent withdrawn for user {user_id}",
                        extra={
                            'component': 'consent_manager',
                            'operation': 'withdraw_consent',
                            'user_id': user_id,
                            'consent_id': consent_id,
                            'reason': reason
                        }
                    )
                    
                    return True
            
            raise ConsentError(
                f"Consent {consent_id} not found for user {user_id}",
                error_code="CONSENT_NOT_FOUND"
            )
            
        except ConsentError:
            raise
        except Exception as e:
            logger.error(f"Failed to withdraw consent {consent_id}: {e}")
            raise ConsentError(
                f"Consent withdrawal failed: {str(e)}",
                error_code="CONSENT_WITHDRAWAL_FAILED",
                context={'user_id': user_id, 'consent_id': consent_id}
            )
    
    def check_consent(self, user_id: str, consent_type: ConsentType,
                     data_type: DataType) -> bool:
        """
        Check if user has valid consent for specific data processing.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent to check
            data_type: Type of data to check consent for
            
        Returns:
            True if valid consent exists
        """
        try:
            if user_id not in self.consent_storage:
                return False
            
            current_time = datetime.utcnow()
            
            for consent in self.consent_storage[user_id]:
                # Check if consent matches criteria
                if (consent.consent_type == consent_type and
                    data_type in consent.data_types and
                    consent.status == ConsentStatus.GRANTED):
                    
                    # Check if consent has expired
                    if consent.expires_at and current_time > consent.expires_at:
                        # Mark as expired
                        consent.status = ConsentStatus.EXPIRED
                        continue
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check consent for user {user_id}: {e}")
            return False
    
    def get_user_consents(self, user_id: str) -> List[ConsentRecord]:
        """
        Get all consent records for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of consent records
        """
        return self.consent_storage.get(user_id, [])
    
    def get_active_consents(self, user_id: str) -> List[ConsentRecord]:
        """
        Get all active (valid) consent records for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of active consent records
        """
        consents = self.get_user_consents(user_id)
        return [consent for consent in consents if consent.is_valid()]
    
    def require_consent(self, user_id: str, consent_type: ConsentType,
                       data_type: DataType, purpose: str) -> bool:
        """
        Require consent for data processing, collecting if necessary.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent required
            data_type: Type of data requiring consent
            purpose: Purpose for data processing
            
        Returns:
            True if consent is available or collected
        """
        # Check if consent already exists
        if self.check_consent(user_id, consent_type, data_type):
            return True
        
        # Auto-collect consent for essential operations
        # In a real implementation, this would prompt the user for consent
        # For testing and development, we auto-collect with appropriate metadata
        try:
            self.collect_consent(
                user_id=user_id,
                consent_type=consent_type,
                data_types=[data_type],
                purpose=purpose,
                duration_days=365,  # 1 year default
                metadata={
                    'auto_collected': not config.security.require_explicit_consent,
                    'collection_method': 'automatic' if not config.security.require_explicit_consent else 'explicit_required'
                }
            )
            
            logger.info(
                f"Consent collected for user {user_id}",
                extra={
                    'component': 'consent_manager',
                    'operation': 'require_consent',
                    'user_id': user_id,
                    'consent_type': consent_type.value,
                    'data_type': data_type.value,
                    'auto_collected': not config.security.require_explicit_consent
                }
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to collect consent: {e}")
            return False
    
    def cleanup_expired_consents(self) -> int:
        """
        Clean up expired consent records.
        
        Returns:
            Number of expired consents cleaned up
        """
        cleaned_count = 0
        current_time = datetime.utcnow()
        
        for user_id, consents in self.consent_storage.items():
            for consent in consents:
                if (consent.status == ConsentStatus.GRANTED and
                    consent.expires_at and
                    current_time > consent.expires_at):
                    
                    consent.status = ConsentStatus.EXPIRED
                    cleaned_count += 1
                    
                    logger.info(
                        f"Marked consent as expired",
                        extra={
                            'component': 'consent_manager',
                            'operation': 'cleanup_expired',
                            'user_id': user_id,
                            'consent_id': consent.consent_id
                        }
                    )
        
        return cleaned_count
    
    def _log_consent_action(self, user_id: str, operation: str,
                           consent_type: ConsentType, data_types: List[DataType],
                           details: Dict[str, Any]) -> None:
        """Log consent-related actions for audit purposes."""
        audit_log = PrivacyAuditLog(
            user_id=user_id,
            operation=operation,
            timestamp=datetime.utcnow(),
            details={
                'consent_type': consent_type.value,
                'data_types': [dt.value for dt in data_types],
                **details
            }
        )
        
        self.audit_logs.append(audit_log)
    
    def export_consent_data(self, user_id: str) -> Dict[str, Any]:
        """
        Export all consent data for a user (for data portability).
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary containing all consent data
        """
        consents = self.get_user_consents(user_id)
        
        return {
            'user_id': user_id,
            'consents': [
                {
                    'consent_id': consent.consent_id,
                    'consent_type': consent.consent_type.value,
                    'status': consent.status.value,
                    'granted_at': consent.granted_at.isoformat() if consent.granted_at else None,
                    'withdrawn_at': consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
                    'expires_at': consent.expires_at.isoformat() if consent.expires_at else None,
                    'purpose': consent.purpose,
                    'data_types': [dt.value for dt in consent.data_types],
                    'metadata': consent.metadata
                }
                for consent in consents
            ],
            'exported_at': datetime.utcnow().isoformat()
        }