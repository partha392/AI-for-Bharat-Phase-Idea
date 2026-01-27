"""
Government API client for connecting to state and central government portals.

This module provides a robust HTTP client for interacting with various
government APIs with proper error handling, retry mechanisms, and
authentication support.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import aiohttp
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

from .models import (
    GovernmentPortal, APIEndpoint, APICredentials, APIResponse,
    AuthMethod, DataFormat, SubmissionStatus
)
from .auth_manager import AuthenticationManager
from ..core.exceptions import (
    GovernmentAPIError, AuthenticationError, NetworkError,
    TimeoutError, RateLimitError, ValidationError
)
from ..core.config import config

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern implementation for API resilience."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if self.last_failure_time and \
               (datetime.now() - self.last_failure_time).seconds >= self.timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        """Record successful execution."""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class GovernmentAPIClient:
    """
    HTTP client for government API interactions.
    
    Provides robust communication with government portals including
    authentication, retry logic, circuit breaker pattern, and
    comprehensive error handling.
    """
    
    def __init__(self, auth_manager: Optional[AuthenticationManager] = None):
        """Initialize the API client."""
        self.auth_manager = auth_manager or AuthenticationManager()
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, Dict[str, Any]] = {}
        self._request_counts: Dict[str, List[datetime]] = {}
        
        # Default headers
        self.default_headers = {
            'User-Agent': 'BharatVoiceAssistant/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        logger.info("GovernmentAPIClient initialized")
    
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
            timeout = aiohttp.ClientTimeout(
                total=config.network.connection_timeout,
                connect=config.network.connection_timeout // 2
            )
            
            connector = aiohttp.TCPConnector(
                limit=config.network.max_retries * 2,
                limit_per_host=config.network.max_retries,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=self.default_headers
            )
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    def _get_circuit_breaker(self, portal_id: str) -> CircuitBreaker:
        """Get or create circuit breaker for portal."""
        if portal_id not in self.circuit_breakers:
            self.circuit_breakers[portal_id] = CircuitBreaker(
                failure_threshold=config.network.max_retries,
                timeout=60
            )
        return self.circuit_breakers[portal_id]
    
    async def _check_rate_limit(self, portal: GovernmentPortal) -> bool:
        """Check if request is within rate limits."""
        if not portal.rate_limit:
            return True
        
        portal_id = portal.id
        now = datetime.now()
        
        # Initialize rate limiter for portal
        if portal_id not in self._request_counts:
            self._request_counts[portal_id] = []
        
        # Clean old requests (older than 1 minute)
        self._request_counts[portal_id] = [
            req_time for req_time in self._request_counts[portal_id]
            if (now - req_time).seconds < 60
        ]
        
        # Check if within rate limit
        if len(self._request_counts[portal_id]) >= portal.rate_limit:
            return False
        
        # Record this request
        self._request_counts[portal_id].append(now)
        return True
    
    async def submit_grievance(self, portal: GovernmentPortal, 
                             endpoint_name: str, data: Dict[str, Any],
                             reference_id: Optional[str] = None) -> APIResponse:
        """
        Submit grievance to government portal.
        
        Args:
            portal: Government portal configuration
            endpoint_name: Name of the endpoint to use
            data: Grievance data to submit
            reference_id: Optional reference ID for tracking
            
        Returns:
            APIResponse with submission result
        """
        endpoint = portal.get_endpoint(endpoint_name)
        if not endpoint:
            raise GovernmentAPIError(
                f"Endpoint '{endpoint_name}' not found for portal '{portal.id}'",
                error_code="ENDPOINT_NOT_FOUND"
            )
        
        # Check circuit breaker
        circuit_breaker = self._get_circuit_breaker(portal.id)
        if not circuit_breaker.can_execute():
            raise GovernmentAPIError(
                f"Circuit breaker is open for portal '{portal.id}'",
                error_code="CIRCUIT_BREAKER_OPEN"
            )
        
        # Check rate limits
        if not await self._check_rate_limit(portal):
            raise RateLimitError(
                f"Rate limit exceeded for portal '{portal.id}'",
                error_code="RATE_LIMIT_EXCEEDED"
            )
        
        try:
            # Prepare request
            url = urljoin(portal.base_url, endpoint.url)
            headers = await self._prepare_headers(portal, endpoint)
            request_data = await self._prepare_request_data(data, endpoint, reference_id)
            
            # Execute request with retries
            response = await self._execute_request_with_retries(
                portal, endpoint, url, headers, request_data
            )
            
            # Record success
            circuit_breaker.record_success()
            
            logger.info(f"Successfully submitted grievance to {portal.id}")
            return response
            
        except Exception as e:
            # Record failure
            circuit_breaker.record_failure()
            
            logger.error(f"Failed to submit grievance to {portal.id}: {e}")
            
            if isinstance(e, (GovernmentAPIError, AuthenticationError, NetworkError, 
                            TimeoutError, RateLimitError)):
                raise
            else:
                raise GovernmentAPIError(
                    f"Unexpected error submitting to {portal.id}: {e}",
                    error_code="SUBMISSION_ERROR"
                )
    
    async def check_status(self, portal: GovernmentPortal, 
                          endpoint_name: str, reference_number: str) -> APIResponse:
        """
        Check status of submitted grievance.
        
        Args:
            portal: Government portal configuration
            endpoint_name: Name of the status endpoint
            reference_number: Reference number to check
            
        Returns:
            APIResponse with status information
        """
        endpoint = portal.get_endpoint(endpoint_name)
        if not endpoint:
            raise GovernmentAPIError(
                f"Status endpoint '{endpoint_name}' not found for portal '{portal.id}'",
                error_code="ENDPOINT_NOT_FOUND"
            )
        
        # Check circuit breaker
        circuit_breaker = self._get_circuit_breaker(portal.id)
        if not circuit_breaker.can_execute():
            raise GovernmentAPIError(
                f"Circuit breaker is open for portal '{portal.id}'",
                error_code="CIRCUIT_BREAKER_OPEN"
            )
        
        try:
            # Prepare request
            url = urljoin(portal.base_url, endpoint.url)
            headers = await self._prepare_headers(portal, endpoint)
            
            # For status checks, usually reference number is in URL or query params
            if endpoint.method.upper() == "GET":
                url = url.replace("{reference_number}", reference_number)
                request_data = None
            else:
                request_data = {"reference_number": reference_number}
            
            # Execute request
            response = await self._execute_request_with_retries(
                portal, endpoint, url, headers, request_data
            )
            
            circuit_breaker.record_success()
            
            logger.info(f"Successfully checked status for {reference_number} on {portal.id}")
            return response
            
        except Exception as e:
            circuit_breaker.record_failure()
            
            logger.error(f"Failed to check status on {portal.id}: {e}")
            
            if isinstance(e, (GovernmentAPIError, AuthenticationError, NetworkError, 
                            TimeoutError, RateLimitError)):
                raise
            else:
                raise GovernmentAPIError(
                    f"Unexpected error checking status on {portal.id}: {e}",
                    error_code="STATUS_CHECK_ERROR"
                )
    
    async def _prepare_headers(self, portal: GovernmentPortal, 
                             endpoint: APIEndpoint) -> Dict[str, str]:
        """Prepare request headers including authentication."""
        headers = self.default_headers.copy()
        headers.update(endpoint.headers)
        
        # Add authentication headers
        if portal.credentials:
            auth_headers = await self.auth_manager.get_auth_headers(portal)
            headers.update(auth_headers)
        
        # Set content type based on data format
        if endpoint.data_format == DataFormat.XML:
            headers['Content-Type'] = 'application/xml'
        elif endpoint.data_format == DataFormat.FORM_DATA:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        elif endpoint.data_format == DataFormat.SOAP:
            headers['Content-Type'] = 'text/xml; charset=utf-8'
        
        return headers
    
    async def _prepare_request_data(self, data: Dict[str, Any], 
                                  endpoint: APIEndpoint,
                                  reference_id: Optional[str] = None) -> Optional[Union[str, Dict[str, Any]]]:
        """Prepare request data based on endpoint format."""
        if endpoint.method.upper() == "GET":
            return None
        
        # Add reference ID if provided
        if reference_id:
            data['reference_id'] = reference_id
        
        # Add timestamp
        data['timestamp'] = datetime.now().isoformat()
        
        # Format data based on endpoint requirements
        if endpoint.data_format == DataFormat.JSON:
            return data
        elif endpoint.data_format == DataFormat.XML:
            return self._dict_to_xml(data)
        elif endpoint.data_format == DataFormat.FORM_DATA:
            return data  # aiohttp will handle form encoding
        elif endpoint.data_format == DataFormat.SOAP:
            return self._dict_to_soap(data)
        else:
            return data
    
    async def _execute_request_with_retries(self, portal: GovernmentPortal,
                                          endpoint: APIEndpoint, url: str,
                                          headers: Dict[str, str],
                                          data: Optional[Union[str, Dict[str, Any]]]) -> APIResponse:
        """Execute HTTP request with retry logic."""
        await self._ensure_session()
        
        last_exception = None
        
        for attempt in range(endpoint.max_retries + 1):
            try:
                start_time = time.time()
                
                # Execute request
                if endpoint.method.upper() == "GET":
                    async with self.session.get(url, headers=headers, 
                                              timeout=endpoint.timeout) as response:
                        response_data = await self._parse_response(response, endpoint)
                elif endpoint.method.upper() == "POST":
                    if endpoint.data_format == DataFormat.FORM_DATA:
                        async with self.session.post(url, headers=headers, data=data,
                                                   timeout=endpoint.timeout) as response:
                            response_data = await self._parse_response(response, endpoint)
                    else:
                        async with self.session.post(url, headers=headers, 
                                                   json=data if isinstance(data, dict) else None,
                                                   data=data if isinstance(data, str) else None,
                                                   timeout=endpoint.timeout) as response:
                            response_data = await self._parse_response(response, endpoint)
                else:
                    raise GovernmentAPIError(
                        f"Unsupported HTTP method: {endpoint.method}",
                        error_code="UNSUPPORTED_METHOD"
                    )
                
                response_time = time.time() - start_time
                
                # Check if response indicates success
                if response.status in endpoint.success_codes:
                    return APIResponse(
                        success=True,
                        status_code=response.status,
                        data=response_data,
                        response_time=response_time,
                        headers=dict(response.headers)
                    )
                else:
                    # Handle error response
                    error_message = response_data.get('message', 'Unknown error') if response_data else 'Unknown error'
                    error_code = response_data.get('error_code', str(response.status)) if response_data else str(response.status)
                    
                    return APIResponse(
                        success=False,
                        status_code=response.status,
                        error_message=error_message,
                        error_code=error_code,
                        data=response_data,
                        response_time=response_time,
                        headers=dict(response.headers)
                    )
                
            except asyncio.TimeoutError as e:
                last_exception = TimeoutError(
                    f"Request timeout for {url}",
                    error_code="REQUEST_TIMEOUT"
                )
                
            except aiohttp.ClientError as e:
                last_exception = NetworkError(
                    f"Network error for {url}: {e}",
                    error_code="NETWORK_ERROR"
                )
                
            except Exception as e:
                last_exception = GovernmentAPIError(
                    f"Unexpected error for {url}: {e}",
                    error_code="UNEXPECTED_ERROR"
                )
            
            # Wait before retry (exponential backoff)
            if attempt < endpoint.max_retries:
                wait_time = endpoint.retry_delay * (2 ** attempt)
                logger.warning(f"Request failed, retrying in {wait_time}s (attempt {attempt + 1}/{endpoint.max_retries + 1})")
                await asyncio.sleep(wait_time)
        
        # All retries exhausted
        raise last_exception
    
    async def _parse_response(self, response: aiohttp.ClientResponse, 
                            endpoint: APIEndpoint) -> Optional[Dict[str, Any]]:
        """Parse response based on expected format."""
        try:
            if endpoint.response_format == DataFormat.JSON:
                return await response.json()
            elif endpoint.response_format == DataFormat.XML:
                text = await response.text()
                return self._xml_to_dict(text)
            else:
                text = await response.text()
                return {'raw_response': text}
                
        except Exception as e:
            logger.warning(f"Failed to parse response: {e}")
            text = await response.text()
            return {'raw_response': text, 'parse_error': str(e)}
    
    def _dict_to_xml(self, data: Dict[str, Any], root_name: str = "request") -> str:
        """Convert dictionary to XML string."""
        root = ET.Element(root_name)
        
        def add_element(parent, key, value):
            element = ET.SubElement(parent, key)
            if isinstance(value, dict):
                for k, v in value.items():
                    add_element(element, k, v)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        item_element = ET.SubElement(element, "item")
                        for k, v in item.items():
                            add_element(item_element, k, v)
                    else:
                        item_element = ET.SubElement(element, "item")
                        item_element.text = str(item)
            else:
                element.text = str(value)
        
        for key, value in data.items():
            add_element(root, key, value)
        
        return ET.tostring(root, encoding='unicode')
    
    def _xml_to_dict(self, xml_string: str) -> Dict[str, Any]:
        """Convert XML string to dictionary."""
        try:
            root = ET.fromstring(xml_string)
            
            def element_to_dict(element):
                result = {}
                
                # Add attributes
                if element.attrib:
                    result.update(element.attrib)
                
                # Add text content
                if element.text and element.text.strip():
                    if len(element) == 0:  # No children
                        return element.text.strip()
                    else:
                        result['text'] = element.text.strip()
                
                # Add children
                for child in element:
                    child_data = element_to_dict(child)
                    if child.tag in result:
                        # Convert to list if multiple elements with same tag
                        if not isinstance(result[child.tag], list):
                            result[child.tag] = [result[child.tag]]
                        result[child.tag].append(child_data)
                    else:
                        result[child.tag] = child_data
                
                return result
            
            return {root.tag: element_to_dict(root)}
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            return {'raw_xml': xml_string, 'parse_error': str(e)}
    
    def _dict_to_soap(self, data: Dict[str, Any]) -> str:
        """Convert dictionary to SOAP envelope."""
        # Basic SOAP envelope template
        soap_template = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Header/>
    <soap:Body>
        {body}
    </soap:Body>
</soap:Envelope>'''
        
        body_xml = self._dict_to_xml(data, "request")
        return soap_template.format(body=body_xml)
    
    async def test_connection(self, portal: GovernmentPortal) -> bool:
        """Test connection to government portal."""
        try:
            await self._ensure_session()
            
            # Try to access base URL
            async with self.session.get(portal.base_url, timeout=10) as response:
                return response.status < 500
                
        except Exception as e:
            logger.error(f"Connection test failed for {portal.id}: {e}")
            return False
    
    def get_circuit_breaker_status(self, portal_id: str) -> Dict[str, Any]:
        """Get circuit breaker status for portal."""
        if portal_id not in self.circuit_breakers:
            return {"state": "CLOSED", "failure_count": 0}
        
        cb = self.circuit_breakers[portal_id]
        return {
            "state": cb.state,
            "failure_count": cb.failure_count,
            "last_failure_time": cb.last_failure_time.isoformat() if cb.last_failure_time else None
        }