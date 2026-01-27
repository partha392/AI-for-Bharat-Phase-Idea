#!/usr/bin/env python3
"""
Government Scheme Database Management Demo

This script demonstrates the automated ingestion, categorization, tagging,
update validation, and version control functionality for government schemes.
"""

import asyncio
import logging
from datetime import datetime, date
from decimal import Decimal

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bharat_voice_assistant.schemes import (
    SchemeDatabaseManager, GovernmentScheme, SchemeCategory, SchemeStatus
)
from bharat_voice_assistant.schemes.models import (
    EligibilityCriteria, SchemeBenefits, ApplicationProcess, SchemeMetadata, DataSource
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_sample_schemes():
    """Create sample government schemes for demonstration."""
    schemes = []
    
    # Sample scheme 1: Agriculture scheme
    scheme1 = GovernmentScheme(
        scheme_id="pmkisan-001",
        name="PM-KISAN Samman Nidhi",
        name_hi="पीएम-किसान सम्मान निधि",
        department="Department of Agriculture and Farmers Welfare",
        ministry="Ministry of Agriculture and Farmers Welfare",
        category=SchemeCategory.AGRICULTURE,
        description="Financial assistance to small and marginal farmers",
        description_hi="छोटे और सीमांत किसानों को वित्तीय सहायता",
        eligibility_criteria=EligibilityCriteria(
            income_limit=200000,
            location_type="rural",
            land_ownership="small_marginal"
        ),
        benefits=SchemeBenefits(
            financial_assistance=6000,
            description="Rs. 6000 per year in three installments"
        ),
        application_process=ApplicationProcess(
            steps=[
                "Visit nearest Common Service Center",
                "Fill PM-KISAN application form",
                "Submit Aadhaar and land documents",
                "Verification by local officials",
                "Approval and fund transfer"
            ],
            required_documents=["aadhaar_card", "land_documents", "bank_account_details"],
            processing_time_days=30,
            application_mode=["online", "offline"]
        ),
        target_states=["UP", "MP", "RJ", "MH", "GJ"],
        status=SchemeStatus.ACTIVE,
        launch_date=date(2019, 2, 24),
        budget_allocated=Decimal("75000000000"),  # 75,000 crores
        beneficiaries_target=120000000,
        beneficiaries_current=110000000,
        metadata=SchemeMetadata(
            data_source=DataSource.GOVERNMENT_API,
            source_url="https://pmkisan.gov.in",
            verification_status="verified",
            tags=["agriculture", "farmers", "financial_assistance", "rural"]
        )
    )
    schemes.append(scheme1)
    
    # Sample scheme 2: Health scheme
    scheme2 = GovernmentScheme(
        scheme_id="ayushman-001",
        name="Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana",
        name_hi="आयुष्मान भारत - प्रधान मंत्री जन आरोग्य योजना",
        department="National Health Authority",
        ministry="Ministry of Health and Family Welfare",
        category=SchemeCategory.HEALTH,
        description="Health insurance scheme for economically vulnerable families",
        description_hi="आर्थिक रूप से कमजोर परिवारों के लिए स्वास्थ्य बीमा योजना",
        eligibility_criteria=EligibilityCriteria(
            income_limit=100000,
            location_type="both",
            additional_criteria={"secc_eligible": True}
        ),
        benefits=SchemeBenefits(
            insurance_coverage=500000,
            description="Health insurance coverage up to Rs. 5 lakh per family per year"
        ),
        application_process=ApplicationProcess(
            steps=[
                "Check eligibility on official website",
                "Visit empaneled hospital",
                "Present Ayushman card or eligible documents",
                "Cashless treatment approval",
                "Receive treatment"
            ],
            required_documents=["aadhaar_card", "ration_card", "secc_verification"],
            processing_time_days=1,
            application_mode=["online", "offline"]
        ),
        target_states=["ALL"],
        status=SchemeStatus.ACTIVE,
        launch_date=date(2018, 9, 23),
        budget_allocated=Decimal("6400000000"),  # 6,400 crores
        beneficiaries_target=500000000,
        beneficiaries_current=230000000,
        metadata=SchemeMetadata(
            data_source=DataSource.GOVERNMENT_API,
            source_url="https://pmjay.gov.in",
            verification_status="verified",
            tags=["health", "insurance", "healthcare", "families"]
        )
    )
    schemes.append(scheme2)
    
    # Sample scheme 3: Housing scheme
    scheme3 = GovernmentScheme(
        scheme_id="pmay-g-001",
        name="Pradhan Mantri Awas Yojana - Gramin",
        name_hi="प्रधान मंत्री आवास योजना - ग्रामीण",
        department="Ministry of Rural Development",
        category=SchemeCategory.HOUSING,
        description="Financial assistance for construction of pucca houses in rural areas",
        description_hi="ग्रामीण क्षेत्रों में पक्के मकान के निर्माण के लिए वित्तीय सहायता",
        eligibility_criteria=EligibilityCriteria(
            income_limit=200000,
            location_type="rural",
            housing_status="homeless_or_inadequate"
        ),
        benefits=SchemeBenefits(
            financial_assistance=120000,
            description="Financial assistance for construction of pucca house"
        ),
        application_process=ApplicationProcess(
            steps=[
                "Apply through Gram Panchayat",
                "Social audit and verification",
                "Technical sanction",
                "First installment release",
                "Construction and monitoring",
                "Final installment on completion"
            ],
            required_documents=["aadhaar_card", "income_certificate", "bank_account_details", "land_documents"],
            processing_time_days=90,
            application_mode=["offline"]
        ),
        target_states=["UP", "MP", "RJ", "WB", "OR", "JH", "CG"],
        status=SchemeStatus.ACTIVE,
        launch_date=date(2016, 11, 20),
        budget_allocated=Decimal("1300000000"),  # 1,300 crores
        beneficiaries_target=10000000,
        beneficiaries_current=8500000,
        metadata=SchemeMetadata(
            data_source=DataSource.WEB_SCRAPING,
            source_url="https://pmayg.nic.in",
            verification_status="verified",
            tags=["housing", "rural", "construction", "pucca_house"]
        )
    )
    schemes.append(scheme3)
    
    return schemes


async def demonstrate_database_operations():
    """Demonstrate various database operations."""
    logger.info("Starting Government Scheme Database Management Demo")
    
    # Initialize database manager
    db_manager = SchemeDatabaseManager()
    
    try:
        # Initialize database connections
        await db_manager.initialize()
        logger.info("Database manager initialized successfully")
        
        # Create sample schemes
        sample_schemes = await create_sample_schemes()
        logger.info(f"Created {len(sample_schemes)} sample schemes")
        
        # Demonstrate scheme saving and retrieval
        logger.info("\n=== Demonstrating Scheme Storage and Retrieval ===")
        for scheme in sample_schemes:
            # Save scheme (in a real implementation, this would save to database)
            success = await db_manager._save_new_scheme(scheme)
            if success:
                logger.info(f"✓ Saved scheme: {scheme.name}")
            else:
                logger.error(f"✗ Failed to save scheme: {scheme.name}")
            
            # Retrieve scheme
            retrieved_scheme = await db_manager.get_scheme_by_id(scheme.scheme_id)
            if retrieved_scheme:
                logger.info(f"✓ Retrieved scheme: {retrieved_scheme.name}")
            else:
                logger.info(f"✗ Could not retrieve scheme: {scheme.scheme_id}")
        
        # Demonstrate categorization and tagging
        logger.info("\n=== Demonstrating Auto-Categorization and Tagging ===")
        for scheme in sample_schemes:
            success, tags = await db_manager.categorize_and_tag_scheme(scheme.scheme_id)
            if success:
                logger.info(f"✓ Categorized {scheme.name}")
                logger.info(f"  Category: {scheme.category.value}")
                logger.info(f"  Tags: {', '.join(tags[:5])}")  # Show first 5 tags
            else:
                logger.info(f"✗ Failed to categorize {scheme.name}")
        
        # Demonstrate scheme search
        logger.info("\n=== Demonstrating Scheme Search ===")
        
        # Search by query
        search_results = await db_manager.search_schemes(query="farmer", limit=5)
        logger.info(f"Search for 'farmer': {len(search_results)} results")
        
        # Search by category
        search_results = await db_manager.search_schemes(
            category=SchemeCategory.HEALTH,
            limit=5
        )
        logger.info(f"Search for health schemes: {len(search_results)} results")
        
        # Search by state
        search_results = await db_manager.search_schemes(
            state="UP",
            limit=5
        )
        logger.info(f"Search for UP schemes: {len(search_results)} results")
        
        # Demonstrate scheme updates and version control
        logger.info("\n=== Demonstrating Scheme Updates and Version Control ===")
        
        # Update a scheme
        update_data = {
            'description': 'Updated description for demonstration',
            'beneficiaries_current': 120000000  # Updated beneficiary count
        }
        
        update_result = await db_manager.validate_scheme_update(
            sample_schemes[0].scheme_id,
            update_data
        )
        
        if update_result.success:
            logger.info(f"✓ Updated scheme: {sample_schemes[0].name}")
            logger.info(f"  Previous version: {update_result.previous_version}")
            logger.info(f"  New version: {update_result.new_version}")
            logger.info(f"  Changes: {', '.join(update_result.changes_detected)}")
        else:
            logger.info(f"✗ Failed to update scheme: {', '.join(update_result.validation_errors)}")
        
        # Get version history
        versions = await db_manager.get_scheme_versions(sample_schemes[0].scheme_id)
        logger.info(f"Version history for {sample_schemes[0].name}: {len(versions)} versions")
        
        # Demonstrate ingestion from sources
        logger.info("\n=== Demonstrating Automated Ingestion ===")
        try:
            ingestion_result = await db_manager.ingest_schemes_from_sources()
            logger.info("✓ Completed automated ingestion")
            logger.info(f"  Total processed: {ingestion_result.total_processed}")
            logger.info(f"  Successful updates: {ingestion_result.successful_updates}")
            logger.info(f"  Failed updates: {ingestion_result.failed_updates}")
            logger.info(f"  New schemes: {ingestion_result.new_schemes}")
            logger.info(f"  Updated schemes: {ingestion_result.updated_schemes}")
            logger.info(f"  Processing time: {ingestion_result.processing_time_seconds:.2f}s")
        except Exception as e:
            logger.info(f"✗ Ingestion failed (expected in demo): {str(e)}")
        
        # Get database statistics
        logger.info("\n=== Database Statistics ===")
        stats = await db_manager.get_database_statistics()
        logger.info(f"Total schemes: {stats.get('total_schemes', 0)}")
        logger.info(f"Schemes by category: {stats.get('schemes_by_category', {})}")
        logger.info(f"Recent ingestions: {len(stats.get('recent_ingestions', []))}")
        
        logger.info("\n=== Demo Completed Successfully ===")
        
    except Exception as e:
        logger.error(f"Demo failed with error: {str(e)}")
        raise
    
    finally:
        # Clean up database connections
        await db_manager.close()
        logger.info("Database connections closed")


async def demonstrate_validation_features():
    """Demonstrate validation and error handling features."""
    logger.info("\n=== Demonstrating Validation Features ===")
    
    db_manager = SchemeDatabaseManager()
    
    try:
        await db_manager.initialize()
        
        # Create an invalid scheme for validation testing
        invalid_scheme = GovernmentScheme(
            scheme_id="",  # Invalid: empty scheme ID
            name="",  # Invalid: empty name
            department="",  # Invalid: empty department
            category=SchemeCategory.AGRICULTURE,
            description="Short",  # Invalid: too short description
            eligibility_criteria=EligibilityCriteria(
                income_limit=-1000,  # Invalid: negative income
                age_min=150,  # Invalid: unrealistic age
                age_max=10   # Invalid: max < min
            ),
            benefits=SchemeBenefits(
                financial_assistance=-5000,  # Invalid: negative assistance
                subsidy_percentage=150  # Invalid: > 100%
            ),
            application_process=ApplicationProcess(
                steps=[],  # Invalid: no steps
                required_documents=["invalid_doc"],  # Invalid document type
                processing_time_days=-10  # Invalid: negative time
            )
        )
        
        # Test validation
        is_valid, errors = db_manager.validator.validate_scheme(invalid_scheme)
        logger.info(f"Validation result: {'✓ Valid' if is_valid else '✗ Invalid'}")
        if not is_valid:
            logger.info("Validation errors:")
            for error in errors[:5]:  # Show first 5 errors
                logger.info(f"  - {error}")
            if len(errors) > 5:
                logger.info(f"  ... and {len(errors) - 5} more errors")
        
        # Test update validation with non-existent scheme
        update_result = await db_manager.validate_scheme_update("nonexistent-scheme", {})
        logger.info(f"Update non-existent scheme: {'✓ Success' if update_result.success else '✗ Failed'}")
        if not update_result.success:
            logger.info(f"  Error: {update_result.validation_errors[0]}")
        
    finally:
        await db_manager.close()


def main():
    """Main function to run the demo."""
    print("Government Scheme Database Management System Demo")
    print("=" * 60)
    
    try:
        # Run the main demonstration
        asyncio.run(demonstrate_database_operations())
        
        # Run validation demonstration
        asyncio.run(demonstrate_validation_features())
        
        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("\nKey features demonstrated:")
        print("✓ Automated scheme ingestion from government sources")
        print("✓ Intelligent categorization and tagging")
        print("✓ Update validation and version control")
        print("✓ Comprehensive search and filtering")
        print("✓ Database statistics and monitoring")
        print("✓ Error handling and validation")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()