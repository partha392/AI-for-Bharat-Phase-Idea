"""
Data format transformation and validation for government APIs.

This module handles transformation of grievance data between different
formats required by various government portals, including validation
and field mapping.
"""

import json
import logging
import re
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union, Callable
from decimal import Decimal
import xml.etree.ElementTree as ET

from .models import (
    TransformationRule, ValidationResult, DataFormat,
    GovernmentPortal, APIEndpoint
)
from ..grievance.models import (
    GrievanceRecord, GrievanceType, GrievancePriority,
    ContactInformation, GrievanceDetails, DocumentReference
)
from ..core.exceptions import ValidationError, GovernmentAPIError

logger = logging.getLogger(__name__)


class DataTransformer:
    """
    Transforms and validates data for government API integration.
    
    Handles conversion between internal data models and various
    government portal formats including field mapping, validation,
    and format conversion.
    """
    
    def __init__(self):
        """Initialize the data transformer."""
        self.transformation_rules: Dict[str, List[TransformationRule]] = {}
        self.validation_patterns: Dict[str, str] = {}
        self.field_mappings: Dict[str, Dict[str, str]] = {}
        self.format_converters: Dict[DataFormat, Callable] = {}
        
        self._initialize_default_rules()
        self._initialize_validation_patterns()
        self._initialize_format_converters()
        
        logger.info("DataTransformer initialized")
    
    def _initialize_default_rules(self):
        """Initialize default transformation rules for common government portals."""
        
        # Central Government Portal Rules
        central_gov_rules = [
            TransformationRule(
                source_field="details.problem_description",
                target_field="complaint_description",
                transformation_type="direct",
                required=True
            ),
            TransformationRule(
                source_field="details.grievance_type",
                target_field="category_code",
                transformation_type="lookup",
                required=True
            ),
            TransformationRule(
                source_field="contact_info.phone_number",
                target_field="mobile_number",
                transformation_type="format",
                format_pattern="+91{0}",
                required=True
            ),
            TransformationRule(
                source_field="contact_info.email",
                target_field="email_id",
                transformation_type="direct",
                required=False
            ),
            TransformationRule(
                source_field="details.location",
                target_field="address",
                transformation_type="direct",
                required=True
            ),
            TransformationRule(
                source_field="language",
                target_field="preferred_language",
                transformation_type="lookup",
                required=False,
                default_value="hindi"
            )
        ]
        
        # State Government Portal Rules
        state_gov_rules = [
            TransformationRule(
                source_field="details.problem_description",
                target_field="grievance_details",
                transformation_type="direct",
                required=True
            ),
            TransformationRule(
                source_field="details.grievance_type",
                target_field="grievance_category",
                transformation_type="lookup",
                required=True
            ),
            TransformationRule(
                source_field="contact_info.phone_number",
                target_field="contact_number",
                transformation_type="direct",
                required=True
            ),
            TransformationRule(
                source_field="contact_info.email",
                target_field="email_address",
                transformation_type="direct",
                required=False
            ),
            TransformationRule(
                source_field="priority",
                target_field="urgency_level",
                transformation_type="lookup",
                required=False,
                default_value="medium"
            )
        ]
        
        self.transformation_rules["central_government"] = central_gov_rules
        self.transformation_rules["state_government"] = state_gov_rules
    
    def _initialize_validation_patterns(self):
        """Initialize validation patterns for common fields."""
        self.validation_patterns = {
            "phone_number": r"^[6-9]\d{9}$",  # Indian mobile number
            "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "pincode": r"^[1-9][0-9]{5}$",  # Indian PIN code
            "aadhar": r"^[2-9]{1}[0-9]{3}[0-9]{4}[0-9]{4}$",  # Aadhar number
            "pan": r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$",  # PAN number
            "reference_number": r"^[A-Z0-9]{6,20}$"
        }
    
    def _initialize_format_converters(self):
        """Initialize format converters for different data formats."""
        self.format_converters = {
            DataFormat.JSON: self._to_json,
            DataFormat.XML: self._to_xml,
            DataFormat.FORM_DATA: self._to_form_data,
            DataFormat.SOAP: self._to_soap
        }
    
    def transform_grievance_data(self, grievance: GrievanceRecord, 
                               portal: GovernmentPortal,
                               endpoint: APIEndpoint) -> ValidationResult:
        """
        Transform grievance data for a specific government portal.
        
        Args:
            grievance: Grievance record to transform
            portal: Target government portal
            endpoint: API endpoint configuration
            
        Returns:
            ValidationResult with transformed data or errors
        """
        try:
            # Get transformation rules for portal
            rules = self._get_transformation_rules(portal)
            
            # Extract source data from grievance
            source_data = self._extract_source_data(grievance)
            
            # Apply transformation rules
            transformed_data = {}
            validation_result = ValidationResult(is_valid=True)
            
            for rule in rules:
                try:
                    value = self._apply_transformation_rule(rule, source_data)
                    
                    if value is not None:
                        transformed_data[rule.target_field] = value
                    elif rule.required:
                        validation_result.add_missing_field(rule.target_field)
                        validation_result.add_error(
                            f"Required field '{rule.target_field}' could not be transformed from '{rule.source_field}'"
                        )
                    
                except Exception as e:
                    logger.error(f"Failed to apply transformation rule for {rule.target_field}: {e}")
                    validation_result.add_error(
                        f"Transformation failed for field '{rule.target_field}': {e}"
                    )
            
            # Add metadata
            transformed_data.update({
                "submission_timestamp": datetime.now().isoformat(),
                "source_system": "bharat_voice_assistant",
                "data_version": "1.0"
            })
            
            # Validate transformed data
            self._validate_transformed_data(transformed_data, endpoint, validation_result)
            
            # Convert to required format
            if validation_result.is_valid:
                formatted_data = self._convert_to_format(transformed_data, endpoint.data_format)
                validation_result.transformed_data = formatted_data
            
            logger.info(f"Data transformation completed for portal {portal.id}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Data transformation failed for portal {portal.id}: {e}")
            result = ValidationResult(is_valid=False)
            result.add_error(f"Data transformation failed: {e}")
            return result
    
    def _get_transformation_rules(self, portal: GovernmentPortal) -> List[TransformationRule]:
        """Get transformation rules for a portal."""
        # Try to get specific rules for portal
        portal_rules = self.transformation_rules.get(portal.id)
        if portal_rules:
            return portal_rules
        
        # Fall back to portal type rules
        type_rules = self.transformation_rules.get(portal.portal_type.value)
        if type_rules:
            return type_rules
        
        # Use default central government rules
        return self.transformation_rules.get("central_government", [])
    
    def _extract_source_data(self, grievance: GrievanceRecord) -> Dict[str, Any]:
        """Extract source data from grievance record."""
        data = {}
        
        # Basic grievance information
        data["id"] = str(grievance.id)
        data["reference_number"] = grievance.reference_number
        data["user_id"] = grievance.user_id
        data["session_id"] = grievance.session_id
        data["status"] = grievance.status.value
        data["priority"] = grievance.priority.value
        data["language"] = grievance.language
        data["source_channel"] = grievance.source_channel
        data["created_at"] = grievance.created_at.isoformat()
        data["updated_at"] = grievance.updated_at.isoformat()
        
        # Grievance details
        if grievance.details:
            details = grievance.details
            data["details"] = {
                "problem_description": details.problem_description,
                "grievance_type": details.grievance_type.value,
                "affected_service": details.affected_service,
                "department": details.department,
                "location": details.location,
                "incident_date": details.incident_date.isoformat() if details.incident_date else None,
                "previous_complaint_reference": details.previous_complaint_reference,
                "expected_resolution": details.expected_resolution,
                "urgency_reason": details.urgency_reason
            }
        
        # Contact information
        if grievance.contact_info:
            contact = grievance.contact_info
            data["contact_info"] = {
                "phone_number": contact.phone_number,
                "email": contact.email,
                "address": contact.address,
                "preferred_contact_method": contact.preferred_contact_method,
                "preferred_language": contact.preferred_language
            }
        
        # Documents
        if grievance.documents:
            data["documents"] = []
            for doc in grievance.documents:
                data["documents"].append({
                    "document_type": doc.document_type,
                    "document_number": doc.document_number,
                    "issuing_authority": doc.issuing_authority,
                    "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
                    "is_required": doc.is_required,
                    "is_available": doc.is_available,
                    "file_path": doc.file_path
                })
        
        return data
    
    def _apply_transformation_rule(self, rule: TransformationRule, 
                                 source_data: Dict[str, Any]) -> Any:
        """Apply a single transformation rule."""
        # Get source value using dot notation
        value = self._get_nested_value(source_data, rule.source_field)
        
        if value is None:
            return rule.default_value
        
        # Apply transformation based on type
        if rule.transformation_type == "direct":
            return value
        
        elif rule.transformation_type == "format" and rule.format_pattern:
            if isinstance(value, str) and "{0}" in rule.format_pattern:
                return rule.format_pattern.format(value)
            else:
                return rule.format_pattern.format(value)
        
        elif rule.transformation_type == "lookup":
            return self._apply_lookup_transformation(rule.target_field, value)
        
        elif rule.transformation_type == "calculate":
            return self._apply_calculation_transformation(rule.transformation_function, value, source_data)
        
        else:
            return value
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _apply_lookup_transformation(self, field: str, value: Any) -> Any:
        """Apply lookup transformation for field values."""
        
        # Grievance type mappings
        if field in ["category_code", "grievance_category"]:
            grievance_type_mapping = {
                "pension_issue": "PENSION",
                "ration_card_issue": "RATION",
                "certificate_delay": "CERTIFICATE",
                "subsidy_delay": "SUBSIDY",
                "corruption_complaint": "CORRUPTION",
                "service_denial": "SERVICE_DENIAL",
                "document_issue": "DOCUMENT",
                "scheme_related": "SCHEME",
                "infrastructure": "INFRASTRUCTURE",
                "other": "OTHER"
            }
            return grievance_type_mapping.get(str(value).lower(), "OTHER")
        
        # Priority mappings
        elif field in ["urgency_level"]:
            priority_mapping = {
                "low": "LOW",
                "medium": "MEDIUM", 
                "high": "HIGH",
                "urgent": "URGENT"
            }
            return priority_mapping.get(str(value).lower(), "MEDIUM")
        
        # Language mappings
        elif field in ["preferred_language"]:
            language_mapping = {
                "hi": "hindi",
                "en": "english",
                "ta": "tamil",
                "te": "telugu",
                "bn": "bengali",
                "mr": "marathi",
                "gu": "gujarati",
                "kn": "kannada",
                "ml": "malayalam",
                "pa": "punjabi"
            }
            return language_mapping.get(str(value).lower(), "hindi")
        
        else:
            return value
    
    def _apply_calculation_transformation(self, function_name: str, 
                                        value: Any, source_data: Dict[str, Any]) -> Any:
        """Apply calculation transformation."""
        # This could be extended with a function registry
        if function_name == "format_phone":
            if isinstance(value, str) and len(value) == 10:
                return f"+91{value}"
        
        elif function_name == "calculate_age":
            # Calculate age from date of birth
            if isinstance(value, str):
                try:
                    birth_date = datetime.fromisoformat(value).date()
                    today = date.today()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    return age
                except:
                    return None
        
        return value
    
    def _validate_transformed_data(self, data: Dict[str, Any], 
                                 endpoint: APIEndpoint,
                                 validation_result: ValidationResult):
        """Validate transformed data against endpoint requirements."""
        
        # Check required fields
        for field in endpoint.required_fields:
            if field not in data or data[field] is None:
                validation_result.add_missing_field(field)
                validation_result.add_error(f"Required field '{field}' is missing")
        
        # Validate field formats
        for field, value in data.items():
            if isinstance(value, str):
                # Check for specific validation patterns
                if field.endswith("phone") or field.endswith("mobile"):
                    if not self._validate_pattern(value, "phone_number"):
                        validation_result.add_invalid_field(field)
                        validation_result.add_error(f"Invalid phone number format: {value}")
                
                elif field.endswith("email"):
                    if not self._validate_pattern(value, "email"):
                        validation_result.add_invalid_field(field)
                        validation_result.add_error(f"Invalid email format: {value}")
                
                elif field.endswith("pincode") or field.endswith("pin"):
                    if not self._validate_pattern(value, "pincode"):
                        validation_result.add_invalid_field(field)
                        validation_result.add_error(f"Invalid PIN code format: {value}")
    
    def _validate_pattern(self, value: str, pattern_name: str) -> bool:
        """Validate value against a pattern."""
        pattern = self.validation_patterns.get(pattern_name)
        if not pattern:
            return True  # No pattern to validate against
        
        return bool(re.match(pattern, value))
    
    def _convert_to_format(self, data: Dict[str, Any], format_type: DataFormat) -> Any:
        """Convert data to required format."""
        converter = self.format_converters.get(format_type)
        if not converter:
            return data  # Return as-is if no converter
        
        return converter(data)
    
    def _to_json(self, data: Dict[str, Any]) -> str:
        """Convert data to JSON format."""
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def _to_xml(self, data: Dict[str, Any], root_name: str = "grievance") -> str:
        """Convert data to XML format."""
        root = ET.Element(root_name)
        
        def add_element(parent, key, value):
            # Clean key name for XML
            clean_key = re.sub(r'[^a-zA-Z0-9_]', '_', str(key))
            element = ET.SubElement(parent, clean_key)
            
            if isinstance(value, dict):
                for k, v in value.items():
                    add_element(element, k, v)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        item_element = ET.SubElement(element, "item")
                        for k, v in item.items():
                            add_element(item_element, k, v)
                    else:
                        item_element = ET.SubElement(element, "item")
                        item_element.text = str(item) if item is not None else ""
            else:
                element.text = str(value) if value is not None else ""
        
        for key, value in data.items():
            add_element(root, key, value)
        
        return ET.tostring(root, encoding='unicode')
    
    def _to_form_data(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Convert data to form data format."""
        form_data = {}
        
        def flatten_dict(d, parent_key='', sep='_'):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            items.extend(flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                        else:
                            items.append((f"{new_key}_{i}", str(item) if item is not None else ""))
                else:
                    items.append((new_key, str(v) if v is not None else ""))
            return dict(items)
        
        return flatten_dict(data)
    
    def _to_soap(self, data: Dict[str, Any]) -> str:
        """Convert data to SOAP format."""
        # Basic SOAP envelope
        soap_template = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:gov="http://government.api/grievance">
    <soap:Header/>
    <soap:Body>
        <gov:SubmitGrievanceRequest>
            {body}
        </gov:SubmitGrievanceRequest>
    </soap:Body>
</soap:Envelope>'''
        
        # Convert data to XML body
        body_xml = self._dict_to_soap_body(data)
        return soap_template.format(body=body_xml)
    
    def _dict_to_soap_body(self, data: Dict[str, Any]) -> str:
        """Convert dictionary to SOAP body XML."""
        elements = []
        
        for key, value in data.items():
            clean_key = re.sub(r'[^a-zA-Z0-9_]', '_', str(key))
            
            if isinstance(value, dict):
                sub_elements = self._dict_to_soap_body(value)
                elements.append(f"<gov:{clean_key}>{sub_elements}</gov:{clean_key}>")
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        sub_elements = self._dict_to_soap_body(item)
                        elements.append(f"<gov:{clean_key}>{sub_elements}</gov:{clean_key}>")
                    else:
                        elements.append(f"<gov:{clean_key}>{item if item is not None else ''}</gov:{clean_key}>")
            else:
                elements.append(f"<gov:{clean_key}>{value if value is not None else ''}</gov:{clean_key}>")
        
        return '\n'.join(elements)
    
    def add_transformation_rule(self, portal_id: str, rule: TransformationRule):
        """Add a transformation rule for a specific portal."""
        if portal_id not in self.transformation_rules:
            self.transformation_rules[portal_id] = []
        
        self.transformation_rules[portal_id].append(rule)
        logger.info(f"Added transformation rule for portal {portal_id}: {rule.source_field} -> {rule.target_field}")
    
    def validate_field_value(self, field_name: str, value: Any) -> ValidationResult:
        """Validate a single field value."""
        result = ValidationResult(is_valid=True)
        
        if isinstance(value, str):
            # Determine validation pattern based on field name
            pattern_name = None
            
            if "phone" in field_name.lower() or "mobile" in field_name.lower():
                pattern_name = "phone_number"
            elif "email" in field_name.lower():
                pattern_name = "email"
            elif "pin" in field_name.lower():
                pattern_name = "pincode"
            elif "aadhar" in field_name.lower():
                pattern_name = "aadhar"
            elif "pan" in field_name.lower():
                pattern_name = "pan"
            elif "reference" in field_name.lower():
                pattern_name = "reference_number"
            
            if pattern_name and not self._validate_pattern(value, pattern_name):
                result.add_error(f"Invalid format for {field_name}: {value}")
        
        return result