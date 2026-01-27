"""
Demo script for conversational grievance filing workflow.

This script demonstrates the step-by-step conversational grievance filing
process with voice instructions and real-time validation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from bharat_voice_assistant.grievance.filing_assistant import ConversationalFilingAssistant


def print_response(response, title="Response"):
    """Pretty print response for demo."""
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"{'='*50}")
    
    if isinstance(response, dict):
        for key, value in response.items():
            if key == 'response' and isinstance(value, dict):
                print(f"\n{key.upper()}:")
                for sub_key, sub_value in value.items():
                    print(f"  {sub_key}: {sub_value}")
            elif key in ['workflow_status', 'voice_instructions', 'validation_feedback']:
                print(f"\n{key.upper()}:")
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        print(f"  {sub_key}: {sub_value}")
                else:
                    print(f"  {value}")
            else:
                print(f"{key}: {value}")
    else:
        print(response)
    
    print(f"{'='*50}\n")


async def demo_grievance_filing():
    """Demonstrate the complete grievance filing workflow."""
    print("🎯 Bharat Voice Assistant - Grievance Filing Demo")
    print("This demo shows the conversational grievance filing workflow")
    
    # Initialize the filing assistant
    filing_assistant = ConversationalFilingAssistant()
    session_id = "demo_session_001"
    
    try:
        # Step 1: Start grievance filing session
        print("\n📋 Step 1: Starting Grievance Filing Session")
        result = filing_assistant.start_grievance_filing(session_id, language="hi")
        print_response(result, "Session Started")
        
        # Step 2: Provide problem description
        print("\n📝 Step 2: Describing the Problem")
        user_input = "मेरा राशन कार्ड खो गया है और नया बनवाने के लिए 2 महीने पहले आवेदन दिया था लेकिन अभी तक नहीं मिला है। कार्यालय में कई बार गया हूं लेकिन कोई जवाब नहीं मिला।"
        print(f"User Input: {user_input}")
        
        result = filing_assistant.process_user_input(session_id, user_input)
        print_response(result, "Problem Description Processed")
        
        # Step 3: Provide contact information
        print("\n📞 Step 3: Providing Contact Information")
        user_input = "मेरा फोन नंबर 9876543210 है और ईमेल राम.कुमार@gmail.com है"
        print(f"User Input: {user_input}")
        
        result = filing_assistant.process_user_input(session_id, user_input)
        print_response(result, "Contact Information Processed")
        
        # Step 4: Handle documents (skip for demo)
        print("\n📄 Step 4: Document Information")
        user_input = "मेरे पास आधार कार्ड और पुराने राशन कार्ड की फोटोकॉपी है"
        print(f"User Input: {user_input}")
        
        result = filing_assistant.process_user_input(session_id, user_input)
        print_response(result, "Document Information Processed")
        
        # Step 5: Get session status
        print("\n📊 Step 5: Checking Session Status")
        status = filing_assistant.get_session_status(session_id)
        print_response(status, "Session Status")
        
        # Step 6: Get contextual help
        print("\n❓ Step 6: Getting Contextual Help")
        help_info = filing_assistant.provide_help(session_id)
        print_response(help_info, "Contextual Help")
        
        # Step 7: Demonstrate low confidence handling
        print("\n🔊 Step 7: Low Confidence Speech Recognition")
        result = filing_assistant.process_user_input(
            session_id, 
            "unclear speech input", 
            confidence=0.3
        )
        print_response(result, "Low Confidence Handling")
        
        # Step 8: End session
        print("\n🏁 Step 8: Ending Session")
        result = filing_assistant.end_session(session_id, save_draft=True)
        print_response(result, "Session Ended")
        
        print("\n✅ Demo completed successfully!")
        print("The conversational grievance filing workflow supports:")
        print("  • Step-by-step guidance with voice instructions")
        print("  • Real-time validation and error handling")
        print("  • Cultural adaptation for different languages")
        print("  • Low confidence speech recognition handling")
        print("  • Contextual help and assistance")
        print("  • Session management and draft saving")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


def demo_validation():
    """Demonstrate the validation system."""
    print("\n🔍 Validation System Demo")
    print("="*50)
    
    from bharat_voice_assistant.grievance.validator import GrievanceValidator
    from bharat_voice_assistant.grievance.models import GrievanceRecord, GrievanceDetails, ContactInformation, GrievanceType
    
    validator = GrievanceValidator()
    
    # Test field validation
    print("\n📱 Phone Number Validation:")
    test_phones = ["9876543210", "+919876543210", "123456789", "abcdefghij"]
    for phone in test_phones:
        errors = validator.validate_field('phone_number', phone)
        status = "✅ Valid" if len(errors) == 0 else f"❌ Invalid: {errors[0].message}"
        print(f"  {phone}: {status}")
    
    print("\n📧 Email Validation:")
    test_emails = ["user@example.com", "test.email@domain.co.in", "invalid-email", "test@"]
    for email in test_emails:
        errors = validator.validate_field('email', email)
        status = "✅ Valid" if len(errors) == 0 else f"❌ Invalid: {errors[0].message}"
        print(f"  {email}: {status}")
    
    # Test complete grievance validation
    print("\n📋 Complete Grievance Validation:")
    grievance = GrievanceRecord(
        session_id="validation_demo",
        details=GrievanceDetails(
            problem_description="मेरा पेंशन 3 महीने से नहीं आया है और कार्यालय में कई बार संपर्क किया है।",
            grievance_type=GrievanceType.PENSION_ISSUE
        ),
        contact_info=ContactInformation(
            phone_number="9876543210",
            email="user@example.com"
        )
    )
    
    result = validator.validate_grievance(grievance)
    print(f"  Validation Status: {'✅ Valid' if result.is_valid else '❌ Invalid'}")
    print(f"  Completion: {result.completion_percentage:.1f}%")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Warnings: {len(result.warnings)}")
    print(f"  Missing Fields: {result.missing_required_fields}")


def demo_workflow_manager():
    """Demonstrate the workflow manager."""
    print("\n⚙️ Workflow Manager Demo")
    print("="*50)
    
    from bharat_voice_assistant.grievance.workflow_manager import GrievanceWorkflowManager
    from bharat_voice_assistant.language.intent_classifier import ServiceIntent
    from bharat_voice_assistant.language.entity_extractor import Entity, EntityType
    
    workflow_manager = GrievanceWorkflowManager()
    
    # Start workflow
    print("\n🚀 Starting Workflow:")
    grievance, response = workflow_manager.start_workflow("workflow_demo", "hi")
    print(f"  Initial Step: {grievance.workflow_progress.current_step.value}")
    print(f"  Initial State: {grievance.workflow_progress.current_state.value}")
    print(f"  Response: {response.get('message', '')[:100]}...")
    
    # Process problem description
    print("\n📝 Processing Problem Description:")
    entities = [Entity(EntityType.GOVERNMENT_SERVICE, "pension", 0.9, 0, 7, "hi")]
    grievance, response = workflow_manager.process_user_input(
        grievance, 
        "मेरा पेंशन बंद हो गया है", 
        ServiceIntent.GRIEVANCE_FILING, 
        entities
    )
    print(f"  Current Step: {grievance.workflow_progress.current_step.value}")
    print(f"  Problem Saved: {bool(grievance.details and grievance.details.problem_description)}")
    
    # Get workflow status
    print("\n📊 Workflow Status:")
    status = workflow_manager.get_workflow_status(grievance)
    print(f"  Completion: {status['completion_percentage']:.1f}%")
    print(f"  Completed Steps: {len(status['completed_steps'])}")
    print(f"  Missing Fields: {status['missing_fields']}")


if __name__ == "__main__":
    print("🇮🇳 Bharat Voice Assistant - Grievance Filing System Demo")
    print("="*60)
    
    # Run the main demo
    asyncio.run(demo_grievance_filing())
    
    # Run additional demos
    demo_validation()
    demo_workflow_manager()
    
    print("\n🎉 All demos completed!")
    print("The system is ready for conversational grievance filing with:")
    print("  ✅ Step-by-step voice guidance")
    print("  ✅ Real-time validation")
    print("  ✅ Cultural adaptation")
    print("  ✅ Error handling and recovery")
    print("  ✅ Session management")
    print("  ✅ Multilingual support")