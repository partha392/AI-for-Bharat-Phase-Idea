"""
Main privacy manager for the Bharat Voice Assistant.

This module orchestrates all privacy-related functionality including encryption,
consent management, and data retention to ensure compliance with privacy regulations.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json

from ..core.logging import get_logger
from ..core.exceptions import PrivacyError, ConsentError, DataEncryptionError, DataRetentionError
from ..core.config import config
from .encryption_service import EncryptionService
from .consent_manager import ConsentManager
from .data_retention_manager import DataRetentionManager
from .models import (
    ConsentType, ConsentStatus, DataType, ConsentRecord,
    DataDeletionRequest, EncryptionMetadata, PrivacyAuditLog
)

logger = get_logger(__name__)


class PrivacyManager:
    """
    Main privacy manager that orchestrates all privacy-related operations.
    
    This class provides a unified interface for:
    - Voice data encryption during transmission and storage
    - Explicit consent collection for data usage
    - Automatic deletion of voice recordings after processing
    - User data deletion within 30 days of request
    """
    
    def __init__(self):
        """Initialize the privacy manager with all sub-components."""
        self.encryption_service = EncryptionService()
        self.consent_manager = ConsentManager()
        self.data_retention_manager = DataRetentionManager()
        self._background_tasks: List[asyncio.Task] = []
        self._is_running = False
        
        logger.info("Privacy manager initialized")
    
    async def start_background_tasks(self) -> None:
        """Start background tasks for automatic data management."""
        if self._is_running:
            return
        
        self._is_running = True
        
        # Start periodic cleanup task
        cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self._background_tasks.append(cleanup_task)
        
        logger.info("Privacy manager background tasks started")
    
    async def stop_background_tasks(self) -> None:
        """Stop all background tasks."""
        self._is_running = False
        
        for task in self._background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._background_tasks.clear()
        logger.info("Privacy manager background tasks stopped")
    
    # Voice Data Encryption Methods
    
    def encrypt_voice_data(self, audio_data: bytes, user_id: str) -> Tuple[bytes, str]:
        """
        Encrypt voice data for secure transmission and storage.
        
        Args:
            audio_data: Raw audio data to encrypt
            user_id: User identifier for key derivation
            
        Returns:
            Tuple of (encrypted_data, data_registration_id)
        """
        try:
            # Check consent for voice recording encryption
            if not self.consent_manager.check_consent(
                user_id, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING
            ):
                # Try to collect consent
                if not self.consent_manager.require_consent(
                    user_id, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING,
                    "Voice data encryption for secure processing"
                ):
                    raise ConsentError(
                        "Consent required for voice data encryption",
                        error_code="VOICE_ENCRYPTION_CONSENT_REQUIRED"
                    )
            
            # Encrypt the voice data
            encrypted_data, encryption_metadata = self.encryption_service.encrypt_voice_data(
                audio_data, user_id
            )
            
            # Register for automatic deletion
            data_id = self.data_retention_manager.schedule_voice_deletion(
                user_id=user_id,
                voice_file_path=f"encrypted_voice_{encryption_metadata.encryption_id}",
                encryption_metadata=encryption_metadata
            )
            
            logger.info(
                f"Voice data encrypted and scheduled for deletion",
                extra={
                    'component': 'privacy_manager',
                    'operation': 'encrypt_voice_data',
                    'user_id': user_id,
                    'data_id': data_id,
                    'original_size': len(audio_data),
                    'encrypted_size': len(encrypted_data)
                }
            )
            
            return encrypted_data, data_id
            
        except (ConsentError, DataEncryptionError):
            raise
        except Exception as e:
            logger.error(f"Failed to encrypt voice data for user {user_id}: {e}")
            raise PrivacyError(
                f"Voice data encryption failed: {str(e)}",
                error_code="VOICE_ENCRYPTION_FAILED",
                context={'user_id': user_id}
            )
    
    def decrypt_voice_data(self, encrypted_data: bytes, 
                          encryption_metadata: EncryptionMetadata) -> bytes:
        """
        Decrypt voice data for processing.
        
        Args:
            encrypted_data: Encrypted voice data
            encryption_metadata: Encryption metadata
            
        Returns:
            Decrypted audio data
        """
        try:
            return self.encryption_service.decrypt_data(encrypted_data, encryption_metadata)
        except Exception as e:
            logger.error(f"Failed to decrypt voice data: {e}")
            raise DataEncryptionError(
                f"Voice data decryption failed: {str(e)}",
                error_code="VOICE_DECRYPTION_FAILED"
            )
    
    # Consent Management Methods
    
    def collect_explicit_consent(self, user_id: str, consent_type: ConsentType,
                                data_types: List[DataType], purpose: str,
                                duration_days: Optional[int] = None) -> ConsentRecord:
        """
        Collect explicit consent from user for data usage.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent being collected
            data_types: Types of data the consent covers
            purpose: Purpose for which consent is being collected
            duration_days: Optional consent duration in days
            
        Returns:
            ConsentRecord with consent details
        """
        try:
            return self.consent_manager.collect_consent(
                user_id=user_id,
                consent_type=consent_type,
                data_types=data_types,
                purpose=purpose,
                duration_days=duration_days
            )
        except Exception as e:
            logger.error(f"Failed to collect consent for user {user_id}: {e}")
            raise ConsentError(
                f"Consent collection failed: {str(e)}",
                error_code="CONSENT_COLLECTION_FAILED",
                context={'user_id': user_id, 'consent_type': consent_type.value}
            )
    
    def check_data_processing_consent(self, user_id: str, data_type: DataType) -> bool:
        """
        Check if user has valid consent for data processing.
        
        Args:
            user_id: User identifier
            data_type: Type of data to check consent for
            
        Returns:
            True if valid consent exists
        """
        return self.consent_manager.check_consent(
            user_id, ConsentType.DATA_PROCESSING, data_type
        )
    
    def withdraw_user_consent(self, user_id: str, consent_id: str,
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
        return self.consent_manager.withdraw_consent(user_id, consent_id, reason)
    
    def get_user_consents(self, user_id: str) -> List[ConsentRecord]:
        """Get all consent records for a user."""
        return self.consent_manager.get_user_consents(user_id)
    
    # Data Retention and Deletion Methods
    
    def mark_voice_processing_complete(self, data_id: str) -> bool:
        """
        Mark voice processing as complete, triggering automatic deletion countdown.
        
        Args:
            data_id: Data registration ID from encrypt_voice_data
            
        Returns:
            True if successfully marked
        """
        return self.data_retention_manager.mark_voice_processing_complete(data_id)
    
    def request_user_data_deletion(self, user_id: str,
                                  data_types: Optional[List[DataType]] = None,
                                  reason: str = "User request") -> DataDeletionRequest:
        """
        Request deletion of all user data within 30 days.
        
        Args:
            user_id: User identifier
            data_types: Specific data types to delete (None for all)
            reason: Reason for deletion request
            
        Returns:
            DataDeletionRequest object
        """
        try:
            # Also withdraw all consents when user requests data deletion
            user_consents = self.consent_manager.get_active_consents(user_id)
            for consent in user_consents:
                self.consent_manager.withdraw_consent(
                    user_id, consent.consent_id, "Data deletion requested"
                )
            
            return self.data_retention_manager.request_user_data_deletion(
                user_id, data_types, reason
            )
        except Exception as e:
            logger.error(f"Failed to request data deletion for user {user_id}: {e}")
            raise DataRetentionError(
                f"Data deletion request failed: {str(e)}",
                error_code="DATA_DELETION_REQUEST_FAILED",
                context={'user_id': user_id}
            )
    
    def get_deletion_request_status(self, request_id: str) -> Optional[DataDeletionRequest]:
        """Get the status of a deletion request."""
        return self.data_retention_manager.get_deletion_request_status(request_id)
    
    # Privacy Compliance Methods
    
    def ensure_voice_data_compliance(self, user_id: str, audio_data: bytes) -> Tuple[bytes, str]:
        """
        Ensure voice data complies with all privacy requirements.
        
        This method:
        1. Checks/collects consent for voice recording
        2. Encrypts the voice data
        3. Schedules automatic deletion after processing
        
        Args:
            user_id: User identifier
            audio_data: Raw audio data
            
        Returns:
            Tuple of (encrypted_data, data_registration_id)
        """
        return self.encrypt_voice_data(audio_data, user_id)
    
    def ensure_data_processing_compliance(self, user_id: str, 
                                        data_type: DataType) -> bool:
        """
        Ensure data processing complies with consent requirements.
        
        Args:
            user_id: User identifier
            data_type: Type of data being processed
            
        Returns:
            True if processing is allowed
        """
        return self.consent_manager.require_consent(
            user_id, ConsentType.DATA_PROCESSING, data_type,
            f"Processing {data_type.value} for government service assistance"
        )
    
    def get_user_privacy_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive privacy summary for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with privacy information
        """
        try:
            consents = self.consent_manager.get_user_consents(user_id)
            active_consents = [c for c in consents if c.is_valid()]
            data_summary = self.data_retention_manager.get_user_data_summary(user_id)
            
            return {
                'user_id': user_id,
                'consents': {
                    'total': len(consents),
                    'active': len(active_consents),
                    'details': [
                        {
                            'consent_id': c.consent_id,
                            'type': c.consent_type.value,
                            'status': c.status.value,
                            'granted_at': c.granted_at.isoformat() if c.granted_at else None,
                            'expires_at': c.expires_at.isoformat() if c.expires_at else None,
                            'purpose': c.purpose
                        }
                        for c in consents
                    ]
                },
                'data_storage': data_summary,
                'privacy_rights': {
                    'can_withdraw_consent': len(active_consents) > 0,
                    'can_request_deletion': data_summary['total_items'] > 0,
                    'can_export_data': True
                },
                'generated_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to generate privacy summary for user {user_id}: {e}")
            raise PrivacyError(
                f"Privacy summary generation failed: {str(e)}",
                error_code="PRIVACY_SUMMARY_FAILED",
                context={'user_id': user_id}
            )
    
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Export all user data for data portability compliance.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary containing all user data
        """
        try:
            consent_data = self.consent_manager.export_consent_data(user_id)
            privacy_summary = self.get_user_privacy_summary(user_id)
            
            return {
                'user_id': user_id,
                'export_type': 'complete_user_data',
                'exported_at': datetime.utcnow().isoformat(),
                'consent_data': consent_data,
                'privacy_summary': privacy_summary,
                'data_retention_info': self.data_retention_manager.get_user_data_summary(user_id)
            }
        except Exception as e:
            logger.error(f"Failed to export data for user {user_id}: {e}")
            raise PrivacyError(
                f"Data export failed: {str(e)}",
                error_code="DATA_EXPORT_FAILED",
                context={'user_id': user_id}
            )
    
    # Background Processing Methods
    
    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup of expired consents and scheduled deletions."""
        while self._is_running:
            try:
                # Clean up expired consents
                expired_count = self.consent_manager.cleanup_expired_consents()
                
                # Process scheduled deletions
                deleted_count = await self.data_retention_manager.process_scheduled_deletions()
                
                if expired_count > 0 or deleted_count > 0:
                    logger.info(
                        f"Privacy cleanup completed",
                        extra={
                            'component': 'privacy_manager',
                            'operation': 'periodic_cleanup',
                            'expired_consents': expired_count,
                            'deleted_items': deleted_count
                        }
                    )
                
                # Sleep for 1 hour before next cleanup
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in privacy cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry
    
    # Utility Methods
    
    def validate_privacy_configuration(self) -> Dict[str, Any]:
        """
        Validate privacy configuration and return status.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'configuration': {
                'encryption_algorithm': config.security.encryption_algorithm,
                'voice_retention_hours': config.security.voice_data_retention_hours,
                'user_deletion_days': config.security.user_data_deletion_days,
                'require_explicit_consent': config.security.require_explicit_consent,
                'anonymize_logs': config.security.anonymize_logs
            }
        }
        
        try:
            # Validate encryption service
            test_data = b"test encryption data"
            encrypted_data, metadata = self.encryption_service.encrypt_data(
                test_data, DataType.VOICE_RECORDING
            )
            decrypted_data = self.encryption_service.decrypt_data(encrypted_data, metadata)
            
            if decrypted_data != test_data:
                validation_results['valid'] = False
                validation_results['errors'].append("Encryption/decryption validation failed")
            
            # Check configuration values
            if config.security.voice_data_retention_hours <= 0:
                validation_results['warnings'].append("Voice data retention period is zero or negative")
            
            if config.security.user_data_deletion_days > 30:
                validation_results['warnings'].append("User data deletion period exceeds 30 days")
            
        except Exception as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Privacy validation failed: {e}")
        
        return validation_results
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """
        Generate compliance report for privacy regulations.
        
        Returns:
            Dictionary with compliance information
        """
        try:
            total_users = len(self.consent_manager.consent_storage)
            total_consents = sum(
                len(consents) for consents in self.consent_manager.consent_storage.values()
            )
            total_data_items = len(self.data_retention_manager.data_registry)
            
            return {
                'report_generated_at': datetime.utcnow().isoformat(),
                'privacy_configuration': self.validate_privacy_configuration(),
                'statistics': {
                    'total_users_with_consents': total_users,
                    'total_consent_records': total_consents,
                    'total_data_items_tracked': total_data_items,
                    'active_deletion_requests': len([
                        req for req in self.data_retention_manager.deletion_requests.values()
                        if req.status in ['pending', 'in_progress']
                    ])
                },
                'compliance_features': {
                    'voice_data_encryption': True,
                    'explicit_consent_collection': True,
                    'automatic_voice_deletion': True,
                    'user_data_deletion_within_30_days': True,
                    'consent_withdrawal': True,
                    'data_export': True,
                    'audit_logging': True
                }
            }
        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}")
            raise PrivacyError(
                f"Compliance report generation failed: {str(e)}",
                error_code="COMPLIANCE_REPORT_FAILED"
            )