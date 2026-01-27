"""
AWS Infrastructure components for the Bharat Voice Assistant.

This module provides Infrastructure as Code (IaC) components for deploying
and managing the scalable, multi-region AWS infrastructure required for
the voice assistant platform.
"""

from .auto_scaling import AutoScalingManager, AutoScalingConfig, ScalingPolicy
from .load_balancer import LoadBalancerManager, LoadBalancerConfig, TargetGroupConfig
from .multi_region import MultiRegionManager, RegionConfig, FailoverConfig
from .monitoring import MonitoringManager, AlertConfig, MetricConfig
from .deployment import DeploymentManager, DeploymentConfig, BlueGreenConfig
from .infrastructure_manager import InfrastructureManager, InfrastructureConfig

__all__ = [
    # Auto-scaling
    "AutoScalingManager", "AutoScalingConfig", "ScalingPolicy",
    
    # Load balancing
    "LoadBalancerManager", "LoadBalancerConfig", "TargetGroupConfig",
    
    # Multi-region deployment
    "MultiRegionManager", "RegionConfig", "FailoverConfig",
    
    # Monitoring and alerting
    "MonitoringManager", "AlertConfig", "MetricConfig",
    
    # Deployment management
    "DeploymentManager", "DeploymentConfig", "BlueGreenConfig",
    
    # Main infrastructure manager
    "InfrastructureManager", "InfrastructureConfig",
]