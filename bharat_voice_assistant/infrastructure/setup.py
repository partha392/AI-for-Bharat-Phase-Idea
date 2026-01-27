"""
Infrastructure setup and orchestration for the Bharat Voice Assistant.

This module provides comprehensive infrastructure setup including:
- Auto-scaling groups and policies
- Load balancers and target groups
- Monitoring and alerting
- Multi-region deployment
- Health checks and failover
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

from .auto_scaling import AutoScalingManager, AutoScalingConfig, ScalingPolicy, ScalingMetric, ScalingDirection
from .load_balancer import LoadBalancerManager, LoadBalancerConfig, TargetGroupConfig, LoadBalancerType, ProtocolType
from .monitoring import MonitoringManager, MetricConfig, AlertConfig, DashboardConfig
from .multi_region import MultiRegionManager, RegionConfig, FailoverConfig, RegionStatus

from ..core.logging import get_logger
from ..core.exceptions import InfrastructureError


logger = get_logger(__name__)


@dataclass
class InfrastructureConfig:
    """Complete infrastructure configuration."""
    # Basic settings
    service_name: str = "bharat-voice-assistant"
    environment: str = "production"
    
    # Regions
    primary_region: str = "ap-south-1"  # Mumbai
    secondary_regions: List[str] = None
    
    # Network settings
    vpc_id: str = ""
    subnets: List[str] = None
    security_groups: List[str] = None
    
    # Scaling settings
    min_capacity: int = 2
    max_capacity: int = 100
    desired_capacity: int = 5
    
    # Load balancer settings
    certificate_arn: Optional[str] = None
    domain_name: Optional[str] = None
    hosted_zone_id: Optional[str] = None
    
    # Monitoring settings
    enable_monitoring: bool = True
    enable_alerting: bool = True
    enable_dashboard: bool = True
    
    # Multi-region settings
    enable_multi_region: bool = False
    enable_failover: bool = False
    
    def __post_init__(self):
        """Set default values."""
        if self.secondary_regions is None:
            self.secondary_regions = ["ap-south-2"]  # Hyderabad
        
        if self.subnets is None:
            self.subnets = []
        
        if self.security_groups is None:
            self.security_groups = []


class InfrastructureOrchestrator:
    """Orchestrates the complete infrastructure setup for the voice assistant."""
    
    def __init__(self):
        """Initialize the infrastructure orchestrator."""
        self.auto_scaling_manager = AutoScalingManager()
        self.load_balancer_manager = LoadBalancerManager()
        self.monitoring_manager = MonitoringManager()
        self.multi_region_manager = MultiRegionManager()
        
        self._infrastructure_state: Dict[str, Any] = {}
    
    async def setup_complete_infrastructure(self, config: InfrastructureConfig) -> Dict[str, Any]:
        """
        Set up complete infrastructure for the voice assistant.
        
        Args:
            config: Infrastructure configuration
            
        Returns:
            Dictionary with setup results
        """
        try:
            logger.info(f"Starting complete infrastructure setup for {config.service_name}")
            
            setup_results = {
                'service_name': config.service_name,
                'environment': config.environment,
                'primary_region': config.primary_region,
                'components': {}
            }
            
            # Step 1: Set up load balancers
            logger.info("Setting up load balancers...")
            load_balancer_result = await self._setup_load_balancers(config)
            setup_results['components']['load_balancers'] = load_balancer_result
            
            # Step 2: Set up auto-scaling
            logger.info("Setting up auto-scaling...")
            auto_scaling_result = await self._setup_auto_scaling(config, load_balancer_result)
            setup_results['components']['auto_scaling'] = auto_scaling_result
            
            # Step 3: Set up monitoring
            if config.enable_monitoring:
                logger.info("Setting up monitoring...")
                monitoring_result = await self._setup_monitoring(config)
                setup_results['components']['monitoring'] = monitoring_result
            
            # Step 4: Set up multi-region deployment
            if config.enable_multi_region:
                logger.info("Setting up multi-region deployment...")
                multi_region_result = await self._setup_multi_region(config, load_balancer_result)
                setup_results['components']['multi_region'] = multi_region_result
            
            # Step 5: Validate setup
            logger.info("Validating infrastructure setup...")
            validation_result = await self._validate_infrastructure_setup(config, setup_results)
            setup_results['validation'] = validation_result
            
            # Store infrastructure state
            self._infrastructure_state = setup_results
            
            logger.info(f"Complete infrastructure setup completed for {config.service_name}")
            
            return setup_results
            
        except Exception as e:
            logger.error(f"Failed to set up complete infrastructure: {e}")
            raise InfrastructureError(
                f"Infrastructure setup failed: {e}",
                error_code="INFRASTRUCTURE_SETUP_FAILED",
                context={'service_name': config.service_name}
            )
    
    async def _setup_load_balancers(self, config: InfrastructureConfig) -> Dict[str, Any]:
        """Set up load balancers for the voice assistant."""
        try:
            # Create target groups for different services
            target_groups = [
                TargetGroupConfig(
                    name=f"{config.service_name}-voice-gateway-tg",
                    protocol=ProtocolType.HTTP,
                    port=8000,
                    vpc_id=config.vpc_id,
                    health_check_path="/health",
                    health_check_interval_seconds=30,
                    healthy_threshold_count=2,
                    unhealthy_threshold_count=3
                ),
                TargetGroupConfig(
                    name=f"{config.service_name}-api-gateway-tg",
                    protocol=ProtocolType.HTTP,
                    port=8080,
                    vpc_id=config.vpc_id,
                    health_check_path="/api/health",
                    health_check_interval_seconds=30,
                    healthy_threshold_count=2,
                    unhealthy_threshold_count=3
                )
            ]
            
            # Create load balancer configuration
            lb_config = LoadBalancerConfig(
                name=f"{config.service_name}-alb",
                load_balancer_type=LoadBalancerType.APPLICATION,
                scheme="internet-facing",
                subnets=config.subnets,
                security_groups=config.security_groups,
                target_groups=target_groups,
                certificate_arn=config.certificate_arn,
                access_logs_enabled=True,
                deletion_protection_enabled=True,
                tags={
                    'Name': f"{config.service_name}-alb",
                    'Service': config.service_name,
                    'Environment': config.environment
                }
            )
            
            # Create load balancer
            lb_result = await self.load_balancer_manager.create_load_balancer(lb_config)
            
            return {
                'load_balancer': lb_result['load_balancer'],
                'target_groups': lb_result['target_groups'],
                'listeners': lb_result['listeners'],
                'dns_name': lb_result['load_balancer']['DNSName']
            }
            
        except Exception as e:
            logger.error(f"Failed to set up load balancers: {e}")
            raise
    
    async def _setup_auto_scaling(
        self, 
        config: InfrastructureConfig, 
        load_balancer_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set up auto-scaling for the voice assistant services."""
        try:
            auto_scaling_results = {}
            
            # Get target group ARNs
            target_group_arns = {
                tg['TargetGroupName']: tg['TargetGroupArn'] 
                for tg in load_balancer_result['target_groups']
            }
            
            # Create auto-scaling configurations for different services
            services = [
                {
                    'name': 'voice-gateway',
                    'cluster_name': f"{config.service_name}-cluster",
                    'target_group_arn': target_group_arns.get(f"{config.service_name}-voice-gateway-tg")
                },
                {
                    'name': 'api-gateway',
                    'cluster_name': f"{config.service_name}-cluster",
                    'target_group_arn': target_group_arns.get(f"{config.service_name}-api-gateway-tg")
                }
            ]
            
            for service in services:
                # Create scaling policies
                scaling_policies = [
                    ScalingPolicy(
                        name=f"{service['name']}-scale-up-cpu",
                        metric=ScalingMetric.CPU_UTILIZATION,
                        threshold=70.0,
                        direction=ScalingDirection.SCALE_UP,
                        scaling_adjustment=2,
                        cooldown_seconds=300
                    ),
                    ScalingPolicy(
                        name=f"{service['name']}-scale-down-cpu",
                        metric=ScalingMetric.CPU_UTILIZATION,
                        threshold=30.0,
                        direction=ScalingDirection.SCALE_DOWN,
                        scaling_adjustment=-1,
                        cooldown_seconds=300
                    ),
                    ScalingPolicy(
                        name=f"{service['name']}-scale-up-requests",
                        metric=ScalingMetric.REQUEST_COUNT,
                        threshold=1000.0,
                        direction=ScalingDirection.SCALE_UP,
                        scaling_adjustment=3,
                        cooldown_seconds=180
                    )
                ]
                
                # Create auto-scaling configuration
                asg_config = AutoScalingConfig(
                    service_name=service['name'],
                    min_capacity=config.min_capacity,
                    max_capacity=config.max_capacity,
                    desired_capacity=config.desired_capacity,
                    target_group_arn=service['target_group_arn'],
                    cluster_name=service['cluster_name'],
                    service_arn=f"arn:aws:ecs:{config.primary_region}:*:service/{service['cluster_name']}/{service['name']}",
                    scaling_policies=scaling_policies
                )
                
                # Create ECS auto-scaling
                asg_result = await self.auto_scaling_manager.create_ecs_auto_scaling(asg_config)
                auto_scaling_results[service['name']] = asg_result
            
            return auto_scaling_results
            
        except Exception as e:
            logger.error(f"Failed to set up auto-scaling: {e}")
            raise
    
    async def _setup_monitoring(self, config: InfrastructureConfig) -> Dict[str, Any]:
        """Set up monitoring and alerting for the voice assistant."""
        try:
            # Set up core monitoring
            monitoring_result = await self.monitoring_manager.setup_core_monitoring()
            
            # Create additional custom metrics for voice assistant
            voice_metrics = [
                MetricConfig(
                    name='VoiceProcessingLatency',
                    namespace='BharatVoiceAssistant',
                    unit='Milliseconds',
                    description='End-to-end voice processing latency',
                    dimensions={'Service': 'voice-processing'}
                ),
                MetricConfig(
                    name='LanguageDetectionAccuracy',
                    namespace='BharatVoiceAssistant',
                    unit='Percent',
                    description='Language detection accuracy rate',
                    dimensions={'Service': 'language-processing'}
                ),
                MetricConfig(
                    name='SchemeMatchingSuccess',
                    namespace='BharatVoiceAssistant',
                    unit='Percent',
                    description='Scheme matching success rate',
                    dimensions={'Service': 'scheme-discovery'}
                ),
                MetricConfig(
                    name='GrievanceFilingSuccess',
                    namespace='BharatVoiceAssistant',
                    unit='Percent',
                    description='Grievance filing success rate',
                    dimensions={'Service': 'grievance-filing'}
                )
            ]
            
            # Create custom metrics
            custom_metrics = {}
            for metric_config in voice_metrics:
                metric_result = await self.monitoring_manager.create_custom_metric(metric_config)
                custom_metrics[metric_config.name] = metric_result
            
            monitoring_result['custom_metrics'] = custom_metrics
            
            return monitoring_result
            
        except Exception as e:
            logger.error(f"Failed to set up monitoring: {e}")
            raise
    
    async def _setup_multi_region(
        self, 
        config: InfrastructureConfig, 
        load_balancer_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set up multi-region deployment with failover."""
        try:
            if not config.enable_multi_region:
                return {'enabled': False}
            
            # Create region configurations
            regions = []
            
            # Primary region
            primary_region = RegionConfig(
                region_name=config.primary_region,
                status=RegionStatus.ACTIVE,
                priority=1,
                vpc_id=config.vpc_id,
                subnets=config.subnets,
                security_groups=config.security_groups,
                load_balancer_arn=load_balancer_result['load_balancer']['LoadBalancerArn'],
                load_balancer_dns=load_balancer_result['load_balancer']['DNSName'],
                cluster_name=f"{config.service_name}-cluster",
                service_names=['voice-gateway', 'api-gateway'],
                health_check_endpoint=load_balancer_result['dns_name'],
                health_check_path="/health",
                tags={
                    'Region': config.primary_region,
                    'Service': config.service_name,
                    'Environment': config.environment
                }
            )
            regions.append(primary_region)
            
            # Secondary regions
            for i, region_name in enumerate(config.secondary_regions):
                secondary_region = RegionConfig(
                    region_name=region_name,
                    status=RegionStatus.STANDBY,
                    priority=i + 2,
                    # Note: In a real implementation, these would be configured for each region
                    vpc_id="",  # Would be set per region
                    subnets=[],  # Would be set per region
                    security_groups=[],  # Would be set per region
                    health_check_endpoint=f"{region_name}.{config.domain_name}" if config.domain_name else "",
                    health_check_path="/health",
                    tags={
                        'Region': region_name,
                        'Service': config.service_name,
                        'Environment': config.environment
                    }
                )
                regions.append(secondary_region)
            
            # Create failover configuration
            failover_config = FailoverConfig(
                enabled=config.enable_failover,
                dns_failover_enabled=True,
                auto_recovery_enabled=True,
                notification_enabled=True
            )
            
            # Configure multi-region deployment
            if config.hosted_zone_id and config.domain_name:
                multi_region_result = await self.multi_region_manager.configure_multi_region_deployment(
                    regions=regions,
                    failover_config=failover_config,
                    hosted_zone_id=config.hosted_zone_id,
                    domain_name=config.domain_name
                )
            else:
                logger.warning("Hosted zone ID and domain name required for DNS failover")
                multi_region_result = {
                    'regions': {r.region_name: r for r in regions},
                    'failover_config': failover_config,
                    'dns_failover': 'not_configured'
                }
            
            return multi_region_result
            
        except Exception as e:
            logger.error(f"Failed to set up multi-region deployment: {e}")
            raise
    
    async def _validate_infrastructure_setup(
        self, 
        config: InfrastructureConfig, 
        setup_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate the infrastructure setup."""
        try:
            validation_results = {
                'overall_status': 'healthy',
                'component_status': {},
                'issues': []
            }
            
            # Validate load balancers
            if 'load_balancers' in setup_results['components']:
                lb_status = await self._validate_load_balancers(setup_results['components']['load_balancers'])
                validation_results['component_status']['load_balancers'] = lb_status
                if not lb_status['healthy']:
                    validation_results['issues'].extend(lb_status['issues'])
            
            # Validate auto-scaling
            if 'auto_scaling' in setup_results['components']:
                asg_status = await self._validate_auto_scaling(setup_results['components']['auto_scaling'])
                validation_results['component_status']['auto_scaling'] = asg_status
                if not asg_status['healthy']:
                    validation_results['issues'].extend(asg_status['issues'])
            
            # Validate monitoring
            if 'monitoring' in setup_results['components']:
                monitoring_status = await self._validate_monitoring(setup_results['components']['monitoring'])
                validation_results['component_status']['monitoring'] = monitoring_status
                if not monitoring_status['healthy']:
                    validation_results['issues'].extend(monitoring_status['issues'])
            
            # Set overall status
            if validation_results['issues']:
                validation_results['overall_status'] = 'degraded' if len(validation_results['issues']) < 3 else 'unhealthy'
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Failed to validate infrastructure setup: {e}")
            return {
                'overall_status': 'unknown',
                'error': str(e)
            }
    
    async def _validate_load_balancers(self, lb_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate load balancer setup."""
        try:
            issues = []
            
            # Check if load balancer is provisioning or active
            lb_state = lb_results['load_balancer'].get('State', {}).get('Code')
            if lb_state != 'active':
                issues.append(f"Load balancer state is {lb_state}, expected 'active'")
            
            # Check target groups
            if not lb_results.get('target_groups'):
                issues.append("No target groups configured")
            
            # Check listeners
            if not lb_results.get('listeners'):
                issues.append("No listeners configured")
            
            return {
                'healthy': len(issues) == 0,
                'issues': issues,
                'load_balancer_state': lb_state,
                'target_groups_count': len(lb_results.get('target_groups', [])),
                'listeners_count': len(lb_results.get('listeners', []))
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'issues': [f"Validation error: {e}"]
            }
    
    async def _validate_auto_scaling(self, asg_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate auto-scaling setup."""
        try:
            issues = []
            
            # Check if auto-scaling groups are configured
            if not asg_results:
                issues.append("No auto-scaling groups configured")
            
            # Check each service
            for service_name, service_result in asg_results.items():
                if 'scalable_target' not in service_result:
                    issues.append(f"No scalable target for service {service_name}")
                
                if not service_result.get('policies'):
                    issues.append(f"No scaling policies for service {service_name}")
            
            return {
                'healthy': len(issues) == 0,
                'issues': issues,
                'services_count': len(asg_results),
                'total_policies': sum(len(result.get('policies', [])) for result in asg_results.values())
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'issues': [f"Validation error: {e}"]
            }
    
    async def _validate_monitoring(self, monitoring_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate monitoring setup."""
        try:
            issues = []
            
            # Check SNS topics
            if not monitoring_results.get('sns_topics'):
                issues.append("No SNS topics configured for alerts")
            
            # Check metrics
            if not monitoring_results.get('metrics'):
                issues.append("No custom metrics configured")
            
            # Check alerts
            if not monitoring_results.get('alerts'):
                issues.append("No alerts configured")
            
            # Check dashboard
            if not monitoring_results.get('dashboard'):
                issues.append("No dashboard configured")
            
            return {
                'healthy': len(issues) == 0,
                'issues': issues,
                'sns_topics_count': len(monitoring_results.get('sns_topics', {})),
                'metrics_count': len(monitoring_results.get('metrics', {})),
                'alerts_count': len(monitoring_results.get('alerts', {}))
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'issues': [f"Validation error: {e}"]
            }
    
    async def get_infrastructure_status(self) -> Dict[str, Any]:
        """
        Get current infrastructure status.
        
        Returns:
            Dictionary with infrastructure status information
        """
        try:
            if not self._infrastructure_state:
                return {'status': 'not_configured'}
            
            # Get current status from each component
            status = {
                'overall_status': 'unknown',
                'components': {},
                'last_updated': self._infrastructure_state.get('timestamp')
            }
            
            # Check load balancer status
            if 'load_balancers' in self._infrastructure_state.get('components', {}):
                lb_name = self._infrastructure_state['components']['load_balancers']['load_balancer']['LoadBalancerName']
                lb_status = await self.load_balancer_manager.get_load_balancer_status(lb_name)
                status['components']['load_balancers'] = lb_status
            
            # Check auto-scaling status
            if 'auto_scaling' in self._infrastructure_state.get('components', {}):
                asg_status = {}
                for service_name in self._infrastructure_state['components']['auto_scaling'].keys():
                    service_status = await self.auto_scaling_manager.get_scaling_status(service_name)
                    asg_status[service_name] = service_status
                status['components']['auto_scaling'] = asg_status
            
            # Check monitoring status
            if 'monitoring' in self._infrastructure_state.get('components', {}):
                monitoring_status = await self.monitoring_manager.get_monitoring_status()
                status['components']['monitoring'] = monitoring_status
            
            # Check multi-region status
            if 'multi_region' in self._infrastructure_state.get('components', {}):
                multi_region_status = await self.multi_region_manager.get_multi_region_status()
                status['components']['multi_region'] = multi_region_status
            
            # Determine overall status
            component_statuses = []
            for component_status in status['components'].values():
                if isinstance(component_status, dict) and 'healthy' in component_status:
                    component_statuses.append(component_status['healthy'])
            
            if all(component_statuses):
                status['overall_status'] = 'healthy'
            elif any(component_statuses):
                status['overall_status'] = 'degraded'
            else:
                status['overall_status'] = 'unhealthy'
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get infrastructure status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def teardown_infrastructure(self, config: InfrastructureConfig) -> Dict[str, Any]:
        """
        Tear down the complete infrastructure.
        
        Args:
            config: Infrastructure configuration
            
        Returns:
            Dictionary with teardown results
        """
        try:
            logger.info(f"Starting infrastructure teardown for {config.service_name}")
            
            teardown_results = {
                'service_name': config.service_name,
                'components_removed': []
            }
            
            # Remove auto-scaling configurations
            if 'auto_scaling' in self._infrastructure_state.get('components', {}):
                for service_name in self._infrastructure_state['components']['auto_scaling'].keys():
                    try:
                        await self.auto_scaling_manager.delete_scaling_configuration(service_name)
                        teardown_results['components_removed'].append(f"auto_scaling_{service_name}")
                    except Exception as e:
                        logger.warning(f"Failed to remove auto-scaling for {service_name}: {e}")
            
            # Remove load balancers
            if 'load_balancers' in self._infrastructure_state.get('components', {}):
                try:
                    lb_name = self._infrastructure_state['components']['load_balancers']['load_balancer']['LoadBalancerName']
                    await self.load_balancer_manager.delete_load_balancer(lb_name)
                    teardown_results['components_removed'].append("load_balancers")
                except Exception as e:
                    logger.warning(f"Failed to remove load balancers: {e}")
            
            # Clear infrastructure state
            self._infrastructure_state = {}
            
            logger.info(f"Infrastructure teardown completed for {config.service_name}")
            
            return teardown_results
            
        except Exception as e:
            logger.error(f"Failed to tear down infrastructure: {e}")
            raise InfrastructureError(
                f"Infrastructure teardown failed: {e}",
                error_code="INFRASTRUCTURE_TEARDOWN_FAILED",
                context={'service_name': config.service_name}
            )


# Convenience function for quick setup
async def setup_bharat_voice_assistant_infrastructure(
    vpc_id: str,
    subnets: List[str],
    security_groups: List[str],
    certificate_arn: Optional[str] = None,
    domain_name: Optional[str] = None,
    hosted_zone_id: Optional[str] = None,
    enable_multi_region: bool = False
) -> Dict[str, Any]:
    """
    Quick setup function for Bharat Voice Assistant infrastructure.
    
    Args:
        vpc_id: VPC ID for deployment
        subnets: List of subnet IDs
        security_groups: List of security group IDs
        certificate_arn: SSL certificate ARN (optional)
        domain_name: Domain name for the service (optional)
        hosted_zone_id: Route 53 hosted zone ID (optional)
        enable_multi_region: Enable multi-region deployment
        
    Returns:
        Dictionary with setup results
    """
    config = InfrastructureConfig(
        vpc_id=vpc_id,
        subnets=subnets,
        security_groups=security_groups,
        certificate_arn=certificate_arn,
        domain_name=domain_name,
        hosted_zone_id=hosted_zone_id,
        enable_multi_region=enable_multi_region,
        enable_failover=enable_multi_region
    )
    
    orchestrator = InfrastructureOrchestrator()
    return await orchestrator.setup_complete_infrastructure(config)