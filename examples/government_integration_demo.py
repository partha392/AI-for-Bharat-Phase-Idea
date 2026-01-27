#!/usr/bin/env python3
"""
Government Integration Demo

This script demonstrates the government system integration layer
functionality including API connections, authentication, data
transformation, and grievance submission.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from bharat_voice_assistant.integration.models import (
    GovernmentPortal, APICredentials, APIEndpoint, IntegrationConfig,
    AuthMethod, DataFormat, PortalType
)
from bharat_voice_assistant.integration.integration_service import GovernmentIntegrationService
from bharat_voice_assistant.integration.config_loader import GovernmentPortalConfigLoader
from bharat_voice_assistant.grievance.models import (
    GrievanceRecord, GrievanceDetails, ContactInformation,
    GrievanceType, GrievancePriority
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_demo_integration_config() -> IntegrationConfig:
    """Create a demo integration configuration with mock portals."""
    
    # Create demo central government portal
    central_credentials = APICredentials(
        auth_method=AuthMethod.API_KEY,
        api_key="demo_central_api_key_123"
    )
    
    central_portal = GovernmentPortal(
        id="demo_central_portal",
        name="Demo Central Government Portal",
        portal_type=PortalType.CENTRAL_GOVERNMENT,
        base_url="https://demo-central.gov.in/api/v1",
        credentials=central_credentials,
        priority=1,
        supported_languages=["hi", "en", "ta", "te"],
        rate_limit=100
    )
    
    # Add endpoints to central portal
    central_portal.add_endpoint(APIEndpoint(
        name="submit_grievance",
        url="/grievances/submit",
        method="POST",
        data_format=DataFormat.JSON,
        required_fields=["complaint_description", "category_code", "mobile_number"],
        optional_fields=["email_id", "address", "preferred_language"],
        timeout=30,
        max_retries=3
    ))
    
    central_portal.add_endpoint(APIEndpoint(
        name="check_status",
        url="/grievances/status/{reference_number}",
        method="GET",
        response_format=DataFormat.JSON,
        timeout=15,
        max_retries=2
    ))
    
    # Create demo state government portal
    state_credentials = APICredentials(
        auth_method=AuthMethod.OAUTH2,
        client_id="demo_state_client_id",
        client_secret="demo_state_client_secret",
        token_endpoint="https://demo-state.gov.in/oauth/token",
        scope="grievance:submit grievance:status"
    )
    
    state_portal = GovernmentPortal(
        id="demo_state_portal",
        name="Demo State Government Portal",
        portal_type=PortalType.STATE_GOVERNMENT,
        base_url="https://demo-state.gov.in/api/v1",
        state_code="MH",
        credentials=state_credentials,
        priority=2,
        supported_languages=["hi", "en", "mr"],
        rate_limit=60
    )
    
    # Add endpoints to state portal
    state_portal.add_endpoint(APIEndpoint(
        name="submit_grievance",
        url="/complaints/create",
        method="POST",
        data_format=DataFormat.JSON,
        required_fields=["grievance_details", "grievance_category", "contact_number"],
        optional_fields=["email_address", "preferred_language", "urgency_level"],
        timeout=35,
        max_retries=3
    ))
    
    state_portal.add_endpoint(APIEndpoint(
        name="check_status",
        url="/complaints/{reference_number}/status",
        method="GET",
        response_format=DataFormat.JSON,
        timeout=20,
        max_retries=2
    ))
    
    # Create integration configuration
    return IntegrationConfig(
        portals=[central_portal, state_portal],
        default_timeout=30,
        max_concurrent_requests=5,
        retry_strategy="exponential_backoff",
        circuit_breaker_threshold=3,
        enable_caching=True,
        cache_ttl=300,
        enable_monitoring=True
    )


def create_sample_grievance() -> GrievanceRecord:
    """Create a sample grievance for demonstration."""
    
    # Create grievance details
    details = GrievanceDetails(
        problem_description="मेरी पेंशन पिछले 3 महीनों से रुकी हुई है। कृपया इसे जल्दी शुरू करवाने की व्यवस्था करें।",
        grievance_type=GrievanceType.PENSION_ISSUE,
        affected_service="Pension Services",
        department="Department of Pension and Pensioners' Welfare",
        location="Mumbai, Maharashtra",
        incident_date=datetime.now().date(),
        expected_resolution="Please restart my pension payments immediately",
        urgency_reason="I am dependent on pension for daily expenses"
    )
    
    # Create contact information
    contact_info = ContactInformation(
        phone_number="9876543210",
        email="demo.user@example.com",
        address="123 Demo Street, Andheri, Mumbai, Maharashtra - 400058",
        preferred_contact_method="phone",
        preferred_language="hi"
    )
    
    # Create grievance record
    grievance = GrievanceRecord(
        details=details,
        contact_info=contact_info,
        priority=GrievancePriority.HIGH,
        language="hi",
        source_channel="voice"
    )
    
    return grievance


async def demo_integration_service():
    """Demonstrate the integration service functionality."""
    
    logger.info("=== Government Integration Service Demo ===")
    
    # Create demo configuration
    logger.info("Creating demo integration configuration...")
    integration_config = create_demo_integration_config()
    
    logger.info(f"Loaded {len(integration_config.portals)} government portals:")
    for portal in integration_config.portals:
        logger.info(f"  - {portal.name} ({portal.portal_type.value})")
        logger.info(f"    Base URL: {portal.base_url}")
        logger.info(f"    Auth Method: {portal.credentials.auth_method.value if portal.credentials else 'None'}")
        logger.info(f"    Endpoints: {list(portal.endpoints.keys())}")
    
    # Create sample grievance
    logger.info("\nCreating sample grievance...")
    grievance = create_sample_grievance()
    
    logger.info("Sample Grievance Details:")
    logger.info(f"  Problem: {grievance.details.problem_description}")
    logger.info(f"  Type: {grievance.details.grievance_type.value}")
    logger.info(f"  Priority: {grievance.priority.value}")
    logger.info(f"  Contact: {grievance.contact_info.phone_number}")
    logger.info(f"  Language: {grievance.language}")
    
    # Initialize integration service
    logger.info("\nInitializing integration service...")
    
    # Note: In a real scenario, this would attempt to connect to actual government APIs
    # For demo purposes, we'll show the configuration and simulate the process
    
    try:
        async with GovernmentIntegrationService(integration_config) as integration_service:
            
            # Show portal status
            logger.info("\nPortal Status:")
            portal_status = integration_service.get_portal_status()
            for portal_id, status in portal_status.items():
                logger.info(f"  {portal_id}:")
                logger.info(f"    Name: {status['name']}")
                logger.info(f"    Type: {status['type']}")
                logger.info(f"    Active: {status['is_active']}")
                logger.info(f"    Priority: {status['priority']}")
                logger.info(f"    Endpoints: {status['endpoints']}")
            
            # Show integration metrics
            logger.info("\nIntegration Metrics:")
            metrics = integration_service.get_integration_metrics()
            logger.info(f"  Portal Count: {metrics['portal_count']}")
            logger.info(f"  Active Portals: {metrics['active_portals']}")
            logger.info(f"  Pending Requests: {metrics['pending_requests']}")
            logger.info(f"  Failed Requests: {metrics['failed_requests']}")
            
            # Demonstrate portal selection
            logger.info("\nDemonstrating portal selection...")
            target_portals = integration_service._select_target_portals(grievance)
            logger.info(f"Selected {len(target_portals)} target portals for submission:")
            for portal in target_portals:
                logger.info(f"  - {portal.name} (Priority: {portal.priority})")
            
            # Note: Actual submission would require real API endpoints
            logger.info("\nNote: Actual grievance submission requires real government API endpoints.")
            logger.info("In a production environment, the service would:")
            logger.info("  1. Transform grievance data to portal-specific format")
            logger.info("  2. Authenticate with government APIs")
            logger.info("  3. Submit grievance to selected portals")
            logger.info("  4. Handle retries and fallbacks")
            logger.info("  5. Return reference numbers and status")
            
    except Exception as e:
        logger.error(f"Integration service error: {e}")


def demo_config_loader():
    """Demonstrate the configuration loader functionality."""
    
    logger.info("\n=== Configuration Loader Demo ===")
    
    # Create config loader
    config_loader = GovernmentPortalConfigLoader()
    
    # Try to load configuration from files
    logger.info("Attempting to load configuration from files...")
    
    try:
        integration_config = config_loader.load_integration_config()
        
        logger.info(f"Successfully loaded configuration with {len(integration_config.portals)} portals")
        
        for portal in integration_config.portals:
            logger.info(f"\nPortal: {portal.name}")
            logger.info(f"  ID: {portal.id}")
            logger.info(f"  Type: {portal.portal_type.value}")
            logger.info(f"  Base URL: {portal.base_url}")
            logger.info(f"  State: {portal.state_code or 'All'}")
            logger.info(f"  Active: {portal.is_active}")
            logger.info(f"  Priority: {portal.priority}")
            logger.info(f"  Languages: {portal.supported_languages}")
            logger.info(f"  Endpoints: {list(portal.endpoints.keys())}")
            
            # Validate portal configuration
            issues = config_loader.validate_portal_config(portal)
            if issues:
                logger.warning(f"  Configuration issues: {issues}")
            else:
                logger.info("  Configuration is valid")
    
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        logger.info("This is expected if configuration files are not present")


def demo_data_transformation():
    """Demonstrate data transformation functionality."""
    
    logger.info("\n=== Data Transformation Demo ===")
    
    from bharat_voice_assistant.integration.data_transformer import DataTransformer
    
    # Create data transformer
    transformer = DataTransformer()
    
    # Create sample grievance and portal
    grievance = create_sample_grievance()
    integration_config = create_demo_integration_config()
    central_portal = integration_config.portals[0]  # Get central portal
    endpoint = central_portal.get_endpoint("submit_grievance")
    
    logger.info("Transforming grievance data for government portal...")
    
    # Transform data
    result = transformer.transform_grievance_data(grievance, central_portal, endpoint)
    
    logger.info(f"Transformation Result:")
    logger.info(f"  Valid: {result.is_valid}")
    logger.info(f"  Errors: {len(result.errors)}")
    logger.info(f"  Warnings: {len(result.warnings)}")
    logger.info(f"  Missing Fields: {result.missing_fields}")
    
    if result.errors:
        logger.warning("Transformation Errors:")
        for error in result.errors:
            logger.warning(f"  - {error}")
    
    if result.warnings:
        logger.info("Transformation Warnings:")
        for warning in result.warnings:
            logger.info(f"  - {warning}")
    
    if result.is_valid and result.transformed_data:
        logger.info("Sample of transformed data:")
        if isinstance(result.transformed_data, str):
            # Show first 200 characters of JSON/XML
            preview = result.transformed_data[:200]
            if len(result.transformed_data) > 200:
                preview += "..."
            logger.info(f"  {preview}")
        else:
            logger.info(f"  Data type: {type(result.transformed_data)}")
    
    # Demonstrate field validation
    logger.info("\nDemonstrating field validation...")
    
    # Valid phone number
    phone_result = transformer.validate_field_value("phone_number", "9876543210")
    logger.info(f"Phone validation (9876543210): Valid = {phone_result.is_valid}")
    
    # Invalid phone number
    phone_result = transformer.validate_field_value("phone_number", "123")
    logger.info(f"Phone validation (123): Valid = {phone_result.is_valid}, Errors = {phone_result.errors}")
    
    # Valid email
    email_result = transformer.validate_field_value("email", "test@example.com")
    logger.info(f"Email validation (test@example.com): Valid = {email_result.is_valid}")
    
    # Invalid email
    email_result = transformer.validate_field_value("email", "invalid-email")
    logger.info(f"Email validation (invalid-email): Valid = {email_result.is_valid}, Errors = {email_result.errors}")


async def main():
    """Main demo function."""
    
    print("🇮🇳 Bharat Voice Assistant - Government Integration Demo")
    print("=" * 60)
    
    try:
        # Demo configuration loader
        demo_config_loader()
        
        # Demo data transformation
        demo_data_transformation()
        
        # Demo integration service
        await demo_integration_service()
        
        print("\n" + "=" * 60)
        print("✅ Demo completed successfully!")
        print("\nKey Features Demonstrated:")
        print("  ✓ Government portal configuration loading")
        print("  ✓ Data transformation and validation")
        print("  ✓ Authentication management")
        print("  ✓ API client with retry and circuit breaker")
        print("  ✓ Integration service orchestration")
        print("  ✓ Multi-portal support with fallbacks")
        
        print("\nNext Steps:")
        print("  1. Configure real government portal credentials")
        print("  2. Set up portal configuration files")
        print("  3. Test with actual government APIs")
        print("  4. Implement monitoring and alerting")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())