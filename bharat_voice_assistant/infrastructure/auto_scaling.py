"""
Auto-scaling group management for the Bharat Voice Assistant.

This module provides comprehensive auto-scaling capabilities including:
- ECS service auto-scaling
- EC2 auto-scaling groups
- Lambda concurrency scaling
- Custom scaling policies based on voice processing load
"""

import boto3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import time

from ..core.logging import get_logger
from ..core.aws_client import aws_clients, safe_aws_call
from ..core.exceptions import InfrastructureError


logger = get_logger(__name__)


class ScalingMetric(Enum):
    """Supported scaling metrics."""
    CPU_UTILIZATION = "CPUUtilization"
    MEMORY_UTILIZATION = "MemoryUtilization"
    REQUEST_COUNT = "RequestCount"
    VOICE_PROCESSING_QUEUE = "VoiceProcessingQueue"
    ACTIVE_CONNECTIONS = "ActiveConnections"
    RESPONSE_TIME = "ResponseTime"


class ScalingDirection(Enum):
    """Scaling direction."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"


@dataclass
class ScalingPolicy:
    """Configuration for a scaling policy."""
    name: str
    metric: ScalingMetric
    threshold: float
    direction: ScalingDirection
    adjustment_type: str = "ChangeInCapacity"  # ChangeInCapacity, ExactCapacity, PercentChangeInCapacity
    scaling_adjustment: int = 1
    cooldown_seconds: int = 300
    evaluation_periods: int = 2
    datapoints_to_alarm: int = 2
    comparison_operator: str = "GreaterThanThreshold"  # For scale up
    
    def __post_init__(self):
        """Set default comparison operator based on scaling direction."""
        if self.direction == ScalingDirection.SCALE_DOWN and self.comparison_operator == "GreaterThanThreshold":
            self.comparison_operator = "LessThanThreshold"


@dataclass
class AutoScalingConfig:
    """Configuration for auto-scaling groups."""
    service_name: str
    min_capacity: int = 2
    max_capacity: int = 100
    desired_capacity: int = 5
    target_group_arn: Optional[str] = None
    health_check_type: str = "ELB"  # ELB or EC2
    health_check_grace_period: int = 300
    default_cooldown: int = 300
    scaling_policies: List[ScalingPolicy] = field(default_factory=list)
    
    # ECS-specific settings
    cluster_name: Optional[str] = None
    service_arn: Optional[str] = None
    
    # EC2-specific settings
    launch_template_id: Optional[str] = None
    launch_template_version: str = "$Latest"
    vpc_zone_identifiers: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Set default scaling policies if none provided."""
        if not self.scaling_policies:
            self.scaling_policies = [
                # Scale up on high CPU
                ScalingPolicy(
                    name=f"{self.service_name}-scale-up-cpu",
                    metric=ScalingMetric.CPU_UTILIZATION,
                    threshold=70.0,
                    direction=ScalingDirection.SCALE_UP,
                    scaling_adjustment=2,
                    cooldown_seconds=300
                ),
                # Scale down on low CPU
                ScalingPolicy(
                    name=f"{self.service_name}-scale-down-cpu",
                    metric=ScalingMetric.CPU_UTILIZATION,
                    threshold=30.0,
                    direction=ScalingDirection.SCALE_DOWN,
                    scaling_adjustment=-1,
                    cooldown_seconds=300
                ),
                # Scale up on high request count
                ScalingPolicy(
                    name=f"{self.service_name}-scale-up-requests",
                    metric=ScalingMetric.REQUEST_COUNT,
                    threshold=1000.0,
                    direction=ScalingDirection.SCALE_UP,
                    scaling_adjustment=3,
                    cooldown_seconds=180
                ),
                # Scale up on voice processing queue depth
                ScalingPolicy(
                    name=f"{self.service_name}-scale-up-voice-queue",
                    metric=ScalingMetric.VOICE_PROCESSING_QUEUE,
                    threshold=50.0,
                    direction=ScalingDirection.SCALE_UP,
                    scaling_adjustment=2,
                    cooldown_seconds=120
                )
            ]


class AutoScalingManager:
    """Manages auto-scaling groups and policies for the voice assistant infrastructure."""
    
    def __init__(self):
        """Initialize the auto-scaling manager."""
        self.autoscaling_client = aws_clients.get_custom_client('autoscaling')
        self.ecs_client = aws_clients.get_custom_client('ecs')
        self.cloudwatch_client = aws_clients.cloudwatch
        self.application_autoscaling_client = aws_clients.get_custom_client('application-autoscaling')
        
        self._scaling_groups: Dict[str, AutoScalingConfig] = {}
        self._scaling_policies: Dict[str, Dict[str, Any]] = {}
    
    async def create_ecs_auto_scaling(self, config: AutoScalingConfig) -> Dict[str, Any]:
        """
        Create auto-scaling for an ECS service.
        
        Args:
            config: Auto-scaling configuration
            
        Returns:
            Dictionary with scaling target and policy information
        """
        try:
            if not config.cluster_name or not config.service_arn:
                raise InfrastructureError(
                    "ECS cluster name and service ARN required for ECS auto-scaling",
                    error_code="MISSING_ECS_CONFIG"
                )
            
            # Register scalable target
            resource_id = f"service/{config.cluster_name}/{config.service_name}"
            
            scalable_target = safe_aws_call(
                self.application_autoscaling_client.register_scalable_target,
                ServiceNamespace='ecs',
                ResourceId=resource_id,
                ScalableDimension='ecs:service:DesiredCount',
                MinCapacity=config.min_capacity,
                MaxCapacity=config.max_capacity
            )
            
            logger.info(f"Created ECS scalable target for {config.service_name}")
            
            # Create scaling policies
            policies = []
            for policy in config.scaling_policies:
                policy_response = await self._create_ecs_scaling_policy(
                    config, policy, resource_id
                )
                policies.append(policy_response)
            
            # Store configuration
            self._scaling_groups[config.service_name] = config
            
            return {
                'scalable_target': scalable_target,
                'policies': policies,
                'resource_id': resource_id
            }
            
        except Exception as e:
            logger.error(f"Failed to create ECS auto-scaling for {config.service_name}: {e}")
            raise InfrastructureError(
                f"Failed to create ECS auto-scaling: {e}",
                error_code="ECS_AUTOSCALING_CREATION_FAILED",
                context={'service_name': config.service_name}
            )
    
    async def _create_ecs_scaling_policy(
        self, 
        config: AutoScalingConfig, 
        policy: ScalingPolicy,
        resource_id: str
    ) -> Dict[str, Any]:
        """Create a scaling policy for ECS service."""
        try:
            # Create the scaling policy
            policy_response = safe_aws_call(
                self.application_autoscaling_client.put_scaling_policy,
                PolicyName=policy.name,
                ServiceNamespace='ecs',
                ResourceId=resource_id,
                ScalableDimension='ecs:service:DesiredCount',
                PolicyType='TargetTrackingScaling' if policy.metric in [
                    ScalingMetric.CPU_UTILIZATION, 
                    ScalingMetric.MEMORY_UTILIZATION
                ] else 'StepScaling',
                **self._get_policy_configuration(policy)
            )
            
            # Create CloudWatch alarm
            alarm_response = await self._create_cloudwatch_alarm(
                config, policy, policy_response['PolicyARN']
            )
            
            logger.info(f"Created scaling policy {policy.name} for {config.service_name}")
            
            return {
                'policy': policy_response,
                'alarm': alarm_response,
                'policy_config': policy
            }
            
        except Exception as e:
            logger.error(f"Failed to create scaling policy {policy.name}: {e}")
            raise
    
    def _get_policy_configuration(self, policy: ScalingPolicy) -> Dict[str, Any]:
        """Get policy configuration based on metric type."""
        if policy.metric in [ScalingMetric.CPU_UTILIZATION, ScalingMetric.MEMORY_UTILIZATION]:
            # Target tracking scaling
            return {
                'TargetTrackingScalingPolicyConfiguration': {
                    'TargetValue': policy.threshold,
                    'PredefinedMetricSpecification': {
                        'PredefinedMetricType': f'ECS{policy.metric.value}'
                    },
                    'ScaleOutCooldown': policy.cooldown_seconds,
                    'ScaleInCooldown': policy.cooldown_seconds
                }
            }
        else:
            # Step scaling
            return {
                'StepScalingPolicyConfiguration': {
                    'AdjustmentType': policy.adjustment_type,
                    'StepAdjustments': [
                        {
                            'MetricIntervalLowerBound': 0,
                            'ScalingAdjustment': policy.scaling_adjustment
                        }
                    ],
                    'Cooldown': policy.cooldown_seconds
                }
            }
    
    async def _create_cloudwatch_alarm(
        self, 
        config: AutoScalingConfig, 
        policy: ScalingPolicy,
        policy_arn: str
    ) -> Dict[str, Any]:
        """Create CloudWatch alarm for scaling policy."""
        try:
            alarm_name = f"{config.service_name}-{policy.name}-alarm"
            
            # Get metric configuration
            metric_config = self._get_metric_configuration(config, policy)
            
            alarm_response = safe_aws_call(
                self.cloudwatch_client.put_metric_alarm,
                AlarmName=alarm_name,
                ComparisonOperator=policy.comparison_operator,
                EvaluationPeriods=policy.evaluation_periods,
                MetricName=metric_config['MetricName'],
                Namespace=metric_config['Namespace'],
                Period=300,  # 5 minutes
                Statistic='Average',
                Threshold=policy.threshold,
                ActionsEnabled=True,
                AlarmActions=[policy_arn],
                AlarmDescription=f'Scaling alarm for {config.service_name} based on {policy.metric.value}',
                Dimensions=metric_config.get('Dimensions', []),
                Unit=metric_config.get('Unit', 'None'),
                DatapointsToAlarm=policy.datapoints_to_alarm
            )
            
            logger.info(f"Created CloudWatch alarm {alarm_name}")
            
            return {
                'alarm_name': alarm_name,
                'alarm_arn': f"arn:aws:cloudwatch:{aws_clients._boto_config.region_name}:*:alarm:{alarm_name}"
            }
            
        except Exception as e:
            logger.error(f"Failed to create CloudWatch alarm for {policy.name}: {e}")
            raise
    
    def _get_metric_configuration(self, config: AutoScalingConfig, policy: ScalingPolicy) -> Dict[str, Any]:
        """Get CloudWatch metric configuration for the scaling policy."""
        if policy.metric == ScalingMetric.CPU_UTILIZATION:
            return {
                'MetricName': 'CPUUtilization',
                'Namespace': 'AWS/ECS',
                'Dimensions': [
                    {'Name': 'ServiceName', 'Value': config.service_name},
                    {'Name': 'ClusterName', 'Value': config.cluster_name}
                ],
                'Unit': 'Percent'
            }
        elif policy.metric == ScalingMetric.MEMORY_UTILIZATION:
            return {
                'MetricName': 'MemoryUtilization',
                'Namespace': 'AWS/ECS',
                'Dimensions': [
                    {'Name': 'ServiceName', 'Value': config.service_name},
                    {'Name': 'ClusterName', 'Value': config.cluster_name}
                ],
                'Unit': 'Percent'
            }
        elif policy.metric == ScalingMetric.REQUEST_COUNT:
            return {
                'MetricName': 'RequestCount',
                'Namespace': 'AWS/ApplicationELB',
                'Dimensions': [
                    {'Name': 'TargetGroup', 'Value': config.target_group_arn.split('/')[-1] if config.target_group_arn else 'unknown'}
                ],
                'Unit': 'Count'
            }
        elif policy.metric == ScalingMetric.VOICE_PROCESSING_QUEUE:
            return {
                'MetricName': 'ApproximateNumberOfMessages',
                'Namespace': 'AWS/SQS',
                'Dimensions': [
                    {'Name': 'QueueName', 'Value': f'{config.service_name}-voice-processing-queue'}
                ],
                'Unit': 'Count'
            }
        elif policy.metric == ScalingMetric.ACTIVE_CONNECTIONS:
            return {
                'MetricName': 'ActiveConnectionCount',
                'Namespace': 'AWS/ApplicationELB',
                'Dimensions': [
                    {'Name': 'LoadBalancer', 'Value': f'{config.service_name}-alb'}
                ],
                'Unit': 'Count'
            }
        else:
            return {
                'MetricName': policy.metric.value,
                'Namespace': 'BharatVoiceAssistant/Custom',
                'Dimensions': [
                    {'Name': 'ServiceName', 'Value': config.service_name}
                ]
            }
    
    async def create_ec2_auto_scaling_group(self, config: AutoScalingConfig) -> Dict[str, Any]:
        """
        Create EC2 auto-scaling group.
        
        Args:
            config: Auto-scaling configuration
            
        Returns:
            Dictionary with auto-scaling group information
        """
        try:
            if not config.launch_template_id:
                raise InfrastructureError(
                    "Launch template ID required for EC2 auto-scaling",
                    error_code="MISSING_LAUNCH_TEMPLATE"
                )
            
            # Create auto-scaling group
            asg_response = safe_aws_call(
                self.autoscaling_client.create_auto_scaling_group,
                AutoScalingGroupName=f"{config.service_name}-asg",
                LaunchTemplate={
                    'LaunchTemplateId': config.launch_template_id,
                    'Version': config.launch_template_version
                },
                MinSize=config.min_capacity,
                MaxSize=config.max_capacity,
                DesiredCapacity=config.desired_capacity,
                DefaultCooldown=config.default_cooldown,
                HealthCheckType=config.health_check_type,
                HealthCheckGracePeriod=config.health_check_grace_period,
                VPCZoneIdentifier=','.join(config.vpc_zone_identifiers),
                TargetGroupARNs=[config.target_group_arn] if config.target_group_arn else [],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': f"{config.service_name}-instance",
                        'PropagateAtLaunch': True,
                        'ResourceId': f"{config.service_name}-asg",
                        'ResourceType': 'auto-scaling-group'
                    },
                    {
                        'Key': 'Service',
                        'Value': config.service_name,
                        'PropagateAtLaunch': True,
                        'ResourceId': f"{config.service_name}-asg",
                        'ResourceType': 'auto-scaling-group'
                    }
                ]
            )
            
            logger.info(f"Created EC2 auto-scaling group for {config.service_name}")
            
            # Create scaling policies
            policies = []
            for policy in config.scaling_policies:
                policy_response = await self._create_ec2_scaling_policy(config, policy)
                policies.append(policy_response)
            
            # Store configuration
            self._scaling_groups[config.service_name] = config
            
            return {
                'auto_scaling_group': f"{config.service_name}-asg",
                'policies': policies
            }
            
        except Exception as e:
            logger.error(f"Failed to create EC2 auto-scaling group for {config.service_name}: {e}")
            raise InfrastructureError(
                f"Failed to create EC2 auto-scaling group: {e}",
                error_code="EC2_AUTOSCALING_CREATION_FAILED",
                context={'service_name': config.service_name}
            )
    
    async def _create_ec2_scaling_policy(
        self, 
        config: AutoScalingConfig, 
        policy: ScalingPolicy
    ) -> Dict[str, Any]:
        """Create a scaling policy for EC2 auto-scaling group."""
        try:
            asg_name = f"{config.service_name}-asg"
            
            # Create the scaling policy
            policy_response = safe_aws_call(
                self.autoscaling_client.put_scaling_policy,
                AutoScalingGroupName=asg_name,
                PolicyName=policy.name,
                PolicyType='SimpleScaling',
                AdjustmentType=policy.adjustment_type,
                ScalingAdjustment=policy.scaling_adjustment,
                Cooldown=policy.cooldown_seconds
            )
            
            # Create CloudWatch alarm
            alarm_response = await self._create_ec2_cloudwatch_alarm(
                config, policy, policy_response['PolicyARN']
            )
            
            logger.info(f"Created EC2 scaling policy {policy.name} for {config.service_name}")
            
            return {
                'policy': policy_response,
                'alarm': alarm_response,
                'policy_config': policy
            }
            
        except Exception as e:
            logger.error(f"Failed to create EC2 scaling policy {policy.name}: {e}")
            raise
    
    async def _create_ec2_cloudwatch_alarm(
        self, 
        config: AutoScalingConfig, 
        policy: ScalingPolicy,
        policy_arn: str
    ) -> Dict[str, Any]:
        """Create CloudWatch alarm for EC2 scaling policy."""
        try:
            alarm_name = f"{config.service_name}-{policy.name}-alarm"
            asg_name = f"{config.service_name}-asg"
            
            alarm_response = safe_aws_call(
                self.cloudwatch_client.put_metric_alarm,
                AlarmName=alarm_name,
                ComparisonOperator=policy.comparison_operator,
                EvaluationPeriods=policy.evaluation_periods,
                MetricName=policy.metric.value,
                Namespace='AWS/EC2',
                Period=300,
                Statistic='Average',
                Threshold=policy.threshold,
                ActionsEnabled=True,
                AlarmActions=[policy_arn],
                AlarmDescription=f'EC2 scaling alarm for {config.service_name} based on {policy.metric.value}',
                Dimensions=[
                    {'Name': 'AutoScalingGroupName', 'Value': asg_name}
                ],
                Unit='Percent' if 'Utilization' in policy.metric.value else 'Count',
                DatapointsToAlarm=policy.datapoints_to_alarm
            )
            
            logger.info(f"Created EC2 CloudWatch alarm {alarm_name}")
            
            return {
                'alarm_name': alarm_name,
                'alarm_arn': f"arn:aws:cloudwatch:{aws_clients._boto_config.region_name}:*:alarm:{alarm_name}"
            }
            
        except Exception as e:
            logger.error(f"Failed to create EC2 CloudWatch alarm for {policy.name}: {e}")
            raise
    
    async def update_scaling_configuration(
        self, 
        service_name: str, 
        config: AutoScalingConfig
    ) -> Dict[str, Any]:
        """
        Update scaling configuration for a service.
        
        Args:
            service_name: Name of the service
            config: Updated auto-scaling configuration
            
        Returns:
            Dictionary with update results
        """
        try:
            if service_name not in self._scaling_groups:
                raise InfrastructureError(
                    f"Scaling group {service_name} not found",
                    error_code="SCALING_GROUP_NOT_FOUND"
                )
            
            old_config = self._scaling_groups[service_name]
            
            # Update capacity if changed
            if (config.min_capacity != old_config.min_capacity or 
                config.max_capacity != old_config.max_capacity or
                config.desired_capacity != old_config.desired_capacity):
                
                if config.cluster_name:  # ECS service
                    resource_id = f"service/{config.cluster_name}/{config.service_name}"
                    safe_aws_call(
                        self.application_autoscaling_client.register_scalable_target,
                        ServiceNamespace='ecs',
                        ResourceId=resource_id,
                        ScalableDimension='ecs:service:DesiredCount',
                        MinCapacity=config.min_capacity,
                        MaxCapacity=config.max_capacity
                    )
                else:  # EC2 auto-scaling group
                    asg_name = f"{config.service_name}-asg"
                    safe_aws_call(
                        self.autoscaling_client.update_auto_scaling_group,
                        AutoScalingGroupName=asg_name,
                        MinSize=config.min_capacity,
                        MaxSize=config.max_capacity,
                        DesiredCapacity=config.desired_capacity
                    )
            
            # Update configuration
            self._scaling_groups[service_name] = config
            
            logger.info(f"Updated scaling configuration for {service_name}")
            
            return {
                'service_name': service_name,
                'updated': True,
                'old_config': old_config,
                'new_config': config
            }
            
        except Exception as e:
            logger.error(f"Failed to update scaling configuration for {service_name}: {e}")
            raise InfrastructureError(
                f"Failed to update scaling configuration: {e}",
                error_code="SCALING_UPDATE_FAILED",
                context={'service_name': service_name}
            )
    
    async def get_scaling_status(self, service_name: str) -> Dict[str, Any]:
        """
        Get current scaling status for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Dictionary with scaling status information
        """
        try:
            if service_name not in self._scaling_groups:
                raise InfrastructureError(
                    f"Scaling group {service_name} not found",
                    error_code="SCALING_GROUP_NOT_FOUND"
                )
            
            config = self._scaling_groups[service_name]
            
            if config.cluster_name:  # ECS service
                resource_id = f"service/{config.cluster_name}/{config.service_name}"
                
                # Get scalable targets
                targets_response = safe_aws_call(
                    self.application_autoscaling_client.describe_scalable_targets,
                    ServiceNamespace='ecs',
                    ResourceIds=[resource_id]
                )
                
                # Get scaling activities
                activities_response = safe_aws_call(
                    self.application_autoscaling_client.describe_scaling_activities,
                    ServiceNamespace='ecs',
                    ResourceId=resource_id,
                    MaxResults=10
                )
                
                return {
                    'service_name': service_name,
                    'type': 'ecs',
                    'targets': targets_response.get('ScalableTargets', []),
                    'recent_activities': activities_response.get('ScalingActivities', [])
                }
                
            else:  # EC2 auto-scaling group
                asg_name = f"{config.service_name}-asg"
                
                # Get auto-scaling group details
                asg_response = safe_aws_call(
                    self.autoscaling_client.describe_auto_scaling_groups,
                    AutoScalingGroupNames=[asg_name]
                )
                
                # Get scaling activities
                activities_response = safe_aws_call(
                    self.autoscaling_client.describe_scaling_activities,
                    AutoScalingGroupName=asg_name,
                    MaxRecords=10
                )
                
                return {
                    'service_name': service_name,
                    'type': 'ec2',
                    'auto_scaling_groups': asg_response.get('AutoScalingGroups', []),
                    'recent_activities': activities_response.get('Activities', [])
                }
                
        except Exception as e:
            logger.error(f"Failed to get scaling status for {service_name}: {e}")
            raise InfrastructureError(
                f"Failed to get scaling status: {e}",
                error_code="SCALING_STATUS_FAILED",
                context={'service_name': service_name}
            )
    
    async def delete_scaling_configuration(self, service_name: str) -> Dict[str, Any]:
        """
        Delete scaling configuration for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Dictionary with deletion results
        """
        try:
            if service_name not in self._scaling_groups:
                logger.warning(f"Scaling group {service_name} not found, nothing to delete")
                return {'service_name': service_name, 'deleted': False, 'reason': 'not_found'}
            
            config = self._scaling_groups[service_name]
            
            if config.cluster_name:  # ECS service
                resource_id = f"service/{config.cluster_name}/{config.service_name}"
                
                # Delete scaling policies
                policies_response = safe_aws_call(
                    self.application_autoscaling_client.describe_scaling_policies,
                    ServiceNamespace='ecs',
                    ResourceId=resource_id
                )
                
                for policy in policies_response.get('ScalingPolicies', []):
                    safe_aws_call(
                        self.application_autoscaling_client.delete_scaling_policy,
                        PolicyName=policy['PolicyName'],
                        ServiceNamespace='ecs',
                        ResourceId=resource_id,
                        ScalableDimension='ecs:service:DesiredCount'
                    )
                
                # Deregister scalable target
                safe_aws_call(
                    self.application_autoscaling_client.deregister_scalable_target,
                    ServiceNamespace='ecs',
                    ResourceId=resource_id,
                    ScalableDimension='ecs:service:DesiredCount'
                )
                
            else:  # EC2 auto-scaling group
                asg_name = f"{config.service_name}-asg"
                
                # Delete scaling policies
                policies_response = safe_aws_call(
                    self.autoscaling_client.describe_policies,
                    AutoScalingGroupName=asg_name
                )
                
                for policy in policies_response.get('ScalingPolicies', []):
                    safe_aws_call(
                        self.autoscaling_client.delete_policy,
                        PolicyName=policy['PolicyName'],
                        AutoScalingGroupName=asg_name
                    )
                
                # Delete auto-scaling group
                safe_aws_call(
                    self.autoscaling_client.delete_auto_scaling_group,
                    AutoScalingGroupName=asg_name,
                    ForceDelete=True
                )
            
            # Remove from local storage
            del self._scaling_groups[service_name]
            
            logger.info(f"Deleted scaling configuration for {service_name}")
            
            return {
                'service_name': service_name,
                'deleted': True,
                'type': 'ecs' if config.cluster_name else 'ec2'
            }
            
        except Exception as e:
            logger.error(f"Failed to delete scaling configuration for {service_name}: {e}")
            raise InfrastructureError(
                f"Failed to delete scaling configuration: {e}",
                error_code="SCALING_DELETION_FAILED",
                context={'service_name': service_name}
            )