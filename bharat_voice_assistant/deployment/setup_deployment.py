"""
Complete deployment setup orchestrator for the Bharat Voice Assistant.

This module provides end-to-end deployment setup including:
- Docker configuration and containerization
- ECS cluster and service setup
- CI/CD pipeline configuration
- Blue-green deployment setup
"""

import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path

from .docker_config import DockerManager, DockerConfig
from .ecs_deployment import ECSDeploymentManager, ECSDeploymentConfig, ContainerDefinition, LaunchType, NetworkMode
from .pipeline import PipelineManager, PipelineConfig, SourceStageConfig, BuildStageConfig, DeployStageConfig, SourceProvider, BuildProvider, DeployProvider
from .blue_green import BlueGreenDeploymentManager, BlueGreenConfig, TrafficShiftConfig, TrafficShiftStrategy

from ..core.logging import get_logger
from ..core.exceptions import DeploymentError


logger = get_logger(__name__)


class DeploymentOrchestrator:
    """Orchestrates complete deployment setup for the voice assistant."""
    
    def __init__(self):
        """Initialize the deployment orchestrator."""
        self.docker_manager = DockerManager()
        self.ecs_manager = ECSDeploymentManager()
        self.pipeline_manager = PipelineManager()
        self.blue_green_manager = BlueGreenDeploymentManager()
    
    async def setup_complete_deployment(
        self,
        service_name: str = "bharat-voice-assistant",
        cluster_name: str = "bharat-voice-assistant-cluster",
        vpc_id: str = "",
        subnets: List[str] = None,
        security_groups: List[str] = None,
        github_repo: str = "",
        github_owner: str = "",
        github_token_secret_arn: str = "",
        artifact_bucket: str = "",
        ecr_repository_uri: str = "",
        load_balancer_name: str = "",
        target_group_blue: str = "",
        target_group_green: str = "",
        listener_arn: str = "",
        enable_blue_green: bool = True
    ) -> Dict[str, Any]:
        """
        Set up complete deployment infrastructure.
        
        Args:
            service_name: Name of the service
            cluster_name: ECS cluster name
            vpc_id: VPC ID for deployment
            subnets: List of subnet IDs
            security_groups: List of security group IDs
            github_repo: GitHub repository name
            github_owner: GitHub repository owner
            github_token_secret_arn: GitHub token secret ARN
            artifact_bucket: S3 bucket for pipeline artifacts
            ecr_repository_uri: ECR repository URI
            load_balancer_name: Load balancer name
            target_group_blue: Blue target group name
            target_group_green: Green target group name
            listener_arn: Load balancer listener ARN
            enable_blue_green: Enable blue-green deployment
            
        Returns:
            Dictionary with setup results
        """
        try:
            logger.info(f"Starting complete deployment setup for {service_name}")
            
            setup_results = {
                'service_name': service_name,
                'components': {}
            }
            
            # Step 1: Generate Docker configuration
            logger.info("Generating Docker configuration...")
            docker_result = await self._setup_docker_configuration(service_name)
            setup_results['components']['docker'] = docker_result
            
            # Step 2: Create ECS cluster
            logger.info("Setting up ECS cluster...")
            cluster_result = await self._setup_ecs_cluster(cluster_name)
            setup_results['components']['ecs_cluster'] = cluster_result
            
            # Step 3: Configure ECS services
            logger.info("Configuring ECS services...")
            ecs_services_result = await self._setup_ecs_services(
                service_name, cluster_name, vpc_id, subnets, security_groups,
                ecr_repository_uri, target_group_blue, target_group_green
            )
            setup_results['components']['ecs_services'] = ecs_services_result
            
            # Step 4: Set up CI/CD pipeline
            logger.info("Setting up CI/CD pipeline...")
            pipeline_result = await self._setup_cicd_pipeline(
                service_name, github_repo, github_owner, github_token_secret_arn,
                artifact_bucket, ecr_repository_uri, cluster_name
            )
            setup_results['components']['pipeline'] = pipeline_result
            
            # Step 5: Configure blue-green deployment (if enabled)
            if enable_blue_green:
                logger.info("Setting up blue-green deployment...")
                blue_green_result = await self._setup_blue_green_deployment(
                    service_name, cluster_name, load_balancer_name,
                    target_group_blue, target_group_green, listener_arn,
                    ecs_services_result
                )
                setup_results['components']['blue_green'] = blue_green_result
            
            logger.info(f"Complete deployment setup completed for {service_name}")
            
            return setup_results
            
        except Exception as e:
            logger.error(f"Failed to set up complete deployment: {e}")
            raise DeploymentError(
                f"Complete deployment setup failed: {e}",
                error_code="COMPLETE_DEPLOYMENT_SETUP_FAILED",
                context={'service_name': service_name}
            )
    
    async def _setup_docker_configuration(self, service_name: str) -> Dict[str, Any]:
        """Set up Docker configuration."""
        try:
            # Create Docker configuration
            docker_config = DockerConfig(
                service_name=service_name,
                base_image="python:3.11-slim",
                multi_stage_build=True,
                optimize_for_size=True,
                expose_ports=[8000, 8080],
                env_vars={
                    "PYTHONPATH": "/app",
                    "PYTHONUNBUFFERED": "1",
                    "AWS_DEFAULT_REGION": "ap-south-1"
                },
                memory_limit="2g",
                cpu_limit="1",
                labels={
                    "service": service_name,
                    "version": "latest",
                    "maintainer": "bharat-voice-assistant-team"
                }
            )
            
            # Generate Dockerfile
            dockerfile_content = self.docker_manager.generate_dockerfile(
                docker_config, 
                output_path="Dockerfile"
            )
            
            # Generate docker-compose.yml for local development
            compose_content = self.docker_manager.generate_docker_compose(
                docker_config,
                services=["voice-assistant", "redis", "postgres"],
                output_path="docker-compose.yml"
            )
            
            # Generate .dockerignore
            dockerignore_content = self.docker_manager.generate_dockerignore(
                output_path=".dockerignore"
            )
            
            # Validate Dockerfile
            validation_result = self.docker_manager.validate_dockerfile("Dockerfile")
            
            return {
                'config': docker_config,
                'dockerfile_generated': True,
                'compose_generated': True,
                'dockerignore_generated': True,
                'validation': validation_result
            }
            
        except Exception as e:
            logger.error(f"Failed to set up Docker configuration: {e}")
            raise
    
    async def _setup_ecs_cluster(self, cluster_name: str) -> Dict[str, Any]:
        """Set up ECS cluster."""
        try:
            # Create ECS cluster with Fargate capacity provider
            cluster_result = await self.ecs_manager.create_cluster(
                cluster_name=cluster_name,
                capacity_providers=["FARGATE", "FARGATE_SPOT"]
            )
            
            return cluster_result
            
        except Exception as e:
            logger.error(f"Failed to set up ECS cluster: {e}")
            raise
    
    async def _setup_ecs_services(
        self,
        service_name: str,
        cluster_name: str,
        vpc_id: str,
        subnets: List[str],
        security_groups: List[str],
        ecr_repository_uri: str,
        target_group_blue: str,
        target_group_green: str
    ) -> Dict[str, Any]:
        """Set up ECS services for blue-green deployment."""
        try:
            services_result = {}
            
            # Create container definition
            container_def = ContainerDefinition(
                name=service_name,
                image=f"{ecr_repository_uri}:latest",
                memory=2048,
                cpu=1024,
                port_mappings=[
                    {
                        "containerPort": 8000,
                        "protocol": "tcp"
                    },
                    {
                        "containerPort": 8080,
                        "protocol": "tcp"
                    }
                ],
                environment=[
                    {"name": "PYTHONPATH", "value": "/app"},
                    {"name": "PYTHONUNBUFFERED", "value": "1"},
                    {"name": "AWS_DEFAULT_REGION", "value": "ap-south-1"}
                ],
                health_check={
                    "command": [
                        "CMD-SHELL",
                        "curl -f http://localhost:8000/health || exit 1"
                    ],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 60
                },
                log_options={
                    "awslogs-group": f"/ecs/{service_name}",
                    "awslogs-region": "ap-south-1",
                    "awslogs-stream-prefix": "ecs"
                }
            )
            
            # Blue service configuration
            blue_config = ECSDeploymentConfig(
                service_name=f"{service_name}-blue",
                cluster_name=cluster_name,
                task_definition_family=f"{service_name}-blue",
                launch_type=LaunchType.FARGATE,
                network_mode=NetworkMode.AWS_VPC,
                subnets=subnets,
                security_groups=security_groups,
                containers=[container_def],
                cpu="1024",
                memory="2048",
                desired_count=2,
                load_balancer_target_groups=[
                    {
                        "targetGroupArn": f"arn:aws:elasticloadbalancing:ap-south-1:*:targetgroup/{target_group_blue}/*",
                        "containerName": service_name,
                        "containerPort": 8000
                    }
                ]
            )
            
            # Green service configuration
            green_config = ECSDeploymentConfig(
                service_name=f"{service_name}-green",
                cluster_name=cluster_name,
                task_definition_family=f"{service_name}-green",
                launch_type=LaunchType.FARGATE,
                network_mode=NetworkMode.AWS_VPC,
                subnets=subnets,
                security_groups=security_groups,
                containers=[container_def],
                cpu="1024",
                memory="2048",
                desired_count=2,
                load_balancer_target_groups=[
                    {
                        "targetGroupArn": f"arn:aws:elasticloadbalancing:ap-south-1:*:targetgroup/{target_group_green}/*",
                        "containerName": service_name,
                        "containerPort": 8000
                    }
                ]
            )
            
            # Deploy blue service (initial deployment)
            blue_deployment = await self.ecs_manager.deploy_service(blue_config)
            services_result['blue'] = blue_deployment
            
            # Create green service configuration (but don't deploy yet)
            green_task_def = await self.ecs_manager.create_task_definition(green_config)
            services_result['green'] = {
                'task_definition': green_task_def,
                'config': green_config
            }
            
            return services_result
            
        except Exception as e:
            logger.error(f"Failed to set up ECS services: {e}")
            raise
    
    async def _setup_cicd_pipeline(
        self,
        service_name: str,
        github_repo: str,
        github_owner: str,
        github_token_secret_arn: str,
        artifact_bucket: str,
        ecr_repository_uri: str,
        cluster_name: str
    ) -> Dict[str, Any]:
        """Set up CI/CD pipeline."""
        try:
            # Source stage configuration
            source_config = SourceStageConfig(
                provider=SourceProvider.GITHUB,
                repository_name=github_repo,
                branch_name="main",
                github_owner=github_owner,
                github_token_secret_arn=github_token_secret_arn
            )
            
            # Build stage configuration
            build_config = BuildStageConfig(
                provider=BuildProvider.CODEBUILD,
                project_name=f"{service_name}-build",
                environment_variables=[
                    {
                        "name": "AWS_DEFAULT_REGION",
                        "value": "ap-south-1",
                        "type": "PLAINTEXT"
                    },
                    {
                        "name": "AWS_ACCOUNT_ID",
                        "value": "{{resolve:secretsmanager:aws-account-id:SecretString:account_id}}",
                        "type": "PLAINTEXT"
                    },
                    {
                        "name": "IMAGE_REPO_NAME",
                        "value": service_name,
                        "type": "PLAINTEXT"
                    },
                    {
                        "name": "IMAGE_TAG",
                        "value": "latest",
                        "type": "PLAINTEXT"
                    }
                ]
            )
            
            # Deploy stage configuration
            deploy_config = DeployStageConfig(
                provider=DeployProvider.ECS,
                cluster_name=cluster_name,
                service_name=f"{service_name}-blue",  # Deploy to blue initially
                image_definitions_file="imagedefinitions.json"
            )
            
            # Pipeline configuration
            pipeline_config = PipelineConfig(
                pipeline_name=f"{service_name}-pipeline",
                service_role_arn=f"arn:aws:iam::*:role/CodePipelineServiceRole",
                artifact_store_bucket=artifact_bucket,
                source_stage=source_config,
                build_stage=build_config,
                deploy_stages=[deploy_config]
            )
            
            # Create pipeline
            pipeline_result = await self.pipeline_manager.create_pipeline(pipeline_config)
            
            return pipeline_result
            
        except Exception as e:
            logger.error(f"Failed to set up CI/CD pipeline: {e}")
            raise
    
    async def _setup_blue_green_deployment(
        self,
        service_name: str,
        cluster_name: str,
        load_balancer_name: str,
        target_group_blue: str,
        target_group_green: str,
        listener_arn: str,
        ecs_services_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set up blue-green deployment configuration."""
        try:
            # Traffic shift configuration
            traffic_config = TrafficShiftConfig(
                strategy=TrafficShiftStrategy.CANARY,
                canary_percentage=10,
                canary_duration_minutes=5,
                auto_rollback_enabled=True,
                rollback_on_health_check_failure=True
            )
            
            # Blue-green configuration
            blue_green_config = BlueGreenConfig(
                service_name=service_name,
                cluster_name=cluster_name,
                load_balancer_name=load_balancer_name,
                target_group_blue=target_group_blue,
                target_group_green=target_group_green,
                listener_arn=listener_arn,
                blue_service_config=ecs_services_result['blue']['service'],
                green_service_config=ecs_services_result['green']['config'],
                traffic_shift_config=traffic_config
            )
            
            return {
                'config': blue_green_config,
                'traffic_strategy': traffic_config.strategy.value,
                'auto_rollback_enabled': traffic_config.auto_rollback_enabled
            }
            
        except Exception as e:
            logger.error(f"Failed to set up blue-green deployment: {e}")
            raise
    
    async def generate_buildspec(self, service_name: str, output_path: str = "buildspec.yml") -> str:
        """Generate buildspec.yml for CodeBuild."""
        buildspec_content = f"""version: 0.2

env:
  variables:
    AWS_DEFAULT_REGION: ap-south-1
    IMAGE_REPO_NAME: {service_name}
    IMAGE_TAG: latest

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
      - REPOSITORY_URI=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$IMAGE_REPO_NAME
      - COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)
      - IMAGE_TAG=${{COMMIT_HASH:=latest}}
      - echo Installing dependencies...
      - pip install --upgrade pip
      - pip install -r requirements-dev.txt
  
  build:
    commands:
      - echo Build started on `date`
      - echo Running tests...
      - python -m pytest tests/ -v --cov=bharat_voice_assistant --cov-report=xml
      - echo Building the Docker image...
      - docker build -t $IMAGE_REPO_NAME:$IMAGE_TAG .
      - docker tag $IMAGE_REPO_NAME:$IMAGE_TAG $REPOSITORY_URI:$IMAGE_TAG
  
  post_build:
    commands:
      - echo Build completed on `date`
      - echo Pushing the Docker image...
      - docker push $REPOSITORY_URI:$IMAGE_TAG
      - echo Writing image definitions file...
      - printf '[{{"name":"{service_name}","imageUri":"%s"}}]' $REPOSITORY_URI:$IMAGE_TAG > imagedefinitions.json
      - cat imagedefinitions.json

artifacts:
  files:
    - imagedefinitions.json
    - '**/*'

reports:
  coverage-reports:
    files:
      - coverage.xml
    base-directory: .
    file-format: COBERTURAXML

cache:
  paths:
    - '/root/.cache/pip/**/*'
"""
        
        with open(output_path, 'w') as f:
            f.write(buildspec_content)
        
        logger.info(f"Generated buildspec.yml at {output_path}")
        return buildspec_content
    
    async def generate_deployment_scripts(self, service_name: str) -> Dict[str, str]:
        """Generate deployment helper scripts."""
        scripts = {}
        
        # Deploy script
        deploy_script = f"""#!/bin/bash
set -e

SERVICE_NAME="{service_name}"
CLUSTER_NAME="{service_name}-cluster"
REGION="ap-south-1"

echo "Starting blue-green deployment for $SERVICE_NAME..."

# Get current active environment
CURRENT_ENV=$(aws elbv2 describe-listeners --listener-arns $LISTENER_ARN --region $REGION --query 'Listeners[0].DefaultActions[0].TargetGroupArn' --output text | grep -o 'blue\\|green')

if [ "$CURRENT_ENV" = "blue" ]; then
    TARGET_ENV="green"
else
    TARGET_ENV="blue"
fi

echo "Current environment: $CURRENT_ENV"
echo "Target environment: $TARGET_ENV"

# Update target environment service
echo "Updating $TARGET_ENV environment..."
aws ecs update-service \\
    --cluster $CLUSTER_NAME \\
    --service $SERVICE_NAME-$TARGET_ENV \\
    --task-definition $SERVICE_NAME-$TARGET_ENV:$TASK_DEFINITION_REVISION \\
    --region $REGION

# Wait for deployment to stabilize
echo "Waiting for deployment to stabilize..."
aws ecs wait services-stable \\
    --cluster $CLUSTER_NAME \\
    --services $SERVICE_NAME-$TARGET_ENV \\
    --region $REGION

echo "Deployment completed successfully!"
"""
        
        scripts['deploy.sh'] = deploy_script
        
        # Rollback script
        rollback_script = f"""#!/bin/bash
set -e

SERVICE_NAME="{service_name}"
CLUSTER_NAME="{service_name}-cluster"
REGION="ap-south-1"

echo "Starting rollback for $SERVICE_NAME..."

# Get current active environment
CURRENT_ENV=$(aws elbv2 describe-listeners --listener-arns $LISTENER_ARN --region $REGION --query 'Listeners[0].DefaultActions[0].TargetGroupArn' --output text | grep -o 'blue\\|green')

if [ "$CURRENT_ENV" = "blue" ]; then
    ROLLBACK_ENV="green"
else
    ROLLBACK_ENV="blue"
fi

echo "Rolling back from $CURRENT_ENV to $ROLLBACK_ENV..."

# Switch traffic back
aws elbv2 modify-listener \\
    --listener-arn $LISTENER_ARN \\
    --default-actions Type=forward,TargetGroupArn=$ROLLBACK_TARGET_GROUP_ARN \\
    --region $REGION

echo "Rollback completed successfully!"
"""
        
        scripts['rollback.sh'] = rollback_script
        
        # Health check script
        health_check_script = f"""#!/bin/bash

SERVICE_NAME="{service_name}"
CLUSTER_NAME="{service_name}-cluster"
REGION="ap-south-1"

echo "Checking health of $SERVICE_NAME services..."

for ENV in blue green; do
    echo "Checking $ENV environment..."
    
    SERVICE_STATUS=$(aws ecs describe-services \\
        --cluster $CLUSTER_NAME \\
        --services $SERVICE_NAME-$ENV \\
        --region $REGION \\
        --query 'services[0].status' \\
        --output text)
    
    RUNNING_COUNT=$(aws ecs describe-services \\
        --cluster $CLUSTER_NAME \\
        --services $SERVICE_NAME-$ENV \\
        --region $REGION \\
        --query 'services[0].runningCount' \\
        --output text)
    
    DESIRED_COUNT=$(aws ecs describe-services \\
        --cluster $CLUSTER_NAME \\
        --services $SERVICE_NAME-$ENV \\
        --region $REGION \\
        --query 'services[0].desiredCount' \\
        --output text)
    
    echo "$ENV environment: Status=$SERVICE_STATUS, Running=$RUNNING_COUNT, Desired=$DESIRED_COUNT"
done
"""
        
        scripts['health-check.sh'] = health_check_script
        
        # Write scripts to files
        for script_name, script_content in scripts.items():
            with open(f"scripts/{script_name}", 'w') as f:
                f.write(script_content)
            
            # Make scripts executable
            import os
            os.chmod(f"scripts/{script_name}", 0o755)
        
        logger.info("Generated deployment scripts")
        return scripts


# Convenience function for quick setup
async def setup_bharat_voice_assistant_deployment(
    vpc_id: str,
    subnets: List[str],
    security_groups: List[str],
    github_repo: str,
    github_owner: str,
    github_token_secret_arn: str,
    artifact_bucket: str,
    ecr_repository_uri: str,
    load_balancer_name: str,
    target_group_blue: str,
    target_group_green: str,
    listener_arn: str
) -> Dict[str, Any]:
    """
    Quick setup function for Bharat Voice Assistant deployment.
    
    Args:
        vpc_id: VPC ID for deployment
        subnets: List of subnet IDs
        security_groups: List of security group IDs
        github_repo: GitHub repository name
        github_owner: GitHub repository owner
        github_token_secret_arn: GitHub token secret ARN
        artifact_bucket: S3 bucket for pipeline artifacts
        ecr_repository_uri: ECR repository URI
        load_balancer_name: Load balancer name
        target_group_blue: Blue target group name
        target_group_green: Green target group name
        listener_arn: Load balancer listener ARN
        
    Returns:
        Dictionary with setup results
    """
    orchestrator = DeploymentOrchestrator()
    
    return await orchestrator.setup_complete_deployment(
        vpc_id=vpc_id,
        subnets=subnets,
        security_groups=security_groups,
        github_repo=github_repo,
        github_owner=github_owner,
        github_token_secret_arn=github_token_secret_arn,
        artifact_bucket=artifact_bucket,
        ecr_repository_uri=ecr_repository_uri,
        load_balancer_name=load_balancer_name,
        target_group_blue=target_group_blue,
        target_group_green=target_group_green,
        listener_arn=listener_arn,
        enable_blue_green=True
    )