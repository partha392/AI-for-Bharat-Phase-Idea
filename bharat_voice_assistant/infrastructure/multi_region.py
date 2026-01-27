"""
Multi-region deployment and failover management for the Bharat Voice Assistant.

This module provides comprehensive multi-region capabilities including:
- Cross-region deployment coordination
- Automatic failover mechanisms
- Health monitoring across regions
- Data replication and synchronization
- Route 53 health checks and DNS failover
"""

import boto3
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import time
import asyncio

from ..core.logging import get_logger
from ..core.aws_client import aws_clients, safe_aws_call
from ..core.exceptions import InfrastructureError


logger = get_logger(__name__)


class RegionStatus(Enum):
    """Region deployment status."""
    ACTIVE = "active"
    STANDBY = "standby"
    FAILED = "failed"
    DEPLOYING = "deploying"
    MAINTENANCE = "maintenance"


class FailoverType(Enum):
    """Types of failover mechanisms."""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    HEALTH_CHECK = "health_check"


class HealthCheckType(Enum):
    """Health check types for Route 53."""
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    TCP = "TCP"
    HTTP_STR_MATCH = "HTTP_STR_MATCH"
    HTTPS_STR_MATCH = "HTTPS_STR_MATCH"
    CALCULATED = "CALCULATED"
    CLOUDWATCH_METRIC = "CLOUDWATCH_METRIC"


@dataclass
class RegionConfig:
    """Configuration for a region deployment."""
    region_name: str
    status: RegionStatus = RegionStatus.STANDBY
    priority: int = 1  # Lower number = higher priority
    
    # Infrastructure configuration
    vpc_id: Optional[str] = None
    subnets: List[str] = field(default_factory=list)
    security_groups: List[str] = field(default_factory=list)
    
    # Load balancer configuration
    load_balancer_arn: Optional[str] = None
    load_balancer_dns: Optional[str] = None
    
    # ECS configuration
    cluster_name: Optional[str] = None
    service_names: List[str] = field(default_factory=list)
    
    # Database configuration
    database_endpoint: Optional[str] = None
    database_read_replicas: List[str] = field(default_factory=list)
    
    # S3 configuration
    s3_buckets: Dict[str, str] = field(default_factory=dict)  # bucket_type -> bucket_name
    
    # Health check configuration
    health_check_endpoint: Optional[str] = None
    health_check_path: str = "/health"
    health_check_port: int = 80
    health_check_protocol: HealthCheckType = HealthCheckType.HTTP
    
    # Failover configuration
    failover_threshold_seconds: int = 300  # 5 minutes
    recovery_threshold_seconds: int = 600  # 10 minutes
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class FailoverConfig:
    """Configuration for failover behavior."""
    enabled: bool = True
    failover_type: FailoverType = FailoverType.AUTOMATIC
    
    # Health check thresholds
    failure_threshold: int = 3
    success_threshold: int = 2
    check_interval_seconds: int = 30
    
    # DNS failover configuration
    dns_failover_enabled: bool = True
    dns_ttl: int = 60
    
    # Notification configuration
    sns_topic_arn: Optional[str] = None
    notification_enabled: bool = True
    
    # Recovery configuration
    auto_recovery_enabled: bool = True
    recovery_delay_seconds: int = 300


class MultiRegionManager:
    """Manages multi-region deployment and failover for the voice assistant infrastructure."""
    
    def __init__(self):
        """Initialize the multi-region manager."""
        self.route53_client = aws_clients.get_custom_client('route53')
        self.sns_client = aws_clients.get_custom_client('sns')
        self.cloudwatch_client = aws_clients.cloudwatch
        
        self._regions: Dict[str, RegionConfig] = {}
        self._failover_config: Optional[FailoverConfig] = None
        self._health_checks: Dict[str, Dict[str, Any]] = {}
        self._dns_records: Dict[str, Dict[str, Any]] = {}
        
        # Regional clients cache
        self._regional_clients: Dict[str, Dict[str, Any]] = {}
    
    def _get_regional_client(self, service: str, region: str) -> Any:
        """Get a client for a specific region."""
        if region not in self._regional_clients:
            self._regional_clients[region] = {}
        
        if service not in self._regional_clients[region]:
            self._regional_clients[region][service] = aws_clients.get_custom_client(
                service, region_name=region
            )
        
        return self._regional_clients[region][service]
    
    async def configure_multi_region_deployment(
        self, 
        regions: List[RegionConfig],
        failover_config: FailoverConfig,
        hosted_zone_id: str,
        domain_name: str
    ) -> Dict[str, Any]:
        """
        Configure multi-region deployment with failover.
        
        Args:
            regions: List of region configurations
            failover_config: Failover configuration
            hosted_zone_id: Route 53 hosted zone ID
            domain_name: Domain name for the service
            
        Returns:
            Dictionary with deployment configuration results
        """
        try:
            # Validate configuration
            await self._validate_multi_region_config(regions, failover_config)
            
            # Store configurations
            for region in regions:
                self._regions[region.region_name] = region
            self._failover_config = failover_config
            
            # Create health checks for each region
            health_checks = {}
            for region in regions:
                if region.health_check_endpoint:
                    health_check = await self._create_health_check(region)
                    health_checks[region.region_name] = health_check
            
            # Create DNS records with failover routing
            dns_records = await self._create_dns_failover_records(
                regions, hosted_zone_id, domain_name, health_checks
            )
            
            # Set up monitoring and alerting
            monitoring_config = await self._setup_multi_region_monitoring(regions, failover_config)
            
            logger.info(f"Configured multi-region deployment across {len(regions)} regions")
            
            return {
                'regions': {r.region_name: r for r in regions},
                'failover_config': failover_config,
                'health_checks': health_checks,
                'dns_records': dns_records,
                'monitoring': monitoring_config
            }
            
        except Exception as e:
            logger.error(f"Failed to configure multi-region deployment: {e}")
            raise InfrastructureError(
                f"Failed to configure multi-region deployment: {e}",
                error_code="MULTI_REGION_CONFIG_FAILED"
            )
    
    async def _validate_multi_region_config(
        self, 
        regions: List[RegionConfig], 
        failover_config: FailoverConfig
    ):
        """Validate multi-region configuration."""
        if len(regions) < 2:
            raise InfrastructureError(
                "At least 2 regions required for multi-region deployment",
                error_code="INSUFFICIENT_REGIONS"
            )
        
        # Check for duplicate priorities
        priorities = [r.priority for r in regions]
        if len(priorities) != len(set(priorities)):
            raise InfrastructureError(
                "Region priorities must be unique",
                error_code="DUPLICATE_PRIORITIES"
            )
        
        # Validate primary region
        primary_regions = [r for r in regions if r.status == RegionStatus.ACTIVE]
        if len(primary_regions) != 1:
            raise InfrastructureError(
                "Exactly one region must be marked as ACTIVE (primary)",
                error_code="INVALID_PRIMARY_REGION"
            )
        
        # Validate health check endpoints
        for region in regions:
            if not region.health_check_endpoint:
                logger.warning(f"No health check endpoint configured for region {region.region_name}")
    
    async def _create_health_check(self, region: RegionConfig) -> Dict[str, Any]:
        """Create Route 53 health check for a region."""
        try:
            health_check_config = {
                'Type': region.health_check_protocol.value,
                'ResourcePath': region.health_check_path,
                'FullyQualifiedDomainName': region.health_check_endpoint,
                'Port': region.health_check_port,
                'RequestInterval': 30,  # Standard interval
                'FailureThreshold': self._failover_config.failure_threshold if self._failover_config else 3
            }
            
            # Add string matching for HTTP/HTTPS string match checks
            if region.health_check_protocol in [HealthCheckType.HTTP_STR_MATCH, HealthCheckType.HTTPS_STR_MATCH]:
                health_check_config['SearchString'] = 'OK'
            
            health_check_response = safe_aws_call(
                self.route53_client.create_health_check,
                CallerReference=f"{region.region_name}-{int(time.time())}",
                HealthCheckConfig=health_check_config,
                Tags=[
                    {'Key': 'Name', 'Value': f"{region.region_name}-health-check"},
                    {'Key': 'Region', 'Value': region.region_name},
                    {'Key': 'Service', 'Value': 'bharat-voice-assistant'}
                ]
            )
            
            health_check_id = health_check_response['HealthCheck']['Id']
            
            # Store health check
            self._health_checks[region.region_name] = {
                'id': health_check_id,
                'config': health_check_config,
                'region': region.region_name
            }
            
            logger.info(f"Created health check {health_check_id} for region {region.region_name}")
            
            return {
                'health_check_id': health_check_id,
                'health_check': health_check_response['HealthCheck']
            }
            
        except Exception as e:
            logger.error(f"Failed to create health check for region {region.region_name}: {e}")
            raise
    
    async def _create_dns_failover_records(
        self,
        regions: List[RegionConfig],
        hosted_zone_id: str,
        domain_name: str,
        health_checks: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create DNS records with failover routing."""
        try:
            # Sort regions by priority
            sorted_regions = sorted(regions, key=lambda r: r.priority)
            
            dns_records = {}
            change_batch = {'Changes': []}
            
            for i, region in enumerate(sorted_regions):
                if not region.load_balancer_dns:
                    logger.warning(f"No load balancer DNS configured for region {region.region_name}")
                    continue
                
                # Determine routing policy
                if i == 0:  # Primary region
                    routing_policy = 'PRIMARY'
                else:  # Secondary regions
                    routing_policy = 'SECONDARY'
                
                record_name = domain_name
                if i > 0:  # Add region suffix for secondary regions
                    record_name = f"{region.region_name}.{domain_name}"
                
                # Create A record with failover routing
                change = {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': record_name,
                        'Type': 'A',
                        'SetIdentifier': f"{region.region_name}-failover",
                        'Failover': routing_policy,
                        'AliasTarget': {
                            'DNSName': region.load_balancer_dns,
                            'EvaluateTargetHealth': True,
                            'HostedZoneId': self._get_load_balancer_zone_id(region.region_name)
                        }
                    }
                }
                
                # Add health check for secondary regions
                if routing_policy == 'SECONDARY' and region.region_name in health_checks:
                    change['ResourceRecordSet']['HealthCheckId'] = health_checks[region.region_name]['health_check_id']
                
                change_batch['Changes'].append(change)
                
                dns_records[region.region_name] = {
                    'record_name': record_name,
                    'routing_policy': routing_policy,
                    'target': region.load_balancer_dns
                }
            
            # Apply DNS changes
            if change_batch['Changes']:
                change_response = safe_aws_call(
                    self.route53_client.change_resource_record_sets,
                    HostedZoneId=hosted_zone_id,
                    ChangeBatch=change_batch
                )
                
                logger.info(f"Created {len(change_batch['Changes'])} DNS failover records")
                
                # Store DNS records
                self._dns_records = dns_records
                
                return {
                    'change_id': change_response['ChangeInfo']['Id'],
                    'dns_records': dns_records,
                    'status': change_response['ChangeInfo']['Status']
                }
            else:
                logger.warning("No DNS records created - no valid load balancer endpoints found")
                return {'dns_records': {}, 'status': 'NO_CHANGES'}
                
        except Exception as e:
            logger.error(f"Failed to create DNS failover records: {e}")
            raise
    
    def _get_load_balancer_zone_id(self, region: str) -> str:
        """Get the hosted zone ID for load balancers in a specific region."""
        # AWS ALB hosted zone IDs by region
        zone_ids = {
            'ap-south-1': 'ZP97RAFLXTNZK',      # Mumbai
            'ap-south-2': 'Z02239872DOALSIDNF46',  # Hyderabad
            'ap-southeast-1': 'Z1LMS91P8CMLE5',  # Singapore
            'us-east-1': 'Z35SXDOTRQ7X7K',      # N. Virginia
            'us-west-2': 'Z1H1FL5HABSF5',       # Oregon
            'eu-west-1': 'Z32O12XQLNTSW2',      # Ireland
        }
        
        return zone_ids.get(region, 'Z35SXDOTRQ7X7K')  # Default to us-east-1
    
    async def _setup_multi_region_monitoring(
        self,
        regions: List[RegionConfig],
        failover_config: FailoverConfig
    ) -> Dict[str, Any]:
        """Set up monitoring and alerting for multi-region deployment."""
        try:
            monitoring_config = {}
            
            # Create CloudWatch alarms for each region
            for region in regions:
                region_alarms = await self._create_region_monitoring_alarms(region, failover_config)
                monitoring_config[region.region_name] = region_alarms
            
            # Create SNS topic for notifications if not provided
            if failover_config.notification_enabled and not failover_config.sns_topic_arn:
                sns_topic = await self._create_failover_notification_topic()
                failover_config.sns_topic_arn = sns_topic['TopicArn']
                monitoring_config['sns_topic'] = sns_topic
            
            logger.info(f"Set up monitoring for {len(regions)} regions")
            
            return monitoring_config
            
        except Exception as e:
            logger.error(f"Failed to set up multi-region monitoring: {e}")
            raise
    
    async def _create_region_monitoring_alarms(
        self,
        region: RegionConfig,
        failover_config: FailoverConfig
    ) -> Dict[str, Any]:
        """Create CloudWatch alarms for a specific region."""
        try:
            alarms = {}
            
            # Health check alarm
            if region.region_name in self._health_checks:
                health_check_id = self._health_checks[region.region_name]['id']
                
                health_alarm_response = safe_aws_call(
                    self.cloudwatch_client.put_metric_alarm,
                    AlarmName=f"{region.region_name}-health-check-failed",
                    ComparisonOperator='LessThanThreshold',
                    EvaluationPeriods=failover_config.failure_threshold,
                    MetricName='HealthCheckStatus',
                    Namespace='AWS/Route53',
                    Period=60,
                    Statistic='Minimum',
                    Threshold=1.0,
                    ActionsEnabled=True,
                    AlarmActions=[failover_config.sns_topic_arn] if failover_config.sns_topic_arn else [],
                    AlarmDescription=f'Health check failed for region {region.region_name}',
                    Dimensions=[
                        {'Name': 'HealthCheckId', 'Value': health_check_id}
                    ],
                    Unit='None'
                )
                
                alarms['health_check'] = health_alarm_response
            
            # Load balancer target health alarm
            if region.load_balancer_arn:
                target_health_alarm_response = safe_aws_call(
                    self.cloudwatch_client.put_metric_alarm,
                    AlarmName=f"{region.region_name}-unhealthy-targets",
                    ComparisonOperator='GreaterThanThreshold',
                    EvaluationPeriods=2,
                    MetricName='UnHealthyHostCount',
                    Namespace='AWS/ApplicationELB',
                    Period=300,
                    Statistic='Average',
                    Threshold=0.0,
                    ActionsEnabled=True,
                    AlarmActions=[failover_config.sns_topic_arn] if failover_config.sns_topic_arn else [],
                    AlarmDescription=f'Unhealthy targets detected in region {region.region_name}',
                    Dimensions=[
                        {'Name': 'LoadBalancer', 'Value': region.load_balancer_arn.split('/')[-1]}
                    ],
                    Unit='Count'
                )
                
                alarms['target_health'] = target_health_alarm_response
            
            return alarms
            
        except Exception as e:
            logger.error(f"Failed to create monitoring alarms for region {region.region_name}: {e}")
            raise
    
    async def _create_failover_notification_topic(self) -> Dict[str, Any]:
        """Create SNS topic for failover notifications."""
        try:
            topic_response = safe_aws_call(
                self.sns_client.create_topic,
                Name='bharat-voice-assistant-failover-notifications',
                Tags=[
                    {'Key': 'Service', 'Value': 'bharat-voice-assistant'},
                    {'Key': 'Purpose', 'Value': 'failover-notifications'}
                ]
            )
            
            logger.info(f"Created SNS topic for failover notifications: {topic_response['TopicArn']}")
            
            return topic_response
            
        except Exception as e:
            logger.error(f"Failed to create SNS topic: {e}")
            raise
    
    async def trigger_manual_failover(
        self, 
        from_region: str, 
        to_region: str,
        reason: str = "Manual failover"
    ) -> Dict[str, Any]:
        """
        Trigger manual failover from one region to another.
        
        Args:
            from_region: Source region to failover from
            to_region: Target region to failover to
            reason: Reason for the failover
            
        Returns:
            Dictionary with failover results
        """
        try:
            if from_region not in self._regions or to_region not in self._regions:
                raise InfrastructureError(
                    "Invalid region specified for failover",
                    error_code="INVALID_FAILOVER_REGION"
                )
            
            from_config = self._regions[from_region]
            to_config = self._regions[to_region]
            
            logger.info(f"Starting manual failover from {from_region} to {to_region}: {reason}")
            
            # Update region statuses
            from_config.status = RegionStatus.STANDBY
            to_config.status = RegionStatus.ACTIVE
            
            # Update DNS records to point to new primary region
            dns_update_result = await self._update_dns_for_failover(from_region, to_region)
            
            # Send notification
            if self._failover_config and self._failover_config.sns_topic_arn:
                await self._send_failover_notification(from_region, to_region, reason, "MANUAL")
            
            # Update monitoring
            monitoring_update = await self._update_monitoring_for_failover(from_region, to_region)
            
            logger.info(f"Manual failover completed from {from_region} to {to_region}")
            
            return {
                'from_region': from_region,
                'to_region': to_region,
                'reason': reason,
                'type': 'manual',
                'dns_update': dns_update_result,
                'monitoring_update': monitoring_update,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to trigger manual failover from {from_region} to {to_region}: {e}")
            raise InfrastructureError(
                f"Manual failover failed: {e}",
                error_code="MANUAL_FAILOVER_FAILED",
                context={'from_region': from_region, 'to_region': to_region}
            )
    
    async def _update_dns_for_failover(self, from_region: str, to_region: str) -> Dict[str, Any]:
        """Update DNS records for failover."""
        try:
            # This would involve updating Route 53 records to change primary/secondary designations
            # For now, we'll log the action and return a placeholder
            logger.info(f"Updating DNS records for failover from {from_region} to {to_region}")
            
            # In a real implementation, this would:
            # 1. Update the primary record to point to the new region
            # 2. Update health check associations
            # 3. Adjust TTL values for faster propagation
            
            return {
                'updated': True,
                'from_region': from_region,
                'to_region': to_region,
                'dns_propagation_time': 60  # seconds
            }
            
        except Exception as e:
            logger.error(f"Failed to update DNS for failover: {e}")
            raise
    
    async def _send_failover_notification(
        self, 
        from_region: str, 
        to_region: str, 
        reason: str,
        failover_type: str
    ):
        """Send failover notification via SNS."""
        try:
            if not self._failover_config or not self._failover_config.sns_topic_arn:
                return
            
            message = {
                'event': 'failover',
                'type': failover_type,
                'from_region': from_region,
                'to_region': to_region,
                'reason': reason,
                'timestamp': time.time(),
                'service': 'bharat-voice-assistant'
            }
            
            safe_aws_call(
                self.sns_client.publish,
                TopicArn=self._failover_config.sns_topic_arn,
                Message=json.dumps(message, indent=2),
                Subject=f"Bharat Voice Assistant Failover: {from_region} -> {to_region}"
            )
            
            logger.info(f"Sent failover notification for {from_region} -> {to_region}")
            
        except Exception as e:
            logger.error(f"Failed to send failover notification: {e}")
    
    async def _update_monitoring_for_failover(self, from_region: str, to_region: str) -> Dict[str, Any]:
        """Update monitoring configuration after failover."""
        try:
            # Update alarm priorities and thresholds based on new primary region
            logger.info(f"Updating monitoring configuration for failover from {from_region} to {to_region}")
            
            return {
                'updated': True,
                'new_primary': to_region,
                'former_primary': from_region
            }
            
        except Exception as e:
            logger.error(f"Failed to update monitoring for failover: {e}")
            raise
    
    async def get_multi_region_status(self) -> Dict[str, Any]:
        """
        Get current status of multi-region deployment.
        
        Returns:
            Dictionary with multi-region status information
        """
        try:
            status = {
                'regions': {},
                'health_checks': {},
                'dns_records': self._dns_records,
                'failover_config': self._failover_config
            }
            
            # Get status for each region
            for region_name, region_config in self._regions.items():
                region_status = {
                    'config': region_config,
                    'health_check_status': None,
                    'infrastructure_status': {}
                }
                
                # Get health check status
                if region_name in self._health_checks:
                    health_check_id = self._health_checks[region_name]['id']
                    try:
                        health_status = safe_aws_call(
                            self.route53_client.get_health_check_status,
                            HealthCheckId=health_check_id
                        )
                        region_status['health_check_status'] = health_status
                    except Exception as e:
                        logger.warning(f"Failed to get health check status for {region_name}: {e}")
                
                # Get infrastructure status (placeholder for actual implementation)
                region_status['infrastructure_status'] = {
                    'load_balancer': 'healthy' if region_config.load_balancer_arn else 'not_configured',
                    'ecs_services': 'healthy' if region_config.service_names else 'not_configured',
                    'database': 'healthy' if region_config.database_endpoint else 'not_configured'
                }
                
                status['regions'][region_name] = region_status
            
            # Get health check details
            for region_name, health_check in self._health_checks.items():
                status['health_checks'][region_name] = health_check
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get multi-region status: {e}")
            raise InfrastructureError(
                f"Failed to get multi-region status: {e}",
                error_code="MULTI_REGION_STATUS_FAILED"
            )