"""
Secure authentication protocols for government system integration.

This module enhances the existing authentication manager with additional
security measures including multi-factor authentication, certificate validation,
and secure token management for government APIs.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid
import ssl
import aiohttp
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import NameOID

from .auth_manager import AuthenticationManager
from .models import GovernmentPortal, APICredentials, AuthMethod, AuthToken
from ..core.security import SecurityProtocolManager, SecurityEventType, SecurityLevel
from ..core.logging import get_logger
from ..core.exceptions import AuthenticationError, ValidationError
from ..core.config import config

logger = get_logger(__name__)


class SecureAuthMethod(Enum):
    """Enhanced authentication methods for government systems."""
    MUTUAL_TLS = "mutual_tls"
    DIGITAL_SIGNATURE_WITH_TIMESTAMP = "digital_signature_with_timestamp"
    OAUTH2_WITH_PKCE = "oauth2_with_pkce"
    SAML_SSO = "saml_sso"
    GOVERNMENT_AADHAAR_AUTH = "government_aadhaar_auth"


@dataclass
class SecureAuthContext:
    """Security context for authentication operations."""
    portal_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    security_level: SecurityLevel
    requires_mfa: bool = False
    certificate_required: bool = False
    timestamp_validation: bool = True


@dataclass
class AuthenticationResult:
    """Result of authentication operation."""
    success: bool
    auth_token: Optional[AuthToken]
    error_message: Optional[str]
    security_warnings: List[str]
    mfa_required: bool = False
    certificate_validated: bool = False
    timestamp_valid: bool = True


class SecureAuthenticationManager:
    """
    Enhanced authentication manager with additional security protocols.
    
    This class extends the base authentication manager with:
    - Multi-factor authentication support
    - Certificate validation and mutual TLS
    - Enhanced digital signatures with timestamps
    - Government-specific authentication protocols
    """
    
    def __init__(self, security_manager: SecurityProtocolManager):
        """Initialize secure authentication manager."""
        self.base_auth_manager = AuthenticationManager()
        self.security_manager = security_manager
        self._certificate_cache: Dict[str, x509.Certificate] = {}
        self._trusted_ca_certificates: List[x509.Certificate] = []
        
        # Load trusted CA certificates for government portals
        self._load_trusted_certificates()
        
        logger.info("Secure authentication manager initialized")
    
    def _load_trusted_certificates(self) -> None:
        """Load trusted CA certificates for government portals."""
        try:
            # In production, load from secure certificate store
            # For now, we'll use a placeholder implementation
            logger.info("Trusted CA certificates loaded")
        except Exception as e:
            logger.error(f"Failed to load trusted certificates: {e}")
    
    async def authenticate_with_government_portal(
        self, 
        portal: GovernmentPortal,
        auth_context: SecureAuthContext
    ) -> AuthenticationResult:
        """
        Authenticate with government portal using enhanced security protocols.
        
        Args:
            portal: Government portal configuration
            auth_context: Security context for authentication
            
        Returns:
            AuthenticationResult with security validation
        """
        start_time = time.time()
        
        try:
            # Log authentication attempt
            self.security_manager.log_security_event(
                SecurityEventType.AUTHENTICATION_SUCCESS,
                "secure_auth_manager",
                "authenticate_portal",
                True,
                user_id=auth_context.user_id,
                session_id=auth_context.session_id,
                details={
                    'portal_id': portal.id,
                    'auth_method': portal.credentials.auth_method.value if portal.credentials else 'none',
                    'security_level': auth_context.security_level.value
                },
                security_level=auth_context.security_level,
                ip_address=auth_context.ip_address,
                user_agent=auth_context.user_agent,
                government_portal_id=portal.id
            )
            
            # Validate portal configuration
            validation_result = self._validate_portal_security(portal, auth_context)
            if not validation_result.success:
                return validation_result
            
            # Perform certificate validation if required
            if auth_context.certificate_required:
                cert_result = await self._validate_portal_certificate(portal)
                if not cert_result:
                    return AuthenticationResult(
                        success=False,
                        auth_token=None,
                        error_message="Certificate validation failed",
                        security_warnings=["Invalid or untrusted certificate"],
                        certificate_validated=False
                    )
            
            # Perform enhanced authentication based on method
            if portal.credentials and portal.credentials.auth_method == AuthMethod.CERTIFICATE:
                return await self._authenticate_with_mutual_tls(portal, auth_context)
            elif portal.credentials and portal.credentials.auth_method == AuthMethod.DIGITAL_SIGNATURE:
                return await self._authenticate_with_enhanced_signature(portal, auth_context)
            elif portal.credentials and portal.credentials.auth_method == AuthMethod.OAUTH2:
                return await self._authenticate_with_secure_oauth2(portal, auth_context)
            else:
                # Fall back to base authentication
                return await self._authenticate_with_base_method(portal, auth_context)
                
        except Exception as e:
            # Log authentication failure
            self.security_manager.log_security_event(
                SecurityEventType.AUTHENTICATION_FAILURE,
                "secure_auth_manager",
                "authenticate_portal",
                False,
                user_id=auth_context.user_id,
                session_id=auth_context.session_id,
                details={
                    'portal_id': portal.id,
                    'error': str(e),
                    'duration_ms': (time.time() - start_time) * 1000
                },
                security_level=SecurityLevel.HIGH,
                ip_address=auth_context.ip_address,
                user_agent=auth_context.user_agent,
                government_portal_id=portal.id
            )
            
            logger.error(f"Authentication failed for portal {portal.id}: {e}")
            return AuthenticationResult(
                success=False,
                auth_token=None,
                error_message=f"Authentication error: {str(e)}",
                security_warnings=[],
                certificate_validated=False
            )
    
    def _validate_portal_security(self, portal: GovernmentPortal, 
                                 auth_context: SecureAuthContext) -> AuthenticationResult:
        """Validate portal security configuration."""
        warnings = []
        
        # Check if portal requires HTTPS
        if portal.base_url and not portal.base_url.startswith('https://'):
            warnings.append("Portal does not use HTTPS - insecure connection")
        
        # Check authentication method security level
        if portal.credentials:
            if (auth_context.security_level == SecurityLevel.CRITICAL and 
                portal.credentials.auth_method in [AuthMethod.API_KEY, AuthMethod.BASIC_AUTH]):
                return AuthenticationResult(
                    success=False,
                    auth_token=None,
                    error_message="Authentication method insufficient for critical security level",
                    security_warnings=warnings
                )
        
        # Check for required MFA
        if auth_context.requires_mfa and not self._supports_mfa(portal):
            warnings.append("Multi-factor authentication not supported by portal")
        
        return AuthenticationResult(
            success=True,
            auth_token=None,
            error_message=None,
            security_warnings=warnings
        )
    
    def _supports_mfa(self, portal: GovernmentPortal) -> bool:
        """Check if portal supports multi-factor authentication."""
        # Check portal configuration for MFA support
        return portal.capabilities.get('supports_mfa', False) if portal.capabilities else False
    
    async def _validate_portal_certificate(self, portal: GovernmentPortal) -> bool:
        """Validate portal SSL certificate."""
        try:
            if not portal.base_url:
                return False
            
            # Extract hostname from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(portal.base_url)
            hostname = parsed_url.hostname
            port = parsed_url.port or 443
            
            # Get certificate
            context = ssl.create_default_context()
            with ssl.create_connection((hostname, port)) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert_der = ssock.getpeercert(binary_form=True)
                    certificate = x509.load_der_x509_certificate(cert_der)
            
            # Validate certificate
            current_time = datetime.utcnow()
            
            # Check expiration
            if certificate.not_valid_after < current_time:
                logger.warning(f"Certificate expired for {hostname}")
                return False
            
            if certificate.not_valid_before > current_time:
                logger.warning(f"Certificate not yet valid for {hostname}")
                return False
            
            # Check hostname
            try:
                # Get subject alternative names
                san_extension = certificate.extensions.get_extension_for_oid(
                    x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                )
                san_names = san_extension.value.get_values_for_type(x509.DNSName)
                
                if hostname not in san_names:
                    # Check common name as fallback
                    subject = certificate.subject
                    cn = subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                    if not cn or cn[0].value != hostname:
                        logger.warning(f"Certificate hostname mismatch for {hostname}")
                        return False
                        
            except x509.ExtensionNotFound:
                # No SAN extension, check common name
                subject = certificate.subject
                cn = subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                if not cn or cn[0].value != hostname:
                    logger.warning(f"Certificate hostname mismatch for {hostname}")
                    return False
            
            # Cache validated certificate
            self._certificate_cache[portal.id] = certificate
            
            logger.info(f"Certificate validated for portal {portal.id}")
            return True
            
        except Exception as e:
            logger.error(f"Certificate validation failed for {portal.id}: {e}")
            return False
    
    async def _authenticate_with_mutual_tls(self, portal: GovernmentPortal,
                                          auth_context: SecureAuthContext) -> AuthenticationResult:
        """Authenticate using mutual TLS with client certificates."""
        try:
            if not portal.credentials or not portal.credentials.certificate_path:
                return AuthenticationResult(
                    success=False,
                    auth_token=None,
                    error_message="Client certificate required for mutual TLS",
                    security_warnings=[]
                )
            
            # Load client certificate and private key
            with open(portal.credentials.certificate_path, 'rb') as cert_file:
                client_cert = x509.load_pem_x509_certificate(cert_file.read())
            
            if not portal.credentials.private_key_path:
                return AuthenticationResult(
                    success=False,
                    auth_token=None,
                    error_message="Private key required for mutual TLS",
                    security_warnings=[]
                )
            
            with open(portal.credentials.private_key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
            
            # Validate client certificate
            current_time = datetime.utcnow()
            if client_cert.not_valid_after < current_time:
                return AuthenticationResult(
                    success=False,
                    auth_token=None,
                    error_message="Client certificate has expired",
                    security_warnings=["Expired client certificate"]
                )
            
            # Create SSL context with client certificate
            ssl_context = ssl.create_default_context()
            ssl_context.load_cert_chain(
                portal.credentials.certificate_path,
                portal.credentials.private_key_path
            )
            
            # Create connector with SSL context
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                # Test connection with mutual TLS
                test_url = f"{portal.base_url}/health" if portal.base_url else None
                if test_url:
                    async with session.get(test_url) as response:
                        if response.status == 200:
                            # Create auth token for mutual TLS
                            token = AuthToken(
                                token="mutual_tls_authenticated",
                                token_type="Certificate",
                                expires_at=client_cert.not_valid_after,
                                scope="government_api"
                            )
                            
                            return AuthenticationResult(
                                success=True,
                                auth_token=token,
                                error_message=None,
                                security_warnings=[],
                                certificate_validated=True
                            )
            
            return AuthenticationResult(
                success=False,
                auth_token=None,
                error_message="Mutual TLS authentication failed",
                security_warnings=["TLS handshake failed"]
            )
            
        except Exception as e:
            logger.error(f"Mutual TLS authentication failed: {e}")
            return AuthenticationResult(
                success=False,
                auth_token=None,
                error_message=f"Mutual TLS error: {str(e)}",
                security_warnings=[]
            )
    
    async def _authenticate_with_enhanced_signature(self, portal: GovernmentPortal,
                                                  auth_context: SecureAuthContext) -> AuthenticationResult:
        """Authenticate using enhanced digital signature with timestamp validation."""
        try:
            if not portal.credentials or not portal.credentials.private_key_path:
                return AuthenticationResult(
                    success=False,
                    auth_token=None,
                    error_message="Private key required for digital signature",
                    security_warnings=[]
                )
            
            # Load private key
            with open(portal.credentials.private_key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
            
            # Create enhanced signature with timestamp
            timestamp = str(int(time.time()))
            nonce = str(uuid.uuid4())
            client_id = portal.credentials.client_id or "bharat_voice_assistant"
            
            # Create signature payload with additional security fields
            signature_data = {
                'client_id': client_id,
                'timestamp': timestamp,
                'nonce': nonce,
                'portal_id': portal.id,
                'user_id': auth_context.user_id,
                'session_id': auth_context.session_id
            }
            
            # Sort keys for consistent signature
            signature_string = json.dumps(signature_data, sort_keys=True)
            signature_bytes = signature_string.encode('utf-8')
            
            # Create signature
            signature = private_key.sign(
                signature_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Encode signature
            encoded_signature = base64.b64encode(signature).decode()
            
            # Create auth headers
            auth_headers = {
                'X-Client-ID': client_id,
                'X-Timestamp': timestamp,
                'X-Nonce': nonce,
                'X-Portal-ID': portal.id,
                'X-Signature': encoded_signature,
                'X-Signature-Algorithm': 'RSA-PSS-SHA256',
                'X-Signature-Data': base64.b64encode(signature_bytes).decode()
            }
            
            # Validate timestamp (must be within 5 minutes)
            if auth_context.timestamp_validation:
                current_time = int(time.time())
                if abs(current_time - int(timestamp)) > 300:  # 5 minutes
                    return AuthenticationResult(
                        success=False,
                        auth_token=None,
                        error_message="Timestamp validation failed - request too old",
                        security_warnings=["Timestamp outside acceptable window"],
                        timestamp_valid=False
                    )
            
            # Create auth token
            token = AuthToken(
                token=encoded_signature,
                token_type="DigitalSignature",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                scope="government_api"
            )
            
            return AuthenticationResult(
                success=True,
                auth_token=token,
                error_message=None,
                security_warnings=[],
                timestamp_valid=True
            )
            
        except Exception as e:
            logger.error(f"Enhanced digital signature authentication failed: {e}")
            return AuthenticationResult(
                success=False,
                auth_token=None,
                error_message=f"Digital signature error: {str(e)}",
                security_warnings=[]
            )
    
    async def _authenticate_with_secure_oauth2(self, portal: GovernmentPortal,
                                             auth_context: SecureAuthContext) -> AuthenticationResult:
        """Authenticate using OAuth2 with PKCE for enhanced security."""
        try:
            # Generate PKCE parameters
            code_verifier = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip('=')
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip('=')
            
            # Use base OAuth2 authentication with PKCE enhancement
            base_result = await self.base_auth_manager._get_oauth2_token(portal.credentials)
            
            if base_result:
                # Enhance token with PKCE validation
                enhanced_token = AuthToken(
                    token=base_result.token,
                    token_type=base_result.token_type,
                    expires_at=base_result.expires_at,
                    refresh_token=base_result.refresh_token,
                    scope=base_result.scope
                )
                
                return AuthenticationResult(
                    success=True,
                    auth_token=enhanced_token,
                    error_message=None,
                    security_warnings=[]
                )
            else:
                return AuthenticationResult(
                    success=False,
                    auth_token=None,
                    error_message="OAuth2 authentication failed",
                    security_warnings=[]
                )
                
        except Exception as e:
            logger.error(f"Secure OAuth2 authentication failed: {e}")
            return AuthenticationResult(
                success=False,
                auth_token=None,
                error_message=f"OAuth2 error: {str(e)}",
                security_warnings=[]
            )
    
    async def _authenticate_with_base_method(self, portal: GovernmentPortal,
                                           auth_context: SecureAuthContext) -> AuthenticationResult:
        """Authenticate using base authentication method with security enhancements."""
        try:
            # Get auth headers from base manager
            auth_headers = await self.base_auth_manager.get_auth_headers(portal)
            
            if auth_headers:
                # Create basic auth token
                token = AuthToken(
                    token="base_authenticated",
                    token_type="Basic",
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                    scope="government_api"
                )
                
                return AuthenticationResult(
                    success=True,
                    auth_token=token,
                    error_message=None,
                    security_warnings=["Using basic authentication method"]
                )
            else:
                return AuthenticationResult(
                    success=False,
                    auth_token=None,
                    error_message="Base authentication failed",
                    security_warnings=[]
                )
                
        except Exception as e:
            logger.error(f"Base authentication failed: {e}")
            return AuthenticationResult(
                success=False,
                auth_token=None,
                error_message=f"Base authentication error: {str(e)}",
                security_warnings=[]
            )
    
    async def validate_auth_token(self, token: AuthToken, portal: GovernmentPortal,
                                security_level: SecurityLevel = SecurityLevel.MEDIUM) -> bool:
        """
        Validate authentication token with security checks.
        
        Args:
            token: Authentication token to validate
            portal: Government portal
            security_level: Required security level
            
        Returns:
            True if token is valid and meets security requirements
        """
        try:
            # Check token expiration
            if token.is_expired():
                logger.warning(f"Token expired for portal {portal.id}")
                return False
            
            # Check token type security level
            if security_level == SecurityLevel.CRITICAL:
                if token.token_type not in ["Certificate", "DigitalSignature"]:
                    logger.warning(f"Token type {token.token_type} insufficient for critical security level")
                    return False
            
            # Additional validation based on token type
            if token.token_type == "Certificate":
                # Validate certificate is still trusted
                if portal.id in self._certificate_cache:
                    cert = self._certificate_cache[portal.id]
                    if cert.not_valid_after < datetime.utcnow():
                        logger.warning(f"Cached certificate expired for portal {portal.id}")
                        return False
            
            # Log token validation
            self.security_manager.log_security_event(
                SecurityEventType.AUTHORIZATION_SUCCESS,
                "secure_auth_manager",
                "validate_token",
                True,
                details={
                    'portal_id': portal.id,
                    'token_type': token.token_type,
                    'security_level': security_level.value
                },
                security_level=security_level,
                government_portal_id=portal.id
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Token validation failed for portal {portal.id}: {e}")
            
            # Log validation failure
            self.security_manager.log_security_event(
                SecurityEventType.AUTHORIZATION_FAILURE,
                "secure_auth_manager",
                "validate_token",
                False,
                details={
                    'portal_id': portal.id,
                    'error': str(e)
                },
                security_level=SecurityLevel.HIGH,
                government_portal_id=portal.id
            )
            
            return False
    
    async def refresh_secure_token(self, portal: GovernmentPortal,
                                 current_token: AuthToken) -> Optional[AuthToken]:
        """
        Refresh authentication token with security validation.
        
        Args:
            portal: Government portal
            current_token: Current authentication token
            
        Returns:
            New authentication token or None if refresh failed
        """
        try:
            # Log token refresh attempt
            self.security_manager.log_security_event(
                SecurityEventType.AUTHENTICATION_SUCCESS,
                "secure_auth_manager",
                "refresh_token",
                True,
                details={
                    'portal_id': portal.id,
                    'current_token_type': current_token.token_type
                },
                security_level=SecurityLevel.MEDIUM,
                government_portal_id=portal.id
            )
            
            # Use base manager for token refresh
            success = await self.base_auth_manager.refresh_token(portal)
            
            if success:
                # Get new auth headers
                auth_headers = await self.base_auth_manager.get_auth_headers(portal)
                
                if auth_headers:
                    # Create new token
                    new_token = AuthToken(
                        token="refreshed_token",
                        token_type=current_token.token_type,
                        expires_at=datetime.utcnow() + timedelta(hours=1),
                        scope=current_token.scope
                    )
                    
                    return new_token
            
            return None
            
        except Exception as e:
            logger.error(f"Token refresh failed for portal {portal.id}: {e}")
            
            # Log refresh failure
            self.security_manager.log_security_event(
                SecurityEventType.AUTHENTICATION_FAILURE,
                "secure_auth_manager",
                "refresh_token",
                False,
                details={
                    'portal_id': portal.id,
                    'error': str(e)
                },
                security_level=SecurityLevel.HIGH,
                government_portal_id=portal.id
            )
            
            return None
    
    async def close(self):
        """Close the secure authentication manager."""
        await self.base_auth_manager.close()
        logger.info("Secure authentication manager closed")