"""
Accessible error handling for user-friendly error explanations.

This module provides comprehensive error handling including:
- User-friendly error messages in simple language
- Context-aware error explanations
- Recovery suggestions and guidance
- Multi-language error support
- Error categorization and prioritization
"""

import traceback
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from ..core.logging import get_logger
from ..core.exceptions import AccessibilityError


logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"           # Minor issues, user can continue
    MEDIUM = "medium"     # Moderate issues, some functionality affected
    HIGH = "high"         # Major issues, significant functionality lost
    CRITICAL = "critical" # System-wide issues, service unavailable


class ErrorCategory(Enum):
    """Categories of errors."""
    NETWORK = "network"           # Internet/connectivity issues
    AUTHENTICATION = "authentication"  # Login/permission issues
    VALIDATION = "validation"     # Input validation errors
    SYSTEM = "system"            # Internal system errors
    INTEGRATION = "integration"   # Government system integration errors
    VOICE = "voice"              # Speech recognition/synthesis errors
    USER_INPUT = "user_input"    # User input related errors


@dataclass
class ErrorContext:
    """Context information for error handling."""
    user_language: str = "hindi"
    user_education_level: str = "basic"
    current_task: Optional[str] = None
    user_location: Optional[str] = None
    device_type: Optional[str] = None
    network_quality: Optional[str] = None


@dataclass
class ErrorExplanation:
    """User-friendly error explanation."""
    simple_message: str
    detailed_explanation: str
    recovery_steps: List[str]
    alternative_actions: List[str] = field(default_factory=list)
    contact_info: Optional[str] = None
    estimated_resolution_time: Optional[str] = None


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""
    error_id: str
    timestamp: datetime
    category: ErrorCategory
    severity: ErrorSeverity
    original_error: str
    user_explanation: ErrorExplanation
    context: ErrorContext
    resolved: bool = False
    resolution_time: Optional[datetime] = None


class AccessibleErrorHandler:
    """Handles errors in an accessible, user-friendly manner."""
    
    def __init__(self):
        """Initialize the accessible error handler."""
        self.logger = get_logger(__name__)
        self._error_templates: Dict[str, Dict[str, Dict[str, str]]] = {}
        self._error_history: List[ErrorRecord] = []
        self._max_history = 100
        self._load_error_templates()
    
    def _load_error_templates(self):
        """Load error message templates for different languages."""
        # Hindi error templates
        hindi_templates = {
            ErrorCategory.NETWORK.value: {
                "simple": "इंटरनेट की समस्या है।",
                "detailed": "आपका इंटरनेट कनेक्शन धीमा है या काम नहीं कर रहा।",
                "recovery": [
                    "अपना वाई-फाई या मोबाइल डेटा चेक करें",
                    "फोन को रीस्टार्ट करें",
                    "थोड़ी देर बाद फिर कोशिश करें"
                ],
                "alternatives": [
                    "ऑफलाइन मोड में काम करें",
                    "बाद में फिर कोशिश करें"
                ]
            },
            ErrorCategory.AUTHENTICATION.value: {
                "simple": "लॉगिन की समस्या है।",
                "detailed": "आपकी पहचान की जांच में समस्या हुई है।",
                "recovery": [
                    "अपना फोन नंबर या आधार नंबर चेक करें",
                    "OTP फिर से मंगवाएं",
                    "कुछ देर बाद कोशिश करें"
                ],
                "alternatives": [
                    "दूसरे तरीके से लॉगिन करें",
                    "हेल्पलाइन पर कॉल करें"
                ]
            },
            ErrorCategory.VALIDATION.value: {
                "simple": "कुछ जानकारी गलत है।",
                "detailed": "आपने जो जानकारी दी है वो सही नहीं है।",
                "recovery": [
                    "अपनी जानकारी दोबारा चेक करें",
                    "सही स्पेलिंग और नंबर डालें",
                    "जरूरी फील्ड भरना न भूलें"
                ],
                "alternatives": [
                    "मदद लेकर फिर भरें",
                    "किसी और से पूछकर करें"
                ]
            },
            ErrorCategory.SYSTEM.value: {
                "simple": "सिस्टम में कुछ समस्या है।",
                "detailed": "हमारे सिस्टम में तकनीकी समस्या हुई है।",
                "recovery": [
                    "कुछ मिनट बाद फिर कोशिश करें",
                    "पेज को रिफ्रेश करें",
                    "ऐप को बंद करके फिर खोलें"
                ],
                "alternatives": [
                    "हेल्पलाइन पर कॉल करें",
                    "सरकारी ऑफिस में जाएं"
                ]
            },
            ErrorCategory.INTEGRATION.value: {
                "simple": "सरकारी वेबसाइट से जुड़ने में समस्या।",
                "detailed": "सरकारी सिस्टम अभी काम नहीं कर रहा या बहुत धीमा है।",
                "recovery": [
                    "थोड़ी देर बाद कोशिश करें",
                    "दिन के दूसरे समय में कोशिश करें",
                    "सप्ताहांत में कोशिश करें"
                ],
                "alternatives": [
                    "सीधे सरकारी ऑफिस जाएं",
                    "हेल्पलाइन नंबर पर कॉल करें"
                ]
            },
            ErrorCategory.VOICE.value: {
                "simple": "आवाज की समस्या है।",
                "detailed": "आपकी आवाज साफ नहीं सुनाई दे रही या समझ नहीं आ रही।",
                "recovery": [
                    "शांत जगह पर जाकर बोलें",
                    "माइक के पास आकर बोलें",
                    "धीरे-धीरे और साफ बोलें"
                ],
                "alternatives": [
                    "टाइप करके लिखें",
                    "किसी और से मदद लें"
                ]
            },
            ErrorCategory.USER_INPUT.value: {
                "simple": "आपकी जानकारी में कुछ गलती है।",
                "detailed": "जो जानकारी आपने दी है वो पूरी नहीं है या गलत है।",
                "recovery": [
                    "सभी जरूरी जानकारी भरें",
                    "सही फॉर्मेट में जानकारी दें",
                    "नंबर और तारीख सही से लिखें"
                ],
                "alternatives": [
                    "किसी से मदद लेकर भरें",
                    "बाद में फिर कोशिश करें"
                ]
            }
        }
        
        # English error templates
        english_templates = {
            ErrorCategory.NETWORK.value: {
                "simple": "Internet problem.",
                "detailed": "Your internet connection is slow or not working.",
                "recovery": [
                    "Check your WiFi or mobile data",
                    "Restart your phone",
                    "Try again after some time"
                ],
                "alternatives": [
                    "Work in offline mode",
                    "Try again later"
                ]
            },
            ErrorCategory.AUTHENTICATION.value: {
                "simple": "Login problem.",
                "detailed": "There was a problem verifying your identity.",
                "recovery": [
                    "Check your phone number or Aadhaar number",
                    "Request OTP again",
                    "Try after some time"
                ],
                "alternatives": [
                    "Login using different method",
                    "Call helpline"
                ]
            },
            ErrorCategory.VALIDATION.value: {
                "simple": "Some information is wrong.",
                "detailed": "The information you provided is not correct.",
                "recovery": [
                    "Check your information again",
                    "Enter correct spelling and numbers",
                    "Don't forget to fill required fields"
                ],
                "alternatives": [
                    "Get help and fill again",
                    "Ask someone else to help"
                ]
            },
            ErrorCategory.SYSTEM.value: {
                "simple": "System problem.",
                "detailed": "There's a technical problem with our system.",
                "recovery": [
                    "Try again after few minutes",
                    "Refresh the page",
                    "Close and reopen the app"
                ],
                "alternatives": [
                    "Call helpline",
                    "Visit government office"
                ]
            },
            ErrorCategory.INTEGRATION.value: {
                "simple": "Problem connecting to government website.",
                "detailed": "Government system is not working or very slow right now.",
                "recovery": [
                    "Try after some time",
                    "Try at different time of day",
                    "Try on weekend"
                ],
                "alternatives": [
                    "Visit government office directly",
                    "Call helpline number"
                ]
            },
            ErrorCategory.VOICE.value: {
                "simple": "Voice problem.",
                "detailed": "Your voice is not clear or not understood.",
                "recovery": [
                    "Go to quiet place and speak",
                    "Come closer to microphone",
                    "Speak slowly and clearly"
                ],
                "alternatives": [
                    "Type instead of speaking",
                    "Get help from someone"
                ]
            },
            ErrorCategory.USER_INPUT.value: {
                "simple": "Problem with your information.",
                "detailed": "The information you provided is incomplete or wrong.",
                "recovery": [
                    "Fill all required information",
                    "Give information in correct format",
                    "Write numbers and dates correctly"
                ],
                "alternatives": [
                    "Get help to fill",
                    "Try again later"
                ]
            }
        }
        
        self._error_templates["hindi"] = hindi_templates
        self._error_templates["english"] = english_templates
    
    def handle_error(
        self, 
        error: Exception, 
        context: ErrorContext,
        custom_message: Optional[str] = None
    ) -> ErrorExplanation:
        """
        Handle an error and provide user-friendly explanation.
        
        Args:
            error: The exception that occurred
            context: Context information for error handling
            custom_message: Custom error message if available
            
        Returns:
            User-friendly error explanation
        """
        try:
            # Categorize the error
            category = self._categorize_error(error)
            severity = self._determine_severity(error, category)
            
            # Generate user-friendly explanation
            explanation = self._generate_explanation(
                error, category, severity, context, custom_message
            )
            
            # Record the error
            error_record = ErrorRecord(
                error_id=self._generate_error_id(),
                timestamp=datetime.now(),
                category=category,
                severity=severity,
                original_error=str(error),
                user_explanation=explanation,
                context=context
            )
            
            self._add_to_history(error_record)
            
            # Log the error
            self.logger.error(
                f"Error handled: {category.value} - {severity.value} - {str(error)}",
                extra={"error_id": error_record.error_id}
            )
            
            return explanation
            
        except Exception as e:
            self.logger.critical(f"Failed to handle error: {e}")
            # Return basic fallback explanation
            return self._get_fallback_explanation(context.user_language)
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize the error based on its type and message."""
        try:
            error_str = str(error).lower()
            error_type = type(error).__name__.lower()
            
            # Network related errors
            if any(keyword in error_str for keyword in [
                "network", "connection", "timeout", "unreachable", 
                "dns", "socket", "http", "ssl", "certificate"
            ]):
                return ErrorCategory.NETWORK
            
            # Authentication errors
            if any(keyword in error_str for keyword in [
                "auth", "login", "permission", "unauthorized", "forbidden",
                "token", "credential", "access denied"
            ]):
                return ErrorCategory.AUTHENTICATION
            
            # Validation errors
            if any(keyword in error_str for keyword in [
                "validation", "invalid", "format", "required", "missing",
                "constraint", "length", "pattern"
            ]) or "validationerror" in error_type:
                return ErrorCategory.VALIDATION
            
            # Integration errors
            if any(keyword in error_str for keyword in [
                "api", "service", "integration", "external", "government",
                "portal", "endpoint"
            ]):
                return ErrorCategory.INTEGRATION
            
            # Voice processing errors
            if any(keyword in error_str for keyword in [
                "speech", "voice", "audio", "recognition", "synthesis",
                "transcribe", "polly", "microphone"
            ]):
                return ErrorCategory.VOICE
            
            # User input errors
            if any(keyword in error_str for keyword in [
                "input", "parameter", "argument", "value", "data"
            ]):
                return ErrorCategory.USER_INPUT
            
            # Default to system error
            return ErrorCategory.SYSTEM
            
        except Exception as e:
            self.logger.warning(f"Failed to categorize error: {e}")
            return ErrorCategory.SYSTEM
    
    def _determine_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Determine the severity of the error."""
        try:
            error_str = str(error).lower()
            
            # Critical errors
            if any(keyword in error_str for keyword in [
                "critical", "fatal", "crash", "system down", "unavailable"
            ]):
                return ErrorSeverity.CRITICAL
            
            # High severity errors
            if category in [ErrorCategory.AUTHENTICATION, ErrorCategory.SYSTEM]:
                return ErrorSeverity.HIGH
            
            # Medium severity errors
            if category in [ErrorCategory.INTEGRATION, ErrorCategory.NETWORK]:
                return ErrorSeverity.MEDIUM
            
            # Low severity errors
            return ErrorSeverity.LOW
            
        except Exception as e:
            self.logger.warning(f"Failed to determine severity: {e}")
            return ErrorSeverity.MEDIUM
    
    def _generate_explanation(
        self, 
        error: Exception, 
        category: ErrorCategory, 
        severity: ErrorSeverity,
        context: ErrorContext,
        custom_message: Optional[str]
    ) -> ErrorExplanation:
        """Generate user-friendly error explanation."""
        try:
            # Get templates for the language
            templates = self._error_templates.get(context.user_language, {})
            category_template = templates.get(category.value, {})
            
            # Use custom message if provided, otherwise use template
            if custom_message:
                simple_message = custom_message
                detailed_explanation = custom_message
            else:
                simple_message = category_template.get("simple", "कुछ समस्या हुई है।" if context.user_language == "hindi" else "There was a problem.")
                detailed_explanation = category_template.get("detailed", simple_message)
            
            # Get recovery steps
            recovery_steps = category_template.get("recovery", [])
            alternative_actions = category_template.get("alternatives", [])
            
            # Add context-specific recovery steps
            recovery_steps = self._add_contextual_recovery_steps(
                recovery_steps, category, context
            )
            
            # Add contact information for high severity errors
            contact_info = None
            if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                contact_info = self._get_contact_information(context.user_language)
            
            # Estimate resolution time
            estimated_time = self._estimate_resolution_time(category, severity, context)
            
            return ErrorExplanation(
                simple_message=simple_message,
                detailed_explanation=detailed_explanation,
                recovery_steps=recovery_steps,
                alternative_actions=alternative_actions,
                contact_info=contact_info,
                estimated_resolution_time=estimated_time
            )
            
        except Exception as e:
            self.logger.error(f"Failed to generate explanation: {e}")
            return self._get_fallback_explanation(context.user_language)
    
    def _add_contextual_recovery_steps(
        self, 
        base_steps: List[str], 
        category: ErrorCategory, 
        context: ErrorContext
    ) -> List[str]:
        """Add context-specific recovery steps."""
        try:
            contextual_steps = base_steps.copy()
            
            # Add network-specific steps based on network quality
            if category == ErrorCategory.NETWORK and context.network_quality == "poor":
                if context.user_language == "hindi":
                    contextual_steps.append("बेहतर नेटवर्क वाली जगह जाएं")
                else:
                    contextual_steps.append("Go to place with better network")
            
            # Add device-specific steps
            if context.device_type == "mobile":
                if context.user_language == "hindi":
                    contextual_steps.append("फोन को रीस्टार्ट करें")
                else:
                    contextual_steps.append("Restart your phone")
            
            # Add location-specific steps
            if context.user_location and category == ErrorCategory.INTEGRATION:
                if context.user_language == "hindi":
                    contextual_steps.append(f"अपने {context.user_location} के सरकारी ऑफिस में जाएं")
                else:
                    contextual_steps.append(f"Visit government office in {context.user_location}")
            
            return contextual_steps
            
        except Exception as e:
            self.logger.warning(f"Failed to add contextual recovery steps: {e}")
            return base_steps
    
    def _get_contact_information(self, language: str) -> str:
        """Get contact information for help."""
        try:
            if language == "hindi":
                return "मदद के लिए हेल्पलाइन: 1800-XXX-XXXX या support@bharatvoice.gov.in पर ईमेल करें"
            else:
                return "For help call helpline: 1800-XXX-XXXX or email support@bharatvoice.gov.in"
                
        except Exception as e:
            self.logger.warning(f"Failed to get contact information: {e}")
            return ""
    
    def _estimate_resolution_time(
        self, 
        category: ErrorCategory, 
        severity: ErrorSeverity, 
        context: ErrorContext
    ) -> str:
        """Estimate resolution time for the error."""
        try:
            if severity == ErrorSeverity.CRITICAL:
                time_estimate = "24 घंटे" if context.user_language == "hindi" else "24 hours"
            elif severity == ErrorSeverity.HIGH:
                time_estimate = "2-4 घंटे" if context.user_language == "hindi" else "2-4 hours"
            elif category == ErrorCategory.NETWORK:
                time_estimate = "कुछ मिनट" if context.user_language == "hindi" else "few minutes"
            elif category == ErrorCategory.INTEGRATION:
                time_estimate = "1-2 घंटे" if context.user_language == "hindi" else "1-2 hours"
            else:
                time_estimate = "30 मिनट" if context.user_language == "hindi" else "30 minutes"
            
            return time_estimate
            
        except Exception as e:
            self.logger.warning(f"Failed to estimate resolution time: {e}")
            return ""
    
    def _get_fallback_explanation(self, language: str) -> ErrorExplanation:
        """Get fallback explanation when error handling fails."""
        if language == "hindi":
            return ErrorExplanation(
                simple_message="कुछ समस्या हुई है।",
                detailed_explanation="तकनीकी समस्या के कारण काम नहीं हो पा रहा।",
                recovery_steps=["कुछ देर बाद फिर कोशिश करें", "हेल्पलाइन पर कॉल करें"],
                alternative_actions=["सरकारी ऑफिस में जाएं"]
            )
        else:
            return ErrorExplanation(
                simple_message="There was a problem.",
                detailed_explanation="Work cannot be done due to technical problem.",
                recovery_steps=["Try again after some time", "Call helpline"],
                alternative_actions=["Visit government office"]
            )
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID."""
        import uuid
        return f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    
    def _add_to_history(self, error_record: ErrorRecord):
        """Add error record to history."""
        try:
            self._error_history.append(error_record)
            if len(self._error_history) > self._max_history:
                self._error_history.pop(0)
                
        except Exception as e:
            self.logger.warning(f"Failed to add error to history: {e}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        try:
            if not self._error_history:
                return {"total_errors": 0}
            
            stats = {
                "total_errors": len(self._error_history),
                "by_category": {},
                "by_severity": {},
                "recent_errors": len([e for e in self._error_history if (datetime.now() - e.timestamp).hours < 24])
            }
            
            for error in self._error_history:
                # Count by category
                category = error.category.value
                stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
                
                # Count by severity
                severity = error.severity.value
                stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get error statistics: {e}")
            return {"error": "Statistics unavailable"}


class UserFriendlyErrors:
    """Provides user-friendly error interface for the voice assistant."""
    
    def __init__(self):
        """Initialize user-friendly errors interface."""
        self.logger = get_logger(__name__)
        self.error_handler = AccessibleErrorHandler()
    
    def explain_error(
        self, 
        error: Exception, 
        user_profile: Dict[str, Any],
        current_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Explain error in user-friendly language.
        
        Args:
            error: The exception that occurred
            user_profile: User profile information
            current_context: Current conversation context
            
        Returns:
            User-friendly error explanation text
        """
        try:
            # Create error context
            context = ErrorContext(
                user_language=user_profile.get("preferred_language", "hindi"),
                user_education_level=user_profile.get("education_level", "basic"),
                current_task=current_context.get("current_task") if current_context else None,
                user_location=user_profile.get("location"),
                device_type=user_profile.get("device_type", "mobile"),
                network_quality=current_context.get("network_quality") if current_context else None
            )
            
            # Handle the error
            explanation = self.error_handler.handle_error(error, context)
            
            # Format the explanation for voice output
            return self._format_for_voice(explanation, context.user_language)
            
        except Exception as e:
            self.logger.error(f"Failed to explain error: {e}")
            # Return basic error message
            if user_profile.get("preferred_language") == "hindi":
                return "माफ करें, कुछ समस्या हुई है। कृपया फिर से कोशिश करें।"
            else:
                return "Sorry, there was a problem. Please try again."
    
    def _format_for_voice(self, explanation: ErrorExplanation, language: str) -> str:
        """Format error explanation for voice output."""
        try:
            # Start with simple message
            voice_text = explanation.simple_message + " "
            
            # Add detailed explanation
            voice_text += explanation.detailed_explanation + " "
            
            # Add recovery steps
            if explanation.recovery_steps:
                if language == "hindi":
                    voice_text += "आप ये कर सकते हैं: "
                else:
                    voice_text += "You can do this: "
                
                for i, step in enumerate(explanation.recovery_steps[:3], 1):  # Limit to 3 steps for voice
                    voice_text += f"{i}. {step}. "
            
            # Add contact info for serious errors
            if explanation.contact_info:
                voice_text += explanation.contact_info
            
            return voice_text.strip()
            
        except Exception as e:
            self.logger.warning(f"Failed to format for voice: {e}")
            return explanation.simple_message
    
    def get_recovery_guidance(
        self, 
        error_category: str, 
        language: str = "hindi"
    ) -> List[str]:
        """Get recovery guidance for specific error category."""
        try:
            templates = self.error_handler._error_templates.get(language, {})
            category_template = templates.get(error_category, {})
            return category_template.get("recovery", [])
            
        except Exception as e:
            self.logger.error(f"Failed to get recovery guidance: {e}")
            return []
    
    def report_error_resolved(self, error_id: str):
        """Report that an error has been resolved."""
        try:
            for error_record in self.error_handler._error_history:
                if error_record.error_id == error_id:
                    error_record.resolved = True
                    error_record.resolution_time = datetime.now()
                    self.logger.info(f"Error {error_id} marked as resolved")
                    break
                    
        except Exception as e:
            self.logger.warning(f"Failed to report error resolved: {e}")
    
    def get_common_errors_help(self, language: str = "hindi") -> str:
        """Get help text for common errors."""
        try:
            if language == "hindi":
                help_text = "आम समस्याएं और उनके समाधान:\n\n"
                help_text += "1. इंटरनेट की समस्या - अपना कनेक्शन चेक करें\n"
                help_text += "2. लॉगिन की समस्या - OTP फिर से मंगवाएं\n"
                help_text += "3. आवाज की समस्या - शांत जगह पर बोलें\n"
                help_text += "4. सिस्टम की समस्या - कुछ देर बाद कोशिश करें\n\n"
                help_text += "मदद के लिए हेल्पलाइन: 1800-XXX-XXXX"
            else:
                help_text = "Common problems and solutions:\n\n"
                help_text += "1. Internet problem - Check your connection\n"
                help_text += "2. Login problem - Request OTP again\n"
                help_text += "3. Voice problem - Speak in quiet place\n"
                help_text += "4. System problem - Try after some time\n\n"
                help_text += "For help call: 1800-XXX-XXXX"
            
            return help_text
            
        except Exception as e:
            self.logger.error(f"Failed to get common errors help: {e}")
            return "मदद उपलब्ध नहीं है।" if language == "hindi" else "Help not available."