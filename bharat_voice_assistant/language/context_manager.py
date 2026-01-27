"""
Context tracking across conversation turns.

This module provides conversation context management capabilities
for maintaining state and context across multiple interaction turns
in government service conversations.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid

from ..core.exceptions import ContextManagementError
from ..core.config import config

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """States of conversation flow."""
    INITIAL = "initial"
    SCHEME_DISCOVERY = "scheme_discovery"
    GRIEVANCE_FILING = "grievance_filing"
    STATUS_TRACKING = "status_tracking"
    DOCUMENT_COLLECTION = "document_collection"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"
    ERROR = "error"


class ContextScope(Enum):
    """Scope of context information."""
    SESSION = "session"  # Current session only
    USER = "user"  # Across all user sessions
    CONVERSATION = "conversation"  # Current conversation thread
    TEMPORARY = "temporary"  # Short-term context


@dataclass
class ConversationTurn:
    """Single turn in a conversation."""
    turn_id: str
    timestamp: datetime
    user_input: str
    language: str
    intent: str
    entities: Dict[str, Any]
    system_response: str
    confidence: float
    state: ConversationState
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Complete conversation context."""
    session_id: str
    user_id: Optional[str]
    conversation_id: str
    created_at: datetime
    last_updated: datetime
    current_state: ConversationState
    language: str
    turns: List[ConversationTurn] = field(default_factory=list)
    persistent_data: Dict[str, Any] = field(default_factory=dict)
    temporary_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """
    Manages conversation context across multiple turns.
    
    Maintains conversation state, user information, and context
    for up to 10 minutes of interaction as specified in requirements.
    """
    
    # Context retention time (10 minutes as per requirements)
    CONTEXT_RETENTION_TIME = timedelta(minutes=10)
    
    def __init__(self):
        """Initialize the context manager."""
        self._active_contexts: Dict[str, ConversationContext] = {}
        self._context_history: Dict[str, List[ConversationContext]] = {}
        self._cleanup_interval = timedelta(minutes=1)
        self._last_cleanup = datetime.now()
        logger.info("ContextManager initialized")
    
    def create_context(self, session_id: str, user_id: Optional[str] = None, 
                      language: str = 'hi') -> ConversationContext:
        """
        Create a new conversation context.
        
        Args:
            session_id: Unique session identifier
            user_id: Optional user identifier
            language: Primary language for the conversation
            
        Returns:
            New ConversationContext
        """
        conversation_id = str(uuid.uuid4())
        now = datetime.now()
        
        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            conversation_id=conversation_id,
            created_at=now,
            last_updated=now,
            current_state=ConversationState.INITIAL,
            language=language
        )
        
        self._active_contexts[session_id] = context
        
        # Initialize user history if needed
        if user_id and user_id not in self._context_history:
            self._context_history[user_id] = []
        
        logger.info("Created new context for session %s", session_id)
        return context
    
    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Get conversation context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ConversationContext if found, None otherwise
        """
        self._cleanup_expired_contexts()
        
        context = self._active_contexts.get(session_id)
        if context:
            # Check if context has expired
            if datetime.now() - context.last_updated > self.CONTEXT_RETENTION_TIME:
                self._expire_context(session_id)
                return None
        
        return context
    
    def update_context(self, session_id: str, turn: ConversationTurn, 
                      new_state: Optional[ConversationState] = None,
                      persistent_data: Optional[Dict[str, Any]] = None,
                      temporary_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update conversation context with new turn and data.
        
        Args:
            session_id: Session identifier
            turn: New conversation turn
            new_state: Optional new conversation state
            persistent_data: Data to persist across turns
            temporary_data: Temporary data for current context
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            context = self.get_context(session_id)
            if not context:
                logger.warning("No context found for session %s", session_id)
                return False
            
            # Add the turn
            context.turns.append(turn)
            context.last_updated = datetime.now()
            
            # Update state if provided
            if new_state:
                context.current_state = new_state
            
            # Update persistent data
            if persistent_data:
                context.persistent_data.update(persistent_data)
            
            # Update temporary data
            if temporary_data:
                context.temporary_data.update(temporary_data)
            
            # Limit number of turns to prevent memory issues
            max_turns = 50
            if len(context.turns) > max_turns:
                context.turns = context.turns[-max_turns:]
            
            logger.debug("Updated context for session %s", session_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update context for session %s: %s", session_id, str(e))
            raise ContextManagementError(f"Failed to update context: {str(e)}")
    
    def get_conversation_history(self, session_id: str, 
                               num_turns: Optional[int] = None) -> List[ConversationTurn]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            num_turns: Number of recent turns to return (all if None)
            
        Returns:
            List of conversation turns
        """
        context = self.get_context(session_id)
        if not context:
            return []
        
        turns = context.turns
        if num_turns:
            turns = turns[-num_turns:]
        
        return turns
    
    def get_persistent_data(self, session_id: str, key: str) -> Any:
        """
        Get persistent data from context.
        
        Args:
            session_id: Session identifier
            key: Data key
            
        Returns:
            Data value or None if not found
        """
        context = self.get_context(session_id)
        if not context:
            return None
        
        return context.persistent_data.get(key)
    
    def set_persistent_data(self, session_id: str, key: str, value: Any) -> bool:
        """
        Set persistent data in context.
        
        Args:
            session_id: Session identifier
            key: Data key
            value: Data value
            
        Returns:
            True if successful, False otherwise
        """
        context = self.get_context(session_id)
        if not context:
            return False
        
        context.persistent_data[key] = value
        context.last_updated = datetime.now()
        return True
    
    def get_temporary_data(self, session_id: str, key: str) -> Any:
        """
        Get temporary data from context.
        
        Args:
            session_id: Session identifier
            key: Data key
            
        Returns:
            Data value or None if not found
        """
        context = self.get_context(session_id)
        if not context:
            return None
        
        return context.temporary_data.get(key)
    
    def set_temporary_data(self, session_id: str, key: str, value: Any) -> bool:
        """
        Set temporary data in context.
        
        Args:
            session_id: Session identifier
            key: Data key
            value: Data value
            
        Returns:
            True if successful, False otherwise
        """
        context = self.get_context(session_id)
        if not context:
            return False
        
        context.temporary_data[key] = value
        context.last_updated = datetime.now()
        return True
    
    def clear_temporary_data(self, session_id: str) -> bool:
        """
        Clear all temporary data for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        context = self.get_context(session_id)
        if not context:
            return False
        
        context.temporary_data.clear()
        context.last_updated = datetime.now()
        return True
    
    def get_context_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of the current context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Context summary dictionary
        """
        context = self.get_context(session_id)
        if not context:
            return {}
        
        # Extract key entities from recent turns
        recent_entities = {}
        for turn in context.turns[-5:]:  # Last 5 turns
            recent_entities.update(turn.entities)
        
        # Get current intent from last turn
        current_intent = context.turns[-1].intent if context.turns else "unknown"
        
        return {
            "session_id": context.session_id,
            "conversation_id": context.conversation_id,
            "current_state": context.current_state.value,
            "language": context.language,
            "turn_count": len(context.turns),
            "current_intent": current_intent,
            "recent_entities": recent_entities,
            "persistent_data_keys": list(context.persistent_data.keys()),
            "temporary_data_keys": list(context.temporary_data.keys()),
            "last_updated": context.last_updated.isoformat(),
            "time_since_update": (datetime.now() - context.last_updated).total_seconds()
        }
    
    def end_conversation(self, session_id: str) -> bool:
        """
        End a conversation and archive the context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            context = self.get_context(session_id)
            if not context:
                return False
            
            # Update state to completed
            context.current_state = ConversationState.COMPLETED
            context.last_updated = datetime.now()
            
            # Archive context if user_id is available
            if context.user_id:
                if context.user_id not in self._context_history:
                    self._context_history[context.user_id] = []
                self._context_history[context.user_id].append(context)
                
                # Limit history size
                max_history = 10
                if len(self._context_history[context.user_id]) > max_history:
                    self._context_history[context.user_id] = self._context_history[context.user_id][-max_history:]
            
            # Remove from active contexts
            del self._active_contexts[session_id]
            
            logger.info("Ended conversation for session %s", session_id)
            return True
            
        except Exception as e:
            logger.error("Failed to end conversation for session %s: %s", session_id, str(e))
            return False
    
    def get_user_history(self, user_id: str) -> List[ConversationContext]:
        """
        Get conversation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of past conversation contexts
        """
        return self._context_history.get(user_id, [])
    
    def _cleanup_expired_contexts(self):
        """Clean up expired contexts."""
        now = datetime.now()
        
        # Only run cleanup periodically
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        expired_sessions = []
        for session_id, context in self._active_contexts.items():
            if now - context.last_updated > self.CONTEXT_RETENTION_TIME:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self._expire_context(session_id)
        
        self._last_cleanup = now
        
        if expired_sessions:
            logger.info("Cleaned up %d expired contexts", len(expired_sessions))
    
    def _expire_context(self, session_id: str):
        """Expire a specific context."""
        context = self._active_contexts.get(session_id)
        if context:
            # Archive if user_id is available
            if context.user_id:
                if context.user_id not in self._context_history:
                    self._context_history[context.user_id] = []
                self._context_history[context.user_id].append(context)
            
            del self._active_contexts[session_id]
            logger.debug("Expired context for session %s", session_id)
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        self._cleanup_expired_contexts()
        return len(self._active_contexts)
    
    def export_context(self, session_id: str) -> Optional[str]:
        """
        Export context as JSON string.
        
        Args:
            session_id: Session identifier
            
        Returns:
            JSON string representation of context
        """
        context = self.get_context(session_id)
        if not context:
            return None
        
        try:
            # Convert to serializable format
            context_dict = {
                "session_id": context.session_id,
                "user_id": context.user_id,
                "conversation_id": context.conversation_id,
                "created_at": context.created_at.isoformat(),
                "last_updated": context.last_updated.isoformat(),
                "current_state": context.current_state.value,
                "language": context.language,
                "turns": [
                    {
                        "turn_id": turn.turn_id,
                        "timestamp": turn.timestamp.isoformat(),
                        "user_input": turn.user_input,
                        "language": turn.language,
                        "intent": turn.intent,
                        "entities": turn.entities,
                        "system_response": turn.system_response,
                        "confidence": turn.confidence,
                        "state": turn.state.value,
                        "metadata": turn.metadata
                    }
                    for turn in context.turns
                ],
                "persistent_data": context.persistent_data,
                "temporary_data": context.temporary_data,
                "metadata": context.metadata
            }
            
            return json.dumps(context_dict, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error("Failed to export context for session %s: %s", session_id, str(e))
            return None