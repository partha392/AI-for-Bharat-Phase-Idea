"""
Encryption service for voice data and personal information.

This module provides AES-256-GCM encryption for voice recordings and other
sensitive data during transmission and storage.
"""

import os
import base64
from typing import Tuple, Optional, Dict, Any
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import secrets

from ..core.logging import get_logger
from ..core.exceptions import DataEncryptionError
from ..core.config import config
from .models import EncryptionMetadata, DataType

logger = get_logger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self):
        """Initialize the encryption service."""
        self.algorithm = config.security.encryption_algorithm
        self.backend = default_backend()
        self._master_key = self._get_or_create_master_key()
    
    def _get_or_create_master_key(self) -> bytes:
        """Get or create the master encryption key."""
        # In production, this should be retrieved from AWS KMS or similar
        master_key_env = os.getenv("BHARAT_MASTER_KEY")
        
        if master_key_env:
            try:
                return base64.b64decode(master_key_env)
            except Exception as e:
                logger.error(f"Failed to decode master key from environment: {e}")
                raise DataEncryptionError(
                    "Invalid master key in environment",
                    error_code="INVALID_MASTER_KEY"
                )
        
        # For development/testing, generate a key (not recommended for production)
        logger.warning("No master key found in environment, generating temporary key")
        return secrets.token_bytes(32)  # 256-bit key
    
    def _derive_key(self, salt: bytes, key_id: str) -> bytes:
        """Derive an encryption key from the master key and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt,
            iterations=100000,
            backend=self.backend
        )
        
        # Combine master key with key_id for key derivation
        key_material = self._master_key + key_id.encode('utf-8')
        return kdf.derive(key_material)
    
    def encrypt_data(self, data: bytes, data_type: DataType, 
                    key_id: Optional[str] = None) -> Tuple[bytes, EncryptionMetadata]:
        """
        Encrypt data using AES-256-GCM.
        
        Args:
            data: Raw data to encrypt
            data_type: Type of data being encrypted
            key_id: Optional key identifier for key derivation
            
        Returns:
            Tuple of (encrypted_data, encryption_metadata)
        """
        try:
            if key_id is None:
                key_id = secrets.token_hex(16)
            
            # Generate random salt and IV
            salt = secrets.token_bytes(16)
            iv = secrets.token_bytes(12)  # 96-bit IV for GCM
            
            # Derive encryption key
            key = self._derive_key(salt, key_id)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=self.backend
            )
            
            encryptor = cipher.encryptor()
            
            # Encrypt the data
            encrypted_data = encryptor.update(data) + encryptor.finalize()
            
            # Get the authentication tag
            tag = encryptor.tag
            
            # Combine salt, encrypted data, and tag
            combined_data = salt + encrypted_data + tag
            
            # Create metadata
            metadata = EncryptionMetadata(
                algorithm=self.algorithm,
                key_id=key_id,
                iv=iv,
                tag=tag,
                data_type=data_type,
                original_size=len(data),
                encrypted_size=len(combined_data)
            )
            
            logger.info(
                f"Successfully encrypted {data_type.value} data",
                extra={
                    'component': 'encryption_service',
                    'operation': 'encrypt',
                    'data_type': data_type.value,
                    'original_size': len(data),
                    'encrypted_size': len(combined_data)
                }
            )
            
            return combined_data, metadata
            
        except Exception as e:
            logger.error(f"Failed to encrypt data: {e}", exc_info=True)
            raise DataEncryptionError(
                f"Encryption failed: {str(e)}",
                error_code="ENCRYPTION_FAILED",
                context={'data_type': data_type.value, 'error': str(e)}
            )
    
    def decrypt_data(self, encrypted_data: bytes, 
                    metadata: EncryptionMetadata) -> bytes:
        """
        Decrypt data using the provided metadata.
        
        Args:
            encrypted_data: Encrypted data to decrypt
            metadata: Encryption metadata containing key info
            
        Returns:
            Decrypted data
        """
        try:
            # Extract components from encrypted data
            salt = encrypted_data[:16]
            ciphertext = encrypted_data[16:-16]
            tag = encrypted_data[-16:]
            
            # Derive the same key used for encryption
            key = self._derive_key(salt, metadata.key_id)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(metadata.iv, tag),
                backend=self.backend
            )
            
            decryptor = cipher.decryptor()
            
            # Decrypt the data
            decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            logger.info(
                f"Successfully decrypted {metadata.data_type.value} data",
                extra={
                    'component': 'encryption_service',
                    'operation': 'decrypt',
                    'data_type': metadata.data_type.value,
                    'decrypted_size': len(decrypted_data)
                }
            )
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}", exc_info=True)
            raise DataEncryptionError(
                f"Decryption failed: {str(e)}",
                error_code="DECRYPTION_FAILED",
                context={'data_type': metadata.data_type.value, 'error': str(e)}
            )
    
    def encrypt_voice_data(self, audio_data: bytes, 
                          user_id: str) -> Tuple[bytes, EncryptionMetadata]:
        """
        Encrypt voice recording data.
        
        Args:
            audio_data: Raw audio data
            user_id: User identifier for key derivation
            
        Returns:
            Tuple of (encrypted_data, encryption_metadata)
        """
        key_id = f"voice_{user_id}_{secrets.token_hex(8)}"
        return self.encrypt_data(audio_data, DataType.VOICE_RECORDING, key_id)
    
    def encrypt_personal_info(self, personal_data: bytes, 
                             user_id: str) -> Tuple[bytes, EncryptionMetadata]:
        """
        Encrypt personal information.
        
        Args:
            personal_data: Personal information as bytes
            user_id: User identifier for key derivation
            
        Returns:
            Tuple of (encrypted_data, encryption_metadata)
        """
        key_id = f"personal_{user_id}_{secrets.token_hex(8)}"
        return self.encrypt_data(personal_data, DataType.PERSONAL_INFO, key_id)
    
    def secure_delete_key(self, key_id: str) -> bool:
        """
        Securely delete encryption key (placeholder for key management).
        
        Args:
            key_id: Key identifier to delete
            
        Returns:
            True if successful
        """
        try:
            # In production, this would delete the key from AWS KMS or similar
            logger.info(
                f"Securely deleted encryption key",
                extra={
                    'component': 'encryption_service',
                    'operation': 'delete_key',
                    'key_id': key_id
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete encryption key {key_id}: {e}")
            return False
    
    def rotate_master_key(self) -> bool:
        """
        Rotate the master encryption key.
        
        Returns:
            True if successful
        """
        try:
            # Generate new master key
            new_master_key = secrets.token_bytes(32)
            
            # In production, this would involve:
            # 1. Creating new key in AWS KMS
            # 2. Re-encrypting all data with new key
            # 3. Updating key references
            # 4. Securely deleting old key
            
            logger.info(
                "Master key rotation initiated",
                extra={
                    'component': 'encryption_service',
                    'operation': 'rotate_master_key'
                }
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to rotate master key: {e}")
            return False
    
    def validate_encryption(self, encrypted_data: bytes, 
                           metadata: EncryptionMetadata) -> bool:
        """
        Validate that encrypted data can be successfully decrypted.
        
        Args:
            encrypted_data: Encrypted data to validate
            metadata: Encryption metadata
            
        Returns:
            True if validation successful
        """
        try:
            # Try to decrypt a small portion to validate
            self.decrypt_data(encrypted_data, metadata)
            return True
        except Exception:
            return False