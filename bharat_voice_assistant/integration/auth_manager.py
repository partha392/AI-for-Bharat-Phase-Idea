"""
Authentication and authorization management for government APIs.

This module handles various authentication methods used by government
portals including API keys, OAuth2, JWT tokens, and digital certificates.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import aiohttp
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

from .models import (
    GovernmentPortal, APICredentials, AuthMethod, AuthToken
)
from ..core.exceptions import (
    AuthenticationError, GovernmentAPIError, ValidationError
)
from ..core.config import config

logger = logging.getLogger(__name__)


class AuthenticationManager:
    """
    Manages authentication with government APIs.
    
    Supports multiple authentication methods including API keys,
    OAuth2, JWT tokens, basic auth, and digital certificates.
    """
    
    def __init__(self):
        """Initialize the authentication manager."""
        self.token_cache: Dict[str, AuthToken] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info("AuthenticationManager initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    async def get_auth_headers(self, portal: GovernmentPortal) -> Dict[str, str]:
        """
        Get authentication headers for a government portal.
        
        Args:
            portal: Government portal configuration
            
        Returns:
            Dictionary of authentication headers
        """
        if not portal.credentials:
            return {}
        
        credentials = portal.credentials
        
        try:
            if credentials.auth_method == AuthMethod.API_KEY:
                return await self._get_api_key_headers(credentials)
            
            elif credentials.auth_method == AuthMethod.OAUTH2:
                return await self._get_oauth2_headers(portal, credentials)
            
            elif credentials.auth_method == AuthMethod.JWT_TOKEN:
                return await self._get_jwt_headers(portal, credentials)
            
            elif credentials.auth_method == AuthMethod.BASIC_AUTH:
                return await self._get_basic_auth_headers(credentials)
            
            elif credentials.auth_method == AuthMethod.CERTIFICATE:
                return await self._get_certificate_headers(credentials)
            
            elif credentials.auth_method == AuthMethod.DIGITAL_SIGNATURE:
                return await self._get_digital_signature_headers(credentials)
            
            else:
                logger.warning(f"Unsupported auth method: {credentials.auth_method}")
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get auth headers for {portal.id}: {e}")
            raise AuthenticationError(
                f"Authentication failed for portal {portal.id}: {e}",
                error_code="AUTH_HEADER_ERROR"
            )
    
    async def _get_api_key_headers(self, credentials: APICredentials) -> Dict[str, str]:
        """Get API key authentication headers."""
        if not credentials.api_key:
            raise AuthenticationError(
                "API key is required for API key authentication",
                error_code="MISSING_API_KEY"
            )
        
        headers = {'X-API-Key': credentials.api_key}
        headers.update(credentials.additional_headers)
        
        return headers
    
    async def _get_oauth2_headers(self, portal: GovernmentPortal, 
                                credentials: APICredentials) -> Dict[str, str]:
        """Get OAuth2 authentication headers."""
        # Check if we have a valid cached token
        cached_token = self.token_cache.get(portal.id)
        if cached_token and cached_token.is_valid():
            return cached_token.to_header()
        
        # Get new token
        token = await self._get_oauth2_token(credentials)
        self.token_cache[portal.id] = token
        
        return token.to_header()
    
    async def _get_oauth2_token(self, credentials: APICredentials) -> AuthToken:
        """Get OAuth2 access token."""
        if not credentials.token_endpoint:
            raise AuthenticationError(
                "Token endpoint is required for OAuth2 authentication",
                error_code="MISSING_TOKEN_ENDPOINT"
            )
        
        if not credentials.client_id or not credentials.client_secret:
            raise AuthenticationError(
                "Client ID and secret are required for OAuth2 authentication",
                error_code="MISSING_OAUTH2_CREDENTIALS"
            )
        
        await self._ensure_session()
        
        # Prepare token request
        data = {
            'grant_type': 'client_credentials',
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret
        }
        
        if credentials.scope:
            data['scope'] = credentials.scope
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            async with self.session.post(credentials.token_endpoint, 
                                       data=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AuthenticationError(
                        f"OAuth2 token request failed: {error_text}",
                        error_code="OAUTH2_TOKEN_ERROR"
                    )
                
                token_data = await response.json()
                
                # Parse token response
                access_token = token_data.get('access_token')
                if not access_token:
                    raise AuthenticationError(
                        "No access token in OAuth2 response",
                        error_code="MISSING_ACCESS_TOKEN"
                    )
                
                token_type = token_data.get('token_type', 'Bearer')
                expires_in = token_data.get('expires_in')
                refresh_token = token_data.get('refresh_token')
                scope = token_data.get('scope')
                
                # Calculate expiration time
                expires_at = None
                if expires_in:
                    expires_at = datetime.now() + timedelta(seconds=int(expires_in) - 60)  # 1 minute buffer
                
                return AuthToken(
                    token=access_token,
                    token_type=token_type,
                    expires_at=expires_at,
                    refresh_token=refresh_token,
                    scope=scope
                )
                
        except aiohttp.ClientError as e:
            raise AuthenticationError(
                f"OAuth2 token request failed: {e}",
                error_code="OAUTH2_NETWORK_ERROR"
            )
    
    async def _get_jwt_headers(self, portal: GovernmentPortal, 
                             credentials: APICredentials) -> Dict[str, str]:
        """Get JWT authentication headers."""
        # Check if we have a valid cached token
        cached_token = self.token_cache.get(portal.id)
        if cached_token and cached_token.is_valid():
            return cached_token.to_header()
        
        # Generate new JWT token
        token = await self._generate_jwt_token(credentials)
        self.token_cache[portal.id] = token
        
        return token.to_header()
    
    async def _generate_jwt_token(self, credentials: APICredentials) -> AuthToken:
        """Generate JWT token for authentication."""
        if not credentials.client_id or not credentials.private_key_path:
            raise AuthenticationError(
                "Client ID and private key are required for JWT authentication",
                error_code="MISSING_JWT_CREDENTIALS"
            )
        
        try:
            # Load private key
            with open(credentials.private_key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None  # Assuming no password for simplicity
                )
            
            # Create JWT payload
            now = datetime.utcnow()
            payload = {
                'iss': credentials.client_id,  # Issuer
                'sub': credentials.client_id,  # Subject
                'aud': credentials.token_endpoint or 'government-api',  # Audience
                'iat': int(now.timestamp()),  # Issued at
                'exp': int((now + timedelta(hours=1)).timestamp()),  # Expires
                'jti': hashlib.sha256(f"{credentials.client_id}{now.timestamp()}".encode()).hexdigest()[:16]  # JWT ID
            }
            
            # Generate JWT token
            token = jwt.encode(payload, private_key, algorithm='RS256')
            
            # Calculate expiration
            expires_at = now + timedelta(minutes=55)  # 5 minute buffer
            
            return AuthToken(
                token=token,
                token_type='Bearer',
                expires_at=expires_at
            )
            
        except Exception as e:
            raise AuthenticationError(
                f"Failed to generate JWT token: {e}",
                error_code="JWT_GENERATION_ERROR"
            )
    
    async def _get_basic_auth_headers(self, credentials: APICredentials) -> Dict[str, str]:
        """Get basic authentication headers."""
        if not credentials.username or not credentials.password:
            raise AuthenticationError(
                "Username and password are required for basic authentication",
                error_code="MISSING_BASIC_AUTH_CREDENTIALS"
            )
        
        # Encode credentials
        auth_string = f"{credentials.username}:{credentials.password}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        headers = {'Authorization': f'Basic {encoded_auth}'}
        headers.update(credentials.additional_headers)
        
        return headers
    
    async def _get_certificate_headers(self, credentials: APICredentials) -> Dict[str, str]:
        """Get certificate-based authentication headers."""
        if not credentials.certificate_path:
            raise AuthenticationError(
                "Certificate path is required for certificate authentication",
                error_code="MISSING_CERTIFICATE"
            )
        
        try:
            # Load certificate
            with open(credentials.certificate_path, 'rb') as cert_file:
                cert_data = cert_file.read()
                certificate = x509.load_pem_x509_certificate(cert_data)
            
            # Extract certificate information
            subject = certificate.subject
            serial_number = certificate.serial_number
            
            # Create certificate-based headers
            headers = {
                'X-Client-Certificate': base64.b64encode(cert_data).decode(),
                'X-Client-Certificate-Serial': str(serial_number),
                'X-Client-Certificate-Subject': str(subject)
            }
            
            headers.update(credentials.additional_headers)
            return headers
            
        except Exception as e:
            raise AuthenticationError(
                f"Failed to load certificate: {e}",
                error_code="CERTIFICATE_LOAD_ERROR"
            )
    
    async def _get_digital_signature_headers(self, credentials: APICredentials) -> Dict[str, str]:
        """Get digital signature authentication headers."""
        if not credentials.private_key_path or not credentials.client_id:
            raise AuthenticationError(
                "Private key and client ID are required for digital signature authentication",
                error_code="MISSING_SIGNATURE_CREDENTIALS"
            )
        
        try:
            # Load private key
            with open(credentials.private_key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
            
            # Create signature payload
            timestamp = str(int(time.time()))
            nonce = hashlib.sha256(f"{credentials.client_id}{timestamp}".encode()).hexdigest()[:16]
            
            # Data to sign
            sign_data = f"{credentials.client_id}{timestamp}{nonce}".encode()
            
            # Create signature
            signature = private_key.sign(
                sign_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Encode signature
            encoded_signature = base64.b64encode(signature).decode()
            
            headers = {
                'X-Client-ID': credentials.client_id,
                'X-Timestamp': timestamp,
                'X-Nonce': nonce,
                'X-Signature': encoded_signature,
                'X-Signature-Algorithm': 'RSA-PSS-SHA256'
            }
            
            headers.update(credentials.additional_headers)
            return headers
            
        except Exception as e:
            raise AuthenticationError(
                f"Failed to create digital signature: {e}",
                error_code="SIGNATURE_CREATION_ERROR"
            )
    
    async def refresh_token(self, portal: GovernmentPortal) -> bool:
        """
        Refresh authentication token for a portal.
        
        Args:
            portal: Government portal configuration
            
        Returns:
            True if token was refreshed successfully
        """
        if not portal.credentials:
            return False
        
        try:
            # Remove cached token
            if portal.id in self.token_cache:
                del self.token_cache[portal.id]
            
            # Get new token
            await self.get_auth_headers(portal)
            
            logger.info(f"Token refreshed for portal {portal.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh token for {portal.id}: {e}")
            return False
    
    def validate_credentials(self, credentials: APICredentials) -> ValidationResult:
        """
        Validate authentication credentials.
        
        Args:
            credentials: Credentials to validate
            
        Returns:
            ValidationResult with validation status
        """
        from .models import ValidationResult
        
        result = ValidationResult(is_valid=True)
        
        # Check required fields based on auth method
        if credentials.auth_method == AuthMethod.API_KEY:
            if not credentials.api_key:
                result.add_error("API key is required for API key authentication")
        
        elif credentials.auth_method == AuthMethod.OAUTH2:
            if not credentials.client_id:
                result.add_error("Client ID is required for OAuth2 authentication")
            if not credentials.client_secret:
                result.add_error("Client secret is required for OAuth2 authentication")
            if not credentials.token_endpoint:
                result.add_error("Token endpoint is required for OAuth2 authentication")
        
        elif credentials.auth_method == AuthMethod.JWT_TOKEN:
            if not credentials.client_id:
                result.add_error("Client ID is required for JWT authentication")
            if not credentials.private_key_path:
                result.add_error("Private key path is required for JWT authentication")
        
        elif credentials.auth_method == AuthMethod.BASIC_AUTH:
            if not credentials.username:
                result.add_error("Username is required for basic authentication")
            if not credentials.password:
                result.add_error("Password is required for basic authentication")
        
        elif credentials.auth_method == AuthMethod.CERTIFICATE:
            if not credentials.certificate_path:
                result.add_error("Certificate path is required for certificate authentication")
        
        elif credentials.auth_method == AuthMethod.DIGITAL_SIGNATURE:
            if not credentials.client_id:
                result.add_error("Client ID is required for digital signature authentication")
            if not credentials.private_key_path:
                result.add_error("Private key path is required for digital signature authentication")
        
        # Validate file paths exist
        if credentials.certificate_path:
            try:
                with open(credentials.certificate_path, 'rb'):
                    pass
            except FileNotFoundError:
                result.add_error(f"Certificate file not found: {credentials.certificate_path}")
            except Exception as e:
                result.add_error(f"Cannot read certificate file: {e}")
        
        if credentials.private_key_path:
            try:
                with open(credentials.private_key_path, 'rb'):
                    pass
            except FileNotFoundError:
                result.add_error(f"Private key file not found: {credentials.private_key_path}")
            except Exception as e:
                result.add_error(f"Cannot read private key file: {e}")
        
        return result
    
    def get_cached_token_info(self, portal_id: str) -> Optional[Dict[str, Any]]:
        """Get information about cached token."""
        token = self.token_cache.get(portal_id)
        if not token:
            return None
        
        return {
            'token_type': token.token_type,
            'expires_at': token.expires_at.isoformat() if token.expires_at else None,
            'is_valid': token.is_valid(),
            'is_expired': token.is_expired(),
            'scope': token.scope,
            'created_at': token.created_at.isoformat()
        }
    
    def clear_token_cache(self, portal_id: Optional[str] = None):
        """Clear token cache for specific portal or all portals."""
        if portal_id:
            if portal_id in self.token_cache:
                del self.token_cache[portal_id]
                logger.info(f"Cleared token cache for portal {portal_id}")
        else:
            self.token_cache.clear()
            logger.info("Cleared all token cache")
    
    async def test_authentication(self, portal: GovernmentPortal) -> bool:
        """
        Test authentication with a government portal.
        
        Args:
            portal: Government portal to test
            
        Returns:
            True if authentication is successful
        """
        try:
            headers = await self.get_auth_headers(portal)
            
            # If we got headers without exception, authentication is likely working
            # For a more thorough test, we would make an actual API call
            return bool(headers)
            
        except Exception as e:
            logger.error(f"Authentication test failed for {portal.id}: {e}")
            return False