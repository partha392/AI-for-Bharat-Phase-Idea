"""
Docker configuration and containerization for the Bharat Voice Assistant.

This module provides comprehensive Docker management including:
- Multi-stage Docker builds
- Container optimization for voice processing
- Security hardening
- Health checks and monitoring
"""

import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

from ..core.logging import get_logger
from ..core.exceptions import DeploymentError


logger = get_logger(__name__)


@dataclass
class DockerConfig:
    """Configuration for Docker containerization."""
    # Basic settings
    service_name: str = "bharat-voice-assistant"
    base_image: str = "python:3.11-slim"
    working_dir: str = "/app"
    
    # Build settings
    multi_stage_build: bool = True
    optimize_for_size: bool = True
    include_dev_dependencies: bool = False
    
    # Runtime settings
    user_id: int = 1000
    group_id: int = 1000
    non_root_user: str = "appuser"
    
    # Port configuration
    expose_ports: List[int] = field(default_factory=lambda: [8000, 8080])
    health_check_port: int = 8000
    health_check_path: str = "/health"
    
    # Environment variables
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    # Volume mounts
    volumes: List[str] = field(default_factory=list)
    
    # Security settings
    read_only_root: bool = True
    no_new_privileges: bool = True
    drop_capabilities: List[str] = field(default_factory=lambda: ["ALL"])
    add_capabilities: List[str] = field(default_factory=list)
    
    # Resource limits
    memory_limit: str = "2g"
    cpu_limit: str = "1"
    
    # Labels
    labels: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default values."""
        if not self.labels:
            self.labels = {
                "service": self.service_name,
                "version": "latest",
                "maintainer": "bharat-voice-assistant-team"
            }


class DockerManager:
    """Manages Docker configuration and containerization."""
    
    def __init__(self):
        """Initialize the Docker manager."""
        self.logger = get_logger(__name__)
    
    def generate_dockerfile(self, config: DockerConfig, output_path: Optional[str] = None) -> str:
        """
        Generate Dockerfile based on configuration.
        
        Args:
            config: Docker configuration
            output_path: Path to save Dockerfile (optional)
            
        Returns:
            Dockerfile content as string
        """
        try:
            if config.multi_stage_build:
                dockerfile_content = self._generate_multi_stage_dockerfile(config)
            else:
                dockerfile_content = self._generate_single_stage_dockerfile(config)
            
            if output_path:
                with open(output_path, 'w') as f:
                    f.write(dockerfile_content)
                logger.info(f"Generated Dockerfile at {output_path}")
            
            return dockerfile_content
            
        except Exception as e:
            logger.error(f"Failed to generate Dockerfile: {e}")
            raise DeploymentError(
                f"Dockerfile generation failed: {e}",
                error_code="DOCKERFILE_GENERATION_FAILED"
            )
    
    def _generate_multi_stage_dockerfile(self, config: DockerConfig) -> str:
        """Generate multi-stage Dockerfile for optimized builds."""
        dockerfile_lines = [
            "# Multi-stage Dockerfile for Bharat Voice Assistant",
            "# Stage 1: Build dependencies and compile code",
            f"FROM {config.base_image} AS builder",
            "",
            "# Install build dependencies",
            "RUN apt-get update && apt-get install -y \\",
            "    build-essential \\",
            "    gcc \\",
            "    g++ \\",
            "    make \\",
            "    cmake \\",
            "    pkg-config \\",
            "    libffi-dev \\",
            "    libssl-dev \\",
            "    libasound2-dev \\",
            "    portaudio19-dev \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "",
            "# Set working directory",
            f"WORKDIR {config.working_dir}",
            "",
            "# Copy requirements and install Python dependencies",
            "COPY requirements.txt requirements-dev.txt ./",
            "RUN pip install --no-cache-dir --upgrade pip setuptools wheel",
        ]
        
        if config.include_dev_dependencies:
            dockerfile_lines.append("RUN pip install --no-cache-dir -r requirements-dev.txt")
        else:
            dockerfile_lines.append("RUN pip install --no-cache-dir -r requirements.txt")
        
        dockerfile_lines.extend([
            "",
            "# Copy source code",
            "COPY . .",
            "",
            "# Compile any native extensions",
            "RUN python setup.py build_ext --inplace || true",
            "",
            "# Stage 2: Runtime image",
            f"FROM {config.base_image} AS runtime",
            "",
            "# Install runtime dependencies only",
            "RUN apt-get update && apt-get install -y \\",
            "    libasound2 \\",
            "    portaudio19-dev \\",
            "    curl \\",
            "    && rm -rf /var/lib/apt/lists/* \\",
            "    && apt-get clean",
            "",
            f"# Create non-root user",
            f"RUN groupadd -g {config.group_id} {config.non_root_user} && \\",
            f"    useradd -r -u {config.user_id} -g {config.non_root_user} {config.non_root_user}",
            "",
            f"# Set working directory",
            f"WORKDIR {config.working_dir}",
            "",
            "# Copy Python dependencies from builder stage",
            f"COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages",
            f"COPY --from=builder /usr/local/bin /usr/local/bin",
            "",
            "# Copy application code from builder stage",
            f"COPY --from=builder --chown={config.non_root_user}:{config.non_root_user} {config.working_dir} {config.working_dir}",
            "",
            "# Create necessary directories",
            "RUN mkdir -p /app/logs /app/cache /app/queue && \\",
            f"    chown -R {config.non_root_user}:{config.non_root_user} /app/logs /app/cache /app/queue",
            ""
        ])
        
        # Add environment variables
        if config.env_vars:
            dockerfile_lines.append("# Environment variables")
            for key, value in config.env_vars.items():
                dockerfile_lines.append(f"ENV {key}={value}")
            dockerfile_lines.append("")
        
        # Add exposed ports
        if config.expose_ports:
            dockerfile_lines.append("# Expose ports")
            for port in config.expose_ports:
                dockerfile_lines.append(f"EXPOSE {port}")
            dockerfile_lines.append("")
        
        # Add health check
        dockerfile_lines.extend([
            "# Health check",
            f"HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \\",
            f"    CMD curl -f http://localhost:{config.health_check_port}{config.health_check_path} || exit 1",
            ""
        ])
        
        # Add labels
        if config.labels:
            dockerfile_lines.append("# Labels")
            for key, value in config.labels.items():
                dockerfile_lines.append(f'LABEL {key}="{value}"')
            dockerfile_lines.append("")
        
        # Switch to non-root user
        dockerfile_lines.extend([
            f"# Switch to non-root user",
            f"USER {config.non_root_user}",
            "",
            "# Default command",
            'CMD ["python", "-m", "bharat_voice_assistant.main"]'
        ])
        
        return "\n".join(dockerfile_lines)
    
    def _generate_single_stage_dockerfile(self, config: DockerConfig) -> str:
        """Generate single-stage Dockerfile for simpler builds."""
        dockerfile_lines = [
            "# Single-stage Dockerfile for Bharat Voice Assistant",
            f"FROM {config.base_image}",
            "",
            "# Install system dependencies",
            "RUN apt-get update && apt-get install -y \\",
            "    build-essential \\",
            "    libasound2-dev \\",
            "    portaudio19-dev \\",
            "    curl \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "",
            f"# Create non-root user",
            f"RUN groupadd -g {config.group_id} {config.non_root_user} && \\",
            f"    useradd -r -u {config.user_id} -g {config.non_root_user} {config.non_root_user}",
            "",
            f"# Set working directory",
            f"WORKDIR {config.working_dir}",
            "",
            "# Copy requirements and install dependencies",
            "COPY requirements.txt ./",
            "RUN pip install --no-cache-dir --upgrade pip && \\",
            "    pip install --no-cache-dir -r requirements.txt",
            "",
            "# Copy application code",
            f"COPY --chown={config.non_root_user}:{config.non_root_user} . .",
            "",
            "# Create necessary directories",
            "RUN mkdir -p /app/logs /app/cache /app/queue && \\",
            f"    chown -R {config.non_root_user}:{config.non_root_user} /app/logs /app/cache /app/queue",
            ""
        ]
        
        # Add environment variables
        if config.env_vars:
            dockerfile_lines.append("# Environment variables")
            for key, value in config.env_vars.items():
                dockerfile_lines.append(f"ENV {key}={value}")
            dockerfile_lines.append("")
        
        # Add exposed ports
        if config.expose_ports:
            dockerfile_lines.append("# Expose ports")
            for port in config.expose_ports:
                dockerfile_lines.append(f"EXPOSE {port}")
            dockerfile_lines.append("")
        
        # Add health check
        dockerfile_lines.extend([
            "# Health check",
            f"HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \\",
            f"    CMD curl -f http://localhost:{config.health_check_port}{config.health_check_path} || exit 1",
            ""
        ])
        
        # Add labels
        if config.labels:
            dockerfile_lines.append("# Labels")
            for key, value in config.labels.items():
                dockerfile_lines.append(f'LABEL {key}="{value}"')
            dockerfile_lines.append("")
        
        # Switch to non-root user
        dockerfile_lines.extend([
            f"# Switch to non-root user",
            f"USER {config.non_root_user}",
            "",
            "# Default command",
            'CMD ["python", "-m", "bharat_voice_assistant.main"]'
        ])
        
        return "\n".join(dockerfile_lines)
    
    def generate_docker_compose(
        self, 
        config: DockerConfig, 
        services: Optional[List[str]] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate docker-compose.yml for local development.
        
        Args:
            config: Docker configuration
            services: List of services to include
            output_path: Path to save docker-compose.yml
            
        Returns:
            Docker Compose content as string
        """
        try:
            if services is None:
                services = ["voice-gateway", "api-gateway", "redis", "postgres"]
            
            compose_config = {
                "version": "3.8",
                "services": {},
                "networks": {
                    "bharat-voice-network": {
                        "driver": "bridge"
                    }
                },
                "volumes": {
                    "postgres_data": {},
                    "redis_data": {},
                    "app_logs": {},
                    "app_cache": {}
                }
            }
            
            # Main application service
            compose_config["services"]["voice-assistant"] = {
                "build": {
                    "context": ".",
                    "dockerfile": "Dockerfile"
                },
                "ports": [f"{port}:{port}" for port in config.expose_ports],
                "environment": config.env_vars,
                "volumes": [
                    "app_logs:/app/logs",
                    "app_cache:/app/cache"
                ],
                "networks": ["bharat-voice-network"],
                "depends_on": ["redis", "postgres"],
                "restart": "unless-stopped",
                "healthcheck": {
                    "test": [
                        "CMD", "curl", "-f", 
                        f"http://localhost:{config.health_check_port}{config.health_check_path}"
                    ],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                    "start_period": "60s"
                }
            }
            
            # Redis service
            if "redis" in services:
                compose_config["services"]["redis"] = {
                    "image": "redis:7-alpine",
                    "ports": ["6379:6379"],
                    "volumes": ["redis_data:/data"],
                    "networks": ["bharat-voice-network"],
                    "restart": "unless-stopped",
                    "command": "redis-server --appendonly yes"
                }
            
            # PostgreSQL service
            if "postgres" in services:
                compose_config["services"]["postgres"] = {
                    "image": "postgres:15-alpine",
                    "ports": ["5432:5432"],
                    "environment": {
                        "POSTGRES_DB": "bharat_voice_assistant",
                        "POSTGRES_USER": "postgres",
                        "POSTGRES_PASSWORD": "postgres"
                    },
                    "volumes": [
                        "postgres_data:/var/lib/postgresql/data",
                        "./scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql"
                    ],
                    "networks": ["bharat-voice-network"],
                    "restart": "unless-stopped"
                }
            
            # Nginx reverse proxy (optional)
            if "nginx" in services:
                compose_config["services"]["nginx"] = {
                    "image": "nginx:alpine",
                    "ports": ["80:80", "443:443"],
                    "volumes": [
                        "./config/nginx.conf:/etc/nginx/nginx.conf:ro"
                    ],
                    "networks": ["bharat-voice-network"],
                    "depends_on": ["voice-assistant"],
                    "restart": "unless-stopped"
                }
            
            compose_content = self._dict_to_yaml(compose_config)
            
            if output_path:
                with open(output_path, 'w') as f:
                    f.write(compose_content)
                logger.info(f"Generated docker-compose.yml at {output_path}")
            
            return compose_content
            
        except Exception as e:
            logger.error(f"Failed to generate docker-compose.yml: {e}")
            raise DeploymentError(
                f"Docker Compose generation failed: {e}",
                error_code="DOCKER_COMPOSE_GENERATION_FAILED"
            )
    
    def generate_dockerignore(self, output_path: Optional[str] = None) -> str:
        """
        Generate .dockerignore file.
        
        Args:
            output_path: Path to save .dockerignore
            
        Returns:
            .dockerignore content as string
        """
        dockerignore_content = """# Git
.git
.gitignore
.gitattributes

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Logs
*.log
logs/

# Cache
.cache/
cache/
.pytest_cache/
.hypothesis/

# Documentation
docs/
*.md
README*

# Development files
.env.local
.env.development
.env.test
docker-compose.override.yml
docker-compose.dev.yml

# Test files
tests/
test_*.py
*_test.py

# Coverage
.coverage
htmlcov/
.tox/
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/

# Jupyter Notebook
.ipynb_checkpoints

# pyenv
.python-version

# Celery
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json
"""
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(dockerignore_content)
            logger.info(f"Generated .dockerignore at {output_path}")
        
        return dockerignore_content
    
    def _dict_to_yaml(self, data: Dict[str, Any], indent: int = 0) -> str:
        """Convert dictionary to YAML format."""
        yaml_lines = []
        
        for key, value in data.items():
            if isinstance(value, dict):
                yaml_lines.append(f"{'  ' * indent}{key}:")
                yaml_lines.append(self._dict_to_yaml(value, indent + 1))
            elif isinstance(value, list):
                yaml_lines.append(f"{'  ' * indent}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        yaml_lines.append(f"{'  ' * (indent + 1)}-")
                        for sub_key, sub_value in item.items():
                            yaml_lines.append(f"{'  ' * (indent + 2)}{sub_key}: {sub_value}")
                    else:
                        yaml_lines.append(f"{'  ' * (indent + 1)}- {item}")
            else:
                if isinstance(value, str) and (' ' in value or ':' in value):
                    yaml_lines.append(f"{'  ' * indent}{key}: \"{value}\"")
                else:
                    yaml_lines.append(f"{'  ' * indent}{key}: {value}")
        
        return "\n".join(yaml_lines)
    
    def validate_dockerfile(self, dockerfile_path: str) -> Dict[str, Any]:
        """
        Validate Dockerfile for best practices and security.
        
        Args:
            dockerfile_path: Path to Dockerfile
            
        Returns:
            Dictionary with validation results
        """
        try:
            if not os.path.exists(dockerfile_path):
                return {
                    'valid': False,
                    'errors': [f"Dockerfile not found at {dockerfile_path}"]
                }
            
            with open(dockerfile_path, 'r') as f:
                dockerfile_content = f.read()
            
            validation_results = {
                'valid': True,
                'warnings': [],
                'errors': [],
                'suggestions': []
            }
            
            lines = dockerfile_content.split('\n')
            
            # Check for best practices
            has_user = any('USER ' in line for line in lines)
            if not has_user:
                validation_results['warnings'].append("No USER instruction found - running as root")
            
            has_healthcheck = any('HEALTHCHECK' in line for line in lines)
            if not has_healthcheck:
                validation_results['suggestions'].append("Consider adding HEALTHCHECK instruction")
            
            has_label = any('LABEL' in line for line in lines)
            if not has_label:
                validation_results['suggestions'].append("Consider adding LABEL instructions for metadata")
            
            # Check for security issues
            if 'ADD' in dockerfile_content:
                validation_results['warnings'].append("Consider using COPY instead of ADD for better security")
            
            if '--privileged' in dockerfile_content:
                validation_results['errors'].append("Privileged mode detected - security risk")
            
            # Set overall validity
            validation_results['valid'] = len(validation_results['errors']) == 0
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Failed to validate Dockerfile: {e}")
            return {
                'valid': False,
                'errors': [f"Validation failed: {e}"]
            }