"""
Multi-modal interface for alternative input methods and accessibility.

This module provides comprehensive multi-modal interaction including:
- Alternative input methods for users with different abilities
- Voice, text, and gesture input support
- Adaptive interface based on user capabilities
- Fallback mechanisms for failed interactions
- Accessibility features for disabled users
"""

from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from ..core.logging import get_logger
from ..core.exceptions import AccessibilityError


logger = get_logger(__name__)


class InputMode(Enum):
    """Available input modes."""
    VOICE = "voice"
    TEXT = "text"
    GESTURE = "gesture"
    TOUCH = "touch"
    KEYBOARD = "keyboard"
    HYBRID = "hybrid"  # Combination of multiple modes


class OutputMode(Enum):
    """Available output modes."""
    VOICE = "voice"
    TEXT = "text"
    VISUAL = "visual"
    HAPTIC = "haptic"
    HYBRID = "hybrid"  # Combination of multiple modes


class AccessibilityNeed(Enum):
    """Types of accessibility needs."""
    VISUAL_IMPAIRMENT = "visual_impairment"
    HEARING_IMPAIRMENT = "hearing_impairment"
    MOTOR_IMPAIRMENT = "motor_impairment"
    COGNITIVE_IMPAIRMENT = "cognitive_impairment"
    SPEECH_IMPAIRMENT = "speech_impairment"
    LOW_LITERACY = "low_literacy"
    ELDERLY = "elderly"


@dataclass
class UserCapabilities:
    """User's capabilities and limitations."""
    can_speak: bool = True
    can_hear: bool = True
    can_see: bool = True
    can_type: bool = True
    can_touch: bool = True
    preferred_input: InputMode = InputMode.VOICE
    preferred_output: OutputMode = OutputMode.VOICE
    accessibility_needs: List[AccessibilityNeed] = field(default_factory=list)
    language_preference: str = "hindi"
    reading_level: str = "basic"
    technology_comfort: str = "low"


@dataclass
class InteractionContext:
    """Context for multi-modal interaction."""
    current_task: Optional[str] = None
    device_type: str = "mobile"
    network_quality: str = "good"
    environment_noise: str = "low"
    lighting_condition: str = "good"
    user_stress_level: str = "normal"
    time_pressure: bool = False


class InputProcessor(ABC):
    """Abstract base class for input processors."""
    
    @abstractmethod
    def can_process(self, input_data: Any, context: InteractionContext) -> bool:
        """Check if this processor can handle the input."""
        pass
    
    @abstractmethod
    def process_input(self, input_data: Any, context: InteractionContext) -> Dict[str, Any]:
        """Process the input and return structured data."""
        pass
    
    @abstractmethod
    def get_confidence(self) -> float:
        """Get confidence score for the processed input."""
        pass


class VoiceInputProcessor(InputProcessor):
    """Processes voice input with accessibility features."""
    
    def __init__(self):
        """Initialize voice input processor."""
        self.logger = get_logger(__name__)
        self._confidence = 0.0
    
    def can_process(self, input_data: Any, context: InteractionContext) -> bool:
        """Check if voice input can be processed."""
        try:
            # Check if input is audio data
            if not hasattr(input_data, 'audio_data'):
                return False
            
            # Check environment conditions
            if context.environment_noise == "high":
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to check voice input capability: {e}")
            return False
    
    def process_input(self, input_data: Any, context: InteractionContext) -> Dict[str, Any]:
        """Process voice input with noise handling and clarity enhancement."""
        try:
            # Simulate voice processing (in real implementation, this would use AWS Transcribe)
            audio_data = getattr(input_data, 'audio_data', '')
            
            # Apply noise reduction based on environment
            if context.environment_noise in ["medium", "high"]:
                audio_data = self._apply_noise_reduction(audio_data)
            
            # Enhance clarity for elderly users or hearing impairment
            if context.user_stress_level == "high":
                audio_data = self._enhance_clarity(audio_data)
            
            # Process the audio (placeholder)
            recognized_text = self._recognize_speech(audio_data, context)
            
            # Calculate confidence based on various factors
            self._confidence = self._calculate_confidence(recognized_text, context)
            
            return {
                "input_mode": InputMode.VOICE.value,
                "recognized_text": recognized_text,
                "confidence": self._confidence,
                "language_detected": context.user_capabilities.language_preference if hasattr(context, 'user_capabilities') else "hindi",
                "processing_time": 0.5  # Simulated processing time
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process voice input: {e}")
            return {
                "input_mode": InputMode.VOICE.value,
                "error": str(e),
                "confidence": 0.0
            }
    
    def _apply_noise_reduction(self, audio_data: Any) -> Any:
        """Apply noise reduction to audio data."""
        # Placeholder for noise reduction logic
        return audio_data
    
    def _enhance_clarity(self, audio_data: Any) -> Any:
        """Enhance audio clarity for better recognition."""
        # Placeholder for clarity enhancement logic
        return audio_data
    
    def _recognize_speech(self, audio_data: Any, context: InteractionContext) -> str:
        """Recognize speech from audio data."""
        # Placeholder for speech recognition logic
        return "sample recognized text"
    
    def _calculate_confidence(self, recognized_text: str, context: InteractionContext) -> float:
        """Calculate confidence score for recognition."""
        try:
            base_confidence = 0.8  # Base confidence
            
            # Adjust based on environment
            if context.environment_noise == "high":
                base_confidence -= 0.3
            elif context.environment_noise == "medium":
                base_confidence -= 0.1
            
            # Adjust based on text length and clarity
            if len(recognized_text.split()) < 2:
                base_confidence -= 0.2
            
            return max(0.0, min(1.0, base_confidence))
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate confidence: {e}")
            return 0.5
    
    def get_confidence(self) -> float:
        """Get confidence score for the processed input."""
        return self._confidence


class TextInputProcessor(InputProcessor):
    """Processes text input with accessibility features."""
    
    def __init__(self):
        """Initialize text input processor."""
        self.logger = get_logger(__name__)
        self._confidence = 0.0
    
    def can_process(self, input_data: Any, context: InteractionContext) -> bool:
        """Check if text input can be processed."""
        try:
            return isinstance(input_data, str) and len(input_data.strip()) > 0
            
        except Exception as e:
            self.logger.warning(f"Failed to check text input capability: {e}")
            return False
    
    def process_input(self, input_data: Any, context: InteractionContext) -> Dict[str, Any]:
        """Process text input with language detection and correction."""
        try:
            text = str(input_data).strip()
            
            # Detect language
            detected_language = self._detect_language(text)
            
            # Apply text corrections for common mistakes
            corrected_text = self._apply_text_corrections(text, detected_language)
            
            # Calculate confidence
            self._confidence = self._calculate_text_confidence(corrected_text)
            
            return {
                "input_mode": InputMode.TEXT.value,
                "original_text": text,
                "corrected_text": corrected_text,
                "confidence": self._confidence,
                "language_detected": detected_language,
                "corrections_applied": corrected_text != text
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process text input: {e}")
            return {
                "input_mode": InputMode.TEXT.value,
                "error": str(e),
                "confidence": 0.0
            }
    
    def _detect_language(self, text: str) -> str:
        """Detect language of the text."""
        try:
            # Simple language detection based on script
            hindi_chars = sum(1 for char in text if '\u0900' <= char <= '\u097F')
            english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
            
            if hindi_chars > english_chars:
                return "hindi"
            else:
                return "english"
                
        except Exception as e:
            self.logger.warning(f"Failed to detect language: {e}")
            return "hindi"
    
    def _apply_text_corrections(self, text: str, language: str) -> str:
        """Apply common text corrections."""
        try:
            corrected = text
            
            # Common corrections for Hindi transliteration
            if language == "hindi":
                corrections = {
                    "shikayat": "शिकायत",
                    "avedan": "आवेदन",
                    "yojana": "योजना",
                    "sarkar": "सरकार",
                    "madad": "मदद"
                }
                
                for english, hindi in corrections.items():
                    corrected = corrected.replace(english, hindi)
            
            # Common corrections for English
            else:
                corrections = {
                    "complain": "complaint",
                    "aply": "apply",
                    "goverment": "government",
                    "recieve": "receive",
                    "seperate": "separate"
                }
                
                for wrong, correct in corrections.items():
                    corrected = corrected.replace(wrong, correct)
            
            return corrected
            
        except Exception as e:
            self.logger.warning(f"Failed to apply text corrections: {e}")
            return text
    
    def _calculate_text_confidence(self, text: str) -> float:
        """Calculate confidence score for text input."""
        try:
            base_confidence = 0.9  # Text input is generally more reliable
            
            # Adjust based on text length
            if len(text.split()) < 2:
                base_confidence -= 0.1
            
            # Adjust based on special characters or numbers
            if any(char.isdigit() for char in text):
                base_confidence += 0.05  # Numbers often indicate specific data
            
            return max(0.0, min(1.0, base_confidence))
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate text confidence: {e}")
            return 0.8
    
    def get_confidence(self) -> float:
        """Get confidence score for the processed input."""
        return self._confidence


class MultiModalInterface:
    """Main interface for multi-modal interaction management."""
    
    def __init__(self):
        """Initialize multi-modal interface."""
        self.logger = get_logger(__name__)
        self._input_processors: Dict[InputMode, InputProcessor] = {}
        self._output_generators: Dict[OutputMode, Callable] = {}
        self._setup_processors()
        self._setup_output_generators()
    
    def _setup_processors(self):
        """Setup input processors for different modes."""
        self._input_processors[InputMode.VOICE] = VoiceInputProcessor()
        self._input_processors[InputMode.TEXT] = TextInputProcessor()
        # Additional processors can be added here
    
    def _setup_output_generators(self):
        """Setup output generators for different modes."""
        self._output_generators[OutputMode.VOICE] = self._generate_voice_output
        self._output_generators[OutputMode.TEXT] = self._generate_text_output
        self._output_generators[OutputMode.VISUAL] = self._generate_visual_output
    
    def process_input(
        self, 
        input_data: Any, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> Dict[str, Any]:
        """
        Process input using the most appropriate method.
        
        Args:
            input_data: Raw input data
            user_capabilities: User's capabilities and preferences
            context: Current interaction context
            
        Returns:
            Processed input data with metadata
        """
        try:
            # Add user capabilities to context
            context.user_capabilities = user_capabilities
            
            # Determine best input mode
            best_mode = self._determine_best_input_mode(input_data, user_capabilities, context)
            
            # Process with the selected mode
            processor = self._input_processors.get(best_mode)
            if not processor:
                raise AccessibilityError(f"No processor available for mode: {best_mode}")
            
            if not processor.can_process(input_data, context):
                # Try fallback modes
                fallback_result = self._try_fallback_input_modes(input_data, user_capabilities, context)
                if fallback_result:
                    return fallback_result
                
                raise AccessibilityError("No suitable input processor found")
            
            result = processor.process_input(input_data, context)
            result["selected_mode"] = best_mode.value
            result["fallback_used"] = False
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process input: {e}")
            return {
                "error": str(e),
                "confidence": 0.0,
                "fallback_available": True
            }
    
    def _determine_best_input_mode(
        self, 
        input_data: Any, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> InputMode:
        """Determine the best input mode for the user and context."""
        try:
            # Start with user preference
            preferred_mode = user_capabilities.preferred_input
            
            # Check if preferred mode is suitable for current context
            if self._is_mode_suitable(preferred_mode, user_capabilities, context):
                return preferred_mode
            
            # Find alternative suitable modes
            suitable_modes = []
            
            for mode in InputMode:
                if mode != preferred_mode and self._is_mode_suitable(mode, user_capabilities, context):
                    suitable_modes.append(mode)
            
            # Return the first suitable alternative, or fallback to text
            if suitable_modes:
                return suitable_modes[0]
            
            return InputMode.TEXT  # Text is usually the most reliable fallback
            
        except Exception as e:
            self.logger.warning(f"Failed to determine best input mode: {e}")
            return InputMode.TEXT
    
    def _is_mode_suitable(
        self, 
        mode: InputMode, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> bool:
        """Check if an input mode is suitable for the user and context."""
        try:
            # Check user capabilities
            if mode == InputMode.VOICE and not user_capabilities.can_speak:
                return False
            
            if mode == InputMode.TEXT and not user_capabilities.can_type:
                return False
            
            # Check context conditions
            if mode == InputMode.VOICE and context.environment_noise == "high":
                return False
            
            # Check accessibility needs
            if AccessibilityNeed.SPEECH_IMPAIRMENT in user_capabilities.accessibility_needs:
                if mode == InputMode.VOICE:
                    return False
            
            if AccessibilityNeed.MOTOR_IMPAIRMENT in user_capabilities.accessibility_needs:
                if mode in [InputMode.TEXT, InputMode.TOUCH, InputMode.GESTURE]:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to check mode suitability: {e}")
            return False
    
    def _try_fallback_input_modes(
        self, 
        input_data: Any, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> Optional[Dict[str, Any]]:
        """Try fallback input modes when primary mode fails."""
        try:
            # Define fallback order
            fallback_order = [InputMode.TEXT, InputMode.VOICE]
            
            for mode in fallback_order:
                if mode == user_capabilities.preferred_input:
                    continue  # Skip the already tried preferred mode
                
                processor = self._input_processors.get(mode)
                if processor and processor.can_process(input_data, context):
                    result = processor.process_input(input_data, context)
                    result["selected_mode"] = mode.value
                    result["fallback_used"] = True
                    result["original_preferred_mode"] = user_capabilities.preferred_input.value
                    return result
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to try fallback input modes: {e}")
            return None
    
    def generate_output(
        self, 
        content: str, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> Dict[str, Any]:
        """
        Generate output in the most appropriate format.
        
        Args:
            content: Content to output
            user_capabilities: User's capabilities and preferences
            context: Current interaction context
            
        Returns:
            Generated output in appropriate format(s)
        """
        try:
            # Determine best output modes
            output_modes = self._determine_best_output_modes(user_capabilities, context)
            
            outputs = {}
            
            for mode in output_modes:
                generator = self._output_generators.get(mode)
                if generator:
                    try:
                        outputs[mode.value] = generator(content, user_capabilities, context)
                    except Exception as e:
                        self.logger.warning(f"Failed to generate {mode.value} output: {e}")
            
            return {
                "outputs": outputs,
                "primary_mode": output_modes[0].value if output_modes else OutputMode.TEXT.value,
                "accessibility_features": self._get_accessibility_features(user_capabilities)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate output: {e}")
            return {
                "outputs": {OutputMode.TEXT.value: content},
                "error": str(e)
            }
    
    def _determine_best_output_modes(
        self, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> List[OutputMode]:
        """Determine the best output modes for the user."""
        try:
            modes = []
            
            # Start with user preference
            preferred_mode = user_capabilities.preferred_output
            if self._is_output_mode_suitable(preferred_mode, user_capabilities, context):
                modes.append(preferred_mode)
            
            # Add complementary modes based on accessibility needs
            if AccessibilityNeed.VISUAL_IMPAIRMENT in user_capabilities.accessibility_needs:
                if OutputMode.VOICE not in modes:
                    modes.append(OutputMode.VOICE)
            
            if AccessibilityNeed.HEARING_IMPAIRMENT in user_capabilities.accessibility_needs:
                if OutputMode.TEXT not in modes:
                    modes.append(OutputMode.TEXT)
                if OutputMode.VISUAL not in modes:
                    modes.append(OutputMode.VISUAL)
            
            # Ensure at least one mode is available
            if not modes:
                modes.append(OutputMode.TEXT)
            
            return modes
            
        except Exception as e:
            self.logger.warning(f"Failed to determine best output modes: {e}")
            return [OutputMode.TEXT]
    
    def _is_output_mode_suitable(
        self, 
        mode: OutputMode, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> bool:
        """Check if an output mode is suitable."""
        try:
            if mode == OutputMode.VOICE and not user_capabilities.can_hear:
                return False
            
            if mode == OutputMode.TEXT and not user_capabilities.can_see:
                return False
            
            if mode == OutputMode.VISUAL and not user_capabilities.can_see:
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to check output mode suitability: {e}")
            return False
    
    def _generate_voice_output(
        self, 
        content: str, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> Dict[str, Any]:
        """Generate voice output."""
        try:
            # Adjust speech parameters based on user needs
            speech_rate = "medium"
            volume = "normal"
            
            if AccessibilityNeed.ELDERLY in user_capabilities.accessibility_needs:
                speech_rate = "slow"
                volume = "loud"
            
            if AccessibilityNeed.COGNITIVE_IMPAIRMENT in user_capabilities.accessibility_needs:
                speech_rate = "slow"
            
            return {
                "content": content,
                "speech_rate": speech_rate,
                "volume": volume,
                "language": user_capabilities.language_preference,
                "voice_type": "female"  # Can be made configurable
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate voice output: {e}")
            return {"content": content, "error": str(e)}
    
    def _generate_text_output(
        self, 
        content: str, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> Dict[str, Any]:
        """Generate text output."""
        try:
            # Adjust text formatting based on user needs
            font_size = "normal"
            contrast = "normal"
            
            if AccessibilityNeed.VISUAL_IMPAIRMENT in user_capabilities.accessibility_needs:
                font_size = "large"
                contrast = "high"
            
            if AccessibilityNeed.ELDERLY in user_capabilities.accessibility_needs:
                font_size = "large"
            
            return {
                "content": content,
                "font_size": font_size,
                "contrast": contrast,
                "language": user_capabilities.language_preference
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate text output: {e}")
            return {"content": content, "error": str(e)}
    
    def _generate_visual_output(
        self, 
        content: str, 
        user_capabilities: UserCapabilities,
        context: InteractionContext
    ) -> Dict[str, Any]:
        """Generate visual output with icons and graphics."""
        try:
            return {
                "content": content,
                "icons": True,
                "graphics": True,
                "color_coding": True,
                "language": user_capabilities.language_preference
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate visual output: {e}")
            return {"content": content, "error": str(e)}
    
    def _get_accessibility_features(self, user_capabilities: UserCapabilities) -> List[str]:
        """Get list of accessibility features enabled for the user."""
        features = []
        
        if AccessibilityNeed.VISUAL_IMPAIRMENT in user_capabilities.accessibility_needs:
            features.extend(["screen_reader_compatible", "high_contrast", "large_text"])
        
        if AccessibilityNeed.HEARING_IMPAIRMENT in user_capabilities.accessibility_needs:
            features.extend(["visual_indicators", "text_alternatives"])
        
        if AccessibilityNeed.MOTOR_IMPAIRMENT in user_capabilities.accessibility_needs:
            features.extend(["voice_navigation", "large_touch_targets"])
        
        if AccessibilityNeed.COGNITIVE_IMPAIRMENT in user_capabilities.accessibility_needs:
            features.extend(["simple_language", "clear_instructions", "progress_indicators"])
        
        if AccessibilityNeed.LOW_LITERACY in user_capabilities.accessibility_needs:
            features.extend(["voice_guidance", "visual_cues", "simple_vocabulary"])
        
        if AccessibilityNeed.ELDERLY in user_capabilities.accessibility_needs:
            features.extend(["large_text", "slow_speech", "patient_interaction"])
        
        return features


class AlternativeInputMethods:
    """Provides alternative input methods for accessibility."""
    
    def __init__(self):
        """Initialize alternative input methods."""
        self.logger = get_logger(__name__)
        self.multi_modal = MultiModalInterface()
    
    def get_available_methods(self, user_capabilities: UserCapabilities) -> List[str]:
        """Get list of available input methods for the user."""
        try:
            methods = []
            
            if user_capabilities.can_speak:
                methods.append("voice_input")
            
            if user_capabilities.can_type:
                methods.append("text_input")
            
            if user_capabilities.can_touch:
                methods.append("touch_input")
            
            # Always available methods
            methods.extend(["guided_input", "step_by_step_input"])
            
            # Special methods for accessibility needs
            if AccessibilityNeed.MOTOR_IMPAIRMENT in user_capabilities.accessibility_needs:
                methods.append("voice_only_navigation")
            
            if AccessibilityNeed.VISUAL_IMPAIRMENT in user_capabilities.accessibility_needs:
                methods.append("audio_guided_input")
            
            if AccessibilityNeed.LOW_LITERACY in user_capabilities.accessibility_needs:
                methods.append("picture_based_input")
            
            return methods
            
        except Exception as e:
            self.logger.error(f"Failed to get available methods: {e}")
            return ["voice_input", "text_input"]
    
    def provide_input_guidance(
        self, 
        method: str, 
        language: str = "hindi"
    ) -> str:
        """Provide guidance for using specific input method."""
        try:
            guidance = {
                "hindi": {
                    "voice_input": "माइक के पास आकर साफ-साफ बोलें। शांत जगह पर बैठकर बात करें।",
                    "text_input": "कीबोर्ड का इस्तेमाल करके टाइप करें। गलती हो तो बैकस्पेस दबाएं।",
                    "touch_input": "स्क्रीन पर टच करके विकल्प चुनें। धीरे-धीरे टच करें।",
                    "guided_input": "मैं आपको स्टेप बाई स्टेप बताऊंगा। हर सवाल का जवाब दें।",
                    "voice_only_navigation": "सिर्फ आवाज से काम करें। 'हाँ', 'नहीं', 'आगे', 'पीछे' बोलें।",
                    "audio_guided_input": "मैं आपको आवाज में बताऊंगा कि क्या करना है। सुनकर जवाब दें।"
                },
                "english": {
                    "voice_input": "Speak clearly near the microphone. Sit in a quiet place to talk.",
                    "text_input": "Use keyboard to type. Press backspace if you make mistake.",
                    "touch_input": "Touch the screen to select options. Touch slowly and gently.",
                    "guided_input": "I will guide you step by step. Answer each question.",
                    "voice_only_navigation": "Use only voice commands. Say 'yes', 'no', 'next', 'back'.",
                    "audio_guided_input": "I will tell you what to do with voice. Listen and respond."
                }
            }
            
            lang_guidance = guidance.get(language, guidance["hindi"])
            return lang_guidance.get(method, "मदद उपलब्ध नहीं है।" if language == "hindi" else "Help not available.")
            
        except Exception as e:
            self.logger.error(f"Failed to provide input guidance: {e}")
            return "मदद उपलब्ध नहीं है।" if language == "hindi" else "Help not available."