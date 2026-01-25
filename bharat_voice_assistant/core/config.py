"""
Configuration management for the Bharat Voice Assistant.

This module handles all configuration settings including AWS credentials,
service endpoints, and environment-specific parameters.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AWSConfig:
    """AWS service configuration."""
    region: str = "ap-south-1"  # Mumbai region as primary
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    
    # AWS Service endpoints
    transcribe_endpoint: Optional[str] = None
    polly_endpoint: Optional[str] = None
    comprehend_endpoint: Optional[str] = None
    
    # S3 configuration
    s3_bucket_voice_data: str = "bharat-voice-data"
    s3_bucket_schemes: str = "bharat-schemes-data"
    s3_bucket_grievances: str = "bharat-grievances-data"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "bharat_voice_assistant"
    username: str = "postgres"
    password: str = ""
    ssl_mode: str = "prefer"
    
    # Connection pool settings
    min_connections: int = 5
    max_connections: int = 20
    connection_timeout: int = 30


@dataclass
class VoiceConfig:
    """Voice processing configuration."""
    # Speech recognition settings
    recognition_confidence_threshold: float = 0.7
    max_recognition_attempts: int = 3
    noise_reduction_enabled: bool = True
    
    # Text-to-speech settings
    default_voice_id: str = "Aditi"  # AWS Polly Hindi voice
    speech_rate: str = "medium"
    audio_format: str = "mp3"
    enable_neural_voices: bool = True
    tts_compression_enabled: bool = True
    
    # Bandwidth optimization
    auto_quality_adjustment: bool = True
    compression_quality_map: Dict[str, int] = None
    
    # Supported languages
    supported_languages: Dict[str, str] = None
    
    def __post_init__(self):
        if self.supported_languages is None:
            self.supported_languages = {
                "hi": "hi-IN",  # Hindi
                "en": "en-IN",  # English (India)
                "ta": "ta-IN",  # Tamil
                "te": "te-IN",  # Telugu
                "bn": "bn-IN",  # Bengali
                "mr": "mr-IN",  # Marathi
                "gu": "gu-IN",  # Gujarati
                "kn": "kn-IN",  # Kannada
                "ml": "ml-IN",  # Malayalam
                "pa": "pa-IN",  # Punjabi
            }
        
        if self.compression_quality_map is None:
            self.compression_quality_map = {
                "excellent": 128,  # High quality
                "good": 64,        # Medium quality
                "medium": 32,      # Low quality
                "slow": 16,        # Very low quality
                "poor": 16,        # Very low quality
                "very_poor": 16    # Very low quality
            }


@dataclass
class NetworkConfig:
    """Network and bandwidth configuration."""
    # Bandwidth thresholds (in kbps)
    low_bandwidth_threshold: int = 64
    high_quality_threshold: int = 256
    
    # Connection settings
    connection_timeout: int = 30
    read_timeout: int = 60
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    
    # Compression settings
    voice_compression_enabled: bool = True
    voice_compression_quality: int = 64  # kbps


@dataclass
class SecurityConfig:
    """Security and privacy configuration."""
    # Encryption settings
    encryption_algorithm: str = "AES-256-GCM"
    key_rotation_days: int = 90
    
    # Data retention settings
    voice_data_retention_hours: int = 24
    user_data_deletion_days: int = 30
    
    # Privacy settings
    require_explicit_consent: bool = True
    anonymize_logs: bool = True


class Config:
    """Main configuration class for the Bharat Voice Assistant."""
    
    def __init__(self, env: str = None):
        """Initialize configuration based on environment."""
        self.env = env or os.getenv("ENVIRONMENT", "development")
        self.aws = AWSConfig()
        self.database = DatabaseConfig()
        self.voice = VoiceConfig()
        self.network = NetworkConfig()
        self.security = SecurityConfig()
        
        self._load_from_environment()
        self._load_from_file()
    
    def _load_from_environment(self):
        """Load configuration from environment variables."""
        # AWS configuration
        self.aws.region = os.getenv("AWS_REGION", self.aws.region)
        self.aws.access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws.secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws.session_token = os.getenv("AWS_SESSION_TOKEN")
        
        # Database configuration
        self.database.host = os.getenv("DB_HOST", self.database.host)
        self.database.port = int(os.getenv("DB_PORT", str(self.database.port)))
        self.database.database = os.getenv("DB_NAME", self.database.database)
        self.database.username = os.getenv("DB_USER", self.database.username)
        self.database.password = os.getenv("DB_PASSWORD", self.database.password)
        
        # Voice configuration
        confidence_threshold = os.getenv("VOICE_CONFIDENCE_THRESHOLD")
        if confidence_threshold:
            self.voice.recognition_confidence_threshold = float(confidence_threshold)
    
    def _load_from_file(self):
        """Load configuration from file if it exists."""
        config_file = Path(f"config/{self.env}.yaml")
        if config_file.exists():
            # TODO: Implement YAML configuration loading
            pass
    
    def get_aws_credentials(self) -> Dict[str, Any]:
        """Get AWS credentials dictionary."""
        credentials = {
            "region_name": self.aws.region
        }
        
        if self.aws.access_key_id:
            credentials["aws_access_key_id"] = self.aws.access_key_id
        if self.aws.secret_access_key:
            credentials["aws_secret_access_key"] = self.aws.secret_access_key
        if self.aws.session_token:
            credentials["aws_session_token"] = self.aws.session_token
            
        return credentials
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.env.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.env.lower() == "development"


# Global configuration instance
config = Config()