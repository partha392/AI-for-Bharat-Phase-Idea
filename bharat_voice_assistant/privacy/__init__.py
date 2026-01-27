"""
Privacy management module for the Bharat Voice Assistant.

This module provides comprehensive privacy protection including data encryption,
consent management, automatic data deletion, and compliance with privacy regulations.
"""

from .privacy_manager import PrivacyManager
from .encryption_service import EncryptionService
from .consent_manager import ConsentManager
from .data_retention_manager import DataRetentionManager
from .models import ConsentRecord, DataRetentionPolicy, EncryptionMetadata

__all__ = [
    'PrivacyManager',
    'EncryptionService', 
    'ConsentManager',
    'DataRetentionManager',
    'ConsentRecord',
    'DataRetentionPolicy',
    'EncryptionMetadata'
]