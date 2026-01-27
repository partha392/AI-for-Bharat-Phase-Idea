"""
Government integration service that orchestrates all integration components.

This module provides the main service for integrating with government
systems, coordinating API clients, authentication, data transformation,
and error handling with retry mechanisms.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import json

from .models import (
    GovernmentPortal, IntegrationConfig, SubmissionRequest,
    APIResponse, StatusResponse, IntegrationResult,
    SubmissionStatus, PortalType
)
from .government_api_client import GovernmentAPIClient
from .auth_manager import AuthenticationManager
from .data_transformer import DataTransformer
from ..grievance.models import GrievanceRecord, GrievanceSubmissionResult
from ..core.exceptions import (
    GovernmentIntegrationError, GovernmentAPIError, AuthenticationError,
    NetworkError, TimeoutError, RateLimitError, DataSynchronizationError
)
from ..core.config import config
from ..core.logging import get_logger

logger = get_logger(__name__)


class GovernmentIntegrationService:
    """
    Main service for government system integration.
    
    Orchestrates API clients, authentication, data transformation,
    and provides high-level methods for grievance submission and
    status tracking with comprehensive error handling and retry logic.
    """
    
    def __init__(self, integration_config: Optional[IntegrationConfig] = None):
        """Initialize the integration service."""
        self.config = integration_config or self._load_default_config()
        self.api_client = GovernmentAPIClient()
        self.auth_manager = AuthenticationManager()
        self.data_transformer = DataTransformer()
        
        # Request queue for handling retries and failures
        self.pending_requests: Dict[str, SubmissionRequest] = {}
        self.failed_requests: Dict[str, Tuple[SubmissionRequest, Exception]] = {}
        
        # Performance tracking
        self.performance_metrics: Dict[str, List[float]] = {}
        
        # Background task for processing queued requests
        self._background_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        logger.info("GovernmentIntegrationService initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.api_client.__aenter__()
        await self.auth_manager.__aenter__()
        
        # Start background processing task
        self._background_task = asyncio.create_task(self._process_background_requests())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for background task to complete
        if self._background_task:
            try:
                await asyncio.wait_for(self._background_task, timeout=10.0)
            except asyncio.TimeoutError:
                self._background_task.cancel()
        
        await self.auth_manager.__aexit__(exc_type, exc_val, exc_tb)
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb)
    
    def _load_default_config(self) -> IntegrationConfig:
        """Load default integration configuration."""
        # This would typically load from configuration files
        # For now, create a basic configuration with sample portals
        
        from .models import APICredentials, APIEndpoint, AuthMethod, DataFormat
        
        # Central Government Portal (Sample)
        central_portal = GovernmentPortal(
            id="central_gov_portal",
            name="Central Government Grievance Portal",
            portal_type=PortalType.CENTRAL_GOVERNMENT,
            base_url="https://pgportal.gov.in/api/v1",
            credentials=APICredentials(
                auth_method=AuthMethod.API_KEY,
                api_key="sample_api_key"  # This would be loaded from secure config
            ),
            priority=1
        )
        
        # Add endpoints
        central_portal.add_endpoint(APIEndpoint(
            name="submit_grievance",
            url="/grievances/submit",
            method="POST",
            data_format=DataFormat.JSON,
            required_fields=["complaint_description", "category_code", "mobile_number"],
            optional_fields=["email_id", "address", "preferred_language"]
        ))
        
        central_portal.add_endpoint(APIEndpoint(
            name="check_status",
            url="/grievances/status/{reference_number}",
            method="GET",
            response_format=DataFormat.JSON
        ))
        
        # State Government Portal (Sample)
        state_portal = GovernmentPortal(
            id="state_gov_portal",
            name="State Government Portal",
            portal_type=PortalType.STATE_GOVERNMENT,
            base_url="https://state.gov.in/api",
            state_code="MH",  # Maharashtra
            credentials=APICredentials(
                auth_method=AuthMethod.OAUTH2,
                client_id="sample_client_id",
                client_secret="sample_client_secret",
                token_endpoint="https://state.gov.in/oauth/token"
            ),
            priority=2
        )
        
        state_portal.add_endpoint(APIEndpoint(
            name="submit_grievance",
            url="/complaints/create",
            method="POST",
            data_format=DataFormat.JSON,
            required_fields=["grievance_details", "grievance_category", "contact_number"]
        ))
        
        return IntegrationConfig(
            portals=[central_portal, state_portal],
            default_timeout=30,
            max_concurrent_requests=5,
            retry_strategy="exponential_backoff",
            circuit_breaker_threshold=3,
            enable_caching=True,
            cache_ttl=300
        )
    
    async def submit_grievance(self, grievance: GrievanceRecord,
                             preferred_portals: Optional[List[str]] = None,
                             fallback_enabled: bool = True) -> IntegrationResult:
        """
        Submit grievance to government portals.
        
        Args:
            grievance: Grievance record to submit
            preferred_portals: List of preferred portal IDs (optional)
            fallback_enabled: Whether to try fallback portals on failure
            
        Returns:
            IntegrationResult with submission status and details
        """
        start_time = time.time()
        
        try:
            # Determine target portals
            target_portals = self._select_target_portals(
                grievance, preferred_portals, fallback_enabled
            )
            
            if not target_portals:
                return IntegrationResult(
                    success=False,
                    portal_id="none",
                    operation="submit_grievance",
                    message="No suitable government portals found",
                    error_code="NO_PORTALS_AVAILABLE"
                )
            
            # Try submitting to portals in order of priority
            last_error = None
            
            for portal in target_portals:
                try:
                    logger.info(f"Attempting to submit grievance to {portal.id}")
                    
                    # Transform data for this portal
                    endpoint = portal.get_endpoint("submit_grievance")
                    if not endpoint:
                        logger.warning(f"No submit_grievance endpoint for {portal.id}")
                        continue
                    
                    transformation_result = self.data_transformer.transform_grievance_data(
                        grievance, portal, endpoint
                    )
                    
                    if not transformation_result.is_valid:
                        logger.warning(f"Data transformation failed for {portal.id}: {transformation_result.errors}")
                        continue
                    
                    # Submit to portal
                    api_response = await self.api_client.submit_grievance(
                        portal, "submit_grievance", 
                        transformation_result.transformed_data,
                        str(grievance.id)
                    )
                    
                    # Process response
                    if api_response.is_success():
                        reference_number = api_response.get_reference_number()
                        
                        # Update grievance record
                        await self._update_grievance_after_submission(
                            grievance, portal, api_response, reference_number
                        )
                        
                        execution_time = time.time() - start_time
                        self._record_performance_metric(portal.id, execution_time)
                        
                        logger.info(f"Successfully submitted grievance to {portal.id}, ref: {reference_number}")
                        
                        return IntegrationResult(
                            success=True,
                            portal_id=portal.id,
                            operation="submit_grievance",
                            reference_number=reference_number,
                            status=SubmissionStatus.SUBMITTED,
                            message=f"Grievance submitted successfully to {portal.name}",
                            response_data=api_response.data,
                            execution_time=execution_time
                        )
                    else:
                        logger.warning(f"Submission failed for {portal.id}: {api_response.error_message}")
                        last_error = GovernmentAPIError(
                            f"Submission failed: {api_response.error_message}",
                            error_code=api_response.error_code
                        )
                
                except Exception as e:
                    logger.error(f"Error submitting to {portal.id}: {e}")
                    last_error = e
                    
                    # If this is a rate limit or temporary error, queue for retry
                    if isinstance(e, (RateLimitError, TimeoutError, NetworkError)):
                        await self._queue_for_retry(grievance, portal, "submit_grievance")
            
            # All portals failed
            execution_time = time.time() - start_time
            
            return IntegrationResult(
                success=False,
                portal_id="multiple_attempted",
                operation="submit_grievance",
                message=f"Failed to submit to all available portals. Last error: {last_error}",
                error_code="ALL_PORTALS_FAILED",
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in submit_grievance: {e}")
            execution_time = time.time() - start_time
            
            return IntegrationResult(
                success=False,
                portal_id="unknown",
                operation="submit_grievance",
                message=f"Unexpected error: {e}",
                error_code="UNEXPECTED_ERROR",
                execution_time=execution_time
            )
    
    async def check_grievance_status(self, reference_number: str,
                                   portal_id: Optional[str] = None) -> IntegrationResult:
        """
        Check status of submitted grievance.
        
        Args:
            reference_number: Government reference number
            portal_id: Specific portal to check (optional)
            
        Returns:
            IntegrationResult with status information
        """
        start_time = time.time()
        
        try:
            # Determine which portals to check
            if portal_id:
                portals = [portal for portal in self.config.portals if portal.id == portal_id]
            else:
                # Check all active portals
                portals = [portal for portal in self.config.portals if portal.is_active]
            
            if not portals:
                return IntegrationResult(
                    success=False,
                    portal_id=portal_id or "none",
                    operation="check_status",
                    message="No portals available for status check",
                    error_code="NO_PORTALS_AVAILABLE"
                )
            
            # Try checking status on each portal
            for portal in portals:
                try:
                    if not portal.get_endpoint("check_status"):
                        continue
                    
                    logger.info(f"Checking status on {portal.id} for ref: {reference_number}")
                    
                    api_response = await self.api_client.check_status(
                        portal, "check_status", reference_number
                    )
                    
                    if api_response.is_success() and api_response.data:
                        # Parse status response
                        status_response = self._parse_status_response(api_response.data, portal)
                        
                        execution_time = time.time() - start_time
                        
                        logger.info(f"Status retrieved from {portal.id}: {status_response.status}")
                        
                        return IntegrationResult(
                            success=True,
                            portal_id=portal.id,
                            operation="check_status",
                            reference_number=reference_number,
                            status=status_response.status,
                            message=status_response.status_message,
                            response_data=status_response.to_dict(),
                            execution_time=execution_time
                        )
                
                except Exception as e:
                    logger.warning(f"Status check failed for {portal.id}: {e}")
                    continue
            
            # No portal returned status
            execution_time = time.time() - start_time
            
            return IntegrationResult(
                success=False,
                portal_id="multiple_attempted",
                operation="check_status",
                reference_number=reference_number,
                message="Status not found on any portal",
                error_code="STATUS_NOT_FOUND",
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in check_grievance_status: {e}")
            execution_time = time.time() - start_time
            
            return IntegrationResult(
                success=False,
                portal_id=portal_id or "unknown",
                operation="check_status",
                reference_number=reference_number,
                message=f"Unexpected error: {e}",
                error_code="UNEXPECTED_ERROR",
                execution_time=execution_time
            )
    
    def _select_target_portals(self, grievance: GrievanceRecord,
                             preferred_portals: Optional[List[str]] = None,
                             fallback_enabled: bool = True) -> List[GovernmentPortal]:
        """Select target portals for grievance submission."""
        
        # Extract location information
        state_code = None
        district_code = None
        
        if grievance.details and grievance.details.location:
            # This would typically parse location to extract state/district codes
            # For now, we'll use a simple approach
            location = grievance.details.location.upper()
            if "MAHARASHTRA" in location or "MH" in location:
                state_code = "MH"
            elif "UTTAR PRADESH" in location or "UP" in location:
                state_code = "UP"
            # Add more state mappings as needed
        
        # Get available portals for location
        available_portals = self.config.get_portals_for_location(state_code, district_code)
        
        # Filter by preferred portals if specified
        if preferred_portals:
            preferred = [p for p in available_portals if p.id in preferred_portals]
            if preferred:
                available_portals = preferred
            elif not fallback_enabled:
                return []
        
        # Filter out portals that don't have submit_grievance endpoint
        target_portals = [
            portal for portal in available_portals
            if portal.get_endpoint("submit_grievance")
        ]
        
        return target_portals
    
    async def _update_grievance_after_submission(self, grievance: GrievanceRecord,
                                               portal: GovernmentPortal,
                                               api_response: APIResponse,
                                               reference_number: Optional[str]):
        """Update grievance record after successful submission."""
        
        # Create submission result
        submission_result = GrievanceSubmissionResult(
            success=True,
            reference_number=reference_number,
            submission_date=datetime.now(),
            assigned_officer=api_response.data.get("assigned_officer") if api_response.data else None,
            department=api_response.data.get("department") if api_response.data else None,
            next_steps=[
                "Your grievance has been submitted successfully",
                f"Reference number: {reference_number}",
                "You will receive updates via SMS/email",
                "Track status using the reference number"
            ]
        )
        
        # Update grievance record
        grievance.reference_number = reference_number
        grievance.government_reference = reference_number
        grievance.submission_result = submission_result
        grievance.status = grievance.status.SUBMITTED
        grievance.submitted_at = datetime.now()
        grievance.updated_at = datetime.now()
        
        # Add portal information to metadata
        grievance.metadata.update({
            "submitted_portal": portal.id,
            "portal_name": portal.name,
            "portal_type": portal.portal_type.value,
            "submission_response": api_response.data
        })
    
    def _parse_status_response(self, response_data: Dict[str, Any], 
                             portal: GovernmentPortal) -> StatusResponse:
        """Parse status response from government portal."""
        
        # Extract status information (this would be portal-specific)
        status_mapping = {
            "submitted": SubmissionStatus.SUBMITTED,
            "acknowledged": SubmissionStatus.ACKNOWLEDGED,
            "in_progress": SubmissionStatus.IN_PROGRESS,
            "under_review": SubmissionStatus.UNDER_REVIEW,
            "resolved": SubmissionStatus.RESOLVED,
            "closed": SubmissionStatus.RESOLVED,
            "rejected": SubmissionStatus.REJECTED
        }
        
        # Try different field names for status
        status_value = (
            response_data.get("status") or
            response_data.get("grievance_status") or
            response_data.get("complaint_status") or
            "submitted"
        ).lower()
        
        status = status_mapping.get(status_value, SubmissionStatus.SUBMITTED)
        
        # Extract other information
        reference_number = (
            response_data.get("reference_number") or
            response_data.get("complaint_id") or
            response_data.get("ticket_id") or
            ""
        )
        
        status_message = (
            response_data.get("status_message") or
            response_data.get("message") or
            response_data.get("description") or
            f"Status: {status_value}"
        )
        
        last_updated_str = (
            response_data.get("last_updated") or
            response_data.get("updated_at") or
            datetime.now().isoformat()
        )
        
        try:
            last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
        except:
            last_updated = datetime.now()
        
        return StatusResponse(
            reference_number=reference_number,
            status=status,
            status_message=status_message,
            last_updated=last_updated,
            assigned_officer=response_data.get("assigned_officer"),
            department=response_data.get("department"),
            actions_taken=response_data.get("actions_taken", []),
            next_steps=response_data.get("next_steps", []),
            additional_info=response_data
        )
    
    async def _queue_for_retry(self, grievance: GrievanceRecord,
                             portal: GovernmentPortal, operation: str):
        """Queue request for retry processing."""
        
        request = SubmissionRequest(
            portal_id=portal.id,
            endpoint_name=operation,
            data=grievance.to_dict(),
            reference_id=str(grievance.id),
            user_id=grievance.user_id,
            language=grievance.language
        )
        
        request_key = f"{portal.id}_{operation}_{grievance.id}"
        self.pending_requests[request_key] = request
        
        logger.info(f"Queued request for retry: {request_key}")
    
    async def _process_background_requests(self):
        """Background task to process queued requests."""
        
        while not self._shutdown_event.is_set():
            try:
                # Process pending requests
                if self.pending_requests:
                    await self._process_pending_requests()
                
                # Wait before next processing cycle
                await asyncio.sleep(60)  # Process every minute
                
            except Exception as e:
                logger.error(f"Error in background request processing: {e}")
                await asyncio.sleep(60)
    
    async def _process_pending_requests(self):
        """Process pending retry requests."""
        
        requests_to_remove = []
        
        for request_key, request in self.pending_requests.items():
            try:
                # Find the portal
                portal = next((p for p in self.config.portals if p.id == request.portal_id), None)
                if not portal:
                    requests_to_remove.append(request_key)
                    continue
                
                # Check if enough time has passed for retry
                time_since_creation = datetime.now() - request.created_at
                if time_since_creation.seconds < 300:  # Wait at least 5 minutes
                    continue
                
                logger.info(f"Retrying background request: {request_key}")
                
                # Attempt the request
                if request.endpoint_name == "submit_grievance":
                    # Reconstruct grievance from data
                    grievance = GrievanceRecord.from_dict(request.data)
                    
                    # Transform data
                    endpoint = portal.get_endpoint("submit_grievance")
                    transformation_result = self.data_transformer.transform_grievance_data(
                        grievance, portal, endpoint
                    )
                    
                    if transformation_result.is_valid:
                        # Submit to portal
                        api_response = await self.api_client.submit_grievance(
                            portal, "submit_grievance",
                            transformation_result.transformed_data,
                            request.reference_id
                        )
                        
                        if api_response.is_success():
                            logger.info(f"Background retry successful: {request_key}")
                            requests_to_remove.append(request_key)
                        else:
                            logger.warning(f"Background retry failed: {request_key}")
                    else:
                        logger.warning(f"Data transformation failed for retry: {request_key}")
                        requests_to_remove.append(request_key)
                
            except Exception as e:
                logger.error(f"Error processing background request {request_key}: {e}")
                
                # Move to failed requests after too many attempts
                if request_key not in self.failed_requests:
                    self.failed_requests[request_key] = (request, e)
                    requests_to_remove.append(request_key)
        
        # Remove processed requests
        for key in requests_to_remove:
            self.pending_requests.pop(key, None)
    
    def _record_performance_metric(self, portal_id: str, execution_time: float):
        """Record performance metric for portal."""
        if portal_id not in self.performance_metrics:
            self.performance_metrics[portal_id] = []
        
        self.performance_metrics[portal_id].append(execution_time)
        
        # Keep only last 100 measurements
        if len(self.performance_metrics[portal_id]) > 100:
            self.performance_metrics[portal_id] = self.performance_metrics[portal_id][-100:]
    
    def get_portal_status(self) -> Dict[str, Any]:
        """Get status of all configured portals."""
        status = {}
        
        for portal in self.config.portals:
            circuit_breaker_status = self.api_client.get_circuit_breaker_status(portal.id)
            token_info = self.auth_manager.get_cached_token_info(portal.id)
            
            # Calculate average response time
            avg_response_time = None
            if portal.id in self.performance_metrics:
                metrics = self.performance_metrics[portal.id]
                if metrics:
                    avg_response_time = sum(metrics) / len(metrics)
            
            status[portal.id] = {
                "name": portal.name,
                "type": portal.portal_type.value,
                "is_active": portal.is_active,
                "priority": portal.priority,
                "circuit_breaker": circuit_breaker_status,
                "authentication": token_info,
                "avg_response_time": avg_response_time,
                "endpoints": list(portal.endpoints.keys())
            }
        
        return status
    
    def get_integration_metrics(self) -> Dict[str, Any]:
        """Get integration performance metrics."""
        return {
            "pending_requests": len(self.pending_requests),
            "failed_requests": len(self.failed_requests),
            "performance_metrics": {
                portal_id: {
                    "count": len(metrics),
                    "avg_time": sum(metrics) / len(metrics) if metrics else 0,
                    "min_time": min(metrics) if metrics else 0,
                    "max_time": max(metrics) if metrics else 0
                }
                for portal_id, metrics in self.performance_metrics.items()
            },
            "portal_count": len(self.config.portals),
            "active_portals": len([p for p in self.config.portals if p.is_active])
        }
    
    async def test_portal_connectivity(self, portal_id: Optional[str] = None) -> Dict[str, bool]:
        """Test connectivity to government portals."""
        results = {}
        
        portals_to_test = (
            [p for p in self.config.portals if p.id == portal_id] if portal_id
            else self.config.portals
        )
        
        for portal in portals_to_test:
            try:
                # Test basic connectivity
                connectivity_ok = await self.api_client.test_connection(portal)
                
                # Test authentication
                auth_ok = await self.auth_manager.test_authentication(portal)
                
                results[portal.id] = connectivity_ok and auth_ok
                
            except Exception as e:
                logger.error(f"Connectivity test failed for {portal.id}: {e}")
                results[portal.id] = False
        
        return results