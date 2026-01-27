"""
Blue-green deployment management for the Bharat Voice Assistant.

This module provides comprehensive blue-green deployment capabilities including:
- Traffic shifting between environments
- Health monitoring and validation
- Automatic rollback on failure
- Zero-downtime deployments
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from .ecs_deployment import ECSDeploymentManager, ECSDeploymentConfig
from ..infrastructure.load_balancer import LoadBalancerManager
from ..infrastructure.monitoring import MonitoringManager

from ..core.logging import get_logger
from ..core.aws_client import aws_clients, safe_aws_call
from ..core.exceptions import DeploymentError


logger = get_logger(__name__)


class DeploymentEnvironment(Enum):
    """Deployment environments."""
    BLUE = "blue"
    GREEN = "green"


class TrafficShiftStrategy(Enum):
    """Traffic shifting strategies."""
    ALL_AT_ONCE = "all_at_once"
    CANARY = "canary"
    LINEAR = "linear"


class HealthCheckStatus(Enum):
    """Health check statuses."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class TrafficShiftConfig:
    """Configuration for traffic shifting."""
    strategy: TrafficShiftStrategy = TrafficShiftStrategy.CANARY
    
    # Canary configuration
    canary_percentage: int = 10
    canary_duration_minutes: int = 5
    
    # Linear configuration
    linear_percentage_per_minute: int = 10
    
    # Health check configuration
    health_check_interval_seconds: int = 30
    health_check_timeout_seconds: int = 10
    healthy_threshold_count: int = 2
    unhealthy_threshold_count: int = 3
    
    # Rollback configuration
    auto_rollback_enabled: bool = True
    rollback_on_alarm: bool = True
    rollback_on_health_check_failure: bool = True


@dataclass
class BlueGreenConfig:
    """Configuration for blue-green deployment."""
    service_name: str
    cluster_name: str
    
    # Load balancer configuration
    load_balancer_name: str
    target_group_blue: str
    target_group_green: str
    listener_arn: str
    
    # ECS configuration
    blue_service_config: ECSDeploymentConfig
    green_service_config: ECSDeploymentConfig
    
    # Traffic shifting
    traffic_shift_config: TrafficShiftConfig = field(default_factory=TrafficShiftConfig)
    
    # Monitoring
    cloudwatch_alarms: List[str] = field(default_factory=list)
    
    # Notification
    sns_topic_arn: Optional[str] = None
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)


class BlueGreenDeploymentManager:
    """Manages blue-green deployments for the voice assistant."""
    
    def __init__(self):
        """Initialize the blue-green deployment manager."""
        self.ecs_manager = ECSDeploymentManager()
        self.lb_manager = LoadBalancerManager()
        self.monitoring_manager = MonitoringManager()
        
        self.elbv2_client = aws_clients.get_custom_client('elbv2')
        self.cloudwatch_client = aws_clients.cloudwatch
        self.sns_client = aws_clients.get_custom_client('sns')
        
        self._deployments: Dict[str, Dict[str, Any]] = {}
    
    async def deploy_blue_green(
        self, 
        config: BlueGreenConfig,
        new_task_definition_arn: str,
        current_environment: DeploymentEnvironment = DeploymentEnvironment.BLUE
    ) -> Dict[str, Any]:
        """
        Perform blue-green deployment.
        
        Args:
            config: Blue-green deployment configuration
            new_task_definition_arn: New task definition ARN to deploy
            current_environment: Current active environment
            
        Returns:
            Dictionary with deployment results
        """
        try:
            logger.info(f"Starting blue-green deployment for {config.service_name}")
            
            # Determine target environment
            target_environment = (
                DeploymentEnvironment.GREEN 
                if current_environment == DeploymentEnvironment.BLUE 
                else DeploymentEnvironment.BLUE
            )
            
            deployment_id = f"{config.service_name}-{int(time.time())}"
            
            # Store deployment state
            deployment_state = {
                'deployment_id': deployment_id,
                'config': config,
                'current_environment': current_environment,
                'target_environment': target_environment,
                'new_task_definition_arn': new_task_definition_arn,
                'status': 'starting',
                'start_time': time.time()
            }
            
            self._deployments[deployment_id] = deployment_state
            
            try:
                # Step 1: Deploy to target environment
                logger.info(f"Deploying to {target_environment.value} environment")
                target_deployment = await self._deploy_to_target_environment(
                    config, target_environment, new_task_definition_arn
                )
                deployment_state['target_deployment'] = target_deployment
                deployment_state['status'] = 'deployed_to_target'
                
                # Step 2: Health check target environment
                logger.info(f"Performing health checks on {target_environment.value} environment")
                health_check_result = await self._perform_health_checks(
                    config, target_environment
                )
                deployment_state['health_check_result'] = health_check_result
                
                if health_check_result['status'] != HealthCheckStatus.HEALTHY:
                    raise DeploymentError(
                        f"Health checks failed for {target_environment.value} environment",
                        error_code="HEALTH_CHECK_FAILED"
                    )
                
                deployment_state['status'] = 'health_checks_passed'
                
                # Step 3: Shift traffic
                logger.info(f"Shifting traffic to {target_environment.value} environment")
                traffic_shift_result = await self._shift_traffic(
                    config, current_environment, target_environment
                )
                deployment_state['traffic_shift_result'] = traffic_shift_result
                deployment_state['status'] = 'traffic_shifted'
                
                # Step 4: Monitor and validate
                logger.info("Monitoring deployment stability")
                monitoring_result = await self._monitor_deployment(
                    config, target_environment, deployment_id
                )
                deployment_state['monitoring_result'] = monitoring_result
                
                if monitoring_result['stable']:
                    # Step 5: Clean up old environment
                    logger.info(f"Cleaning up {current_environment.value} environment")
                    cleanup_result = await self._cleanup_old_environment(
                        config, current_environment
                    )
                    deployment_state['cleanup_result'] = cleanup_result
                    deployment_state['status'] = 'completed'
                    
                    logger.info(f"Blue-green deployment completed successfully for {config.service_name}")
                else:
                    # Rollback
                    logger.warning("Deployment not stable, initiating rollback")
                    rollback_result = await self._rollback_deployment(
                        config, current_environment, target_environment
                    )
                    deployment_state['rollback_result'] = rollback_result
                    deployment_state['status'] = 'rolled_back'
                
                deployment_state['end_time'] = time.time()
                deployment_state['duration_seconds'] = deployment_state['end_time'] - deployment_state['start_time']
                
                # Send notification
                if config.sns_topic_arn:
                    await self._send_deployment_notification(deployment_state)
                
                return deployment_state
                
            except Exception as e:
                # Rollback on error
                logger.error(f"Deployment failed, initiating rollback: {e}")
                deployment_state['error'] = str(e)
                deployment_state['status'] = 'failed'
                
                try:
                    rollback_result = await self._rollback_deployment(
                        config, current_environment, target_environment
                    )
                    deployment_state['rollback_result'] = rollback_result
                    deployment_state['status'] = 'rolled_back'
                except Exception as rollback_error:
                    logger.error(f"Rollback also failed: {rollback_error}")
                    deployment_state['rollback_error'] = str(rollback_error)
                    deployment_state['status'] = 'rollback_failed'
                
                deployment_state['end_time'] = time.time()
                deployment_state['duration_seconds'] = deployment_state['end_time'] - deployment_state['start_time']
                
                raise
                
        except Exception as e:
            logger.error(f"Blue-green deployment failed for {config.service_name}: {e}")
            raise DeploymentError(
                f"Blue-green deployment failed: {e}",
                error_code="BLUE_GREEN_DEPLOYMENT_FAILED",
                context={'service_name': config.service_name}
            )
    
    async def _deploy_to_target_environment(
        self, 
        config: BlueGreenConfig,
        target_environment: DeploymentEnvironment,
        task_definition_arn: str
    ) -> Dict[str, Any]:
        """Deploy to target environment."""
        try:
            # Get target service configuration
            if target_environment == DeploymentEnvironment.BLUE:
                service_config = config.blue_service_config
            else:
                service_config = config.green_service_config
            
            # Update task definition
            service_config.task_definition_family = task_definition_arn.split('/')[-1].split(':')[0]
            
            # Deploy service
            deployment_result = await self.ecs_manager.deploy_service(service_config)
            
            return {
                'environment': target_environment.value,
                'deployment': deployment_result,
                'task_definition_arn': task_definition_arn
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy to {target_environment.value} environment: {e}")
            raise
    
    async def _perform_health_checks(
        self, 
        config: BlueGreenConfig,
        target_environment: DeploymentEnvironment
    ) -> Dict[str, Any]:
        """Perform health checks on target environment."""
        try:
            # Get target group name
            target_group_name = (
                config.target_group_blue 
                if target_environment == DeploymentEnvironment.BLUE 
                else config.target_group_green
            )
            
            # Perform health checks
            health_check_attempts = 0
            max_attempts = 10
            healthy_checks = 0
            required_healthy_checks = config.traffic_shift_config.healthy_threshold_count
            
            while health_check_attempts < max_attempts:
                try:
                    # Get target health
                    target_health = await self.lb_manager.get_target_health(target_group_name)
                    
                    # Check if all targets are healthy
                    healthy_targets = 0
                    total_targets = len(target_health['target_health_descriptions'])
                    
                    for target_health_desc in target_health['target_health_descriptions']:
                        if target_health_desc['TargetHealth']['State'] == 'healthy':
                            healthy_targets += 1
                    
                    if healthy_targets == total_targets and total_targets > 0:
                        healthy_checks += 1
                        if healthy_checks >= required_healthy_checks:
                            return {
                                'status': HealthCheckStatus.HEALTHY,
                                'healthy_targets': healthy_targets,
                                'total_targets': total_targets,
                                'attempts': health_check_attempts + 1
                            }
                    else:
                        healthy_checks = 0  # Reset counter
                    
                    health_check_attempts += 1
                    
                    if health_check_attempts < max_attempts:
                        await asyncio.sleep(config.traffic_shift_config.health_check_interval_seconds)
                    
                except Exception as e:
                    logger.warning(f"Health check attempt {health_check_attempts + 1} failed: {e}")
                    health_check_attempts += 1
                    healthy_checks = 0
                    
                    if health_check_attempts < max_attempts:
                        await asyncio.sleep(config.traffic_shift_config.health_check_interval_seconds)
            
            return {
                'status': HealthCheckStatus.UNHEALTHY,
                'attempts': health_check_attempts,
                'reason': 'Max health check attempts exceeded'
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': HealthCheckStatus.UNKNOWN,
                'error': str(e)
            }
    
    async def _shift_traffic(
        self, 
        config: BlueGreenConfig,
        current_environment: DeploymentEnvironment,
        target_environment: DeploymentEnvironment
    ) -> Dict[str, Any]:
        """Shift traffic between environments."""
        try:
            # Get target group ARNs
            current_tg = (
                config.target_group_blue 
                if current_environment == DeploymentEnvironment.BLUE 
                else config.target_group_green
            )
            target_tg = (
                config.target_group_blue 
                if target_environment == DeploymentEnvironment.BLUE 
                else config.target_group_green
            )
            
            strategy = config.traffic_shift_config.strategy
            
            if strategy == TrafficShiftStrategy.ALL_AT_ONCE:
                return await self._shift_traffic_all_at_once(
                    config.listener_arn, current_tg, target_tg
                )
            elif strategy == TrafficShiftStrategy.CANARY:
                return await self._shift_traffic_canary(
                    config, current_tg, target_tg
                )
            elif strategy == TrafficShiftStrategy.LINEAR:
                return await self._shift_traffic_linear(
                    config, current_tg, target_tg
                )
            else:
                raise DeploymentError(
                    f"Unsupported traffic shift strategy: {strategy}",
                    error_code="UNSUPPORTED_TRAFFIC_SHIFT_STRATEGY"
                )
                
        except Exception as e:
            logger.error(f"Traffic shifting failed: {e}")
            raise
    
    async def _shift_traffic_all_at_once(
        self, 
        listener_arn: str,
        current_tg: str,
        target_tg: str
    ) -> Dict[str, Any]:
        """Shift all traffic at once."""
        try:
            # Update listener to point to target environment
            safe_aws_call(
                self.elbv2_client.modify_listener,
                ListenerArn=listener_arn,
                DefaultActions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': target_tg
                    }
                ]
            )
            
            logger.info(f"Shifted 100% traffic to {target_tg}")
            
            return {
                'strategy': 'all_at_once',
                'current_target_group': current_tg,
                'new_target_group': target_tg,
                'traffic_percentage': 100
            }
            
        except Exception as e:
            logger.error(f"All-at-once traffic shift failed: {e}")
            raise
    
    async def _shift_traffic_canary(
        self, 
        config: BlueGreenConfig,
        current_tg: str,
        target_tg: str
    ) -> Dict[str, Any]:
        """Shift traffic using canary strategy."""
        try:
            canary_percentage = config.traffic_shift_config.canary_percentage
            canary_duration = config.traffic_shift_config.canary_duration_minutes
            
            # Phase 1: Canary traffic
            logger.info(f"Starting canary deployment with {canary_percentage}% traffic")
            
            safe_aws_call(
                self.elbv2_client.modify_listener,
                ListenerArn=config.listener_arn,
                DefaultActions=[
                    {
                        'Type': 'forward',
                        'ForwardConfig': {
                            'TargetGroups': [
                                {
                                    'TargetGroupArn': current_tg,
                                    'Weight': 100 - canary_percentage
                                },
                                {
                                    'TargetGroupArn': target_tg,
                                    'Weight': canary_percentage
                                }
                            ]
                        }
                    }
                ]
            )
            
            # Wait for canary duration
            logger.info(f"Monitoring canary deployment for {canary_duration} minutes")
            await asyncio.sleep(canary_duration * 60)
            
            # Check health during canary
            health_check = await self._perform_health_checks(
                config, 
                DeploymentEnvironment.GREEN if target_tg == config.target_group_green else DeploymentEnvironment.BLUE
            )
            
            if health_check['status'] != HealthCheckStatus.HEALTHY:
                raise DeploymentError(
                    "Canary health checks failed",
                    error_code="CANARY_HEALTH_CHECK_FAILED"
                )
            
            # Phase 2: Full traffic shift
            logger.info("Canary successful, shifting 100% traffic")
            
            safe_aws_call(
                self.elbv2_client.modify_listener,
                ListenerArn=config.listener_arn,
                DefaultActions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': target_tg
                    }
                ]
            )
            
            return {
                'strategy': 'canary',
                'canary_percentage': canary_percentage,
                'canary_duration_minutes': canary_duration,
                'current_target_group': current_tg,
                'new_target_group': target_tg,
                'final_traffic_percentage': 100
            }
            
        except Exception as e:
            logger.error(f"Canary traffic shift failed: {e}")
            raise
    
    async def _shift_traffic_linear(
        self, 
        config: BlueGreenConfig,
        current_tg: str,
        target_tg: str
    ) -> Dict[str, Any]:
        """Shift traffic using linear strategy."""
        try:
            percentage_per_minute = config.traffic_shift_config.linear_percentage_per_minute
            current_percentage = 0
            
            logger.info(f"Starting linear deployment with {percentage_per_minute}% per minute")
            
            while current_percentage < 100:
                current_percentage = min(current_percentage + percentage_per_minute, 100)
                
                logger.info(f"Shifting {current_percentage}% traffic to target environment")
                
                if current_percentage == 100:
                    # Final shift - all traffic
                    safe_aws_call(
                        self.elbv2_client.modify_listener,
                        ListenerArn=config.listener_arn,
                        DefaultActions=[
                            {
                                'Type': 'forward',
                                'TargetGroupArn': target_tg
                            }
                        ]
                    )
                else:
                    # Weighted shift
                    safe_aws_call(
                        self.elbv2_client.modify_listener,
                        ListenerArn=config.listener_arn,
                        DefaultActions=[
                            {
                                'Type': 'forward',
                                'ForwardConfig': {
                                    'TargetGroups': [
                                        {
                                            'TargetGroupArn': current_tg,
                                            'Weight': 100 - current_percentage
                                        },
                                        {
                                            'TargetGroupArn': target_tg,
                                            'Weight': current_percentage
                                        }
                                    ]
                                }
                            }
                        ]
                    )
                
                if current_percentage < 100:
                    await asyncio.sleep(60)  # Wait 1 minute
            
            return {
                'strategy': 'linear',
                'percentage_per_minute': percentage_per_minute,
                'current_target_group': current_tg,
                'new_target_group': target_tg,
                'final_traffic_percentage': 100
            }
            
        except Exception as e:
            logger.error(f"Linear traffic shift failed: {e}")
            raise
    
    async def _monitor_deployment(
        self, 
        config: BlueGreenConfig,
        target_environment: DeploymentEnvironment,
        deployment_id: str
    ) -> Dict[str, Any]:
        """Monitor deployment stability."""
        try:
            monitoring_duration = 5  # minutes
            check_interval = 30  # seconds
            
            logger.info(f"Monitoring deployment stability for {monitoring_duration} minutes")
            
            start_time = time.time()
            end_time = start_time + (monitoring_duration * 60)
            
            alarm_triggered = False
            health_check_failed = False
            
            while time.time() < end_time:
                # Check CloudWatch alarms
                if config.cloudwatch_alarms:
                    for alarm_name in config.cloudwatch_alarms:
                        try:
                            alarm_response = safe_aws_call(
                                self.cloudwatch_client.describe_alarms,
                                AlarmNames=[alarm_name]
                            )
                            
                            if alarm_response['MetricAlarms']:
                                alarm = alarm_response['MetricAlarms'][0]
                                if alarm['StateValue'] == 'ALARM':
                                    logger.warning(f"CloudWatch alarm {alarm_name} triggered")
                                    alarm_triggered = True
                                    break
                        except Exception as e:
                            logger.warning(f"Failed to check alarm {alarm_name}: {e}")
                
                # Check target health
                health_check = await self._perform_health_checks(config, target_environment)
                if health_check['status'] != HealthCheckStatus.HEALTHY:
                    logger.warning("Health check failed during monitoring")
                    health_check_failed = True
                    break
                
                if alarm_triggered:
                    break
                
                await asyncio.sleep(check_interval)
            
            stable = not alarm_triggered and not health_check_failed
            
            return {
                'stable': stable,
                'monitoring_duration_minutes': monitoring_duration,
                'alarm_triggered': alarm_triggered,
                'health_check_failed': health_check_failed
            }
            
        except Exception as e:
            logger.error(f"Deployment monitoring failed: {e}")
            return {
                'stable': False,
                'error': str(e)
            }
    
    async def _rollback_deployment(
        self, 
        config: BlueGreenConfig,
        current_environment: DeploymentEnvironment,
        target_environment: DeploymentEnvironment
    ) -> Dict[str, Any]:
        """Rollback deployment to previous environment."""
        try:
            logger.info(f"Rolling back to {current_environment.value} environment")
            
            # Get current target group
            current_tg = (
                config.target_group_blue 
                if current_environment == DeploymentEnvironment.BLUE 
                else config.target_group_green
            )
            
            # Shift all traffic back to current environment
            safe_aws_call(
                self.elbv2_client.modify_listener,
                ListenerArn=config.listener_arn,
                DefaultActions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': current_tg
                    }
                ]
            )
            
            logger.info(f"Rollback completed - all traffic restored to {current_environment.value}")
            
            return {
                'rolled_back': True,
                'rollback_environment': current_environment.value,
                'target_group': current_tg
            }
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise DeploymentError(
                f"Rollback failed: {e}",
                error_code="ROLLBACK_FAILED"
            )
    
    async def _cleanup_old_environment(
        self, 
        config: BlueGreenConfig,
        old_environment: DeploymentEnvironment
    ) -> Dict[str, Any]:
        """Clean up old environment after successful deployment."""
        try:
            logger.info(f"Cleaning up {old_environment.value} environment")
            
            # Get old service configuration
            if old_environment == DeploymentEnvironment.BLUE:
                old_service_config = config.blue_service_config
            else:
                old_service_config = config.green_service_config
            
            # Scale down old service (but don't delete it completely for quick rollback)
            await self.ecs_manager.update_service(
                config.cluster_name,
                old_service_config.service_name,
                desired_count=1  # Keep minimal capacity
            )
            
            return {
                'cleaned_up': True,
                'environment': old_environment.value,
                'action': 'scaled_down_to_minimal'
            }
            
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
            return {
                'cleaned_up': False,
                'error': str(e)
            }
    
    async def _send_deployment_notification(self, deployment_state: Dict[str, Any]):
        """Send deployment notification."""
        try:
            config = deployment_state['config']
            
            if not config.sns_topic_arn:
                return
            
            message = {
                'deployment_id': deployment_state['deployment_id'],
                'service_name': config.service_name,
                'status': deployment_state['status'],
                'duration_seconds': deployment_state.get('duration_seconds'),
                'current_environment': deployment_state['current_environment'].value,
                'target_environment': deployment_state['target_environment'].value
            }
            
            if deployment_state.get('error'):
                message['error'] = deployment_state['error']
            
            safe_aws_call(
                self.sns_client.publish,
                TopicArn=config.sns_topic_arn,
                Message=json.dumps(message, indent=2),
                Subject=f"Blue-Green Deployment {deployment_state['status'].title()}: {config.service_name}"
            )
            
            logger.info(f"Sent deployment notification for {deployment_state['deployment_id']}")
            
        except Exception as e:
            logger.warning(f"Failed to send deployment notification: {e}")
    
    async def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """
        Get deployment status.
        
        Args:
            deployment_id: Deployment ID
            
        Returns:
            Dictionary with deployment status
        """
        try:
            if deployment_id not in self._deployments:
                return {
                    'exists': False,
                    'deployment_id': deployment_id
                }
            
            return {
                'exists': True,
                'deployment': self._deployments[deployment_id]
            }
            
        except Exception as e:
            logger.error(f"Failed to get deployment status: {e}")
            raise DeploymentError(
                f"Deployment status check failed: {e}",
                error_code="DEPLOYMENT_STATUS_CHECK_FAILED"
            )