"""
Intent classification for government service requests.

This module provides intent classification capabilities for identifying
user intentions in government service interactions across multiple
Indian languages.
"""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
import re
from dataclasses import dataclass

from ..core.exceptions import IntentRecognitionError
from ..core.config import config

logger = logging.getLogger(__name__)


class ServiceIntent(Enum):
    """Government service intent categories."""
    SCHEME_DISCOVERY = "scheme_discovery"
    GRIEVANCE_FILING = "grievance_filing"
    STATUS_TRACKING = "status_tracking"
    DOCUMENT_HELP = "document_help"
    ELIGIBILITY_CHECK = "eligibility_check"
    APPLICATION_HELP = "application_help"
    GENERAL_INQUIRY = "general_inquiry"
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: ServiceIntent
    confidence: float
    language: str
    entities: Dict[str, str]
    raw_text: str


class IntentClassifier:
    """
    Multilingual intent classifier for government service requests.
    
    Supports Hindi, English, and 8 major regional Indian languages:
    Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi.
    """
    
    # Supported languages
    SUPPORTED_LANGUAGES = {
        'hi': 'Hindi',
        'en': 'English', 
        'ta': 'Tamil',
        'te': 'Telugu',
        'bn': 'Bengali',
        'mr': 'Marathi',
        'gu': 'Gujarati',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'pa': 'Punjabi'
    }
    
    def __init__(self):
        """Initialize the intent classifier."""
        self._intent_patterns = self._load_intent_patterns()
        self._language_patterns = self._load_language_patterns()
        logger.info("IntentClassifier initialized with %d languages", 
                   len(self.SUPPORTED_LANGUAGES))
    
    def classify_intent(self, text: str, language: Optional[str] = None) -> IntentResult:
        """
        Classify the intent of user input text.
        
        Args:
            text: User input text
            language: Optional language code (auto-detected if not provided)
            
        Returns:
            IntentResult with classified intent and metadata
            
        Raises:
            IntentRecognitionError: If intent classification fails
        """
        try:
            # Detect language if not provided
            if not language:
                language = self._detect_language(text)
            
            # Validate language support
            if language not in self.SUPPORTED_LANGUAGES:
                logger.warning("Unsupported language detected: %s", language)
                language = 'hi'  # Default to Hindi
            
            # Clean and normalize text
            normalized_text = self._normalize_text(text, language)
            
            # Extract basic entities
            entities = self._extract_basic_entities(normalized_text, language)
            
            # Classify intent using pattern matching
            intent, confidence = self._classify_using_patterns(normalized_text, language)
            
            result = IntentResult(
                intent=intent,
                confidence=confidence,
                language=language,
                entities=entities,
                raw_text=text
            )
            
            logger.info("Intent classified: %s (confidence: %.2f, language: %s)", 
                       intent.value, confidence, language)
            
            return result
            
        except Exception as e:
            logger.error("Intent classification failed: %s", str(e))
            raise IntentRecognitionError(f"Failed to classify intent: {str(e)}")
    
    def _detect_language(self, text: str) -> str:
        """
        Detect the language of input text.
        
        Args:
            text: Input text
            
        Returns:
            Language code
        """
        # Simple language detection based on character patterns
        text_lower = text.lower()
        
        # Check for English patterns (high proportion of Latin characters)
        latin_chars = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(re.findall(r'[^\s\d\W]', text))  # Non-space, non-digit, non-punctuation
        
        if total_chars > 0 and latin_chars / total_chars > 0.7:
            return 'en'
        
        # Check for specific language patterns with better scoring
        language_scores = {}
        
        for lang_code, patterns in self._language_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text))
                score += matches * 2  # Weight pattern matches more heavily
            
            if score > 0:
                language_scores[lang_code] = score
        
        # Return language with highest score if confident enough
        if language_scores:
            best_lang = max(language_scores.items(), key=lambda x: x[1])
            if best_lang[1] >= 2:  # Require at least 2 points for confidence
                return best_lang[0]
        
        # Check for Hindi/Devanagari script (default for Devanagari)
        if re.search(r'[\u0900-\u097F]', text):
            # Check for common Hindi words to distinguish from Marathi
            hindi_words = ['मुझे', 'चाहिए', 'योजना', 'सहायता', 'जानकारी', 'के लिए']
            for word in hindi_words:
                if word in text:
                    return 'hi'
            # If no specific Hindi words found but has Devanagari, default to Hindi
            return 'hi'
        
        # Default to Hindi if no specific pattern matches
        return 'hi'
    
    def _normalize_text(self, text: str, language: str) -> str:
        """
        Normalize text for processing.
        
        Args:
            text: Input text
            language: Language code
            
        Returns:
            Normalized text
        """
        # Basic normalization
        normalized = text.strip().lower()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Language-specific normalization
        if language == 'en':
            # Remove common English stop words for intent classification
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            words = normalized.split()
            normalized = ' '.join([word for word in words if word not in stop_words])
        
        return normalized
    
    def _extract_basic_entities(self, text: str, language: str) -> Dict[str, str]:
        """
        Extract basic entities from text.
        
        Args:
            text: Normalized text
            language: Language code
            
        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        
        # Extract reference numbers (common pattern across languages)
        ref_pattern = r'(?:reference|ref|रेफरेंस|संदर्भ|ಉಲ್ಲೇಖ|సూచన|রেফারেন্স|સંદર્ભ|संदर्भ|റഫറൻസ്|ਹਵਾਲਾ)[\s:]*([A-Z0-9]{6,})'
        ref_match = re.search(ref_pattern, text, re.IGNORECASE)
        if ref_match:
            entities['reference_number'] = ref_match.group(1)
        
        # Extract phone numbers
        phone_pattern = r'(?:\+91|91)?[\s-]?[6-9]\d{9}'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            entities['phone_number'] = phone_match.group(0)
        
        # Extract common government terms
        gov_terms = {
            'en': ['pension', 'ration', 'card', 'certificate', 'license', 'subsidy', 'scheme'],
            'hi': ['पेंशन', 'राशन', 'कार्ड', 'प्रमाणपत्र', 'लाइसेंस', 'सब्सिडी', 'योजना'],
            'ta': ['ஓய்வூதியம்', 'ரேஷன்', 'அட்டை', 'சான்றிதழ்', 'உரிமம்', 'மானியம்', 'திட்டம்'],
            'te': ['పెన్షన్', 'రేషన్', 'కార్డ్', 'సర్టిఫికేట్', 'లైసెన్స్', 'సబ్సిడీ', 'పథకం'],
            'bn': ['পেনশন', 'রেশন', 'কার্ড', 'সার্টিফিকেট', 'লাইসেন্স', 'ভর্তুকি', 'প্রকল্প'],
            'mr': ['पेन्शन', 'रेशन', 'कार्ड', 'प्रमाणपत्र', 'परवाना', 'अनुदान', 'योजना'],
            'gu': ['પેન્શન', 'રાશન', 'કાર્ડ', 'પ્રમાણપત્ર', 'લાયસન્સ', 'સબસિડી', 'યોજના'],
            'kn': ['ಪಿಂಚಣಿ', 'ರೇಷನ್', 'ಕಾರ್ಡ್', 'ಪ್ರಮಾಣಪತ್ರ', 'ಪರವಾನಗಿ', 'ಸಬ್ಸಿಡಿ', 'ಯೋಜನೆ'],
            'ml': ['പെൻഷൻ', 'റേഷൻ', 'കാർഡ്', 'സർട്ടിഫിക്കറ്റ്', 'ലൈസൻസ്', 'സബ്സിഡി', 'പദ്ധതി'],
            'pa': ['ਪੈਨਸ਼ਨ', 'ਰਾਸ਼ਨ', 'ਕਾਰਡ', 'ਸਰਟੀਫਿਕੇਟ', 'ਲਾਇਸੈਂਸ', 'ਸਬਸਿਡੀ', 'ਸਕੀਮ']
        }
        
        if language in gov_terms:
            for term in gov_terms[language]:
                if term in text:
                    entities['government_service'] = term
                    break
        
        return entities
    
    def _classify_using_patterns(self, text: str, language: str) -> Tuple[ServiceIntent, float]:
        """
        Classify intent using pattern matching.
        
        Args:
            text: Normalized text
            language: Language code
            
        Returns:
            Tuple of (intent, confidence)
        """
        max_confidence = 0.0
        best_intent = ServiceIntent.UNKNOWN
        
        # Get patterns for the language
        patterns = self._intent_patterns.get(language, self._intent_patterns['en'])
        
        for intent, intent_patterns in patterns.items():
            confidence = 0.0
            matches = 0
            
            for pattern in intent_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matches += 1
                    confidence += 0.4  # Increased base confidence per pattern match
            
            # Boost confidence based on number of matches
            if matches > 0:
                confidence = min(0.95, confidence + (matches - 1) * 0.15)
                
                if confidence > max_confidence:
                    max_confidence = confidence
                    best_intent = ServiceIntent(intent)
        
        # Ensure minimum confidence for unknown intent
        if max_confidence < 0.4:
            best_intent = ServiceIntent.UNKNOWN
            max_confidence = 0.2
        
        return best_intent, max_confidence
    
    def _load_intent_patterns(self) -> Dict[str, Dict[str, List[str]]]:
        """Load intent classification patterns for all supported languages."""
        return {
            'en': {
                'scheme_discovery': [
                    r'scheme', r'pension', r'benefit', r'subsidy', r'program',
                    r'help.*with.*scheme', r'need.*scheme', r'want.*scheme',
                    r'eligible.*scheme', r'government.*scheme', r'find.*scheme',
                    r'about.*scheme', r'information.*scheme', r'know.*about.*pension'
                ],
                'grievance_filing': [
                    r'file.*complaint', r'register.*grievance', r'complaint',
                    r'problem.*with', r'issue.*with', r'complain',
                    r'lodge.*complaint', r'submit.*complaint', r'grievance'
                ],
                'status_tracking': [
                    r'status', r'check.*status', r'track', r'reference',
                    r'application.*status', r'where.*is.*my', r'update',
                    r'progress', r'ref\d+', r'reference.*number'
                ],
                'document_help': [
                    r'document', r'paper', r'certificate', r'proof',
                    r'what.*document', r'need.*document', r'required.*document'
                ],
                'eligibility_check': [
                    r'eligible', r'qualify', r'can.*i.*apply', r'am.*i.*eligible',
                    r'criteria', r'requirement'
                ],
                'application_help': [
                    r'how.*to.*apply', r'apply', r'application.*process',
                    r'steps.*apply', r'procedure', r'form'
                ]
            },
            'hi': {
                'scheme_discovery': [
                    r'योजना', r'पेंशन', r'लाभ', r'सब्सिडी', r'सरकारी',
                    r'योजना.*चाहिए', r'योजना.*के.*बारे', r'जानकारी.*चाहिए',
                    r'पेंशन.*योजना', r'सरकारी.*योजना', r'लाभ.*योजना'
                ],
                'grievance_filing': [
                    r'शिकायत', r'गुहार', r'समस्या', r'परेशानी',
                    r'शिकायत.*दर्ज', r'शिकायत.*करना', r'समस्या.*है'
                ],
                'status_tracking': [
                    r'स्थिति', r'जांच', r'ट्रैक', r'संदर्भ', r'रेफरेंस',
                    r'आवेदन.*स्थिति', r'कहां.*है', r'अपडेट'
                ],
                'document_help': [
                    r'दस्तावेज', r'कागज', r'प्रमाणपत्र', r'सर्टिफिकेट',
                    r'दस्तावेज.*चाहिए', r'कागज.*चाहिए'
                ],
                'eligibility_check': [
                    r'पात्र', r'योग्य', r'आवेदन.*कर.*सकता', r'मिल.*सकता',
                    r'योग्यता', r'मापदंड'
                ],
                'application_help': [
                    r'आवेदन', r'अप्लाई', r'फॉर्म', r'प्रक्रिया',
                    r'कैसे.*आवेदन', r'आवेदन.*कैसे'
                ]
            }
        }
    
    def _load_language_patterns(self) -> Dict[str, List[str]]:
        """Load language detection patterns."""
        return {
            'ta': [r'[ஃ-ௌ]', r'என்', r'அது', r'இது', r'எப்படி'],
            'te': [r'[ఀ-౿]', r'అది', r'ఇది', r'ఎలా', r'ఎందుకు'],
            'bn': [r'[ঀ-৿]', r'এটি', r'সেটি', r'কিভাবে', r'কেন'],
            'mr': [r'हे\s', r'ते\s', r'कसे', r'का\s', r'मी\s'],  # More specific Marathi patterns
            'gu': [r'[ઁ-૿]', r'આ', r'તે', r'કેવી', r'કેમ'],
            'kn': [r'[ಀ-೿]', r'ಇದು', r'ಅದು', r'ಹೇಗೆ', r'ಯಾಕೆ'],
            'ml': [r'[ഀ-ൿ]', r'ഇത്', r'അത്', r'എങ്ങനെ', r'എന്തുകൊണ്ട്'],
            'pa': [r'[ਁ-੿]', r'ਇਹ', r'ਉਹ', r'ਕਿਵੇਂ', r'ਕਿਉਂ']
        }