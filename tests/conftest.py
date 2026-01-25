"""
Pytest configuration and shared fixtures for the Bharat Voice Assistant tests.

This module provides common test fixtures, configuration, and utilities
used across all test modules.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, Generator
import os

# Import hypothesis for property-based testing configuration
from hypothesis import settings, Verbosity, HealthCheck

# Configure Hypothesis for property-based testing
settings.register_profile("dev", 
    max_examples=100,
    verbosity=Verbosity.normal,
    suppress_health_check=[HealthCheck.too_slow]
)

settings.register_profile("ci", 
    max_examples=1000,
    verbosity=Verbosity.verbose,
    deadline=None
)

# Use dev profile by default
settings.load_profile("dev")

# Import application modules
from bharat_voice_assistant.core.config import Config
from bharat_voice_assistant.core.logging import setup_logging


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config():
    """Create a test configuration."""
    # Set test environment
    os.environ["ENVIRONMENT"] = "test"
    
    config = Config(env="test")
    
    # Override settings for testing
    config.aws.region = "us-east-1"  # Use US East for testing
    config.database.database = "bharat_voice_assistant_test"
    config.voice.recognition_confidence_threshold = 0.5  # Lower threshold for testing
    config.network.connection_timeout = 5  # Shorter timeout for tests
    config.security.voice_data_retention_hours = 1  # Short retention for tests
    
    return config


@pytest.fixture(scope="session")
def test_logging():
    """Set up test logging configuration."""
    setup_logging(log_level="DEBUG", log_format="simple")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_aws_clients():
    """Mock AWS service clients."""
    clients = {
        'transcribe': Mock(),
        'polly': Mock(),
        'comprehend': Mock(),
        's3': Mock(),
        'dynamodb': Mock(),
        'cloudwatch': Mock(),
        'sts': Mock(),
    }
    
    # Configure common mock responses
    clients['sts'].get_caller_identity.return_value = {
        'UserId': 'test-user-id',
        'Account': '123456789012',
        'Arn': 'arn:aws:iam::123456789012:user/test-user'
    }
    
    clients['polly'].describe_voices.return_value = {
        'Voices': [
            {
                'Id': 'Aditi',
                'Name': 'Aditi',
                'Gender': 'Female',
                'LanguageCode': 'hi-IN',
                'LanguageName': 'Hindi'
            }
        ]
    }
    
    clients['transcribe'].list_transcription_jobs.return_value = {
        'TranscriptionJobSummaries': []
    }
    
    clients['comprehend'].detect_dominant_language.return_value = {
        'Languages': [
            {
                'LanguageCode': 'hi',
                'Score': 0.95
            }
        ]
    }
    
    return clients


@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing."""
    # Simple sine wave audio data (mock)
    import numpy as np
    
    sample_rate = 16000
    duration = 1.0  # 1 second
    frequency = 440  # A4 note
    
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = np.sin(2 * np.pi * frequency * t)
    
    return {
        'data': audio_data,
        'sample_rate': sample_rate,
        'duration': duration,
        'format': 'wav'
    }


@pytest.fixture
def sample_user_profile():
    """Generate sample user profile data."""
    return {
        'user_id': 'test-user-123',
        'preferred_language': 'hi',
        'location': {
            'state': 'Maharashtra',
            'district': 'Mumbai',
            'block': 'Andheri'
        },
        'demographics': {
            'age_group': '25-35',
            'income_category': 'below_poverty_line',
            'education_level': 'primary'
        },
        'communication_preferences': {
            'voice_notifications': True,
            'sms_notifications': False,
            'email_notifications': False
        }
    }


@pytest.fixture
def sample_government_schemes():
    """Generate sample government scheme data."""
    return [
        {
            'scheme_id': 'pmay-g-001',
            'name': 'Pradhan Mantri Awas Yojana - Gramin',
            'name_hi': 'प्रधान मंत्री आवास योजना - ग्रामीण',
            'department': 'Ministry of Rural Development',
            'category': 'housing',
            'eligibility_criteria': {
                'income_limit': 200000,
                'location_type': 'rural',
                'housing_status': 'homeless_or_inadequate'
            },
            'benefits': {
                'financial_assistance': 120000,
                'description': 'Financial assistance for construction of pucca house'
            },
            'required_documents': [
                'aadhaar_card',
                'income_certificate',
                'bank_account_details',
                'land_documents'
            ],
            'application_process': [
                'Visit Common Service Center',
                'Fill application form',
                'Submit required documents',
                'Wait for verification',
                'Receive approval and funds'
            ]
        },
        {
            'scheme_id': 'pmkisan-001',
            'name': 'PM-KISAN',
            'name_hi': 'पीएम-किसान',
            'department': 'Ministry of Agriculture',
            'category': 'agriculture',
            'eligibility_criteria': {
                'occupation': 'farmer',
                'land_ownership': 'small_marginal',
                'land_size_max': 2.0  # hectares
            },
            'benefits': {
                'financial_assistance': 6000,
                'description': 'Annual financial assistance of Rs. 6000 in three installments'
            },
            'required_documents': [
                'aadhaar_card',
                'bank_account_details',
                'land_ownership_documents'
            ],
            'application_process': [
                'Register on PM-KISAN portal',
                'Fill farmer details',
                'Upload documents',
                'Submit application',
                'Receive payments directly in bank account'
            ]
        }
    ]


@pytest.fixture
def sample_grievance_data():
    """Generate sample grievance data."""
    return {
        'grievance_id': 'GRV-2024-001',
        'user_id': 'test-user-123',
        'category': 'pension',
        'subcategory': 'delayed_payment',
        'description': 'My pension payment has been delayed for 3 months',
        'description_hi': 'मेरी पेंशन का भुगतान 3 महीने से देर से हो रहा है',
        'priority': 'high',
        'status': 'submitted',
        'submitted_date': '2024-01-15T10:30:00Z',
        'expected_resolution_date': '2024-02-15T10:30:00Z',
        'supporting_documents': [
            'pension_card_copy.pdf',
            'bank_statement.pdf'
        ],
        'contact_details': {
            'phone': '9876543210',
            'address': 'Village Rampur, Block Andheri, District Mumbai, Maharashtra'
        }
    }


@pytest.fixture
def sample_voice_input():
    """Generate sample voice input data."""
    return {
        'text': 'मुझे आवास योजना के बारे में जानकारी चाहिए',
        'text_en': 'I need information about housing scheme',
        'language': 'hi',
        'confidence': 0.85,
        'audio_quality': 'good',
        'background_noise': 'low',
        'speaker_characteristics': {
            'gender': 'male',
            'age_estimate': '35-45',
            'accent': 'maharashtrian'
        }
    }


@pytest.fixture
def mock_government_api():
    """Mock government API responses."""
    return {
        'scheme_search': {
            'status': 'success',
            'schemes': [
                {
                    'id': 'pmay-g-001',
                    'name': 'PM Awas Yojana',
                    'eligibility_match': 0.9
                }
            ]
        },
        'grievance_submit': {
            'status': 'success',
            'reference_number': 'GRV-2024-001',
            'estimated_resolution_days': 30
        },
        'status_check': {
            'status': 'in_progress',
            'current_stage': 'verification',
            'progress_percentage': 45,
            'last_updated': '2024-01-20T15:30:00Z',
            'next_action': 'Document verification in progress'
        }
    }


# Property-based testing utilities
class PropertyTestHelpers:
    """Helper class for property-based testing."""
    
    @staticmethod
    def is_valid_language_code(code: str) -> bool:
        """Check if language code is valid."""
        valid_codes = ['hi', 'en', 'ta', 'te', 'bn', 'mr', 'gu', 'kn', 'ml', 'pa']
        return code in valid_codes
    
    @staticmethod
    def is_valid_phone_number(phone: str) -> bool:
        """Check if phone number is valid Indian format."""
        import re
        pattern = r'^[6-9]\d{9}$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def is_valid_aadhaar(aadhaar: str) -> bool:
        """Check if Aadhaar number format is valid."""
        import re
        pattern = r'^\d{12}$'
        return bool(re.match(pattern, aadhaar))


@pytest.fixture
def property_helpers():
    """Provide property testing helper functions."""
    return PropertyTestHelpers()


# Performance testing utilities
@pytest.fixture
def performance_monitor():
    """Monitor for performance testing."""
    import time
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        def duration_ms(self):
            if self.start_time and self.end_time:
                return (self.end_time - self.start_time) * 1000
            return None
        
        def assert_duration_under(self, max_ms: float):
            duration = self.duration_ms()
            assert duration is not None, "Performance monitor not started/stopped"
            assert duration < max_ms, f"Operation took {duration:.2f}ms, expected under {max_ms}ms"
    
    return PerformanceMonitor()


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_environment():
    """Clean up environment after each test."""
    yield
    # Clean up any test artifacts
    # This runs after each test
    pass