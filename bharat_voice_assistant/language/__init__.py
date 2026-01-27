"""
Language processing module for Bharat Voice Assistant.

This module provides multilingual natural language understanding capabilities
including intent classification, entity extraction, and context tracking
for government service requests in Hindi, English, and 8 major regional
Indian languages.
"""

from .intent_classifier import IntentClassifier
from .entity_extractor import EntityExtractor
from .context_manager import ContextManager
from .conversation_manager import ConversationManager
from .language_processor import LanguageProcessor

__all__ = [
    "IntentClassifier",
    "EntityExtractor", 
    "ContextManager",
    "ConversationManager",
    "LanguageProcessor"
]