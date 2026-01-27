"""
Status tracking service for grievances.

This module provides a high-level interface for tracking grievance status,
managing user interactions, and providing status information in a
user-friendly format.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from enum import Enum
from dataclasses import dataclass, field

from .models import GrievanceRecord, GrievanceStatus
from .status_monitor import (
    GrievanceStatusMonitor, StatusTimeline, NotificationPreference,
    NotificationChannel, StatusChangeType
)
from ..integration.models import SubmissionStatus
from ..language.intent_classifier import ServiceIntent
from ..language.entity_extractor import Entity, EntityType
from ..core.exceptions import ValidationError, GrievanceError

logger = logging.getLogger(__name__)


class StatusInquiryType(Enum):
    """Types of status inquiries."""
    CURRENT_STATUS = "current_status"
    FULL_TIMELINE = "full_timeline"
    ESTIMATED_COMPLETION = "estimated_completion"
    REQUIRED_ACTIONS = "required_actions"
    CONTACT_OFFICER = "contact_officer"


class StatusExplanationLevel(Enum):
    """Levels of status explanation detail."""
    SIMPLE = "simple"      # Basic status only
    DETAILED = "detailed"  # Status with explanation
    COMPLETE = "complete"  # Full timeline and details


@dataclass
class StatusInquiry:
    """Represents a status inquiry from user."""
    reference_number: str
    inquiry_type: StatusInquiryType
    user_id: Optional[str] = None
    language: str = "hi"
    explanation_level: StatusExplanationLevel = StatusExplanationLevel.DETAILED
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StatusResponse:
    """Response to status inquiry."""
    reference_number: str
    success: bool
    message: str
    current_status: Optional[str] = None
    progress_percentage: Optional[float] = None
    estimated_completion_date: Optional[str] = None
    assigned_officer: Optional[str] = None
    department: Optional[str] = None
    actions_required: List[str] = field(default_factory=list)
    timeline: Optional[List[Dict[str, Any]]] = None
    next_steps: List[str] = field(default_factory=list)
    language: str = "hi"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'reference_number': self.reference_number,
            'success': self.success,
            'message': self.message,
            'current_status': self.current_status,
            'progress_percentage': self.progress_percentage,
            'estimated_completion_date': self.estimated_completion_date,
            'assigned_officer': self.assigned_officer,
            'department': self.department,
            'actions_required': self.actions_required,
            'timeline': self.timeline,
            'next_steps': self.next_steps,
            'language': self.language
        }


class GrievanceStatusTracker:
    """
    High-level status tracking service.
    
    Provides user-friendly status tracking functionality with
    multilingual support and different levels of detail.
    """
    
    def __init__(self, status_monitor: Optional[GrievanceStatusMonitor] = None):
        """Initialize the status tracker."""
        self.status_monitor = status_monitor
        self._status_explanations = self._load_status_explanations()
        logger.info("GrievanceStatusTracker initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not self.status_monitor:
            self.status_monitor = GrievanceStatusMonitor()
        await self.status_monitor.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.status_monitor:
            await self.status_monitor.__aexit__(exc_type, exc_val, exc_tb)
    
    async def check_grievance_status(self, reference_number: str,
                                   inquiry_type: StatusInquiryType = StatusInquiryType.CURRENT_STATUS,
                                   language: str = "hi",
                                   explanation_level: StatusExplanationLevel = StatusExplanationLevel.DETAILED) -> StatusResponse:
        """
        Check status of a grievance.
        
        Args:
            reference_number: Reference number to check
            inquiry_type: Type of status inquiry
            language: Response language
            explanation_level: Level of detail in explanation
            
        Returns:
            StatusResponse with status information
        """
        try:
            # Validate reference number
            if not self._validate_reference_number(reference_number):
                return StatusResponse(
                    reference_number=reference_number,
                    success=False,
                    message=self._get_error_message("invalid_reference", language),
                    language=language
                )
            
            # Get current status from monitor
            current_status_info = await self.status_monitor.get_current_status(reference_number)
            
            if not current_status_info:
                return StatusResponse(
                    reference_number=reference_number,
                    success=False,
                    message=self._get_error_message("not_found", language),
                    language=language
                )
            
            # Build response based on inquiry type
            if inquiry_type == StatusInquiryType.CURRENT_STATUS:
                return await self._build_current_status_response(
                    current_status_info, language, explanation_level
                )
            
            elif inquiry_type == StatusInquiryType.FULL_TIMELINE:
                return await self._build_timeline_response(
                    reference_number, current_status_info, language
                )
            
            elif inquiry_type == StatusInquiryType.ESTIMATED_COMPLETION:
                return await self._build_completion_estimate_response(
                    current_status_info, language
                )
            
            elif inquiry_type == StatusInquiryType.REQUIRED_ACTIONS:
                return await self._build_required_actions_response(
                    current_status_info, language
                )
            
            elif inquiry_type == StatusInquiryType.CONTACT_OFFICER:
                return await self._build_contact_officer_response(
                    current_status_info, language
                )
            
            else:
                return await self._build_current_status_response(
                    current_status_info, language, explanation_level
                )
                
        except Exception as e:
            logger.error(f"Error checking status for {reference_number}: {e}")
            return StatusResponse(
                reference_number=reference_number,
                success=False,
                message=self._get_error_message("system_error", language),
                language=language
            )
    
    async def process_status_inquiry(self, user_input: str, entities: List[Entity],
                                   language: str = "hi") -> StatusResponse:
        """
        Process natural language status inquiry.
        
        Args:
            user_input: User's input text
            entities: Extracted entities
            language: User's language
            
        Returns:
            StatusResponse with status information
        """
        try:
            # Extract reference number from entities
            reference_number = None
            for entity in entities:
                if entity.type == EntityType.REFERENCE_NUMBER:
                    reference_number = entity.value
                    break
            
            if not reference_number:
                return StatusResponse(
                    reference_number="",
                    success=False,
                    message=self._get_error_message("missing_reference", language),
                    language=language
                )
            
            # Determine inquiry type from user input
            inquiry_type = self._determine_inquiry_type(user_input, language)
            
            # Determine explanation level
            explanation_level = self._determine_explanation_level(user_input, language)
            
            # Check status
            return await self.check_grievance_status(
                reference_number, inquiry_type, language, explanation_level
            )
            
        except Exception as e:
            logger.error(f"Error processing status inquiry: {e}")
            return StatusResponse(
                reference_number="",
                success=False,
                message=self._get_error_message("system_error", language),
                language=language
            )
    
    async def setup_notifications(self, reference_number: str, user_id: str,
                                phone_number: Optional[str] = None,
                                email: Optional[str] = None,
                                language: str = "hi",
                                channels: Optional[List[NotificationChannel]] = None) -> bool:
        """
        Set up status change notifications for a user.
        
        Args:
            reference_number: Reference number to monitor
            user_id: User identifier
            phone_number: User's phone number
            email: User's email address
            language: User's preferred language
            channels: Preferred notification channels
            
        Returns:
            True if notifications were set up successfully
        """
        try:
            # Default channels if not specified
            if not channels:
                channels = [NotificationChannel.IN_APP]
                if phone_number:
                    channels.append(NotificationChannel.SMS)
                if email:
                    channels.append(NotificationChannel.EMAIL)
            
            # Create notification preferences
            preferences = NotificationPreference(
                user_id=user_id,
                reference_number=reference_number,
                channels=channels,
                language=language,
                phone_number=phone_number,
                email=email,
                notification_types=list(StatusChangeType)  # All types by default
            )
            
            # Set preferences in monitor
            await self.status_monitor.set_notification_preferences(preferences)
            
            logger.info(f"Set up notifications for {reference_number} (user: {user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup notifications for {reference_number}: {e}")
            return False
    
    async def start_monitoring_grievance(self, grievance: GrievanceRecord,
                                       user_id: Optional[str] = None,
                                       phone_number: Optional[str] = None,
                                       email: Optional[str] = None) -> bool:
        """
        Start monitoring a grievance for status changes.
        
        Args:
            grievance: Grievance record to monitor
            user_id: User identifier for notifications
            phone_number: Phone number for SMS notifications
            email: Email for email notifications
            
        Returns:
            True if monitoring started successfully
        """
        try:
            # Set up notifications if user info provided
            notification_preferences = None
            if user_id:
                channels = [NotificationChannel.IN_APP]
                if phone_number:
                    channels.append(NotificationChannel.SMS)
                if email:
                    channels.append(NotificationChannel.EMAIL)
                
                notification_preferences = NotificationPreference(
                    user_id=user_id,
                    reference_number=grievance.reference_number or grievance.government_reference,
                    channels=channels,
                    language=grievance.language,
                    phone_number=phone_number,
                    email=email
                )
            
            # Start monitoring
            success = await self.status_monitor.start_monitoring(
                grievance, notification_preferences
            )
            
            if success:
                logger.info(f"Started monitoring grievance {grievance.reference_number}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to start monitoring grievance: {e}")
            return False
    
    async def stop_monitoring_grievance(self, reference_number: str) -> bool:
        """Stop monitoring a grievance."""
        try:
            return await self.status_monitor.stop_monitoring(reference_number)
        except Exception as e:
            logger.error(f"Failed to stop monitoring {reference_number}: {e}")
            return False
    
    def _validate_reference_number(self, reference_number: str) -> bool:
        """Validate reference number format."""
        if not reference_number or len(reference_number.strip()) < 5:
            return False
        
        # Basic validation - could be enhanced with specific format checks
        return True
    
    def _determine_inquiry_type(self, user_input: str, language: str) -> StatusInquiryType:
        """Determine the type of status inquiry from user input."""
        user_input_lower = user_input.lower()
        
        if language == 'hi':
            keywords = {
                StatusInquiryType.FULL_TIMELINE: ['पूरा इतिहास', 'सभी अपडेट', 'टाइमलाइन', 'सारी जानकारी'],
                StatusInquiryType.ESTIMATED_COMPLETION: ['कब तक', 'समय', 'कितने दिन', 'अनुमान'],
                StatusInquiryType.REQUIRED_ACTIONS: ['क्या करना', 'अगला कदम', 'कार्रवाई', 'जरूरी'],
                StatusInquiryType.CONTACT_OFFICER: ['अधिकारी', 'संपर्क', 'कौन', 'जिम्मेदार']
            }
        else:  # English
            keywords = {
                StatusInquiryType.FULL_TIMELINE: ['full history', 'all updates', 'timeline', 'complete'],
                StatusInquiryType.ESTIMATED_COMPLETION: ['when', 'time', 'how long', 'estimate', 'completion'],
                StatusInquiryType.REQUIRED_ACTIONS: ['what to do', 'next step', 'action', 'required'],
                StatusInquiryType.CONTACT_OFFICER: ['officer', 'contact', 'who', 'responsible']
            }
        
        for inquiry_type, type_keywords in keywords.items():
            if any(keyword in user_input_lower for keyword in type_keywords):
                return inquiry_type
        
        return StatusInquiryType.CURRENT_STATUS
    
    def _determine_explanation_level(self, user_input: str, language: str) -> StatusExplanationLevel:
        """Determine the level of explanation needed."""
        user_input_lower = user_input.lower()
        
        if language == 'hi':
            simple_keywords = ['सिर्फ', 'केवल', 'बस', 'छोटा']
            detailed_keywords = ['विस्तार', 'समझाएं', 'बताएं', 'जानकारी']
        else:  # English
            simple_keywords = ['just', 'only', 'brief', 'short']
            detailed_keywords = ['detail', 'explain', 'tell me', 'information']
        
        if any(keyword in user_input_lower for keyword in simple_keywords):
            return StatusExplanationLevel.SIMPLE
        elif any(keyword in user_input_lower for keyword in detailed_keywords):
            return StatusExplanationLevel.COMPLETE
        
        return StatusExplanationLevel.DETAILED
    
    async def _build_current_status_response(self, status_info: Dict[str, Any],
                                           language: str,
                                           explanation_level: StatusExplanationLevel) -> StatusResponse:
        """Build current status response."""
        reference_number = status_info['reference_number']
        current_status = status_info['current_status']
        
        # Get status explanation
        status_explanation = self._get_status_explanation(current_status, language, explanation_level)
        
        # Build message
        if language == 'hi':
            if explanation_level == StatusExplanationLevel.SIMPLE:
                message = f"आपकी शिकायत {reference_number} की स्थिति: {status_explanation}"
            else:
                message = f"आपकी शिकायत {reference_number} की वर्तमान स्थिति: {status_explanation}"
                if status_info.get('progress_percentage'):
                    message += f"\nप्रगति: {status_info['progress_percentage']:.0f}%"
        else:  # English
            if explanation_level == StatusExplanationLevel.SIMPLE:
                message = f"Your grievance {reference_number} status: {status_explanation}"
            else:
                message = f"Current status of your grievance {reference_number}: {status_explanation}"
                if status_info.get('progress_percentage'):
                    message += f"\nProgress: {status_info['progress_percentage']:.0f}%"
        
        # Add next steps if available
        next_steps = []
        if status_info.get('actions_required'):
            next_steps.extend(status_info['actions_required'])
        
        return StatusResponse(
            reference_number=reference_number,
            success=True,
            message=message,
            current_status=current_status,
            progress_percentage=status_info.get('progress_percentage'),
            estimated_completion_date=status_info.get('estimated_completion_date'),
            assigned_officer=status_info.get('assigned_officer'),
            department=status_info.get('department'),
            actions_required=status_info.get('actions_required', []),
            next_steps=next_steps,
            language=language
        )
    
    async def _build_timeline_response(self, reference_number: str,
                                     status_info: Dict[str, Any],
                                     language: str) -> StatusResponse:
        """Build full timeline response."""
        timeline = await self.status_monitor.get_status_timeline(reference_number)
        
        timeline_data = []
        if timeline and timeline.status_history:
            for change in timeline.status_history:
                timeline_data.append({
                    'timestamp': change.timestamp.isoformat(),
                    'status': change.new_status.value if change.new_status else 'unknown',
                    'message': change.message,
                    'officer': change.assigned_officer,
                    'department': change.department
                })
        
        if language == 'hi':
            message = f"आपकी शिकायत {reference_number} का पूरा इतिहास:\n"
            if timeline_data:
                for i, entry in enumerate(timeline_data, 1):
                    message += f"{i}. {entry['message']} ({entry['timestamp'][:10]})\n"
            else:
                message += "अभी तक कोई अपडेट नहीं मिला है।"
        else:  # English
            message = f"Complete timeline for your grievance {reference_number}:\n"
            if timeline_data:
                for i, entry in enumerate(timeline_data, 1):
                    message += f"{i}. {entry['message']} ({entry['timestamp'][:10]})\n"
            else:
                message += "No updates available yet."
        
        return StatusResponse(
            reference_number=reference_number,
            success=True,
            message=message,
            current_status=status_info.get('current_status'),
            timeline=timeline_data,
            language=language
        )
    
    async def _build_completion_estimate_response(self, status_info: Dict[str, Any],
                                                language: str) -> StatusResponse:
        """Build completion estimate response."""
        reference_number = status_info['reference_number']
        estimated_date = status_info.get('estimated_completion_date')
        
        if language == 'hi':
            if estimated_date:
                message = f"आपकी शिकायत {reference_number} का अनुमानित समाधान दिनांक: {estimated_date}"
            else:
                message = f"आपकी शिकायत {reference_number} के लिए अभी तक कोई अनुमानित समय नहीं दिया गया है। सामान्यतः 15-30 कार्य दिवस लगते हैं।"
        else:  # English
            if estimated_date:
                message = f"Estimated completion date for your grievance {reference_number}: {estimated_date}"
            else:
                message = f"No estimated completion date available for grievance {reference_number}. Typically takes 15-30 working days."
        
        return StatusResponse(
            reference_number=reference_number,
            success=True,
            message=message,
            estimated_completion_date=estimated_date,
            language=language
        )
    
    async def _build_required_actions_response(self, status_info: Dict[str, Any],
                                             language: str) -> StatusResponse:
        """Build required actions response."""
        reference_number = status_info['reference_number']
        actions_required = status_info.get('actions_required', [])
        
        if language == 'hi':
            if actions_required:
                message = f"आपकी शिकायत {reference_number} के लिए आवश्यक कार्रवाई:\n"
                for i, action in enumerate(actions_required, 1):
                    message += f"{i}. {action}\n"
            else:
                message = f"आपकी शिकायत {reference_number} के लिए फिलहाल कोई कार्रवाई की आवश्यकता नहीं है।"
        else:  # English
            if actions_required:
                message = f"Required actions for your grievance {reference_number}:\n"
                for i, action in enumerate(actions_required, 1):
                    message += f"{i}. {action}\n"
            else:
                message = f"No actions required from your side for grievance {reference_number} at this time."
        
        return StatusResponse(
            reference_number=reference_number,
            success=True,
            message=message,
            actions_required=actions_required,
            language=language
        )
    
    async def _build_contact_officer_response(self, status_info: Dict[str, Any],
                                            language: str) -> StatusResponse:
        """Build contact officer response."""
        reference_number = status_info['reference_number']
        assigned_officer = status_info.get('assigned_officer')
        department = status_info.get('department')
        
        if language == 'hi':
            if assigned_officer:
                message = f"आपकी शिकायत {reference_number} के लिए जिम्मेदार अधिकारी: {assigned_officer}"
                if department:
                    message += f"\nविभाग: {department}"
            else:
                message = f"आपकी शिकायत {reference_number} के लिए अभी तक कोई अधिकारी नियुक्त नहीं किया गया है।"
        else:  # English
            if assigned_officer:
                message = f"Officer assigned to your grievance {reference_number}: {assigned_officer}"
                if department:
                    message += f"\nDepartment: {department}"
            else:
                message = f"No officer has been assigned to your grievance {reference_number} yet."
        
        return StatusResponse(
            reference_number=reference_number,
            success=True,
            message=message,
            assigned_officer=assigned_officer,
            department=department,
            language=language
        )
    
    def _get_status_explanation(self, status: str, language: str,
                              explanation_level: StatusExplanationLevel) -> str:
        """Get human-readable status explanation."""
        explanations = self._status_explanations.get(language, self._status_explanations['en'])
        status_explanations = explanations.get(status, explanations.get('unknown', {}))
        
        if explanation_level == StatusExplanationLevel.SIMPLE:
            return status_explanations.get('simple', status)
        elif explanation_level == StatusExplanationLevel.COMPLETE:
            return status_explanations.get('complete', status_explanations.get('detailed', status))
        else:  # DETAILED
            return status_explanations.get('detailed', status)
    
    def _get_error_message(self, error_type: str, language: str) -> str:
        """Get error message in specified language."""
        error_messages = {
            'hi': {
                'invalid_reference': 'संदर्भ संख्या सही नहीं है। कृपया सही संदर्भ संख्या दें।',
                'not_found': 'इस संदर्भ संख्या के लिए कोई जानकारी नहीं मिली। कृपया संदर्भ संख्या की जांच करें।',
                'missing_reference': 'कृपया अपनी शिकायत की संदर्भ संख्या बताएं।',
                'system_error': 'तकनीकी समस्या के कारण स्थिति की जांच नहीं हो सकी। कृपया बाद में पुनः प्रयास करें।'
            },
            'en': {
                'invalid_reference': 'Invalid reference number. Please provide a valid reference number.',
                'not_found': 'No information found for this reference number. Please check the reference number.',
                'missing_reference': 'Please provide your grievance reference number.',
                'system_error': 'Unable to check status due to technical issues. Please try again later.'
            }
        }
        
        lang_messages = error_messages.get(language, error_messages['en'])
        return lang_messages.get(error_type, 'Unknown error occurred.')
    
    def _load_status_explanations(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Load status explanations in different languages."""
        return {
            'hi': {
                'pending': {
                    'simple': 'प्रतीक्षा में',
                    'detailed': 'आपकी शिकायत प्राप्त हुई है और प्रक्रिया की प्रतीक्षा में है',
                    'complete': 'आपकी शिकायत सफलतापूर्वक प्राप्त हुई है और अब यह प्रक्रिया की प्रतीक्षा में है। जल्द ही इसकी समीक्षा की जाएगी।'
                },
                'submitted': {
                    'simple': 'जमा की गई',
                    'detailed': 'आपकी शिकायत सरकारी पोर्टल पर जमा कर दी गई है',
                    'complete': 'आपकी शिकायत सफलतापूर्वक सरकारी पोर्टल पर जमा कर दी गई है। अब यह संबंधित विभाग को भेजी जाएगी।'
                },
                'acknowledged': {
                    'simple': 'स्वीकार की गई',
                    'detailed': 'आपकी शिकायत को संबंधित विभाग द्वारा स्वीकार कर लिया गया है',
                    'complete': 'आपकी शिकायत को संबंधित विभाग द्वारा स्वीकार कर लिया गया है और अब इसकी जांच शुरू की जाएगी।'
                },
                'in_progress': {
                    'simple': 'प्रगति में',
                    'detailed': 'आपकी शिकायत की जांच चल रही है',
                    'complete': 'आपकी शिकायत की सक्रिय रूप से जांच की जा रही है। संबंधित अधिकारी इस मामले पर काम कर रहे हैं।'
                },
                'under_review': {
                    'simple': 'समीक्षा में',
                    'detailed': 'आपकी शिकायत की समीक्षा की जा रही है',
                    'complete': 'आपकी शिकायत की विस्तृत समीक्षा की जा रही है। सभी तथ्यों और दस्तावेजों की जांच की जा रही है।'
                },
                'resolved': {
                    'simple': 'हल हो गई',
                    'detailed': 'आपकी शिकायत का समाधान हो गया है',
                    'complete': 'बधाई हो! आपकी शिकायत का सफलतापूर्वक समाधान हो गया है। समाधान की जानकारी आपको भेजी जा रही है।'
                },
                'rejected': {
                    'simple': 'अस्वीकार',
                    'detailed': 'आपकी शिकायत को अस्वीकार कर दिया गया है',
                    'complete': 'खेद है कि आपकी शिकायत को अस्वीकार कर दिया गया है। अस्वीकार के कारण की जानकारी आपको भेजी जा रही है।'
                },
                'unknown': {
                    'simple': 'अज्ञात',
                    'detailed': 'स्थिति की जानकारी उपलब्ध नहीं है',
                    'complete': 'वर्तमान में आपकी शिकायत की स्थिति की जानकारी उपलब्ध नहीं है। कृपया बाद में पुनः जांच करें।'
                }
            },
            'en': {
                'pending': {
                    'simple': 'Pending',
                    'detailed': 'Your grievance has been received and is awaiting processing',
                    'complete': 'Your grievance has been successfully received and is now awaiting processing. It will be reviewed shortly.'
                },
                'submitted': {
                    'simple': 'Submitted',
                    'detailed': 'Your grievance has been submitted to the government portal',
                    'complete': 'Your grievance has been successfully submitted to the government portal and will now be forwarded to the relevant department.'
                },
                'acknowledged': {
                    'simple': 'Acknowledged',
                    'detailed': 'Your grievance has been acknowledged by the relevant department',
                    'complete': 'Your grievance has been acknowledged by the relevant department and investigation will now begin.'
                },
                'in_progress': {
                    'simple': 'In Progress',
                    'detailed': 'Your grievance is being investigated',
                    'complete': 'Your grievance is being actively investigated. The concerned officers are working on your case.'
                },
                'under_review': {
                    'simple': 'Under Review',
                    'detailed': 'Your grievance is under review',
                    'complete': 'Your grievance is under detailed review. All facts and documents are being examined.'
                },
                'resolved': {
                    'simple': 'Resolved',
                    'detailed': 'Your grievance has been resolved',
                    'complete': 'Congratulations! Your grievance has been successfully resolved. Resolution details are being sent to you.'
                },
                'rejected': {
                    'simple': 'Rejected',
                    'detailed': 'Your grievance has been rejected',
                    'complete': 'We regret that your grievance has been rejected. Details about the rejection reason are being sent to you.'
                },
                'unknown': {
                    'simple': 'Unknown',
                    'detailed': 'Status information is not available',
                    'complete': 'Status information for your grievance is currently not available. Please check again later.'
                }
            }
        }