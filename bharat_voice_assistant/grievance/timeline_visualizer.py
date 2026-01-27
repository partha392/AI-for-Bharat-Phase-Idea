"""
Timeline visualization and progress estimation for grievances.

This module provides visual timeline representation and progress
estimation functionality for grievance status tracking.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json

from .status_monitor import StatusTimeline, StatusChange, StatusChangeType
from ..integration.models import SubmissionStatus

logger = logging.getLogger(__name__)


class TimelineVisualizationType(Enum):
    """Types of timeline visualizations."""
    TEXT_BASED = "text_based"
    PROGRESS_BAR = "progress_bar"
    MILESTONE_VIEW = "milestone_view"
    DETAILED_TIMELINE = "detailed_timeline"


class ProgressEstimationMethod(Enum):
    """Methods for progress estimation."""
    STATUS_BASED = "status_based"
    TIME_BASED = "time_based"
    HISTORICAL_AVERAGE = "historical_average"
    MACHINE_LEARNING = "machine_learning"


@dataclass
class TimelineMilestone:
    """Represents a milestone in the grievance timeline."""
    name: str
    status: SubmissionStatus
    description: str
    expected_duration_days: int
    is_completed: bool = False
    completion_date: Optional[datetime] = None
    is_current: bool = False
    progress_percentage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'name': self.name,
            'status': self.status.value,
            'description': self.description,
            'expected_duration_days': self.expected_duration_days,
            'is_completed': self.is_completed,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'is_current': self.is_current,
            'progress_percentage': self.progress_percentage
        }


@dataclass
class ProgressEstimate:
    """Progress estimation for a grievance."""
    reference_number: str
    current_progress_percentage: float
    estimated_completion_date: Optional[date]
    estimated_days_remaining: Optional[int]
    confidence_level: float  # 0.0 to 1.0
    estimation_method: ProgressEstimationMethod
    factors_considered: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'reference_number': self.reference_number,
            'current_progress_percentage': self.current_progress_percentage,
            'estimated_completion_date': self.estimated_completion_date.isoformat() if self.estimated_completion_date else None,
            'estimated_days_remaining': self.estimated_days_remaining,
            'confidence_level': self.confidence_level,
            'estimation_method': self.estimation_method.value,
            'factors_considered': self.factors_considered,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class TimelineVisualization:
    """Visual representation of grievance timeline."""
    reference_number: str
    visualization_type: TimelineVisualizationType
    content: str
    milestones: List[TimelineMilestone] = field(default_factory=list)
    progress_estimate: Optional[ProgressEstimate] = None
    language: str = "hi"
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'reference_number': self.reference_number,
            'visualization_type': self.visualization_type.value,
            'content': self.content,
            'milestones': [m.to_dict() for m in self.milestones],
            'progress_estimate': self.progress_estimate.to_dict() if self.progress_estimate else None,
            'language': self.language,
            'created_at': self.created_at.isoformat()
        }


class GrievanceTimelineVisualizer:
    """
    Timeline visualization and progress estimation service.
    
    Provides visual representations of grievance progress and
    estimates completion timelines based on various factors.
    """
    
    def __init__(self):
        """Initialize the timeline visualizer."""
        self.milestone_definitions = self._load_milestone_definitions()
        self.historical_data = {}  # In production, load from database
        logger.info("GrievanceTimelineVisualizer initialized")
    
    def create_timeline_visualization(self, timeline: StatusTimeline,
                                    visualization_type: TimelineVisualizationType = TimelineVisualizationType.DETAILED_TIMELINE,
                                    language: str = "hi") -> TimelineVisualization:
        """
        Create a visual timeline representation.
        
        Args:
            timeline: Status timeline to visualize
            visualization_type: Type of visualization to create
            language: Language for the visualization
            
        Returns:
            TimelineVisualization object
        """
        try:
            # Create milestones
            milestones = self._create_milestones(timeline, language)
            
            # Generate progress estimate
            progress_estimate = self.estimate_progress(timeline)
            
            # Generate visualization content
            if visualization_type == TimelineVisualizationType.TEXT_BASED:
                content = self._create_text_timeline(timeline, milestones, language)
            elif visualization_type == TimelineVisualizationType.PROGRESS_BAR:
                content = self._create_progress_bar(timeline, milestones, language)
            elif visualization_type == TimelineVisualizationType.MILESTONE_VIEW:
                content = self._create_milestone_view(milestones, language)
            else:  # DETAILED_TIMELINE
                content = self._create_detailed_timeline(timeline, milestones, language)
            
            return TimelineVisualization(
                reference_number=timeline.reference_number,
                visualization_type=visualization_type,
                content=content,
                milestones=milestones,
                progress_estimate=progress_estimate,
                language=language
            )
            
        except Exception as e:
            logger.error(f"Error creating timeline visualization: {e}")
            # Return basic visualization
            return TimelineVisualization(
                reference_number=timeline.reference_number,
                visualization_type=visualization_type,
                content=self._create_error_visualization(timeline.reference_number, language),
                language=language
            )
    
    def estimate_progress(self, timeline: StatusTimeline,
                         method: ProgressEstimationMethod = ProgressEstimationMethod.STATUS_BASED) -> ProgressEstimate:
        """
        Estimate progress and completion timeline.
        
        Args:
            timeline: Status timeline to analyze
            method: Estimation method to use
            
        Returns:
            ProgressEstimate object
        """
        try:
            if method == ProgressEstimationMethod.STATUS_BASED:
                return self._estimate_progress_by_status(timeline)
            elif method == ProgressEstimationMethod.TIME_BASED:
                return self._estimate_progress_by_time(timeline)
            elif method == ProgressEstimationMethod.HISTORICAL_AVERAGE:
                return self._estimate_progress_by_history(timeline)
            else:  # Default to status-based
                return self._estimate_progress_by_status(timeline)
                
        except Exception as e:
            logger.error(f"Error estimating progress: {e}")
            # Return basic estimate
            return ProgressEstimate(
                reference_number=timeline.reference_number,
                current_progress_percentage=timeline.progress_percentage,
                estimated_completion_date=None,
                estimated_days_remaining=None,
                confidence_level=0.3,
                estimation_method=method,
                factors_considered=["error_fallback"]
            )
    
    def get_progress_summary(self, timeline: StatusTimeline, language: str = "hi") -> Dict[str, Any]:
        """
        Get a summary of progress information.
        
        Args:
            timeline: Status timeline
            language: Language for the summary
            
        Returns:
            Dictionary with progress summary
        """
        try:
            progress_estimate = self.estimate_progress(timeline)
            milestones = self._create_milestones(timeline, language)
            
            # Count completed milestones
            completed_milestones = sum(1 for m in milestones if m.is_completed)
            total_milestones = len(milestones)
            
            # Get current milestone
            current_milestone = next((m for m in milestones if m.is_current), None)
            
            if language == 'hi':
                summary = {
                    'progress_text': f"{progress_estimate.current_progress_percentage:.0f}% पूर्ण",
                    'milestone_text': f"{completed_milestones}/{total_milestones} चरण पूर्ण",
                    'current_stage': current_milestone.name if current_milestone else "अज्ञात",
                    'estimated_completion': self._format_date_hindi(progress_estimate.estimated_completion_date) if progress_estimate.estimated_completion_date else "अनुमान उपलब्ध नहीं",
                    'days_remaining': f"{progress_estimate.estimated_days_remaining} दिन शेष" if progress_estimate.estimated_days_remaining else "अनुमान उपलब्ध नहीं"
                }
            else:  # English
                summary = {
                    'progress_text': f"{progress_estimate.current_progress_percentage:.0f}% Complete",
                    'milestone_text': f"{completed_milestones}/{total_milestones} Milestones Complete",
                    'current_stage': current_milestone.name if current_milestone else "Unknown",
                    'estimated_completion': progress_estimate.estimated_completion_date.strftime("%B %d, %Y") if progress_estimate.estimated_completion_date else "Not Available",
                    'days_remaining': f"{progress_estimate.estimated_days_remaining} days remaining" if progress_estimate.estimated_days_remaining else "Not Available"
                }
            
            summary.update({
                'progress_percentage': progress_estimate.current_progress_percentage,
                'completed_milestones': completed_milestones,
                'total_milestones': total_milestones,
                'confidence_level': progress_estimate.confidence_level,
                'last_updated': timeline.last_updated.isoformat()
            })
            
            return summary
            
        except Exception as e:
            logger.error(f"Error creating progress summary: {e}")
            return {
                'progress_text': "Error",
                'milestone_text': "Error",
                'current_stage': "Error",
                'estimated_completion': "Error",
                'days_remaining': "Error",
                'progress_percentage': 0.0,
                'completed_milestones': 0,
                'total_milestones': 0,
                'confidence_level': 0.0,
                'last_updated': datetime.now().isoformat()
            }
    
    def _create_milestones(self, timeline: StatusTimeline, language: str) -> List[TimelineMilestone]:
        """Create milestone list based on timeline."""
        milestones = []
        milestone_defs = self.milestone_definitions.get(language, self.milestone_definitions['en'])
        
        for status, milestone_info in milestone_defs.items():
            milestone = TimelineMilestone(
                name=milestone_info['name'],
                status=SubmissionStatus(status),
                description=milestone_info['description'],
                expected_duration_days=milestone_info['expected_duration_days']
            )
            
            # Check if milestone is completed
            if timeline.status_history:
                for change in timeline.status_history:
                    if change.new_status == SubmissionStatus(status):
                        milestone.is_completed = True
                        milestone.completion_date = change.timestamp
                        milestone.progress_percentage = 100.0
                        break
            
            # Check if this is the current milestone
            if timeline.current_status == SubmissionStatus(status):
                milestone.is_current = True
                if not milestone.is_completed:
                    milestone.progress_percentage = 50.0  # Assume 50% if current but not completed
            
            milestones.append(milestone)
        
        return milestones
    
    def _create_text_timeline(self, timeline: StatusTimeline, milestones: List[TimelineMilestone], language: str) -> str:
        """Create text-based timeline."""
        if language == 'hi':
            content = f"शिकायत {timeline.reference_number} की समयसीमा:\n\n"
        else:
            content = f"Timeline for Grievance {timeline.reference_number}:\n\n"
        
        for i, milestone in enumerate(milestones, 1):
            status_symbol = "✓" if milestone.is_completed else ("→" if milestone.is_current else "○")
            content += f"{status_symbol} {milestone.name}\n"
            
            if milestone.completion_date:
                date_str = milestone.completion_date.strftime("%Y-%m-%d")
                if language == 'hi':
                    content += f"   पूर्ण: {date_str}\n"
                else:
                    content += f"   Completed: {date_str}\n"
            elif milestone.is_current:
                if language == 'hi':
                    content += f"   वर्तमान चरण\n"
                else:
                    content += f"   Current Stage\n"
            
            content += "\n"
        
        return content
    
    def _create_progress_bar(self, timeline: StatusTimeline, milestones: List[TimelineMilestone], language: str) -> str:
        """Create progress bar visualization."""
        progress = timeline.progress_percentage
        bar_length = 20
        filled_length = int(bar_length * progress / 100)
        
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        if language == 'hi':
            content = f"शिकायत {timeline.reference_number} की प्रगति:\n\n"
            content += f"[{bar}] {progress:.0f}%\n\n"
            content += f"वर्तमान स्थिति: {timeline.current_status.value if timeline.current_status else 'अज्ञात'}\n"
        else:
            content = f"Progress for Grievance {timeline.reference_number}:\n\n"
            content += f"[{bar}] {progress:.0f}%\n\n"
            content += f"Current Status: {timeline.current_status.value if timeline.current_status else 'Unknown'}\n"
        
        return content
    
    def _create_milestone_view(self, milestones: List[TimelineMilestone], language: str) -> str:
        """Create milestone-focused view."""
        if language == 'hi':
            content = "मुख्य चरण:\n\n"
        else:
            content = "Key Milestones:\n\n"
        
        for milestone in milestones:
            if milestone.is_completed:
                status_text = "✓ पूर्ण" if language == 'hi' else "✓ Complete"
            elif milestone.is_current:
                status_text = "→ चालू" if language == 'hi' else "→ Current"
            else:
                status_text = "○ प्रतीक्षा" if language == 'hi' else "○ Pending"
            
            content += f"{milestone.name}: {status_text}\n"
            content += f"   {milestone.description}\n\n"
        
        return content
    
    def _create_detailed_timeline(self, timeline: StatusTimeline, milestones: List[TimelineMilestone], language: str) -> str:
        """Create detailed timeline with all information."""
        if language == 'hi':
            content = f"शिकायत {timeline.reference_number} का विस्तृत समयसीमा:\n\n"
            content += f"प्रगति: {timeline.progress_percentage:.0f}%\n"
            content += f"अंतिम अपडेट: {timeline.last_updated.strftime('%Y-%m-%d %H:%M')}\n\n"
        else:
            content = f"Detailed Timeline for Grievance {timeline.reference_number}:\n\n"
            content += f"Progress: {timeline.progress_percentage:.0f}%\n"
            content += f"Last Updated: {timeline.last_updated.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        # Add status history
        if timeline.status_history:
            if language == 'hi':
                content += "स्थिति इतिहास:\n"
            else:
                content += "Status History:\n"
            
            for change in reversed(timeline.status_history):  # Most recent first
                date_str = change.timestamp.strftime("%Y-%m-%d %H:%M")
                content += f"• {date_str}: {change.message}\n"
                if change.assigned_officer:
                    officer_text = "अधिकारी" if language == 'hi' else "Officer"
                    content += f"  {officer_text}: {change.assigned_officer}\n"
        
        content += "\n"
        
        # Add milestones
        if language == 'hi':
            content += "चरण:\n"
        else:
            content += "Milestones:\n"
        
        for milestone in milestones:
            status_symbol = "✓" if milestone.is_completed else ("→" if milestone.is_current else "○")
            content += f"{status_symbol} {milestone.name}\n"
            content += f"   {milestone.description}\n"
            
            if milestone.completion_date:
                date_str = milestone.completion_date.strftime("%Y-%m-%d")
                completion_text = "पूर्ण" if language == 'hi' else "Completed"
                content += f"   {completion_text}: {date_str}\n"
            
            content += "\n"
        
        return content
    
    def _create_error_visualization(self, reference_number: str, language: str) -> str:
        """Create error visualization when timeline creation fails."""
        if language == 'hi':
            return f"शिकायत {reference_number} के लिए समयसीमा बनाने में त्रुटि हुई।"
        else:
            return f"Error creating timeline for grievance {reference_number}."
    
    def _estimate_progress_by_status(self, timeline: StatusTimeline) -> ProgressEstimate:
        """Estimate progress based on current status."""
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
        
        # Expected days for each status
        status_duration_map = {
            SubmissionStatus.PENDING: 1,
            SubmissionStatus.SUBMITTED: 2,
            SubmissionStatus.ACKNOWLEDGED: 3,
            SubmissionStatus.IN_PROGRESS: 10,
            SubmissionStatus.UNDER_REVIEW: 7,
            SubmissionStatus.RESOLVED: 0,
            SubmissionStatus.REJECTED: 0,
            SubmissionStatus.FAILED: 0,
            SubmissionStatus.TIMEOUT: 0
        }
        
        current_progress = timeline.progress_percentage
        if timeline.current_status:
            current_progress = status_progress_map.get(timeline.current_status, current_progress)
        
        # Estimate completion date
        estimated_completion_date = None
        estimated_days_remaining = None
        
        if timeline.current_status and timeline.current_status not in [SubmissionStatus.RESOLVED, SubmissionStatus.REJECTED]:
            # Calculate remaining days based on current status
            remaining_statuses = []
            found_current = False
            
            for status in [SubmissionStatus.PENDING, SubmissionStatus.SUBMITTED, SubmissionStatus.ACKNOWLEDGED,
                          SubmissionStatus.IN_PROGRESS, SubmissionStatus.UNDER_REVIEW, SubmissionStatus.RESOLVED]:
                if status == timeline.current_status:
                    found_current = True
                elif found_current:
                    remaining_statuses.append(status)
            
            if remaining_statuses:
                estimated_days_remaining = sum(status_duration_map.get(status, 5) for status in remaining_statuses)
                estimated_completion_date = (datetime.now() + timedelta(days=estimated_days_remaining)).date()
        
        return ProgressEstimate(
            reference_number=timeline.reference_number,
            current_progress_percentage=current_progress,
            estimated_completion_date=estimated_completion_date,
            estimated_days_remaining=estimated_days_remaining,
            confidence_level=0.7,
            estimation_method=ProgressEstimationMethod.STATUS_BASED,
            factors_considered=["current_status", "status_progression"]
        )
    
    def _estimate_progress_by_time(self, timeline: StatusTimeline) -> ProgressEstimate:
        """Estimate progress based on time elapsed."""
        if not timeline.status_history:
            return self._estimate_progress_by_status(timeline)
        
        # Get first status change (submission time)
        first_change = min(timeline.status_history, key=lambda x: x.timestamp)
        days_elapsed = (datetime.now() - first_change.timestamp).days
        
        # Assume average grievance takes 30 days
        average_duration = 30
        time_based_progress = min(100.0, (days_elapsed / average_duration) * 100)
        
        # Estimate remaining days
        estimated_days_remaining = max(0, average_duration - days_elapsed)
        estimated_completion_date = (datetime.now() + timedelta(days=estimated_days_remaining)).date()
        
        return ProgressEstimate(
            reference_number=timeline.reference_number,
            current_progress_percentage=time_based_progress,
            estimated_completion_date=estimated_completion_date,
            estimated_days_remaining=estimated_days_remaining,
            confidence_level=0.5,
            estimation_method=ProgressEstimationMethod.TIME_BASED,
            factors_considered=["time_elapsed", "average_duration"]
        )
    
    def _estimate_progress_by_history(self, timeline: StatusTimeline) -> ProgressEstimate:
        """Estimate progress based on historical data."""
        # This would use historical data from similar grievances
        # For now, fall back to status-based estimation
        return self._estimate_progress_by_status(timeline)
    
    def _format_date_hindi(self, date_obj: Optional[date]) -> str:
        """Format date in Hindi."""
        if not date_obj:
            return "अनुपलब्ध"
        
        months_hindi = {
            1: "जनवरी", 2: "फरवरी", 3: "मार्च", 4: "अप्रैल",
            5: "मई", 6: "जून", 7: "जुलाई", 8: "अगस्त",
            9: "सितंबर", 10: "अक्टूबर", 11: "नवंबर", 12: "दिसंबर"
        }
        
        return f"{date_obj.day} {months_hindi[date_obj.month]} {date_obj.year}"
    
    def _load_milestone_definitions(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Load milestone definitions for different languages."""
        return {
            'hi': {
                'pending': {
                    'name': 'प्रतीक्षा में',
                    'description': 'शिकायत प्राप्त हुई और प्रक्रिया की प्रतीक्षा में है',
                    'expected_duration_days': 1
                },
                'submitted': {
                    'name': 'जमा की गई',
                    'description': 'शिकायत सरकारी पोर्टल पर जमा की गई',
                    'expected_duration_days': 2
                },
                'acknowledged': {
                    'name': 'स्वीकार की गई',
                    'description': 'संबंधित विभाग द्वारा शिकायत स्वीकार की गई',
                    'expected_duration_days': 3
                },
                'in_progress': {
                    'name': 'प्रगति में',
                    'description': 'शिकायत की जांच चल रही है',
                    'expected_duration_days': 10
                },
                'under_review': {
                    'name': 'समीक्षा में',
                    'description': 'शिकायत की विस्तृत समीक्षा हो रही है',
                    'expected_duration_days': 7
                },
                'resolved': {
                    'name': 'हल हो गई',
                    'description': 'शिकायत का समाधान हो गया है',
                    'expected_duration_days': 0
                }
            },
            'en': {
                'pending': {
                    'name': 'Pending',
                    'description': 'Grievance received and awaiting processing',
                    'expected_duration_days': 1
                },
                'submitted': {
                    'name': 'Submitted',
                    'description': 'Grievance submitted to government portal',
                    'expected_duration_days': 2
                },
                'acknowledged': {
                    'name': 'Acknowledged',
                    'description': 'Grievance acknowledged by relevant department',
                    'expected_duration_days': 3
                },
                'in_progress': {
                    'name': 'In Progress',
                    'description': 'Grievance is being investigated',
                    'expected_duration_days': 10
                },
                'under_review': {
                    'name': 'Under Review',
                    'description': 'Grievance is under detailed review',
                    'expected_duration_days': 7
                },
                'resolved': {
                    'name': 'Resolved',
                    'description': 'Grievance has been resolved',
                    'expected_duration_days': 0
                }
            }
        }