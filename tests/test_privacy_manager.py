"""
Unit tests for the privacy manager and related components.

Tests cover encryption, consent management, data retention, and compliance features.
"""

import pytest
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from bharat_voice_assistant.privacy import (
    PrivacyManager, EncryptionService, ConsentManager, DataRetentionManager
)
from bharat_voice_assistant.privacy.models import (
    ConsentType, ConsentStatus, DataType, ConsentRecord,
    DataRetentionPolicy, EncryptionMetadata, DataDeletionRequest
)
from bharat_voice_assistant.core.exceptions import (
    PrivacyError, ConsentError, DataEncryptionError, DataRetentionError
)


class TestEncryptionService:
    """Test encryption service functionality."""
    
    @pytest.fixture
    def encryption_service(self):
        """Create encryption service instance."""
        return EncryptionService()
    
    def test_encrypt_decrypt_voice_data(self, encryption_service):
        """Test voice data encryption and decryption."""
        # Test data
        user_id = "test_user_123"
        audio_data = b"fake audio data for testing"
        
        # Encrypt data
        encrypted_data, metadata = encryption_service.encrypt_voice_data(audio_data, user_id)
        
        # Verify encryption
        assert isinstance(encrypted_data, bytes)
        assert len(encrypted_data) > len(audio_data)  # Should be larger due to salt/tag
        assert isinstance(metadata, EncryptionMetadata)
        assert metadata.data_type == DataType.VOICE_RECORDING
        assert metadata.original_size == len(audio_data)
        
        # Decrypt data
        decrypted_data = encryption_service.decrypt_data(encrypted_data, metadata)
        
        # Verify decryption
        assert decrypted_data == audio_data
    
    def test_encrypt_personal_info(self, encryption_service):
        """Test personal information encryption."""
        user_id = "test_user_123"
        personal_data = b'{"name": "Test User", "phone": "1234567890"}'
        
        encrypted_data, metadata = encryption_service.encrypt_personal_info(personal_data, user_id)
        
        assert isinstance(encrypted_data, bytes)
        assert metadata.data_type == DataType.PERSONAL_INFO
        
        decrypted_data = encryption_service.decrypt_data(encrypted_data, metadata)
        assert decrypted_data == personal_data
    
    def test_encryption_with_different_keys(self, encryption_service):
        """Test that different keys produce different encrypted data."""
        data = b"test data"
        
        encrypted1, metadata1 = encryption_service.encrypt_data(data, DataType.VOICE_RECORDING, "key1")
        encrypted2, metadata2 = encryption_service.encrypt_data(data, DataType.VOICE_RECORDING, "key2")
        
        # Different keys should produce different encrypted data
        assert encrypted1 != encrypted2
        assert metadata1.key_id != metadata2.key_id
    
    def test_invalid_decryption(self, encryption_service):
        """Test decryption with invalid data."""
        invalid_data = b"invalid encrypted data"
        metadata = EncryptionMetadata(
            key_id="test_key",
            iv=b"invalid_iv",
            tag=b"invalid_tag",
            data_type=DataType.VOICE_RECORDING
        )
        
        with pytest.raises(DataEncryptionError):
            encryption_service.decrypt_data(invalid_data, metadata)


class TestConsentManager:
    """Test consent management functionality."""
    
    @pytest.fixture
    def consent_manager(self):
        """Create consent manager instance."""
        return ConsentManager()
    
    def test_collect_consent(self, consent_manager):
        """Test consent collection."""
        user_id = "test_user_123"
        consent_type = ConsentType.VOICE_RECORDING
        data_types = [DataType.VOICE_RECORDING]
        purpose = "Voice processing for government services"
        
        consent = consent_manager.collect_consent(
            user_id=user_id,
            consent_type=consent_type,
            data_types=data_types,
            purpose=purpose,
            duration_days=30
        )
        
        assert isinstance(consent, ConsentRecord)
        assert consent.user_id == user_id
        assert consent.consent_type == consent_type
        assert consent.status == ConsentStatus.GRANTED
        assert consent.data_types == data_types
        assert consent.purpose == purpose
        assert consent.granted_at is not None
        assert consent.expires_at is not None
    
    def test_check_consent(self, consent_manager):
        """Test consent checking."""
        user_id = "test_user_123"
        
        # No consent initially
        assert not consent_manager.check_consent(
            user_id, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING
        )
        
        # Collect consent
        consent_manager.collect_consent(
            user_id=user_id,
            consent_type=ConsentType.VOICE_RECORDING,
            data_types=[DataType.VOICE_RECORDING],
            purpose="Testing"
        )
        
        # Should have consent now
        assert consent_manager.check_consent(
            user_id, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING
        )
    
    def test_withdraw_consent(self, consent_manager):
        """Test consent withdrawal."""
        user_id = "test_user_123"
        
        # Collect consent
        consent = consent_manager.collect_consent(
            user_id=user_id,
            consent_type=ConsentType.VOICE_RECORDING,
            data_types=[DataType.VOICE_RECORDING],
            purpose="Testing"
        )
        
        # Withdraw consent
        success = consent_manager.withdraw_consent(
            user_id, consent.consent_id, "User requested withdrawal"
        )
        
        assert success
        assert consent.status == ConsentStatus.WITHDRAWN
        assert consent.withdrawn_at is not None
        
        # Should not have consent anymore
        assert not consent_manager.check_consent(
            user_id, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING
        )
    
    def test_expired_consent(self, consent_manager):
        """Test expired consent handling."""
        user_id = "test_user_123"
        
        # Collect consent with very short duration
        consent = consent_manager.collect_consent(
            user_id=user_id,
            consent_type=ConsentType.VOICE_RECORDING,
            data_types=[DataType.VOICE_RECORDING],
            purpose="Testing",
            duration_days=0  # Expires immediately
        )
        
        # Manually set expiration to past
        consent.expires_at = datetime.utcnow() - timedelta(hours=1)
        
        # Should not have valid consent
        assert not consent_manager.check_consent(
            user_id, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING
        )
        
        # Consent should be marked as expired
        assert consent.status == ConsentStatus.EXPIRED
    
    def test_require_consent(self, consent_manager):
        """Test consent requirement functionality."""
        user_id = "test_user_123"
        
        # Test with explicit consent not required (should auto-collect)
        with patch('bharat_voice_assistant.core.config.config.security.require_explicit_consent', False):
            result = consent_manager.require_consent(
                user_id, ConsentType.DATA_PROCESSING, DataType.PERSONAL_INFO, "Testing"
            )
            assert result
            
            # Should have consent now
            assert consent_manager.check_consent(
                user_id, ConsentType.DATA_PROCESSING, DataType.PERSONAL_INFO
            )
        
        # Test with explicit consent required (should still collect for testing)
        user_id2 = "test_user_456"
        with patch('bharat_voice_assistant.core.config.config.security.require_explicit_consent', True):
            result = consent_manager.require_consent(
                user_id2, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING, "Testing explicit"
            )
            assert result  # Should still work for testing purposes
            
            # Should have consent now
            assert consent_manager.check_consent(
                user_id2, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING
            )


class TestDataRetentionManager:
    """Test data retention and deletion functionality."""
    
    @pytest.fixture
    def retention_manager(self):
        """Create data retention manager instance."""
        return DataRetentionManager()
    
    def test_register_data(self, retention_manager):
        """Test data registration for retention tracking."""
        user_id = "test_user_123"
        data_type = DataType.VOICE_RECORDING
        data_location = "/tmp/test_voice.wav"
        
        data_id = retention_manager.register_data(
            user_id=user_id,
            data_type=data_type,
            data_location=data_location
        )
        
        assert isinstance(data_id, str)
        assert data_id in retention_manager.data_registry
        
        registration = retention_manager.data_registry[data_id]
        assert registration['user_id'] == user_id
        assert registration['data_type'] == data_type
        assert registration['data_location'] == data_location
        assert registration['deletion_scheduled']  # Voice recordings should be auto-scheduled
    
    def test_schedule_voice_deletion(self, retention_manager):
        """Test voice recording deletion scheduling."""
        user_id = "test_user_123"
        voice_file = "/tmp/test_voice.wav"
        
        data_id = retention_manager.schedule_voice_deletion(user_id, voice_file)
        
        assert data_id in retention_manager.data_registry
        registration = retention_manager.data_registry[data_id]
        assert registration['data_type'] == DataType.VOICE_RECORDING
        assert registration['deletion_scheduled']
    
    def test_mark_processing_complete(self, retention_manager):
        """Test marking voice processing as complete."""
        user_id = "test_user_123"
        voice_file = "/tmp/test_voice.wav"
        
        data_id = retention_manager.schedule_voice_deletion(user_id, voice_file)
        success = retention_manager.mark_voice_processing_complete(data_id)
        
        assert success
        registration = retention_manager.data_registry[data_id]
        assert registration['metadata']['processing_completed']
        assert 'processing_completed_at' in registration
    
    def test_user_data_deletion_request(self, retention_manager):
        """Test user data deletion request."""
        user_id = "test_user_123"
        data_types = [DataType.VOICE_RECORDING, DataType.PERSONAL_INFO]
        
        request = retention_manager.request_user_data_deletion(
            user_id=user_id,
            data_types=data_types,
            reason="User requested deletion"
        )
        
        assert isinstance(request, DataDeletionRequest)
        assert request.user_id == user_id
        assert request.data_types == data_types
        assert request.status == "pending"
        assert request.get_deadline() > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_process_scheduled_deletions(self, retention_manager):
        """Test processing of scheduled deletions."""
        user_id = "test_user_123"
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test data")
            temp_path = tmp_file.name
        
        try:
            # Register data with immediate deletion
            data_id = retention_manager.register_data(
                user_id=user_id,
                data_type=DataType.VOICE_RECORDING,
                data_location=temp_path
            )
            
            # Set deletion time to past
            registration = retention_manager.data_registry[data_id]
            registration['scheduled_deletion_at'] = datetime.utcnow() - timedelta(hours=1)
            
            # Process deletions
            deleted_count = await retention_manager.process_scheduled_deletions()
            
            assert deleted_count >= 1
            assert data_id not in retention_manager.data_registry
            assert not os.path.exists(temp_path)  # File should be deleted
            
        finally:
            # Cleanup if file still exists
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_get_user_data_summary(self, retention_manager):
        """Test user data summary generation."""
        user_id = "test_user_123"
        
        # Register some data
        retention_manager.register_data(user_id, DataType.VOICE_RECORDING, "/tmp/voice1.wav")
        retention_manager.register_data(user_id, DataType.PERSONAL_INFO, "/tmp/personal.json")
        
        summary = retention_manager.get_user_data_summary(user_id)
        
        assert summary['user_id'] == user_id
        assert summary['total_items'] == 2
        assert 'voice_recording' in summary['data_types']
        assert 'personal_info' in summary['data_types']
        assert summary['oldest_item'] is not None
        assert summary['newest_item'] is not None


class TestPrivacyManager:
    """Test main privacy manager functionality."""
    
    @pytest.fixture
    def privacy_manager(self):
        """Create privacy manager instance."""
        return PrivacyManager()
    
    def test_encrypt_voice_data_with_consent(self, privacy_manager):
        """Test voice data encryption with consent handling."""
        user_id = "test_user_123"
        audio_data = b"test audio data"
        
        # Should auto-collect consent and encrypt
        encrypted_data, data_id = privacy_manager.encrypt_voice_data(audio_data, user_id)
        
        assert isinstance(encrypted_data, bytes)
        assert len(encrypted_data) > len(audio_data)
        assert isinstance(data_id, str)
        
        # Should have voice recording consent now
        assert privacy_manager.consent_manager.check_consent(
            user_id, ConsentType.VOICE_RECORDING, DataType.VOICE_RECORDING
        )
    
    def test_ensure_voice_data_compliance(self, privacy_manager):
        """Test comprehensive voice data compliance."""
        user_id = "test_user_123"
        audio_data = b"test audio data"
        
        encrypted_data, data_id = privacy_manager.ensure_voice_data_compliance(user_id, audio_data)
        
        assert isinstance(encrypted_data, bytes)
        assert isinstance(data_id, str)
        
        # Mark processing complete
        success = privacy_manager.mark_voice_processing_complete(data_id)
        assert success
    
    def test_user_data_deletion_request(self, privacy_manager):
        """Test user data deletion request."""
        user_id = "test_user_123"
        
        # First create some data
        audio_data = b"test audio data"
        privacy_manager.encrypt_voice_data(audio_data, user_id)
        
        # Request deletion
        request = privacy_manager.request_user_data_deletion(user_id)
        
        assert isinstance(request, DataDeletionRequest)
        assert request.user_id == user_id
        assert request.status == "pending"
        
        # Check status
        status = privacy_manager.get_deletion_request_status(request.request_id)
        assert status is not None
        assert status.request_id == request.request_id
    
    def test_get_user_privacy_summary(self, privacy_manager):
        """Test user privacy summary generation."""
        user_id = "test_user_123"
        
        # Create some data and consents
        audio_data = b"test audio data"
        privacy_manager.encrypt_voice_data(audio_data, user_id)
        
        summary = privacy_manager.get_user_privacy_summary(user_id)
        
        assert summary['user_id'] == user_id
        assert 'consents' in summary
        assert 'data_storage' in summary
        assert 'privacy_rights' in summary
        assert summary['consents']['total'] > 0
        assert summary['data_storage']['total_items'] > 0
    
    def test_export_user_data(self, privacy_manager):
        """Test user data export for portability."""
        user_id = "test_user_123"
        
        # Create some data
        audio_data = b"test audio data"
        privacy_manager.encrypt_voice_data(audio_data, user_id)
        
        export_data = privacy_manager.export_user_data(user_id)
        
        assert export_data['user_id'] == user_id
        assert export_data['export_type'] == 'complete_user_data'
        assert 'consent_data' in export_data
        assert 'privacy_summary' in export_data
        assert 'exported_at' in export_data
    
    def test_validate_privacy_configuration(self, privacy_manager):
        """Test privacy configuration validation."""
        validation = privacy_manager.validate_privacy_configuration()
        
        assert 'valid' in validation
        assert 'errors' in validation
        assert 'warnings' in validation
        assert 'configuration' in validation
        
        # Should be valid with default configuration
        assert validation['valid'] or len(validation['errors']) == 0
    
    def test_compliance_report(self, privacy_manager):
        """Test compliance report generation."""
        report = privacy_manager.get_compliance_report()
        
        assert 'report_generated_at' in report
        assert 'privacy_configuration' in report
        assert 'statistics' in report
        assert 'compliance_features' in report
        
        features = report['compliance_features']
        assert features['voice_data_encryption']
        assert features['explicit_consent_collection']
        assert features['automatic_voice_deletion']
        assert features['user_data_deletion_within_30_days']
        assert features['consent_withdrawal']
        assert features['data_export']
        assert features['audit_logging']
    
    @pytest.mark.asyncio
    async def test_background_tasks(self, privacy_manager):
        """Test background task management."""
        # Start background tasks
        await privacy_manager.start_background_tasks()
        assert privacy_manager._is_running
        assert len(privacy_manager._background_tasks) > 0
        
        # Stop background tasks
        await privacy_manager.stop_background_tasks()
        assert not privacy_manager._is_running
        assert len(privacy_manager._background_tasks) == 0
    
    def test_consent_withdrawal(self, privacy_manager):
        """Test consent withdrawal functionality."""
        user_id = "test_user_123"
        
        # Create consent
        audio_data = b"test audio data"
        privacy_manager.encrypt_voice_data(audio_data, user_id)
        
        # Get consents
        consents = privacy_manager.get_user_consents(user_id)
        assert len(consents) > 0
        
        # Withdraw consent
        consent_id = consents[0].consent_id
        success = privacy_manager.withdraw_user_consent(user_id, consent_id, "Testing withdrawal")
        
        assert success
        
        # Check consent status
        updated_consents = privacy_manager.get_user_consents(user_id)
        withdrawn_consent = next(c for c in updated_consents if c.consent_id == consent_id)
        assert withdrawn_consent.status == ConsentStatus.WITHDRAWN


# Integration tests
class TestPrivacyIntegration:
    """Integration tests for privacy manager with other components."""
    
    @pytest.fixture
    def privacy_manager(self):
        """Create privacy manager instance."""
        return PrivacyManager()
    
    def test_end_to_end_voice_processing(self, privacy_manager):
        """Test complete voice processing workflow with privacy compliance."""
        user_id = "test_user_123"
        audio_data = b"test voice recording data"
        
        # Step 1: Encrypt voice data (with consent collection)
        encrypted_data, data_id = privacy_manager.ensure_voice_data_compliance(user_id, audio_data)
        
        # Step 2: Process voice data (simulated)
        # In real implementation, this would involve speech recognition
        
        # Step 3: Mark processing complete (triggers deletion countdown)
        success = privacy_manager.mark_voice_processing_complete(data_id)
        assert success
        
        # Step 4: Verify privacy compliance
        summary = privacy_manager.get_user_privacy_summary(user_id)
        assert summary['consents']['active'] > 0
        assert summary['data_storage']['total_items'] > 0
        
        # Step 5: User requests data deletion
        deletion_request = privacy_manager.request_user_data_deletion(user_id)
        assert deletion_request.status == "pending"
    
    def test_privacy_error_handling(self, privacy_manager):
        """Test privacy error handling scenarios."""
        user_id = "test_user_123"
        
        # Test invalid consent withdrawal
        with pytest.raises(ConsentError):
            privacy_manager.withdraw_user_consent(user_id, "invalid_consent_id")
        
        # Test invalid deletion request status
        invalid_status = privacy_manager.get_deletion_request_status("invalid_request_id")
        assert invalid_status is None
    
    @pytest.mark.asyncio
    async def test_automatic_cleanup(self, privacy_manager):
        """Test automatic cleanup of expired data and consents."""
        user_id = "test_user_123"
        
        # Create some data
        audio_data = b"test audio data"
        encrypted_data, data_id = privacy_manager.encrypt_voice_data(audio_data, user_id)
        
        # Mark processing complete
        privacy_manager.mark_voice_processing_complete(data_id)
        
        # Manually set deletion time to past for testing
        registration = privacy_manager.data_retention_manager.data_registry[data_id]
        registration['scheduled_deletion_at'] = datetime.utcnow() - timedelta(hours=1)
        
        # Process cleanup
        deleted_count = await privacy_manager.data_retention_manager.process_scheduled_deletions()
        
        assert deleted_count >= 1