"""
Demonstration of offline functionality and caching for the Bharat Voice Assistant.

This example shows how to use the offline functionality including:
- Local caching for frequently accessed information
- Request queuing for intermittent connectivity  
- Basic offline features using cached data

Implements Requirements 5.3, 5.4, and 5.5.
"""

import asyncio
import json
import time
from typing import Dict, Any, List

from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.offline_integration import (
    offline_integration, OfflineConfig
)
from bharat_voice_assistant.core.cache_manager import CacheType
from bharat_voice_assistant.core.request_queue import RequestPriority
from bharat_voice_assistant.core.offline_manager import OfflineMode

logger = get_logger(__name__)


async def demonstrate_caching():
    """Demonstrate local caching functionality (Requirement 5.3)."""
    logger.info("\n=== Demonstrating Local Caching (Requirement 5.3) ===")
    
    # Sample government schemes data
    sample_schemes = [
        {
            "id": "pm_kisan_2024",
            "name": "PM-KISAN (प्रधानमंत्री किसान सम्मान निधि)",
            "description": "किसानों के लिए आर्थिक सहायता योजना",
            "eligibility": "छोटे और सीमांत किसान",
            "benefits": "₹6000 प्रति वर्ष",
            "documents_required": ["आधार कार्ड", "भूमि दस्तावेज", "बैंक खाता"],
            "application_mode": ["online", "offline"],
            "states": ["ALL"],
            "category": "agriculture"
        },
        {
            "id": "ayushman_bharat_2024",
            "name": "Ayushman Bharat (आयुष्मान भारत)",
            "description": "स्वास्थ्य बीमा योजना",
            "eligibility": "गरीब और कमजोर वर्गीय परिवार",
            "benefits": "₹5 लाख तक का स्वास्थ्य बीमा",
            "documents_required": ["आधार कार्ड", "राशन कार्ड", "SECC सत्यापन"],
            "application_mode": ["online", "offline"],
            "states": ["ALL"],
            "category": "health"
        },
        {
            "id": "ujjwala_yojana_2024",
            "name": "Pradhan Mantri Ujjwala Yojana (प्रधानमंत्री उज्ज्वला योजना)",
            "description": "महिलाओं के लिए मुफ्त गैस कनेक्शन",
            "eligibility": "BPL परिवार की महिलाएं",
            "benefits": "मुफ्त LPG कनेक्शन",
            "documents_required": ["आधार कार्ड", "BPL कार्ड", "बैंक खाता"],
            "application_mode": ["offline"],
            "states": ["ALL"],
            "category": "energy"
        }
    ]
    
    # Cache schemes data
    logger.info("Caching government schemes...")
    success = await offline_integration.cache_data(
        key="schemes_all",
        data=sample_schemes,
        ttl_seconds=3600,  # 1 hour
        metadata={"type": "schemes", "count": len(sample_schemes)}
    )
    logger.info(f"Schemes cached successfully: {success}")
    
    # Cache user-specific data
    user_profile = {
        "user_id": "user_123",
        "name": "राम कुमार",
        "state": "उत्तर प्रदेश",
        "district": "लखनऊ",
        "category": "farmer",
        "language": "hi",
        "income_category": "below_poverty_line"
    }
    
    logger.info("Caching user profile...")
    success = await offline_integration.cache_data(
        key="user_profile_123",
        data=user_profile,
        ttl_seconds=1800,  # 30 minutes
        metadata={"type": "user_profile", "user_id": "user_123"}
    )
    logger.info(f"User profile cached successfully: {success}")
    
    # Cache response templates
    response_templates = {
        "greeting_hi": [
            "नमस्ते! मैं भारत वॉयस असिस्टेंट हूं। मैं आपकी सरकारी योजनाओं में मदद कर सकता हूं।",
            "आपका स्वागत है! मैं सरकारी सेवाओं में आपकी सहायता के लिए यहां हूं।"
        ],
        "help_hi": [
            "मैं आपको सरकारी योजनाओं के बारे में जानकारी दे सकता हूं और शिकायत दर्ज करने में मदद कर सकता हूं।",
            "आप मुझसे योजनाओं की जानकारी, पात्रता की जांच, और आवेदन प्रक्रिया के बारे में पूछ सकते हैं।"
        ],
        "offline_hi": [
            "मैं अभी ऑफलाइन मोड में हूं। मैं कैश्ड डेटा का उपयोग करके आपकी मदद करूंगा।",
            "इंटरनेट कनेक्शन उपलब्ध नहीं है। मैं स्थानीय डेटा से आपकी सहायता करूंगा।"
        ]
    }
    
    for intent, responses in response_templates.items():
        success = await offline_integration.cache_data(
            key=f"responses_{intent}",
            data=responses,
            ttl_seconds=7200,  # 2 hours
            metadata={"type": "responses", "intent": intent, "language": "hi"}
        )
        logger.info(f"Response templates for {intent} cached: {success}")
    
    # Demonstrate cache retrieval
    logger.info("\nRetrieving cached data...")
    
    cached_schemes = await offline_integration.get_cached_data("schemes_all")
    logger.info(f"Retrieved {len(cached_schemes)} cached schemes")
    
    cached_user = await offline_integration.get_cached_data("user_profile_123")
    logger.info(f"Retrieved cached user: {cached_user['name']} from {cached_user['state']}")
    
    cached_responses = await offline_integration.get_cached_data("responses_greeting_hi")
    logger.info(f"Retrieved {len(cached_responses)} greeting responses")


async def demonstrate_request_queuing():
    """Demonstrate request queuing for intermittent connectivity (Requirement 5.4)."""
    logger.info("\n=== Demonstrating Request Queuing (Requirement 5.4) ===")
    
    # Sample requests that would be queued when offline
    sample_requests = [
        {
            "user_id": "user_123",
            "request_type": "grievance_submission",
            "endpoint": "/api/grievances/submit",
            "payload": {
                "title": "सड़क की मरम्मत की आवश्यकता",
                "description": "हमारे गांव की मुख्य सड़क में बड़े गड्ढे हैं जिससे यातायात में समस्या हो रही है।",
                "category": "infrastructure",
                "location": "गांव: रामपुर, जिला: लखनऊ, उत्तर प्रदेश",
                "priority": "medium",
                "contact": {
                    "name": "राम कुमार",
                    "phone": "9876543210"
                }
            },
            "priority": RequestPriority.HIGH
        },
        {
            "user_id": "user_456",
            "request_type": "status_inquiry",
            "endpoint": "/api/grievances/status",
            "payload": {
                "reference_number": "GRV2024001234",
                "user_id": "user_456"
            },
            "priority": RequestPriority.MEDIUM
        },
        {
            "user_id": "user_789",
            "request_type": "scheme_application",
            "endpoint": "/api/schemes/apply",
            "payload": {
                "scheme_id": "pm_kisan_2024",
                "applicant": {
                    "name": "श्याम लाल",
                    "aadhaar": "1234-5678-9012",
                    "phone": "9876543211",
                    "address": "गांव: सीतापुर, जिला: सीतापुर, उत्तर प्रदेश"
                },
                "documents": ["aadhaar_card", "land_documents", "bank_account"]
            },
            "priority": RequestPriority.HIGH
        }
    ]
    
    # Queue requests (simulating offline scenario)
    logger.info("Queuing requests for later processing...")
    queued_request_ids = []
    
    for request_data in sample_requests:
        request_id = await offline_integration.queue_request(
            user_id=request_data["user_id"],
            request_type=request_data["request_type"],
            endpoint=request_data["endpoint"],
            payload=request_data["payload"],
            priority=request_data["priority"]
        )
        
        if request_id:
            queued_request_ids.append(request_id)
            logger.info(f"Queued {request_data['request_type']} request: {request_id}")
    
    # Check request statuses
    logger.info("\nChecking request statuses...")
    for request_id in queued_request_ids:
        status = await offline_integration.get_request_status(request_id)
        if status:
            logger.info(f"Request {request_id}: {status['status']} "
                       f"(retry count: {status['retry_count']})")
    
    # Simulate processing when connection is restored
    logger.info("\nSimulating connection restoration and request processing...")
    
    # Register mock processors for demonstration
    async def mock_grievance_processor(request):
        """Mock processor for grievance submissions."""
        logger.info(f"Processing grievance: {request.payload['title']}")
        await asyncio.sleep(1)  # Simulate processing time
        return {
            "status": "submitted",
            "reference_number": f"GRV{int(time.time())}",
            "message": "शिकायत सफलतापूर्वक दर्ज की गई है"
        }
    
    async def mock_status_processor(request):
        """Mock processor for status inquiries."""
        logger.info(f"Processing status inquiry: {request.payload['reference_number']}")
        await asyncio.sleep(0.5)  # Simulate processing time
        return {
            "status": "in_progress",
            "message": "आपकी शिकायत की जांच की जा रही है",
            "estimated_resolution": "7 दिन"
        }
    
    async def mock_application_processor(request):
        """Mock processor for scheme applications."""
        logger.info(f"Processing scheme application: {request.payload['scheme_id']}")
        await asyncio.sleep(1.5)  # Simulate processing time
        return {
            "status": "submitted",
            "application_id": f"APP{int(time.time())}",
            "message": "आवेदन सफलतापूर्वक जमा किया गया है"
        }
    
    # Register processors
    offline_integration.register_request_processor("grievance_submission", mock_grievance_processor)
    offline_integration.register_request_processor("status_inquiry", mock_status_processor)
    offline_integration.register_request_processor("scheme_application", mock_application_processor)
    
    # Wait for processing
    logger.info("Waiting for request processing...")
    await asyncio.sleep(5)
    
    # Check final statuses
    logger.info("\nFinal request statuses:")
    for request_id in queued_request_ids:
        status = await offline_integration.get_request_status(request_id)
        if status:
            logger.info(f"Request {request_id}: {status['status']}")


async def demonstrate_offline_features():
    """Demonstrate basic offline features using cached data (Requirement 5.5)."""
    logger.info("\n=== Demonstrating Offline Features (Requirement 5.5) ===")
    
    # Set system to offline mode for demonstration
    logger.info("Setting system to offline mode...")
    await offline_integration.offline_manager.set_offline_mode(
        OfflineMode.FULL_OFFLINE, force=True
    )
    
    # Check online status
    is_online = await offline_integration.is_online()
    logger.info(f"System is online: {is_online}")
    
    # Get offline capabilities
    logger.info("\nChecking offline capabilities...")
    capabilities = await offline_integration.offline_manager.get_offline_capabilities()
    
    for capability in capabilities:
        logger.info(f"Feature: {capability['feature_name']}")
        logger.info(f"  Available offline: {capability['is_available']}")
        logger.info(f"  Description: {capability['description']}")
    
    # Demonstrate offline scheme discovery
    logger.info("\nDemonstrating offline scheme discovery...")
    offline_schemes = await offline_integration.get_offline_schemes()
    
    logger.info(f"Found {len(offline_schemes)} schemes available offline:")
    for scheme in offline_schemes[:3]:  # Show first 3
        logger.info(f"  - {scheme['name']}")
        logger.info(f"    Benefits: {scheme['benefits']}")
        logger.info(f"    Application: {', '.join(scheme['application_mode'])}")
    
    # Demonstrate offline responses
    logger.info("\nDemonstrating offline response generation...")
    
    intents_to_test = ["greeting", "help", "offline", "error"]
    
    for intent in intents_to_test:
        responses = await offline_integration.get_offline_responses(intent, "hi")
        if responses:
            logger.info(f"Offline responses for '{intent}':")
            for i, response in enumerate(responses[:2], 1):  # Show first 2
                logger.info(f"  {i}. {response}")
    
    # Demonstrate offline user data access
    logger.info("\nDemonstrating offline user data access...")
    
    # Try to get cached user data
    cached_user = await offline_integration.get_cached_data("user_profile_123")
    if cached_user:
        logger.info(f"Offline user data available for: {cached_user['name']}")
        logger.info(f"  State: {cached_user['state']}")
        logger.info(f"  Category: {cached_user['category']}")
        logger.info(f"  Language: {cached_user['language']}")
    else:
        logger.info("No cached user data available")
    
    # Demonstrate offline request handling with fallback
    logger.info("\nDemonstrating offline request handling with fallback...")
    
    async def online_scheme_search(payload):
        """Mock online scheme search (would fail in offline mode)."""
        raise Exception("Network unavailable")
    
    async def offline_scheme_search(payload):
        """Offline scheme search using cached data."""
        user_category = payload.get("category", "general")
        cached_schemes = await offline_integration.get_cached_data("schemes_all", [])
        
        # Filter schemes by category
        matching_schemes = [
            scheme for scheme in cached_schemes
            if scheme.get("category") == user_category or scheme.get("states") == ["ALL"]
        ]
        
        return {
            "schemes": matching_schemes[:3],  # Return top 3 matches
            "total_found": len(matching_schemes),
            "source": "offline_cache"
        }
    
    # Test fallback handling
    result = await offline_integration.handle_request_with_fallback(
        user_id="user_123",
        request_type="scheme_search",
        endpoint="/api/schemes/search",
        payload={"category": "agriculture", "state": "उत्तर प्रदेश"},
        online_handler=online_scheme_search,
        offline_handler=offline_scheme_search,
        priority=RequestPriority.MEDIUM
    )
    
    logger.info(f"Fallback result: {result['status']} from {result['source']}")
    if result["status"] == "success":
        schemes_found = result["result"]["total_found"]
        logger.info(f"Found {schemes_found} matching schemes offline")
    
    # Reset to hybrid mode
    logger.info("\nResetting to hybrid mode...")
    await offline_integration.offline_manager.set_offline_mode(
        OfflineMode.HYBRID, force=False
    )


async def demonstrate_system_monitoring():
    """Demonstrate system status monitoring and statistics."""
    logger.info("\n=== Demonstrating System Monitoring ===")
    
    # Get comprehensive system status
    system_status = await offline_integration.get_system_status()
    
    logger.info("System Status:")
    logger.info(f"  Online: {system_status['is_online']}")
    logger.info(f"  Timestamp: {time.ctime(system_status['timestamp'])}")
    
    # Cache component status
    cache_info = system_status["components"]["caching"]
    logger.info(f"\nCache Component:")
    logger.info(f"  Enabled: {cache_info['enabled']}")
    if cache_info["stats"]:
        stats = cache_info["stats"]
        logger.info(f"  Hit Rate: {stats.hit_rate:.2%}")
        logger.info(f"  Total Entries: {stats.total_entries}")
        logger.info(f"  Total Size: {stats.total_size_bytes} bytes")
    
    # Request queue status
    queue_info = system_status["components"]["request_queue"]
    logger.info(f"\nRequest Queue Component:")
    logger.info(f"  Enabled: {queue_info['enabled']}")
    if queue_info["stats"]:
        stats = queue_info["stats"]
        logger.info(f"  Pending Requests: {stats.pending_requests}")
        logger.info(f"  Completed Requests: {stats.completed_requests}")
        logger.info(f"  Success Rate: {stats.success_rate:.2%}")
    
    # Offline mode status
    offline_info = system_status["components"]["offline_mode"]
    logger.info(f"\nOffline Mode Component:")
    logger.info(f"  Enabled: {offline_info['enabled']}")
    if offline_info["connectivity"]:
        conn = offline_info["connectivity"]
        logger.info(f"  Connectivity Status: {conn.status.value}")
        logger.info(f"  Bandwidth: {conn.bandwidth_kbps:.1f} kbps")
        logger.info(f"  Latency: {conn.latency_ms:.1f} ms")
    
    # Offline capabilities
    capabilities = offline_info.get("capabilities", [])
    logger.info(f"  Available Offline Features: {len([c for c in capabilities if c['is_available']])}")


async def main():
    """Main demonstration function."""
    logger.info("Starting Offline Functionality Demonstration")
    logger.info("=" * 60)
    
    try:
        # Initialize offline integration
        logger.info("Initializing offline integration...")
        await offline_integration.initialize()
        
        # Run demonstrations
        await demonstrate_caching()
        await demonstrate_request_queuing()
        await demonstrate_offline_features()
        await demonstrate_system_monitoring()
        
        logger.info("\n" + "=" * 60)
        logger.info("Offline Functionality Demonstration Complete!")
        logger.info("\nKey Features Demonstrated:")
        logger.info("✓ Local caching for frequently accessed information (Req 5.3)")
        logger.info("✓ Request queuing for intermittent connectivity (Req 5.4)")
        logger.info("✓ Basic offline features using cached data (Req 5.5)")
        logger.info("✓ Automatic online/offline fallback handling")
        logger.info("✓ System status monitoring and statistics")
        
    except Exception as e:
        logger.error(f"Error in demonstration: {e}")
        raise
    
    finally:
        # Cleanup
        logger.info("\nCleaning up...")
        await offline_integration.shutdown()


if __name__ == "__main__":
    asyncio.run(main())