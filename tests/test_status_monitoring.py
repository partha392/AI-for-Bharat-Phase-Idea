"""
Unit tests for grievance status monitoring system.

Tests the status monitor, status tracker, and timeline visualizer
components for correctness and reliability.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, date
from unittest.mock import Mock, AsyncMock, patch

from bharat_voice_assistant.grievance import (
    GrievanceRecord, GrievanceStatus, GrievanceType, GrievancePriority,
    GrievanceDetails, ContactInformation,
    GrievanceStatusMonitor, GrievanceStatusTracker,
    GrievanceTimelineVisualizer, TimelineVisualizationType,
    StatusChange, StatusChangeType, NotificationPreference, NotificationChannel,
    StatusTimeline, StatusInquiryType, StatusExplanationLevel,
    ProgressEstimationMethod
)
from bharat_voice_assistant.integration.models import (
    SubmissionStatus, StatusResponse as IntegrationStatusResponse
)
from bharat_voice_assistant.language.entity_extractor import Entity, EntityType


class TestGrievanceStatusMonitor:
    """Test cases for GrievanceStatusMonitor."""
    
    @pytest.fixture
    def sample_grievance(self):
        """Create a sample grievance for testing."""
        return GrievanceRecord(
            reference_number="TEST2024001",
            user_id="test_user",
            details=GrievanceDetails(
                problem_description="Test grievance",
                grievance_type=GrievanceType.PENSION_ISSUE
            ),
            contact_info=ContactInformation(
                phone_number="+91-9876543210",
                email="test@example.com"
            ),
            status=GrievanceStatus.SUBMITTED,
            language="hi"
        )
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client."""
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock successful status response
        mock_response = Mock()
        mock_response.is_success.return_value = True
        mock_response.data = {
            'status': 'in_progress',
            'status_message': 'Your grievance is being processed',
            'last_updated': datetime.now().isoformat(),
            'assigned_officer': 'Test Officer',
            'department': 'Test Department'
        }
        client.check_status = AsyncMock(return_value=mock_response)
        
        return client
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create a mock config loader."""
        loader = Mock()
        config = Mock()
        config.portals = []
        loader.load_integration_config.return_value = config
        return loader
    
    @pytest.mark.asyncio
    async def test_status_monitor_initialization(self, mock_api_client, mock_config_loader):
        """Test status monitor initialization."""
        async with GrievanceStatusMonitor(mock_api_client, mock_config_loader) as monitor:
            assert monitor.api_client == mock_api_client
            assert monitor.config_loader == mock_config_loader
            assert isinstance(monitor.status_timelines, dict)
            assert isinstance(monitor.notification_preferences, dict)
            assert isinstance(monitor.polling_tasks, dict)
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self, sample_grievance, mock_api_client, mock_config_loader):
        """Test starting monitoring for a grievance."""
        async with GrievanceStatusMonitor(mock_api_client, mock_config_loader) as monitor:
            success = await monitor.start_monitoring(sample_grievance)
            
            assert success is True
            assert sample_grievance.reference_number in monitor.status_timelines
            assert sample_grievance.reference_number in monitor.polling_tasks
    
    @pytest.mark.asyncio
    async def test_stop_monitoring(self, sample_grievance, mock_api_client, mock_config_loader):
        """Test stopping monitoring for a grievance."""
        async with GrievanceStatusMonitor(mock_api_client, mock_config_loader) as monitor:
            # Start monitoring first
            await monitor.start_monitoring(sample_grievance)
            
            # Stop monitoring
            success = await monitor.stop_monitoring(sample_grievance.reference_number)
            
            assert success is True
            assert sample_grievance.reference_number not in monitor.polling_tasks
    
    @pytest.mark.asyncio
    async def test_check_status_once(self, mock_api_client, mock_config_loader):
        """Test checking status once."""
        # Mock integration config with portals
        mock_config = Mock()
        mock_portal = Mock()
        mock_portal.id = "test_portal"
        mock_portal.is_active = True
        mock_portal.endpoints = {"status": Mock()}
        mock_config.portals = [mock_portal]
        mock_config_loader.load_integration_config.return_value = mock_config
        
        async with GrievanceStatusMonitor(mock_api_client, mock_config_loader) as monitor:
            status_response = await monitor.check_status_once("TEST2024001")
            
            assert status_response is not None
            assert status_response.reference_number == "TEST2024001"
            assert status_response.status == SubmissionStatus.IN_PROGRESS
    
    @pytest.mark.asyncio
    async def test_get_status_timeline(self, sample_grievance, mock_api_client, mock_config_loader):
        """Test getting status timeline."""
        async with GrievanceStatusMonitor(mock_api_client, mock_config_loader) as monitor:
            # Start monitoring to create timeline
            await monitor.start_monitoring(sample_grievance)
            
            timeline = await monitor.get_status_timeline(sample_grievance.reference_number)
            
            assert timeline is not None
            assert timeline.reference_number == sample_grievance.reference_number
            assert isinstance(timeline.status_history, list)
    
    @pytest.mark.asyncio
    async def test_notification_preferences(self, mock_api_client, mock_config_loader):
        """Test setting and getting notification preferences."""
        async with GrievanceStatusMonitor(mock_api_client, mock_config_loader) as monitor:
            preferences = NotificationPreference(
                user_id="test_user",
                reference_number="TEST2024001",
                channels=[NotificationChannel.SMS, NotificationChannel.EMAIL],
                language="hi"
            )
            
            await monitor.set_notification_preferences(preferences)
            
            retrieved_prefs = await monitor.get_notification_preferences("TEST2024001")
            
            assert retrieved_prefs is not None
            assert retrieved_prefs.user_id == "test_user"
            assert NotificationChannel.SMS in retrieved_prefs.channels
    
    def test_monitoring_stats(self, mock_api_client, mock_config_loader):
        """Test getting monitoring statistics."""
        monitor = GrievanceStatusMonitor(mock_api_client, mock_config_loader)
        
        stats = monitor.get_monitoring_stats()
        
        assert isinstance(stats, dict)
        assert 'active_monitoring_tasks' in stats
        assert 'total_timelines' in stats
        assert 'notification_preferences' in stats
        assert 'polling_interval' in stats


class TestGrievanceStatusTracker:
    """Test cases for GrievanceStatusTracker."""
    
    @pytest.fixture
    def mock_status_monitor(self):
        """Create a mock status monitor."""
        monitor = AsyncMock()
        monitor.__aenter__ = AsyncMock(return_value=monitor)
        monitor.__aexit__ = AsyncMock(return_value=None)
        
        # Mock current status response
        monitor.get_current_status.return_value = {
            'reference_number': 'TEST2024001',
            'current_status': 'in_progress',
            'progress_percentage': 50.0,
            'last_updated': datetime.now().isoformat(),
            'assigned_officer': 'Test Officer',
            'department': 'Test Department',
            'actions_required': ['Submit additional documents']
        }
        
        return monitor
    
    @pytest.mark.asyncio
    async def test_status_tracker_initialization(self, mock_status_monitor):
        """Test status tracker initialization."""
        async with GrievanceStatusTracker(mock_status_monitor) as tracker:
            assert tracker.status_monitor == mock_status_monitor
            assert hasattr(tracker, '_status_explanations')
    
    @pytest.mark.asyncio
    async def test_check_grievance_status_success(self, mock_status_monitor):
        """Test successful status check."""
        async with GrievanceStatusTracker(mock_status_monitor) as tracker:
            response = await tracker.check_grievance_status(
                "TEST2024001",
                StatusInquiryType.CURRENT_STATUS,
                "hi",
                StatusExplanationLevel.DETAILED
            )
            
            assert response.success is True
            assert response.reference_number == "TEST2024001"
            assert response.current_status == "in_progress"
            assert response.progress_percentage == 50.0
            assert response.language == "hi"
    
    @pytest.mark.asyncio
    async def test_check_grievance_status_not_found(self, mock_status_monitor):
        """Test status check when grievance not found."""
        mock_status_monitor.get_current_status.return_value = None
        
        async with GrievanceStatusTracker(mock_status_monitor) as tracker:
            response = await tracker.check_grievance_status("NOTFOUND", language="en")
            
            assert response.success is False
            assert "no information found" in response.message.lower() or "not found" in response.message.lower()
            assert response.language == "en"
    
    @pytest.mark.asyncio
    async def test_process_status_inquiry_with_reference(self, mock_status_monitor):
        """Test processing status inquiry with reference number."""
        entities = [Entity(type=EntityType.REFERENCE_NUMBER, value='TEST2024001', confidence=0.9, start_pos=0, end_pos=11, language='en')]
        
        async with GrievanceStatusTracker(mock_status_monitor) as tracker:
            response = await tracker.process_status_inquiry(
                "Check status of TEST2024001",
                entities,
                "en"
            )
            
            assert response.success is True
            assert response.reference_number == "TEST2024001"
    
    @pytest.mark.asyncio
    async def test_process_status_inquiry_missing_reference(self, mock_status_monitor):
        """Test processing status inquiry without reference number."""
        async with GrievanceStatusTracker(mock_status_monitor) as tracker:
            response = await tracker.process_status_inquiry(
                "Check my status",
                [],
                "hi"
            )
            
            assert response.success is False
            assert "संदर्भ संख्या" in response.message
    
    @pytest.mark.asyncio
    async def test_setup_notifications(self, mock_status_monitor):
        """Test setting up notifications."""
        async with GrievanceStatusTracker(mock_status_monitor) as tracker:
            success = await tracker.setup_notifications(
                "TEST2024001",
                "test_user",
                "+91-9876543210",
                "test@example.com",
                "hi",
                [NotificationChannel.SMS, NotificationChannel.EMAIL]
            )
            
            assert success is True
            mock_status_monitor.set_notification_preferences.assert_called_once()
    
    def test_validate_reference_number(self, mock_status_monitor):
        """Test reference number validation."""
        tracker = GrievanceStatusTracker(mock_status_monitor)
        
        assert tracker._validate_reference_number("TEST2024001") is True
        assert tracker._validate_reference_number("ABC") is False
        assert tracker._validate_reference_number("") is False
        assert tracker._validate_reference_number(None) is False
    
    def test_determine_inquiry_type(self, mock_status_monitor):
        """Test inquiry type determination."""
        tracker = GrievanceStatusTracker(mock_status_monitor)
        
        # Test Hindi keywords
        assert tracker._determine_inquiry_type("पूरा इतिहास दिखाएं", "hi") == StatusInquiryType.FULL_TIMELINE
        assert tracker._determine_inquiry_type("कब तक होगा", "hi") == StatusInquiryType.ESTIMATED_COMPLETION
        assert tracker._determine_inquiry_type("क्या करना है", "hi") == StatusInquiryType.REQUIRED_ACTIONS
        assert tracker._determine_inquiry_type("अधिकारी कौन है", "hi") == StatusInquiryType.CONTACT_OFFICER
        
        # Test English keywords
        assert tracker._determine_inquiry_type("show full timeline", "en") == StatusInquiryType.FULL_TIMELINE
        assert tracker._determine_inquiry_type("when will it finish", "en") == StatusInquiryType.ESTIMATED_COMPLETION
        assert tracker._determine_inquiry_type("what action required", "en") == StatusInquiryType.REQUIRED_ACTIONS
        assert tracker._determine_inquiry_type("who is the officer", "en") == StatusInquiryType.CONTACT_OFFICER
        
        # Default case
        assert tracker._determine_inquiry_type("simple status", "en") == StatusInquiryType.CURRENT_STATUS
    
    def test_determine_explanation_level(self, mock_status_monitor):
        """Test explanation level determination."""
        tracker = GrievanceStatusTracker(mock_status_monitor)
        
        # Test simple level
        assert tracker._determine_explanation_level("सिर्फ स्थिति बताएं", "hi") == StatusExplanationLevel.SIMPLE
        assert tracker._determine_explanation_level("just the status", "en") == StatusExplanationLevel.SIMPLE
        
        # Test detailed level
        assert tracker._determine_explanation_level("विस्तार से बताएं", "hi") == StatusExplanationLevel.COMPLETE
        assert tracker._determine_explanation_level("explain in detail", "en") == StatusExplanationLevel.COMPLETE
        
        # Default case
        assert tracker._determine_explanation_level("status check", "en") == StatusExplanationLevel.DETAILED


class TestGrievanceTimelineVisualizer:
    """Test cases for GrievanceTimelineVisualizer."""
    
    @pytest.fixture
    def sample_timeline(self):
        """Create a sample timeline for testing."""
        timeline = StatusTimeline(reference_number="TEST2024001")
        
        # Add some status changes
        change1 = StatusChange(
            reference_number="TEST2024001",
            change_type=StatusChangeType.STATUS_UPDATE,
            old_status=None,
            new_status=SubmissionStatus.SUBMITTED,
            message="Grievance submitted",
            timestamp=datetime.now() - timedelta(days=5)
        )
        
        change2 = StatusChange(
            reference_number="TEST2024001",
            change_type=StatusChangeType.STATUS_UPDATE,
            old_status=SubmissionStatus.SUBMITTED,
            new_status=SubmissionStatus.IN_PROGRESS,
            message="Investigation started",
            timestamp=datetime.now() - timedelta(days=2),
            assigned_officer="Test Officer"
        )
        
        timeline.add_status_change(change1)
        timeline.add_status_change(change2)
        
        return timeline
    
    def test_visualizer_initialization(self):
        """Test timeline visualizer initialization."""
        visualizer = GrievanceTimelineVisualizer()
        
        assert hasattr(visualizer, 'milestone_definitions')
        assert isinstance(visualizer.milestone_definitions, dict)
        assert 'hi' in visualizer.milestone_definitions
        assert 'en' in visualizer.milestone_definitions
    
    def test_create_timeline_visualization(self, sample_timeline):
        """Test creating timeline visualization."""
        visualizer = GrievanceTimelineVisualizer()
        
        viz = visualizer.create_timeline_visualization(
            sample_timeline,
            TimelineVisualizationType.DETAILED_TIMELINE,
            "hi"
        )
        
        assert viz.reference_number == "TEST2024001"
        assert viz.visualization_type == TimelineVisualizationType.DETAILED_TIMELINE
        assert viz.language == "hi"
        assert isinstance(viz.content, str)
        assert len(viz.content) > 0
        assert isinstance(viz.milestones, list)
        assert viz.progress_estimate is not None
    
    def test_create_text_timeline(self, sample_timeline):
        """Test creating text-based timeline."""
        visualizer = GrievanceTimelineVisualizer()
        
        viz = visualizer.create_timeline_visualization(
            sample_timeline,
            TimelineVisualizationType.TEXT_BASED,
            "en"
        )
        
        assert "Timeline for Grievance" in viz.content
        assert "TEST2024001" in viz.content
    
    def test_create_progress_bar(self, sample_timeline):
        """Test creating progress bar visualization."""
        visualizer = GrievanceTimelineVisualizer()
        
        viz = visualizer.create_timeline_visualization(
            sample_timeline,
            TimelineVisualizationType.PROGRESS_BAR,
            "hi"
        )
        
        assert "प्रगति" in viz.content
        assert "█" in viz.content or "░" in viz.content  # Progress bar characters
    
    def test_create_milestone_view(self, sample_timeline):
        """Test creating milestone view."""
        visualizer = GrievanceTimelineVisualizer()
        
        viz = visualizer.create_timeline_visualization(
            sample_timeline,
            TimelineVisualizationType.MILESTONE_VIEW,
            "en"
        )
        
        assert "Key Milestones" in viz.content
        assert "✓" in viz.content or "→" in viz.content or "○" in viz.content
    
    def test_estimate_progress_by_status(self, sample_timeline):
        """Test progress estimation by status."""
        visualizer = GrievanceTimelineVisualizer()
        
        estimate = visualizer.estimate_progress(
            sample_timeline,
            ProgressEstimationMethod.STATUS_BASED
        )
        
        assert estimate.reference_number == "TEST2024001"
        assert 0 <= estimate.current_progress_percentage <= 100
        assert estimate.confidence_level > 0
        assert estimate.estimation_method == ProgressEstimationMethod.STATUS_BASED
    
    def test_estimate_progress_by_time(self, sample_timeline):
        """Test progress estimation by time."""
        visualizer = GrievanceTimelineVisualizer()
        
        estimate = visualizer.estimate_progress(
            sample_timeline,
            ProgressEstimationMethod.TIME_BASED
        )
        
        assert estimate.reference_number == "TEST2024001"
        assert estimate.estimation_method == ProgressEstimationMethod.TIME_BASED
        assert estimate.estimated_days_remaining is not None
    
    def test_get_progress_summary(self, sample_timeline):
        """Test getting progress summary."""
        visualizer = GrievanceTimelineVisualizer()
        
        # Test Hindi summary
        summary_hi = visualizer.get_progress_summary(sample_timeline, "hi")
        
        assert isinstance(summary_hi, dict)
        assert 'progress_text' in summary_hi
        assert 'milestone_text' in summary_hi
        assert 'current_stage' in summary_hi
        assert 'progress_percentage' in summary_hi
        assert "पूर्ण" in summary_hi['progress_text']
        
        # Test English summary
        summary_en = visualizer.get_progress_summary(sample_timeline, "en")
        
        assert isinstance(summary_en, dict)
        assert "Complete" in summary_en['progress_text']
        assert "Milestones" in summary_en['milestone_text']
    
    def test_format_date_hindi(self):
        """Test Hindi date formatting."""
        visualizer = GrievanceTimelineVisualizer()
        
        test_date = date(2024, 3, 15)
        formatted = visualizer._format_date_hindi(test_date)
        
        assert "15" in formatted
        assert "मार्च" in formatted
        assert "2024" in formatted
        
        # Test None date
        assert visualizer._format_date_hindi(None) == "अनुपलब्ध"


class TestStatusChange:
    """Test cases for StatusChange model."""
    
    def test_status_change_creation(self):
        """Test creating a status change."""
        change = StatusChange(
            reference_number="TEST2024001",
            change_type=StatusChangeType.STATUS_UPDATE,
            old_status=SubmissionStatus.SUBMITTED,
            new_status=SubmissionStatus.IN_PROGRESS,
            message="Status updated",
            assigned_officer="Test Officer"
        )
        
        assert change.reference_number == "TEST2024001"
        assert change.change_type == StatusChangeType.STATUS_UPDATE
        assert change.old_status == SubmissionStatus.SUBMITTED
        assert change.new_status == SubmissionStatus.IN_PROGRESS
        assert change.message == "Status updated"
        assert change.assigned_officer == "Test Officer"
        assert isinstance(change.timestamp, datetime)
    
    def test_status_change_to_dict(self):
        """Test converting status change to dictionary."""
        change = StatusChange(
            reference_number="TEST2024001",
            change_type=StatusChangeType.STATUS_UPDATE,
            new_status=SubmissionStatus.IN_PROGRESS,
            message="Test message"
        )
        
        change_dict = change.to_dict()
        
        assert isinstance(change_dict, dict)
        assert change_dict['reference_number'] == "TEST2024001"
        assert change_dict['change_type'] == StatusChangeType.STATUS_UPDATE.value
        assert change_dict['new_status'] == SubmissionStatus.IN_PROGRESS.value
        assert change_dict['message'] == "Test message"
        assert 'timestamp' in change_dict


class TestStatusTimeline:
    """Test cases for StatusTimeline model."""
    
    def test_timeline_creation(self):
        """Test creating a status timeline."""
        timeline = StatusTimeline(reference_number="TEST2024001")
        
        assert timeline.reference_number == "TEST2024001"
        assert isinstance(timeline.status_history, list)
        assert len(timeline.status_history) == 0
        assert timeline.current_status is None
        assert timeline.progress_percentage == 0.0
    
    def test_add_status_change(self):
        """Test adding status change to timeline."""
        timeline = StatusTimeline(reference_number="TEST2024001")
        
        change = StatusChange(
            reference_number="TEST2024001",
            change_type=StatusChangeType.STATUS_UPDATE,
            new_status=SubmissionStatus.IN_PROGRESS,
            message="Test change"
        )
        
        timeline.add_status_change(change)
        
        assert len(timeline.status_history) == 1
        assert timeline.current_status == SubmissionStatus.IN_PROGRESS
        assert timeline.progress_percentage > 0
    
    def test_get_latest_change(self):
        """Test getting latest status change."""
        timeline = StatusTimeline(reference_number="TEST2024001")
        
        change1 = StatusChange(
            reference_number="TEST2024001",
            change_type=StatusChangeType.STATUS_UPDATE,
            new_status=SubmissionStatus.SUBMITTED,
            message="First change",
            timestamp=datetime.now() - timedelta(hours=1)
        )
        
        change2 = StatusChange(
            reference_number="TEST2024001",
            change_type=StatusChangeType.STATUS_UPDATE,
            new_status=SubmissionStatus.IN_PROGRESS,
            message="Second change",
            timestamp=datetime.now()
        )
        
        timeline.add_status_change(change1)
        timeline.add_status_change(change2)
        
        latest = timeline.get_latest_change()
        assert latest.message == "Second change"
    
    def test_timeline_to_dict(self):
        """Test converting timeline to dictionary."""
        timeline = StatusTimeline(reference_number="TEST2024001")
        
        change = StatusChange(
            reference_number="TEST2024001",
            change_type=StatusChangeType.STATUS_UPDATE,
            new_status=SubmissionStatus.IN_PROGRESS,
            message="Test change"
        )
        
        timeline.add_status_change(change)
        timeline_dict = timeline.to_dict()
        
        assert isinstance(timeline_dict, dict)
        assert timeline_dict['reference_number'] == "TEST2024001"
        assert timeline_dict['current_status'] == SubmissionStatus.IN_PROGRESS.value
        assert len(timeline_dict['status_history']) == 1
        assert 'progress_percentage' in timeline_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])