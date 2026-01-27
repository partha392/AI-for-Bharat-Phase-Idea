"""
User notification system for grievance status changes.

This module provides comprehensive notification management including
proactive notifications, escalation triggers, and user preference management.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta, date
from enum import Enum
from dataclasses import dataclass, field
import json
from abc import ABC, abstractmethod

from .models import GrievanceRecord, GrievanceStatus
from .status_monitor import (
    StatusChange, StatusChangeType, NotificationChannel, NotificationPreference,
    GrievanceStatusMonitor
)
from ..integration.models import SubmissionStatus
from ..core.exceptions import NotificationError, ValidationError
from ..core.config import config

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    """Escalation levels for delayed cases."""
    NONE = "none"
    LEVEL_1 = "level_1"  # First escalation
    LEVEL_2 = "level_2"  # Second escalation
    LEVEL_3 = "level_3"  # Final escalation


class NotificationPriority(Enum):
    """Priority levels for notifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(Enum):
    """Status of notification delivery."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class EscalationRule:
    """Rules for escalating delayed cases."""
    status: SubmissionStatus
    delay_threshold_days: int
    escalation_level: EscalationLevel
    notification_message_key: str
    escalation_department: Optional[str] = None
    escalation_officer: Optional[str] = None
    auto_escalate: bool = True
    
    def is_applicable(self, current_status: SubmissionStatus, days_in_status: int) -> bool:
        """Check if escalation rule applies to current case."""
        return self.status == current_status and days_in_status >= self.delay_threshold_days


@dataclass
class NotificationTemplate:
    """Template for notification messages."""
    template_id: str
    change_type: StatusChangeType
    language: str
    channel: NotificationChannel
    subject_template: str
    message_template: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    variables: List[str] = field(default_factory=list)
    
    def render(self, variables: Dict[str, Any]) -> Tuple[str, str]:
        """Render template with variables."""
        try:
            subject = self.subject_template.format(**variables)
            message = self.message_template.format(**variables)
            return subject, message
        except KeyError as e:
            logger.error(f"Missing variable {e} for template {self.template_id}")
            return self.subject_template, self.message_template


@dataclass
class NotificationRecord:
    """Record of a notification sent to user."""
    notification_id: str
    reference_number: str
    user_id: str
    channel: NotificationChannel
    change_type: StatusChangeType
    priority: NotificationPriority
    subject: str
    message: str
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'notification_id': self.notification_id,
            'reference_number': self.reference_number,
            'user_id': self.user_id,
            'channel': self.channel.value,
            'change_type': self.change_type.value,
            'priority': self.priority.value,
            'subject': self.subject,
            'message': self.message,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'error_message': self.error_message,
            'metadata': self.metadata
        }


@dataclass
class UserNotificationPreferences:
    """Enhanced user notification preferences."""
    user_id: str
    reference_numbers: Set[str] = field(default_factory=set)
    global_enabled: bool = True
    channels: List[NotificationChannel] = field(default_factory=list)
    language: str = "hi"
    
    # Contact information
    phone_number: Optional[str] = None
    email: Optional[str] = None
    
    # Notification types
    enabled_change_types: Set[StatusChangeType] = field(default_factory=lambda: set(StatusChangeType))
    
    # Timing preferences
    quiet_hours_start: Optional[int] = None  # Hour (0-23)
    quiet_hours_end: Optional[int] = None    # Hour (0-23)
    timezone: str = "Asia/Kolkata"
    
    # Escalation preferences
    escalation_notifications: bool = True
    escalation_channels: List[NotificationChannel] = field(default_factory=list)
    
    # Frequency control
    max_notifications_per_day: int = 10
    batch_notifications: bool = False
    batch_interval_hours: int = 4
    
    # Priority filtering
    min_priority: NotificationPriority = NotificationPriority.LOW
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def is_notification_allowed(self, change_type: StatusChangeType, 
                              priority: NotificationPriority,
                              current_time: Optional[datetime] = None) -> bool:
        """Check if notification is allowed based on preferences."""
        if not self.global_enabled:
            return False
        
        if change_type not in self.enabled_change_types:
            return False
        
        if priority.value < self.min_priority.value:
            return False
        
        # Check quiet hours
        if self._is_quiet_hours(current_time):
            return priority == NotificationPriority.URGENT
        
        return True
    
    def _is_quiet_hours(self, current_time: Optional[datetime] = None) -> bool:
        """Check if current time is within quiet hours."""
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        if not current_time:
            current_time = datetime.now()
        
        current_hour = current_time.hour
        start = self.quiet_hours_start
        end = self.quiet_hours_end
        
        if start <= end:
            return start <= current_hour <= end
        else:  # Quiet hours span midnight
            return current_hour >= start or current_hour <= end


class NotificationChannel_Handler(ABC):
    """Abstract base class for notification channel handlers."""
    
    @abstractmethod
    async def send_notification(self, notification: NotificationRecord,
                              preferences: UserNotificationPreferences) -> bool:
        """Send notification through this channel."""
        pass
    
    @abstractmethod
    def get_channel_type(self) -> NotificationChannel:
        """Get the channel type this handler supports."""
        pass


class SMSNotificationHandler(NotificationChannel_Handler):
    """SMS notification handler."""
    
    def __init__(self):
        self.sms_service_url = os.getenv('SMS_SERVICE_URL')
        self.sms_api_key = os.getenv('SMS_API_KEY')
    
    async def send_notification(self, notification: NotificationRecord,
                              preferences: UserNotificationPreferences) -> bool:
        """Send SMS notification."""
        try:
            if not preferences.phone_number:
                logger.warning(f"No phone number for user {preferences.user_id}")
                return False
            
            # In production, integrate with actual SMS service
            logger.info(f"SMS sent to {preferences.phone_number}: {notification.message}")
            
            # Simulate SMS sending
            await asyncio.sleep(0.1)
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {e}")
            return False
    
    def get_channel_type(self) -> NotificationChannel:
        return NotificationChannel.SMS


class EmailNotificationHandler(NotificationChannel_Handler):
    """Email notification handler."""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
    
    async def send_notification(self, notification: NotificationRecord,
                              preferences: UserNotificationPreferences) -> bool:
        """Send email notification."""
        try:
            if not preferences.email:
                logger.warning(f"No email address for user {preferences.user_id}")
                return False
            
            # In production, integrate with actual email service
            logger.info(f"Email sent to {preferences.email}: {notification.subject}")
            
            # Simulate email sending
            await asyncio.sleep(0.1)
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    def get_channel_type(self) -> NotificationChannel:
        return NotificationChannel.EMAIL


class VoiceNotificationHandler(NotificationChannel_Handler):
    """Voice notification handler."""
    
    def __init__(self):
        self.voice_service_url = os.getenv('VOICE_SERVICE_URL')
        self.voice_api_key = os.getenv('VOICE_API_KEY')
    
    async def send_notification(self, notification: NotificationRecord,
                              preferences: UserNotificationPreferences) -> bool:
        """Send voice notification."""
        try:
            if not preferences.phone_number:
                logger.warning(f"No phone number for user {preferences.user_id}")
                return False
            
            # In production, integrate with voice calling service
            logger.info(f"Voice call initiated to {preferences.phone_number}: {notification.message}")
            
            # Simulate voice call
            await asyncio.sleep(0.2)
            return True
            
        except Exception as e:
            logger.error(f"Failed to send voice notification: {e}")
            return False
    
    def get_channel_type(self) -> NotificationChannel:
        return NotificationChannel.VOICE


class InAppNotificationHandler(NotificationChannel_Handler):
    """In-app notification handler."""
    
    def __init__(self):
        self.notification_store: Dict[str, List[NotificationRecord]] = {}
    
    async def send_notification(self, notification: NotificationRecord,
                              preferences: UserNotificationPreferences) -> bool:
        """Store in-app notification."""
        try:
            user_id = preferences.user_id
            if user_id not in self.notification_store:
                self.notification_store[user_id] = []
            
            self.notification_store[user_id].append(notification)
            
            # Keep only last 50 notifications per user
            if len(self.notification_store[user_id]) > 50:
                self.notification_store[user_id] = self.notification_store[user_id][-50:]
            
            logger.info(f"In-app notification stored for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store in-app notification: {e}")
            return False
    
    def get_channel_type(self) -> NotificationChannel:
        return NotificationChannel.IN_APP
    
    def get_user_notifications(self, user_id: str, limit: int = 20) -> List[NotificationRecord]:
        """Get in-app notifications for user."""
        return self.notification_store.get(user_id, [])[-limit:]


class UserNotificationSystem:
    """
    Comprehensive user notification system.
    
    Provides proactive notifications, escalation triggers, and
    user preference management for grievance status changes.
    """
    
    def __init__(self, status_monitor: Optional[GrievanceStatusMonitor] = None):
        """Initialize the notification system."""
        self.status_monitor = status_monitor
        
        # Storage (in production, use database)
        self.user_preferences: Dict[str, UserNotificationPreferences] = {}
        self.notification_records: Dict[str, NotificationRecord] = {}
        self.escalation_rules: List[EscalationRule] = []
        self.notification_templates: Dict[str, NotificationTemplate] = {}
        
        # Channel handlers
        self.channel_handlers: Dict[NotificationChannel, NotificationChannel_Handler] = {
            NotificationChannel.SMS: SMSNotificationHandler(),
            NotificationChannel.EMAIL: EmailNotificationHandler(),
            NotificationChannel.VOICE: VoiceNotificationHandler(),
            NotificationChannel.IN_APP: InAppNotificationHandler()
        }
        
        # Background tasks
        self.escalation_task: Optional[asyncio.Task] = None
        self.retry_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.escalation_check_interval = 3600  # 1 hour
        self.retry_interval = 300  # 5 minutes
        
        # Initialize default rules and templates
        self._initialize_escalation_rules()
        self._initialize_notification_templates()
        
        logger.info("UserNotificationSystem initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not self.status_monitor:
            self.status_monitor = GrievanceStatusMonitor()
        await self.status_monitor.__aenter__()
        
        # Start background tasks
        self.escalation_task = asyncio.create_task(self._escalation_monitor())
        self.retry_task = asyncio.create_task(self._retry_failed_notifications())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Stop background tasks
        if self.escalation_task:
            self.escalation_task.cancel()
            try:
                await self.escalation_task
            except asyncio.CancelledError:
                pass
        
        if self.retry_task:
            self.retry_task.cancel()
            try:
                await self.retry_task
            except asyncio.CancelledError:
                pass
        
        if self.status_monitor:
            await self.status_monitor.__aexit__(exc_type, exc_val, exc_tb)
    
    async def setup_user_notifications(self, user_id: str, reference_number: str,
                                     phone_number: Optional[str] = None,
                                     email: Optional[str] = None,
                                     language: str = "hi",
                                     channels: Optional[List[NotificationChannel]] = None,
                                     change_types: Optional[List[StatusChangeType]] = None) -> bool:
        """
        Set up notifications for a user and grievance.
        
        Args:
            user_id: User identifier
            reference_number: Grievance reference number
            phone_number: User's phone number
            email: User's email address
            language: User's preferred language
            channels: Preferred notification channels
            change_types: Types of changes to notify about
            
        Returns:
            True if setup was successful
        """
        try:
            # Get or create user preferences
            if user_id not in self.user_preferences:
                self.user_preferences[user_id] = UserNotificationPreferences(
                    user_id=user_id,
                    language=language,
                    phone_number=phone_number,
                    email=email
                )
            
            preferences = self.user_preferences[user_id]
            
            # Add reference number
            preferences.reference_numbers.add(reference_number)
            
            # Update contact information if provided
            if phone_number:
                preferences.phone_number = phone_number
            if email:
                preferences.email = email
            
            # Set channels
            if channels:
                preferences.channels = channels
            elif not preferences.channels:
                # Default channels based on available contact info
                default_channels = [NotificationChannel.IN_APP]
                if preferences.phone_number:
                    default_channels.append(NotificationChannel.SMS)
                if preferences.email:
                    default_channels.append(NotificationChannel.EMAIL)
                preferences.channels = default_channels
            
            # Set change types
            if change_types:
                preferences.enabled_change_types = set(change_types)
            elif not preferences.enabled_change_types:
                # Default to all change types
                preferences.enabled_change_types = set(StatusChangeType)
            
            preferences.updated_at = datetime.now()
            
            # Set up monitoring with status monitor
            notification_preference = NotificationPreference(
                user_id=user_id,
                reference_number=reference_number,
                channels=preferences.channels,
                language=preferences.language,
                phone_number=preferences.phone_number,
                email=preferences.email,
                notification_types=list(preferences.enabled_change_types)
            )
            
            await self.status_monitor.set_notification_preferences(notification_preference)
            
            logger.info(f"Set up notifications for user {user_id}, reference {reference_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup notifications for user {user_id}: {e}")
            return False
    
    async def update_user_preferences(self, user_id: str,
                                    preferences_update: Dict[str, Any]) -> bool:
        """
        Update user notification preferences.
        
        Args:
            user_id: User identifier
            preferences_update: Dictionary of preferences to update
            
        Returns:
            True if update was successful
        """
        try:
            if user_id not in self.user_preferences:
                logger.warning(f"No preferences found for user {user_id}")
                return False
            
            preferences = self.user_preferences[user_id]
            
            # Update preferences
            for key, value in preferences_update.items():
                if hasattr(preferences, key):
                    if key == 'channels' and isinstance(value, list):
                        preferences.channels = [NotificationChannel(ch) for ch in value]
                    elif key == 'enabled_change_types' and isinstance(value, list):
                        preferences.enabled_change_types = {StatusChangeType(ct) for ct in value}
                    elif key == 'escalation_channels' and isinstance(value, list):
                        preferences.escalation_channels = [NotificationChannel(ch) for ch in value]
                    elif key == 'min_priority' and isinstance(value, str):
                        preferences.min_priority = NotificationPriority(value)
                    else:
                        setattr(preferences, key, value)
            
            preferences.updated_at = datetime.now()
            
            logger.info(f"Updated preferences for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update preferences for user {user_id}: {e}")
            return False
    
    async def send_status_change_notification(self, status_change: StatusChange) -> bool:
        """
        Send notifications for a status change.
        
        Args:
            status_change: Status change event
            
        Returns:
            True if notifications were sent successfully
        """
        try:
            reference_number = status_change.reference_number
            
            # Find users who should be notified
            users_to_notify = []
            for user_id, preferences in self.user_preferences.items():
                if reference_number in preferences.reference_numbers:
                    users_to_notify.append((user_id, preferences))
            
            if not users_to_notify:
                logger.info(f"No users to notify for reference {reference_number}")
                return True
            
            # Determine notification priority
            priority = self._determine_notification_priority(status_change)
            
            # Send notifications to each user
            success_count = 0
            for user_id, preferences in users_to_notify:
                if preferences.is_notification_allowed(status_change.change_type, priority):
                    success = await self._send_user_notification(
                        user_id, preferences, status_change, priority
                    )
                    if success:
                        success_count += 1
            
            logger.info(f"Sent notifications to {success_count}/{len(users_to_notify)} users for {reference_number}")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send status change notifications: {e}")
            return False
    
    async def check_and_escalate_delayed_cases(self) -> int:
        """
        Check for delayed cases and trigger escalations.
        
        Returns:
            Number of cases escalated
        """
        try:
            escalated_count = 0
            
            # Get all monitored grievances
            monitoring_stats = self.status_monitor.get_monitoring_stats()
            monitored_references = monitoring_stats.get('monitored_references', [])
            
            for reference_number in monitored_references:
                timeline = await self.status_monitor.get_status_timeline(reference_number)
                if not timeline or not timeline.current_status:
                    continue
                
                # Calculate days in current status
                latest_change = timeline.get_latest_change()
                if not latest_change:
                    continue
                
                days_in_status = (datetime.now() - latest_change.timestamp).days
                
                # Check escalation rules
                for rule in self.escalation_rules:
                    if rule.is_applicable(timeline.current_status, days_in_status):
                        escalated = await self._escalate_case(reference_number, rule, timeline)
                        if escalated:
                            escalated_count += 1
                        break  # Only apply first matching rule
            
            if escalated_count > 0:
                logger.info(f"Escalated {escalated_count} delayed cases")
            
            return escalated_count
            
        except Exception as e:
            logger.error(f"Error checking delayed cases: {e}")
            return 0
    
    def get_user_preferences(self, user_id: str) -> Optional[UserNotificationPreferences]:
        """Get user notification preferences."""
        return self.user_preferences.get(user_id)
    
    def get_user_notifications(self, user_id: str, limit: int = 20) -> List[NotificationRecord]:
        """Get in-app notifications for user."""
        in_app_handler = self.channel_handlers.get(NotificationChannel.IN_APP)
        if isinstance(in_app_handler, InAppNotificationHandler):
            return in_app_handler.get_user_notifications(user_id, limit)
        return []
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification system statistics."""
        total_notifications = len(self.notification_records)
        status_counts = {}
        channel_counts = {}
        
        for notification in self.notification_records.values():
            status = notification.status.value
            channel = notification.channel.value
            
            status_counts[status] = status_counts.get(status, 0) + 1
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
        
        return {
            'total_users': len(self.user_preferences),
            'total_notifications': total_notifications,
            'status_distribution': status_counts,
            'channel_distribution': channel_counts,
            'escalation_rules': len(self.escalation_rules),
            'notification_templates': len(self.notification_templates)
        }
    
    async def _send_user_notification(self, user_id: str,
                                    preferences: UserNotificationPreferences,
                                    status_change: StatusChange,
                                    priority: NotificationPriority) -> bool:
        """Send notification to a specific user."""
        try:
            success_count = 0
            
            # Send through each preferred channel
            for channel in preferences.channels:
                if channel not in self.channel_handlers:
                    logger.warning(f"No handler for channel {channel}")
                    continue
                
                # Get notification template
                template = self._get_notification_template(
                    status_change.change_type, preferences.language, channel
                )
                
                if not template:
                    logger.warning(f"No template for {status_change.change_type} in {preferences.language}")
                    continue
                
                # Render notification content
                variables = self._prepare_template_variables(status_change, preferences)
                subject, message = template.render(variables)
                
                # Create notification record
                notification_id = f"{user_id}_{status_change.reference_number}_{datetime.now().timestamp()}"
                notification = NotificationRecord(
                    notification_id=notification_id,
                    reference_number=status_change.reference_number,
                    user_id=user_id,
                    channel=channel,
                    change_type=status_change.change_type,
                    priority=priority,
                    subject=subject,
                    message=message
                )
                
                # Send notification
                handler = self.channel_handlers[channel]
                success = await handler.send_notification(notification, preferences)
                
                if success:
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.now()
                    success_count += 1
                else:
                    notification.status = NotificationStatus.FAILED
                    notification.error_message = "Failed to send notification"
                
                # Store notification record
                self.notification_records[notification_id] = notification
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            return False
    
    async def _escalate_case(self, reference_number: str, rule: EscalationRule,
                           timeline) -> bool:
        """Escalate a delayed case."""
        try:
            # Create escalation status change
            escalation_change = StatusChange(
                reference_number=reference_number,
                change_type=StatusChangeType.ESCALATION,
                old_status=timeline.current_status,
                new_status=timeline.current_status,  # Status doesn't change, just escalated
                message=f"Case escalated to {rule.escalation_level.value} due to delay",
                department=rule.escalation_department,
                assigned_officer=rule.escalation_officer,
                additional_info={
                    'escalation_level': rule.escalation_level.value,
                    'delay_days': (datetime.now() - timeline.get_latest_change().timestamp).days,
                    'escalation_reason': 'delay_threshold_exceeded'
                }
            )
            
            # Add to timeline
            timeline.add_status_change(escalation_change)
            
            # Send escalation notifications
            await self._send_escalation_notifications(escalation_change, rule)
            
            logger.info(f"Escalated case {reference_number} to {rule.escalation_level.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to escalate case {reference_number}: {e}")
            return False
    
    async def _send_escalation_notifications(self, escalation_change: StatusChange,
                                           rule: EscalationRule):
        """Send notifications for case escalation."""
        try:
            reference_number = escalation_change.reference_number
            
            # Find users who should be notified about escalations
            for user_id, preferences in self.user_preferences.items():
                if (reference_number in preferences.reference_numbers and 
                    preferences.escalation_notifications):
                    
                    # Use escalation channels if specified, otherwise regular channels
                    channels = preferences.escalation_channels or preferences.channels
                    
                    for channel in channels:
                        if channel not in self.channel_handlers:
                            continue
                        
                        # Get escalation template
                        template = self._get_escalation_template(
                            rule.escalation_level, preferences.language, channel
                        )
                        
                        if not template:
                            continue
                        
                        # Render notification
                        variables = self._prepare_escalation_variables(
                            escalation_change, rule, preferences
                        )
                        subject, message = template.render(variables)
                        
                        # Create and send notification
                        notification_id = f"esc_{user_id}_{reference_number}_{datetime.now().timestamp()}"
                        notification = NotificationRecord(
                            notification_id=notification_id,
                            reference_number=reference_number,
                            user_id=user_id,
                            channel=channel,
                            change_type=StatusChangeType.ESCALATION,
                            priority=NotificationPriority.HIGH,
                            subject=subject,
                            message=message
                        )
                        
                        handler = self.channel_handlers[channel]
                        success = await handler.send_notification(notification, preferences)
                        
                        notification.status = NotificationStatus.SENT if success else NotificationStatus.FAILED
                        if success:
                            notification.sent_at = datetime.now()
                        
                        self.notification_records[notification_id] = notification
            
        except Exception as e:
            logger.error(f"Failed to send escalation notifications: {e}")
    
    async def _escalation_monitor(self):
        """Background task to monitor for escalations."""
        logger.info("Starting escalation monitor")
        
        try:
            while True:
                try:
                    await self.check_and_escalate_delayed_cases()
                    await asyncio.sleep(self.escalation_check_interval)
                    
                except asyncio.CancelledError:
                    logger.info("Escalation monitor cancelled")
                    break
                    
                except Exception as e:
                    logger.error(f"Error in escalation monitor: {e}")
                    await asyncio.sleep(60)  # Wait 1 minute before retry
                    
        except Exception as e:
            logger.error(f"Fatal error in escalation monitor: {e}")
    
    async def _retry_failed_notifications(self):
        """Background task to retry failed notifications."""
        logger.info("Starting notification retry task")
        
        try:
            while True:
                try:
                    await self._retry_failed_notifications_once()
                    await asyncio.sleep(self.retry_interval)
                    
                except asyncio.CancelledError:
                    logger.info("Notification retry task cancelled")
                    break
                    
                except Exception as e:
                    logger.error(f"Error in notification retry task: {e}")
                    await asyncio.sleep(60)  # Wait 1 minute before retry
                    
        except Exception as e:
            logger.error(f"Fatal error in notification retry task: {e}")
    
    async def _retry_failed_notifications_once(self):
        """Retry failed notifications once."""
        try:
            failed_notifications = [
                notification for notification in self.notification_records.values()
                if (notification.status == NotificationStatus.FAILED and 
                    notification.retry_count < notification.max_retries)
            ]
            
            for notification in failed_notifications:
                try:
                    # Get user preferences
                    preferences = self.user_preferences.get(notification.user_id)
                    if not preferences:
                        continue
                    
                    # Retry sending
                    handler = self.channel_handlers.get(notification.channel)
                    if not handler:
                        continue
                    
                    success = await handler.send_notification(notification, preferences)
                    
                    notification.retry_count += 1
                    
                    if success:
                        notification.status = NotificationStatus.SENT
                        notification.sent_at = datetime.now()
                        logger.info(f"Successfully retried notification {notification.notification_id}")
                    else:
                        if notification.retry_count >= notification.max_retries:
                            notification.status = NotificationStatus.FAILED
                            logger.warning(f"Max retries reached for notification {notification.notification_id}")
                        else:
                            notification.status = NotificationStatus.RETRY
                
                except Exception as e:
                    logger.error(f"Error retrying notification {notification.notification_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in retry failed notifications: {e}")
    
    def _determine_notification_priority(self, status_change: StatusChange) -> NotificationPriority:
        """Determine notification priority based on status change."""
        priority_map = {
            StatusChangeType.FINAL_RESOLUTION: NotificationPriority.HIGH,
            StatusChangeType.ESCALATION: NotificationPriority.HIGH,
            StatusChangeType.DOCUMENT_REQUESTED: NotificationPriority.HIGH,
            StatusChangeType.STATUS_UPDATE: NotificationPriority.NORMAL,
            StatusChangeType.PROGRESS_UPDATE: NotificationPriority.NORMAL,
            StatusChangeType.OFFICER_ASSIGNED: NotificationPriority.NORMAL,
            StatusChangeType.RESOLUTION_TIMELINE: NotificationPriority.LOW
        }
        
        return priority_map.get(status_change.change_type, NotificationPriority.NORMAL)
    
    def _get_notification_template(self, change_type: StatusChangeType,
                                 language: str, channel: NotificationChannel) -> Optional[NotificationTemplate]:
        """Get notification template for change type, language, and channel."""
        template_key = f"{change_type.value}_{language}_{channel.value}"
        return self.notification_templates.get(template_key)
    
    def _get_escalation_template(self, escalation_level: EscalationLevel,
                               language: str, channel: NotificationChannel) -> Optional[NotificationTemplate]:
        """Get escalation notification template."""
        template_key = f"escalation_{escalation_level.value}_{language}_{channel.value}"
        return self.notification_templates.get(template_key)
    
    def _prepare_template_variables(self, status_change: StatusChange,
                                  preferences: UserNotificationPreferences) -> Dict[str, Any]:
        """Prepare variables for template rendering."""
        return {
            'reference_number': status_change.reference_number,
            'old_status': status_change.old_status.value if status_change.old_status else '',
            'new_status': status_change.new_status.value if status_change.new_status else '',
            'message': status_change.message,
            'assigned_officer': status_change.assigned_officer or '',
            'department': status_change.department or '',
            'estimated_date': status_change.estimated_resolution_date.strftime('%d/%m/%Y') if status_change.estimated_resolution_date else '',
            'actions_required': ', '.join(status_change.actions_required),
            'timestamp': status_change.timestamp.strftime('%d/%m/%Y %H:%M'),
            'user_language': preferences.language
        }
    
    def _prepare_escalation_variables(self, escalation_change: StatusChange,
                                    rule: EscalationRule,
                                    preferences: UserNotificationPreferences) -> Dict[str, Any]:
        """Prepare variables for escalation template rendering."""
        delay_days = escalation_change.additional_info.get('delay_days', 0)
        
        return {
            'reference_number': escalation_change.reference_number,
            'escalation_level': rule.escalation_level.value,
            'delay_days': delay_days,
            'escalation_department': rule.escalation_department or '',
            'escalation_officer': rule.escalation_officer or '',
            'current_status': escalation_change.old_status.value if escalation_change.old_status else '',
            'timestamp': escalation_change.timestamp.strftime('%d/%m/%Y %H:%M'),
            'user_language': preferences.language
        }
    
    def _initialize_escalation_rules(self):
        """Initialize default escalation rules."""
        self.escalation_rules = [
            # Level 1 escalations (7 days)
            EscalationRule(
                status=SubmissionStatus.SUBMITTED,
                delay_threshold_days=7,
                escalation_level=EscalationLevel.LEVEL_1,
                notification_message_key="escalation_level_1_submitted",
                escalation_department="District Administration"
            ),
            EscalationRule(
                status=SubmissionStatus.ACKNOWLEDGED,
                delay_threshold_days=7,
                escalation_level=EscalationLevel.LEVEL_1,
                notification_message_key="escalation_level_1_acknowledged",
                escalation_department="District Administration"
            ),
            
            # Level 2 escalations (15 days)
            EscalationRule(
                status=SubmissionStatus.IN_PROGRESS,
                delay_threshold_days=15,
                escalation_level=EscalationLevel.LEVEL_2,
                notification_message_key="escalation_level_2_in_progress",
                escalation_department="State Administration"
            ),
            EscalationRule(
                status=SubmissionStatus.UNDER_REVIEW,
                delay_threshold_days=15,
                escalation_level=EscalationLevel.LEVEL_2,
                notification_message_key="escalation_level_2_under_review",
                escalation_department="State Administration"
            ),
            
            # Level 3 escalations (30 days)
            EscalationRule(
                status=SubmissionStatus.IN_PROGRESS,
                delay_threshold_days=30,
                escalation_level=EscalationLevel.LEVEL_3,
                notification_message_key="escalation_level_3_final",
                escalation_department="Central Administration",
                escalation_officer="Chief Secretary"
            )
        ]
    
    def _initialize_notification_templates(self):
        """Initialize notification templates."""
        # Hindi templates
        self.notification_templates.update({
            # Status update templates - Hindi
            f"{StatusChangeType.STATUS_UPDATE.value}_hi_{NotificationChannel.SMS.value}": NotificationTemplate(
                template_id="status_update_hi_sms",
                change_type=StatusChangeType.STATUS_UPDATE,
                language="hi",
                channel=NotificationChannel.SMS,
                subject_template="शिकायत अपडेट - {reference_number}",
                message_template="आपकी शिकायत {reference_number} की स्थिति अपडेट हुई है: {message}। वर्तमान स्थिति: {new_status}।",
                variables=["reference_number", "message", "new_status"]
            ),
            
            f"{StatusChangeType.STATUS_UPDATE.value}_hi_{NotificationChannel.IN_APP.value}": NotificationTemplate(
                template_id="status_update_hi_in_app",
                change_type=StatusChangeType.STATUS_UPDATE,
                language="hi",
                channel=NotificationChannel.IN_APP,
                subject_template="शिकायत अपडेट - {reference_number}",
                message_template="आपकी शिकायत {reference_number} की स्थिति अपडेट हुई है: {message}। वर्तमान स्थिति: {new_status}।",
                variables=["reference_number", "message", "new_status"]
            ),
            
            f"{StatusChangeType.STATUS_UPDATE.value}_hi_{NotificationChannel.EMAIL.value}": NotificationTemplate(
                template_id="status_update_hi_email",
                change_type=StatusChangeType.STATUS_UPDATE,
                language="hi",
                channel=NotificationChannel.EMAIL,
                subject_template="शिकायत स्थिति अपडेट - {reference_number}",
                message_template="""प्रिय नागरिक,

आपकी शिकायत {reference_number} की स्थिति में अपडेट है:

पुरानी स्थिति: {old_status}
नई स्थिति: {new_status}
संदेश: {message}

{assigned_officer} द्वारा अपडेट किया गया: {timestamp}

धन्यवाद,
भारत वॉयस असिस्टेंट टीम""",
                variables=["reference_number", "old_status", "new_status", "message", "assigned_officer", "timestamp"]
            ),
            
            # Final resolution templates - Hindi
            f"{StatusChangeType.FINAL_RESOLUTION.value}_hi_{NotificationChannel.SMS.value}": NotificationTemplate(
                template_id="final_resolution_hi_sms",
                change_type=StatusChangeType.FINAL_RESOLUTION,
                language="hi",
                channel=NotificationChannel.SMS,
                subject_template="शिकायत समाधान - {reference_number}",
                message_template="बधाई हो! आपकी शिकायत {reference_number} का समाधान हो गया है: {message}",
                priority=NotificationPriority.HIGH,
                variables=["reference_number", "message"]
            ),
            
            # Document requested templates - Hindi
            f"{StatusChangeType.DOCUMENT_REQUESTED.value}_hi_{NotificationChannel.SMS.value}": NotificationTemplate(
                template_id="document_requested_hi_sms",
                change_type=StatusChangeType.DOCUMENT_REQUESTED,
                language="hi",
                channel=NotificationChannel.SMS,
                subject_template="दस्तावेज़ आवश्यक - {reference_number}",
                message_template="आपकी शिकायत {reference_number} के लिए अतिरिक्त दस्तावेज़ चाहिए: {actions_required}",
                priority=NotificationPriority.HIGH,
                variables=["reference_number", "actions_required"]
            ),
            
            # Escalation templates - Hindi
            f"escalation_{EscalationLevel.LEVEL_1.value}_hi_{NotificationChannel.SMS.value}": NotificationTemplate(
                template_id="escalation_level_1_hi_sms",
                change_type=StatusChangeType.ESCALATION,
                language="hi",
                channel=NotificationChannel.SMS,
                subject_template="शिकायत एस्केलेशन - {reference_number}",
                message_template="आपकी शिकायत {reference_number} को {delay_days} दिन की देरी के कारण उच्च अधिकारी को भेजा गया है।",
                priority=NotificationPriority.HIGH,
                variables=["reference_number", "delay_days"]
            ),
        })
        
        # English templates
        self.notification_templates.update({
            # Status update templates - English
            f"{StatusChangeType.STATUS_UPDATE.value}_en_{NotificationChannel.SMS.value}": NotificationTemplate(
                template_id="status_update_en_sms",
                change_type=StatusChangeType.STATUS_UPDATE,
                language="en",
                channel=NotificationChannel.SMS,
                subject_template="Grievance Update - {reference_number}",
                message_template="Your grievance {reference_number} status updated: {message}. Current status: {new_status}.",
                variables=["reference_number", "message", "new_status"]
            ),
            
            f"{StatusChangeType.STATUS_UPDATE.value}_en_{NotificationChannel.IN_APP.value}": NotificationTemplate(
                template_id="status_update_en_in_app",
                change_type=StatusChangeType.STATUS_UPDATE,
                language="en",
                channel=NotificationChannel.IN_APP,
                subject_template="Grievance Update - {reference_number}",
                message_template="Your grievance {reference_number} status updated: {message}. Current status: {new_status}.",
                variables=["reference_number", "message", "new_status"]
            ),
            
            f"{StatusChangeType.STATUS_UPDATE.value}_en_{NotificationChannel.EMAIL.value}": NotificationTemplate(
                template_id="status_update_en_email",
                change_type=StatusChangeType.STATUS_UPDATE,
                language="en",
                channel=NotificationChannel.EMAIL,
                subject_template="Grievance Status Update - {reference_number}",
                message_template="""Dear Citizen,

Your grievance {reference_number} has been updated:

Previous Status: {old_status}
Current Status: {new_status}
Message: {message}

Updated by {assigned_officer} on {timestamp}

Thank you,
Bharat Voice Assistant Team""",
                variables=["reference_number", "old_status", "new_status", "message", "assigned_officer", "timestamp"]
            ),
            
            # Final resolution templates - English
            f"{StatusChangeType.FINAL_RESOLUTION.value}_en_{NotificationChannel.SMS.value}": NotificationTemplate(
                template_id="final_resolution_en_sms",
                change_type=StatusChangeType.FINAL_RESOLUTION,
                language="en",
                channel=NotificationChannel.SMS,
                subject_template="Grievance Resolved - {reference_number}",
                message_template="Congratulations! Your grievance {reference_number} has been resolved: {message}",
                priority=NotificationPriority.HIGH,
                variables=["reference_number", "message"]
            ),
            
            # Escalation templates - English
            f"escalation_{EscalationLevel.LEVEL_1.value}_en_{NotificationChannel.SMS.value}": NotificationTemplate(
                template_id="escalation_level_1_en_sms",
                change_type=StatusChangeType.ESCALATION,
                language="en",
                channel=NotificationChannel.SMS,
                subject_template="Grievance Escalated - {reference_number}",
                message_template="Your grievance {reference_number} has been escalated to higher authority due to {delay_days} days delay.",
                priority=NotificationPriority.HIGH,
                variables=["reference_number", "delay_days"]
            ),
        })
        
        logger.info(f"Initialized {len(self.notification_templates)} notification templates")