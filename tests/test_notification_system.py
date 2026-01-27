"""
Unit tests for the user notification system.

Tests proactive notifications, escalation triggers, and user preference management.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, date
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from bharat_voice_assistant.grievance.notification_system import (
    UserNotificationSystem, UserNotificationPreferences, NotificationRecord,
    EscalationRule, EscalationLevel, NotificationPriority, NotificationStatus,
    SMSNotificationHandler, EmailNotificationHandler, VoiceNotificationHandler,
    InAppNotificationHandler
)
from bharat_voice_assistant.grievance.status_monitor import (
    StatusChange, StatusChangeType, NotificationChannel, StatusTimeline
)
from bharat_voice_assistant.integration.models import SubmissionStatus
from bharat_voice_assistant.grievance.models import GrievanceRecord


class TestUserNotificationPreferences:
    """Test user notification preferences."""
    
    def test_create_preferences(self):
        """Test creating user notification preferences."""
        preferences = UserNotificationPreferences(
            user_id="user123",
            language="hi",
            phone_number="+919876543210",
            email="user@example.com"
        )
        
        assert preferences.user_id == "user123"
        assert preferences.language == "hi"
        assert preferences.phone_number == "+919876543210"
        assert preferences.email == "user@example.com"
        assert preferences.global_enabled is True
        assert len(preferences.enabled_change_types) == len(StatusChangeType)
    
    def test_notification_allowed(self):
        """Test notification permission checking."""
        preferences = UserNotificationPreferences(
            user_id="user123",
            enabled_change_types={StatusChangeType.STATUS_UPDATE, StatusChangeType.FINAL_RESOLUTION},
            min_priority=NotificationPriority.NORMAL
        )
        
        # Allowed notification
        assert preferences.is_notification_allowed(
            StatusChangeType.STATUS_UPDATE, NotificationPriority.NORMAL
        ) is True
        
        # Not allowed - change type not enabled
        assert preferences.is_notification_allowed(
            StatusChangeType.ESCALATION, NotificationPriority.NORMAL
        ) is False
        
        # Not allowed - priority too low
        assert preferences.is_notification_allowed(
            StatusChangeType.STATUS_UPDATE, NotificationPriority.LOW
        ) is False
        
        # Allowed - urgent priority overrides quiet hours
        preferences.quiet_hours_start = 22
        preferences.quiet_hours_end = 6
        current_time = datetime.now().replace(hour=23, minute=0)
        
        assert preferences.is_notification_allowed(
            StatusChangeType.STATUS_UPDATE, NotificationPriority.URGENT, current_time
        ) is True
    
    def test_quiet_hours(self):
        """Test quiet hours functionality."""
        preferences = UserNotificationPreferences(
            user_id="user123",
            quiet_hours_start=22,
            quiet_hours_end=6
        )
        
        # During quiet hours
        night_time = datetime.now().replace(hour=23, minute=0)
        assert preferences._is_quiet_hours(night_time) is True
        
        early_morning = datetime.now().replace(hour=5, minute=0)
        assert preferences._is_quiet_hours(early_morning) is True
        
        # Outside quiet hours
        day_time = datetime.now().replace(hour=10, minute=0)
        assert preferences._is_quiet_hours(day_time) is False


class TestNotificationHandlers:
    """Test notification channel handlers."""
    
    @pytest.mark.asyncio
    async def test_sms_handler(self):
        """Test SMS notification handler."""
        handler = SMSNotificationHandler()
        
        preferences = UserNotificationPreferences(
            user_id="user123",
            phone_number="+919876543210"
        )
        
        notification = NotificationRecord(
            notification_id="test123",
            reference_number="REF123",
            user_id="user123",
            channel=NotificationChannel.SMS,
            change_type=StatusChangeType.STATUS_UPDATE,
            priority=NotificationPriority.NORMAL,
            subject="Test Subject",
            message="Test message"
        )
        
        # Test successful sending
        result = await handler.send_notification(notification, preferences)
        assert result is True
        
        # Test failure when no phone number
        preferences.phone_number = None
        result = await handler.send_notification(notification, preferences)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_email_handler(self):
        """Test email notification handler."""
        handler = EmailNotificationHandler()
        
        preferences = UserNotificationPreferences(
            user_id="user123",
            email="user@example.com"
        )
        
        notification = NotificationRecord(
            notification_id="test123",
            reference_number="REF123",
            user_id="user123",
            channel=NotificationChannel.EMAIL,
            change_type=StatusChangeType.STATUS_UPDATE,
            priority=NotificationPriority.NORMAL,
            subject="Test Subject",
            message="Test message"
        )
        
        # Test successful sending
        result = await handler.send_notification(notification, preferences)
        assert result is True
        
        # Test failure when no email
        preferences.email = None
        result = await handler.send_notification(notification, preferences)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_in_app_handler(self):
        """Test in-app notification handler."""
        handler = InAppNotificationHandler()
        
        preferences = UserNotificationPreferences(user_id="user123")
        
        notification = NotificationRecord(
            notification_id="test123",
            reference_number="REF123",
            user_id="user123",
            channel=NotificationChannel.IN_APP,
            change_type=StatusChangeType.STATUS_UPDATE,
            priority=NotificationPriority.NORMAL,
            subject="Test Subject",
            message="Test message"
        )
        
        # Test storing notification
        result = await handler.send_notification(notification, preferences)
        assert result is True
        
        # Test retrieving notifications
        notifications = handler.get_user_notifications("user123")
        assert len(notifications) == 1
        assert notifications[0].notification_id == "test123"


class TestEscalationRules:
    """Test escalation rules."""
    
    def test_escalation_rule_applicability(self):
        """Test escalation rule applicability."""
        rule = EscalationRule(
            status=SubmissionStatus.IN_PROGRESS,
            delay_threshold_days=15,
            escalation_level=EscalationLevel.LEVEL_1,
            notification_message_key="escalation_test"
        )
        
        # Rule applies
        assert rule.is_applicable(SubmissionStatus.IN_PROGRESS, 16) is True
        assert rule.is_applicable(SubmissionStatus.IN_PROGRESS, 15) is True
        
        # Rule doesn't apply
        assert rule.is_applicable(SubmissionStatus.IN_PROGRESS, 14) is False
        assert rule.is_applicable(SubmissionStatus.SUBMITTED, 16) is False


class TestUserNotificationSystem:
    """Test the main notification system."""
    
    @pytest.fixture
    def notification_system(self):
        """Create notification system for testing."""
        mock_status_monitor = Mock()
        mock_status_monitor.__aenter__ = AsyncMock(return_value=mock_status_monitor)
        mock_status_monitor.__aexit__ = AsyncMock()
        mock_status_monitor.set_notification_preferences = AsyncMock()
        mock_status_monitor.get_monitoring_stats = Mock(return_value={'monitored_references': []})
        
        return UserNotificationSystem(status_monitor=mock_status_monitor)
    
    @pytest.mark.asyncio
    async def test_setup_user_notifications(self, notification_system):
        """Test setting up user notifications."""
        async with notification_system:
            result = await notification_system.setup_user_notifications(
                user_id="user123",
                reference_number="REF123",
                phone_number="+919876543210",
                email="user@example.com",
                language="hi",
                channels=[NotificationChannel.SMS, NotificationChannel.EMAIL]
            )
            
            assert result is True
            
            # Check preferences were created
            preferences = notification_system.get_user_preferences("user123")
            assert preferences is not None
            assert preferences.user_id == "user123"
            assert "REF123" in preferences.reference_numbers
            assert preferences.phone_number == "+919876543210"
            assert preferences.email == "user@example.com"
            assert NotificationChannel.SMS in preferences.channels
            assert NotificationChannel.EMAIL in preferences.channels
    
    @pytest.mark.asyncio
    async def test_update_user_preferences(self, notification_system):
        """Test updating user preferences."""
        async with notification_system:
            # Setup initial preferences
            await notification_system.setup_user_notifications(
                user_id="user123",
                reference_number="REF123"
            )
            
            # Update preferences
            result = await notification_system.update_user_preferences(
                user_id="user123",
                preferences_update={
                    'global_enabled': False,
                    'language': 'en',
                    'max_notifications_per_day': 5,
                    'channels': ['sms', 'email'],
                    'min_priority': 'high'
                }
            )
            
            assert result is True
            
            # Check preferences were updated
            preferences = notification_system.get_user_preferences("user123")
            assert preferences.global_enabled is False
            assert preferences.language == 'en'
            assert preferences.max_notifications_per_day == 5
            assert NotificationChannel.SMS in preferences.channels
            assert NotificationChannel.EMAIL in preferences.channels
            assert preferences.min_priority == NotificationPriority.HIGH
    
    @pytest.mark.asyncio
    async def test_send_status_change_notification(self, notification_system):
        """Test sending status change notifications."""
        async with notification_system:
            # Setup user preferences
            await notification_system.setup_user_notifications(
                user_id="user123",
                reference_number="REF123",
                channels=[NotificationChannel.IN_APP]
            )
            
            # Create status change
            status_change = StatusChange(
                reference_number="REF123",
                change_type=StatusChangeType.STATUS_UPDATE,
                old_status=SubmissionStatus.SUBMITTED,
                new_status=SubmissionStatus.IN_PROGRESS,
                message="Your grievance is now being processed"
            )
            
            # Send notification
            result = await notification_system.send_status_change_notification(status_change)
            assert result is True
            
            # Check notification was stored
            notifications = notification_system.get_user_notifications("user123")
            assert len(notifications) == 1
            assert notifications[0].reference_number == "REF123"
            assert notifications[0].change_type == StatusChangeType.STATUS_UPDATE
    
    @pytest.mark.asyncio
    async def test_escalation_check(self, notification_system):
        """Test escalation checking for delayed cases."""
        async with notification_system:
            # Mock status monitor to return a delayed case
            mock_timeline = StatusTimeline(reference_number="REF123")
            old_change = StatusChange(
                reference_number="REF123",
                change_type=StatusChangeType.STATUS_UPDATE,
                new_status=SubmissionStatus.IN_PROGRESS,
                message="In progress",
                timestamp=datetime.now() - timedelta(days=20)  # 20 days old
            )
            mock_timeline.add_status_change(old_change)
            
            notification_system.status_monitor.get_monitoring_stats = Mock(
                return_value={'monitored_references': ['REF123']}
            )
            notification_system.status_monitor.get_status_timeline = AsyncMock(
                return_value=mock_timeline
            )
            
            # Setup user for escalation notifications
            await notification_system.setup_user_notifications(
                user_id="user123",
                reference_number="REF123",
                channels=[NotificationChannel.IN_APP]
            )
            
            # Check escalations
            escalated_count = await notification_system.check_and_escalate_delayed_cases()
            
            # Should have escalated one case (20 days > 15 day threshold)
            assert escalated_count == 1
    
    def test_notification_priority_determination(self, notification_system):
        """Test notification priority determination."""
        # High priority changes
        high_priority_change = StatusChange(
            reference_number="REF123",
            change_type=StatusChangeType.FINAL_RESOLUTION,
            message="Resolved"
        )
        priority = notification_system._determine_notification_priority(high_priority_change)
        assert priority == NotificationPriority.HIGH
        
        # Normal priority changes
        normal_priority_change = StatusChange(
            reference_number="REF123",
            change_type=StatusChangeType.STATUS_UPDATE,
            message="Updated"
        )
        priority = notification_system._determine_notification_priority(normal_priority_change)
        assert priority == NotificationPriority.NORMAL
    
    def test_template_variable_preparation(self, notification_system):
        """Test template variable preparation."""
        status_change = StatusChange(
            reference_number="REF123",
            change_type=StatusChangeType.STATUS_UPDATE,
            old_status=SubmissionStatus.SUBMITTED,
            new_status=SubmissionStatus.IN_PROGRESS,
            message="Processing started",
            assigned_officer="Officer Smith",
            department="Revenue Department",
            estimated_resolution_date=date(2024, 12, 31),
            actions_required=["Submit documents", "Verify details"]
        )
        
        preferences = UserNotificationPreferences(
            user_id="user123",
            language="hi"
        )
        
        variables = notification_system._prepare_template_variables(status_change, preferences)
        
        assert variables['reference_number'] == "REF123"
        assert variables['old_status'] == "submitted"
        assert variables['new_status'] == "in_progress"
        assert variables['message'] == "Processing started"
        assert variables['assigned_officer'] == "Officer Smith"
        assert variables['department'] == "Revenue Department"
        assert variables['estimated_date'] == "31/12/2024"
        assert variables['actions_required'] == "Submit documents, Verify details"
        assert variables['user_language'] == "hi"
    
    def test_notification_stats(self, notification_system):
        """Test notification system statistics."""
        # Add some test data
        notification_system.user_preferences["user1"] = UserNotificationPreferences(user_id="user1")
        notification_system.user_preferences["user2"] = UserNotificationPreferences(user_id="user2")
        
        notification_system.notification_records["notif1"] = NotificationRecord(
            notification_id="notif1",
            reference_number="REF123",
            user_id="user1",
            channel=NotificationChannel.SMS,
            change_type=StatusChangeType.STATUS_UPDATE,
            priority=NotificationPriority.NORMAL,
            subject="Test",
            message="Test",
            status=NotificationStatus.SENT
        )
        
        stats = notification_system.get_notification_stats()
        
        assert stats['total_users'] == 2
        assert stats['total_notifications'] == 1
        assert stats['status_distribution']['sent'] == 1
        assert stats['channel_distribution']['sms'] == 1
        assert stats['escalation_rules'] > 0
        assert stats['notification_templates'] > 0


class TestNotificationTemplates:
    """Test notification templates."""
    
    def test_template_rendering(self):
        """Test template rendering with variables."""
        from bharat_voice_assistant.grievance.notification_system import NotificationTemplate
        
        template = NotificationTemplate(
            template_id="test_template",
            change_type=StatusChangeType.STATUS_UPDATE,
            language="hi",
            channel=NotificationChannel.SMS,
            subject_template="शिकायत अपडेट - {reference_number}",
            message_template="आपकी शिकायत {reference_number} की स्थिति: {new_status}",
            variables=["reference_number", "new_status"]
        )
        
        variables = {
            'reference_number': 'REF123',
            'new_status': 'in_progress'
        }
        
        subject, message = template.render(variables)
        
        assert subject == "शिकायत अपडेट - REF123"
        assert message == "आपकी शिकायत REF123 की स्थिति: in_progress"
    
    def test_template_missing_variables(self):
        """Test template rendering with missing variables."""
        from bharat_voice_assistant.grievance.notification_system import NotificationTemplate
        
        template = NotificationTemplate(
            template_id="test_template",
            change_type=StatusChangeType.STATUS_UPDATE,
            language="hi",
            channel=NotificationChannel.SMS,
            subject_template="शिकायत अपडेट - {reference_number}",
            message_template="आपकी शिकायत {reference_number} की स्थिति: {new_status}",
            variables=["reference_number", "new_status"]
        )
        
        # Missing new_status variable
        variables = {
            'reference_number': 'REF123'
        }
        
        subject, message = template.render(variables)
        
        # Should return original templates when variables are missing
        assert subject == "शिकायत अपडेट - {reference_number}"
        assert message == "आपकी शिकायत {reference_number} की स्थिति: {new_status}"


@pytest.mark.asyncio
async def test_notification_system_integration():
    """Test notification system integration with status monitor."""
    # This test would require more complex setup with actual status monitor
    # For now, we'll test the basic integration points
    
    mock_status_monitor = Mock()
    mock_status_monitor.__aenter__ = AsyncMock(return_value=mock_status_monitor)
    mock_status_monitor.__aexit__ = AsyncMock()
    mock_status_monitor.set_notification_preferences = AsyncMock()
    
    async with UserNotificationSystem(status_monitor=mock_status_monitor) as system:
        # Test that system initializes properly
        assert system.status_monitor is mock_status_monitor
        assert len(system.escalation_rules) > 0
        assert len(system.notification_templates) > 0
        assert len(system.channel_handlers) == 4  # SMS, Email, Voice, In-App
        
        # Test that background tasks are created
        assert system.escalation_task is not None
        assert system.retry_task is not None


if __name__ == "__main__":
    pytest.main([__file__])