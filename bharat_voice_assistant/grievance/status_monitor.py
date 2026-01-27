"""
Grievance status monitoring service.

This module provides real-time status polling from government systems,
status change detection, notification management, and progress visualization
for submitted grievances.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from enum import Enum
import json
from dataclasses import dataclass, field

from .models import (
    GrievanceRecord, GrievanceStatus, GrievanceSubmissionResult
)
from ..integration.models import (
    StatusResponse, SubmissionStatus, GovernmentPortal, IntegrationResult
)
from ..integration.government_api_client import GovernmentAPIClient
from ..integration.config_loader import GovernmentPortalConfigLoader
from ..core.exceptions import (
    GovernmentAPIError, NetworkError, TimeoutError, ValidationError
)
from ..core.config import config

logger = logging.getLogger(__name__)


class StatusChangeType(Enum):
    """Types of status changes."""
    STATUS_UPDATE = "status_update"
    PROGRESS_UPDATE = "progress_update"
    OFFICER_ASSIGNED = "officer_assigned"
    DOCUMENT_REQUESTED = "document_requested"
    RESOLUTION_TIMELINE = "resolution_timeline"
    FINAL_RESOLUTION = "final_resolution"
    ESCALATION = "escalation"


class NotificationChannel(Enum):
    """Notification delivery channels."""
    VOICE = "voice"
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"


@dataclass
class StatusChange:
    """Represents a status change event."""
    reference_number: str
    change_type: StatusChangeType
    old_status: Optional[SubmissionStatus] = None
    new_status: Optional[SubmissionStatus] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    assigned_officer: Optional[str] = None
    department: Optional[str] = None
    estimated_resolution_date: Optional[date] = None
    actions_required: List[str] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'reference_number': self.reference_number,
            'change_type': self.change_type.value,
            'old_status': self.old_status.value if self.old_status else None,
            'new_status': self.new_status.value if self.new_status else None,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'assigned_officer': self.assigned_officer,
            'department': self.department,
            'estimated_resolution_date': self.estimated_resolution_date.isoformat() if self.estimated_resolution_date else None,
            'actions_required': self.actions_required,
            'additional_info': self.additional_info
        }


@dataclass
class NotificationPreference:
    """User notification preferences."""
    user_id: str
    reference_number: str
    channels: List[NotificationChannel] = field(default_factory=list)
    enabled: bool = True
    language: str = "hi"
    phone_number: Optional[str] = None
    email: Optional[str] = None
    notification_types: List[StatusChangeType] = field(default_factory=lambda: list(StatusChangeType))
    quiet_hours_start: Optional[int] = None  # Hour (0-23)
    quiet_hours_end: Optional[int] = None    # Hour (0-23)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class StatusTimeline:
    """Timeline of status changes for a grievance."""
    reference_number: str
    status_history: List[StatusChange] = field(default_factory=list)
    current_status: Optional[SubmissionStatus] = None
    estimated_completion_date: Optional[date] = None
    progress_percentage: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def add_status_change(self, change: StatusChange):
        """Add a status change to the timeline."""
        self.status_history.append(change)
        if change.new_status:
            self.current_status = change.new_status
        if change.estimated_resolution_date:
            self.estimated_completion_date = change.estimated_resolution_date
        self.last_updated = datetime.now()
        self._update_progress_percentage()
    
    def _update_progress_percentage(self):
        """Update progress percentage based on current status."""
        status_progress_map = {
            SubmissionStatus.PENDING: 10.0,
            SubmissionStatus.SUBMITTED: 20.0,
            SubmissionStatus.ACKNOWLEDGED: 30.0,
            SubmissionStatus.IN_PROGRESS: 50.0,
            SubmissionStatus.UNDER_REVIEW: 70.0,
            SubmissionStatus.RESOLVED: 100.0,
            SubmissionStatus.REJECTED: 100.0,
            SubmissionStatus.FAILED: 0.0,
            SubmissionStatus.TIMEOUT: 0.0
        }
        
        if self.current_status:
            self.progress_percentage = status_progress_map.get(self.current_status, 0.0)
    
    def get_latest_change(self) -> Optional[StatusChange]:
        """Get the most recent status change."""
        return self.status_history[-1] if self.status_history else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'reference_number': self.reference_number,
            'status_history': [change.to_dict() for change in self.status_history],
            'current_status': self.current_status.value if self.current_status else None,
            'estimated_completion_date': self.estimated_completion_date.isoformat() if self.estimated_completion_date else None,
            'progress_percentage': self.progress_percentage,
            'last_updated': self.last_updated.isoformat()
        }


class GrievanceStatusMonitor:
    """
    Real-time grievance status monitoring service.
    
    Provides status polling, change detection, notifications, and
    progress visualization for submitted grievances.
    """
    
    def __init__(self, api_client: Optional[GovernmentAPIClient] = None,
                 config_loader: Optional[GovernmentPortalConfigLoader] = None):
        """Initialize the status monitor."""
        self.api_client = api_client
        self.config_loader = config_loader or GovernmentPortalConfigLoader()
        self.integration_config = None
        
        # In-memory storage for demo (in production, use database)
        self.status_timelines: Dict[str, StatusTimeline] = {}
        self.notification_preferences: Dict[str, NotificationPreference] = {}
        self.polling_tasks: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self.polling_interval = 300  # 5 minutes default
        self.max_concurrent_polls = 10
        self.retry_failed_polls = True
        
        logger.info("GrievanceStatusMonitor initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not self.api_client:
            self.api_client = GovernmentAPIClient()
        await self.api_client.__aenter__()
        
        # Load integration configuration
        self.integration_config = self.config_loader.load_integration_config()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Stop all polling tasks
        await self.stop_all_monitoring()
        
        if self.api_client:
            await self.api_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def start_monitoring(self, grievance: GrievanceRecord,
                             notification_preferences: Optional[NotificationPreference] = None) -> bool:
        """
        Start monitoring a grievance for status changes.
        
        Args:
            grievance: Grievance record to monitor
            notification_preferences: User notification preferences
            
        Returns:
            True if monitoring started successfully
        """
        try:
            reference_number = grievance.reference_number or grievance.government_reference
            if not reference_number:
                logger.warning("Cannot monitor grievance without reference number")
                return False
            
            # Create status timeline if not exists
            if reference_number not in self.status_timelines:
                self.status_timelines[reference_number] = StatusTimeline(
                    reference_number=reference_number
                )
            
            # Store notification preferences
            if notification_preferences:
                self.notification_preferences[reference_number] = notification_preferences
            
            # Start polling task if not already running
            if reference_number not in self.polling_tasks:
                task = asyncio.create_task(
                    self._poll_status_continuously(reference_number, grievance)
                )
                self.polling_tasks[reference_number] = task
                
                logger.info(f"Started monitoring grievance {reference_number}")
                return True
            else:
                logger.info(f"Already monitoring grievance {reference_number}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to start monitoring for {reference_number}: {e}")
            return False
    
    async def stop_monitoring(self, reference_number: str) -> bool:
        """
        Stop monitoring a specific grievance.
        
        Args:
            reference_number: Reference number to stop monitoring
            
        Returns:
            True if stopped successfully
        """
        try:
            if reference_number in self.polling_tasks:
                task = self.polling_tasks[reference_number]
                task.cancel()
                
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                del self.polling_tasks[reference_number]
                logger.info(f"Stopped monitoring grievance {reference_number}")
                return True
            else:
                logger.warning(f"No monitoring task found for {reference_number}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to stop monitoring for {reference_number}: {e}")
            return False
    
    async def stop_all_monitoring(self):
        """Stop all monitoring tasks."""
        tasks_to_cancel = list(self.polling_tasks.values())
        
        for task in tasks_to_cancel:
            task.cancel()
        
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        
        self.polling_tasks.clear()
        logger.info("Stopped all monitoring tasks")
    
    async def check_status_once(self, reference_number: str,
                              portal_id: Optional[str] = None) -> Optional[StatusResponse]:
        """
        Check status once for a specific reference number.
        
        Args:
            reference_number: Reference number to check
            portal_id: Specific portal to check (optional)
            
        Returns:
            StatusResponse if successful, None otherwise
        """
        try:
            if not self.integration_config:
                logger.error("Integration configuration not loaded")
                return None
            
            # Determine which portals to check
            portals_to_check = []
            if portal_id:
                portal = next((p for p in self.integration_config.portals if p.id == portal_id), None)
                if portal:
                    portals_to_check = [portal]
            else:
                # Check all active grievance portals
                portals_to_check = [
                    p for p in self.integration_config.portals 
                    if p.is_active and 'status' in p.endpoints
                ]
            
            if not portals_to_check:
                logger.warning("No portals available for status checking")
                return None
            
            # Try each portal until we get a successful response
            for portal in portals_to_check:
                try:
                    api_response = await self.api_client.check_status(
                        portal, 'status', reference_number
                    )
                    
                    if api_response.is_success() and api_response.data:
                        # Convert API response to StatusResponse
                        status_response = self._parse_status_response(api_response.data, reference_number)
                        
                        # Update timeline
                        await self._update_status_timeline(reference_number, status_response)
                        
                        logger.info(f"Successfully checked status for {reference_number} on {portal.id}")
                        return status_response
                    
                except Exception as e:
                    logger.warning(f"Failed to check status on {portal.id}: {e}")
                    continue
            
            logger.warning(f"Failed to check status on all available portals for {reference_number}")
            return None
            
        except Exception as e:
            logger.error(f"Error checking status for {reference_number}: {e}")
            return None
    
    async def get_status_timeline(self, reference_number: str) -> Optional[StatusTimeline]:
        """
        Get the complete status timeline for a grievance.
        
        Args:
            reference_number: Reference number to get timeline for
            
        Returns:
            StatusTimeline if found, None otherwise
        """
        return self.status_timelines.get(reference_number)
    
    async def get_current_status(self, reference_number: str) -> Optional[Dict[str, Any]]:
        """
        Get current status information for a grievance.
        
        Args:
            reference_number: Reference number to get status for
            
        Returns:
            Dictionary with current status information
        """
        timeline = await self.get_status_timeline(reference_number)
        if not timeline:
            # Try to fetch status once
            status_response = await self.check_status_once(reference_number)
            if status_response:
                timeline = self.status_timelines.get(reference_number)
        
        if timeline:
            latest_change = timeline.get_latest_change()
            return {
                'reference_number': reference_number,
                'current_status': timeline.current_status.value if timeline.current_status else 'unknown',
                'progress_percentage': timeline.progress_percentage,
                'estimated_completion_date': timeline.estimated_completion_date.isoformat() if timeline.estimated_completion_date else None,
                'last_updated': timeline.last_updated.isoformat(),
                'latest_message': latest_change.message if latest_change else None,
                'assigned_officer': latest_change.assigned_officer if latest_change else None,
                'department': latest_change.department if latest_change else None,
                'actions_required': latest_change.actions_required if latest_change else []
            }
        
        return None
    
    async def set_notification_preferences(self, preference: NotificationPreference):
        """Set notification preferences for a user."""
        self.notification_preferences[preference.reference_number] = preference
        logger.info(f"Updated notification preferences for {preference.reference_number}")
    
    async def get_notification_preferences(self, reference_number: str) -> Optional[NotificationPreference]:
        """Get notification preferences for a reference number."""
        return self.notification_preferences.get(reference_number)
    
    async def _poll_status_continuously(self, reference_number: str, grievance: GrievanceRecord):
        """Continuously poll status for a grievance."""
        logger.info(f"Starting continuous polling for {reference_number}")
        
        try:
            while True:
                try:
                    # Check status
                    status_response = await self.check_status_once(reference_number)
                    
                    if status_response:
                        # Check if this is a final status
                        if status_response.status in [SubmissionStatus.RESOLVED, SubmissionStatus.REJECTED]:
                            logger.info(f"Grievance {reference_number} reached final status: {status_response.status}")
                            break
                    
                    # Wait for next poll
                    await asyncio.sleep(self.polling_interval)
                    
                except asyncio.CancelledError:
                    logger.info(f"Polling cancelled for {reference_number}")
                    break
                    
                except Exception as e:
                    logger.error(f"Error during polling for {reference_number}: {e}")
                    
                    if self.retry_failed_polls:
                        # Wait shorter interval before retry
                        await asyncio.sleep(min(60, self.polling_interval // 5))
                    else:
                        break
                        
        except Exception as e:
            logger.error(f"Fatal error in polling task for {reference_number}: {e}")
        finally:
            # Clean up
            if reference_number in self.polling_tasks:
                del self.polling_tasks[reference_number]
            logger.info(f"Polling task ended for {reference_number}")
    
    async def _update_status_timeline(self, reference_number: str, status_response: StatusResponse):
        """Update status timeline with new status information."""
        timeline = self.status_timelines.get(reference_number)
        if not timeline:
            timeline = StatusTimeline(reference_number=reference_number)
            self.status_timelines[reference_number] = timeline
        
        # Check if this is a status change
        old_status = timeline.current_status
        new_status = status_response.status
        
        if old_status != new_status or not timeline.status_history:
            # Create status change event
            change = StatusChange(
                reference_number=reference_number,
                change_type=StatusChangeType.STATUS_UPDATE,
                old_status=old_status,
                new_status=new_status,
                message=status_response.status_message,
                assigned_officer=status_response.assigned_officer,
                department=status_response.department,
                estimated_resolution_date=status_response.estimated_resolution_date,
                actions_required=status_response.next_steps,
                additional_info=status_response.additional_info
            )
            
            # Add to timeline
            timeline.add_status_change(change)
            
            # Send notifications if this is a change
            if old_status != new_status and old_status is not None:
                await self._send_notifications(change)
            
            logger.info(f"Updated status timeline for {reference_number}: {old_status} -> {new_status}")
    
    def _parse_status_response(self, api_data: Dict[str, Any], reference_number: str) -> StatusResponse:
        """Parse API response data into StatusResponse."""
        # Map common status strings to SubmissionStatus enum
        status_mapping = {
            'pending': SubmissionStatus.PENDING,
            'submitted': SubmissionStatus.SUBMITTED,
            'acknowledged': SubmissionStatus.ACKNOWLEDGED,
            'in_progress': SubmissionStatus.IN_PROGRESS,
            'under_review': SubmissionStatus.UNDER_REVIEW,
            'resolved': SubmissionStatus.RESOLVED,
            'rejected': SubmissionStatus.REJECTED,
            'failed': SubmissionStatus.FAILED,
            'timeout': SubmissionStatus.TIMEOUT
        }
        
        # Extract status
        status_str = str(api_data.get('status', 'pending')).lower()
        status = status_mapping.get(status_str, SubmissionStatus.PENDING)
        
        # Extract other fields
        status_message = api_data.get('status_message', api_data.get('message', ''))
        last_updated_str = api_data.get('last_updated', api_data.get('updated_at'))
        
        # Parse last updated
        last_updated = datetime.now()
        if last_updated_str:
            try:
                last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
            except:
                pass
        
        # Parse estimated resolution date
        estimated_resolution_date = None
        resolution_date_str = api_data.get('estimated_resolution_date', api_data.get('expected_completion'))
        if resolution_date_str:
            try:
                estimated_resolution_date = datetime.fromisoformat(resolution_date_str.replace('Z', '+00:00')).date()
            except:
                pass
        
        return StatusResponse(
            reference_number=reference_number,
            status=status,
            status_message=status_message,
            last_updated=last_updated,
            assigned_officer=api_data.get('assigned_officer'),
            department=api_data.get('department'),
            estimated_resolution_date=estimated_resolution_date,
            actions_taken=api_data.get('actions_taken', []),
            next_steps=api_data.get('next_steps', []),
            additional_info=api_data.get('additional_info', {})
        )
    
    async def _send_notifications(self, change: StatusChange):
        """Send notifications for status changes."""
        preferences = self.notification_preferences.get(change.reference_number)
        if not preferences or not preferences.enabled:
            return
        
        # Check if this change type should trigger notifications
        if change.change_type not in preferences.notification_types:
            return
        
        # Check quiet hours
        if self._is_quiet_hours(preferences):
            logger.info(f"Skipping notification during quiet hours for {change.reference_number}")
            return
        
        # Generate notification message
        message = self._generate_notification_message(change, preferences.language)
        
        # Send through preferred channels
        for channel in preferences.channels:
            try:
                await self._send_notification_via_channel(
                    channel, message, preferences, change
                )
            except Exception as e:
                logger.error(f"Failed to send notification via {channel}: {e}")
    
    def _is_quiet_hours(self, preferences: NotificationPreference) -> bool:
        """Check if current time is within quiet hours."""
        if not preferences.quiet_hours_start or not preferences.quiet_hours_end:
            return False
        
        current_hour = datetime.now().hour
        start = preferences.quiet_hours_start
        end = preferences.quiet_hours_end
        
        if start <= end:
            return start <= current_hour <= end
        else:  # Quiet hours span midnight
            return current_hour >= start or current_hour <= end
    
    def _generate_notification_message(self, change: StatusChange, language: str) -> str:
        """Generate notification message based on language."""
        if language == 'hi':
            messages = {
                StatusChangeType.STATUS_UPDATE: f"आपकी शिकायत {change.reference_number} की स्थिति अपडेट हुई है: {change.message}",
                StatusChangeType.OFFICER_ASSIGNED: f"आपकी शिकायत {change.reference_number} को {change.assigned_officer} को सौंपा गया है",
                StatusChangeType.FINAL_RESOLUTION: f"आपकी शिकायत {change.reference_number} का समाधान हो गया है: {change.message}",
                StatusChangeType.DOCUMENT_REQUESTED: f"आपकी शिकायत {change.reference_number} के लिए अतिरिक्त दस्तावेज़ चाहिए",
                StatusChangeType.ESCALATION: f"आपकी शिकायत {change.reference_number} को उच्च अधिकारी को भेजा गया है"
            }
        else:  # English
            messages = {
                StatusChangeType.STATUS_UPDATE: f"Your grievance {change.reference_number} status has been updated: {change.message}",
                StatusChangeType.OFFICER_ASSIGNED: f"Your grievance {change.reference_number} has been assigned to {change.assigned_officer}",
                StatusChangeType.FINAL_RESOLUTION: f"Your grievance {change.reference_number} has been resolved: {change.message}",
                StatusChangeType.DOCUMENT_REQUESTED: f"Additional documents are required for your grievance {change.reference_number}",
                StatusChangeType.ESCALATION: f"Your grievance {change.reference_number} has been escalated to higher authority"
            }
        
        return messages.get(change.change_type, change.message)
    
    async def _send_notification_via_channel(self, channel: NotificationChannel,
                                           message: str, preferences: NotificationPreference,
                                           change: StatusChange):
        """Send notification through specific channel."""
        # This is a placeholder implementation
        # In production, integrate with actual notification services
        
        if channel == NotificationChannel.SMS and preferences.phone_number:
            logger.info(f"SMS notification sent to {preferences.phone_number}: {message}")
            
        elif channel == NotificationChannel.EMAIL and preferences.email:
            logger.info(f"Email notification sent to {preferences.email}: {message}")
            
        elif channel == NotificationChannel.VOICE:
            # Could integrate with voice calling service
            logger.info(f"Voice notification queued: {message}")
            
        elif channel == NotificationChannel.IN_APP:
            # Store for in-app display
            logger.info(f"In-app notification: {message}")
            
        else:
            logger.warning(f"Notification channel {channel} not implemented or missing contact info")
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            'active_monitoring_tasks': len(self.polling_tasks),
            'total_timelines': len(self.status_timelines),
            'notification_preferences': len(self.notification_preferences),
            'polling_interval': self.polling_interval,
            'max_concurrent_polls': self.max_concurrent_polls,
            'monitored_references': list(self.polling_tasks.keys())
        }