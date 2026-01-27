#!/usr/bin/env python3
"""
Demo script for grievance status monitoring system.

This script demonstrates the complete status monitoring functionality
including real-time polling, notifications, and timeline visualization.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from bharat_voice_assistant.grievance import (
    GrievanceRecord, GrievanceStatus, GrievanceType, GrievancePriority,
    GrievanceDetails, ContactInformation,
    GrievanceStatusMonitor, GrievanceStatusTracker,
    GrievanceTimelineVisualizer, TimelineVisualizationType,
    NotificationPreference, NotificationChannel, StatusChangeType
)
from bharat_voice_assistant.integration.models import SubmissionStatus


class MockGovernmentAPIClient:
    """Mock API client for demonstration purposes."""
    
    def __init__(self):
        self.mock_statuses = {}
        self.call_count = 0
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def check_status(self, portal, endpoint_name, reference_number):
        """Mock status check that simulates government API responses."""
        self.call_count += 1
        
        # Simulate status progression over time
        if reference_number not in self.mock_statuses:
            self.mock_statuses[reference_number] = {
                'status': 'submitted',
                'message': 'Your grievance has been submitted successfully',
                'last_updated': datetime.now().isoformat(),
                'assigned_officer': None,
                'department': 'Revenue Department'
            }
        
        # Simulate status changes based on call count
        current_status = self.mock_statuses[reference_number]
        
        if self.call_count == 2:
            current_status.update({
                'status': 'acknowledged',
                'message': 'Your grievance has been acknowledged by the department',
                'assigned_officer': 'Mr. Rajesh Kumar',
                'last_updated': datetime.now().isoformat()
            })
        elif self.call_count == 4:
            current_status.update({
                'status': 'in_progress',
                'message': 'Investigation has started on your grievance',
                'last_updated': datetime.now().isoformat(),
                'estimated_resolution_date': (datetime.now() + timedelta(days=15)).date().isoformat()
            })
        elif self.call_count == 6:
            current_status.update({
                'status': 'under_review',
                'message': 'Your grievance is under detailed review',
                'last_updated': datetime.now().isoformat(),
                'next_steps': ['Document verification in progress', 'Field inspection scheduled']
            })
        elif self.call_count >= 8:
            current_status.update({
                'status': 'resolved',
                'message': 'Your grievance has been resolved successfully',
                'last_updated': datetime.now().isoformat(),
                'next_steps': ['Resolution letter will be sent to your address', 'Case closed']
            })
        
        # Mock API response
        class MockResponse:
            def __init__(self, data):
                self.data = data
                self.status_code = 200
            
            def is_success(self):
                return True
        
        return MockResponse(current_status)


async def demo_status_monitoring():
    """Demonstrate status monitoring functionality."""
    print("🚀 Starting Grievance Status Monitoring Demo")
    print("=" * 50)
    
    # Create a sample grievance record
    grievance = GrievanceRecord(
        reference_number="DEMO2024001",
        user_id="user123",
        details=GrievanceDetails(
            problem_description="Delay in pension payment for the last 3 months",
            grievance_type=GrievanceType.PENSION_ISSUE,
            department="Revenue Department",
            location="Delhi"
        ),
        contact_info=ContactInformation(
            phone_number="+91-9876543210",
            email="user@example.com",
            preferred_language="hi"
        ),
        status=GrievanceStatus.SUBMITTED,
        priority=GrievancePriority.HIGH,
        language="hi"
    )
    
    print(f"📋 Created sample grievance: {grievance.reference_number}")
    print(f"   Problem: {grievance.details.problem_description}")
    print(f"   Type: {grievance.details.grievance_type.value}")
    print()
    
    # Initialize status monitoring components with mock client
    mock_client = MockGovernmentAPIClient()
    
    async with GrievanceStatusMonitor(api_client=mock_client) as status_monitor:
        async with GrievanceStatusTracker(status_monitor) as status_tracker:
            
            # Set up notifications
            notification_prefs = NotificationPreference(
                user_id=grievance.user_id,
                reference_number=grievance.reference_number,
                channels=[NotificationChannel.SMS, NotificationChannel.EMAIL, NotificationChannel.IN_APP],
                language=grievance.language,
                phone_number=grievance.contact_info.phone_number,
                email=grievance.contact_info.email,
                notification_types=list(StatusChangeType)
            )
            
            print("🔔 Setting up notifications...")
            await status_tracker.setup_notifications(
                grievance.reference_number,
                grievance.user_id,
                grievance.contact_info.phone_number,
                grievance.contact_info.email,
                grievance.language,
                notification_prefs.channels
            )
            print("   ✅ Notifications configured")
            print()
            
            # Start monitoring
            print("👀 Starting status monitoring...")
            success = await status_tracker.start_monitoring_grievance(
                grievance,
                grievance.user_id,
                grievance.contact_info.phone_number,
                grievance.contact_info.email
            )
            
            if success:
                print("   ✅ Monitoring started successfully")
            else:
                print("   ❌ Failed to start monitoring")
                return
            print()
            
            # Simulate status checks over time
            print("⏰ Simulating status checks over time...")
            print("   (In real system, this would happen automatically)")
            print()
            
            for check_num in range(1, 6):
                print(f"📊 Status Check #{check_num}")
                print("-" * 30)
                
                # Check current status
                status_response = await status_tracker.check_grievance_status(
                    grievance.reference_number,
                    language=grievance.language
                )
                
                if status_response.success:
                    print(f"   Status: {status_response.current_status}")
                    print(f"   Message: {status_response.message}")
                    if status_response.progress_percentage:
                        print(f"   Progress: {status_response.progress_percentage:.0f}%")
                    if status_response.assigned_officer:
                        print(f"   Officer: {status_response.assigned_officer}")
                    if status_response.estimated_completion_date:
                        print(f"   Est. Completion: {status_response.estimated_completion_date}")
                else:
                    print(f"   ❌ Error: {status_response.message}")
                
                print()
                
                # Show timeline visualization
                timeline = await status_monitor.get_status_timeline(grievance.reference_number)
                if timeline:
                    visualizer = GrievanceTimelineVisualizer()
                    
                    # Create different types of visualizations
                    if check_num == 1:
                        viz = visualizer.create_timeline_visualization(
                            timeline, TimelineVisualizationType.PROGRESS_BAR, grievance.language
                        )
                        print("📈 Progress Bar View:")
                        print(viz.content)
                    elif check_num == 3:
                        viz = visualizer.create_timeline_visualization(
                            timeline, TimelineVisualizationType.MILESTONE_VIEW, grievance.language
                        )
                        print("🎯 Milestone View:")
                        print(viz.content)
                    elif check_num == 5:
                        viz = visualizer.create_timeline_visualization(
                            timeline, TimelineVisualizationType.DETAILED_TIMELINE, grievance.language
                        )
                        print("📋 Detailed Timeline:")
                        print(viz.content)
                    
                    # Show progress summary
                    summary = visualizer.get_progress_summary(timeline, grievance.language)
                    print("📊 Progress Summary:")
                    print(f"   {summary['progress_text']}")
                    print(f"   {summary['milestone_text']}")
                    print(f"   Current Stage: {summary['current_stage']}")
                    print(f"   Est. Completion: {summary['estimated_completion']}")
                    print()
                
                # Wait before next check (simulating polling interval)
                if check_num < 5:
                    print("⏳ Waiting for next status check...")
                    await asyncio.sleep(2)  # Short delay for demo
                    print()
            
            # Show final monitoring statistics
            print("📈 Monitoring Statistics:")
            stats = status_monitor.get_monitoring_stats()
            print(f"   Active Tasks: {stats['active_monitoring_tasks']}")
            print(f"   Total Timelines: {stats['total_timelines']}")
            print(f"   Notification Preferences: {stats['notification_preferences']}")
            print(f"   Polling Interval: {stats['polling_interval']} seconds")
            print()
            
            # Stop monitoring
            print("🛑 Stopping monitoring...")
            await status_tracker.stop_monitoring_grievance(grievance.reference_number)
            print("   ✅ Monitoring stopped")
            print()


async def demo_status_inquiry():
    """Demonstrate natural language status inquiry processing."""
    print("🗣️  Natural Language Status Inquiry Demo")
    print("=" * 50)
    
    # Mock entities for status inquiry
    from bharat_voice_assistant.language.entity_extractor import Entity, EntityType
    
    # Create mock status tracker
    mock_client = MockGovernmentAPIClient()
    
    async with GrievanceStatusMonitor(api_client=mock_client) as status_monitor:
        async with GrievanceStatusTracker(status_monitor) as status_tracker:
            
            # First, create some status data
            await mock_client.check_status(None, None, "DEMO2024001")
            await mock_client.check_status(None, None, "DEMO2024001")  # Trigger status change
            
            # Test different types of inquiries
            test_inquiries = [
                {
                    'text': 'मेरी शिकायत DEMO2024001 की स्थिति क्या है?',
                    'entities': [Entity(type=EntityType.REFERENCE_NUMBER, value='DEMO2024001', confidence=0.9, start_pos=10, end_pos=21, language='hi')],
                    'language': 'hi'
                },
                {
                    'text': 'Check status of my application DEMO2024001',
                    'entities': [Entity(type=EntityType.REFERENCE_NUMBER, value='DEMO2024001', confidence=0.9, start_pos=32, end_pos=43, language='en')],
                    'language': 'en'
                },
                {
                    'text': 'DEMO2024001 का पूरा इतिहास बताएं',
                    'entities': [Entity(type=EntityType.REFERENCE_NUMBER, value='DEMO2024001', confidence=0.9, start_pos=0, end_pos=11, language='hi')],
                    'language': 'hi'
                },
                {
                    'text': 'When will DEMO2024001 be completed?',
                    'entities': [Entity(type=EntityType.REFERENCE_NUMBER, value='DEMO2024001', confidence=0.9, start_pos=10, end_pos=21, language='en')],
                    'language': 'en'
                }
            ]
            
            for i, inquiry in enumerate(test_inquiries, 1):
                print(f"🔍 Inquiry #{i}: {inquiry['text']}")
                print("-" * 40)
                
                response = await status_tracker.process_status_inquiry(
                    inquiry['text'],
                    inquiry['entities'],
                    inquiry['language']
                )
                
                if response.success:
                    print(f"✅ Response: {response.message}")
                    if response.current_status:
                        print(f"   Status: {response.current_status}")
                    if response.progress_percentage:
                        print(f"   Progress: {response.progress_percentage:.0f}%")
                else:
                    print(f"❌ Error: {response.message}")
                
                print()


async def main():
    """Run all demos."""
    try:
        await demo_status_monitoring()
        print("\n" + "=" * 60 + "\n")
        await demo_status_inquiry()
        
        print("🎉 Demo completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✅ Real-time status monitoring")
        print("✅ Status change detection")
        print("✅ Notification management")
        print("✅ Timeline visualization")
        print("✅ Progress estimation")
        print("✅ Natural language status inquiries")
        print("✅ Multilingual support (Hindi/English)")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())