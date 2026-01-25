"""
Unit tests for core infrastructure components.

This module tests the configuration, logging, monitoring, and AWS client
management components to ensure proper setup and functionality.
"""

import pytest
import os
import tempfile
import logging
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from bharat_voice_assistant.core.config import Config, AWSConfig, VoiceConfig
from bharat_voice_assistant.core.logging import (
    setup_logging, get_logger, PrivacyAwareFormatter, 
    StructuredFormatter, PerformanceLogger, LogPerformance
)
from bharat_voice_assistant.core.monitoring import (
    MetricsCollector, HealthMonitor, HealthCheck, Monitor
)
from bharat_voice_assistant.core.aws_client import (
    AWSClientManager, safe_aws_call, validate_aws_configuration
)
from bharat_voice_assistant.core.exceptions import (
    BharatVoiceAssistantError, ConfigurationError, AWSServiceError,
    ValidationError, handle_aws_error, handle_validation_error
)


class TestConfig:
    """Test configuration management."""
    
    def test_config_initialization(self):
        """Test basic configuration initialization."""
        config = Config(env="test")
        
        assert config.env == "test"
        assert isinstance(config.aws, AWSConfig)
        assert isinstance(config.voice, VoiceConfig)
        assert config.aws.region == "ap-south-1"  # Default region
    
    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            'AWS_REGION': 'us-west-2',
            'DB_HOST': 'test-db-host',
            'VOICE_CONFIDENCE_THRESHOLD': '0.8'
        }):
            config = Config(env="test")
            
            assert config.aws.region == "us-west-2"
            assert config.database.host == "test-db-host"
            assert config.voice.recognition_confidence_threshold == 0.8
    
    def test_aws_credentials_dict(self):
        """Test AWS credentials dictionary generation."""
        config = Config(env="test")
        config.aws.access_key_id = "test-key"
        config.aws.secret_access_key = "test-secret"
        
        credentials = config.get_aws_credentials()
        
        assert credentials["region_name"] == config.aws.region
        assert credentials["aws_access_key_id"] == "test-key"
        assert credentials["aws_secret_access_key"] == "test-secret"
    
    def test_supported_languages(self):
        """Test supported languages configuration."""
        config = Config(env="test")
        
        expected_languages = {
            "hi": "hi-IN", "en": "en-IN", "ta": "ta-IN", "te": "te-IN",
            "bn": "bn-IN", "mr": "mr-IN", "gu": "gu-IN", "kn": "kn-IN",
            "ml": "ml-IN", "pa": "pa-IN"
        }
        
        assert config.voice.supported_languages == expected_languages
    
    def test_environment_detection(self):
        """Test environment detection methods."""
        dev_config = Config(env="development")
        prod_config = Config(env="production")
        
        assert dev_config.is_development()
        assert not dev_config.is_production()
        assert prod_config.is_production()
        assert not prod_config.is_development()


class TestLogging:
    """Test logging configuration and functionality."""
    
    def test_privacy_aware_formatter(self):
        """Test privacy-aware log formatting."""
        formatter = PrivacyAwareFormatter()
        
        # Create a log record with sensitive data
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="User phone: 9876543210, Aadhaar: 123456789012, email: test@example.com",
            args=(), exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Check that sensitive data is masked
        assert "****PHONE****" in formatted
        assert "****AADHAAR****" in formatted
        assert "****EMAIL****" in formatted
        assert "9876543210" not in formatted
        assert "123456789012" not in formatted
        assert "test@example.com" not in formatted
    
    def test_structured_formatter(self):
        """Test structured JSON log formatting."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Test message", args=(), exc_info=None
        )
        record.user_id = "test-user"
        record.session_id = "test-session"
        
        formatted = formatter.format(record)
        
        # Should be valid JSON
        import json
        log_data = json.loads(formatted)
        
        assert log_data["message"] == "Test message"
        assert log_data["level"] == "INFO"
        assert log_data["user_id"] == "test-user"
        assert log_data["session_id"] == "test-session"
        assert "timestamp" in log_data
    
    def test_performance_logger(self):
        """Test performance logging functionality."""
        with patch('bharat_voice_assistant.core.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            perf_logger = PerformanceLogger()
            
            perf_logger.log_response_time("voice_processing", "transcribe", 150.5, "user-123", "hi")
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            assert "voice_processing.transcribe took 150.50ms" in call_args[0][0]
            assert call_args[1]["extra"]["component"] == "voice_processing"
            assert call_args[1]["extra"]["duration_ms"] == 150.5
    
    def test_log_performance_context_manager(self):
        """Test performance logging context manager."""
        with patch('bharat_voice_assistant.core.logging.get_performance_logger') as mock_get_perf:
            mock_perf_logger = Mock()
            mock_get_perf.return_value = mock_perf_logger
            
            with LogPerformance("test_component", "test_operation", "user-123", "hi"):
                # Simulate some work
                import time
                time.sleep(0.01)
            
            mock_perf_logger.log_response_time.assert_called_once()
            call_args = mock_perf_logger.log_response_time.call_args[0]
            
            assert call_args[0] == "test_component"
            assert call_args[1] == "test_operation"
            assert call_args[2] > 0  # Duration should be positive
    
    def test_logging_setup(self, temp_dir):
        """Test logging setup with different configurations."""
        # Test with temporary log directory
        with patch('bharat_voice_assistant.core.logging.Path') as mock_path:
            mock_path.return_value = temp_dir / "logs"
            
            setup_logging(log_level="DEBUG", log_format="simple")
            
            logger = get_logger("test_logger")
            assert logger.level <= logging.DEBUG


class TestMonitoring:
    """Test monitoring and metrics functionality."""
    
    def test_metrics_collector(self):
        """Test metrics collection functionality."""
        collector = MetricsCollector()
        
        # Test counter
        collector.increment_counter("test_counter", 5)
        assert collector.get_counter("test_counter") == 5
        
        collector.increment_counter("test_counter", 3)
        assert collector.get_counter("test_counter") == 8
        
        # Test gauge
        collector.set_gauge("test_gauge", 42.5)
        assert collector.get_gauge("test_gauge") == 42.5
        
        # Test timer
        collector.record_timer("test_timer", 100.0)
        collector.record_timer("test_timer", 200.0)
        collector.record_timer("test_timer", 150.0)
        
        stats = collector.get_timer_stats("test_timer")
        assert stats["count"] == 3
        assert stats["avg"] == 150.0
        assert stats["min"] == 100.0
        assert stats["max"] == 200.0
    
    def test_health_monitor(self):
        """Test health monitoring functionality."""
        monitor = HealthMonitor()
        
        # Create test health checks
        def passing_check():
            return True
        
        def failing_check():
            return False
        
        def exception_check():
            raise Exception("Test exception")
        
        # Register health checks
        monitor.register_health_check(HealthCheck(
            name="passing_test",
            check_function=passing_check,
            critical=True,
            description="Test passing check"
        ))
        
        monitor.register_health_check(HealthCheck(
            name="failing_test",
            check_function=failing_check,
            critical=False,
            description="Test failing check"
        ))
        
        monitor.register_health_check(HealthCheck(
            name="exception_test",
            check_function=exception_check,
            critical=True,
            description="Test exception check"
        ))
        
        # Run individual health checks
        assert monitor.run_health_check("passing_test") is True
        assert monitor.run_health_check("failing_test") is False
        assert monitor.run_health_check("exception_test") is False
        
        # Run all health checks
        results = monitor.run_all_health_checks()
        assert results["passing_test"] is True
        assert results["failing_test"] is False
        assert results["exception_test"] is False
        
        # Get health status
        status = monitor.get_health_status()
        assert status["healthy"] is False  # Critical check failed
        assert "exception_test" in status["critical_failures"]
        assert len(status["checks"]) == 3
    
    def test_monitor_initialization(self):
        """Test main monitor class initialization."""
        monitor = Monitor()
        
        assert isinstance(monitor.metrics, MetricsCollector)
        assert isinstance(monitor.health, HealthMonitor)
        
        # Check that default health checks are registered
        health_status = monitor.health.get_health_status()
        expected_checks = ["memory_usage", "disk_space", "aws_connectivity"]
        
        for check_name in expected_checks:
            assert check_name in health_status["checks"]


class TestAWSClient:
    """Test AWS client management."""
    
    @patch('bharat_voice_assistant.core.aws_client.boto3')
    def test_aws_client_manager_initialization(self, mock_boto3):
        """Test AWS client manager initialization."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        
        manager = AWSClientManager()
        
        # Test client creation
        transcribe_client = manager.transcribe
        assert transcribe_client == mock_client
        
        # Verify boto3.client was called with correct parameters
        mock_boto3.client.assert_called_with('transcribe', config=manager._boto_config)
    
    @patch('bharat_voice_assistant.core.aws_client.boto3')
    def test_aws_connectivity_test(self, mock_boto3):
        """Test AWS connectivity testing."""
        # Mock successful responses
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        mock_s3 = Mock()
        mock_s3.list_buckets.return_value = {"Buckets": []}
        
        mock_transcribe = Mock()
        mock_transcribe.list_transcription_jobs.return_value = {"TranscriptionJobSummaries": []}
        
        mock_polly = Mock()
        mock_polly.describe_voices.return_value = {"Voices": []}
        
        mock_comprehend = Mock()
        mock_comprehend.detect_dominant_language.return_value = {"Languages": []}
        
        # Configure boto3 mock to return appropriate clients
        def mock_client_factory(service_name, **kwargs):
            clients = {
                'sts': mock_sts,
                's3': mock_s3,
                'transcribe': mock_transcribe,
                'polly': mock_polly,
                'comprehend': mock_comprehend
            }
            return clients.get(service_name, Mock())
        
        mock_boto3.client.side_effect = mock_client_factory
        
        manager = AWSClientManager()
        results = manager.test_connectivity()
        
        # All services should pass
        expected_services = ['sts', 's3', 'transcribe', 'polly', 'comprehend']
        for service in expected_services:
            assert results[service] is True
    
    def test_safe_aws_call_success(self):
        """Test successful AWS API call."""
        mock_method = Mock(return_value={"Status": "Success"})
        
        result = safe_aws_call(mock_method, "arg1", kwarg1="value1")
        
        assert result == {"Status": "Success"}
        mock_method.assert_called_once_with("arg1", kwarg1="value1")
    
    def test_safe_aws_call_client_error(self):
        """Test AWS API call with ClientError."""
        from botocore.exceptions import ClientError
        
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access denied'
            }
        }
        mock_method = Mock(side_effect=ClientError(error_response, 'TestOperation'))
        
        with pytest.raises(AWSServiceError) as exc_info:
            safe_aws_call(mock_method)
        
        assert "AWS API call" in str(exc_info.value)
        assert exc_info.value.context['error_code'] == 'AccessDenied'
    
    @patch('bharat_voice_assistant.core.aws_client.aws_clients')
    def test_validate_aws_configuration(self, mock_aws_clients):
        """Test AWS configuration validation."""
        # Mock successful connectivity test
        mock_aws_clients.test_connectivity.return_value = {
            'sts': True,
            's3': True,
            'transcribe': True,
            'polly': True,
            'comprehend': True
        }
        
        results = validate_aws_configuration()
        
        assert results['valid'] is True
        assert len(results['errors']) == 0
        assert 'services' in results


class TestExceptions:
    """Test custom exception handling."""
    
    def test_base_exception(self):
        """Test base exception functionality."""
        error = BharatVoiceAssistantError(
            "Test error message",
            error_code="TEST_ERROR",
            context={"key": "value"}
        )
        
        assert str(error) == "Test error message"
        assert error.error_code == "TEST_ERROR"
        assert error.context == {"key": "value"}
        
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "BharatVoiceAssistantError"
        assert error_dict["message"] == "Test error message"
        assert error_dict["error_code"] == "TEST_ERROR"
        assert error_dict["context"] == {"key": "value"}
    
    def test_handle_aws_error(self):
        """Test AWS error handling utility."""
        from botocore.exceptions import ClientError
        
        # Test throttling error
        throttling_error = ClientError(
            {'Error': {'Code': 'Throttling', 'Message': 'Rate exceeded'}},
            'TestOperation'
        )
        
        result = handle_aws_error(throttling_error, "test operation")
        assert isinstance(result, BharatVoiceAssistantError)
        assert "rate limit" in str(result).lower()
        
        # Test generic error
        generic_error = Exception("Generic error")
        result = handle_aws_error(generic_error, "test operation")
        assert isinstance(result, AWSServiceError)
    
    def test_handle_validation_error(self):
        """Test validation error handling utility."""
        error = handle_validation_error("test_field", "invalid_value", "valid format")
        
        assert isinstance(error, ValidationError)
        assert "test_field" in str(error)
        assert error.context["field"] == "test_field"
        assert error.context["value"] == "invalid_value"
        assert error.context["expected"] == "valid format"


@pytest.mark.integration
class TestCoreIntegration:
    """Integration tests for core infrastructure components."""
    
    def test_logging_and_monitoring_integration(self):
        """Test integration between logging and monitoring."""
        from bharat_voice_assistant.core.monitoring import monitor
        from bharat_voice_assistant.core.logging import get_performance_logger
        
        # Test that performance logging works with monitoring
        perf_logger = get_performance_logger()
        
        # Record some metrics
        monitor.metrics.increment_counter("test_integration_counter")
        monitor.metrics.set_gauge("test_integration_gauge", 100.0)
        
        # Verify metrics were recorded
        assert monitor.metrics.get_counter("test_integration_counter") == 1
        assert monitor.metrics.get_gauge("test_integration_gauge") == 100.0
    
    def test_config_and_aws_client_integration(self, test_config):
        """Test integration between configuration and AWS clients."""
        with patch('bharat_voice_assistant.core.aws_client.boto3') as mock_boto3:
            mock_boto3.client.return_value = Mock()
            
            manager = AWSClientManager()
            
            # Test that configuration is properly used
            transcribe_client = manager.transcribe
            
            # Verify that boto3.client was called with config parameters
            call_args = mock_boto3.client.call_args
            assert call_args[0][0] == 'transcribe'  # Service name
            assert 'config' in call_args[1]  # Boto config passed