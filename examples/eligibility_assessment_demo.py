"""
Eligibility Assessment System Demo

This script demonstrates the eligibility assessment system functionality,
including rule-based eligibility checking, document requirement analysis,
and success probability estimation.
"""

import asyncio
import logging
from datetime import datetime

from bharat_voice_assistant.schemes.eligibility_assessor import (
    EligibilityAssessor, EligibilityStatus, DocumentStatus
)
from bharat_voice_assistant.schemes.user_profile import (
    UserProfileManager, DemographicInfo, EconomicInfo, LocationInfo
)
from bharat_voice_assistant.schemes.models import (
    GovernmentScheme, SchemeCategory, EligibilityCriteria, 
    SchemeBenefits, ApplicationProcess, SchemeMetadata, DataSource
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_sample_schemes():
    """Create sample government schemes for demonstration."""
    
    # PM Awas Yojana (Housing Scheme)
    pm_awas = GovernmentScheme(
        scheme_id="pmay-g-001",
        name="Pradhan Mantri Awas Yojana - Gramin",
        name_hi="प्रधानमंत्री आवास योजना - ग्रामीण",
        department="Ministry of Rural Development",
        category=SchemeCategory.HOUSING,
        description="Financial assistance for construction of pucca house in rural areas",
        description_hi="ग्रामीण क्षेत्रों में पक्का मकान निर्माण के लिए वित्तीय सहायता",
        eligibility_criteria=EligibilityCriteria(
            age_min=18,
            age_max=70,
            income_limit=200000,
            location_type="rural",
            housing_status="homeless"
        ),
        benefits=SchemeBenefits(
            financial_assistance=120000,
            description="₹1.2 lakh assistance for house construction"
        ),
        application_process=ApplicationProcess(
            required_documents=[
                "Aadhaar Card",
                "Income Certificate", 
                "Caste Certificate",
                "Bank Account Details",
                "Land Documents"
            ],
            processing_time_days=60
        ),
        target_states=["Karnataka", "Tamil Nadu", "Andhra Pradesh"],
        metadata=SchemeMetadata(
            data_source=DataSource.GOVERNMENT_API,
            success_rate=0.78
        )
    )
    
    # PM Kisan Scheme (Agriculture)
    pm_kisan = GovernmentScheme(
        scheme_id="pm-kisan-001",
        name="PM Kisan Samman Nidhi",
        name_hi="पीएम किसान सम्मान निधि",
        department="Ministry of Agriculture",
        category=SchemeCategory.AGRICULTURE,
        description="Income support to small and marginal farmers",
        description_hi="छोटे और सीमांत किसानों को आय सहायता",
        eligibility_criteria=EligibilityCriteria(
            age_min=18,
            land_ownership="small_marginal",
            employment_status="farmer"
        ),
        benefits=SchemeBenefits(
            financial_assistance=6000,
            description="₹6000 per year in three installments"
        ),
        application_process=ApplicationProcess(
            required_documents=[
                "Aadhaar Card",
                "Land Records",
                "Bank Account Details"
            ],
            processing_time_days=30
        ),
        target_states=["All States"],
        metadata=SchemeMetadata(
            data_source=DataSource.GOVERNMENT_API,
            success_rate=0.85
        )
    )
    
    # Disability Pension Scheme
    disability_pension = GovernmentScheme(
        scheme_id="disability-pension-001",
        name="Indira Gandhi National Disability Pension Scheme",
        name_hi="इंदिरा गांधी राष्ट्रीय विकलांगता पेंशन योजना",
        department="Ministry of Social Justice",
        category=SchemeCategory.DISABILITY,
        description="Monthly pension for persons with disabilities",
        description_hi="विकलांग व्यक्तियों के लिए मासिक पेंशन",
        eligibility_criteria=EligibilityCriteria(
            age_min=18,
            age_max=79,
            income_limit=48000,
            disability_status=True
        ),
        benefits=SchemeBenefits(
            financial_assistance=500,
            description="₹500 per month pension"
        ),
        application_process=ApplicationProcess(
            required_documents=[
                "Aadhaar Card",
                "Disability Certificate",
                "Income Certificate",
                "Bank Account Details"
            ],
            processing_time_days=45
        ),
        target_states=["All States"],
        metadata=SchemeMetadata(
            data_source=DataSource.GOVERNMENT_API,
            success_rate=0.72
        )
    )
    
    return [pm_awas, pm_kisan, disability_pension]


async def create_sample_users(profile_manager):
    """Create sample user profiles for demonstration."""
    
    # User 1: Rural farmer eligible for multiple schemes
    await profile_manager.create_profile(
        user_id="farmer_001",
        location=LocationInfo(
            state="Karnataka",
            district="Mysore",
            location_type="rural"
        ),
        demographics=DemographicInfo(
            age=35,
            gender="male",
            caste_category="sc",
            marital_status="married",
            family_size=4
        ),
        economic=EconomicInfo(
            income=150000,
            employment_status="farmer",
            land_ownership="small_marginal",
            housing_status="inadequate",
            bank_account=True
        )
    )
    
    # User 2: Urban person with disability
    await profile_manager.create_profile(
        user_id="urban_disabled_001",
        location=LocationInfo(
            state="Tamil Nadu",
            district="Chennai",
            location_type="urban"
        ),
        demographics=DemographicInfo(
            age=28,
            gender="female",
            disability_status=True,
            marital_status="single"
        ),
        economic=EconomicInfo(
            income=40000,
            employment_status="unemployed",
            housing_status="rented",
            bank_account=True
        )
    )
    
    # User 3: High-income person (not eligible for most schemes)
    await profile_manager.create_profile(
        user_id="high_income_001",
        location=LocationInfo(
            state="Karnataka",
            district="Bangalore",
            location_type="urban"
        ),
        demographics=DemographicInfo(
            age=45,
            gender="male",
            marital_status="married",
            family_size=3
        ),
        economic=EconomicInfo(
            income=800000,
            employment_status="employed",
            housing_status="owned",
            bank_account=True
        )
    )


async def demonstrate_eligibility_assessment():
    """Demonstrate the eligibility assessment system."""
    
    print("=" * 80)
    print("BHARAT VOICE ASSISTANT - ELIGIBILITY ASSESSMENT DEMO")
    print("=" * 80)
    
    # Initialize components
    profile_manager = UserProfileManager()
    assessor = EligibilityAssessor(profile_manager)
    
    # Create sample data
    schemes = await create_sample_schemes()
    await create_sample_users(profile_manager)
    
    users = ["farmer_001", "urban_disabled_001", "high_income_001"]
    user_names = ["Rural Farmer", "Urban Person with Disability", "High-Income Person"]
    
    # Assess eligibility for each user-scheme combination
    for user_id, user_name in zip(users, user_names):
        print(f"\n{'='*60}")
        print(f"ELIGIBILITY ASSESSMENT FOR: {user_name} ({user_id})")
        print(f"{'='*60}")
        
        for scheme in schemes:
            print(f"\n{'-'*50}")
            print(f"SCHEME: {scheme.name}")
            print(f"CATEGORY: {scheme.category.value.title()}")
            print(f"{'-'*50}")
            
            try:
                # Perform eligibility assessment
                assessment = await assessor.assess_eligibility(user_id, scheme)
                
                # Display results
                print(f"Overall Status: {assessment.overall_status.value.upper()}")
                print(f"Eligibility Score: {assessment.eligibility_score:.2f}")
                print(f"Success Probability: {assessment.success_probability:.2%}")
                print(f"Confidence Level: {assessment.confidence_level:.2%}")
                print(f"Data Completeness: {assessment.data_completeness:.2%}")
                
                # Show rule results
                if assessment.passed_rules:
                    print(f"✅ Passed Rules: {', '.join(assessment.passed_rules)}")
                if assessment.failed_rules:
                    print(f"❌ Failed Rules: {', '.join(assessment.failed_rules)}")
                if assessment.missing_data_rules:
                    print(f"❓ Missing Data: {', '.join(assessment.missing_data_rules)}")
                
                # Show document requirements
                print(f"\n📋 Required Documents ({len(assessment.required_documents)}):")
                for doc in assessment.required_documents[:3]:  # Show first 3
                    print(f"   • {doc.document_name} ({doc.document_type})")
                if len(assessment.required_documents) > 3:
                    print(f"   ... and {len(assessment.required_documents) - 3} more")
                
                # Show recommendations
                if assessment.recommendations:
                    print(f"\n💡 Recommendations:")
                    for rec in assessment.recommendations[:2]:  # Show first 2
                        print(f"   • {rec}")
                
                # Show next steps
                if assessment.next_steps:
                    print(f"\n📝 Next Steps:")
                    for step in assessment.next_steps[:2]:  # Show first 2
                        print(f"   • {step}")
                
                # Estimate timeline
                timeline = await assessor.estimate_approval_timeline(assessment, scheme)
                print(f"\n⏱️  Estimated Processing Time: {timeline['estimated_processing_days']} days")
                
            except Exception as e:
                print(f"❌ Error assessing eligibility: {str(e)}")
    
    # Demonstrate document checklist functionality
    print(f"\n{'='*60}")
    print("DOCUMENT CHECKLIST DEMO")
    print(f"{'='*60}")
    
    scheme = schemes[0]  # PM Awas Yojana
    user_id = "farmer_001"
    
    print(f"\nDocument Checklist for {scheme.name}:")
    checklist = await assessor.get_document_checklist(user_id, scheme)
    
    for i, item in enumerate(checklist, 1):
        status_icon = "✅" if item['status'] == 'required' else "📄"
        mandatory_text = "(Mandatory)" if item['mandatory'] else "(Optional)"
        print(f"{i}. {status_icon} {item['document']} {mandatory_text}")
        print(f"   Type: {item['type'].title()}")
        print(f"   Description: {item['description']}")
        if item['alternatives']:
            print(f"   Alternatives: {', '.join(item['alternatives'][:2])}")
        print()


async def demonstrate_edge_cases():
    """Demonstrate edge cases and error handling."""
    
    print(f"\n{'='*60}")
    print("EDGE CASES AND ERROR HANDLING DEMO")
    print(f"{'='*60}")
    
    profile_manager = UserProfileManager()
    assessor = EligibilityAssessor(profile_manager)
    
    # Create a scheme with complex eligibility criteria
    complex_scheme = GovernmentScheme(
        scheme_id="complex-001",
        name="Complex Eligibility Scheme",
        department="Test Department",
        category=SchemeCategory.SOCIAL_SECURITY,
        description="Scheme with complex eligibility rules",
        eligibility_criteria=EligibilityCriteria(
            age_min=25,
            age_max=55,
            income_limit=300000,
            gender="female",
            caste_category=["sc", "st"],
            location_type="rural",
            marital_status="married",
            family_size=3,
            disability_status=False
        ),
        application_process=ApplicationProcess(
            required_documents=[
                "Identity Proof",
                "Age Proof", 
                "Income Certificate",
                "Caste Certificate",
                "Address Proof",
                "Marriage Certificate",
                "Family Composition Certificate"
            ],
            processing_time_days=90
        ),
        metadata=SchemeMetadata(
            data_source=DataSource.MANUAL_ENTRY,
            success_rate=0.45  # Lower success rate
        )
    )
    
    # Create user with incomplete profile
    await profile_manager.create_profile(
        user_id="incomplete_001",
        location=LocationInfo(
            state="Unknown",
            district="Unknown",
            location_type="unknown"
        ),
        demographics=DemographicInfo(
            age=None,  # Missing age
            gender=None,  # Missing gender
            caste_category=None  # Missing caste
        ),
        economic=EconomicInfo(
            income=None,  # Missing income
            employment_status=None
        )
    )
    
    print("\n1. Assessment with Incomplete Profile:")
    print("-" * 40)
    
    try:
        assessment = await assessor.assess_eligibility("incomplete_001", complex_scheme)
        print(f"Status: {assessment.overall_status.value}")
        print(f"Eligibility Score: {assessment.eligibility_score:.2f}")
        print(f"Data Completeness: {assessment.data_completeness:.2%}")
        print(f"Missing Data Rules: {len(assessment.missing_data_rules)}")
        print(f"Confidence Level: {assessment.confidence_level:.2%}")
        
        if assessment.recommendations:
            print("Recommendations:")
            for rec in assessment.recommendations:
                print(f"  • {rec}")
                
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Test with non-existent user
    print("\n2. Assessment with Non-existent User:")
    print("-" * 40)
    
    try:
        assessment = await assessor.assess_eligibility("nonexistent_user", complex_scheme)
        print("This should not print")
    except Exception as e:
        print(f"Expected Error: {str(e)}")
    
    print("\n3. Document Analysis for Various Document Types:")
    print("-" * 50)
    
    sample_documents = [
        "Unknown Document Type",
        "Aadhaar Card",
        "Income Certificate", 
        "Education Qualification",
        "Bank Passbook",
        "Disability Certificate"
    ]
    
    for doc_name in sample_documents:
        doc_req = assessor._analyze_document_requirement(doc_name, {}, complex_scheme)
        print(f"{doc_name}:")
        print(f"  Type: {doc_req.document_type}")
        print(f"  Status: {doc_req.status.value}")
        print(f"  Mandatory: {doc_req.mandatory}")
        if doc_req.alternatives:
            print(f"  Alternatives: {', '.join(doc_req.alternatives[:2])}")
        print()


if __name__ == "__main__":
    print("Starting Eligibility Assessment System Demo...")
    
    # Run the main demonstration
    asyncio.run(demonstrate_eligibility_assessment())
    
    # Run edge cases demonstration
    asyncio.run(demonstrate_edge_cases())
    
    print("\n" + "="*80)
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("="*80)
    print("\nKey Features Demonstrated:")
    print("✅ Rule-based eligibility checking")
    print("✅ Document requirement analysis")
    print("✅ Success probability estimation")
    print("✅ Comprehensive assessment reporting")
    print("✅ Document checklist generation")
    print("✅ Timeline estimation")
    print("✅ Error handling and edge cases")
    print("\nThe eligibility assessment system is ready for integration!")