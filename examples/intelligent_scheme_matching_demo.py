#!/usr/bin/env python3
"""
Demo script for intelligent scheme matching algorithm.

This script demonstrates the multi-criteria matching based on demographics and location,
relevance scoring with machine learning models, and personalization based on user
interaction history.

Requirements: 2.1, 2.4, 2.5
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from bharat_voice_assistant.schemes.scheme_matcher import (
    IntelligentSchemeMatcher, UserProfile, MatchScore
)
from bharat_voice_assistant.schemes.user_profile import (
    UserProfileManager, InteractionRecord, LocationInfo, DemographicInfo, EconomicInfo
)
from bharat_voice_assistant.schemes.models import (
    GovernmentScheme, SchemeCategory, EligibilityCriteria, SchemeBenefits, ApplicationProcess
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_schemes() -> List[GovernmentScheme]:
    """Create sample government schemes for demonstration."""
    schemes = []
    
    # 1. Housing Scheme - PM Awas Yojana
    housing_scheme = GovernmentScheme(
        scheme_id="pmay-g-001",
        name="Pradhan Mantri Awas Yojana - Gramin",
        name_hi="प्रधान मंत्री आवास योजना - ग्रामीण",
        department="Ministry of Rural Development",
        category=SchemeCategory.HOUSING,
        description="Financial assistance for construction of pucca house in rural areas",
        description_hi="ग्रामीण क्षेत्रों में पक्का मकान बनाने के लिए वित्तीय सहायता",
        eligibility_criteria=EligibilityCriteria(
            income_limit=200000,
            location_type="rural",
            housing_status="homeless_or_inadequate"
        ),
        benefits=SchemeBenefits(
            financial_assistance=120000,
            description="Financial assistance up to Rs. 1.2 lakh for construction"
        ),
        application_process=ApplicationProcess(
            steps=[
                "Visit Common Service Center",
                "Fill application form with Aadhaar",
                "Submit required documents",
                "Wait for verification",
                "Receive approval and funds"
            ],
            required_documents=[
                "Aadhaar Card",
                "Income Certificate",
                "Bank Account Details",
                "Land Documents"
            ],
            processing_time_days=45,
            application_mode=["online", "offline"]
        ),
        target_states=["Maharashtra", "Gujarat", "Rajasthan"],
        target_districts=["Mumbai", "Pune", "Nashik"]
    )
    schemes.append(housing_scheme)
    
    # 2. Agriculture Scheme - PM-KISAN
    agriculture_scheme = GovernmentScheme(
        scheme_id="pmkisan-001",
        name="PM-KISAN",
        name_hi="पीएम-किसान",
        department="Ministry of Agriculture",
        category=SchemeCategory.AGRICULTURE,
        description="Annual financial assistance for small and marginal farmers",
        description_hi="छोटे और सीमांत किसानों के लिए वार्षिक वित्तीय सहायता",
        eligibility_criteria=EligibilityCriteria(
            land_ownership="small_marginal",
            employment_status="farmer"
        ),
        benefits=SchemeBenefits(
            financial_assistance=6000,
            description="Rs. 6000 per year in three installments"
        ),
        application_process=ApplicationProcess(
            steps=[
                "Register on PM-KISAN portal",
                "Fill farmer details",
                "Upload land documents",
                "Submit application",
                "Receive payments in bank account"
            ],
            required_documents=[
                "Aadhaar Card",
                "Bank Account Details",
                "Land Ownership Documents"
            ],
            processing_time_days=30,
            application_mode=["online"]
        ),
        target_states=["Maharashtra", "Punjab", "Haryana"]
    )
    schemes.append(agriculture_scheme)
    
    # 3. Education Scheme - Scholarship
    education_scheme = GovernmentScheme(
        scheme_id="edu-scholarship-001",
        name="Merit Scholarship Scheme",
        name_hi="मेधा छात्रवृत्ति योजना",
        department="Ministry of Education",
        category=SchemeCategory.EDUCATION,
        description="Educational scholarship for meritorious students",
        description_hi="मेधावी छात्रों के लिए शैक्षिक छात्रवृत्ति",
        eligibility_criteria=EligibilityCriteria(
            age_min=5,
            age_max=25,
            income_limit=300000,
            education_level="secondary"
        ),
        benefits=SchemeBenefits(
            financial_assistance=25000,
            description="Annual scholarship of Rs. 25,000"
        ),
        application_process=ApplicationProcess(
            steps=[
                "Apply through education portal",
                "Submit academic certificates",
                "Income verification",
                "Merit list preparation",
                "Scholarship disbursement"
            ],
            required_documents=[
                "Academic Certificates",
                "Income Certificate",
                "Aadhaar Card",
                "Bank Account Details"
            ],
            processing_time_days=60,
            application_mode=["online"]
        ),
        target_states=["Maharashtra", "Karnataka", "Tamil Nadu"]
    )
    schemes.append(education_scheme)
    
    # 4. Women Empowerment Scheme
    women_scheme = GovernmentScheme(
        scheme_id="women-emp-001",
        name="Mahila Shakti Yojana",
        name_hi="महिला शक्ति योजना",
        department="Ministry of Women and Child Development",
        category=SchemeCategory.WOMEN_EMPOWERMENT,
        description="Skill development and employment for women",
        description_hi="महिलाओं के लिए कौशल विकास और रोजगार",
        eligibility_criteria=EligibilityCriteria(
            gender="female",
            age_min=18,
            age_max=45,
            employment_status="unemployed"
        ),
        benefits=SchemeBenefits(
            financial_assistance=50000,
            training_provided=True,
            description="Training and financial support for self-employment"
        ),
        application_process=ApplicationProcess(
            steps=[
                "Register at Anganwadi Center",
                "Attend counseling session",
                "Choose skill training",
                "Complete training program",
                "Receive financial assistance"
            ],
            required_documents=[
                "Aadhaar Card",
                "Age Proof",
                "Income Certificate",
                "Bank Account Details"
            ],
            processing_time_days=90,
            application_mode=["offline"]
        ),
        target_states=["Maharashtra", "Uttar Pradesh", "Bihar"]
    )
    schemes.append(women_scheme)
    
    # 5. Senior Citizen Scheme
    senior_scheme = GovernmentScheme(
        scheme_id="senior-pension-001",
        name="Indira Gandhi National Old Age Pension Scheme",
        name_hi="इंदिरा गांधी राष्ट्रीय वृद्धावस्था पेंशन योजना",
        department="Ministry of Rural Development",
        category=SchemeCategory.SENIOR_CITIZEN,
        description="Monthly pension for senior citizens below poverty line",
        description_hi="गरीबी रेखा से नीचे के वरिष्ठ नागरिकों के लिए मासिक पेंशन",
        eligibility_criteria=EligibilityCriteria(
            age_min=60,
            income_limit=100000,
            caste_category=["general", "obc", "sc", "st"]
        ),
        benefits=SchemeBenefits(
            financial_assistance=2400,  # Annual (200 per month)
            description="Monthly pension of Rs. 200"
        ),
        application_process=ApplicationProcess(
            steps=[
                "Apply at Block/District office",
                "Submit required documents",
                "Verification by officials",
                "Approval and pension start",
                "Monthly pension in bank account"
            ],
            required_documents=[
                "Aadhaar Card",
                "Age Certificate",
                "Income Certificate",
                "BPL Card",
                "Bank Account Details"
            ],
            processing_time_days=30,
            application_mode=["offline"]
        ),
        target_states=["Maharashtra", "Madhya Pradesh", "Chhattisgarh"]
    )
    schemes.append(senior_scheme)
    
    return schemes


def create_sample_user_profiles() -> List[UserProfile]:
    """Create sample user profiles for demonstration."""
    profiles = []
    
    # 1. Rural farmer profile
    farmer_profile = UserProfile(
        user_id="farmer-001",
        age=45,
        gender="male",
        income=80000,
        location={
            "state": "Maharashtra",
            "district": "Pune",
            "type": "rural"
        },
        education_level="primary",
        employment_status="farmer",
        caste_category="general",
        disability_status=False,
        marital_status="married",
        family_size=5,
        land_ownership="small_marginal",
        housing_status="inadequate",
        preferred_categories=[SchemeCategory.AGRICULTURE, SchemeCategory.HOUSING],
        interaction_history=[
            {
                "scheme_id": "pmkisan-001",
                "category": "agriculture",
                "action": "applied",
                "outcome": "approved",
                "timestamp": (datetime.now() - timedelta(days=30)).isoformat(),
                "engagement_time": 300
            }
        ]
    )
    profiles.append(farmer_profile)
    
    # 2. Urban young woman profile
    woman_profile = UserProfile(
        user_id="woman-001",
        age=28,
        gender="female",
        income=150000,
        location={
            "state": "Maharashtra",
            "district": "Mumbai",
            "type": "urban"
        },
        education_level="graduate",
        employment_status="unemployed",
        caste_category="general",
        disability_status=False,
        marital_status="married",
        family_size=3,
        land_ownership="landless",
        housing_status="rented",
        preferred_categories=[SchemeCategory.WOMEN_EMPOWERMENT, SchemeCategory.EDUCATION],
        interaction_history=[
            {
                "scheme_id": "women-emp-001",
                "category": "women_empowerment",
                "action": "viewed",
                "timestamp": (datetime.now() - timedelta(days=5)).isoformat(),
                "engagement_time": 180
            }
        ]
    )
    profiles.append(woman_profile)
    
    # 3. Senior citizen profile
    senior_profile = UserProfile(
        user_id="senior-001",
        age=65,
        gender="male",
        income=50000,
        location={
            "state": "Maharashtra",
            "district": "Nashik",
            "type": "rural"
        },
        education_level="primary",
        employment_status="retired",
        caste_category="sc",
        disability_status=False,
        marital_status="widowed",
        family_size=2,
        land_ownership="landless",
        housing_status="owned",
        preferred_categories=[SchemeCategory.SENIOR_CITIZEN, SchemeCategory.HEALTH],
        interaction_history=[]
    )
    profiles.append(senior_profile)
    
    # 4. Student profile
    student_profile = UserProfile(
        user_id="student-001",
        age=20,
        gender="female",
        income=200000,  # Family income
        location={
            "state": "Maharashtra",
            "district": "Mumbai",
            "type": "urban"
        },
        education_level="higher_secondary",
        employment_status="student",
        caste_category="obc",
        disability_status=False,
        marital_status="single",
        family_size=4,
        land_ownership="landless",
        housing_status="rented",
        preferred_categories=[SchemeCategory.EDUCATION],
        interaction_history=[
            {
                "scheme_id": "edu-scholarship-001",
                "category": "education",
                "action": "viewed",
                "timestamp": (datetime.now() - timedelta(days=10)).isoformat(),
                "engagement_time": 240
            }
        ]
    )
    profiles.append(student_profile)
    
    return profiles


async def demonstrate_scheme_matching():
    """Demonstrate the intelligent scheme matching algorithm."""
    print("🚀 Intelligent Scheme Matching Algorithm Demo")
    print("=" * 60)
    
    # Initialize the matcher
    matcher = IntelligentSchemeMatcher()
    
    # Create sample data
    schemes = create_sample_schemes()
    user_profiles = create_sample_user_profiles()
    
    print(f"📊 Created {len(schemes)} sample schemes and {len(user_profiles)} user profiles")
    print()
    
    # Demonstrate matching for each user profile
    for i, user_profile in enumerate(user_profiles, 1):
        print(f"👤 User Profile {i}: {user_profile.user_id}")
        print(f"   Age: {user_profile.age}, Gender: {user_profile.gender}")
        print(f"   Income: ₹{user_profile.income:,}, Location: {user_profile.location.get('state')} ({user_profile.location.get('type')})")
        print(f"   Employment: {user_profile.employment_status}, Education: {user_profile.education_level}")
        print(f"   Preferred Categories: {[cat.value for cat in user_profile.preferred_categories]}")
        print()
        
        # Perform intelligent matching
        try:
            match_results = await matcher.match_schemes(
                user_profile=user_profile,
                available_schemes=schemes,
                max_results=3
            )
            
            print(f"🎯 Top {len(match_results)} Scheme Matches:")
            print("-" * 40)
            
            for rank, (scheme, match_score) in enumerate(match_results, 1):
                print(f"{rank}. {scheme.name}")
                print(f"   📈 Overall Score: {match_score.overall_score:.2f}")
                print(f"   ✅ Eligibility Match: {match_score.eligibility_match}")
                print(f"   🎲 Approval Likelihood: {match_score.approval_likelihood:.2f}")
                print(f"   🔍 Confidence: {match_score.confidence:.2f}")
                
                # Show detailed criteria scores
                print("   📊 Criteria Scores:")
                for criteria, score in match_score.criteria_scores.items():
                    print(f"      • {criteria.value.replace('_', ' ').title()}: {score:.2f}")
                
                # Show explanation
                if match_score.explanation:
                    print("   💡 Explanation:")
                    for explanation in match_score.explanation[:2]:  # Show top 2 explanations
                        print(f"      • {explanation}")
                
                # Show estimated benefit
                if scheme.benefits.financial_assistance:
                    print(f"   💰 Estimated Benefit: ₹{scheme.benefits.financial_assistance:,}")
                
                print()
            
        except Exception as e:
            print(f"❌ Error matching schemes for {user_profile.user_id}: {str(e)}")
        
        print("=" * 60)
        print()


async def demonstrate_personalization():
    """Demonstrate personalization based on interaction history."""
    print("🎨 Personalization Demo")
    print("=" * 40)
    
    matcher = IntelligentSchemeMatcher()
    schemes = create_sample_schemes()
    
    # Create two similar profiles - one with interaction history, one without
    base_profile = UserProfile(
        user_id="base-user",
        age=30,
        gender="female",
        income=120000,
        location={"state": "Maharashtra", "district": "Mumbai", "type": "urban"},
        employment_status="unemployed",
        preferred_categories=[SchemeCategory.WOMEN_EMPOWERMENT]
    )
    
    experienced_profile = UserProfile(
        user_id="experienced-user",
        age=30,
        gender="female",
        income=120000,
        location={"state": "Maharashtra", "district": "Mumbai", "type": "urban"},
        employment_status="unemployed",
        preferred_categories=[SchemeCategory.WOMEN_EMPOWERMENT],
        interaction_history=[
            {
                "scheme_id": "women-emp-001",
                "category": "women_empowerment",
                "action": "applied",
                "outcome": "approved",
                "timestamp": (datetime.now() - timedelta(days=15)).isoformat(),
                "engagement_time": 600
            },
            {
                "scheme_id": "edu-scholarship-001",
                "category": "education",
                "action": "viewed",
                "timestamp": (datetime.now() - timedelta(days=7)).isoformat(),
                "engagement_time": 300
            }
        ]
    )
    
    print("Comparing recommendations for similar users:")
    print()
    
    # Match for base user (no history)
    base_results = await matcher.match_schemes(base_profile, schemes, max_results=3)
    print("👤 New User (No History):")
    for rank, (scheme, score) in enumerate(base_results, 1):
        print(f"  {rank}. {scheme.name} - Score: {score.overall_score:.2f}, Boost: {score.personalization_boost:.2f}")
    print()
    
    # Match for experienced user (with history)
    exp_results = await matcher.match_schemes(experienced_profile, schemes, max_results=3)
    print("👤 Experienced User (With History):")
    for rank, (scheme, score) in enumerate(exp_results, 1):
        print(f"  {rank}. {scheme.name} - Score: {score.overall_score:.2f}, Boost: {score.personalization_boost:.2f}")
    print()
    
    print("📈 Personalization Impact:")
    print("  • Users with interaction history get personalized boosts")
    print("  • Schemes in categories with successful applications get higher scores")
    print("  • Recent interactions influence recommendations")


async def main():
    """Main demo function."""
    try:
        await demonstrate_scheme_matching()
        await demonstrate_personalization()
        
        print("✅ Demo completed successfully!")
        print()
        print("🔍 Key Features Demonstrated:")
        print("  • Multi-criteria matching (demographics, location, income)")
        print("  • Eligibility compliance checking")
        print("  • ML-based relevance scoring")
        print("  • Personalization based on interaction history")
        print("  • Approval likelihood estimation")
        print("  • Detailed match explanations")
        
    except Exception as e:
        logger.error(f"Demo failed: {str(e)}")
        print(f"❌ Demo failed: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())