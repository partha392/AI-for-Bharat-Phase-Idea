"""
Consistent command patterns for accessibility and usability.

This module provides comprehensive command pattern management including:
- Consistent voice commands across all features
- Easy-to-remember command structures
- Pattern recognition and suggestion
- Command validation and correction
- Multi-language command support
"""

import re
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from ..core.logging import get_logger
from ..core.exceptions import AccessibilityError


logger = get_logger(__name__)


class CommandCategory(Enum):
    """Categories of voice commands."""
    NAVIGATION = "navigation"
    INFORMATION = "information"
    ACTION = "action"
    HELP = "help"
    CONFIRMATION = "confirmation"
    CORRECTION = "correction"


class CommandComplexity(Enum):
    """Command complexity levels."""
    SIMPLE = "simple"      # Single word commands
    MODERATE = "moderate"  # 2-3 word commands
    COMPLEX = "complex"    # Multi-phrase commands


@dataclass
class CommandPattern:
    """Represents a voice command pattern."""
    pattern: str
    category: CommandCategory
    complexity: CommandComplexity
    language: str
    alternatives: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    description: str = ""
    response_template: str = ""
    requires_confirmation: bool = False


@dataclass
class CommandMatch:
    """Result of command pattern matching."""
    pattern: CommandPattern
    confidence: float
    matched_text: str
    extracted_parameters: Dict[str, Any] = field(default_factory=dict)


class CommandPatternManager:
    """Manages consistent command patterns for accessibility."""
    
    def __init__(self):
        """Initialize the command pattern manager."""
        self.logger = get_logger(__name__)
        self._command_patterns: Dict[str, List[CommandPattern]] = defaultdict(list)
        self._command_index: Dict[str, Set[str]] = defaultdict(set)
        self._load_default_command_patterns()
    
    def _load_default_command_patterns(self):
        """Load default command patterns for different languages."""
        # Hindi command patterns
        hindi_patterns = [
            # Navigation commands
            CommandPattern(
                pattern="वापस जाओ|पीछे जाओ|वापस",
                category=CommandCategory.NAVIGATION,
                complexity=CommandComplexity.SIMPLE,
                language="hindi",
                alternatives=["पीछे", "वापस चलो", "पहले वाला"],
                examples=["वापस जाओ", "पीछे जाओ"],
                description="पिछले पेज पर जाने के लिए",
                response_template="ठीक है, वापस जा रहे हैं।"
            ),
            CommandPattern(
                pattern="आगे बढ़ो|आगे जाओ|अगला",
                category=CommandCategory.NAVIGATION,
                complexity=CommandComplexity.SIMPLE,
                language="hindi",
                alternatives=["आगे", "अगला पेज", "आगे चलो"],
                examples=["आगे बढ़ो", "अगला"],
                description="अगले पेज पर जाने के लिए",
                response_template="ठीक है, आगे बढ़ रहे हैं।"
            ),
            CommandPattern(
                pattern="घर जाओ|मुख्य पेज|होम",
                category=CommandCategory.NAVIGATION,
                complexity=CommandComplexity.SIMPLE,
                language="hindi",
                alternatives=["घर", "शुरुआत", "मुख्य मेन्यू"],
                examples=["घर जाओ", "मुख्य पेज"],
                description="मुख्य पेज पर जाने के लिए",
                response_template="मुख्य पेज पर जा रहे हैं।"
            ),
            
            # Information commands
            CommandPattern(
                pattern="स्थिति बताओ|क्या हाल है|स्टेटस",
                category=CommandCategory.INFORMATION,
                complexity=CommandComplexity.SIMPLE,
                language="hindi",
                alternatives=["हालत बताओ", "कैसा चल रहा है", "अपडेट दो"],
                examples=["स्थिति बताओ", "क्या हाल है"],
                description="आपकी शिकायत की स्थिति जानने के लिए",
                response_template="आपकी स्थिति की जानकारी ला रहे हैं।"
            ),
            CommandPattern(
                pattern="योजना बताओ|स्कीम दिखाओ|सरकारी योजना",
                category=CommandCategory.INFORMATION,
                complexity=CommandComplexity.MODERATE,
                language="hindi",
                alternatives=["योजनाएं", "सरकारी मदद", "स्कीम"],
                examples=["योजना बताओ", "सरकारी योजना"],
                description="सरकारी योजनाओं की जानकारी के लिए",
                response_template="आपके लिए योजनाएं ढूंढ रहे हैं।"
            ),
            CommandPattern(
                pattern="मदद चाहिए|हेल्प|सहायता",
                category=CommandCategory.HELP,
                complexity=CommandComplexity.SIMPLE,
                language="hindi",
                alternatives=["मदद करो", "गाइड करो", "बताओ कैसे करें"],
                examples=["मदद चाहिए", "हेल्प"],
                description="मदद और गाइडेंस के लिए",
                response_template="मैं आपकी मदद करूंगा। क्या चाहिए?"
            ),
            
            # Action commands
            CommandPattern(
                pattern="शिकायत करनी है|कंप्लेंट करना है|समस्या है",
                category=CommandCategory.ACTION,
                complexity=CommandComplexity.MODERATE,
                language="hindi",
                alternatives=["शिकायत दर्ज करो", "कंप्लेंट फाइल करो", "समस्या बताना है"],
                examples=["शिकायत करनी है", "समस्या है"],
                description="नई शिकायत दर्ज करने के लिए",
                response_template="शिकायत दर्ज करने में मदद करूंगा।",
                requires_confirmation=True
            ),
            CommandPattern(
                pattern="आवेदन करना है|अप्लाई करना है|फॉर्म भरना है",
                category=CommandCategory.ACTION,
                complexity=CommandComplexity.MODERATE,
                language="hindi",
                alternatives=["एप्लीकेशन करनी है", "फॉर्म जमा करना है"],
                examples=["आवेदन करना है", "फॉर्म भरना है"],
                description="नया आवेदन करने के लिए",
                response_template="आवेदन करने में मदद करूंगा।",
                requires_confirmation=True
            ),
            
            # Confirmation commands
            CommandPattern(
                pattern="हाँ|ठीक है|सही है|जी हाँ",
                category=CommandCategory.CONFIRMATION,
                complexity=CommandComplexity.SIMPLE,
                language="hindi",
                alternatives=["बिल्कुल", "सही", "ओके"],
                examples=["हाँ", "ठीक है"],
                description="हाँ कहने के लिए",
                response_template="समझ गया।"
            ),
            CommandPattern(
                pattern="नहीं|गलत है|नहीं चाहिए",
                category=CommandCategory.CONFIRMATION,
                complexity=CommandComplexity.SIMPLE,
                language="hindi",
                alternatives=["ना", "रद्द करो", "नहीं करना"],
                examples=["नहीं", "गलत है"],
                description="ना कहने के लिए",
                response_template="ठीक है, रद्द कर रहे हैं।"
            ),
            
            # Correction commands
            CommandPattern(
                pattern="फिर से बोलो|दोबारा कहो|रिपीट करो",
                category=CommandCategory.CORRECTION,
                complexity=CommandComplexity.MODERATE,
                language="hindi",
                alternatives=["फिर से", "दोहराओ", "एक बार और"],
                examples=["फिर से बोलो", "दोबारा कहो"],
                description="दोबारा सुनने के लिए",
                response_template="फिर से बता रहा हूँ।"
            ),
            CommandPattern(
                pattern="गलत है|सही नहीं है|बदलो",
                category=CommandCategory.CORRECTION,
                complexity=CommandComplexity.SIMPLE,
                language="hindi",
                alternatives=["ठीक नहीं", "चेंज करो", "सुधारो"],
                examples=["गलत है", "बदलो"],
                description="कुछ सुधारने के लिए",
                response_template="ठीक है, सुधार रहे हैं।"
            ),
        ]
        
        # English command patterns
        english_patterns = [
            # Navigation commands
            CommandPattern(
                pattern="go back|back|previous",
                category=CommandCategory.NAVIGATION,
                complexity=CommandComplexity.SIMPLE,
                language="english",
                alternatives=["return", "go to previous", "back page"],
                examples=["go back", "back"],
                description="to go to previous page",
                response_template="Going back."
            ),
            CommandPattern(
                pattern="go forward|next|forward",
                category=CommandCategory.NAVIGATION,
                complexity=CommandComplexity.SIMPLE,
                language="english",
                alternatives=["continue", "next page", "proceed"],
                examples=["go forward", "next"],
                description="to go to next page",
                response_template="Going forward."
            ),
            CommandPattern(
                pattern="go home|home|main page",
                category=CommandCategory.NAVIGATION,
                complexity=CommandComplexity.SIMPLE,
                language="english",
                alternatives=["main menu", "start", "beginning"],
                examples=["go home", "home"],
                description="to go to main page",
                response_template="Going to home page."
            ),
            
            # Information commands
            CommandPattern(
                pattern="check status|what's the status|status",
                category=CommandCategory.INFORMATION,
                complexity=CommandComplexity.MODERATE,
                language="english",
                alternatives=["show status", "status update", "current status"],
                examples=["check status", "what's the status"],
                description="to check your complaint status",
                response_template="Getting your status information."
            ),
            CommandPattern(
                pattern="show schemes|government schemes|available schemes",
                category=CommandCategory.INFORMATION,
                complexity=CommandComplexity.MODERATE,
                language="english",
                alternatives=["list schemes", "what schemes", "government programs"],
                examples=["show schemes", "government schemes"],
                description="to see available government schemes",
                response_template="Finding schemes for you."
            ),
            CommandPattern(
                pattern="help|need help|assistance",
                category=CommandCategory.HELP,
                complexity=CommandComplexity.SIMPLE,
                language="english",
                alternatives=["guide me", "how to", "support"],
                examples=["help", "need help"],
                description="for help and guidance",
                response_template="I'll help you. What do you need?"
            ),
            
            # Action commands
            CommandPattern(
                pattern="file complaint|make complaint|report problem",
                category=CommandCategory.ACTION,
                complexity=CommandComplexity.MODERATE,
                language="english",
                alternatives=["lodge complaint", "submit complaint", "register complaint"],
                examples=["file complaint", "report problem"],
                description="to file a new complaint",
                response_template="I'll help you file a complaint.",
                requires_confirmation=True
            ),
            CommandPattern(
                pattern="apply|submit application|fill form",
                category=CommandCategory.ACTION,
                complexity=CommandComplexity.MODERATE,
                language="english",
                alternatives=["make application", "submit form", "apply for scheme"],
                examples=["apply", "submit application"],
                description="to submit a new application",
                response_template="I'll help you apply.",
                requires_confirmation=True
            ),
            
            # Confirmation commands
            CommandPattern(
                pattern="yes|okay|correct|right",
                category=CommandCategory.CONFIRMATION,
                complexity=CommandComplexity.SIMPLE,
                language="english",
                alternatives=["ok", "sure", "absolutely"],
                examples=["yes", "okay"],
                description="to say yes",
                response_template="Got it."
            ),
            CommandPattern(
                pattern="no|wrong|cancel|not correct",
                category=CommandCategory.CONFIRMATION,
                complexity=CommandComplexity.SIMPLE,
                language="english",
                alternatives=["nope", "incorrect", "stop"],
                examples=["no", "wrong"],
                description="to say no",
                response_template="Okay, cancelling."
            ),
            
            # Correction commands
            CommandPattern(
                pattern="repeat|say again|once more",
                category=CommandCategory.CORRECTION,
                complexity=CommandComplexity.SIMPLE,
                language="english",
                alternatives=["again", "repeat that", "one more time"],
                examples=["repeat", "say again"],
                description="to hear again",
                response_template="Let me repeat that."
            ),
            CommandPattern(
                pattern="wrong|incorrect|change|fix",
                category=CommandCategory.CORRECTION,
                complexity=CommandComplexity.SIMPLE,
                language="english",
                alternatives=["not right", "modify", "correct"],
                examples=["wrong", "change"],
                description="to correct something",
                response_template="Okay, let me fix that."
            ),
        ]
        
        # Store patterns by language
        self._command_patterns["hindi"] = hindi_patterns
        self._command_patterns["english"] = english_patterns
        
        # Build search index
        self._build_command_index()
    
    def _build_command_index(self):
        """Build search index for fast command lookup."""
        try:
            for language, patterns in self._command_patterns.items():
                for pattern in patterns:
                    # Index main pattern
                    words = pattern.pattern.lower().split('|')
                    for word in words:
                        self._command_index[language].add(word.strip())
                    
                    # Index alternatives
                    for alt in pattern.alternatives:
                        alt_words = alt.lower().split()
                        for word in alt_words:
                            self._command_index[language].add(word.strip())
            
            self.logger.info("Command index built successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to build command index: {e}")
    
    def match_command(
        self, 
        user_input: str, 
        language: str = "hindi",
        confidence_threshold: float = 0.6
    ) -> Optional[CommandMatch]:
        """
        Match user input to command patterns.
        
        Args:
            user_input: User's voice input
            language: Language of the input
            confidence_threshold: Minimum confidence for match
            
        Returns:
            CommandMatch if found, None otherwise
        """
        try:
            user_input_lower = user_input.lower().strip()
            patterns = self._command_patterns.get(language, [])
            
            best_match = None
            best_confidence = 0.0
            
            for pattern in patterns:
                confidence = self._calculate_pattern_confidence(user_input_lower, pattern)
                
                if confidence > best_confidence and confidence >= confidence_threshold:
                    best_confidence = confidence
                    best_match = CommandMatch(
                        pattern=pattern,
                        confidence=confidence,
                        matched_text=user_input,
                        extracted_parameters=self._extract_parameters(user_input_lower, pattern)
                    )
            
            return best_match
            
        except Exception as e:
            self.logger.error(f"Failed to match command: {e}")
            return None
    
    def _calculate_pattern_confidence(self, user_input: str, pattern: CommandPattern) -> float:
        """Calculate confidence score for pattern match."""
        try:
            # Check exact pattern match
            pattern_options = pattern.pattern.lower().split('|')
            for option in pattern_options:
                if option.strip() == user_input:
                    return 1.0
                if option.strip() in user_input or user_input in option.strip():
                    return 0.9
            
            # Check alternatives
            for alt in pattern.alternatives:
                alt_lower = alt.lower()
                if alt_lower == user_input:
                    return 0.95
                if alt_lower in user_input or user_input in alt_lower:
                    return 0.85
            
            # Check word overlap
            pattern_words = set()
            for option in pattern_options:
                pattern_words.update(option.strip().split())
            
            for alt in pattern.alternatives:
                pattern_words.update(alt.lower().split())
            
            user_words = set(user_input.split())
            
            if pattern_words and user_words:
                overlap = len(pattern_words.intersection(user_words))
                total_words = len(pattern_words.union(user_words))
                return overlap / total_words if total_words > 0 else 0.0
            
            return 0.0
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate pattern confidence: {e}")
            return 0.0
    
    def _extract_parameters(self, user_input: str, pattern: CommandPattern) -> Dict[str, Any]:
        """Extract parameters from user input based on pattern."""
        try:
            parameters = {}
            
            # Simple parameter extraction for common patterns
            if pattern.category == CommandCategory.INFORMATION:
                # Extract reference numbers
                ref_match = re.search(r'\b\d{6,}\b', user_input)
                if ref_match:
                    parameters['reference_number'] = ref_match.group()
            
            elif pattern.category == CommandCategory.ACTION:
                # Extract action-specific parameters
                if "शिकायत" in pattern.pattern or "complaint" in pattern.pattern:
                    parameters['action_type'] = 'complaint'
                elif "आवेदन" in pattern.pattern or "apply" in pattern.pattern:
                    parameters['action_type'] = 'application'
            
            return parameters
            
        except Exception as e:
            self.logger.warning(f"Failed to extract parameters: {e}")
            return {}
    
    def get_command_suggestions(
        self, 
        partial_input: str, 
        language: str = "hindi",
        max_suggestions: int = 3
    ) -> List[CommandPattern]:
        """
        Get command suggestions based on partial input.
        
        Args:
            partial_input: Partial user input
            language: Language for suggestions
            max_suggestions: Maximum number of suggestions
            
        Returns:
            List of suggested command patterns
        """
        try:
            partial_lower = partial_input.lower().strip()
            patterns = self._command_patterns.get(language, [])
            
            suggestions = []
            
            for pattern in patterns:
                # Check if partial input matches pattern start
                pattern_options = pattern.pattern.lower().split('|')
                for option in pattern_options:
                    if option.strip().startswith(partial_lower):
                        suggestions.append(pattern)
                        break
                
                # Check alternatives
                if pattern not in suggestions:
                    for alt in pattern.alternatives:
                        if alt.lower().startswith(partial_lower):
                            suggestions.append(pattern)
                            break
                
                if len(suggestions) >= max_suggestions:
                    break
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Failed to get command suggestions: {e}")
            return []
    
    def add_custom_pattern(self, pattern: CommandPattern):
        """Add a custom command pattern."""
        try:
            if pattern.language not in self._command_patterns:
                self._command_patterns[pattern.language] = []
            
            self._command_patterns[pattern.language].append(pattern)
            
            # Update index
            words = pattern.pattern.lower().split('|')
            for word in words:
                self._command_index[pattern.language].add(word.strip())
            
            for alt in pattern.alternatives:
                alt_words = alt.lower().split()
                for word in alt_words:
                    self._command_index[pattern.language].add(word.strip())
            
            self.logger.info(f"Added custom command pattern: {pattern.pattern}")
            
        except Exception as e:
            self.logger.error(f"Failed to add custom pattern: {e}")
            raise AccessibilityError(
                f"Failed to add custom pattern: {e}",
                error_code="CUSTOM_PATTERN_ADD_FAILED"
            )
    
    def get_patterns_by_category(
        self, 
        category: CommandCategory, 
        language: str = "hindi"
    ) -> List[CommandPattern]:
        """Get all patterns for a specific category."""
        try:
            patterns = self._command_patterns.get(language, [])
            return [p for p in patterns if p.category == category]
            
        except Exception as e:
            self.logger.error(f"Failed to get patterns by category: {e}")
            return []
    
    def validate_command_consistency(self) -> Dict[str, List[str]]:
        """Validate command consistency across languages."""
        try:
            issues = defaultdict(list)
            
            # Check for missing translations
            hindi_categories = set()
            english_categories = set()
            
            for pattern in self._command_patterns.get("hindi", []):
                hindi_categories.add(pattern.category)
            
            for pattern in self._command_patterns.get("english", []):
                english_categories.add(pattern.category)
            
            missing_in_english = hindi_categories - english_categories
            missing_in_hindi = english_categories - hindi_categories
            
            if missing_in_english:
                issues["missing_english_translations"] = [cat.value for cat in missing_in_english]
            
            if missing_in_hindi:
                issues["missing_hindi_translations"] = [cat.value for cat in missing_in_hindi]
            
            return dict(issues)
            
        except Exception as e:
            self.logger.error(f"Failed to validate command consistency: {e}")
            return {"validation_error": [str(e)]}


class ConsistentCommands:
    """Provides consistent command interface for the voice assistant."""
    
    def __init__(self):
        """Initialize consistent commands interface."""
        self.logger = get_logger(__name__)
        self.pattern_manager = CommandPatternManager()
        self._command_history: List[str] = []
        self._max_history = 10
    
    def process_voice_command(
        self, 
        voice_input: str, 
        language: str = "hindi",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process voice command and return structured response.
        
        Args:
            voice_input: User's voice input
            language: Language of the input
            context: Current conversation context
            
        Returns:
            Structured command response
        """
        try:
            # Add to command history
            self._add_to_history(voice_input)
            
            # Match command pattern
            command_match = self.pattern_manager.match_command(voice_input, language)
            
            if not command_match:
                return self._handle_unrecognized_command(voice_input, language)
            
            # Process matched command
            response = {
                "recognized": True,
                "command_category": command_match.pattern.category.value,
                "confidence": command_match.confidence,
                "response_text": command_match.pattern.response_template,
                "requires_confirmation": command_match.pattern.requires_confirmation,
                "parameters": command_match.extracted_parameters,
                "next_action": self._determine_next_action(command_match, context)
            }
            
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to process voice command: {e}")
            return {
                "recognized": False,
                "error": "Command processing failed",
                "response_text": "माफ करें, कुछ समस्या हुई है। फिर से कोशिश करें।" if language == "hindi" else "Sorry, there was a problem. Please try again."
            }
    
    def _add_to_history(self, command: str):
        """Add command to history."""
        try:
            self._command_history.append(command)
            if len(self._command_history) > self._max_history:
                self._command_history.pop(0)
                
        except Exception as e:
            self.logger.warning(f"Failed to add command to history: {e}")
    
    def _handle_unrecognized_command(self, voice_input: str, language: str) -> Dict[str, Any]:
        """Handle unrecognized commands with suggestions."""
        try:
            # Get suggestions
            suggestions = self.pattern_manager.get_command_suggestions(voice_input, language)
            
            if suggestions:
                if language == "hindi":
                    response_text = "मैं समझ नहीं पाया। क्या आप यह कहना चाहते थे:\n"
                    for i, suggestion in enumerate(suggestions, 1):
                        response_text += f"{i}. {suggestion.examples[0] if suggestion.examples else suggestion.pattern.split('|')[0]}\n"
                else:
                    response_text = "I didn't understand. Did you mean:\n"
                    for i, suggestion in enumerate(suggestions, 1):
                        response_text += f"{i}. {suggestion.examples[0] if suggestion.examples else suggestion.pattern.split('|')[0]}\n"
            else:
                if language == "hindi":
                    response_text = "मैं समझ नहीं पाया। 'मदद चाहिए' कहें या फिर से कोशिश करें।"
                else:
                    response_text = "I didn't understand. Say 'help' or try again."
            
            return {
                "recognized": False,
                "suggestions": [s.examples[0] if s.examples else s.pattern.split('|')[0] for s in suggestions],
                "response_text": response_text,
                "help_available": True
            }
            
        except Exception as e:
            self.logger.error(f"Failed to handle unrecognized command: {e}")
            return {
                "recognized": False,
                "response_text": "माफ करें, मैं समझ नहीं पाया।" if language == "hindi" else "Sorry, I didn't understand."
            }
    
    def _determine_next_action(
        self, 
        command_match: CommandMatch, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Determine the next action based on command match."""
        try:
            category = command_match.pattern.category
            
            if category == CommandCategory.NAVIGATION:
                if "back" in command_match.pattern.pattern or "वापस" in command_match.pattern.pattern:
                    return "navigate_back"
                elif "forward" in command_match.pattern.pattern or "आगे" in command_match.pattern.pattern:
                    return "navigate_forward"
                elif "home" in command_match.pattern.pattern or "घर" in command_match.pattern.pattern:
                    return "navigate_home"
            
            elif category == CommandCategory.INFORMATION:
                if "status" in command_match.pattern.pattern or "स्थिति" in command_match.pattern.pattern:
                    return "show_status"
                elif "scheme" in command_match.pattern.pattern or "योजना" in command_match.pattern.pattern:
                    return "show_schemes"
            
            elif category == CommandCategory.ACTION:
                if "complaint" in command_match.pattern.pattern or "शिकायत" in command_match.pattern.pattern:
                    return "start_complaint_filing"
                elif "apply" in command_match.pattern.pattern or "आवेदन" in command_match.pattern.pattern:
                    return "start_application"
            
            elif category == CommandCategory.HELP:
                return "show_help"
            
            elif category == CommandCategory.CONFIRMATION:
                if "yes" in command_match.pattern.pattern or "हाँ" in command_match.pattern.pattern:
                    return "confirm_action"
                else:
                    return "cancel_action"
            
            elif category == CommandCategory.CORRECTION:
                if "repeat" in command_match.pattern.pattern or "फिर से" in command_match.pattern.pattern:
                    return "repeat_last_response"
                else:
                    return "correct_last_input"
            
            return "continue_conversation"
            
        except Exception as e:
            self.logger.warning(f"Failed to determine next action: {e}")
            return "continue_conversation"
    
    def get_command_help(self, language: str = "hindi") -> str:
        """Get help text for available commands."""
        try:
            patterns = self.pattern_manager._command_patterns.get(language, [])
            
            if language == "hindi":
                help_text = "आप ये कमांड बोल सकते हैं:\n\n"
                
                categories = {
                    CommandCategory.NAVIGATION: "नेवीगेशन:",
                    CommandCategory.INFORMATION: "जानकारी:",
                    CommandCategory.ACTION: "काम:",
                    CommandCategory.HELP: "मदद:",
                    CommandCategory.CONFIRMATION: "हाँ/ना:",
                    CommandCategory.CORRECTION: "सुधार:"
                }
            else:
                help_text = "You can say these commands:\n\n"
                
                categories = {
                    CommandCategory.NAVIGATION: "Navigation:",
                    CommandCategory.INFORMATION: "Information:",
                    CommandCategory.ACTION: "Actions:",
                    CommandCategory.HELP: "Help:",
                    CommandCategory.CONFIRMATION: "Yes/No:",
                    CommandCategory.CORRECTION: "Corrections:"
                }
            
            for category, title in categories.items():
                category_patterns = [p for p in patterns if p.category == category]
                if category_patterns:
                    help_text += f"{title}\n"
                    for pattern in category_patterns[:3]:  # Show max 3 examples per category
                        example = pattern.examples[0] if pattern.examples else pattern.pattern.split('|')[0]
                        help_text += f"  • {example} - {pattern.description}\n"
                    help_text += "\n"
            
            return help_text
            
        except Exception as e:
            self.logger.error(f"Failed to get command help: {e}")
            return "मदद उपलब्ध नहीं है।" if language == "hindi" else "Help not available."
    
    def get_command_history(self) -> List[str]:
        """Get recent command history."""
        return self._command_history.copy()
    
    def clear_command_history(self):
        """Clear command history."""
        self._command_history.clear()