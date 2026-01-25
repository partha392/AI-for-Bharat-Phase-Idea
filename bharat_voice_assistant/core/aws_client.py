"""
AWS client configuration and management for the Bharat Voice Assistant.

This module provides centralized AWS service client management with proper
authentication, error handling, and retry logic.
"""

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from typing import Dict, Any, Optional
import threading
import os
from functools import lru_cache

from .config import config
from .logging import get_logger
from .exceptions import AWSServiceError, AuthenticationError, handle_aws_error


logger = get_logger(__name__)


class AWSClientManager:
    """Manages AWS service clients with proper configuration and error handling."""
    
    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._boto_config = self._create_boto_config()
        self._credentials = config.get_aws_credentials()
    
    def _create_boto_config(self) -> Config:
        """Create boto3 configuration with retry and timeout settings."""
        return Config(
            region_name=config.aws.region,
            retries={
                'max_attempts': config.network.max_retries,
                'mode': 'adaptive'
            },
            connect_timeout=config.network.connection_timeout,
            read_timeout=config.network.read_timeout,
            max_pool_connections=50
        )
    
    def _get_client(self, service_name: str, **kwargs) -> Any:
        """Get or create an AWS service client."""
        client_key = f"{service_name}_{hash(str(sorted(kwargs.items())))}"
        
        with self._lock:
            if client_key not in self._clients:
                try:
                    client_kwargs = {**self._credentials, 'config': self._boto_config, **kwargs}
                    self._clients[client_key] = boto3.client(service_name, **client_kwargs)
                    logger.info(f"Created AWS {service_name} client")
                except (NoCredentialsError, PartialCredentialsError) as e:
                    raise AuthenticationError(
                        f"AWS credentials not found or incomplete for {service_name}",
                        error_code="AWS_CREDENTIALS_MISSING",
                        context={'service': service_name, 'error': str(e)}
                    )
                except Exception as e:
                    raise handle_aws_error(e, f"creating {service_name} client")
            
            return self._clients[client_key]
    
    @property
    def transcribe(self):
        """Get AWS Transcribe client."""
        return self._get_client('transcribe')
    
    @property
    def polly(self):
        """Get AWS Polly client."""
        return self._get_client('polly')
    
    @property
    def comprehend(self):
        """Get AWS Comprehend client."""
        return self._get_client('comprehend')
    
    @property
    def s3(self):
        """Get AWS S3 client."""
        return self._get_client('s3')
    
    @property
    def dynamodb(self):
        """Get AWS DynamoDB client."""
        return self._get_client('dynamodb')
    
    @property
    def cloudwatch(self):
        """Get AWS CloudWatch client."""
        return self._get_client('cloudwatch')
    
    @property
    def sts(self):
        """Get AWS STS client."""
        return self._get_client('sts')
    
    @property
    def lambda_client(self):
        """Get AWS Lambda client."""
        return self._get_client('lambda')
    
    @property
    def apigateway(self):
        """Get AWS API Gateway client."""
        return self._get_client('apigateway')
    
    def get_custom_client(self, service_name: str, **kwargs):
        """Get a custom AWS service client with additional parameters."""
        return self._get_client(service_name, **kwargs)
    
    def test_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to AWS services."""
        results = {}
        
        # Test STS (basic AWS connectivity)
        try:
            self.sts.get_caller_identity()
            results['sts'] = True
            logger.info("AWS STS connectivity test passed")
        except Exception as e:
            results['sts'] = False
            logger.error(f"AWS STS connectivity test failed: {e}")
        
        # Test S3
        try:
            self.s3.list_buckets()
            results['s3'] = True
            logger.info("AWS S3 connectivity test passed")
        except Exception as e:
            results['s3'] = False
            logger.error(f"AWS S3 connectivity test failed: {e}")
        
        # Test Transcribe
        try:
            self.transcribe.list_transcription_jobs(MaxResults=1)
            results['transcribe'] = True
            logger.info("AWS Transcribe connectivity test passed")
        except Exception as e:
            results['transcribe'] = False
            logger.error(f"AWS Transcribe connectivity test failed: {e}")
        
        # Test Polly
        try:
            self.polly.describe_voices(LanguageCode='hi-IN')
            results['polly'] = True
            logger.info("AWS Polly connectivity test passed")
        except Exception as e:
            results['polly'] = False
            logger.error(f"AWS Polly connectivity test failed: {e}")
        
        # Test Comprehend
        try:
            self.comprehend.detect_dominant_language(Text="Test text")
            results['comprehend'] = True
            logger.info("AWS Comprehend connectivity test passed")
        except Exception as e:
            results['comprehend'] = False
            logger.error(f"AWS Comprehend connectivity test failed: {e}")
        
        return results
    
    def refresh_credentials(self):
        """Refresh AWS credentials and recreate clients."""
        with self._lock:
            self._credentials = config.get_aws_credentials()
            self._clients.clear()
            logger.info("AWS credentials refreshed, clients cleared")


# Global AWS client manager instance
aws_clients = AWSClientManager()


# Utility functions for common AWS operations
def safe_aws_call(client_method, *args, **kwargs):
    """
    Safely execute an AWS client method with proper error handling.
    
    Args:
        client_method: The AWS client method to call
        *args: Positional arguments for the method
        **kwargs: Keyword arguments for the method
        
    Returns:
        The result of the AWS API call
        
    Raises:
        Appropriate application-specific exceptions
    """
    try:
        return client_method(*args, **kwargs)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        context = {
            'error_code': error_code,
            'error_message': error_message,
            'operation': client_method.__name__,
            'args': str(args),
            'kwargs': str(kwargs)
        }
        
        raise handle_aws_error(e, f"AWS API call {client_method.__name__}", context)
    except Exception as e:
        raise handle_aws_error(e, f"AWS API call {client_method.__name__}")


@lru_cache(maxsize=128)
def get_aws_region_endpoints(service: str) -> Dict[str, str]:
    """
    Get AWS service endpoints for different regions.
    
    Args:
        service: AWS service name
        
    Returns:
        Dictionary mapping region names to endpoints
    """
    # Common AWS regions in India and nearby
    regions = {
        'ap-south-1': f'https://{service}.ap-south-1.amazonaws.com',  # Mumbai
        'ap-south-2': f'https://{service}.ap-south-2.amazonaws.com',  # Hyderabad
        'ap-southeast-1': f'https://{service}.ap-southeast-1.amazonaws.com',  # Singapore
        'us-east-1': f'https://{service}.us-east-1.amazonaws.com',  # N. Virginia
    }
    
    return regions


def validate_aws_configuration() -> Dict[str, Any]:
    """
    Validate AWS configuration and return status.
    
    Returns:
        Dictionary with validation results
    """
    validation_results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'services': {}
    }
    
    try:
        # Test basic connectivity
        connectivity_results = aws_clients.test_connectivity()
        validation_results['services'] = connectivity_results
        
        # Check if any critical services failed
        critical_services = ['sts', 's3', 'transcribe', 'polly']
        failed_critical = [
            service for service in critical_services 
            if not connectivity_results.get(service, False)
        ]
        
        if failed_critical:
            validation_results['valid'] = False
            validation_results['errors'].append(
                f"Critical AWS services failed connectivity test: {', '.join(failed_critical)}"
            )
        
        # Check configuration completeness
        if not config.aws.region:
            validation_results['warnings'].append("AWS region not configured")
        
        if not config.aws.access_key_id and not config.aws.secret_access_key:
            validation_results['warnings'].append(
                "AWS credentials not configured (using IAM role or environment)"
            )
        
    except Exception as e:
        validation_results['valid'] = False
        validation_results['errors'].append(f"AWS validation failed: {e}")
    
    return validation_results


# Initialize AWS clients on module import
try:
    # Test basic connectivity on startup only if boto3 is available
    logger.info("Initializing AWS clients...")
    
    # Only validate if we're not in test mode and boto3 is available
    if os.getenv("ENVIRONMENT") != "test":
        validation_results = validate_aws_configuration()
        
        if validation_results['valid']:
            logger.info("AWS configuration validated successfully")
        else:
            logger.error(f"AWS configuration validation failed: {validation_results['errors']}")
            
        if validation_results['warnings']:
            for warning in validation_results['warnings']:
                logger.warning(f"AWS configuration warning: {warning}")
    else:
        logger.info("Skipping AWS validation in test mode")
            
except ImportError:
    logger.warning("boto3 not available, AWS functionality will be limited")
except Exception as e:
    logger.error(f"Failed to initialize AWS clients: {e}", exc_info=True)