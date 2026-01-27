"""
Entity extraction for personal information and requirements.

This module provides entity extraction capabilities for identifying
personal information, government service requirements, and other
relevant entities from user input across multiple Indian languages.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from ..core.exceptions import EntityExtractionError
from ..core.config import config

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Types of entities that can be extracted."""
    PERSON_NAME = "person_name"
    PHONE_NUMBER = "phone_number"
    EMAIL = "email"
    ADDRESS = "address"
    REFERENCE_NUMBER = "reference_number"
    DATE = "date"
    AMOUNT = "amount"
    GOVERNMENT_SERVICE = "government_service"
    DOCUMENT_TYPE = "document_type"
    LOCATION = "location"
    AGE = "age"
    INCOME = "income"
    CASTE_CATEGORY = "caste_category"
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """Extracted entity with metadata."""
    type: EntityType
    value: str
    confidence: float
    start_pos: int
    end_pos: int
    language: str
    normalized_value: Optional[str] = None


@dataclass
class EntityExtractionResult:
    """Result of entity extraction."""
    entities: List[Entity]
    text: str
    language: str
    processing_time: float


class EntityExtractor:
    """
    Multilingual entity extractor for personal information and requirements.
    
    Extracts entities relevant to government service interactions including
    personal details, service requirements, and administrative information.
    """
    
    def __init__(self):
        """Initialize the entity extractor."""
        self._entity_patterns = self._load_entity_patterns()
        self._normalization_rules = self._load_normalization_rules()
        logger.info("EntityExtractor initialized")
    
    def extract_entities(self, text: str, language: str = 'hi') -> EntityExtractionResult:
        """
        Extract entities from input text.
        
        Args:
            text: Input text
            language: Language code
            
        Returns:
            EntityExtractionResult with extracted entities
            
        Raises:
            EntityExtractionError: If entity extraction fails
        """
        start_time = datetime.now()
        
        try:
            entities = []
            
            # Extract different types of entities
            entities.extend(self._extract_phone_numbers(text, language))
            entities.extend(self._extract_emails(text, language))
            entities.extend(self._extract_reference_numbers(text, language))
            entities.extend(self._extract_dates(text, language))
            entities.extend(self._extract_amounts(text, language))
            entities.extend(self._extract_government_services(text, language))
            entities.extend(self._extract_document_types(text, language))
            entities.extend(self._extract_locations(text, language))
            entities.extend(self._extract_person_names(text, language))
            entities.extend(self._extract_ages(text, language))
            entities.extend(self._extract_income(text, language))
            entities.extend(self._extract_caste_categories(text, language))
            
            # Sort entities by position
            entities.sort(key=lambda e: e.start_pos)
            
            # Remove overlapping entities (keep highest confidence)
            entities = self._remove_overlapping_entities(entities)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = EntityExtractionResult(
                entities=entities,
                text=text,
                language=language,
                processing_time=processing_time
            )
            
            logger.info("Extracted %d entities in %.3f seconds", 
                       len(entities), processing_time)
            
            return result
            
        except Exception as e:
            logger.error("Entity extraction failed: %s", str(e))
            raise EntityExtractionError(f"Failed to extract entities: {str(e)}")
    
    def _extract_phone_numbers(self, text: str, language: str) -> List[Entity]:
        """Extract phone numbers from text."""
        entities = []
        
        # Indian phone number patterns
        patterns = [
            r'(?:\+91|91)?[\s-]?([6-9]\d{9})',  # Standard Indian mobile
            r'(?:\+91|91)?[\s-]?(\d{2,4}[\s-]?\d{6,8})',  # Landline
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                phone = match.group(1) if match.groups() else match.group(0)
                # Clean phone number
                phone = re.sub(r'[\s-]', '', phone)
                
                if len(phone) == 10 and phone[0] in '6789':  # Valid mobile
                    entities.append(Entity(
                        type=EntityType.PHONE_NUMBER,
                        value=match.group(0),
                        confidence=0.9,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        language=language,
                        normalized_value=phone
                    ))
        
        return entities
    
    def _extract_emails(self, text: str, language: str) -> List[Entity]:
        """Extract email addresses from text."""
        entities = []
        
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        for match in re.finditer(email_pattern, text):
            entities.append(Entity(
                type=EntityType.EMAIL,
                value=match.group(0),
                confidence=0.95,
                start_pos=match.start(),
                end_pos=match.end(),
                language=language,
                normalized_value=match.group(0).lower()
            ))
        
        return entities
    
    def _extract_reference_numbers(self, text: str, language: str) -> List[Entity]:
        """Extract reference/application numbers from text."""
        entities = []
        
        # Common reference number patterns - more specific
        patterns = [
            r'(?:ref|reference|रेफरेंस|संदर्भ|ಉಲ್ಲೇಖ|సూచన|রেফারেন্স|સંદર્ભ|संदर्भ|റഫറൻസ്|ਹਵਾਲਾ)[\s:]*([A-Z0-9]{6,})',
            r'(?:application|आवेदन|अर्जी|ಅರ್ಜಿ|దరఖాస్తు|আবেদন|અરજી|अर्ज|അപേക്ഷ|ਅਰਜ਼ੀ)[\s:]*(?:no|number|संख्या|क्रमांक|ಸಂಖ್ಯೆ|సంఖ్య|নম্বর|નંબર|क्रमांक|നമ്പർ|ਨੰਬਰ)?[\s:]*([A-Z0-9]{6,})',
            r'\b([A-Z]{2,4}\d{6,})\b',  # Generic alphanumeric reference
            r'\b(REF\d{6,})\b',  # REF followed by numbers
            r'\b(APP\d{6,})\b',  # APP followed by numbers
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                ref_num = match.group(1) if match.groups() else match.group(0)
                # Only add if it looks like a real reference number
                if len(ref_num) >= 6 and re.search(r'\d', ref_num):
                    entities.append(Entity(
                        type=EntityType.REFERENCE_NUMBER,
                        value=match.group(0),
                        confidence=0.85,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        language=language,
                        normalized_value=ref_num.upper()
                    ))
        
        return entities
    
    def _extract_dates(self, text: str, language: str) -> List[Entity]:
        """Extract dates from text."""
        entities = []
        
        # Date patterns for different formats
        patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',  # DD/MM/YYYY or MM/DD/YYYY
            r'\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{2,4})\b',  # DD Mon YYYY
            r'\b(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\b',  # YYYY/MM/DD
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(Entity(
                    type=EntityType.DATE,
                    value=match.group(0),
                    confidence=0.8,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    language=language,
                    normalized_value=match.group(1)
                ))
        
        return entities
    
    def _extract_amounts(self, text: str, language: str) -> List[Entity]:
        """Extract monetary amounts from text."""
        entities = []
        
        # Amount patterns
        patterns = [
            r'(?:rs|rupees|₹|रुपये|रुपए|ರೂಪಾಯಿ|రూపాయలు|টাকা|રૂપિયા|रुपये|രൂപ|ਰੁਪਏ)[\s]*(\d+(?:,\d+)*(?:\.\d+)?)',
            r'(\d+(?:,\d+)*(?:\.\d+)?)[\s]*(?:rs|rupees|₹|रुपये|रुपए|ರೂಪಾಯಿ|రూపాయలు|টাকা|રૂપિયા|रुपये|രൂപ|ਰੁਪਏ)',
            r'(\d+(?:,\d+)*(?:\.\d+)?)[\s]*(?:lakh|lakhs|crore|crores|लाख|करोड़|ಲಕ್ಷ|ಕೋಟಿ|లక్ష|కోటి|লাখ|কোটি|લાખ|કરોડ|लाख|करोड|ലക്ഷം|കോടി|ਲੱਖ|ਕਰੋੜ)',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                amount = match.group(1) if match.groups() else match.group(0)
                entities.append(Entity(
                    type=EntityType.AMOUNT,
                    value=match.group(0),
                    confidence=0.85,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    language=language,
                    normalized_value=amount.replace(',', '')
                ))
        
        return entities
    
    def _extract_government_services(self, text: str, language: str) -> List[Entity]:
        """Extract government service mentions from text."""
        entities = []
        
        # Government service terms by language
        service_terms = {
            'en': ['pension', 'ration', 'card', 'certificate', 'license', 'subsidy', 'scheme', 'benefit', 'allowance'],
            'hi': ['पेंशन', 'राशन', 'कार्ड', 'प्रमाणपत्र', 'लाइसेंस', 'सब्सिडी', 'योजना', 'लाभ', 'भत्ता'],
            'ta': ['ஓய்வூதியம்', 'ரேஷன்', 'அட்டை', 'சான்றிதழ்', 'உரிமம்', 'மானியம்', 'திட்டம்', 'நன்மை', 'படி'],
            'te': ['పెన్షన్', 'రేషన్', 'కార్డ్', 'సర్టిఫికేట్', 'లైసెన్స్', 'సబ్సిడీ', 'పథకం', 'ప్రయోజనం', 'భత్యం'],
            'bn': ['পেনশন', 'রেশন', 'কার্ড', 'সার্টিফিকেট', 'লাইসেন্স', 'ভর্তুকি', 'প্রকল্প', 'সুবিধা', 'ভাতা'],
            'mr': ['पेन्शन', 'रेशन', 'कार्ड', 'प्रमाणपत्र', 'परवाना', 'अनुदान', 'योजना', 'लाभ', 'भत्ता'],
            'gu': ['પેન્શન', 'રાશન', 'કાર્ડ', 'પ્રમાણપત્ર', 'લાયસન્સ', 'સબસિડી', 'યોજના', 'લાભ', 'ભથ્થું'],
            'kn': ['ಪಿಂಚಣಿ', 'ರೇಷನ್', 'ಕಾರ್ಡ್', 'ಪ್ರಮಾಣಪತ್ರ', 'ಪರವಾನಗಿ', 'ಸಬ್ಸಿಡಿ', 'ಯೋಜನೆ', 'ಲಾಭ', 'ಭತ್ಯೆ'],
            'ml': ['പെൻഷൻ', 'റേഷൻ', 'കാർഡ്', 'സർട്ടിഫിക്കറ്റ്', 'ലൈസൻസ്', 'സബ്സിഡി', 'പദ്ധതി', 'ആനുകൂല്യം', 'അലവൻസ്'],
            'pa': ['ਪੈਨਸ਼ਨ', 'ਰਾਸ਼ਨ', 'ਕਾਰਡ', 'ਸਰਟੀਫਿਕੇਟ', 'ਲਾਇਸੈਂਸ', 'ਸਬਸਿਡੀ', 'ਸਕੀਮ', 'ਲਾਭ', 'ਭੱਤਾ']
        }
        
        terms = service_terms.get(language, service_terms['en'])
        
        for term in terms:
            pattern = r'\b' + re.escape(term) + r'\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(Entity(
                    type=EntityType.GOVERNMENT_SERVICE,
                    value=match.group(0),
                    confidence=0.8,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    language=language,
                    normalized_value=term.lower()
                ))
        
        return entities
    
    def _extract_document_types(self, text: str, language: str) -> List[Entity]:
        """Extract document type mentions from text."""
        entities = []
        
        # Document types by language
        doc_terms = {
            'en': ['aadhar', 'pan', 'passport', 'voter', 'driving', 'birth', 'income', 'caste', 'domicile'],
            'hi': ['आधार', 'पैन', 'पासपोर्ट', 'वोटर', 'ड्राइविंग', 'जन्म', 'आय', 'जाति', 'निवास'],
            'ta': ['ஆதார்', 'பான்', 'பாஸ்போர்ட்', 'வாக்காளர்', 'ஓட்டுநர்', 'பிறப்பு', 'வருமானம்', 'சாதி', 'வசிப்பிடம்'],
            'te': ['ఆధార్', 'పాన్', 'పాస్‌పోర్ట్', 'ఓటర్', 'డ్రైవింగ్', 'జన్మ', 'ఆదాయం', 'కుల', 'నివాస'],
            'bn': ['আধার', 'প্যান', 'পাসপোর্ট', 'ভোটার', 'ড্রাইভিং', 'জন্ম', 'আয়', 'জাতি', 'বাসস্থান'],
            'mr': ['आधार', 'पॅन', 'पासपोर्ट', 'मतदार', 'ड्रायव्हिंग', 'जन्म', 'उत्पन्न', 'जात', 'अधिवास'],
            'gu': ['આધાર', 'પાન', 'પાસપોર્ટ', 'મતદાર', 'ડ્રાઇવિંગ', 'જન્મ', 'આવક', 'જાતિ', 'નિવાસ'],
            'kn': ['ಆಧಾರ್', 'ಪ್ಯಾನ್', 'ಪಾಸ್‌ಪೋರ್ಟ್', 'ಮತದಾರ', 'ಚಾಲನಾ', 'ಜನ್ಮ', 'ಆದಾಯ', 'ಜಾತಿ', 'ನಿವಾಸ'],
            'ml': ['ആധാർ', 'പാൻ', 'പാസ്‌പോർട്ട്', 'വോട്ടർ', 'ഡ്രൈവിംഗ്', 'ജനനം', 'വരുമാനം', 'ജാതി', 'വസതി'],
            'pa': ['ਆਧਾਰ', 'ਪੈਨ', 'ਪਾਸਪੋਰਟ', 'ਵੋਟਰ', 'ਡਰਾਇਵਿੰਗ', 'ਜਨਮ', 'ਆਮਦਨ', 'ਜਾਤੀ', 'ਨਿਵਾਸ']
        }
        
        terms = doc_terms.get(language, doc_terms['en'])
        
        for term in terms:
            pattern = r'\b' + re.escape(term) + r'\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(Entity(
                    type=EntityType.DOCUMENT_TYPE,
                    value=match.group(0),
                    confidence=0.8,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    language=language,
                    normalized_value=term.lower()
                ))
        
        return entities
    
    def _extract_locations(self, text: str, language: str) -> List[Entity]:
        """Extract location mentions from text."""
        entities = []
        
        # Common Indian location patterns
        patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:district|जिला|జిల్లా|জেলা|જિલ્લો|जिल्हा|ಜಿಲ್ಲೆ|ജില്ല|ਜ਼ਿਲ੍ਹਾ)\b',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:state|राज्य|రాష్ట్రం|রাজ্য|રાજ્ય|राज्य|ರಾಜ್ಯ|സംസ്ഥാനം|ਰਾਜ)\b',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:city|शहर|నగరం|শহর|શહેર|शहर|ನಗರ|നഗരം|ਸ਼ਹਿਰ)\b',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                location = match.group(1)
                entities.append(Entity(
                    type=EntityType.LOCATION,
                    value=match.group(0),
                    confidence=0.7,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    language=language,
                    normalized_value=location.title()
                ))
        
        return entities
    
    def _extract_person_names(self, text: str, language: str) -> List[Entity]:
        """Extract person names from text."""
        entities = []
        
        # Simple name patterns (this could be enhanced with NER models)
        patterns = [
            r'\b(?:mr|mrs|ms|dr|prof|श्री|श्रीमती|डॉ|ಶ್ರೀ|ಶ್ರೀಮತಿ|డాక్టర్|শ্রী|শ্রীমতী|ડૉ|डॉ|ഡോ|ਡਾ)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b(?:name|नाम|ಹೆಸರು|పేరు|নাম|નામ|नाव|പേര്|ਨਾਮ)[\s:]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                name = match.group(1)
                entities.append(Entity(
                    type=EntityType.PERSON_NAME,
                    value=match.group(0),
                    confidence=0.6,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    language=language,
                    normalized_value=name.title()
                ))
        
        return entities
    
    def _extract_ages(self, text: str, language: str) -> List[Entity]:
        """Extract age mentions from text."""
        entities = []
        
        patterns = [
            r'\b(?:age|उम्र|ವಯಸ್ಸು|వయస్సు|বয়স|ઉંમર|वय|പ്രായം|ਉਮਰ)[\s:]*(\d{1,3})\b',
            r'\b(\d{1,3})[\s]*(?:years|year|साल|वर्ष|ವರ್ಷ|సంవత్సరాలు|বছর|વર્ષ|वर्षे|വർഷം|ਸਾਲ)\b',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                age = match.group(1)
                if 0 <= int(age) <= 120:  # Reasonable age range
                    entities.append(Entity(
                        type=EntityType.AGE,
                        value=match.group(0),
                        confidence=0.8,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        language=language,
                        normalized_value=age
                    ))
        
        return entities
    
    def _extract_income(self, text: str, language: str) -> List[Entity]:
        """Extract income mentions from text."""
        entities = []
        
        patterns = [
            r'\b(?:income|salary|आय|वेतन|ಆದಾಯ|ಸಂಬಳ|ఆదాయం|జీతం|আয়|বেতন|આવક|પગાર|उत्पन्न|पगार|വരുമാനം|ശമ്പളം|ਆਮਦਨ|ਤਨਖਾਹ)[\s:]*(?:rs|₹)?[\s]*(\d+(?:,\d+)*(?:\.\d+)?)\b',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                income = match.group(1)
                entities.append(Entity(
                    type=EntityType.INCOME,
                    value=match.group(0),
                    confidence=0.8,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    language=language,
                    normalized_value=income.replace(',', '')
                ))
        
        return entities
    
    def _extract_caste_categories(self, text: str, language: str) -> List[Entity]:
        """Extract caste category mentions from text."""
        entities = []
        
        # Caste categories
        categories = ['sc', 'st', 'obc', 'general', 'ews', 'अनुसूचित जाति', 'अनुसूचित जनजाति', 'अन्य पिछड़ा वर्ग', 'सामान्य']
        
        for category in categories:
            pattern = r'\b' + re.escape(category) + r'\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(Entity(
                    type=EntityType.CASTE_CATEGORY,
                    value=match.group(0),
                    confidence=0.9,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    language=language,
                    normalized_value=category.upper() if len(category) <= 3 else category.lower()
                ))
        
        return entities
    
    def _remove_overlapping_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove overlapping entities, keeping the one with highest confidence."""
        if not entities:
            return entities
        
        # Sort by start position, then by confidence (descending)
        entities.sort(key=lambda e: (e.start_pos, -e.confidence))
        
        filtered = []
        for entity in entities:
            # Check if this entity overlaps with any already selected entity
            overlaps = False
            for selected in filtered:
                if (entity.start_pos < selected.end_pos and 
                    entity.end_pos > selected.start_pos):
                    overlaps = True
                    break
            
            if not overlaps:
                filtered.append(entity)
        
        return filtered
    
    def _load_entity_patterns(self) -> Dict[str, Any]:
        """Load entity extraction patterns."""
        # This could be loaded from configuration files
        return {}
    
    def _load_normalization_rules(self) -> Dict[str, Any]:
        """Load normalization rules for entities."""
        # This could be loaded from configuration files
        return {}