"""
Demo script for the user notification system.

This script demonstrates the comprehensive notification system including
proactive notifications, escalation triggers, and user preference management.
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from uuid import uuid4

from bharat_voice_assistant.grievance.notification_system import (
    UserNotificationSystem, UserNotificationPreferences, NotificationChannel,
    NotificationPriority, EscalationLevel
)
from bharat_voice_assistant.grievance.status_monitor import (
    StatusChange, StatusChangeType, StatusTimeline, GrievanceStatusMonitor
)
from bharat_voice_assistant.integration.models import SubmissionStatus
from bharat_voice_assistant.grievance.models import GrievanceRecord, GrievanceDetails, GrievanceType
from bharat_voice_assistant.core.logging import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


async def demo_basic_notification_setup():
    """Demonstrate basic notification setup."""
    print("\n" + "="*60)
    print("DEMO: Basic Notification Setup")
    print("="*60)
    
    async with UserNotificationSystem() as notification_system:
        # Setup notifications for a user
        user_id = "demo_user_123"
        reference_number = "REF2024001"
        
        success = await notification_system.setup_user_notifications(
            user_id=user_id,
            reference_number=reference_number,
            phone_number="+919876543210",
            email="demo.user@example.com",
            language="hi",
            channels=[NotificationChannel.SMS, NotificationChannel.EMAIL, NotificationChannel.IN_APP],
            change_types=[
                StatusChangeType.STATUS_UPDATE,
                StatusChangeType.FINAL_RESOLUTION,
                StatusChangeType.DOCUMENT_REQUESTED,
                StatusChangeType.ESCALATION
            ]
        )
        
        print(f"✅ Notification setup successful: {success}")
        
        # Get and display user preferences
        preferences = notification_system.get_user_preferences(user_id)
        if preferences:
            print(f"📱 User ID: {preferences.user_id}")
            print(f"📞 Phone: {preferences.phone_number}")
            print(f"📧 Email: {preferences.email}")
            print(f"🌐 Language: {preferences.language}")
            print(f"📢 Channels: {[ch.value for ch in preferences.channels]}")
            print(f"🔔 Enabled notifications: {len(preferences.enabled_change_types)}")
            print(f"📋 Monitoring references: {list(preferences.reference_numbers)}")


async def demo_status_change_notifications():
    """Demonstrate status change notifications."""
    print("\n" + "="*60)
    print("DEMO: Status Change Notifications")
    print("="*60)
    
    async with UserNotificationSystem() as notification_system:
        user_id = "demo_user_456"
        reference_number = "REF2024002"
        
        # Setup user
        await notification_system.setup_user_notifications(
            user_id=user_id,
            reference_number=reference_number,
            phone_number="+919876543211",
            email="user456@example.com",
            language="en",
            channels=[NotificationChannel.SMS, NotificationChannel.IN_APP]
        )
        
        # Simulate various status changes
        status_changes = [
            StatusChange(
                reference_number=reference_number,
                change_type=StatusChangeType.STATUS_UPDATE,
                old_status=SubmissionStatus.SUBMITTED,
                new_status=SubmissionStatus.ACKNOWLEDGED,
                message="Your grievance has been acknowledged by the department",
                department="Revenue Department",
                assigned_officer="Officer Sharma"
            ),
            StatusChange(
                reference_number=reference_number,
                change_type=StatusChangeType.STATUS_UPDATE,
                old_status=SubmissionStatus.ACKNOWLEDGED,
                new_status=SubmissionStatus.IN_PROGRESS,
                message="Investigation has started on your grievance",
                department="Revenue Department",
                assigned_officer="Officer Sharma"
            ),
            StatusChange(
                reference_number=reference_number,
                change_type=StatusChangeType.DOCUMENT_REQUESTED,
                old_status=SubmissionStatus.IN_PROGRESS,
                new_status=SubmissionStatus.IN_PROGRESS,
                message="Additional documents required for processing",
                actions_required=["Submit income certificate", "Provide address proof"],
                department="Revenue Department"
            ),
            StatusChange(
                reference_number=reference_number,
                change_type=StatusChangeType.FINAL_RESOLUTION,
                old_status=SubmissionStatus.IN_PROGRESS,
                new_status=SubmissionStatus.RESOLVED,
                message="Your grievance has been successfully resolved. Certificate issued.",
                department="Revenue Department",
                assigned_officer="Officer Sharma"
            )
        ]
        
        # Send notifications for each status change
        for i, change in enumerate(status_changes, 1):
            print(f"\n📢 Sending notification {i}/4...")
            print(f"   Change Type: {change.change_type.value}")
            print(f"   Status: {change.old_status.value if change.old_status else 'N/A'} → {change.new_status.value if change.new_status else 'N/A'}")
            print(f"   Message: {change.message}")
            
            success = await notification_system.send_status_change_notification(change)
            print(f"   ✅ Notification sent: {success}")
            
            # Small delay between notifications
            await asyncio.sleep(0.5)
        
        # Show in-app notifications
        print(f"\n📱 In-app notifications for user {user_id}:")
        notifications = notification_system.get_user_notifications(user_id)
        for i, notif in enumerate(notifications, 1):
            print(f"   {i}. [{notif.change_type.value}] {notif.subject}")
            print(f"      {notif.message[:100]}...")
            print(f"      Status: {notif.status.value}, Priority: {notif.priority.value}")


async def demo_user_preference_management():
    """Demonstrate user preference management."""
    print("\n" + "="*60)
    print("DEMO: User Preference Management")
    print("="*60)
    
    async with UserNotificationSystem() as notification_system:
        user_id = "demo_user_789"
        reference_number = "REF2024003"
        
        # Initial setup
        await notification_system.setup_user_notifications(
            user_id=user_id,
            reference_number=reference_number,
            phone_number="+919876543212",
            language="hi"
        )
        
        print("📋 Initial preferences:")
        preferences = notification_system.get_user_preferences(user_id)
        print(f"   Global enabled: {preferences.global_enabled}")
        print(f"   Language: {preferences.language}")
        print(f"   Channels: {[ch.value for ch in preferences.channels]}")
        print(f"   Min priority: {preferences.min_priority.value}")
        print(f"   Max notifications/day: {preferences.max_notifications_per_day}")
        
        # Update preferences
        print("\n🔧 Updating preferences...")
        updates = {
            'language': 'en',
            'channels': ['sms', 'email', 'in_app'],
            'min_priority': 'high',
            'max_notifications_per_day': 5,
            'quiet_hours_start': 22,
            'quiet_hours_end': 6,
            'escalation_notifications': True,
            'escalation_channels': ['sms', 'voice']
        }
        
        success = await notification_system.update_user_preferences(user_id, updates)
        print(f"✅ Preferences updated: {success}")
        
        # Show updated preferences
        print("\n📋 Updated preferences:")
        preferences = notification_system.get_user_preferences(user_id)
        print(f"   Language: {preferences.language}")
        print(f"   Channels: {[ch.value for ch in preferences.channels]}")
        print(f"   Min priority: {preferences.min_priority.value}")
        print(f"   Max notifications/day: {preferences.max_notifications_per_day}")
        print(f"   Quiet hours: {preferences.quiet_hours_start}:00 - {preferences.quiet_hours_end}:00")
        print(f"   Escalation notifications: {preferences.escalation_notifications}")
        print(f"   Escalation channels: {[ch.value for ch in preferences.escalation_channels]}")
        
        # Test notification filtering
        print("\n🔍 Testing notification filtering...")
        
        # Low priority notification (should be blocked)
        low_priority_change = StatusChange(
            reference_number=reference_number,
            change_type=StatusChangeType.PROGRESS_UPDATE,
            message="Minor progress update"
        )
        
        print("   Testing low priority notification (should be blocked)...")
        success = await notification_system.send_status_change_notification(low_priority_change)
        print(f"   Result: {success}")
        
        # High priority notification (should go through)
        high_priority_change = StatusChange(
            reference_number=reference_number,
            change_type=StatusChangeType.FINAL_RESOLUTION,
            message="Your grievance has been resolved"
        )
        
        print("   Testing high priority notification (should go through)...")
        success = await notification_system.send_status_change_notification(high_priority_change)
        print(f"   Result: {success}")


async def demo_escalation_system():
    """Demonstrate escalation system for delayed cases."""
    print("\n" + "="*60)
    print("DEMO: Escalation System")
    print("="*60)
    
    # Create a mock status monitor with delayed cases
    class MockStatusMonitor:
        def __init__(self):
            self.timelines = {}
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        
        async def set_notification_preferences(self, preferences):
            pass
        
        def get_monitoring_stats(self):
            return {'monitored_references': list(self.timelines.keys())}
        
        async def get_status_timeline(self, reference_number):
            return self.timelines.get(reference_number)
        
        def add_delayed_case(self, reference_number, status, days_old):
            timeline = StatusTimeline(reference_number=reference_number)
            old_change = StatusChange(
                reference_number=reference_number,
                change_type=StatusChangeType.STATUS_UPDATE,
                new_status=status,
                message=f"Status: {status.value}",
                timestamp=datetime.now() - timedelta(days=days_old)
            )
            timeline.add_status_change(old_change)
            self.timelines[reference_number] = timeline
    
    mock_monitor = MockStatusMonitor()
    
    # Add some delayed cases
    mock_monitor.add_delayed_case("REF2024004", SubmissionStatus.SUBMITTED, 8)  # Should escalate (>7 days)
    mock_monitor.add_delayed_case("REF2024005", SubmissionStatus.IN_PROGRESS, 20)  # Should escalate (>15 days)
    mock_monitor.add_delayed_case("REF2024006", SubmissionStatus.ACKNOWLEDGED, 5)  # Should not escalate (<7 days)
    
    async with UserNotificationSystem(status_monitor=mock_monitor) as notification_system:
        # Setup users for escalation notifications
        for i, ref_num in enumerate(["REF2024004", "REF2024005", "REF2024006"], 1):
            await notification_system.setup_user_notifications(
                user_id=f"user_{i}",
                reference_number=ref_num,
                phone_number=f"+91987654321{i}",
                channels=[NotificationChannel.SMS, NotificationChannel.IN_APP]
            )
        
        print("📊 Checking for delayed cases...")
        print("   REF2024004: SUBMITTED for 8 days (threshold: 7 days)")
        print("   REF2024005: IN_PROGRESS for 20 days (threshold: 15 days)")
        print("   REF2024006: ACKNOWLEDGED for 5 days (threshold: 7 days)")
        
        # Check and escalate delayed cases
        escalated_count = await notification_system.check_and_escalate_delayed_cases()
        
        print(f"\n🚨 Escalated {escalated_count} cases")
        
        # Show escalation notifications
        for i in range(1, 4):
            user_id = f"user_{i}"
            notifications = notification_system.get_user_notifications(user_id)
            escalation_notifications = [n for n in notifications if n.change_type == StatusChangeType.ESCALATION]
            
            if escalation_notifications:
                print(f"\n📢 Escalation notifications for {user_id}:")
                for notif in escalation_notifications:
                    print(f"   Subject: {notif.subject}")
                    print(f"   Message: {notif.message}")
                    print(f"   Priority: {notif.priority.value}")
            else:
                print(f"\n📢 No escalation notifications for {user_id}")


async def demo_notification_statistics():
    """Demonstrate notification system statistics."""
    print("\n" + "="*60)
    print("DEMO: Notification Statistics")
    print("="*60)
    
    async with UserNotificationSystem() as notification_system:
        # Setup multiple users and send various notifications
        users_data = [
            ("user_stats_1", "REF2024007", "+919876543213", "user1@example.com", "hi"),
            ("user_stats_2", "REF2024008", "+919876543214", "user2@example.com", "en"),
            ("user_stats_3", "REF2024009", "+919876543215", "user3@example.com", "hi"),
        ]
        
        # Setup users
        for user_id, ref_num, phone, email, lang in users_data:
            await notification_system.setup_user_notifications(
                user_id=user_id,
                reference_number=ref_num,
                phone_number=phone,
                email=email,
                language=lang,
                channels=[NotificationChannel.SMS, NotificationChannel.EMAIL, NotificationChannel.IN_APP]
            )
        
        # Send various notifications
        notification_types = [
            StatusChangeType.STATUS_UPDATE,
            StatusChangeType.FINAL_RESOLUTION,
            StatusChangeType.DOCUMENT_REQUESTED,
            StatusChangeType.ESCALATION
        ]
        
        for i, (user_id, ref_num, _, _, _) in enumerate(users_data):
            for j, change_type in enumerate(notification_types):
                change = StatusChange(
                    reference_number=ref_num,
                    change_type=change_type,
                    message=f"Test notification {j+1} for {user_id}"
                )
                await notification_system.send_status_change_notification(change)
        
        # Get and display statistics
        stats = notification_system.get_notification_stats()
        
        print("📊 Notification System Statistics:")
        print(f"   Total users: {stats['total_users']}")
        print(f"   Total notifications: {stats['total_notifications']}")
        print(f"   Escalation rules: {stats['escalation_rules']}")
        print(f"   Notification templates: {stats['notification_templates']}")
        
        print("\n📈 Status Distribution:")
        for status, count in stats['status_distribution'].items():
            print(f"   {status}: {count}")
        
        print("\n📱 Channel Distribution:")
        for channel, count in stats['channel_distribution'].items():
            print(f"   {channel}: {count}")
        
        # Show sample notifications for each user
        print("\n📋 Sample Notifications by User:")
        for user_id, ref_num, _, _, _ in users_data:
            notifications = notification_system.get_user_notifications(user_id, limit=2)
            print(f"\n   {user_id} ({ref_num}):")
            for notif in notifications:
                print(f"     • [{notif.change_type.value}] {notif.subject}")
                print(f"       Status: {notif.status.value}, Priority: {notif.priority.value}")


async def main():
    """Run all notification system demos."""
    print("🚀 Starting Bharat Voice Assistant Notification System Demo")
    print("This demo showcases the comprehensive notification system features:")
    print("• Proactive status change notifications")
    print("• Escalation triggers for delayed cases")
    print("• User preference management")
    print("• Multi-channel notification delivery")
    
    try:
        await demo_basic_notification_setup()
        await demo_status_change_notifications()
        await demo_user_preference_management()
        await demo_escalation_system()
        await demo_notification_statistics()
        
        print("\n" + "="*60)
        print("✅ All demos completed successfully!")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())