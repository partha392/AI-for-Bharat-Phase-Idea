"""
Accessibility and usability components for the Bharat Voice Assistant.

This package provides comprehensive accessibility features including:
- Simple vocabulary and jargon-free communication
- Consistent command patterns
- Multiple task completion methods
- Helpful error explanations
- User-friendly interfaces for low digital literacy users
"""

from .simple_communication import SimpleCommunicationManager, VocabularySimplifier
from .command_patterns import CommandPatternManager, ConsistentCommands
from .error_handling import AccessibleErrorHandler, UserFriendlyErrors
from .multi_modal import MultiModalInterface, AlternativeInputMethods
from .user_assistance import UserAssistanceSystem, ConfusionDetector, HelpProvider

__all__ = [
    'SimpleCommunicationManager',
    'VocabularySimplifier',
    'CommandPatternManager',
    'ConsistentCommands',
    'AccessibleErrorHandler',
    'UserFriendlyErrors',
    'MultiModalInterface',
    'AlternativeInputMethods',
    'UserAssistanceSystem',
    'ConfusionDetector',
    'HelpProvider'
]