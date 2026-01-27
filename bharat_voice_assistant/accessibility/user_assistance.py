"""
User assistance system for confusion detection and help provision.

This module provides comprehensive user assistance including:
- Confusion detection and help offering
- Instruction repetition and additional assistance
- Adaptive response pacing based on user speaking patterns
- Context-aware help and guidance
- Progressive assistance levels
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from ..core.logging import get_logger
from ..core.exceptions import AccessibilityError


logger = get_logger(__name__)


class ConfusionLevel(Enum):
    """Levels of user confusion."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssistanceLevel(Enum):
    """Levels of assistance to provide."""
    MINIMAL = "minimal"      # Basic confirmation
    STANDARD = "standard"    # Normal help
    DETAILED = "detailed"    # Step-by-step guidance
    COMPREHENSIVE = "comprehensive"  # Full hand-holding


class UserState(Enum):
    """Current state of user interaction."""
    CONFIDENT = "confident"
    HESITANT = "hesitant"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    LEARNING = "learning"


@dataclass
class InteractionMetrics:
    """Metrics for tracking user interaction patterns."""
    response_time: float = 0.0
    pause_duration: float = 0.0
    repetition_requests: int = 0
    error_count: int = 0
    help_requests: int = 0
    successful_completions: int = 0
    speaking_pace: str = "normal"  # slow, normal, fast
    confidence_indicators: List[str] = field(default_factory=list)


@dataclass
class AssistanceContext:
    """Context for providing user assistance."""
    current_task: Optional[str] = None
    task_complexity: str = "medium"
    user_experience_level: str = "beginner"
    previous_interactions: int = 0
    time_spent_on_task: float = 0.0
    language_preference: str = "hindi"
    education_level: str = "basic"


@dataclass
class HelpContent:
    """Content for providing help to users."""
    title: str
    simple_explanation: str
    detailed_explanation: str
    step_by_step_guide: List[str]
    examples: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    tips: List[str] = field(default_factory=list)


class ConfusionDetector:
    """Detects user confusion based on interaction patterns."""
    
    def __init__(self):
        """Initialize confusion detector."""
        self.logger = get_logger(__name__)
        self._confusion_indicators = self._load_confusion_indicators()
    
    def _load_confusion_indicators(self) -> Dict[str, List[str]]:
        """Load indicators of user confusion."""
        return {
            "verbal_indicators": [
                # Hindi indicators
                "समझ नहीं आया", "क्या करना है", "कैसे करें", "मुझे नहीं पता",
                "फिर से बताओ", "समझाओ", "कन्फ्यूज हो गया", "गलत हो गया",
                "ये क्या है", "कहाँ है", "कैसे", "क्यों",
                
                # English indicators
                "don't understand", "what to do", "how to", "i don't know",
                "tell again", "explain", "confused", "went wrong",
                "what is this", "where is", "how", "why"
            ],
            "behavioral_indicators": [
                "long_pause", "repeated_attempts", "random_inputs",
                "help_requests", "back_navigation", "task_abandonment"
            ],
            "timing_indicators": [
                "slow_response", "very_fast_response", "irregular_timing",
                "extended_silence", "multiple_corrections"
            ]
        }
    
    def detect_confusion(
        self, 
        user_input: str, 
        metrics: InteractionMetrics,
        context: AssistanceContext
    ) -> Tuple[ConfusionLevel, List[str]]:
        """
        Detect user confusion level and reasons.
        
        Args:
            user_input: User's latest input
            metrics: Interaction metrics
            context: Current assistance context
            
        Returns:
            Tuple of confusion level and list of indicators
        """
        try:
            confusion_score = 0.0
            detected_indicators = []
            
            # Check verbal indicators
            verbal_score, verbal_indicators = self._check_verbal_indicators(user_input)
            confusion_score += verbal_score
            detected_indicators.extend(verbal_indicators)
            
            # Check behavioral indicators
            behavioral_score, behavioral_indicators = self._check_behavioral_indicators(metrics)
            confusion_score += behavioral_score
            detected_indicators.extend(behavioral_indicators)
            
            # Check timing indicators
            timing_score, timing_indicators = self._check_timing_indicators(metrics)
            confusion_score += timing_score
            detected_indicators.extend(timing_indicators)
            
            # Adjust score based on context
            confusion_score = self._adjust_for_context(confusion_score, context)
            
            # Determine confusion level
            confusion_level = self._score_to_level(confusion_score)
            
            self.logger.info(f"Confusion detected: {confusion_level.value} (score: {confusion_score:.2f})")
            
            return confusion_level, detected_indicators
            
        except Exception as e:
            self.logger.error(f"Failed to detect confusion: {e}")
            return ConfusionLevel.NONE, []
    
    def _check_verbal_indicators(self, user_input: str) -> Tuple[float, List[str]]:
        """Check for verbal indicators of confusion."""
        try:
            score = 0.0
            indicators = []
            
            user_input_lower = user_input.lower()
            
            for indicator in self._confusion_indicators["verbal_indicators"]:
                if indicator in user_input_lower:
                    score += 0.3
                    indicators.append(f"verbal: {indicator}")
            
            return min(score, 1.0), indicators
            
        except Exception as e:
            self.logger.warning(f"Failed to check verbal indicators: {e}")
            return 0.0, []
    
    def _check_behavioral_indicators(self, metrics: InteractionMetrics) -> Tuple[float, List[str]]:
        """Check for behavioral indicators of confusion."""
        try:
            score = 0.0
            indicators = []
            
            # High repetition requests
            if metrics.repetition_requests > 2:
                score += 0.4
                indicators.append("behavioral: high_repetition_requests")
            
            # High error count
            if metrics.error_count > 3:
                score += 0.3
                indicators.append("behavioral: high_error_count")
            
            # Multiple help requests
            if metrics.help_requests > 1:
                score += 0.2
                indicators.append("behavioral: multiple_help_requests")
            
            # Low success rate
            total_attempts = metrics.successful_completions + metrics.error_count
            if total_attempts > 0:
                success_rate = metrics.successful_completions / total_attempts
                if success_rate < 0.5:
                    score += 0.3
                    indicators.append("behavioral: low_success_rate")
            
            return min(score, 1.0), indicators
            
        except Exception as e:
            self.logger.warning(f"Failed to check behavioral indicators: {e}")
            return 0.0, []
    
    def _check_timing_indicators(self, metrics: InteractionMetrics) -> Tuple[float, List[str]]:
        """Check for timing indicators of confusion."""
        try:
            score = 0.0
            indicators = []
            
            # Very slow response (over 10 seconds)
            if metrics.response_time > 10.0:
                score += 0.3
                indicators.append("timing: slow_response")
            
            # Very fast response (under 1 second) - might indicate random input
            elif metrics.response_time < 1.0:
                score += 0.2
                indicators.append("timing: very_fast_response")
            
            # Long pauses
            if metrics.pause_duration > 5.0:
                score += 0.2
                indicators.append("timing: long_pause")
            
            return min(score, 1.0), indicators
            
        except Exception as e:
            self.logger.warning(f"Failed to check timing indicators: {e}")
            return 0.0, []
    
    def _adjust_for_context(self, base_score: float, context: AssistanceContext) -> float:
        """Adjust confusion score based on context."""
        try:
            adjusted_score = base_score
            
            # Adjust for user experience level
            if context.user_experience_level == "beginner":
                adjusted_score *= 1.2  # Beginners more likely to be confused
            elif context.user_experience_level == "expert":
                adjusted_score *= 0.8  # Experts less likely to be confused
            
            # Adjust for task complexity
            if context.task_complexity == "high":
                adjusted_score *= 1.1
            elif context.task_complexity == "low":
                adjusted_score *= 0.9
            
            # Adjust for time spent on task
            if context.time_spent_on_task > 300:  # More than 5 minutes
                adjusted_score *= 1.1
            
            return min(adjusted_score, 1.0)
            
        except Exception as e:
            self.logger.warning(f"Failed to adjust for context: {e}")
            return base_score
    
    def _score_to_level(self, score: float) -> ConfusionLevel:
        """Convert confusion score to level."""
        if score >= 0.8:
            return ConfusionLevel.CRITICAL
        elif score >= 0.6:
            return ConfusionLevel.HIGH
        elif score >= 0.4:
            return ConfusionLevel.MEDIUM
        elif score >= 0.2:
            return ConfusionLevel.LOW
        else:
            return ConfusionLevel.NONE


class HelpProvider:
    """Provides contextual help and assistance to users."""
    
    def __init__(self):
        """Initialize help provider."""
        self.logger = get_logger(__name__)
        self._help_content: Dict[str, Dict[str, HelpContent]] = {}
        self._load_help_content()
    
    def _load_help_content(self):
        """Load help content for different topics and languages."""
        # Hindi help content
        hindi_help = {
            "navigation": HelpContent(
                title="नेवीगेशन की मदद",
                simple_explanation="आप 'वापस जाओ', 'आगे बढ़ो', या 'घर जाओ' कह सकते हैं।",
                detailed_explanation="इस सिस्टम में आप आवाज के जरिए कहीं भी जा सकते हैं। अलग-अलग पेजों के बीच जाने के लिए सिंपल कमांड का इस्तेमाल करें।",
                step_by_step_guide=[
                    "पिछले पेज पर जाने के लिए 'वापस जाओ' कहें",
                    "अगले पेज पर जाने के लिए 'आगे बढ़ो' कहें",
                    "मुख्य पेज पर जाने के लिए 'घर जाओ' कहें"
                ],
                examples=["वापस जाओ", "आगे बढ़ो", "घर जाओ"],
                tips=["साफ-साफ बोलें", "एक समय में एक ही कमांड दें"]
            ),
            "complaint_filing": HelpContent(
                title="शिकायत दर्ज करने की मदद",
                simple_explanation="शिकायत दर्ज करने के लिए 'शिकायत करनी है' कहें।",
                detailed_explanation="आप अपनी समस्या के बारे में बताकर शिकायत दर्ज कर सकते हैं। सिस्टम आपको स्टेप बाई स्टेप गाइड करेगा।",
                step_by_step_guide=[
                    "'शिकायत करनी है' कहें",
                    "अपनी समस्या के बारे में बताएं",
                    "जरूरी जानकारी दें जब पूछा जाए",
                    "कन्फर्म करें कि सब कुछ सही है"
                ],
                examples=["बिजली नहीं आ रही", "पानी की समस्या है", "सड़क खराब है"],
                common_mistakes=["अधूरी जानकारी देना", "गलत डिटेल्स देना"],
                tips=["सभी जरूरी जानकारी तैयार रखें", "धैर्य रखें"]
            ),
            "scheme_search": HelpContent(
                title="योजना खोजने की मदद",
                simple_explanation="योजना खोजने के लिए 'योजना बताओ' कहें।",
                detailed_explanation="सरकारी योजनाओं की जानकारी पाने के लिए अपनी जरूरत या स्थिति बताएं।",
                step_by_step_guide=[
                    "'योजना बताओ' कहें",
                    "अपनी जरूरत या स्थिति बताएं",
                    "सुझाई गई योजनाओं को सुनें",
                    "जिस योजना में दिलचस्पी हो उसके बारे में और पूछें"
                ],
                examples=["किसान हूँ", "बुजुर्ग हूँ", "महिला हूँ"],
                tips=["अपनी सही उम्र और स्थिति बताएं", "सभी योजनाओं को ध्यान से सुनें"]
            )
        }
        
        # English help content
        english_help = {
            "navigation": HelpContent(
                title="Navigation Help",
                simple_explanation="You can say 'go back', 'go forward', or 'go home'.",
                detailed_explanation="In this system you can go anywhere using voice commands. Use simple commands to move between different pages.",
                step_by_step_guide=[
                    "Say 'go back' to go to previous page",
                    "Say 'go forward' to go to next page",
                    "Say 'go home' to go to main page"
                ],
                examples=["go back", "go forward", "go home"],
                tips=["Speak clearly", "Give one command at a time"]
            ),
            "complaint_filing": HelpContent(
                title="Complaint Filing Help",
                simple_explanation="To file complaint, say 'file complaint'.",
                detailed_explanation="You can file complaint by describing your problem. System will guide you step by step.",
                step_by_step_guide=[
                    "Say 'file complaint'",
                    "Describe your problem",
                    "Provide required information when asked",
                    "Confirm that everything is correct"
                ],
                examples=["no electricity", "water problem", "road is damaged"],
                common_mistakes=["Giving incomplete information", "Wrong details"],
                tips=["Keep all required information ready", "Be patient"]
            ),
            "scheme_search": HelpContent(
                title="Scheme Search Help",
                simple_explanation="To find schemes, say 'show schemes'.",
                detailed_explanation="To get information about government schemes, describe your need or situation.",
                step_by_step_guide=[
                    "Say 'show schemes'",
                    "Describe your need or situation",
                    "Listen to suggested schemes",
                    "Ask more about schemes you're interested in"
                ],
                examples=["I am farmer", "I am elderly", "I am woman"],
                tips=["Give your correct age and situation", "Listen to all schemes carefully"]
            )
        }
        
        self._help_content["hindi"] = hindi_help
        self._help_content["english"] = english_help
    
    def provide_help(
        self, 
        topic: str, 
        assistance_level: AssistanceLevel,
        context: AssistanceContext
    ) -> str:
        """
        Provide help for a specific topic.
        
        Args:
            topic: Help topic
            assistance_level: Level of assistance needed
            context: Current assistance context
            
        Returns:
            Help content formatted for the user
        """
        try:
            # Get help content for the language
            lang_help = self._help_content.get(context.language_preference, self._help_content["hindi"])
            help_content = lang_help.get(topic)
            
            if not help_content:
                return self._get_generic_help(context.language_preference)
            
            # Format help based on assistance level
            return self._format_help(help_content, assistance_level, context)
            
        except Exception as e:
            self.logger.error(f"Failed to provide help: {e}")
            return self._get_generic_help(context.language_preference)
    
    def _format_help(
        self, 
        help_content: HelpContent, 
        assistance_level: AssistanceLevel,
        context: AssistanceContext
    ) -> str:
        """Format help content based on assistance level."""
        try:
            if assistance_level == AssistanceLevel.MINIMAL:
                return help_content.simple_explanation
            
            elif assistance_level == AssistanceLevel.STANDARD:
                help_text = f"{help_content.title}\n\n{help_content.detailed_explanation}"
                if help_content.examples:
                    if context.language_preference == "hindi":
                        help_text += f"\n\nउदाहरण: {', '.join(help_content.examples[:3])}"
                    else:
                        help_text += f"\n\nExamples: {', '.join(help_content.examples[:3])}"
                return help_text
            
            elif assistance_level == AssistanceLevel.DETAILED:
                help_text = f"{help_content.title}\n\n{help_content.detailed_explanation}\n\n"
                
                if context.language_preference == "hindi":
                    help_text += "स्टेप बाई स्टेप गाइड:\n"
                else:
                    help_text += "Step by step guide:\n"
                
                for i, step in enumerate(help_content.step_by_step_guide, 1):
                    help_text += f"{i}. {step}\n"
                
                if help_content.examples:
                    if context.language_preference == "hindi":
                        help_text += f"\nउदाहरण: {', '.join(help_content.examples)}"
                    else:
                        help_text += f"\nExamples: {', '.join(help_content.examples)}"
                
                return help_text
            
            elif assistance_level == AssistanceLevel.COMPREHENSIVE:
                help_text = f"{help_content.title}\n\n{help_content.detailed_explanation}\n\n"
                
                if context.language_preference == "hindi":
                    help_text += "स्टेप बाई स्टेप गाइड:\n"
                else:
                    help_text += "Step by step guide:\n"
                
                for i, step in enumerate(help_content.step_by_step_guide, 1):
                    help_text += f"{i}. {step}\n"
                
                if help_content.examples:
                    if context.language_preference == "hindi":
                        help_text += f"\nउदाहरण: {', '.join(help_content.examples)}\n"
                    else:
                        help_text += f"\nExamples: {', '.join(help_content.examples)}\n"
                
                if help_content.common_mistakes:
                    if context.language_preference == "hindi":
                        help_text += f"\nआम गलतियां: {', '.join(help_content.common_mistakes)}\n"
                    else:
                        help_text += f"\nCommon mistakes: {', '.join(help_content.common_mistakes)}\n"
                
                if help_content.tips:
                    if context.language_preference == "hindi":
                        help_text += f"\nटिप्स: {', '.join(help_content.tips)}"
                    else:
                        help_text += f"\nTips: {', '.join(help_content.tips)}"
                
                return help_text
            
            return help_content.simple_explanation
            
        except Exception as e:
            self.logger.warning(f"Failed to format help: {e}")
            return help_content.simple_explanation
    
    def _get_generic_help(self, language: str) -> str:
        """Get generic help when specific help is not available."""
        if language == "hindi":
            return """मदद उपलब्ध है:
            
• नेवीगेशन के लिए: 'वापस जाओ', 'आगे बढ़ो', 'घर जाओ' कहें
• शिकायत के लिए: 'शिकायत करनी है' कहें
• योजना के लिए: 'योजना बताओ' कहें
• मदद के लिए: 'मदद चाहिए' कहें

कोई भी समस्या हो तो बताएं, मैं आपकी मदद करूंगा।"""
        else:
            return """Help is available:
            
• For navigation: Say 'go back', 'go forward', 'go home'
• For complaints: Say 'file complaint'
• For schemes: Say 'show schemes'
• For help: Say 'help'

If you have any problem, tell me and I will help you."""
    
    def get_available_topics(self, language: str = "hindi") -> List[str]:
        """Get list of available help topics."""
        try:
            lang_help = self._help_content.get(language, self._help_content["hindi"])
            return list(lang_help.keys())
            
        except Exception as e:
            self.logger.error(f"Failed to get available topics: {e}")
            return []


class UserAssistanceSystem:
    """Main user assistance system that coordinates confusion detection and help provision."""
    
    def __init__(self):
        """Initialize user assistance system."""
        self.logger = get_logger(__name__)
        self.confusion_detector = ConfusionDetector()
        self.help_provider = HelpProvider()
        self._user_sessions: Dict[str, Dict[str, Any]] = {}
        self._assistance_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def process_user_interaction(
        self, 
        user_id: str,
        user_input: str, 
        response_time: float,
        context: AssistanceContext
    ) -> Dict[str, Any]:
        """
        Process user interaction and provide assistance if needed.
        
        Args:
            user_id: Unique user identifier
            user_input: User's input
            response_time: Time taken to respond
            context: Current assistance context
            
        Returns:
            Assistance response with recommendations
        """
        try:
            # Get or create user session
            session = self._get_user_session(user_id)
            
            # Update interaction metrics
            metrics = self._update_metrics(session, user_input, response_time)
            
            # Detect confusion
            confusion_level, indicators = self.confusion_detector.detect_confusion(
                user_input, metrics, context
            )
            
            # Determine assistance needed
            assistance_response = self._determine_assistance(
                user_id, confusion_level, indicators, context
            )
            
            # Update session
            session["last_interaction"] = datetime.now()
            session["confusion_level"] = confusion_level.value
            session["total_interactions"] += 1
            
            # Log assistance provided
            self._log_assistance(user_id, confusion_level, assistance_response)
            
            return assistance_response
            
        except Exception as e:
            self.logger.error(f"Failed to process user interaction: {e}")
            return {
                "assistance_needed": False,
                "error": str(e)
            }
    
    def _get_user_session(self, user_id: str) -> Dict[str, Any]:
        """Get or create user session."""
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = {
                "created_at": datetime.now(),
                "last_interaction": datetime.now(),
                "total_interactions": 0,
                "confusion_level": ConfusionLevel.NONE.value,
                "assistance_level": AssistanceLevel.STANDARD.value,
                "metrics": InteractionMetrics(),
                "help_topics_accessed": [],
                "speaking_pace": "normal"
            }
        
        return self._user_sessions[user_id]
    
    def _update_metrics(
        self, 
        session: Dict[str, Any], 
        user_input: str, 
        response_time: float
    ) -> InteractionMetrics:
        """Update interaction metrics for the session."""
        try:
            metrics = session["metrics"]
            
            # Update response time
            metrics.response_time = response_time
            
            # Detect repetition requests
            repetition_keywords = [
                "फिर से", "दोबारा", "रिपीट", "again", "repeat", "once more"
            ]
            if any(keyword in user_input.lower() for keyword in repetition_keywords):
                metrics.repetition_requests += 1
            
            # Detect help requests
            help_keywords = [
                "मदद", "हेल्प", "सहायता", "help", "assist", "guide"
            ]
            if any(keyword in user_input.lower() for keyword in help_keywords):
                metrics.help_requests += 1
            
            # Detect speaking pace
            words_per_minute = len(user_input.split()) / max(response_time / 60, 0.1)
            if words_per_minute < 60:
                metrics.speaking_pace = "slow"
                session["speaking_pace"] = "slow"
            elif words_per_minute > 150:
                metrics.speaking_pace = "fast"
                session["speaking_pace"] = "fast"
            else:
                metrics.speaking_pace = "normal"
                session["speaking_pace"] = "normal"
            
            return metrics
            
        except Exception as e:
            self.logger.warning(f"Failed to update metrics: {e}")
            return session["metrics"]
    
    def _determine_assistance(
        self, 
        user_id: str,
        confusion_level: ConfusionLevel, 
        indicators: List[str],
        context: AssistanceContext
    ) -> Dict[str, Any]:
        """Determine what assistance to provide."""
        try:
            session = self._user_sessions[user_id]
            
            # Determine if assistance is needed
            assistance_needed = confusion_level != ConfusionLevel.NONE
            
            if not assistance_needed:
                return {
                    "assistance_needed": False,
                    "confusion_level": confusion_level.value,
                    "speaking_pace_adjustment": self._get_pace_adjustment(session["speaking_pace"])
                }
            
            # Determine assistance level
            assistance_level = self._determine_assistance_level(confusion_level, session)
            
            # Get appropriate help
            help_topic = self._determine_help_topic(context.current_task, indicators)
            help_content = self.help_provider.provide_help(help_topic, assistance_level, context)
            
            # Prepare assistance response
            response = {
                "assistance_needed": True,
                "confusion_level": confusion_level.value,
                "assistance_level": assistance_level.value,
                "help_topic": help_topic,
                "help_content": help_content,
                "indicators": indicators,
                "speaking_pace_adjustment": self._get_pace_adjustment(session["speaking_pace"]),
                "suggestions": self._get_suggestions(confusion_level, context)
            }
            
            # Add repetition if requested
            if "repetition_requests" in [i.split(":")[0] for i in indicators]:
                response["repeat_last_instruction"] = True
            
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to determine assistance: {e}")
            return {
                "assistance_needed": True,
                "error": str(e),
                "help_content": self.help_provider._get_generic_help(context.language_preference)
            }
    
    def _determine_assistance_level(
        self, 
        confusion_level: ConfusionLevel, 
        session: Dict[str, Any]
    ) -> AssistanceLevel:
        """Determine the appropriate level of assistance."""
        try:
            # Start with confusion level mapping
            if confusion_level == ConfusionLevel.CRITICAL:
                base_level = AssistanceLevel.COMPREHENSIVE
            elif confusion_level == ConfusionLevel.HIGH:
                base_level = AssistanceLevel.DETAILED
            elif confusion_level == ConfusionLevel.MEDIUM:
                base_level = AssistanceLevel.STANDARD
            else:
                base_level = AssistanceLevel.MINIMAL
            
            # Adjust based on user history
            if session["total_interactions"] < 3:
                # New users need more help
                if base_level == AssistanceLevel.MINIMAL:
                    base_level = AssistanceLevel.STANDARD
                elif base_level == AssistanceLevel.STANDARD:
                    base_level = AssistanceLevel.DETAILED
            
            # Adjust based on previous assistance effectiveness
            if len(session.get("help_topics_accessed", [])) > 3:
                # User has accessed help multiple times, might need comprehensive help
                if base_level in [AssistanceLevel.MINIMAL, AssistanceLevel.STANDARD]:
                    base_level = AssistanceLevel.DETAILED
            
            return base_level
            
        except Exception as e:
            self.logger.warning(f"Failed to determine assistance level: {e}")
            return AssistanceLevel.STANDARD
    
    def _determine_help_topic(self, current_task: Optional[str], indicators: List[str]) -> str:
        """Determine the most relevant help topic."""
        try:
            # Map current task to help topic
            task_topic_map = {
                "complaint_filing": "complaint_filing",
                "scheme_search": "scheme_search",
                "status_check": "navigation",
                "application": "complaint_filing"
            }
            
            if current_task and current_task in task_topic_map:
                return task_topic_map[current_task]
            
            # Determine from indicators
            if any("navigation" in indicator for indicator in indicators):
                return "navigation"
            elif any("complaint" in indicator or "शिकायत" in indicator for indicator in indicators):
                return "complaint_filing"
            elif any("scheme" in indicator or "योजना" in indicator for indicator in indicators):
                return "scheme_search"
            
            # Default to navigation help
            return "navigation"
            
        except Exception as e:
            self.logger.warning(f"Failed to determine help topic: {e}")
            return "navigation"
    
    def _get_pace_adjustment(self, speaking_pace: str) -> Dict[str, Any]:
        """Get speaking pace adjustment recommendations."""
        try:
            if speaking_pace == "slow":
                return {
                    "response_pace": "slow",
                    "pause_duration": 2.0,
                    "speech_rate": 0.8,
                    "message": "धीरे-धीरे बोल रहे हैं, मैं भी धीरे बोलूंगा।" if speaking_pace == "slow" else "Speaking slowly, I will also speak slowly."
                }
            elif speaking_pace == "fast":
                return {
                    "response_pace": "normal",
                    "pause_duration": 0.5,
                    "speech_rate": 1.0,
                    "message": "तेज बोल रहे हैं, कृपया धीरे बोलें।" if speaking_pace == "fast" else "Speaking fast, please speak slowly."
                }
            else:
                return {
                    "response_pace": "normal",
                    "pause_duration": 1.0,
                    "speech_rate": 1.0,
                    "message": ""
                }
                
        except Exception as e:
            self.logger.warning(f"Failed to get pace adjustment: {e}")
            return {"response_pace": "normal", "pause_duration": 1.0, "speech_rate": 1.0}
    
    def _get_suggestions(self, confusion_level: ConfusionLevel, context: AssistanceContext) -> List[str]:
        """Get suggestions based on confusion level."""
        try:
            if context.language_preference == "hindi":
                if confusion_level == ConfusionLevel.CRITICAL:
                    return [
                        "कृपया धीरे-धीरे बोलें",
                        "एक समय में एक ही काम करें",
                        "मदद चाहिए तो 'मदद चाहिए' कहें"
                    ]
                elif confusion_level == ConfusionLevel.HIGH:
                    return [
                        "फिर से कोशिश करें",
                        "सिंपल शब्दों में बताएं",
                        "मदद के लिए पूछें"
                    ]
                else:
                    return [
                        "साफ-साफ बोलें",
                        "धैर्य रखें"
                    ]
            else:
                if confusion_level == ConfusionLevel.CRITICAL:
                    return [
                        "Please speak slowly",
                        "Do one thing at a time",
                        "Say 'help' if you need assistance"
                    ]
                elif confusion_level == ConfusionLevel.HIGH:
                    return [
                        "Try again",
                        "Use simple words",
                        "Ask for help"
                    ]
                else:
                    return [
                        "Speak clearly",
                        "Be patient"
                    ]
                    
        except Exception as e:
            self.logger.warning(f"Failed to get suggestions: {e}")
            return []
    
    def _log_assistance(
        self, 
        user_id: str, 
        confusion_level: ConfusionLevel, 
        assistance_response: Dict[str, Any]
    ):
        """Log assistance provided for analytics."""
        try:
            if user_id not in self._assistance_history:
                self._assistance_history[user_id] = []
            
            log_entry = {
                "timestamp": datetime.now(),
                "confusion_level": confusion_level.value,
                "assistance_provided": assistance_response.get("assistance_needed", False),
                "help_topic": assistance_response.get("help_topic"),
                "assistance_level": assistance_response.get("assistance_level")
            }
            
            self._assistance_history[user_id].append(log_entry)
            
            # Keep only last 50 entries per user
            if len(self._assistance_history[user_id]) > 50:
                self._assistance_history[user_id] = self._assistance_history[user_id][-50:]
                
        except Exception as e:
            self.logger.warning(f"Failed to log assistance: {e}")
    
    def get_user_assistance_stats(self, user_id: str) -> Dict[str, Any]:
        """Get assistance statistics for a user."""
        try:
            if user_id not in self._assistance_history:
                return {"total_assistance": 0}
            
            history = self._assistance_history[user_id]
            
            stats = {
                "total_assistance": len(history),
                "confusion_levels": {},
                "help_topics": {},
                "recent_assistance": len([h for h in history if (datetime.now() - h["timestamp"]).hours < 24])
            }
            
            for entry in history:
                # Count confusion levels
                level = entry["confusion_level"]
                stats["confusion_levels"][level] = stats["confusion_levels"].get(level, 0) + 1
                
                # Count help topics
                topic = entry.get("help_topic")
                if topic:
                    stats["help_topics"][topic] = stats["help_topics"].get(topic, 0) + 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get user assistance stats: {e}")
            return {"error": str(e)}
    
    def provide_proactive_help(
        self, 
        user_id: str, 
        context: AssistanceContext
    ) -> Optional[str]:
        """Provide proactive help based on user patterns."""
        try:
            session = self._user_sessions.get(user_id)
            if not session:
                return None
            
            # Check if user has been struggling
            if session["total_interactions"] > 5:
                recent_confusion = session.get("confusion_level", "none")
                if recent_confusion in ["high", "critical"]:
                    if context.language_preference == "hindi":
                        return "लगता है आपको कुछ परेशानी हो रही है। क्या मैं आपकी मदद कर सकता हूँ?"
                    else:
                        return "It seems you're having some difficulty. Can I help you?"
            
            # Check if user is taking too long on a task
            if context.time_spent_on_task > 300:  # 5 minutes
                if context.language_preference == "hindi":
                    return "इस काम में काफी समय लग रहा है। क्या आपको मदद चाहिए?"
                else:
                    return "This task is taking quite some time. Do you need help?"
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to provide proactive help: {e}")
            return None