"""
Configuration loader for government portal integration.

This module loads government portal configurations from various sources
including configuration files, environment variables, and databases.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from .models import (
    GovernmentPortal, IntegrationConfig, APICredentials, APIEndpoint,
    AuthMethod, DataFormat, PortalType
)
from ..core.exceptions import ConfigurationError
from ..core.config import config

logger = logging.getLogger(__name__)


class GovernmentPortalConfigLoader:
    """
    Loads government portal configurations from various sources.
    
    Supports loading from YAML files, JSON files, environment variables,
    and database configurations with proper validation and error handling.
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the configuration loader."""
        self.config_dir = Path(config_dir or "config/government_portals")
        self.loaded_portals: Dict[str, GovernmentPortal] = {}
        logger.info(f"GovernmentPortalConfigLoader initialized with config_dir: {self.config_dir}")
    
    def load_integration_config(self) -> IntegrationConfig:
        """
        Load complete integration configuration.
        
        Returns:
            IntegrationConfig with all loaded portals and settings
        """
        try:
            # Load portals from various sources
            portals = []
            
            # Load from configuration files
            file_portals = self._load_from_files()
            portals.extend(file_portals)
            
            # Load from environment variables
            env_portals = self._load_from_environment()
            portals.extend(env_portals)
            
            # Load from database (if configured)
            db_portals = self._load_from_database()
            portals.extend(db_portals)
            
            # Remove duplicates (prefer later sources)
            unique_portals = {}
            for portal in portals:
                unique_portals[portal.id] = portal
            
            # Create integration config
            integration_config = IntegrationConfig(
                portals=list(unique_portals.values()),
                default_timeout=int(os.getenv("INTEGRATION_DEFAULT_TIMEOUT", "30")),
                max_concurrent_requests=int(os.getenv("INTEGRATION_MAX_CONCURRENT", "10")),
                retry_strategy=os.getenv("INTEGRATION_RETRY_STRATEGY", "exponential_backoff"),
                circuit_breaker_threshold=int(os.getenv("INTEGRATION_CIRCUIT_BREAKER_THRESHOLD", "5")),
                circuit_breaker_timeout=int(os.getenv("INTEGRATION_CIRCUIT_BREAKER_TIMEOUT", "60")),
                enable_caching=os.getenv("INTEGRATION_ENABLE_CACHING", "true").lower() == "true",
                cache_ttl=int(os.getenv("INTEGRATION_CACHE_TTL", "300")),
                enable_monitoring=os.getenv("INTEGRATION_ENABLE_MONITORING", "true").lower() == "true"
            )
            
            logger.info(f"Loaded integration config with {len(integration_config.portals)} portals")
            return integration_config
            
        except Exception as e:
            logger.error(f"Failed to load integration configuration: {e}")
            raise ConfigurationError(f"Integration configuration loading failed: {e}")
    
    def _load_from_files(self) -> List[GovernmentPortal]:
        """Load portal configurations from files."""
        portals = []
        
        if not self.config_dir.exists():
            logger.warning(f"Configuration directory does not exist: {self.config_dir}")
            return portals
        
        # Load YAML files
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                portals.extend(self._load_yaml_file(yaml_file))
            except Exception as e:
                logger.error(f"Failed to load YAML file {yaml_file}: {e}")
        
        # Load JSON files
        for json_file in self.config_dir.glob("*.json"):
            try:
                portals.extend(self._load_json_file(json_file))
            except Exception as e:
                logger.error(f"Failed to load JSON file {json_file}: {e}")
        
        logger.info(f"Loaded {len(portals)} portals from configuration files")
        return portals
    
    def _load_yaml_file(self, file_path: Path) -> List[GovernmentPortal]:
        """Load portals from YAML file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            portals = []
            
            if 'portals' in data:
                for portal_config in data['portals']:
                    portal = self._create_portal_from_config(portal_config)
                    if portal:
                        portals.append(portal)
            
            logger.info(f"Loaded {len(portals)} portals from {file_path}")
            return portals
            
        except Exception as e:
            logger.error(f"Failed to load YAML file {file_path}: {e}")
            return []
    
    def _load_json_file(self, file_path: Path) -> List[GovernmentPortal]:
        """Load portals from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            portals = []
            
            if 'portals' in data:
                for portal_config in data['portals']:
                    portal = self._create_portal_from_config(portal_config)
                    if portal:
                        portals.append(portal)
            
            logger.info(f"Loaded {len(portals)} portals from {file_path}")
            return portals
            
        except Exception as e:
            logger.error(f"Failed to load JSON file {file_path}: {e}")
            return []
    
    def _load_from_environment(self) -> List[GovernmentPortal]:
        """Load portal configurations from environment variables."""
        portals = []
        
        # Look for environment variables with pattern: PORTAL_<ID>_CONFIG
        for key, value in os.environ.items():
            if key.startswith("PORTAL_") and key.endswith("_CONFIG"):
                try:
                    portal_config = json.loads(value)
                    portal = self._create_portal_from_config(portal_config)
                    if portal:
                        portals.append(portal)
                except Exception as e:
                    logger.error(f"Failed to parse portal config from env var {key}: {e}")
        
        logger.info(f"Loaded {len(portals)} portals from environment variables")
        return portals
    
    def _load_from_database(self) -> List[GovernmentPortal]:
        """Load portal configurations from database."""
        # This would connect to a database and load portal configurations
        # For now, return empty list
        logger.info("Database portal loading not implemented yet")
        return []
    
    def _create_portal_from_config(self, config_data: Dict[str, Any]) -> Optional[GovernmentPortal]:
        """Create GovernmentPortal from configuration data."""
        try:
            # Required fields
            portal_id = config_data.get('id')
            name = config_data.get('name')
            portal_type_str = config_data.get('type')
            base_url = config_data.get('base_url')
            
            if not all([portal_id, name, portal_type_str, base_url]):
                logger.error(f"Missing required fields in portal config: {config_data}")
                return None
            
            # Parse portal type
            try:
                portal_type = PortalType(portal_type_str)
            except ValueError:
                logger.error(f"Invalid portal type: {portal_type_str}")
                return None
            
            # Create portal
            portal = GovernmentPortal(
                id=portal_id,
                name=name,
                portal_type=portal_type,
                base_url=base_url,
                state_code=config_data.get('state_code'),
                district_code=config_data.get('district_code'),
                is_active=config_data.get('is_active', True),
                priority=config_data.get('priority', 1),
                supported_languages=config_data.get('supported_languages', ['hi', 'en']),
                rate_limit=config_data.get('rate_limit'),
                metadata=config_data.get('metadata', {})
            )
            
            # Add credentials
            if 'credentials' in config_data:
                credentials = self._create_credentials_from_config(config_data['credentials'])
                if credentials:
                    portal.credentials = credentials
            
            # Add endpoints
            if 'endpoints' in config_data:
                for endpoint_config in config_data['endpoints']:
                    endpoint = self._create_endpoint_from_config(endpoint_config)
                    if endpoint:
                        portal.add_endpoint(endpoint)
            
            return portal
            
        except Exception as e:
            logger.error(f"Failed to create portal from config: {e}")
            return None
    
    def _create_credentials_from_config(self, cred_config: Dict[str, Any]) -> Optional[APICredentials]:
        """Create APICredentials from configuration data."""
        try:
            auth_method_str = cred_config.get('auth_method')
            if not auth_method_str:
                return None
            
            try:
                auth_method = AuthMethod(auth_method_str)
            except ValueError:
                logger.error(f"Invalid auth method: {auth_method_str}")
                return None
            
            # Get credentials from config or environment variables
            credentials = APICredentials(
                auth_method=auth_method,
                api_key=self._get_credential_value(cred_config, 'api_key'),
                client_id=self._get_credential_value(cred_config, 'client_id'),
                client_secret=self._get_credential_value(cred_config, 'client_secret'),
                username=self._get_credential_value(cred_config, 'username'),
                password=self._get_credential_value(cred_config, 'password'),
                certificate_path=self._get_credential_value(cred_config, 'certificate_path'),
                private_key_path=self._get_credential_value(cred_config, 'private_key_path'),
                token_endpoint=cred_config.get('token_endpoint'),
                scope=cred_config.get('scope'),
                additional_headers=cred_config.get('additional_headers', {})
            )
            
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to create credentials from config: {e}")
            return None
    
    def _get_credential_value(self, cred_config: Dict[str, Any], key: str) -> Optional[str]:
        """Get credential value from config or environment variable."""
        # Check if value is directly in config
        value = cred_config.get(key)
        if value:
            return value
        
        # Check if there's an environment variable reference
        env_key = cred_config.get(f'{key}_env')
        if env_key:
            return os.getenv(env_key)
        
        # Check default environment variable pattern
        default_env_key = f"PORTAL_{key.upper()}"
        return os.getenv(default_env_key)
    
    def _create_endpoint_from_config(self, endpoint_config: Dict[str, Any]) -> Optional[APIEndpoint]:
        """Create APIEndpoint from configuration data."""
        try:
            name = endpoint_config.get('name')
            url = endpoint_config.get('url')
            
            if not name or not url:
                logger.error(f"Missing required endpoint fields: {endpoint_config}")
                return None
            
            # Parse data format
            data_format_str = endpoint_config.get('data_format', 'json')
            try:
                data_format = DataFormat(data_format_str)
            except ValueError:
                logger.warning(f"Invalid data format: {data_format_str}, using JSON")
                data_format = DataFormat.JSON
            
            # Parse response format
            response_format_str = endpoint_config.get('response_format', 'json')
            try:
                response_format = DataFormat(response_format_str)
            except ValueError:
                logger.warning(f"Invalid response format: {response_format_str}, using JSON")
                response_format = DataFormat.JSON
            
            endpoint = APIEndpoint(
                name=name,
                url=url,
                method=endpoint_config.get('method', 'POST'),
                data_format=data_format,
                timeout=endpoint_config.get('timeout', 30),
                max_retries=endpoint_config.get('max_retries', 3),
                retry_delay=endpoint_config.get('retry_delay', 1.0),
                required_fields=endpoint_config.get('required_fields', []),
                optional_fields=endpoint_config.get('optional_fields', []),
                response_format=response_format,
                success_codes=endpoint_config.get('success_codes', [200, 201, 202]),
                headers=endpoint_config.get('headers', {})
            )
            
            return endpoint
            
        except Exception as e:
            logger.error(f"Failed to create endpoint from config: {e}")
            return None
    
    def save_portal_config(self, portal: GovernmentPortal, file_path: Optional[Path] = None) -> bool:
        """Save portal configuration to file."""
        try:
            if not file_path:
                file_path = self.config_dir / f"{portal.id}.yaml"
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert portal to configuration format
            config_data = {
                'portals': [self._portal_to_config_dict(portal)]
            }
            
            # Save as YAML
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Saved portal configuration to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save portal configuration: {e}")
            return False
    
    def _portal_to_config_dict(self, portal: GovernmentPortal) -> Dict[str, Any]:
        """Convert GovernmentPortal to configuration dictionary."""
        config_dict = {
            'id': portal.id,
            'name': portal.name,
            'type': portal.portal_type.value,
            'base_url': portal.base_url,
            'is_active': portal.is_active,
            'priority': portal.priority,
            'supported_languages': portal.supported_languages,
            'metadata': portal.metadata
        }
        
        if portal.state_code:
            config_dict['state_code'] = portal.state_code
        
        if portal.district_code:
            config_dict['district_code'] = portal.district_code
        
        if portal.rate_limit:
            config_dict['rate_limit'] = portal.rate_limit
        
        # Add credentials (without sensitive data)
        if portal.credentials:
            config_dict['credentials'] = self._credentials_to_config_dict(portal.credentials)
        
        # Add endpoints
        if portal.endpoints:
            config_dict['endpoints'] = [
                self._endpoint_to_config_dict(endpoint)
                for endpoint in portal.endpoints.values()
            ]
        
        return config_dict
    
    def _credentials_to_config_dict(self, credentials: APICredentials) -> Dict[str, Any]:
        """Convert APICredentials to configuration dictionary."""
        config_dict = {
            'auth_method': credentials.auth_method.value
        }
        
        # Add non-sensitive fields
        if credentials.client_id:
            config_dict['client_id'] = credentials.client_id
        
        if credentials.username:
            config_dict['username'] = credentials.username
        
        if credentials.token_endpoint:
            config_dict['token_endpoint'] = credentials.token_endpoint
        
        if credentials.scope:
            config_dict['scope'] = credentials.scope
        
        if credentials.certificate_path:
            config_dict['certificate_path'] = credentials.certificate_path
        
        if credentials.private_key_path:
            config_dict['private_key_path'] = credentials.private_key_path
        
        if credentials.additional_headers:
            config_dict['additional_headers'] = credentials.additional_headers
        
        # For sensitive fields, reference environment variables
        if credentials.api_key:
            config_dict['api_key_env'] = f"PORTAL_{credentials.auth_method.value.upper()}_API_KEY"
        
        if credentials.client_secret:
            config_dict['client_secret_env'] = f"PORTAL_{credentials.auth_method.value.upper()}_CLIENT_SECRET"
        
        if credentials.password:
            config_dict['password_env'] = f"PORTAL_{credentials.auth_method.value.upper()}_PASSWORD"
        
        return config_dict
    
    def _endpoint_to_config_dict(self, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Convert APIEndpoint to configuration dictionary."""
        return {
            'name': endpoint.name,
            'url': endpoint.url,
            'method': endpoint.method,
            'data_format': endpoint.data_format.value,
            'response_format': endpoint.response_format.value,
            'timeout': endpoint.timeout,
            'max_retries': endpoint.max_retries,
            'retry_delay': endpoint.retry_delay,
            'required_fields': endpoint.required_fields,
            'optional_fields': endpoint.optional_fields,
            'success_codes': endpoint.success_codes,
            'headers': endpoint.headers
        }
    
    def validate_portal_config(self, portal: GovernmentPortal) -> List[str]:
        """Validate portal configuration and return list of issues."""
        issues = []
        
        # Validate basic fields
        if not portal.id:
            issues.append("Portal ID is required")
        
        if not portal.name:
            issues.append("Portal name is required")
        
        if not portal.base_url:
            issues.append("Base URL is required")
        elif not portal.base_url.startswith(('http://', 'https://')):
            issues.append("Base URL must start with http:// or https://")
        
        # Validate credentials
        if portal.credentials:
            from .auth_manager import AuthenticationManager
            auth_manager = AuthenticationManager()
            validation_result = auth_manager.validate_credentials(portal.credentials)
            if not validation_result.is_valid:
                issues.extend(validation_result.errors)
        
        # Validate endpoints
        if not portal.endpoints:
            issues.append("At least one endpoint is required")
        else:
            for endpoint_name, endpoint in portal.endpoints.items():
                try:
                    # This will raise ValueError if URL is invalid
                    APIEndpoint(
                        name=endpoint.name,
                        url=endpoint.url,
                        method=endpoint.method
                    )
                except ValueError as e:
                    issues.append(f"Invalid endpoint {endpoint_name}: {e}")
        
        return issues