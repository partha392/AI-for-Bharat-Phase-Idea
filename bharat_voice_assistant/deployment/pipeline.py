"""
CI/CD pipeline management for the Bharat Voice Assistant.

This module provides comprehensive pipeline capabilities including:
- CodePipeline configuration
- CodeBuild projects
- CodeDeploy applications
- GitHub integration
- Automated testing and deployment
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


class SourceProvider(Enum):
    """Source code providers."""
    GITHUB = "GitHub"
    CODECOMMIT = "CodeCommit"
    S3 = "S3"


class BuildProvider(Enum):
    """Build providers."""
    CODEBUILD = "CodeBuild"
    JENKINS = "Jenkins"


class DeployProvider(Enum):
    """Deploy providers."""
    CODEDEPLOY = "CodeDeploy"
    ECS = "ECS"
    S3 = "S3"
    CLOUDFORMATION = "CloudFormation"


@dataclass
class SourceStageConfig:
    """Configuration for source stage."""
    provider: SourceProvider
    repository_name: str
    branch_name: str = "main"
    
    # GitHub specific
    github_owner: Optional[str] = None
    github_token_secret_arn: Optional[str] = None
    
    # S3 specific
    s3_bucket: Optional[str] = None
    s3_key: Optional[str] = None
    
    # Output artifacts
    output_artifacts: List[str] = field(default_factory=lambda: ["SourceOutput"])


@dataclass
class BuildStageConfig:
    """Configuration for build stage."""
    provider: BuildProvider = BuildProvider.CODEBUILD
    project_name: str = ""
    
    # Input/Output artifacts
    input_artifacts: List[str] = field(default_factory=lambda: ["SourceOutput"])
    output_artifacts: List[str] = field(default_factory=lambda: ["BuildOutput"])
    
    # Build environment
    compute_type: str = "BUILD_GENERAL1_MEDIUM"
    image: str = "aws/codebuild/amazonlinux2-x86_64-standard:3.0"
    environment_type: str = "LINUX_CONTAINER"
    privileged_mode: bool = True
    
    # Environment variables
    environment_variables: List[Dict[str, str]] = field(default_factory=list)
    
    # Build spec
    buildspec_path: str = "buildspec.yml"
    inline_buildspec: Optional[str] = None
    
    # Service role
    service_role_arn: Optional[str] = None
    
    # VPC configuration
    vpc_config: Optional[Dict[str, Any]] = None
    
    # Cache configuration
    cache_type: str = "NO_CACHE"
    cache_location: Optional[str] = None


@dataclass
class DeployStageConfig:
    """Configuration for deploy stage."""
    provider: DeployProvider
    
    # Input artifacts
    input_artifacts: List[str] = field(default_factory=lambda: ["BuildOutput"])
    
    # ECS specific
    cluster_name: Optional[str] = None
    service_name: Optional[str] = None
    image_definitions_file: str = "imagedefinitions.json"
    
    # CodeDeploy specific
    application_name: Optional[str] = None
    deployment_group_name: Optional[str] = None
    
    # CloudFormation specific
    stack_name: Optional[str] = None
    template_path: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    parameter_overrides: Dict[str, str] = field(default_factory=dict)
    
    # S3 specific
    s3_bucket: Optional[str] = None
    s3_key: Optional[str] = None
    extract: bool = True
    
    # Role ARN
    role_arn: Optional[str] = None


@dataclass
class PipelineConfig:
    """Configuration for CI/CD pipeline."""
    pipeline_name: str
    service_role_arn: str
    artifact_store_bucket: str
    
    # Stages
    source_stage: SourceStageConfig
    build_stage: Optional[BuildStageConfig] = None
    deploy_stages: List[DeployStageConfig] = field(default_factory=list)
    
    # Additional stages
    test_stages: List[Dict[str, Any]] = field(default_factory=list)
    approval_stages: List[Dict[str, Any]] = field(default_factory=list)
    
    # Encryption
    encryption_key_id: Optional[str] = None
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default values."""
        if not self.tags:
            self.tags = {
                "Service": "bharat-voice-assistant",
                "ManagedBy": "pipeline-manager"
            }


class PipelineManager:
    """Manages CI/CD pipelines for the voice assistant."""
    
    def __init__(self):
        """Initialize the pipeline manager."""
        self.codepipeline_client = aws_clients.get_custom_client('codepipeline')
        self.codebuild_client = aws_clients.get_custom_client('codebuild')
        self.codedeploy_client = aws_clients.get_custom_client('codedeploy')
        self.iam_client = aws_clients.get_custom_client('iam')
        self.s3_client = aws_clients.get_custom_client('s3')
        
        self._pipelines: Dict[str, Dict[str, Any]] = {}
    
    async def create_codebuild_project(self, config: BuildStageConfig) -> Dict[str, Any]:
        """
        Create CodeBuild project.
        
        Args:
            config: Build stage configuration
            
        Returns:
            Dictionary with CodeBuild project information
        """
        try:
            # Prepare build spec
            if config.inline_buildspec:
                buildspec = config.inline_buildspec
            else:
                buildspec = self._generate_default_buildspec()
            
            # Prepare project configuration
            project_config = {
                'name': config.project_name,
                'description': f'Build project for {config.project_name}',
                'source': {
                    'type': 'CODEPIPELINE',
                    'buildspec': buildspec
                },
                'artifacts': {
                    'type': 'CODEPIPELINE'
                },
                'environment': {
                    'type': config.environment_type,
                    'image': config.image,
                    'computeType': config.compute_type,
                    'privilegedMode': config.privileged_mode
                },
                'tags': [
                    {'key': 'Service', 'value': 'bharat-voice-assistant'},
                    {'key': 'ManagedBy', 'value': 'pipeline-manager'}
                ]
            }
            
            # Add service role
            if config.service_role_arn:
                project_config['serviceRole'] = config.service_role_arn
            
            # Add environment variables
            if config.environment_variables:
                project_config['environment']['environmentVariables'] = config.environment_variables
            
            # Add VPC configuration
            if config.vpc_config:
                project_config['vpcConfig'] = config.vpc_config
            
            # Add cache configuration
            if config.cache_type != "NO_CACHE":
                project_config['cache'] = {
                    'type': config.cache_type
                }
                if config.cache_location:
                    project_config['cache']['location'] = config.cache_location
            
            # Create CodeBuild project
            project_response = safe_aws_call(
                self.codebuild_client.create_project,
                **project_config
            )
            
            logger.info(f"Created CodeBuild project {config.project_name}")
            
            return {
                'project': project_response['project'],
                'project_arn': project_response['project']['arn']
            }
            
        except Exception as e:
            logger.error(f"Failed to create CodeBuild project {config.project_name}: {e}")
            raise DeploymentError(
                f"CodeBuild project creation failed: {e}",
                error_code="CODEBUILD_PROJECT_CREATION_FAILED",
                context={'project_name': config.project_name}
            )
    
    def _generate_default_buildspec(self) -> str:
        """Generate default buildspec for the voice assistant."""
        buildspec = {
            "version": "0.2",
            "phases": {
                "pre_build": {
                    "commands": [
                        "echo Logging in to Amazon ECR...",
                        "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com",
                        "REPOSITORY_URI=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$IMAGE_REPO_NAME",
                        "COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)",
                        "IMAGE_TAG=${COMMIT_HASH:=latest}"
                    ]
                },
                "build": {
                    "commands": [
                        "echo Build started on `date`",
                        "echo Building the Docker image...",
                        "docker build -t $IMAGE_REPO_NAME:$IMAGE_TAG .",
                        "docker tag $IMAGE_REPO_NAME:$IMAGE_TAG $REPOSITORY_URI:$IMAGE_TAG"
                    ]
                },
                "post_build": {
                    "commands": [
                        "echo Build completed on `date`",
                        "echo Pushing the Docker image...",
                        "docker push $REPOSITORY_URI:$IMAGE_TAG",
                        "echo Writing image definitions file...",
                        "printf '[{\"name\":\"bharat-voice-assistant\",\"imageUri\":\"%s\"}]' $REPOSITORY_URI:$IMAGE_TAG > imagedefinitions.json"
                    ]
                }
            },
            "artifacts": {
                "files": [
                    "imagedefinitions.json"
                ]
            }
        }
        
        return json.dumps(buildspec, indent=2)
    
    async def create_pipeline(self, config: PipelineConfig) -> Dict[str, Any]:
        """
        Create CI/CD pipeline.
        
        Args:
            config: Pipeline configuration
            
        Returns:
            Dictionary with pipeline information
        """
        try:
            # Prepare pipeline stages
            stages = []
            
            # Source stage
            source_stage = await self._create_source_stage(config.source_stage)
            stages.append(source_stage)
            
            # Build stage
            if config.build_stage:
                # Create CodeBuild project if needed
                if config.build_stage.provider == BuildProvider.CODEBUILD:
                    await self.create_codebuild_project(config.build_stage)
                
                build_stage = await self._create_build_stage(config.build_stage)
                stages.append(build_stage)
            
            # Test stages
            for test_stage_config in config.test_stages:
                test_stage = await self._create_test_stage(test_stage_config)
                stages.append(test_stage)
            
            # Approval stages
            for approval_stage_config in config.approval_stages:
                approval_stage = await self._create_approval_stage(approval_stage_config)
                stages.append(approval_stage)
            
            # Deploy stages
            for deploy_stage_config in config.deploy_stages:
                deploy_stage = await self._create_deploy_stage(deploy_stage_config)
                stages.append(deploy_stage)
            
            # Prepare artifact store
            artifact_store = {
                'type': 'S3',
                'location': config.artifact_store_bucket
            }
            
            if config.encryption_key_id:
                artifact_store['encryptionKey'] = {
                    'id': config.encryption_key_id,
                    'type': 'KMS'
                }
            
            # Prepare pipeline configuration
            pipeline_config = {
                'pipeline': {
                    'name': config.pipeline_name,
                    'roleArn': config.service_role_arn,
                    'artifactStore': artifact_store,
                    'stages': stages
                },
                'tags': [{'key': k, 'value': v} for k, v in config.tags.items()]
            }
            
            # Create pipeline
            pipeline_response = safe_aws_call(
                self.codepipeline_client.create_pipeline,
                **pipeline_config
            )
            
            # Store pipeline information
            self._pipelines[config.pipeline_name] = {
                'config': config,
                'pipeline': pipeline_response['pipeline']
            }
            
            logger.info(f"Created CI/CD pipeline {config.pipeline_name}")
            
            return {
                'pipeline': pipeline_response['pipeline'],
                'pipeline_arn': f"arn:aws:codepipeline:{aws_clients._boto_config.region_name}:*:pipeline/{config.pipeline_name}"
            }
            
        except Exception as e:
            logger.error(f"Failed to create pipeline {config.pipeline_name}: {e}")
            raise DeploymentError(
                f"Pipeline creation failed: {e}",
                error_code="PIPELINE_CREATION_FAILED",
                context={'pipeline_name': config.pipeline_name}
            )
    
    async def _create_source_stage(self, config: SourceStageConfig) -> Dict[str, Any]:
        """Create source stage configuration."""
        stage = {
            'name': 'Source',
            'actions': [
                {
                    'name': 'SourceAction',
                    'actionTypeId': {
                        'category': 'Source',
                        'owner': 'ThirdParty' if config.provider == SourceProvider.GITHUB else 'AWS',
                        'provider': config.provider.value,
                        'version': '1'
                    },
                    'outputArtifacts': [
                        {'name': artifact} for artifact in config.output_artifacts
                    ]
                }
            ]
        }
        
        # Configure based on provider
        if config.provider == SourceProvider.GITHUB:
            stage['actions'][0]['configuration'] = {
                'Owner': config.github_owner,
                'Repo': config.repository_name,
                'Branch': config.branch_name,
                'OAuthToken': f"{{{{resolve:secretsmanager:{config.github_token_secret_arn}:SecretString:token}}}}"
            }
        elif config.provider == SourceProvider.CODECOMMIT:
            stage['actions'][0]['configuration'] = {
                'RepositoryName': config.repository_name,
                'BranchName': config.branch_name
            }
        elif config.provider == SourceProvider.S3:
            stage['actions'][0]['configuration'] = {
                'S3Bucket': config.s3_bucket,
                'S3ObjectKey': config.s3_key
            }
        
        return stage
    
    async def _create_build_stage(self, config: BuildStageConfig) -> Dict[str, Any]:
        """Create build stage configuration."""
        stage = {
            'name': 'Build',
            'actions': [
                {
                    'name': 'BuildAction',
                    'actionTypeId': {
                        'category': 'Build',
                        'owner': 'AWS',
                        'provider': config.provider.value,
                        'version': '1'
                    },
                    'inputArtifacts': [
                        {'name': artifact} for artifact in config.input_artifacts
                    ],
                    'outputArtifacts': [
                        {'name': artifact} for artifact in config.output_artifacts
                    ],
                    'configuration': {
                        'ProjectName': config.project_name
                    }
                }
            ]
        }
        
        return stage
    
    async def _create_test_stage(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create test stage configuration."""
        stage = {
            'name': test_config.get('name', 'Test'),
            'actions': [
                {
                    'name': 'TestAction',
                    'actionTypeId': {
                        'category': 'Test',
                        'owner': 'AWS',
                        'provider': 'CodeBuild',
                        'version': '1'
                    },
                    'inputArtifacts': [
                        {'name': artifact} for artifact in test_config.get('input_artifacts', ['BuildOutput'])
                    ],
                    'configuration': {
                        'ProjectName': test_config['project_name']
                    }
                }
            ]
        }
        
        return stage
    
    async def _create_approval_stage(self, approval_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create manual approval stage configuration."""
        stage = {
            'name': approval_config.get('name', 'Approval'),
            'actions': [
                {
                    'name': 'ApprovalAction',
                    'actionTypeId': {
                        'category': 'Approval',
                        'owner': 'AWS',
                        'provider': 'Manual',
                        'version': '1'
                    },
                    'configuration': {
                        'CustomData': approval_config.get('message', 'Please review and approve the deployment')
                    }
                }
            ]
        }
        
        if approval_config.get('sns_topic_arn'):
            stage['actions'][0]['configuration']['NotificationArn'] = approval_config['sns_topic_arn']
        
        return stage
    
    async def _create_deploy_stage(self, config: DeployStageConfig) -> Dict[str, Any]:
        """Create deploy stage configuration."""
        stage = {
            'name': f'Deploy-{config.provider.value}',
            'actions': [
                {
                    'name': 'DeployAction',
                    'actionTypeId': {
                        'category': 'Deploy',
                        'owner': 'AWS',
                        'provider': config.provider.value,
                        'version': '1'
                    },
                    'inputArtifacts': [
                        {'name': artifact} for artifact in config.input_artifacts
                    ]
                }
            ]
        }
        
        # Configure based on provider
        if config.provider == DeployProvider.ECS:
            stage['actions'][0]['configuration'] = {
                'ClusterName': config.cluster_name,
                'ServiceName': config.service_name,
                'FileName': config.image_definitions_file
            }
        elif config.provider == DeployProvider.CODEDEPLOY:
            stage['actions'][0]['configuration'] = {
                'ApplicationName': config.application_name,
                'DeploymentGroupName': config.deployment_group_name
            }
        elif config.provider == DeployProvider.CLOUDFORMATION:
            stage['actions'][0]['configuration'] = {
                'ActionMode': 'CREATE_UPDATE',
                'StackName': config.stack_name,
                'TemplatePath': config.template_path,
                'Capabilities': 'CAPABILITY_IAM,CAPABILITY_NAMED_IAM',
                'RoleArn': config.role_arn
            }
            
            if config.parameter_overrides:
                stage['actions'][0]['configuration']['ParameterOverrides'] = json.dumps(config.parameter_overrides)
        elif config.provider == DeployProvider.S3:
            stage['actions'][0]['configuration'] = {
                'BucketName': config.s3_bucket,
                'ObjectKey': config.s3_key,
                'Extract': str(config.extract).lower()
            }
        
        return stage
    
    async def start_pipeline_execution(self, pipeline_name: str) -> Dict[str, Any]:
        """
        Start pipeline execution.
        
        Args:
            pipeline_name: Name of the pipeline
            
        Returns:
            Dictionary with execution information
        """
        try:
            execution_response = safe_aws_call(
                self.codepipeline_client.start_pipeline_execution,
                name=pipeline_name
            )
            
            logger.info(f"Started pipeline execution for {pipeline_name}")
            
            return {
                'pipeline_name': pipeline_name,
                'execution_id': execution_response['pipelineExecutionId']
            }
            
        except Exception as e:
            logger.error(f"Failed to start pipeline execution for {pipeline_name}: {e}")
            raise DeploymentError(
                f"Pipeline execution start failed: {e}",
                error_code="PIPELINE_EXECUTION_START_FAILED",
                context={'pipeline_name': pipeline_name}
            )
    
    async def get_pipeline_status(self, pipeline_name: str) -> Dict[str, Any]:
        """
        Get pipeline execution status.
        
        Args:
            pipeline_name: Name of the pipeline
            
        Returns:
            Dictionary with pipeline status
        """
        try:
            # Get pipeline state
            pipeline_state = safe_aws_call(
                self.codepipeline_client.get_pipeline_state,
                name=pipeline_name
            )
            
            # Get recent executions
            executions_response = safe_aws_call(
                self.codepipeline_client.list_pipeline_executions,
                pipelineName=pipeline_name,
                maxResults=5
            )
            
            return {
                'pipeline_name': pipeline_name,
                'pipeline_state': pipeline_state,
                'recent_executions': executions_response['pipelineExecutionSummaries']
            }
            
        except Exception as e:
            logger.error(f"Failed to get pipeline status for {pipeline_name}: {e}")
            raise DeploymentError(
                f"Pipeline status check failed: {e}",
                error_code="PIPELINE_STATUS_CHECK_FAILED",
                context={'pipeline_name': pipeline_name}
            )
    
    async def delete_pipeline(self, pipeline_name: str) -> Dict[str, Any]:
        """
        Delete pipeline.
        
        Args:
            pipeline_name: Name of the pipeline
            
        Returns:
            Dictionary with deletion results
        """
        try:
            safe_aws_call(
                self.codepipeline_client.delete_pipeline,
                name=pipeline_name
            )
            
            # Remove from local storage
            if pipeline_name in self._pipelines:
                del self._pipelines[pipeline_name]
            
            logger.info(f"Deleted pipeline {pipeline_name}")
            
            return {
                'pipeline_name': pipeline_name,
                'deleted': True
            }
            
        except Exception as e:
            logger.error(f"Failed to delete pipeline {pipeline_name}: {e}")
            raise DeploymentError(
                f"Pipeline deletion failed: {e}",
                error_code="PIPELINE_DELETION_FAILED",
                context={'pipeline_name': pipeline_name}
            )