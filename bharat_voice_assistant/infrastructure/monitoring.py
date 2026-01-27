"""
Monitoring and alerting system for the Bharat Voice Assistant.

This module provides comprehensive monitoring capabilities including:
- CloudWatch metrics and alarms
- Custom application metrics
- Performance monitoring
- Error tracking and alerting
- Dashboard creation and management
- Log aggregation and analysis
"""

import boto3
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from datetime import datetime, timedelta

from ..core.logging import get_logger
from ..core.aws_client import aws_clients, safe_aws_call
from ..core.exceptions import InfrastructureError


logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics to monitor."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ComparisonOperator(Enum):
    """CloudWatch comparison operators."""
    GREATER_THAN_THRESHOLD = "GreaterThanThreshold"
    GREATER_THAN_OR_EQUAL_TO_THRESHOLD = "GreaterThanOrEqualToThreshold"
    LESS_THAN_THRESHOLD = "LessThanThreshold"
    LESS_THAN_OR_EQUAL_TO_THRESHOLD = "LessThanOrEqualToThreshold"
    LESS_THAN_LOWER_OR_GREATER_THAN_UPPER_THRESHOLD = "LessThanLowerOrGreaterThanUpperThreshold"
    LESS_THAN_LOWER_THRESHOLD = "LessThanLowerThreshold"
    GREATER_THAN_UPPER_THRESHOLD = "GreaterThanUpperThreshold"


class Statistic(Enum):
    """CloudWatch statistics."""
    AVERAGE = "Average"
    MAXIMUM = "Maximum"
    MINIMUM = "Minimum"
    SUM = "Sum"
    SAMPLE_COUNT = "SampleCount"


@dataclass
class MetricConfig:
    """Configuration for a custom metric."""
    name: str
    namespace: str
    metric_type: MetricType = MetricType.GAUGE
    unit: str = "None"
    dimensions: Dict[str, str] = field(default_factory=dict)
    description: Optional[str] = None
    
    # Retention and aggregation
    retention_days: int = 30
    aggregation_period: int = 300  # 5 minutes
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AlertConfig:
    """Configuration for an alert/alarm."""
    name: str
    metric_name: str
    namespace: str
    threshold: float
    comparison_operator: ComparisonOperator
    severity: AlertSeverity = AlertSeverity.MEDIUM
    
    # Evaluation settings
    evaluation_periods: int = 2
    datapoints_to_alarm: int = 2
    period: int = 300  # 5 minutes
    statistic: Statistic = Statistic.AVERAGE
    
    # Dimensions for the metric
    dimensions: Dict[str, str] = field(default_factory=dict)
    
    # Actions
    alarm_actions: List[str] = field(default_factory=list)  # SNS topic ARNs
    ok_actions: List[str] = field(default_factory=list)
    insufficient_data_actions: List[str] = field(default_factory=list)
    
    # Notification settings
    treat_missing_data: str = "missing"  # missing, ignore, breaching, notBreaching
    
    # Description and tags
    description: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class DashboardConfig:
    """Configuration for a CloudWatch dashboard."""
    name: str
    widgets: List[Dict[str, Any]] = field(default_factory=list)
    width: int = 24
    height: int = 6
    
    # Auto-refresh settings
    auto_refresh: bool = True
    refresh_interval: int = 300  # 5 minutes
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)


class MonitoringManager:
    """Manages monitoring and alerting for the voice assistant infrastructure."""
    
    def __init__(self):
        """Initialize the monitoring manager."""
        self.cloudwatch_client = aws_clients.cloudwatch
        self.logs_client = aws_clients.get_custom_client('logs')
        self.sns_client = aws_clients.get_custom_client('sns')
        
        self._metrics: Dict[str, MetricConfig] = {}
        self._alerts: Dict[str, AlertConfig] = {}
        self._dashboards: Dict[str, DashboardConfig] = {}
        self._sns_topics: Dict[str, str] = {}  # severity -> topic_arn
        
        # Default namespace for custom metrics
        self.default_namespace = "BharatVoiceAssistant"
    
    async def setup_core_monitoring(self) -> Dict[str, Any]:
        """
        Set up core monitoring for the voice assistant.
        
        Returns:
            Dictionary with monitoring setup results
        """
        try:
            # Create SNS topics for different severity levels
            sns_topics = await self._create_alert_sns_topics()
            
            # Define core metrics
            core_metrics = self._define_core_metrics()
            
            # Create core metrics
            created_metrics = {}
            for metric_name, metric_config in core_metrics.items():
                created_metrics[metric_name] = await self.create_custom_metric(metric_config)
            
            # Define core alerts
            core_alerts = self._define_core_alerts(sns_topics)
            
            # Create core alerts
            created_alerts = {}
            for alert_name, alert_config in core_alerts.items():
                created_alerts[alert_name] = await self.create_alert(alert_config)
            
            # Create main dashboard
            dashboard_config = self._create_main_dashboard_config()
            main_dashboard = await self.create_dashboard(dashboard_config)
            
            logger.info("Core monitoring setup completed successfully")
            
            return {
                'sns_topics': sns_topics,
                'metrics': created_metrics,
                'alerts': created_alerts,
                'dashboard': main_dashboard
            }
            
        except Exception as e:
            logger.error(f"Failed to set up core monitoring: {e}")
            raise InfrastructureError(
                f"Failed to set up core monitoring: {e}",
                error_code="MONITORING_SETUP_FAILED"
            )
    
    async def _create_alert_sns_topics(self) -> Dict[str, str]:
        """Create SNS topics for different alert severities."""
        try:
            topics = {}
            
            for severity in AlertSeverity:
                topic_name = f"bharat-voice-assistant-alerts-{severity.value}"
                
                topic_response = safe_aws_call(
                    self.sns_client.create_topic,
                    Name=topic_name,
                    Tags=[
                        {'Key': 'Service', 'Value': 'bharat-voice-assistant'},
                        {'Key': 'AlertSeverity', 'Value': severity.value},
                        {'Key': 'Purpose', 'Value': 'monitoring-alerts'}
                    ]
                )
                
                topics[severity.value] = topic_response['TopicArn']
                self._sns_topics[severity.value] = topic_response['TopicArn']
                
                logger.info(f"Created SNS topic for {severity.value} alerts: {topic_response['TopicArn']}")
            
            return topics
            
        except Exception as e:
            logger.error(f"Failed to create SNS topics: {e}")
            raise
    
    def _define_core_metrics(self) -> Dict[str, MetricConfig]:
        """Define core metrics for the voice assistant."""
        return {
            'voice_requests_total': MetricConfig(
                name='VoiceRequestsTotal',
                namespace=self.default_namespace,
                metric_type=MetricType.COUNTER,
                unit='Count',
                description='Total number of voice requests processed',
                dimensions={'Service': 'voice-processing'}
            ),
            'voice_requests_per_second': MetricConfig(
                name='VoiceRequestsPerSecond',
                namespace=self.default_namespace,
                metric_type=MetricType.GAUGE,
                unit='Count/Second',
                description='Voice requests processed per second',
                dimensions={'Service': 'voice-processing'}
            ),
            'speech_recognition_latency': MetricConfig(
                name='SpeechRecognitionLatency',
                namespace=self.default_namespace,
                metric_type=MetricType.TIMER,
                unit='Milliseconds',
                description='Time taken for speech recognition',
                dimensions={'Service': 'speech-recognition'}
            ),
            'text_to_speech_latency': MetricConfig(
                name='TextToSpeechLatency',
                namespace=self.default_namespace,
                metric_type=MetricType.TIMER,
                unit='Milliseconds',
                description='Time taken for text-to-speech synthesis',
                dimensions={'Service': 'text-to-speech'}
            ),
            'scheme_discovery_requests': MetricConfig(
                name='SchemeDiscoveryRequests',
                namespace=self.default_namespace,
                metric_type=MetricType.COUNTER,
                unit='Count',
                description='Number of scheme discovery requests',
                dimensions={'Service': 'scheme-discovery'}
            ),
            'grievance_filing_requests': MetricConfig(
                name='GrievanceFilingRequests',
                namespace=self.default_namespace,
                metric_type=MetricType.COUNTER,
                unit='Count',
                description='Number of grievance filing requests',
                dimensions={'Service': 'grievance-filing'}
            ),
            'active_connections': MetricConfig(
                name='ActiveConnections',
                namespace=self.default_namespace,
                metric_type=MetricType.GAUGE,
                unit='Count',
                description='Number of active connections',
                dimensions={'Service': 'voice-gateway'}
            ),
            'error_rate': MetricConfig(
                name='ErrorRate',
                namespace=self.default_namespace,
                metric_type=MetricType.GAUGE,
                unit='Percent',
                description='Error rate percentage',
                dimensions={'Service': 'all'}
            ),
            'response_time': MetricConfig(
                name='ResponseTime',
                namespace=self.default_namespace,
                metric_type=MetricType.TIMER,
                unit='Milliseconds',
                description='Average response time',
                dimensions={'Service': 'all'}
            )
        }
    
    def _define_core_alerts(self, sns_topics: Dict[str, str]) -> Dict[str, AlertConfig]:
        """Define core alerts for the voice assistant."""
        return {
            'high_error_rate': AlertConfig(
                name='HighErrorRate',
                metric_name='ErrorRate',
                namespace=self.default_namespace,
                threshold=5.0,  # 5% error rate
                comparison_operator=ComparisonOperator.GREATER_THAN_THRESHOLD,
                severity=AlertSeverity.HIGH,
                alarm_actions=[sns_topics['high']],
                description='Error rate is above acceptable threshold'
            ),
            'high_response_time': AlertConfig(
                name='HighResponseTime',
                metric_name='ResponseTime',
                namespace=self.default_namespace,
                threshold=3000.0,  # 3 seconds
                comparison_operator=ComparisonOperator.GREATER_THAN_THRESHOLD,
                severity=AlertSeverity.MEDIUM,
                alarm_actions=[sns_topics['medium']],
                description='Response time is above acceptable threshold'
            ),
            'low_active_connections': AlertConfig(
                name='LowActiveConnections',
                metric_name='ActiveConnections',
                namespace=self.default_namespace,
                threshold=10.0,
                comparison_operator=ComparisonOperator.LESS_THAN_THRESHOLD,
                severity=AlertSeverity.LOW,
                alarm_actions=[sns_topics['low']],
                description='Active connections are below expected threshold'
            )
        }
    
    def _create_main_dashboard_config(self) -> DashboardConfig:
        """Create configuration for the main monitoring dashboard."""
        widgets = [
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        [self.default_namespace, "VoiceRequestsPerSecond"],
                        [self.default_namespace, "ActiveConnections"]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "ap-south-1",
                    "title": "Voice Processing Metrics"
                }
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        [self.default_namespace, "SpeechRecognitionLatency"],
                        [self.default_namespace, "TextToSpeechLatency"]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "ap-south-1",
                    "title": "Latency Metrics"
                }
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        [self.default_namespace, "ErrorRate"],
                        [self.default_namespace, "ResponseTime"]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "ap-south-1",
                    "title": "Performance Metrics"
                }
            }
        ]
        
        return DashboardConfig(
            name='BharatVoiceAssistant-MainDashboard',
            widgets=widgets,
            tags={
                'Service': 'bharat-voice-assistant',
                'Purpose': 'main-monitoring'
            }
        )
    
    async def create_custom_metric(self, config: MetricConfig) -> Dict[str, Any]:
        """
        Create a custom metric.
        
        Args:
            config: Metric configuration
            
        Returns:
            Dictionary with metric creation results
        """
        try:
            # Store metric configuration
            self._metrics[config.name] = config
            
            logger.info(f"Registered custom metric {config.name} in namespace {config.namespace}")
            
            return {
                'metric_name': config.name,
                'namespace': config.namespace,
                'metric_type': config.metric_type.value,
                'dimensions': config.dimensions
            }
            
        except Exception as e:
            logger.error(f"Failed to create custom metric {config.name}: {e}")
            raise InfrastructureError(
                f"Failed to create custom metric: {e}",
                error_code="METRIC_CREATION_FAILED",
                context={'metric_name': config.name}
            )
    
    async def create_alert(self, config: AlertConfig) -> Dict[str, Any]:
        """
        Create an alert/alarm.
        
        Args:
            config: Alert configuration
            
        Returns:
            Dictionary with alert creation results
        """
        try:
            alarm_response = safe_aws_call(
                self.cloudwatch_client.put_metric_alarm,
                AlarmName=config.name,
                ComparisonOperator=config.comparison_operator.value,
                EvaluationPeriods=config.evaluation_periods,
                MetricName=config.metric_name,
                Namespace=config.namespace,
                Period=config.period,
                Statistic=config.statistic.value,
                Threshold=config.threshold,
                ActionsEnabled=True,
                AlarmActions=config.alarm_actions,
                OKActions=config.ok_actions,
                InsufficientDataActions=config.insufficient_data_actions,
                AlarmDescription=config.description or f'Alert for {config.metric_name}',
                Dimensions=[{'Name': k, 'Value': v} for k, v in config.dimensions.items()],
                DatapointsToAlarm=config.datapoints_to_alarm,
                TreatMissingData=config.treat_missing_data,
                Tags=[{'Key': k, 'Value': v} for k, v in config.tags.items()]
            )
            
            # Store alert configuration
            self._alerts[config.name] = config
            
            logger.info(f"Created alert {config.name} for metric {config.metric_name}")
            
            return {
                'alarm_name': config.name,
                'alarm_arn': f"arn:aws:cloudwatch:{aws_clients._boto_config.region_name}:*:alarm:{config.name}",
                'severity': config.severity.value
            }
            
        except Exception as e:
            logger.error(f"Failed to create alert {config.name}: {e}")
            raise InfrastructureError(
                f"Failed to create alert: {e}",
                error_code="ALERT_CREATION_FAILED",
                context={'alert_name': config.name}
            )
    
    async def create_dashboard(self, config: DashboardConfig) -> Dict[str, Any]:
        """
        Create a CloudWatch dashboard.
        
        Args:
            config: Dashboard configuration
            
        Returns:
            Dictionary with dashboard creation results
        """
        try:
            dashboard_body = {
                "widgets": config.widgets
            }
            
            dashboard_response = safe_aws_call(
                self.cloudwatch_client.put_dashboard,
                DashboardName=config.name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            # Store dashboard configuration
            self._dashboards[config.name] = config
            
            logger.info(f"Created dashboard {config.name} with {len(config.widgets)} widgets")
            
            return {
                'dashboard_name': config.name,
                'dashboard_arn': dashboard_response.get('DashboardArn'),
                'widgets_count': len(config.widgets)
            }
            
        except Exception as e:
            logger.error(f"Failed to create dashboard {config.name}: {e}")
            raise InfrastructureError(
                f"Failed to create dashboard: {e}",
                error_code="DASHBOARD_CREATION_FAILED",
                context={'dashboard_name': config.name}
            )
    
    async def publish_metric(
        self, 
        metric_name: str, 
        value: float, 
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Publish a metric value to CloudWatch.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement
            dimensions: Metric dimensions
            timestamp: Timestamp for the metric (defaults to current time)
            
        Returns:
            Dictionary with publish results
        """
        try:
            if metric_name not in self._metrics:
                logger.warning(f"Metric {metric_name} not registered, using default configuration")
                namespace = self.default_namespace
            else:
                namespace = self._metrics[metric_name].namespace
            
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            if timestamp:
                metric_data['Timestamp'] = timestamp
            
            safe_aws_call(
                self.cloudwatch_client.put_metric_data,
                Namespace=namespace,
                MetricData=[metric_data]
            )
            
            return {
                'metric_name': metric_name,
                'value': value,
                'namespace': namespace,
                'published': True
            }
            
        except Exception as e:
            logger.error(f"Failed to publish metric {metric_name}: {e}")
            raise InfrastructureError(
                f"Failed to publish metric: {e}",
                error_code="METRIC_PUBLISH_FAILED",
                context={'metric_name': metric_name}
            )
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """
        Get current monitoring status.
        
        Returns:
            Dictionary with monitoring status information
        """
        try:
            # Get alarm states
            alarm_states = {}
            if self._alerts:
                alarm_names = list(self._alerts.keys())
                alarms_response = safe_aws_call(
                    self.cloudwatch_client.describe_alarms,
                    AlarmNames=alarm_names
                )
                
                for alarm in alarms_response.get('MetricAlarms', []):
                    alarm_states[alarm['AlarmName']] = {
                        'state': alarm['StateValue'],
                        'reason': alarm['StateReason'],
                        'updated': alarm['StateUpdatedTimestamp']
                    }
            
            # Get recent metric data
            recent_metrics = {}
            for metric_name, metric_config in self._metrics.items():
                try:
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(minutes=30)
                    
                    metrics_response = safe_aws_call(
                        self.cloudwatch_client.get_metric_statistics,
                        Namespace=metric_config.namespace,
                        MetricName=metric_name,
                        Dimensions=[
                            {'Name': k, 'Value': v} for k, v in metric_config.dimensions.items()
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300,
                        Statistics=['Average', 'Maximum', 'Minimum']
                    )
                    
                    recent_metrics[metric_name] = {
                        'datapoints': len(metrics_response.get('Datapoints', [])),
                        'latest_value': metrics_response.get('Datapoints', [{}])[-1].get('Average') if metrics_response.get('Datapoints') else None
                    }
                    
                except Exception as e:
                    logger.warning(f"Failed to get recent data for metric {metric_name}: {e}")
                    recent_metrics[metric_name] = {'error': str(e)}
            
            return {
                'metrics_count': len(self._metrics),
                'alerts_count': len(self._alerts),
                'dashboards_count': len(self._dashboards),
                'alarm_states': alarm_states,
                'recent_metrics': recent_metrics,
                'sns_topics': self._sns_topics
            }
            
        except Exception as e:
            logger.error(f"Failed to get monitoring status: {e}")
            raise InfrastructureError(
                f"Failed to get monitoring status: {e}",
                error_code="MONITORING_STATUS_FAILED"
            )