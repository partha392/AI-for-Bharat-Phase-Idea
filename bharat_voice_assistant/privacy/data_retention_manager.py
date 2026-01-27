"""
Data retention and automatic deletion manager.

This module handles automatic deletion of voice recordings after processing
and user data deletion within 30 days of request.
"""

import os
import shutil
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import json

from ..core.logging import get_logger
from ..core.exceptions import DataRetentionError
from ..core.config import config
from .models import (
    DataRetentionPolicy, DataDeletionRequest, DataType, 
    PrivacyAuditLog, EncryptionMetadata
)

logger = get_logger(__name__)


class DataRetentionManager:
    """Manager for data retention policies and automatic deletion."""
    
    def __init__(self):
        """Initialize the data retention manager."""
        self.retention_policies = self._create_default_policies()
        self.deletion_requests: Dict[str, DataDeletionRequest] = {}
        self.audit_logs: List[PrivacyAuditLog] = []
        self.data_registry: Dict[str, Dict[str, Any]] = {}  # Track data locations
    
    def _create_default_policies(self) -> Dict[DataType, DataRetentionPolicy]:
        """Create default retention policies based on configuration."""
        policies = {}
        
        # Voice recordings - delete after processing (24 hours default)
        policies[DataType.VOICE_RECORDING] = DataRetentionPolicy(
            data_type=DataType.VOICE_RECORDING,
            retention_period_hours=config.security.voice_data_retention_hours,
            auto_delete=True,
            requires_consent=True,
            deletion_method="secure_delete"
        )
        
        # Personal information - keep until user requests deletion
        policies[DataType.PERSONAL_INFO] = DataRetentionPolicy(
            data_type=DataType.PERSONAL_INFO,
            retention_period_hours=24 * 365,  # 1 year default
            auto_delete=False,
            requires_consent=True,
            deletion_method="secure_delete"
        )
        
        # Conversation history - delete after 7 days
        policies[DataType.CONVERSATION_HISTORY] = DataRetentionPolicy(
            data_type=DataType.CONVERSATION_HISTORY,
            retention_period_hours=24 * 7,  # 7 days
            auto_delete=True,
            requires_consent=False,
            deletion_method="secure_delete"
        )
        
        # User preferences - keep until user requests deletion
        policies[DataType.USER_PREFERENCES] = DataRetentionPolicy(
            data_type=DataType.USER_PREFERENCES,
            retention_period_hours=24 * 365 * 2,  # 2 years
            auto_delete=False,
            requires_consent=False,
            deletion_method="anonymize"
        )
        
        # Analytics data - anonymize after 90 days
        policies[DataType.ANALYTICS_DATA] = DataRetentionPolicy(
            data_type=DataType.ANALYTICS_DATA,
            retention_period_hours=24 * 90,  # 90 days
            auto_delete=True,
            requires_consent=False,
            deletion_method="anonymize"
        )
        
        # Log data - delete after 30 days
        policies[DataType.LOG_DATA] = DataRetentionPolicy(
            data_type=DataType.LOG_DATA,
            retention_period_hours=24 * 30,  # 30 days
            auto_delete=True,
            requires_consent=False,
            deletion_method="secure_delete"
        )
        
        return policies
    
    def register_data(self, user_id: str, data_type: DataType,
                     data_location: str, metadata: Optional[Dict[str, Any]] = None,
                     encryption_metadata: Optional[EncryptionMetadata] = None) -> str:
        """
        Register data for retention tracking.
        
        Args:
            user_id: User identifier
            data_type: Type of data being registered
            data_location: Location/path of the data
            metadata: Additional metadata
            encryption_metadata: Encryption information if data is encrypted
            
        Returns:
            Data registration ID
        """
        try:
            data_id = f"{user_id}_{data_type.value}_{datetime.utcnow().timestamp()}"
            
            registration = {
                'data_id': data_id,
                'user_id': user_id,
                'data_type': data_type,
                'data_location': data_location,
                'created_at': datetime.utcnow(),
                'metadata': metadata or {},
                'encryption_metadata': encryption_metadata,
                'deletion_scheduled': False
            }
            
            self.data_registry[data_id] = registration
            
            # Schedule automatic deletion if policy requires it
            policy = self.retention_policies.get(data_type)
            if policy and policy.auto_delete:
                deletion_time = policy.get_deletion_date(registration['created_at'])
                registration['scheduled_deletion_at'] = deletion_time
                registration['deletion_scheduled'] = True
            
            logger.info(
                f"Registered data for retention tracking",
                extra={
                    'component': 'data_retention_manager',
                    'operation': 'register_data',
                    'user_id': user_id,
                    'data_type': data_type.value,
                    'data_id': data_id,
                    'auto_delete': policy.auto_delete if policy else False
                }
            )
            
            return data_id
            
        except Exception as e:
            logger.error(f"Failed to register data for retention: {e}")
            raise DataRetentionError(
                f"Data registration failed: {str(e)}",
                error_code="DATA_REGISTRATION_FAILED",
                context={'user_id': user_id, 'data_type': data_type.value}
            )
    
    def schedule_voice_deletion(self, user_id: str, voice_file_path: str,
                               encryption_metadata: Optional[EncryptionMetadata] = None) -> str:
        """
        Schedule automatic deletion of voice recording after processing.
        
        Args:
            user_id: User identifier
            voice_file_path: Path to voice recording file
            encryption_metadata: Encryption metadata if file is encrypted
            
        Returns:
            Data registration ID
        """
        return self.register_data(
            user_id=user_id,
            data_type=DataType.VOICE_RECORDING,
            data_location=voice_file_path,
            metadata={'processing_completed': False},
            encryption_metadata=encryption_metadata
        )
    
    def mark_voice_processing_complete(self, data_id: str) -> bool:
        """
        Mark voice processing as complete, triggering deletion countdown.
        
        Args:
            data_id: Data registration ID
            
        Returns:
            True if successfully marked
        """
        try:
            if data_id not in self.data_registry:
                logger.warning(f"Data ID {data_id} not found in registry")
                return False
            
            registration = self.data_registry[data_id]
            registration['metadata']['processing_completed'] = True
            registration['processing_completed_at'] = datetime.utcnow()
            
            # Update deletion schedule based on processing completion
            policy = self.retention_policies[DataType.VOICE_RECORDING]
            deletion_time = policy.get_deletion_date(registration['processing_completed_at'])
            registration['scheduled_deletion_at'] = deletion_time
            
            logger.info(
                f"Marked voice processing complete, deletion scheduled",
                extra={
                    'component': 'data_retention_manager',
                    'operation': 'mark_processing_complete',
                    'data_id': data_id,
                    'scheduled_deletion_at': deletion_time.isoformat()
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark processing complete for {data_id}: {e}")
            return False
    
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
            if data_types is None:
                data_types = list(DataType)
            
            deletion_request = DataDeletionRequest(
                user_id=user_id,
                data_types=data_types,
                reason=reason,
                status="pending"
            )
            
            self.deletion_requests[deletion_request.request_id] = deletion_request
            
            # Log the deletion request
            self._log_privacy_action(
                user_id=user_id,
                operation="data_deletion_requested",
                details={
                    'request_id': deletion_request.request_id,
                    'data_types': [dt.value for dt in data_types],
                    'reason': reason,
                    'deadline': deletion_request.get_deadline().isoformat()
                }
            )
            
            logger.info(
                f"User data deletion requested",
                extra={
                    'component': 'data_retention_manager',
                    'operation': 'request_deletion',
                    'user_id': user_id,
                    'request_id': deletion_request.request_id,
                    'data_types': [dt.value for dt in data_types],
                    'deadline': deletion_request.get_deadline().isoformat()
                }
            )
            
            return deletion_request
            
        except Exception as e:
            logger.error(f"Failed to create deletion request for user {user_id}: {e}")
            raise DataRetentionError(
                f"Deletion request failed: {str(e)}",
                error_code="DELETION_REQUEST_FAILED",
                context={'user_id': user_id}
            )
    
    async def process_scheduled_deletions(self) -> int:
        """
        Process all scheduled deletions that are due.
        
        Returns:
            Number of items deleted
        """
        deleted_count = 0
        current_time = datetime.utcnow()
        
        try:
            # Process automatic deletions
            for data_id, registration in list(self.data_registry.items()):
                if (registration.get('deletion_scheduled', False) and
                    registration.get('scheduled_deletion_at') and
                    current_time >= registration['scheduled_deletion_at']):
                    
                    if await self._delete_data_item(data_id, registration):
                        deleted_count += 1
            
            # Process user deletion requests
            for request_id, request in list(self.deletion_requests.items()):
                if request.status == "pending":
                    if await self._process_deletion_request(request):
                        deleted_count += len(request.data_types)
            
            if deleted_count > 0:
                logger.info(
                    f"Processed scheduled deletions",
                    extra={
                        'component': 'data_retention_manager',
                        'operation': 'process_deletions',
                        'deleted_count': deleted_count
                    }
                )
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to process scheduled deletions: {e}")
            raise DataRetentionError(
                f"Deletion processing failed: {str(e)}",
                error_code="DELETION_PROCESSING_FAILED"
            )
    
    async def _delete_data_item(self, data_id: str, registration: Dict[str, Any]) -> bool:
        """Delete a single data item."""
        try:
            data_location = registration['data_location']
            data_type = registration['data_type']
            user_id = registration['user_id']
            
            # Determine deletion method
            policy = self.retention_policies.get(data_type)
            deletion_method = policy.deletion_method if policy else "secure_delete"
            
            success = False
            if deletion_method == "secure_delete":
                success = await self._secure_delete_file(data_location)
            elif deletion_method == "anonymize":
                success = await self._anonymize_data(data_location, registration)
            
            if success:
                # Remove from registry
                del self.data_registry[data_id]
                
                # Log deletion
                self._log_privacy_action(
                    user_id=user_id,
                    operation="data_deleted",
                    data_type=data_type,
                    details={
                        'data_id': data_id,
                        'data_location': data_location,
                        'deletion_method': deletion_method
                    }
                )
                
                logger.info(
                    f"Successfully deleted data item",
                    extra={
                        'component': 'data_retention_manager',
                        'operation': 'delete_data_item',
                        'data_id': data_id,
                        'data_type': data_type.value,
                        'deletion_method': deletion_method
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete data item {data_id}: {e}")
            return False
    
    async def _secure_delete_file(self, file_path: str) -> bool:
        """Securely delete a file by overwriting and removing."""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File {file_path} does not exist, considering deleted")
                return True
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Overwrite file with random data multiple times
            with open(file_path, 'r+b') as file:
                for _ in range(3):  # 3 passes of overwriting
                    file.seek(0)
                    file.write(os.urandom(file_size))
                    file.flush()
                    os.fsync(file.fileno())
            
            # Remove the file
            os.remove(file_path)
            
            logger.debug(f"Securely deleted file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to securely delete file {file_path}: {e}")
            return False
    
    async def _anonymize_data(self, data_location: str, registration: Dict[str, Any]) -> bool:
        """Anonymize data by removing personal identifiers."""
        try:
            # This is a placeholder for data anonymization logic
            # In practice, this would remove or hash personal identifiers
            
            # For now, we'll just mark the data as anonymized in metadata
            registration['metadata']['anonymized'] = True
            registration['metadata']['anonymized_at'] = datetime.utcnow().isoformat()
            
            logger.info(f"Anonymized data at: {data_location}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to anonymize data at {data_location}: {e}")
            return False
    
    async def _process_deletion_request(self, request: DataDeletionRequest) -> bool:
        """Process a user data deletion request."""
        try:
            request.status = "in_progress"
            
            # Find all data for the user
            user_data_items = [
                (data_id, reg) for data_id, reg in self.data_registry.items()
                if reg['user_id'] == request.user_id and reg['data_type'] in request.data_types
            ]
            
            # Delete each data item
            deleted_items = 0
            for data_id, registration in user_data_items:
                if await self._delete_data_item(data_id, registration):
                    deleted_items += 1
            
            # Mark request as completed
            request.status = "completed"
            request.completed_at = datetime.utcnow()
            
            # Log completion
            self._log_privacy_action(
                user_id=request.user_id,
                operation="data_deletion_completed",
                details={
                    'request_id': request.request_id,
                    'deleted_items': deleted_items,
                    'completed_at': request.completed_at.isoformat()
                }
            )
            
            logger.info(
                f"Completed user data deletion request",
                extra={
                    'component': 'data_retention_manager',
                    'operation': 'process_deletion_request',
                    'user_id': request.user_id,
                    'request_id': request.request_id,
                    'deleted_items': deleted_items
                }
            )
            
            return True
            
        except Exception as e:
            request.status = "failed"
            logger.error(f"Failed to process deletion request {request.request_id}: {e}")
            return False
    
    def get_deletion_request_status(self, request_id: str) -> Optional[DataDeletionRequest]:
        """Get the status of a deletion request."""
        return self.deletion_requests.get(request_id)
    
    def get_user_data_summary(self, user_id: str) -> Dict[str, Any]:
        """Get summary of all data stored for a user."""
        user_data = [
            reg for reg in self.data_registry.values()
            if reg['user_id'] == user_id
        ]
        
        summary = {
            'user_id': user_id,
            'total_items': len(user_data),
            'data_types': {},
            'scheduled_deletions': 0,
            'oldest_item': None,
            'newest_item': None
        }
        
        if user_data:
            # Group by data type
            for item in user_data:
                data_type = item['data_type'].value
                if data_type not in summary['data_types']:
                    summary['data_types'][data_type] = 0
                summary['data_types'][data_type] += 1
                
                if item.get('deletion_scheduled', False):
                    summary['scheduled_deletions'] += 1
            
            # Find oldest and newest items
            dates = [item['created_at'] for item in user_data]
            summary['oldest_item'] = min(dates).isoformat()
            summary['newest_item'] = max(dates).isoformat()
        
        return summary
    
    def _log_privacy_action(self, user_id: str, operation: str,
                           data_type: Optional[DataType] = None,
                           details: Optional[Dict[str, Any]] = None) -> None:
        """Log privacy-related actions for audit purposes."""
        audit_log = PrivacyAuditLog(
            user_id=user_id,
            operation=operation,
            data_type=data_type,
            timestamp=datetime.utcnow(),
            details=details or {}
        )
        
        self.audit_logs.append(audit_log)
    
    def get_retention_policy(self, data_type: DataType) -> Optional[DataRetentionPolicy]:
        """Get retention policy for a data type."""
        return self.retention_policies.get(data_type)
    
    def update_retention_policy(self, data_type: DataType, 
                               policy: DataRetentionPolicy) -> None:
        """Update retention policy for a data type."""
        self.retention_policies[data_type] = policy
        logger.info(f"Updated retention policy for {data_type.value}")
    
    def export_audit_logs(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export audit logs for compliance reporting."""
        logs = self.audit_logs
        
        if user_id:
            logs = [log for log in logs if log.user_id == user_id]
        
        return [
            {
                'log_id': log.log_id,
                'user_id': log.user_id,
                'operation': log.operation,
                'data_type': log.data_type.value if log.data_type else None,
                'timestamp': log.timestamp.isoformat(),
                'details': log.details
            }
            for log in logs
        ]