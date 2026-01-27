"""
Intelligent scheme categorization and tagging system.

This module provides automated categorization and tagging of government schemes
based on their content, eligibility criteria, and benefits using machine learning
and rule-based approaches.
"""

import logging
from typing import Dict, List, Set, Tuple, Optional
import re
from collections import defaultdict

from .models import GovernmentScheme, SchemeCategory
from ..core.exceptions import CategorizationError

logger = logging.getLogger(__name__)


class SchemeCategorizer:
    """
    Intelligent categorizer for government schemes.
    
    Uses a combination of keyword matching, rule-based logic,
    and content analysis to automatically categorize and tag schemes.
    """
    
    def __init__(self):
        """Initialize the scheme categorizer."""
        self.category_keywords = self._load_category_keywords()
        self.tag_patterns = self._load_tag_patterns()
        self.beneficiary_patterns = self._load_beneficiary_patterns()
        
    def categorize_scheme(self, scheme: GovernmentScheme) -> Tuple[SchemeCategory, float, List[str]]:
        """
        Automatically categorize a government scheme.
        
        Args:
            scheme: The government scheme to categorize
            
        Returns:
            Tuple of (category, confidence_score, suggested_tags)
        """
        try:
            # Extract text content for analysis
            content = self._extract_content(scheme)
            
            # Calculate category scores
            category_scores = self._calculate_category_scores(content, scheme)
            
            # Determine best category
            best_category = max(category_scores.items(), key=lambda x: x[1])
            category, confidence = best_category
            
            # Generate tags
            tags = self._generate_tags(content, scheme, category)
            
            logger.info(f"Categorized scheme {scheme.scheme_id} as {category.value} with confidence {confidence:.2f}")
            
            return category, confidence, tags
            
        except Exception as e:
            logger.error(f"Error categorizing scheme {scheme.scheme_id}: {str(e)}")
            raise CategorizationError(f"Failed to categorize scheme: {str(e)}")
    
    def suggest_subcategory(self, scheme: GovernmentScheme, category: SchemeCategory) -> Optional[str]:
        """
        Suggest a subcategory based on the main category and scheme content.
        
        Args:
            scheme: The government scheme
            category: The main category
            
        Returns:
            Suggested subcategory or None
        """
        content = self._extract_content(scheme)
        subcategory_patterns = self._get_subcategory_patterns(category)
        
        best_match = None
        best_score = 0.0
        
        for subcategory, patterns in subcategory_patterns.items():
            score = self._calculate_pattern_score(content, patterns)
            if score > best_score:
                best_score = score
                best_match = subcategory
        
        return best_match if best_score > 0.3 else None
    
    def generate_comprehensive_tags(self, scheme: GovernmentScheme) -> List[str]:
        """
        Generate comprehensive tags for a scheme.
        
        Args:
            scheme: The government scheme
            
        Returns:
            List of relevant tags
        """
        content = self._extract_content(scheme)
        tags = set()
        
        # Add category-based tags
        tags.update(self._get_category_tags(scheme.category))
        
        # Add beneficiary-based tags
        tags.update(self._extract_beneficiary_tags(content, scheme))
        
        # Add location-based tags
        tags.update(self._extract_location_tags(scheme))
        
        # Add benefit-based tags
        tags.update(self._extract_benefit_tags(scheme))
        
        # Add process-based tags
        tags.update(self._extract_process_tags(scheme))
        
        # Add demographic tags
        tags.update(self._extract_demographic_tags(scheme))
        
        return sorted(list(tags))
    
    def _extract_content(self, scheme: GovernmentScheme) -> str:
        """Extract all textual content from a scheme for analysis."""
        content_parts = [
            scheme.name or "",
            scheme.name_hi or "",
            scheme.description or "",
            scheme.description_hi or "",
            scheme.department or "",
            scheme.ministry or "",
            scheme.subcategory or "",
            scheme.benefits.description or ""
        ]
        
        # Add regional names and descriptions
        content_parts.extend(scheme.name_regional.values())
        content_parts.extend(scheme.description_regional.values())
        
        # Add application process steps
        content_parts.extend(scheme.application_process.steps)
        
        return " ".join(content_parts).lower()
    
    def _calculate_category_scores(self, content: str, scheme: GovernmentScheme) -> Dict[SchemeCategory, float]:
        """Calculate scores for each category based on content analysis."""
        scores = defaultdict(float)
        
        # Keyword-based scoring
        for category, keywords in self.category_keywords.items():
            keyword_score = self._calculate_keyword_score(content, keywords)
            scores[category] += keyword_score * 0.4
        
        # Department-based scoring
        dept_score = self._calculate_department_score(scheme.department, scheme.ministry)
        for category, score in dept_score.items():
            scores[category] += score * 0.3
        
        # Eligibility-based scoring
        eligibility_score = self._calculate_eligibility_score(scheme.eligibility_criteria)
        for category, score in eligibility_score.items():
            scores[category] += score * 0.2
        
        # Benefits-based scoring
        benefits_score = self._calculate_benefits_score(scheme.benefits)
        for category, score in benefits_score.items():
            scores[category] += score * 0.1
        
        # Normalize scores
        max_score = max(scores.values()) if scores else 1.0
        if max_score > 0:
            scores = {k: v / max_score for k, v in scores.items()}
        
        return dict(scores)
    
    def _calculate_keyword_score(self, content: str, keywords: List[str]) -> float:
        """Calculate keyword matching score."""
        if not keywords:
            return 0.0
        
        matches = 0
        total_weight = 0
        
        for keyword in keywords:
            weight = len(keyword.split())  # Multi-word keywords get higher weight
            if keyword in content:
                matches += weight
            total_weight += weight
        
        return matches / total_weight if total_weight > 0 else 0.0
    
    def _calculate_department_score(self, department: str, ministry: Optional[str]) -> Dict[SchemeCategory, float]:
        """Calculate category scores based on department and ministry."""
        scores = defaultdict(float)
        
        dept_lower = department.lower() if department else ""
        ministry_lower = ministry.lower() if ministry else ""
        
        # Department mappings
        dept_mappings = {
            'agriculture': SchemeCategory.AGRICULTURE,
            'education': SchemeCategory.EDUCATION,
            'health': SchemeCategory.HEALTH,
            'housing': SchemeCategory.HOUSING,
            'employment': SchemeCategory.EMPLOYMENT,
            'rural development': SchemeCategory.RURAL_DEVELOPMENT,
            'women': SchemeCategory.WOMEN_EMPOWERMENT,
            'disability': SchemeCategory.DISABILITY,
            'social security': SchemeCategory.SOCIAL_SECURITY,
            'financial': SchemeCategory.FINANCIAL_INCLUSION
        }
        
        for keyword, category in dept_mappings.items():
            if keyword in dept_lower or keyword in ministry_lower:
                scores[category] += 1.0
        
        return dict(scores)
    
    def _calculate_eligibility_score(self, criteria) -> Dict[SchemeCategory, float]:
        """Calculate category scores based on eligibility criteria."""
        scores = defaultdict(float)
        
        # Age-based categorization
        if criteria.age_min is not None and criteria.age_min >= 60:
            scores[SchemeCategory.SENIOR_CITIZEN] += 0.8
        elif criteria.age_max is not None and criteria.age_max <= 18:
            scores[SchemeCategory.EDUCATION] += 0.6
        
        # Gender-based categorization
        if criteria.gender == 'female':
            scores[SchemeCategory.WOMEN_EMPOWERMENT] += 0.7
        
        # Location-based categorization
        if criteria.location_type == 'rural':
            scores[SchemeCategory.RURAL_DEVELOPMENT] += 0.5
            scores[SchemeCategory.AGRICULTURE] += 0.3
        
        # Disability-based categorization
        if criteria.disability_status is True:
            scores[SchemeCategory.DISABILITY] += 1.0
        
        # Income-based categorization
        if criteria.income_limit is not None and criteria.income_limit < 200000:
            scores[SchemeCategory.SOCIAL_SECURITY] += 0.4
            scores[SchemeCategory.FINANCIAL_INCLUSION] += 0.3
        
        return dict(scores)
    
    def _calculate_benefits_score(self, benefits) -> Dict[SchemeCategory, float]:
        """Calculate category scores based on benefits."""
        scores = defaultdict(float)
        
        # Financial assistance patterns
        if benefits.financial_assistance is not None:
            if benefits.financial_assistance > 100000:
                scores[SchemeCategory.HOUSING] += 0.5
            else:
                scores[SchemeCategory.SOCIAL_SECURITY] += 0.3
        
        # Loan-based benefits
        if benefits.loan_amount is not None:
            scores[SchemeCategory.FINANCIAL_INCLUSION] += 0.6
            if benefits.loan_amount > 500000:
                scores[SchemeCategory.HOUSING] += 0.4
            else:
                scores[SchemeCategory.EMPLOYMENT] += 0.3
        
        # Insurance coverage
        if benefits.insurance_coverage is not None:
            scores[SchemeCategory.HEALTH] += 0.7
            scores[SchemeCategory.SOCIAL_SECURITY] += 0.4
        
        # Training and equipment
        if benefits.training_provided:
            scores[SchemeCategory.EMPLOYMENT] += 0.5
            scores[SchemeCategory.EDUCATION] += 0.3
        
        if benefits.equipment_provided:
            scores[SchemeCategory.AGRICULTURE] += 0.4
            scores[SchemeCategory.EMPLOYMENT] += 0.3
        
        return dict(scores)
    
    def _generate_tags(self, content: str, scheme: GovernmentScheme, category: SchemeCategory) -> List[str]:
        """Generate relevant tags for the scheme."""
        tags = set()
        
        # Add category-specific tags
        tags.update(self._get_category_tags(category))
        
        # Add pattern-based tags
        for pattern, tag_list in self.tag_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                tags.update(tag_list)
        
        # Add beneficiary tags
        tags.update(self._extract_beneficiary_tags(content, scheme))
        
        # Limit to most relevant tags
        return sorted(list(tags))[:15]
    
    def _extract_beneficiary_tags(self, content: str, scheme: GovernmentScheme) -> Set[str]:
        """Extract beneficiary-related tags."""
        tags = set()
        
        for pattern, tag in self.beneficiary_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                tags.add(tag)
        
        # Add eligibility-based tags
        criteria = scheme.eligibility_criteria
        if criteria.age_min is not None and criteria.age_min >= 60:
            tags.add("senior_citizens")
        if criteria.gender == 'female':
            tags.add("women")
        if criteria.location_type == 'rural':
            tags.add("rural")
        if criteria.disability_status is True:
            tags.add("disabled")
        
        return tags
    
    def _extract_location_tags(self, scheme: GovernmentScheme) -> Set[str]:
        """Extract location-based tags."""
        tags = set()
        
        if scheme.target_states:
            if len(scheme.target_states) <= 5:
                tags.update([f"state_{state.lower()}" for state in scheme.target_states])
            else:
                tags.add("national")
        
        if scheme.eligibility_criteria.location_type:
            tags.add(scheme.eligibility_criteria.location_type)
        
        return tags
    
    def _extract_benefit_tags(self, scheme: GovernmentScheme) -> Set[str]:
        """Extract benefit-related tags."""
        tags = set()
        
        benefits = scheme.benefits
        if benefits.financial_assistance is not None:
            tags.add("financial_assistance")
            if benefits.financial_assistance > 100000:
                tags.add("high_value")
        
        if benefits.loan_amount is not None:
            tags.add("loan")
        
        if benefits.insurance_coverage is not None:
            tags.add("insurance")
        
        if benefits.training_provided:
            tags.add("training")
        
        if benefits.equipment_provided:
            tags.add("equipment")
        
        if benefits.subsidy_percentage is not None:
            tags.add("subsidy")
        
        return tags
    
    def _extract_process_tags(self, scheme: GovernmentScheme) -> Set[str]:
        """Extract process-related tags."""
        tags = set()
        
        process = scheme.application_process
        if 'online' in process.application_mode:
            tags.add("online_application")
        
        if process.application_fee is not None and process.application_fee == 0:
            tags.add("free_application")
        
        if process.processing_time_days is not None:
            if process.processing_time_days <= 30:
                tags.add("fast_processing")
            elif process.processing_time_days > 90:
                tags.add("slow_processing")
        
        return tags
    
    def _extract_demographic_tags(self, scheme: GovernmentScheme) -> Set[str]:
        """Extract demographic-related tags."""
        tags = set()
        
        criteria = scheme.eligibility_criteria
        
        # Age-based tags
        if criteria.age_min is not None or criteria.age_max is not None:
            if criteria.age_max is not None and criteria.age_max <= 25:
                tags.add("youth")
            elif criteria.age_min is not None and criteria.age_min >= 60:
                tags.add("elderly")
        
        # Income-based tags
        if criteria.income_limit is not None:
            if criteria.income_limit <= 100000:
                tags.add("below_poverty_line")
            elif criteria.income_limit <= 300000:
                tags.add("low_income")
        
        # Education-based tags
        if criteria.education_level:
            tags.add(f"education_{criteria.education_level.lower()}")
        
        return tags
    
    def _get_category_tags(self, category: SchemeCategory) -> List[str]:
        """Get standard tags for a category."""
        category_tags = {
            SchemeCategory.AGRICULTURE: ["farming", "agriculture", "rural", "crops"],
            SchemeCategory.EDUCATION: ["education", "learning", "students", "schools"],
            SchemeCategory.HEALTH: ["health", "medical", "healthcare", "treatment"],
            SchemeCategory.HOUSING: ["housing", "shelter", "construction", "home"],
            SchemeCategory.EMPLOYMENT: ["employment", "jobs", "work", "livelihood"],
            SchemeCategory.SOCIAL_SECURITY: ["social_security", "welfare", "support"],
            SchemeCategory.RURAL_DEVELOPMENT: ["rural", "development", "villages"],
            SchemeCategory.WOMEN_EMPOWERMENT: ["women", "empowerment", "female"],
            SchemeCategory.DISABILITY: ["disability", "disabled", "special_needs"],
            SchemeCategory.SENIOR_CITIZEN: ["senior_citizen", "elderly", "pension"],
            SchemeCategory.FINANCIAL_INCLUSION: ["financial", "banking", "credit"]
        }
        return category_tags.get(category, [])
    
    def _get_subcategory_patterns(self, category: SchemeCategory) -> Dict[str, List[str]]:
        """Get subcategory patterns for a given category."""
        patterns = {
            SchemeCategory.AGRICULTURE: {
                "crop_insurance": ["crop insurance", "fasal bima", "insurance"],
                "irrigation": ["irrigation", "water", "drip", "sprinkler"],
                "seeds_fertilizer": ["seeds", "fertilizer", "inputs"],
                "machinery": ["machinery", "equipment", "tractor", "harvester"],
                "organic_farming": ["organic", "natural", "bio"],
                "animal_husbandry": ["animal", "livestock", "dairy", "poultry"]
            },
            SchemeCategory.EDUCATION: {
                "scholarships": ["scholarship", "financial aid", "fee"],
                "infrastructure": ["school building", "infrastructure", "classroom"],
                "teacher_training": ["teacher", "training", "capacity"],
                "digital_education": ["digital", "computer", "technology"],
                "vocational_training": ["vocational", "skill", "trade"]
            },
            SchemeCategory.HEALTH: {
                "insurance": ["insurance", "coverage", "premium"],
                "maternal_health": ["maternal", "pregnancy", "child"],
                "immunization": ["immunization", "vaccination", "vaccine"],
                "nutrition": ["nutrition", "food", "malnutrition"],
                "mental_health": ["mental", "psychological", "counseling"]
            }
        }
        return patterns.get(category, {})
    
    def _calculate_pattern_score(self, content: str, patterns: List[str]) -> float:
        """Calculate score for pattern matching."""
        if not patterns:
            return 0.0
        
        matches = sum(1 for pattern in patterns if pattern in content)
        return matches / len(patterns)
    
    def _load_category_keywords(self) -> Dict[SchemeCategory, List[str]]:
        """Load category-specific keywords."""
        return {
            SchemeCategory.AGRICULTURE: [
                "agriculture", "farming", "crop", "farmer", "irrigation", "seeds",
                "fertilizer", "pesticide", "harvest", "livestock", "dairy", "poultry",
                "fisheries", "horticulture", "organic", "kisan", "krishi", "fasal"
            ],
            SchemeCategory.EDUCATION: [
                "education", "school", "student", "scholarship", "learning", "study",
                "teacher", "classroom", "university", "college", "skill", "training",
                "vidya", "shiksha", "adhyayan", "padhna"
            ],
            SchemeCategory.HEALTH: [
                "health", "medical", "hospital", "doctor", "treatment", "medicine",
                "healthcare", "clinic", "surgery", "insurance", "ayushman", "swasthya",
                "chikitsa", "dawai", "ilaj"
            ],
            SchemeCategory.HOUSING: [
                "housing", "house", "home", "shelter", "construction", "building",
                "awas", "ghar", "makan", "nirman", "pradhan mantri awas"
            ],
            SchemeCategory.EMPLOYMENT: [
                "employment", "job", "work", "livelihood", "income", "wage",
                "rozgar", "kaam", "naukri", "vyavasaya", "udyog"
            ],
            SchemeCategory.SOCIAL_SECURITY: [
                "pension", "welfare", "support", "assistance", "security", "protection",
                "samajik suraksha", "sahayata", "madad", "pension"
            ],
            SchemeCategory.RURAL_DEVELOPMENT: [
                "rural", "village", "gram", "development", "infrastructure",
                "grameen", "gaon", "vikas", "panchayat"
            ],
            SchemeCategory.WOMEN_EMPOWERMENT: [
                "women", "female", "girl", "mother", "empowerment", "mahila",
                "stree", "nari", "shakti", "beti"
            ],
            SchemeCategory.DISABILITY: [
                "disability", "disabled", "handicapped", "special needs", "divyang",
                "viklang", "apang"
            ],
            SchemeCategory.SENIOR_CITIZEN: [
                "senior citizen", "elderly", "old age", "pension", "vridha",
                "buzurg", "varishtha"
            ],
            SchemeCategory.FINANCIAL_INCLUSION: [
                "financial", "bank", "credit", "loan", "savings", "insurance",
                "vittiya", "arthik", "rin", "bachat"
            ]
        }
    
    def _load_tag_patterns(self) -> Dict[str, List[str]]:
        """Load tag patterns for content analysis."""
        return {
            r'\b(loan|credit|rin)\b': ["loan", "credit"],
            r'\b(insurance|bima)\b': ["insurance"],
            r'\b(subsidy|anudan)\b': ["subsidy"],
            r'\b(training|prashikshan)\b': ["training"],
            r'\b(scholarship|chhatravritti)\b': ["scholarship"],
            r'\b(pension|pension)\b': ["pension"],
            r'\b(free|muft|nishulk)\b': ["free"],
            r'\b(online|digital)\b': ["online", "digital"],
            r'\b(rural|grameen|gaon)\b': ["rural"],
            r'\b(urban|shahari|nagar)\b': ["urban"],
            r'\b(women|mahila|stree)\b': ["women"],
            r'\b(youth|yuva|naujawan)\b': ["youth"],
            r'\b(farmer|kisan)\b': ["farmer"],
            r'\b(small business|laghu udyog)\b': ["small_business"],
            r'\b(self help|swayam sahayata)\b': ["self_help_group"]
        }
    
    def _load_beneficiary_patterns(self) -> Dict[str, str]:
        """Load beneficiary patterns for tag extraction."""
        return {
            r'\b(farmer|kisan|krishi)\b': "farmers",
            r'\b(women|mahila|stree)\b': "women",
            r'\b(youth|yuva|naujawan)\b': "youth",
            r'\b(senior|elderly|vridha|buzurg)\b': "senior_citizens",
            r'\b(disabled|divyang|viklang)\b': "disabled",
            r'\b(student|vidyarthi|chatra)\b': "students",
            r'\b(worker|shramik|mazdoor)\b': "workers",
            r'\b(entrepreneur|udyami)\b': "entrepreneurs",
            r'\b(artisan|karigar|shilpkar)\b': "artisans",
            r'\b(tribal|adivasi|janajati)\b': "tribal",
            r'\b(minority|alpsankhyak)\b': "minority"
        }