"""
Offline functionality manager for the Bharat Voice Assistant.

This module coordinates offline features using cached data, manages
offline-to-online synchronization, and provides basic functionality
when network connectivity is unavailable.

Implements Requirement 5.5: Function with basic features even when offline, using cached data.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
from datetime import datetime, timedelta

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import OfflineError, NetworkError
from bharat_voice_assistant.core.cache_manager import cache_manager, CacheType
from bharat_voice_assistant.core.request_queue import request_queue, RequestPriority

logger = get_logger(__name__)


class ConnectivityStatus(Enum):
    """Network connectivity status."""
    ONLINE = "online"
    OFFLINE = "offline"
    LIMITED = "limited"  # Poor connectivity
    UNKNOWN = "unknown"


class OfflineMode(Enum):
    """Offline operation modes."""
    FULL_OFFLINE = "full_offline"      # Complete offline operation
    CACHE_ONLY = "cache_only"          # Use cached data only
    QUEUE_REQUESTS = "queue_requests"  # Queue requests for later
    HYBRID = "hybrid"                  # Mix of cached and limited online


@dataclass
class OfflineCapability:
    """Represents an offline capability."""
    feature_name: str
    is_available_offline: bool
    requires_cache: bool
    cache_keys: List[str]
    fallback_responses: List[str]
    description: str


@dataclass
class ConnectivityInfo:
    """Network connectivity information."""
    status: ConnectivityStatus
    bandwidth_kbps: float
    latency_ms: float
    last_check: float
    consecutive_failures: int
    is_stable: bool


class OfflineManager:
    """
    Manages offline functionality and cached data access.
    
    Implements Requirement 5.5: Function with basic features even when offline, using cached data.
    """
    
    def __init__(self):
        """Initialize the offline manager."""
        self.connectivity_info = ConnectivityInfo(
            status=ConnectivityStatus.UNKNOWN,
            bandwidth_kbps=0.0,
            latency_ms=0.0,
            last_check=0.0,
            consecutive_failures=0,
            is_stable=False
        )
        
        # Offline capabilities
        self.offline_capabilities: Dict[str, OfflineCapability] = {}
        self._register_default_capabilities()
        
        # Background tasks
        self._connectivity_task: Optional[asyncio.Task] = None
        self._sync_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Configuration
        self.connectivity_check_interval = 30  # seconds
        self.sync_interval = 60  # seconds
        self.max_consecutive_failures = 3
        
        # Offline mode
        self.current_mode = OfflineMode.HYBRID
        self.force_offline = False
        
        # Callbacks
        self.connectivity_change_callbacks: List[Callable] = []
        
        logger.info("OfflineManager initialized")
    
    async def start(self):
        """Start the offline manager background tasks."""
        # Start connectivity monitoring
        self._connectivity_task = asyncio.create_task(self._monitor_connectivity())
        
        # Start sync task
        self._sync_task = asyncio.create_task(self._sync_offline_data())
        
        # Initial connectivity check
        await self._check_connectivity()
        
        logger.info("OfflineManager started")
    
    async def stop(self):
        """Stop the offline manager."""
        self._shutdown_event.set()
        
        if self._connectivity_task:
            self._connectivity_task.cancel()
        if self._sync_task:
            self._sync_task.cancel()
        
        logger.info("OfflineManager stopped")
    
    def register_offline_capability(self, capability: OfflineCapability):
        """
        Register an offline capability.
        
        Args:
            capability: Offline capability to register
        """
        self.offline_capabilities[capability.feature_name] = capability
        logger.info(f"Registered offline capability: {capability.feature_name}")
    
    def add_connectivity_callback(self, callback: Callable):
        """
        Add callback for connectivity changes.
        
        Args:
            callback: Function to call when connectivity changes
        """
        self.connectivity_change_callbacks.append(callback)
    
    async def is_online(self) -> bool:
        """
        Check if system is currently online.
        
        Returns:
            True if online, False if offline
        """
        if self.force_offline:
            return False
        
        return self.connectivity_info.status == ConnectivityStatus.ONLINE
    
    async def get_connectivity_status(self) -> ConnectivityInfo:
        """Get current connectivity information."""
        return self.connectivity_info
    
    async def set_offline_mode(self, mode: OfflineMode, force: bool = False):
        """
        Set offline operation mode.
        
        Args:
            mode: Offline mode to set
            force: Force offline mode regardless of connectivity
        """
        self.current_mode = mode
        self.force_offline = force
        
        logger.info(f"Offline mode set to: {mode.value} (forced: {force})")
        
        # Notify callbacks
        for callback in self.connectivity_change_callbacks:
            try:
                await callback(self.connectivity_info)
            except Exception as e:
                logger.error(f"Error in connectivity callback: {e}")
    
    async def get_offline_schemes(self, user_profile: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get government schemes from cache for offline use.
        
        Args:
            user_profile: Optional user profile for filtering
            
        Returns:
            List of cached schemes
        """
        try:
            schemes = await cache_manager.get_cached_schemes(user_profile)
            
            if not schemes:
                # Return basic fallback schemes if no cache available
                schemes = self._get_fallback_schemes()
                logger.info("Using fallback schemes (no cache available)")
            else:
                logger.info(f"Retrieved {len(schemes)} schemes from cache")
            
            return schemes
            
        except Exception as e:
            logger.error(f"Error getting offline schemes: {e}")
            return self._get_fallback_schemes()
    
    async def get_offline_responses(self, intent: str, language: str = "hi") -> List[str]:
        """
        Get cached response templates for offline use.
        
        Args:
            intent: Intent identifier
            language: Language code
            
        Returns:
            List of response templates
        """
        try:
            responses = await cache_manager.get_cached_responses(intent, language)
            
            if not responses:
                # Return fallback responses
                responses = self._get_fallback_responses(intent, language)
                logger.debug(f"Using fallback responses for {intent} ({language})")
            
            return responses
            
        except Exception as e:
            logger.error(f"Error getting offline responses: {e}")
            return self._get_fallback_responses(intent, language)
    
    async def queue_offline_request(self, user_id: str, request_type: str,
                                  endpoint: str, payload: Dict[str, Any],
                                  priority: RequestPriority = RequestPriority.MEDIUM) -> str:
        """
        Queue a request for processing when online.
        
        Args:
            user_id: User identifier
            request_type: Type of request
            endpoint: API endpoint
            payload: Request payload
            priority: Request priority
            
        Returns:
            Request ID
        """
        try:
            request_id = await request_queue.enqueue(
                user_id=user_id,
                request_type=request_type,
                endpoint=endpoint,
                payload=payload,
                priority=priority,
                metadata={"queued_offline": True, "queued_at": time.time()}
            )
            
            logger.info(f"Request queued for offline processing: {request_id}")
            return request_id
            
        except Exception as e:
            logger.error(f"Error queuing offline request: {e}")
            raise OfflineError(
                "Failed to queue offline request",
                error_code="QUEUE_FAILED",
                context={"error": str(e)}
            )
    
    async def get_offline_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached user data for offline use.
        
        Args:
            user_id: User identifier
            
        Returns:
            Cached user data or None
        """
        try:
            user_data = await cache_manager.get_cached_user_data(user_id)
            
            if user_data:
                logger.debug(f"Retrieved cached user data for {user_id}")
            else:
                logger.debug(f"No cached user data found for {user_id}")
            
            return user_data
            
        except Exception as e:
            logger.error(f"Error getting offline user data: {e}")
            return None
    
    async def can_handle_offline(self, feature_name: str) -> bool:
        """
        Check if a feature can be handled offline.
        
        Args:
            feature_name: Name of the feature
            
        Returns:
            True if feature is available offline
        """
        capability = self.offline_capabilities.get(feature_name)
        if not capability:
            return False
        
        if not capability.is_available_offline:
            return False
        
        # Check if required cache data is available
        if capability.requires_cache:
            for cache_key in capability.cache_keys:
                cached_data = await cache_manager.get(cache_key)
                if cached_data is None:
                    logger.debug(f"Missing cache data for offline feature {feature_name}: {cache_key}")
                    return False
        
        return True
    
    async def get_offline_capabilities(self) -> List[Dict[str, Any]]:
        """
        Get list of available offline capabilities.
        
        Returns:
            List of offline capabilities with availability status
        """
        capabilities = []
        
        for name, capability in self.offline_capabilities.items():
            is_available = await self.can_handle_offline(name)
            
            capabilities.append({
                "feature_name": name,
                "description": capability.description,
                "is_available": is_available,
                "requires_cache": capability.requires_cache,
                "cache_status": await self._get_cache_status(capability.cache_keys) if capability.requires_cache else None
            })
        
        return capabilities
    
    async def sync_when_online(self) -> Dict[str, Any]:
        """
        Synchronize offline data when connection is restored.
        
        Returns:
            Sync results
        """
        if not await self.is_online():
            return {"status": "offline", "message": "Cannot sync while offline"}
        
        try:
            sync_results = {
                "queued_requests_processed": 0,
                "cache_updated": False,
                "errors": []
            }
            
            # Process queued requests
            stats = await request_queue.get_queue_stats()
            if stats.pending_requests > 0:
                logger.info(f"Processing {stats.pending_requests} queued requests")
                # The request queue will automatically process pending requests
                sync_results["queued_requests_processed"] = stats.pending_requests
            
            # Update cache with fresh data
            try:
                await self._update_cache_from_online()
                sync_results["cache_updated"] = True
            except Exception as e:
                sync_results["errors"].append(f"Cache update failed: {e}")
            
            logger.info("Offline data synchronized")
            return sync_results
            
        except Exception as e:
            logger.error(f"Error synchronizing offline data: {e}")
            return {"status": "error", "message": str(e)}
    
    def _register_default_capabilities(self):
        """Register default offline capabilities."""
        # Scheme discovery
        self.register_offline_capability(OfflineCapability(
            feature_name="scheme_discovery",
            is_available_offline=True,
            requires_cache=True,
            cache_keys=["schemes_all"],
            fallback_responses=[
                "मैं आपको कुछ बुनियादी योजनाओं के बारे में बता सकता हूं।",
                "I can tell you about some basic schemes."
            ],
            description="Discover government schemes using cached data"
        ))
        
        # Basic conversation
        self.register_offline_capability(OfflineCapability(
            feature_name="basic_conversation",
            is_available_offline=True,
            requires_cache=True,
            cache_keys=["responses_greeting_hi", "responses_help_hi"],
            fallback_responses=[
                "नमस्ते! मैं भारत वॉयस असिस्टेंट हूं।",
                "Hello! I am Bharat Voice Assistant."
            ],
            description="Basic conversation and greetings"
        ))
        
        # Status inquiry (limited)
        self.register_offline_capability(OfflineCapability(
            feature_name="status_inquiry",
            is_available_offline=True,
            requires_cache=False,
            cache_keys=[],
            fallback_responses=[
                "मैं अभी ऑफलाइन हूं। कृपया बाद में कोशिश करें।",
                "I am currently offline. Please try again later."
            ],
            description="Limited status inquiry with cached data"
        ))
        
        # Grievance filing (queue only)
        self.register_offline_capability(OfflineCapability(
            feature_name="grievance_filing",
            is_available_offline=True,
            requires_cache=False,
            cache_keys=[],
            fallback_responses=[
                "आपकी शिकायत को सहेज लिया गया है। जब इंटरनेट उपलब्ध होगा तो इसे भेज दिया जाएगा।",
                "Your complaint has been saved. It will be submitted when internet is available."
            ],
            description="Queue grievances for submission when online"
        ))
    
    def _get_fallback_schemes(self) -> List[Dict[str, Any]]:
        """Get basic fallback schemes when cache is unavailable."""
        return [
            {
                "id": "fallback_pm_kisan",
                "name": "PM-KISAN (प्रधानमंत्री किसान सम्मान निधि)",
                "description": "किसानों के लिए आर्थिक सहायता योजना",
                "eligibility": "छोटे और सीमांत किसान",
                "benefits": "₹6000 प्रति वर्ष",
                "application_mode": ["online", "offline"],
                "is_fallback": True
            },
            {
                "id": "fallback_ayushman_bharat",
                "name": "Ayushman Bharat (आयुष्मान भारत)",
                "description": "स्वास्थ्य बीमा योजना",
                "eligibility": "गरीब और कमजोर वर्गीय परिवार",
                "benefits": "₹5 लाख तक का स्वास्थ्य बीमा",
                "application_mode": ["online", "offline"],
                "is_fallback": True
            },
            {
                "id": "fallback_ujjwala",
                "name": "Pradhan Mantri Ujjwala Yojana (प्रधानमंत्री उज्ज्वला योजना)",
                "description": "महिलाओं के लिए मुफ्त गैस कनेक्शन",
                "eligibility": "BPL परिवार की महिलाएं",
                "benefits": "मुफ्त LPG कनेक्शन",
                "application_mode": ["offline"],
                "is_fallback": True
            }
        ]
    
    def _get_fallback_responses(self, intent: str, language: str) -> List[str]:
        """Get fallback responses for common intents."""
        fallback_responses = {
            "greeting": {
                "hi": [
                    "नमस्ते! मैं भारत वॉयस असिस्टेंट हूं। मैं आपकी सरकारी योजनाओं में मदद कर सकता हूं।",
                    "आपका स्वागत है! मैं सरकारी सेवाओं में आपकी सहायता के लिए यहां हूं।"
                ],
                "en": [
                    "Hello! I am Bharat Voice Assistant. I can help you with government schemes.",
                    "Welcome! I am here to assist you with government services."
                ]
            },
            "help": {
                "hi": [
                    "मैं आपको सरकारी योजनाओं के बारे में जानकारी दे सकता हूं और शिकायत दर्ज करने में मदद कर सकता हूं।",
                    "आप मुझसे योजनाओं की जानकारी, पात्रता की जांच, और आवेदन प्रक्रिया के बारे में पूछ सकते हैं।"
                ],
                "en": [
                    "I can provide information about government schemes and help you file complaints.",
                    "You can ask me about scheme information, eligibility checks, and application processes."
                ]
            },
            "offline": {
                "hi": [
                    "मैं अभी ऑफलाइन मोड में हूं। मैं बुनियादी जानकारी दे सकता हूं और आपके अनुरोधों को सहेज सकता हूं।",
                    "इंटरनेट कनेक्शन उपलब्ध नहीं है। मैं कैश्ड डेटा का उपयोग करके आपकी मदद करूंगा।"
                ],
                "en": [
                    "I am currently in offline mode. I can provide basic information and save your requests.",
                    "Internet connection is not available. I will help you using cached data."
                ]
            },
            "error": {
                "hi": [
                    "क्षमा करें, कुछ तकनीकी समस्या है। कृपया बाद में कोशिश करें।",
                    "मुझे खुशी होगी यदि आप अपना प्रश्न दोबारा पूछें।"
                ],
                "en": [
                    "Sorry, there is a technical issue. Please try again later.",
                    "I would be happy if you could ask your question again."
                ]
            }
        }
        
        return fallback_responses.get(intent, {}).get(language, [
            "मैं आपकी मदद करने की कोशिश कर रहा हूं।",
            "I am trying to help you."
        ])
    
    async def _check_connectivity(self) -> bool:
        """Check network connectivity."""
        try:
            # Simple connectivity test
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                start_time = time.time()
                async with session.get('https://www.google.com') as response:
                    latency = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        # Update connectivity info
                        self.connectivity_info.status = ConnectivityStatus.ONLINE
                        self.connectivity_info.latency_ms = latency
                        self.connectivity_info.last_check = time.time()
                        self.connectivity_info.consecutive_failures = 0
                        self.connectivity_info.is_stable = True
                        
                        # Estimate bandwidth (very rough)
                        if latency < 200:
                            self.connectivity_info.bandwidth_kbps = 256.0
                        elif latency < 500:
                            self.connectivity_info.bandwidth_kbps = 128.0
                        else:
                            self.connectivity_info.bandwidth_kbps = 64.0
                        
                        return True
            
        except Exception as e:
            logger.debug(f"Connectivity check failed: {e}")
            
            # Update connectivity info
            self.connectivity_info.status = ConnectivityStatus.OFFLINE
            self.connectivity_info.last_check = time.time()
            self.connectivity_info.consecutive_failures += 1
            self.connectivity_info.is_stable = False
            
            if self.connectivity_info.consecutive_failures >= self.max_consecutive_failures:
                self.connectivity_info.status = ConnectivityStatus.OFFLINE
            
            return False
    
    async def _monitor_connectivity(self):
        """Background task to monitor connectivity."""
        previous_status = ConnectivityStatus.UNKNOWN
        
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.connectivity_check_interval)
                
                is_connected = await self._check_connectivity()
                current_status = self.connectivity_info.status
                
                # Check for status change
                if current_status != previous_status:
                    logger.info(f"Connectivity status changed: {previous_status.value} -> {current_status.value}")
                    
                    # Notify callbacks
                    for callback in self.connectivity_change_callbacks:
                        try:
                            await callback(self.connectivity_info)
                        except Exception as e:
                            logger.error(f"Error in connectivity callback: {e}")
                    
                    # Trigger sync if coming back online
                    if (previous_status == ConnectivityStatus.OFFLINE and 
                        current_status == ConnectivityStatus.ONLINE):
                        asyncio.create_task(self.sync_when_online())
                
                previous_status = current_status
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connectivity monitoring: {e}")
    
    async def _sync_offline_data(self):
        """Background task to sync offline data."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.sync_interval)
                
                if await self.is_online():
                    await self.sync_when_online()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in offline data sync: {e}")
    
    async def _update_cache_from_online(self):
        """Update cache with fresh data from online sources."""
        try:
            # This would typically fetch fresh data from APIs
            # For now, we'll just log the intent
            logger.info("Updating cache with fresh online data")
            
            # Example: Update scheme cache
            # fresh_schemes = await fetch_schemes_from_api()
            # await cache_manager.cache_schemes(fresh_schemes)
            
            # Example: Update response templates
            # fresh_responses = await fetch_response_templates()
            # for intent, language, responses in fresh_responses:
            #     await cache_manager.cache_responses(intent, language, responses)
            
        except Exception as e:
            logger.error(f"Error updating cache from online: {e}")
            raise
    
    async def _get_cache_status(self, cache_keys: List[str]) -> Dict[str, Any]:
        """Get status of cache keys."""
        cache_status = {}
        
        for key in cache_keys:
            cached_data = await cache_manager.get(key)
            cache_status[key] = {
                "available": cached_data is not None,
                "size": len(str(cached_data)) if cached_data else 0
            }
        
        return cache_status


# Global offline manager instance
offline_manager = OfflineManager()