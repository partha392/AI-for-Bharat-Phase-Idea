"""
Simple communication and vocabulary management for accessibility.

This module provides comprehensive vocabulary simplification including:
- Technical jargon replacement
- Simple language generation
- Cultural adaptation
- Regional language support
- Education level appropriate communication
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..core.logging import get_logger
from ..core.exceptions import AccessibilityError


logger = get_logger(__name__)


class EducationLevel(Enum):
    """Education levels for communication adaptation."""
    BASIC = "basic"          # Primary education or less
    INTERMEDIATE = "intermediate"  # Secondary education
    ADVANCED = "advanced"    # Higher education


class CommunicationStyle(Enum):
    """Communication styles."""
    FORMAL = "formal"
    INFORMAL = "informal"
    CONVERSATIONAL = "conversational"


@dataclass
class VocabularyRule:
    """Rule for vocabulary simplification."""
    complex_term: str
    simple_replacement: str
    context: Optional[str] = None
    education_level: EducationLevel = EducationLevel.BASIC
    language: str = "hindi"
    explanation: Optional[str] = None


@dataclass
class CommunicationConfig:
    """Configuration for communication adaptation."""
    education_level: EducationLevel = EducationLevel.BASIC
    preferred_language: str = "hindi"
    communication_style: CommunicationStyle = CommunicationStyle.CONVERSATIONAL
    use_examples: bool = True
    use_analogies: bool = True
    max_sentence_length: int = 15
    avoid_passive_voice: bool = True
    use_local_context: bool = True


class VocabularySimplifier:
    """Simplifies vocabulary for better accessibility."""
    
    def __init__(self):
        """Initialize the vocabulary simplifier."""
        self.logger = get_logger(__name__)
        self._vocabulary_rules: Dict[str, List[VocabularyRule]] = {}
        self._load_default_vocabulary_rules()
    
    def _load_default_vocabulary_rules(self):
        """Load default vocabulary simplification rules."""
        # Government and administrative terms
        govt_rules = [
            VocabularyRule("application", "आवेदन", "government", EducationLevel.BASIC, "hindi", "फॉर्म भरना"),
            VocabularyRule("grievance", "शिकायत", "government", EducationLevel.BASIC, "hindi", "समस्या बताना"),
            VocabularyRule("beneficiary", "लाभार्थी", "government", EducationLevel.BASIC, "hindi", "जिसे फायदा मिलता है"),
            VocabularyRule("eligibility", "योग्यता", "government", EducationLevel.BASIC, "hindi", "हकदार होना"),
            VocabularyRule("documentation", "कागजात", "government", EducationLevel.BASIC, "hindi", "जरूरी कागज"),
            VocabularyRule("verification", "जांच", "government", EducationLevel.BASIC, "hindi", "सही होना देखना"),
            VocabularyRule("processing", "काम चल रहा है", "government", EducationLevel.BASIC, "hindi", "आपका काम हो रहा है"),
            VocabularyRule("status", "स्थिति", "government", EducationLevel.BASIC, "hindi", "क्या हाल है"),
            VocabularyRule("reference number", "नंबर", "government", EducationLevel.BASIC, "hindi", "आपका खास नंबर"),
            VocabularyRule("portal", "वेबसाइट", "technology", EducationLevel.BASIC, "hindi", "इंटरनेट पर जगह"),
        ]
        
        # Technical terms
        tech_rules = [
            VocabularyRule("authentication", "पहचान", "technology", EducationLevel.BASIC, "hindi", "आप कौन हैं यह बताना"),
            VocabularyRule("database", "रिकॉर्ड", "technology", EducationLevel.BASIC, "hindi", "सभी जानकारी रखने की जगह"),
            VocabularyRule("interface", "स्क्रीन", "technology", EducationLevel.BASIC, "hindi", "जो आप देखते हैं"),
            VocabularyRule("system", "व्यवस्था", "technology", EducationLevel.BASIC, "hindi", "काम करने का तरीका"),
            VocabularyRule("server", "कंप्यूटर", "technology", EducationLevel.BASIC, "hindi", "बड़ा कंप्यूटर"),
            VocabularyRule("network", "जुड़ाव", "technology", EducationLevel.BASIC, "hindi", "सब कुछ जुड़ा हुआ"),
            VocabularyRule("update", "नया करना", "technology", EducationLevel.BASIC, "hindi", "पुराना हटाकर नया लगाना"),
            VocabularyRule("download", "लेना", "technology", EducationLevel.BASIC, "hindi", "अपने फोन में लाना"),
            VocabularyRule("upload", "भेजना", "technology", EducationLevel.BASIC, "hindi", "अपने फोन से भेजना"),
            VocabularyRule("password", "गुप्त शब्द", "technology", EducationLevel.BASIC, "hindi", "सिर्फ आपका खास शब्द"),
        ]
        
        # Financial terms
        finance_rules = [
            VocabularyRule("subsidy", "सहायता", "finance", EducationLevel.BASIC, "hindi", "सरकार की तरफ से पैसे की मदद"),
            VocabularyRule("pension", "मासिक पैसा", "finance", EducationLevel.BASIC, "hindi", "हर महीने मिलने वाला पैसा"),
            VocabularyRule("loan", "कर्ज", "finance", EducationLevel.BASIC, "hindi", "उधार पैसा"),
            VocabularyRule("interest", "ब्याज", "finance", EducationLevel.BASIC, "hindi", "कर्ज पर अतिरिक्त पैसा"),
            VocabularyRule("installment", "किस्त", "finance", EducationLevel.BASIC, "hindi", "थोड़ा-थोड़ा करके पैसा देना"),
            VocabularyRule("account", "खाता", "finance", EducationLevel.BASIC, "hindi", "बैंक में आपका पैसा"),
            VocabularyRule("transaction", "लेन-देन", "finance", EducationLevel.BASIC, "hindi", "पैसा आना-जाना"),
            VocabularyRule("balance", "बचा हुआ पैसा", "finance", EducationLevel.BASIC, "hindi", "आपके पास कितना पैसा है"),
        ]
        
        # Store rules by language
        self._vocabulary_rules["hindi"] = govt_rules + tech_rules + finance_rules
        
        # English equivalents for bilingual users
        english_rules = [
            VocabularyRule("application", "form", "government", EducationLevel.BASIC, "english", "filling out a form"),
            VocabularyRule("grievance", "complaint", "government", EducationLevel.BASIC, "english", "reporting a problem"),
            VocabularyRule("beneficiary", "person who gets help", "government", EducationLevel.BASIC, "english", "someone who receives benefits"),
            VocabularyRule("eligibility", "qualification", "government", EducationLevel.BASIC, "english", "meeting the requirements"),
            VocabularyRule("documentation", "papers", "government", EducationLevel.BASIC, "english", "required documents"),
            VocabularyRule("verification", "checking", "government", EducationLevel.BASIC, "english", "making sure it's correct"),
            VocabularyRule("processing", "working on it", "government", EducationLevel.BASIC, "english", "your request is being handled"),
            VocabularyRule("status", "current situation", "government", EducationLevel.BASIC, "english", "what's happening now"),
        ]
        
        self._vocabulary_rules["english"] = english_rules
    
    def simplify_text(
        self, 
        text: str, 
        config: CommunicationConfig
    ) -> str:
        """
        Simplify text based on communication configuration.
        
        Args:
            text: Text to simplify
            config: Communication configuration
            
        Returns:
            Simplified text
        """
        try:
            simplified_text = text
            
            # Get vocabulary rules for the language
            rules = self._vocabulary_rules.get(config.preferred_language, [])
            
            # Apply vocabulary simplification
            for rule in rules:
                if rule.education_level.value <= config.education_level.value:
                    # Use word boundaries to avoid partial matches
                    pattern = r'\b' + re.escape(rule.complex_term) + r'\b'
                    simplified_text = re.sub(
                        pattern, 
                        rule.simple_replacement, 
                        simplified_text, 
                        flags=re.IGNORECASE
                    )
            
            # Apply sentence structure simplification
            simplified_text = self._simplify_sentence_structure(simplified_text, config)
            
            # Add explanations if needed
            if config.use_examples:
                simplified_text = self._add_examples(simplified_text, config)
            
            return simplified_text
            
        except Exception as e:
            self.logger.error(f"Failed to simplify text: {e}")
            return text  # Return original text if simplification fails
    
    def _simplify_sentence_structure(self, text: str, config: CommunicationConfig) -> str:
        """Simplify sentence structure."""
        try:
            sentences = text.split('.')
            simplified_sentences = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                # Break long sentences
                if len(sentence.split()) > config.max_sentence_length:
                    # Try to break at conjunctions
                    conjunctions = ['और', 'तथा', 'एवं', 'लेकिन', 'परंतु', 'किंतु', 'and', 'but', 'however', 'therefore']
                    for conj in conjunctions:
                        if conj in sentence:
                            parts = sentence.split(conj, 1)
                            if len(parts) == 2:
                                simplified_sentences.append(parts[0].strip())
                                simplified_sentences.append(parts[1].strip())
                                break
                    else:
                        simplified_sentences.append(sentence)
                else:
                    simplified_sentences.append(sentence)
            
            return '. '.join(simplified_sentences) + '.'
            
        except Exception as e:
            self.logger.warning(f"Failed to simplify sentence structure: {e}")
            return text
    
    def _add_examples(self, text: str, config: CommunicationConfig) -> str:
        """Add examples to make text clearer."""
        try:
            # Add examples for common concepts
            examples = {
                "hindi": {
                    "आवेदन": "जैसे राशन कार्ड के लिए फॉर्म भरना",
                    "शिकायत": "जैसे बिजली नहीं आने की समस्या बताना",
                    "योग्यता": "जैसे आपकी उम्र 18 साल से ज्यादा होना",
                    "कागजात": "जैसे आधार कार्ड, राशन कार्ड",
                },
                "english": {
                    "form": "like filling out a ration card application",
                    "complaint": "like reporting a power outage problem",
                    "qualification": "like being over 18 years old",
                    "papers": "like Aadhaar card, ration card",
                }
            }
            
            lang_examples = examples.get(config.preferred_language, {})
            
            for term, example in lang_examples.items():
                if term in text:
                    text = text.replace(term, f"{term} ({example})")
            
            return text
            
        except Exception as e:
            self.logger.warning(f"Failed to add examples: {e}")
            return text
    
    def add_vocabulary_rule(self, rule: VocabularyRule):
        """Add a custom vocabulary rule."""
        try:
            if rule.language not in self._vocabulary_rules:
                self._vocabulary_rules[rule.language] = []
            
            self._vocabulary_rules[rule.language].append(rule)
            self.logger.info(f"Added vocabulary rule: {rule.complex_term} -> {rule.simple_replacement}")
            
        except Exception as e:
            self.logger.error(f"Failed to add vocabulary rule: {e}")
            raise AccessibilityError(
                f"Failed to add vocabulary rule: {e}",
                error_code="VOCABULARY_RULE_ADD_FAILED"
            )
    
    def get_explanation(self, term: str, language: str = "hindi") -> Optional[str]:
        """Get explanation for a term."""
        try:
            rules = self._vocabulary_rules.get(language, [])
            
            for rule in rules:
                if rule.complex_term.lower() == term.lower() or rule.simple_replacement.lower() == term.lower():
                    return rule.explanation
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get explanation for term {term}: {e}")
            return None


class SimpleCommunicationManager:
    """Manages simple and accessible communication."""
    
    def __init__(self):
        """Initialize the communication manager."""
        self.logger = get_logger(__name__)
        self.vocabulary_simplifier = VocabularySimplifier()
        self._communication_templates: Dict[str, Dict[str, str]] = {}
        self._load_communication_templates()
    
    def _load_communication_templates(self):
        """Load communication templates for different scenarios."""
        # Hindi templates
        hindi_templates = {
            "greeting": "नमस्ते! मैं आपकी मदद करने के लिए यहाँ हूँ।",
            "confirmation": "ठीक है, मैं समझ गया।",
            "clarification": "क्षमा करें, क्या आप फिर से बता सकते हैं?",
            "wait": "कृपया थोड़ा इंतजार करें, मैं आपकी जानकारी देख रहा हूँ।",
            "success": "बहुत अच्छा! आपका काम हो गया।",
            "error": "माफ करें, कुछ समस्या हुई है। फिर से कोशिश करते हैं।",
            "help": "मैं आपकी मदद कर सकता हूँ। बताइए आपको क्या चाहिए?",
            "goodbye": "धन्यवाद! फिर मिलते हैं।",
            "repeat": "मैं फिर से बताता हूँ:",
            "options": "आप ये काम कर सकते हैं:",
            "next_step": "अब आपको यह करना है:",
            "important": "यह बात जरूरी है:",
        }
        
        # English templates
        english_templates = {
            "greeting": "Hello! I'm here to help you.",
            "confirmation": "Okay, I understand.",
            "clarification": "Sorry, can you please tell me again?",
            "wait": "Please wait a moment, I'm checking your information.",
            "success": "Great! Your work is done.",
            "error": "Sorry, there was a problem. Let's try again.",
            "help": "I can help you. What do you need?",
            "goodbye": "Thank you! See you again.",
            "repeat": "Let me tell you again:",
            "options": "You can do these things:",
            "next_step": "Now you need to do this:",
            "important": "This is important:",
        }
        
        self._communication_templates["hindi"] = hindi_templates
        self._communication_templates["english"] = english_templates
    
    def generate_accessible_response(
        self, 
        content: str, 
        response_type: str,
        config: CommunicationConfig
    ) -> str:
        """
        Generate an accessible response.
        
        Args:
            content: Main content of the response
            response_type: Type of response (greeting, error, success, etc.)
            config: Communication configuration
            
        Returns:
            Accessible response text
        """
        try:
            # Get template for the response type
            templates = self._communication_templates.get(config.preferred_language, {})
            template_prefix = templates.get(response_type, "")
            
            # Simplify the content
            simplified_content = self.vocabulary_simplifier.simplify_text(content, config)
            
            # Combine template with content
            if template_prefix:
                response = f"{template_prefix} {simplified_content}"
            else:
                response = simplified_content
            
            # Apply communication style
            response = self._apply_communication_style(response, config)
            
            # Add local context if enabled
            if config.use_local_context:
                response = self._add_local_context(response, config)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to generate accessible response: {e}")
            return content  # Return original content if generation fails
    
    def _apply_communication_style(self, text: str, config: CommunicationConfig) -> str:
        """Apply communication style to text."""
        try:
            if config.communication_style == CommunicationStyle.CONVERSATIONAL:
                # Make it more conversational
                if config.preferred_language == "hindi":
                    # Add conversational markers
                    text = text.replace("आप", "आप")  # Keep respectful form
                    if not text.endswith(("।", "?", "!")):
                        text += "।"
                else:
                    # English conversational style
                    if not text.endswith((".", "?", "!")):
                        text += "."
            
            elif config.communication_style == CommunicationStyle.INFORMAL:
                # Make it more informal and friendly
                if config.preferred_language == "hindi":
                    text = text.replace("कृपया", "")  # Remove formal "please"
                    text = text.replace("आपका", "आपका")  # Keep respectful
                
            return text
            
        except Exception as e:
            self.logger.warning(f"Failed to apply communication style: {e}")
            return text
    
    def _add_local_context(self, text: str, config: CommunicationConfig) -> str:
        """Add local context to make communication more relatable."""
        try:
            # Add local examples and references
            local_context = {
                "hindi": {
                    "सरकारी कार्यालय": "जैसे तहसील या ब्लॉक ऑफिस",
                    "बैंक": "जैसे आपका नजदीकी बैंक",
                    "दस्तावेज": "जैसे आधार कार्ड या वोटर आईडी",
                    "आवेदन": "जैसे पंचायत में फॉर्म जमा करना",
                },
                "english": {
                    "government office": "like your local tehsil or block office",
                    "bank": "like your nearby bank",
                    "documents": "like Aadhaar card or voter ID",
                    "application": "like submitting form at panchayat",
                }
            }
            
            lang_context = local_context.get(config.preferred_language, {})
            
            for term, context in lang_context.items():
                if term in text and context not in text:
                    text = text.replace(term, f"{term} ({context})")
            
            return text
            
        except Exception as e:
            self.logger.warning(f"Failed to add local context: {e}")
            return text
    
    def create_step_by_step_instructions(
        self, 
        steps: List[str], 
        config: CommunicationConfig
    ) -> str:
        """
        Create step-by-step instructions.
        
        Args:
            steps: List of instruction steps
            config: Communication configuration
            
        Returns:
            Formatted step-by-step instructions
        """
        try:
            if config.preferred_language == "hindi":
                instruction_text = "आपको ये काम करने हैं:\n\n"
                for i, step in enumerate(steps, 1):
                    simplified_step = self.vocabulary_simplifier.simplify_text(step, config)
                    instruction_text += f"{i}. {simplified_step}\n"
            else:
                instruction_text = "You need to do these steps:\n\n"
                for i, step in enumerate(steps, 1):
                    simplified_step = self.vocabulary_simplifier.simplify_text(step, config)
                    instruction_text += f"{i}. {simplified_step}\n"
            
            return instruction_text.strip()
            
        except Exception as e:
            self.logger.error(f"Failed to create step-by-step instructions: {e}")
            return "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps))
    
    def create_error_explanation(
        self, 
        error_message: str, 
        suggested_action: str,
        config: CommunicationConfig
    ) -> str:
        """
        Create user-friendly error explanation.
        
        Args:
            error_message: Technical error message
            suggested_action: What user should do
            config: Communication configuration
            
        Returns:
            User-friendly error explanation
        """
        try:
            if config.preferred_language == "hindi":
                explanation = f"कुछ समस्या हुई है। {suggested_action}"
                
                # Add common error explanations
                if "network" in error_message.lower() or "connection" in error_message.lower():
                    explanation = "इंटरनेट की समस्या है। कृपया अपना इंटरनेट चेक करें और फिर कोशिश करें।"
                elif "timeout" in error_message.lower():
                    explanation = "काम में ज्यादा समय लग रहा है। कृपया फिर से कोशिश करें।"
                elif "invalid" in error_message.lower():
                    explanation = "कुछ गलत जानकारी दी गई है। कृपया सही जानकारी दें।"
                elif "not found" in error_message.lower():
                    explanation = "यह जानकारी नहीं मिली। कृपया दूसरी जानकारी दें।"
                
            else:
                explanation = f"There was a problem. {suggested_action}"
                
                # Add common error explanations
                if "network" in error_message.lower() or "connection" in error_message.lower():
                    explanation = "There's an internet problem. Please check your internet and try again."
                elif "timeout" in error_message.lower():
                    explanation = "It's taking too long. Please try again."
                elif "invalid" in error_message.lower():
                    explanation = "Some wrong information was given. Please give correct information."
                elif "not found" in error_message.lower():
                    explanation = "This information was not found. Please give different information."
            
            return self.vocabulary_simplifier.simplify_text(explanation, config)
            
        except Exception as e:
            self.logger.error(f"Failed to create error explanation: {e}")
            return suggested_action
    
    def get_communication_config(
        self, 
        user_profile: Dict[str, Any]
    ) -> CommunicationConfig:
        """
        Get communication configuration based on user profile.
        
        Args:
            user_profile: User profile information
            
        Returns:
            Communication configuration
        """
        try:
            # Determine education level
            education = user_profile.get("education_level", "basic")
            if education in ["graduate", "postgraduate"]:
                education_level = EducationLevel.ADVANCED
            elif education in ["secondary", "higher_secondary"]:
                education_level = EducationLevel.INTERMEDIATE
            else:
                education_level = EducationLevel.BASIC
            
            # Determine preferred language
            preferred_language = user_profile.get("preferred_language", "hindi")
            
            # Determine communication style
            age = user_profile.get("age", 30)
            if age > 60:
                communication_style = CommunicationStyle.FORMAL
            else:
                communication_style = CommunicationStyle.CONVERSATIONAL
            
            return CommunicationConfig(
                education_level=education_level,
                preferred_language=preferred_language,
                communication_style=communication_style,
                use_examples=education_level == EducationLevel.BASIC,
                use_analogies=education_level == EducationLevel.BASIC,
                max_sentence_length=12 if education_level == EducationLevel.BASIC else 20,
                use_local_context=True
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get communication config: {e}")
            # Return default configuration
            return CommunicationConfig()