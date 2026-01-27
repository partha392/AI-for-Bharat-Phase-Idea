"""
Load balancer management for the Bharat Voice Assistant.

This module provides comprehensive load balancing capabilities including:
- Application Load Balancers (ALB) for HTTP/HTTPS traffic
- Network Load Balancers (NLB) for TCP/UDP traffic
- Target group management with health checks
- SSL/TLS certificate management
- Multi-region load balancing
"""

import boto3
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import time

from ..core.logging import get_logger
from ..core.aws_client import aws_clients, safe_aws_call
from ..core.exceptions import InfrastructureError


logger = get_logger(__name__)


class LoadBalancerType(Enum):
    """Supported load balancer types."""
    APPLICATION = "application"
    NETWORK = "network"
    GATEWAY = "gateway"


class TargetType(Enum):
    """Target types for target groups."""
    INSTANCE = "instance"
    IP = "ip"
    LAMBDA = "lambda"
    ALB = "alb"


class ProtocolType(Enum):
    """Supported protocols."""
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    TCP = "TCP"
    TLS = "TLS"
    UDP = "UDP"
    TCP_UDP = "TCP_UDP"
    GENEVE = "GENEVE"


class HealthCheckProtocol(Enum):
    """Health check protocols."""
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    TCP = "TCP"


@dataclass
class TargetGroupConfig:
    """Configuration for a target group."""
    name: str
    protocol: ProtocolType
    port: int
    vpc_id: str
    target_type: TargetType = TargetType.INSTANCE
    
    # Health check configuration
    health_check_enabled: bool = True
    health_check_protocol: HealthCheckProtocol = HealthCheckProtocol.HTTP
    health_check_port: str = "traffic-port"
    health_check_path: str = "/health"
    health_check_interval_seconds: int = 30
    health_check_timeout_seconds: int = 5
    healthy_threshold_count: int = 2
    unhealthy_threshold_count: int = 3
    
    # Target group attributes
    deregistration_delay_timeout_seconds: int = 300
    stickiness_enabled: bool = False
    stickiness_type: str = "lb_cookie"
    stickiness_duration_seconds: int = 86400
    
    # Load balancing algorithm
    load_balancing_algorithm_type: str = "round_robin"  # round_robin, least_outstanding_requests
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default health check protocol based on target protocol."""
        if self.health_check_protocol == HealthCheckProtocol.HTTP and self.protocol == ProtocolType.HTTPS:
            self.health_check_protocol = HealthCheckProtocol.HTTPS


@dataclass
class LoadBalancerConfig:
    """Configuration for a load balancer."""
    name: str
    load_balancer_type: LoadBalancerType
    scheme: str = "internet-facing"  # internet-facing or internal
    ip_address_type: str = "ipv4"  # ipv4 or dualstack
    
    # Network configuration
    subnets: List[str] = field(default_factory=list)
    security_groups: List[str] = field(default_factory=list)
    
    # Target groups
    target_groups: List[TargetGroupConfig] = field(default_factory=list)
    
    # SSL/TLS configuration
    certificate_arn: Optional[str] = None
    ssl_policy: str = "ELBSecurityPolicy-TLS-1-2-2017-01"
    
    # Access logging
    access_logs_enabled: bool = True
    access_logs_s3_bucket: Optional[str] = None
    access_logs_s3_prefix: Optional[str] = None
    
    # Connection settings
    idle_timeout_seconds: int = 60
    deletion_protection_enabled: bool = True
    
    # Cross-zone load balancing (NLB only)
    cross_zone_load_balancing_enabled: bool = True
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default values based on load balancer type."""
        if not self.target_groups:
            # Create default target group
            default_tg = TargetGroupConfig(
                name=f"{self.name}-default-tg",
                protocol=ProtocolType.HTTP if self.load_balancer_type == LoadBalancerType.APPLICATION else ProtocolType.TCP,
                port=80 if self.load_balancer_type == LoadBalancerType.APPLICATION else 8000,
                vpc_id="",  # Will be set when creating
                target_type=TargetType.INSTANCE
            )
            self.target_groups = [default_tg]
        
        # Set default tags
        if not self.tags:
            self.tags = {
                "Name": self.name,
                "Service": "bharat-voice-assistant",
                "Environment": "production"
            }


class LoadBalancerManager:
    """Manages load balancers and target groups for the voice assistant infrastructure."""
    
    def __init__(self):
        """Initialize the load balancer manager."""
        self.elbv2_client = aws_clients.get_custom_client('elbv2')
        self.ec2_client = aws_clients.get_custom_client('ec2')
        self.acm_client = aws_clients.get_custom_client('acm')
        
        self._load_balancers: Dict[str, Dict[str, Any]] = {}
        self._target_groups: Dict[str, Dict[str, Any]] = {}
    
    async def create_load_balancer(self, config: LoadBalancerConfig) -> Dict[str, Any]:
        """
        Create a load balancer with target groups.
        
        Args:
            config: Load balancer configuration
            
        Returns:
            Dictionary with load balancer and target group information
        """
        try:
            # Validate configuration
            await self._validate_load_balancer_config(config)
            
            # Create load balancer
            lb_response = await self._create_load_balancer(config)
            load_balancer_arn = lb_response['LoadBalancers'][0]['LoadBalancerArn']
            
            # Create target groups
            target_groups = []
            for tg_config in config.target_groups:
                tg_response = await self._create_target_group(tg_config, config)
                target_groups.append(tg_response)
            
            # Create listeners
            listeners = []
            for i, tg_config in enumerate(config.target_groups):
                listener_response = await self._create_listener(
                    config, load_balancer_arn, target_groups[i]['TargetGroupArn'], tg_config
                )
                listeners.append(listener_response)
            
            # Store configuration
            self._load_balancers[config.name] = {
                'config': config,
                'load_balancer': lb_response['LoadBalancers'][0],
                'target_groups': target_groups,
                'listeners': listeners
            }
            
            logger.info(f"Created load balancer {config.name} with {len(target_groups)} target groups")
            
            return {
                'load_balancer': lb_response['LoadBalancers'][0],
                'target_groups': target_groups,
                'listeners': listeners
            }
            
        except Exception as e:
            logger.error(f"Failed to create load balancer {config.name}: {e}")
            raise InfrastructureError(
                f"Failed to create load balancer: {e}",
                error_code="LOAD_BALANCER_CREATION_FAILED",
                context={'load_balancer_name': config.name}
            )
    
    async def _validate_load_balancer_config(self, config: LoadBalancerConfig):
        """Validate load balancer configuration."""
        if not config.subnets:
            raise InfrastructureError(
                "At least one subnet must be specified",
                error_code="MISSING_SUBNETS"
            )
        
        if len(config.subnets) < 2 and config.scheme == "internet-facing":
            raise InfrastructureError(
                "Internet-facing load balancers require at least 2 subnets in different AZs",
                error_code="INSUFFICIENT_SUBNETS"
            )
        
        if config.load_balancer_type == LoadBalancerType.APPLICATION and not config.security_groups:
            raise InfrastructureError(
                "Application load balancers require security groups",
                error_code="MISSING_SECURITY_GROUPS"
            )
        
        # Validate target groups
        for tg_config in config.target_groups:
            if not tg_config.vpc_id:
                # Get VPC ID from subnet
                subnet_response = safe_aws_call(
                    self.ec2_client.describe_subnets,
                    SubnetIds=[config.subnets[0]]
                )
                tg_config.vpc_id = subnet_response['Subnets'][0]['VpcId']
    
    async def _create_load_balancer(self, config: LoadBalancerConfig) -> Dict[str, Any]:
        """Create the load balancer."""
        create_params = {
            'Name': config.name,
            'Subnets': config.subnets,
            'Type': config.load_balancer_type.value,
            'Scheme': config.scheme,
            'IpAddressType': config.ip_address_type,
            'Tags': [{'Key': k, 'Value': v} for k, v in config.tags.items()]
        }
        
        # Add security groups for ALB
        if config.load_balancer_type == LoadBalancerType.APPLICATION:
            create_params['SecurityGroups'] = config.security_groups
        
        lb_response = safe_aws_call(
            self.elbv2_client.create_load_balancer,
            **create_params
        )
        
        # Configure load balancer attributes
        attributes = []
        
        if config.load_balancer_type == LoadBalancerType.APPLICATION:
            attributes.extend([
                {'Key': 'idle_timeout.timeout_seconds', 'Value': str(config.idle_timeout_seconds)},
                {'Key': 'deletion_protection.enabled', 'Value': str(config.deletion_protection_enabled).lower()}
            ])
        elif config.load_balancer_type == LoadBalancerType.NETWORK:
            attributes.extend([
                {'Key': 'load_balancing.cross_zone.enabled', 'Value': str(config.cross_zone_load_balancing_enabled).lower()},
                {'Key': 'deletion_protection.enabled', 'Value': str(config.deletion_protection_enabled).lower()}
            ])
        
        # Access logging configuration
        if config.access_logs_enabled and config.access_logs_s3_bucket:
            attributes.extend([
                {'Key': 'access_logs.s3.enabled', 'Value': 'true'},
                {'Key': 'access_logs.s3.bucket', 'Value': config.access_logs_s3_bucket}
            ])
            if config.access_logs_s3_prefix:
                attributes.append({
                    'Key': 'access_logs.s3.prefix', 
                    'Value': config.access_logs_s3_prefix
                })
        
        if attributes:
            safe_aws_call(
                self.elbv2_client.modify_load_balancer_attributes,
                LoadBalancerArn=lb_response['LoadBalancers'][0]['LoadBalancerArn'],
                Attributes=attributes
            )
        
        return lb_response
    
    async def _create_target_group(
        self, 
        tg_config: TargetGroupConfig, 
        lb_config: LoadBalancerConfig
    ) -> Dict[str, Any]:
        """Create a target group."""
        create_params = {
            'Name': tg_config.name,
            'Protocol': tg_config.protocol.value,
            'Port': tg_config.port,
            'VpcId': tg_config.vpc_id,
            'TargetType': tg_config.target_type.value,
            'Tags': [{'Key': k, 'Value': v} for k, v in tg_config.tags.items()]
        }
        
        # Add health check configuration
        if tg_config.health_check_enabled:
            create_params.update({
                'HealthCheckEnabled': True,
                'HealthCheckProtocol': tg_config.health_check_protocol.value,
                'HealthCheckPort': tg_config.health_check_port,
                'HealthCheckIntervalSeconds': tg_config.health_check_interval_seconds,
                'HealthCheckTimeoutSeconds': tg_config.health_check_timeout_seconds,
                'HealthyThresholdCount': tg_config.healthy_threshold_count,
                'UnhealthyThresholdCount': tg_config.unhealthy_threshold_count
            })
            
            # Add health check path for HTTP/HTTPS
            if tg_config.health_check_protocol in [HealthCheckProtocol.HTTP, HealthCheckProtocol.HTTPS]:
                create_params['HealthCheckPath'] = tg_config.health_check_path
        
        tg_response = safe_aws_call(
            self.elbv2_client.create_target_group,
            **create_params
        )
        
        target_group_arn = tg_response['TargetGroups'][0]['TargetGroupArn']
        
        # Configure target group attributes
        attributes = [
            {
                'Key': 'deregistration_delay.timeout_seconds',
                'Value': str(tg_config.deregistration_delay_timeout_seconds)
            },
            {
                'Key': 'load_balancing.algorithm.type',
                'Value': tg_config.load_balancing_algorithm_type
            }
        ]
        
        # Stickiness configuration
        if tg_config.stickiness_enabled:
            attributes.extend([
                {'Key': 'stickiness.enabled', 'Value': 'true'},
                {'Key': 'stickiness.type', 'Value': tg_config.stickiness_type},
                {'Key': 'stickiness.lb_cookie.duration_seconds', 'Value': str(tg_config.stickiness_duration_seconds)}
            ])
        
        safe_aws_call(
            self.elbv2_client.modify_target_group_attributes,
            TargetGroupArn=target_group_arn,
            Attributes=attributes
        )
        
        # Store target group
        self._target_groups[tg_config.name] = {
            'config': tg_config,
            'target_group': tg_response['TargetGroups'][0]
        }
        
        return tg_response['TargetGroups'][0]
    
    async def _create_listener(
        self, 
        lb_config: LoadBalancerConfig,
        load_balancer_arn: str,
        target_group_arn: str,
        tg_config: TargetGroupConfig
    ) -> Dict[str, Any]:
        """Create a listener for the load balancer."""
        listener_params = {
            'LoadBalancerArn': load_balancer_arn,
            'Protocol': tg_config.protocol.value,
            'Port': tg_config.port,
            'DefaultActions': [
                {
                    'Type': 'forward',
                    'TargetGroupArn': target_group_arn
                }
            ]
        }
        
        # Add SSL certificate for HTTPS/TLS
        if tg_config.protocol in [ProtocolType.HTTPS, ProtocolType.TLS] and lb_config.certificate_arn:
            listener_params['Certificates'] = [
                {'CertificateArn': lb_config.certificate_arn}
            ]
            listener_params['SslPolicy'] = lb_config.ssl_policy
        
        listener_response = safe_aws_call(
            self.elbv2_client.create_listener,
            **listener_params
        )
        
        return listener_response['Listeners'][0]
    
    async def register_targets(
        self, 
        target_group_name: str, 
        targets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Register targets with a target group.
        
        Args:
            target_group_name: Name of the target group
            targets: List of target dictionaries with 'Id' and optional 'Port'
            
        Returns:
            Dictionary with registration results
        """
        try:
            if target_group_name not in self._target_groups:
                raise InfrastructureError(
                    f"Target group {target_group_name} not found",
                    error_code="TARGET_GROUP_NOT_FOUND"
                )
            
            target_group_arn = self._target_groups[target_group_name]['target_group']['TargetGroupArn']
            
            # Format targets for AWS API
            formatted_targets = []
            for target in targets:
                formatted_target = {'Id': target['Id']}
                if 'Port' in target:
                    formatted_target['Port'] = target['Port']
                formatted_targets.append(formatted_target)
            
            safe_aws_call(
                self.elbv2_client.register_targets,
                TargetGroupArn=target_group_arn,
                Targets=formatted_targets
            )
            
            logger.info(f"Registered {len(targets)} targets with target group {target_group_name}")
            
            return {
                'target_group_name': target_group_name,
                'registered_targets': formatted_targets,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Failed to register targets with {target_group_name}: {e}")
            raise InfrastructureError(
                f"Failed to register targets: {e}",
                error_code="TARGET_REGISTRATION_FAILED",
                context={'target_group_name': target_group_name}
            )
    
    async def deregister_targets(
        self, 
        target_group_name: str, 
        targets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Deregister targets from a target group.
        
        Args:
            target_group_name: Name of the target group
            targets: List of target dictionaries with 'Id' and optional 'Port'
            
        Returns:
            Dictionary with deregistration results
        """
        try:
            if target_group_name not in self._target_groups:
                raise InfrastructureError(
                    f"Target group {target_group_name} not found",
                    error_code="TARGET_GROUP_NOT_FOUND"
                )
            
            target_group_arn = self._target_groups[target_group_name]['target_group']['TargetGroupArn']
            
            # Format targets for AWS API
            formatted_targets = []
            for target in targets:
                formatted_target = {'Id': target['Id']}
                if 'Port' in target:
                    formatted_target['Port'] = target['Port']
                formatted_targets.append(formatted_target)
            
            safe_aws_call(
                self.elbv2_client.deregister_targets,
                TargetGroupArn=target_group_arn,
                Targets=formatted_targets
            )
            
            logger.info(f"Deregistered {len(targets)} targets from target group {target_group_name}")
            
            return {
                'target_group_name': target_group_name,
                'deregistered_targets': formatted_targets,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Failed to deregister targets from {target_group_name}: {e}")
            raise InfrastructureError(
                f"Failed to deregister targets: {e}",
                error_code="TARGET_DEREGISTRATION_FAILED",
                context={'target_group_name': target_group_name}
            )
    
    async def get_target_health(self, target_group_name: str) -> Dict[str, Any]:
        """
        Get health status of targets in a target group.
        
        Args:
            target_group_name: Name of the target group
            
        Returns:
            Dictionary with target health information
        """
        try:
            if target_group_name not in self._target_groups:
                raise InfrastructureError(
                    f"Target group {target_group_name} not found",
                    error_code="TARGET_GROUP_NOT_FOUND"
                )
            
            target_group_arn = self._target_groups[target_group_name]['target_group']['TargetGroupArn']
            
            health_response = safe_aws_call(
                self.elbv2_client.describe_target_health,
                TargetGroupArn=target_group_arn
            )
            
            return {
                'target_group_name': target_group_name,
                'target_health_descriptions': health_response['TargetHealthDescriptions']
            }
            
        except Exception as e:
            logger.error(f"Failed to get target health for {target_group_name}: {e}")
            raise InfrastructureError(
                f"Failed to get target health: {e}",
                error_code="TARGET_HEALTH_FAILED",
                context={'target_group_name': target_group_name}
            )
    
    async def get_load_balancer_status(self, load_balancer_name: str) -> Dict[str, Any]:
        """
        Get status and metrics for a load balancer.
        
        Args:
            load_balancer_name: Name of the load balancer
            
        Returns:
            Dictionary with load balancer status and metrics
        """
        try:
            if load_balancer_name not in self._load_balancers:
                raise InfrastructureError(
                    f"Load balancer {load_balancer_name} not found",
                    error_code="LOAD_BALANCER_NOT_FOUND"
                )
            
            lb_info = self._load_balancers[load_balancer_name]
            load_balancer_arn = lb_info['load_balancer']['LoadBalancerArn']
            
            # Get load balancer details
            lb_response = safe_aws_call(
                self.elbv2_client.describe_load_balancers,
                LoadBalancerArns=[load_balancer_arn]
            )
            
            # Get target group health for all target groups
            target_health = {}
            for tg in lb_info['target_groups']:
                tg_name = tg['TargetGroupName']
                health_info = await self.get_target_health(tg_name)
                target_health[tg_name] = health_info['target_health_descriptions']
            
            return {
                'load_balancer_name': load_balancer_name,
                'load_balancer': lb_response['LoadBalancers'][0],
                'target_health': target_health,
                'listeners': lb_info['listeners']
            }
            
        except Exception as e:
            logger.error(f"Failed to get load balancer status for {load_balancer_name}: {e}")
            raise InfrastructureError(
                f"Failed to get load balancer status: {e}",
                error_code="LOAD_BALANCER_STATUS_FAILED",
                context={'load_balancer_name': load_balancer_name}
            )
    
    async def delete_load_balancer(self, load_balancer_name: str) -> Dict[str, Any]:
        """
        Delete a load balancer and its associated resources.
        
        Args:
            load_balancer_name: Name of the load balancer
            
        Returns:
            Dictionary with deletion results
        """
        try:
            if load_balancer_name not in self._load_balancers:
                logger.warning(f"Load balancer {load_balancer_name} not found, nothing to delete")
                return {'load_balancer_name': load_balancer_name, 'deleted': False, 'reason': 'not_found'}
            
            lb_info = self._load_balancers[load_balancer_name]
            load_balancer_arn = lb_info['load_balancer']['LoadBalancerArn']
            
            # Delete load balancer (this also deletes listeners)
            safe_aws_call(
                self.elbv2_client.delete_load_balancer,
                LoadBalancerArn=load_balancer_arn
            )
            
            # Delete target groups
            deleted_target_groups = []
            for tg in lb_info['target_groups']:
                try:
                    safe_aws_call(
                        self.elbv2_client.delete_target_group,
                        TargetGroupArn=tg['TargetGroupArn']
                    )
                    deleted_target_groups.append(tg['TargetGroupName'])
                    
                    # Remove from local storage
                    if tg['TargetGroupName'] in self._target_groups:
                        del self._target_groups[tg['TargetGroupName']]
                        
                except Exception as e:
                    logger.warning(f"Failed to delete target group {tg['TargetGroupName']}: {e}")
            
            # Remove from local storage
            del self._load_balancers[load_balancer_name]
            
            logger.info(f"Deleted load balancer {load_balancer_name} and {len(deleted_target_groups)} target groups")
            
            return {
                'load_balancer_name': load_balancer_name,
                'deleted': True,
                'deleted_target_groups': deleted_target_groups
            }
            
        except Exception as e:
            logger.error(f"Failed to delete load balancer {load_balancer_name}: {e}")
            raise InfrastructureError(
                f"Failed to delete load balancer: {e}",
                error_code="LOAD_BALANCER_DELETION_FAILED",
                context={'load_balancer_name': load_balancer_name}
            )