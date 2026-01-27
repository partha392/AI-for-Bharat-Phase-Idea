"""
ECS deployment management for the Bharat Voice Assistant.

This module provides comprehensive ECS deployment capabilities including:
- Task definition management
- Service deployment and updates
- Cluster management
- Service discovery integration
- Rolling updates and health checks
"""

import boto3
import json
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from ..core.logging import get_logger
from ..core.aws_client import aws_clients, safe_aws_call
from ..core.exceptions import DeploymentError


logger = get_logger(__name__)


class LaunchType(Enum):
    """ECS launch types."""
    EC2 = "EC2"
    FARGATE = "FARGATE"
    EXTERNAL = "EXTERNAL"


class NetworkMode(Enum):
    """ECS network modes."""
    BRIDGE = "bridge"
    HOST = "host"
    AWS_VPC = "awsvpc"
    NONE = "none"


class DeploymentStrategy(Enum):
    """ECS deployment strategies."""
    ROLLING_UPDATE = "rolling_update"
    BLUE_GREEN = "blue_green"
    RECREATE = "recreate"


@dataclass
class ContainerDefinition:
    """ECS container definition."""
    name: str
    image: str
    memory: Optional[int] = None
    memory_reservation: Optional[int] = None
    cpu: Optional[int] = None
    
    # Port mappings
    port_mappings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Environment
    environment: List[Dict[str, str]] = field(default_factory=list)
    secrets: List[Dict[str, str]] = field(default_factory=list)
    
    # Logging
    log_driver: str = "awslogs"
    log_options: Dict[str, str] = field(default_factory=dict)
    
    # Health check
    health_check: Optional[Dict[str, Any]] = None
    
    # Startup dependency
    depends_on: List[Dict[str, Any]] = field(default_factory=list)
    
    # Essential flag
    essential: bool = True
    
    # Entry point and command
    entry_point: List[str] = field(default_factory=list)
    command: List[str] = field(default_factory=list)
    
    # Working directory
    working_directory: Optional[str] = None
    
    # User
    user: Optional[str] = None
    
    # Volumes
    mount_points: List[Dict[str, Any]] = field(default_factory=list)
    volumes_from: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to ECS container definition format."""
        definition = {
            "name": self.name,
            "image": self.image,
            "essential": self.essential
        }
        
        if self.memory:
            definition["memory"] = self.memory
        if self.memory_reservation:
            definition["memoryReservation"] = self.memory_reservation
        if self.cpu:
            definition["cpu"] = self.cpu
        
        if self.port_mappings:
            definition["portMappings"] = self.port_mappings
        
        if self.environment:
            definition["environment"] = self.environment
        if self.secrets:
            definition["secrets"] = self.secrets
        
        if self.log_driver:
            definition["logConfiguration"] = {
                "logDriver": self.log_driver,
                "options": self.log_options
            }
        
        if self.health_check:
            definition["healthCheck"] = self.health_check
        
        if self.depends_on:
            definition["dependsOn"] = self.depends_on
        
        if self.entry_point:
            definition["entryPoint"] = self.entry_point
        if self.command:
            definition["command"] = self.command
        
        if self.working_directory:
            definition["workingDirectory"] = self.working_directory
        if self.user:
            definition["user"] = self.user
        
        if self.mount_points:
            definition["mountPoints"] = self.mount_points
        if self.volumes_from:
            definition["volumesFrom"] = self.volumes_from
        
        return definition


@dataclass
class ECSDeploymentConfig:
    """Configuration for ECS deployment."""
    # Basic settings
    service_name: str
    cluster_name: str
    task_definition_family: str
    
    # Launch configuration
    launch_type: LaunchType = LaunchType.FARGATE
    platform_version: str = "LATEST"
    
    # Capacity
    desired_count: int = 2
    min_capacity: int = 1
    max_capacity: int = 10
    
    # Network configuration
    network_mode: NetworkMode = NetworkMode.AWS_VPC
    subnets: List[str] = field(default_factory=list)
    security_groups: List[str] = field(default_factory=list)
    assign_public_ip: bool = False
    
    # Container definitions
    containers: List[ContainerDefinition] = field(default_factory=list)
    
    # Task role and execution role
    task_role_arn: Optional[str] = None
    execution_role_arn: Optional[str] = None
    
    # CPU and memory (for Fargate)
    cpu: str = "256"  # .25 vCPU
    memory: str = "512"  # 512 MB
    
    # Load balancer configuration
    load_balancer_target_groups: List[Dict[str, Any]] = field(default_factory=list)
    
    # Service discovery
    service_registry_arn: Optional[str] = None
    
    # Deployment configuration
    deployment_strategy: DeploymentStrategy = DeploymentStrategy.ROLLING_UPDATE
    deployment_minimum_healthy_percent: int = 50
    deployment_maximum_percent: int = 200
    
    # Health check grace period
    health_check_grace_period_seconds: int = 300
    
    # Placement constraints and strategies
    placement_constraints: List[Dict[str, Any]] = field(default_factory=list)
    placement_strategy: List[Dict[str, Any]] = field(default_factory=list)
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default values."""
        if not self.tags:
            self.tags = {
                "Service": self.service_name,
                "Environment": "production"
            }


class ECSDeploymentManager:
    """Manages ECS deployments for the voice assistant."""
    
    def __init__(self):
        """Initialize the ECS deployment manager."""
        self.ecs_client = aws_clients.get_custom_client('ecs')
        self.logs_client = aws_clients.get_custom_client('logs')
        self.iam_client = aws_clients.get_custom_client('iam')
        
        self._deployments: Dict[str, Dict[str, Any]] = {}
    
    async def create_cluster(self, cluster_name: str, capacity_providers: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create ECS cluster.
        
        Args:
            cluster_name: Name of the cluster
            capacity_providers: List of capacity providers
            
        Returns:
            Dictionary with cluster information
        """
        try:
            cluster_config = {
                'clusterName': cluster_name,
                'tags': [
                    {'key': 'Service', 'value': 'bharat-voice-assistant'},
                    {'key': 'ManagedBy', 'value': 'ecs-deployment-manager'}
                ]
            }
            
            if capacity_providers:
                cluster_config['capacityProviders'] = capacity_providers
                cluster_config['defaultCapacityProviderStrategy'] = [
                    {
                        'capacityProvider': cp,
                        'weight': 1
                    } for cp in capacity_providers
                ]
            
            cluster_response = safe_aws_call(
                self.ecs_client.create_cluster,
                **cluster_config
            )
            
            logger.info(f"Created ECS cluster {cluster_name}")
            
            return {
                'cluster': cluster_response['cluster'],
                'cluster_arn': cluster_response['cluster']['clusterArn']
            }
            
        except Exception as e:
            logger.error(f"Failed to create ECS cluster {cluster_name}: {e}")
            raise DeploymentError(
                f"ECS cluster creation failed: {e}",
                error_code="ECS_CLUSTER_CREATION_FAILED",
                context={'cluster_name': cluster_name}
            )
    
    async def create_task_definition(self, config: ECSDeploymentConfig) -> Dict[str, Any]:
        """
        Create ECS task definition.
        
        Args:
            config: ECS deployment configuration
            
        Returns:
            Dictionary with task definition information
        """
        try:
            # Prepare container definitions
            container_definitions = []
            for container in config.containers:
                container_def = container.to_dict()
                
                # Set up CloudWatch logging if not specified
                if not container.log_options and container.log_driver == "awslogs":
                    log_group_name = f"/ecs/{config.task_definition_family}"
                    await self._ensure_log_group_exists(log_group_name)
                    
                    container_def["logConfiguration"] = {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": log_group_name,
                            "awslogs-region": aws_clients._boto_config.region_name,
                            "awslogs-stream-prefix": "ecs"
                        }
                    }
                
                container_definitions.append(container_def)
            
            # Prepare task definition
            task_def_config = {
                'family': config.task_definition_family,
                'containerDefinitions': container_definitions,
                'requiresCompatibilities': [config.launch_type.value],
                'networkMode': config.network_mode.value,
                'tags': [{'key': k, 'value': v} for k, v in config.tags.items()]
            }
            
            # Add CPU and memory for Fargate
            if config.launch_type == LaunchType.FARGATE:
                task_def_config['cpu'] = config.cpu
                task_def_config['memory'] = config.memory
            
            # Add task role and execution role
            if config.task_role_arn:
                task_def_config['taskRoleArn'] = config.task_role_arn
            if config.execution_role_arn:
                task_def_config['executionRoleArn'] = config.execution_role_arn
            
            # Create task definition
            task_def_response = safe_aws_call(
                self.ecs_client.register_task_definition,
                **task_def_config
            )
            
            logger.info(f"Created task definition {config.task_definition_family}")
            
            return {
                'task_definition': task_def_response['taskDefinition'],
                'task_definition_arn': task_def_response['taskDefinition']['taskDefinitionArn']
            }
            
        except Exception as e:
            logger.error(f"Failed to create task definition {config.task_definition_family}: {e}")
            raise DeploymentError(
                f"Task definition creation failed: {e}",
                error_code="TASK_DEFINITION_CREATION_FAILED",
                context={'task_definition_family': config.task_definition_family}
            )
    
    async def _ensure_log_group_exists(self, log_group_name: str):
        """Ensure CloudWatch log group exists."""
        try:
            safe_aws_call(
                self.logs_client.describe_log_groups,
                logGroupNamePrefix=log_group_name
            )
        except Exception:
            # Log group doesn't exist, create it
            try:
                safe_aws_call(
                    self.logs_client.create_log_group,
                    logGroupName=log_group_name,
                    tags={
                        'Service': 'bharat-voice-assistant',
                        'ManagedBy': 'ecs-deployment-manager'
                    }
                )
                logger.info(f"Created CloudWatch log group {log_group_name}")
            except Exception as e:
                logger.warning(f"Failed to create log group {log_group_name}: {e}")
    
    async def create_service(self, config: ECSDeploymentConfig, task_definition_arn: str) -> Dict[str, Any]:
        """
        Create ECS service.
        
        Args:
            config: ECS deployment configuration
            task_definition_arn: Task definition ARN
            
        Returns:
            Dictionary with service information
        """
        try:
            # Prepare service configuration
            service_config = {
                'serviceName': config.service_name,
                'cluster': config.cluster_name,
                'taskDefinition': task_definition_arn,
                'desiredCount': config.desired_count,
                'launchType': config.launch_type.value,
                'platformVersion': config.platform_version,
                'deploymentConfiguration': {
                    'minimumHealthyPercent': config.deployment_minimum_healthy_percent,
                    'maximumPercent': config.deployment_maximum_percent
                },
                'tags': [{'key': k, 'value': v} for k, v in config.tags.items()]
            }
            
            # Add network configuration for awsvpc mode
            if config.network_mode == NetworkMode.AWS_VPC:
                service_config['networkConfiguration'] = {
                    'awsvpcConfiguration': {
                        'subnets': config.subnets,
                        'securityGroups': config.security_groups,
                        'assignPublicIp': 'ENABLED' if config.assign_public_ip else 'DISABLED'
                    }
                }
            
            # Add load balancer configuration
            if config.load_balancer_target_groups:
                service_config['loadBalancers'] = config.load_balancer_target_groups
                service_config['healthCheckGracePeriodSeconds'] = config.health_check_grace_period_seconds
            
            # Add service discovery
            if config.service_registry_arn:
                service_config['serviceRegistries'] = [
                    {
                        'registryArn': config.service_registry_arn
                    }
                ]
            
            # Add placement constraints and strategies
            if config.placement_constraints:
                service_config['placementConstraints'] = config.placement_constraints
            if config.placement_strategy:
                service_config['placementStrategy'] = config.placement_strategy
            
            # Create service
            service_response = safe_aws_call(
                self.ecs_client.create_service,
                **service_config
            )
            
            # Store deployment information
            self._deployments[config.service_name] = {
                'config': config,
                'service': service_response['service'],
                'task_definition_arn': task_definition_arn
            }
            
            logger.info(f"Created ECS service {config.service_name}")
            
            return {
                'service': service_response['service'],
                'service_arn': service_response['service']['serviceArn']
            }
            
        except Exception as e:
            logger.error(f"Failed to create ECS service {config.service_name}: {e}")
            raise DeploymentError(
                f"ECS service creation failed: {e}",
                error_code="ECS_SERVICE_CREATION_FAILED",
                context={'service_name': config.service_name}
            )
    
    async def deploy_service(self, config: ECSDeploymentConfig) -> Dict[str, Any]:
        """
        Deploy complete ECS service with task definition.
        
        Args:
            config: ECS deployment configuration
            
        Returns:
            Dictionary with deployment results
        """
        try:
            logger.info(f"Starting deployment of ECS service {config.service_name}")
            
            # Create task definition
            task_def_result = await self.create_task_definition(config)
            task_definition_arn = task_def_result['task_definition_arn']
            
            # Create or update service
            service_result = await self.create_service(config, task_definition_arn)
            
            # Wait for deployment to stabilize
            deployment_status = await self.wait_for_deployment_stable(
                config.cluster_name, 
                config.service_name,
                timeout_minutes=15
            )
            
            logger.info(f"Successfully deployed ECS service {config.service_name}")
            
            return {
                'service_name': config.service_name,
                'cluster_name': config.cluster_name,
                'task_definition': task_def_result,
                'service': service_result,
                'deployment_status': deployment_status
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy ECS service {config.service_name}: {e}")
            raise DeploymentError(
                f"ECS service deployment failed: {e}",
                error_code="ECS_SERVICE_DEPLOYMENT_FAILED",
                context={'service_name': config.service_name}
            )
    
    async def update_service(
        self, 
        cluster_name: str, 
        service_name: str, 
        task_definition_arn: Optional[str] = None,
        desired_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update ECS service.
        
        Args:
            cluster_name: Cluster name
            service_name: Service name
            task_definition_arn: New task definition ARN (optional)
            desired_count: New desired count (optional)
            
        Returns:
            Dictionary with update results
        """
        try:
            update_config = {
                'cluster': cluster_name,
                'service': service_name
            }
            
            if task_definition_arn:
                update_config['taskDefinition'] = task_definition_arn
            if desired_count is not None:
                update_config['desiredCount'] = desired_count
            
            update_response = safe_aws_call(
                self.ecs_client.update_service,
                **update_config
            )
            
            # Wait for deployment to stabilize
            deployment_status = await self.wait_for_deployment_stable(
                cluster_name, 
                service_name,
                timeout_minutes=15
            )
            
            logger.info(f"Updated ECS service {service_name}")
            
            return {
                'service': update_response['service'],
                'deployment_status': deployment_status
            }
            
        except Exception as e:
            logger.error(f"Failed to update ECS service {service_name}: {e}")
            raise DeploymentError(
                f"ECS service update failed: {e}",
                error_code="ECS_SERVICE_UPDATE_FAILED",
                context={'service_name': service_name}
            )
    
    async def wait_for_deployment_stable(
        self, 
        cluster_name: str, 
        service_name: str,
        timeout_minutes: int = 15
    ) -> Dict[str, Any]:
        """
        Wait for ECS service deployment to stabilize.
        
        Args:
            cluster_name: Cluster name
            service_name: Service name
            timeout_minutes: Timeout in minutes
            
        Returns:
            Dictionary with deployment status
        """
        try:
            logger.info(f"Waiting for deployment of {service_name} to stabilize...")
            
            start_time = time.time()
            timeout_seconds = timeout_minutes * 60
            
            while time.time() - start_time < timeout_seconds:
                # Get service status
                services_response = safe_aws_call(
                    self.ecs_client.describe_services,
                    cluster=cluster_name,
                    services=[service_name]
                )
                
                if not services_response['services']:
                    raise DeploymentError(
                        f"Service {service_name} not found",
                        error_code="SERVICE_NOT_FOUND"
                    )
                
                service = services_response['services'][0]
                deployments = service['deployments']
                
                # Check if deployment is stable
                primary_deployment = next(
                    (d for d in deployments if d['status'] == 'PRIMARY'), 
                    None
                )
                
                if primary_deployment:
                    running_count = primary_deployment['runningCount']
                    desired_count = primary_deployment['desiredCount']
                    
                    if running_count == desired_count and primary_deployment['rolloutState'] == 'COMPLETED':
                        logger.info(f"Deployment of {service_name} is stable")
                        return {
                            'stable': True,
                            'running_count': running_count,
                            'desired_count': desired_count,
                            'deployment_id': primary_deployment['id']
                        }
                
                # Wait before checking again
                await asyncio.sleep(30)
            
            # Timeout reached
            logger.warning(f"Deployment of {service_name} did not stabilize within {timeout_minutes} minutes")
            return {
                'stable': False,
                'timeout': True,
                'timeout_minutes': timeout_minutes
            }
            
        except Exception as e:
            logger.error(f"Failed to wait for deployment stability: {e}")
            raise DeploymentError(
                f"Deployment stability check failed: {e}",
                error_code="DEPLOYMENT_STABILITY_CHECK_FAILED"
            )
    
    async def get_service_status(self, cluster_name: str, service_name: str) -> Dict[str, Any]:
        """
        Get ECS service status.
        
        Args:
            cluster_name: Cluster name
            service_name: Service name
            
        Returns:
            Dictionary with service status
        """
        try:
            # Get service details
            services_response = safe_aws_call(
                self.ecs_client.describe_services,
                cluster=cluster_name,
                services=[service_name]
            )
            
            if not services_response['services']:
                return {
                    'exists': False,
                    'service_name': service_name
                }
            
            service = services_response['services'][0]
            
            # Get task details
            tasks_response = safe_aws_call(
                self.ecs_client.list_tasks,
                cluster=cluster_name,
                serviceName=service_name
            )
            
            task_arns = tasks_response['taskArns']
            task_details = []
            
            if task_arns:
                tasks_detail_response = safe_aws_call(
                    self.ecs_client.describe_tasks,
                    cluster=cluster_name,
                    tasks=task_arns
                )
                task_details = tasks_detail_response['tasks']
            
            return {
                'exists': True,
                'service': service,
                'tasks': task_details,
                'running_count': service['runningCount'],
                'desired_count': service['desiredCount'],
                'pending_count': service['pendingCount'],
                'status': service['status'],
                'deployments': service['deployments']
            }
            
        except Exception as e:
            logger.error(f"Failed to get service status for {service_name}: {e}")
            raise DeploymentError(
                f"Service status check failed: {e}",
                error_code="SERVICE_STATUS_CHECK_FAILED",
                context={'service_name': service_name}
            )
    
    async def delete_service(self, cluster_name: str, service_name: str) -> Dict[str, Any]:
        """
        Delete ECS service.
        
        Args:
            cluster_name: Cluster name
            service_name: Service name
            
        Returns:
            Dictionary with deletion results
        """
        try:
            # Scale service to 0
            safe_aws_call(
                self.ecs_client.update_service,
                cluster=cluster_name,
                service=service_name,
                desiredCount=0
            )
            
            # Wait for tasks to stop
            await self.wait_for_deployment_stable(cluster_name, service_name, timeout_minutes=10)
            
            # Delete service
            delete_response = safe_aws_call(
                self.ecs_client.delete_service,
                cluster=cluster_name,
                service=service_name
            )
            
            # Remove from local storage
            if service_name in self._deployments:
                del self._deployments[service_name]
            
            logger.info(f"Deleted ECS service {service_name}")
            
            return {
                'service_name': service_name,
                'deleted': True,
                'service': delete_response['service']
            }
            
        except Exception as e:
            logger.error(f"Failed to delete ECS service {service_name}: {e}")
            raise DeploymentError(
                f"ECS service deletion failed: {e}",
                error_code="ECS_SERVICE_DELETION_FAILED",
                context={'service_name': service_name}
            )