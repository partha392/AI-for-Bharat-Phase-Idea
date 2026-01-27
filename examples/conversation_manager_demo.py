#!/usr/bin/env python3
"""
Demo script for the enhanced conversation management system.

This script demonstrates the cultural adaptation, error recovery, and 
sophisticated flow management capabilities of the Bharat Voice Assistant's
conversation management system.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bharat_voice_assistant.language.language_processor import LanguageProcessor
from bharat_voice_assistant.language.intent_classifier import ServiceIntent
import uuid


def print_separator():
    """Print a visual separator."""
    print("\n" + "="*80 + "\n")


def print_conversation_result(result, turn_number):
    """Print the conversation result in a formatted way."""
    print(f"Turn {turn_number}:")
    print(f"  Intent: {result.intent.value}")
    print(f"  Language: {result.language}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Cultural Context: {result.metadata.get('cultural_context', 'N/A')}")
    print(f"  State: {result.next_state.value}")
    print(f"  Error Recovery: {result.metadata.get('error_recovery', False)}")
    print(f"  Requires Followup: {result.metadata.get('requires_followup', False)}")
    print(f"  Response: {result.response_text}")
    
    if result.entities:
        print(f"  Entities: {[(e.type.value, e.value) for e in result.entities]}")
    
    print()


def demo_elderly_user_scheme_discovery():
    """Demo conversation with elderly user for scheme discovery."""
    print("🧓 DEMO: Elderly User Scheme Discovery (Hindi)")
    print("Demonstrating respectful cultural adaptation for elderly users")
    print_separator()
    
    processor = LanguageProcessor()
    session_id = str(uuid.uuid4())
    
    # Elderly user asking about pension in Hindi
    conversations = [
        ("मैं 75 साल का हूं और पेंशन योजना के बारे में जानना चाहता हूं", "hi"),
        ("मुझे कौन से दस्तावेज चाहिए?", "hi"),
        ("क्या मैं ऑनलाइन आवेदन कर सकता हूं?", "hi")
    ]
    
    for i, (text, lang) in enumerate(conversations, 1):
        print(f"User: {text}")
        result = processor.process_input(text, session_id, language=lang)
        print_conversation_result(result, i)


def demo_grievance_filing_with_error_recovery():
    """Demo grievance filing with error recovery."""
    print("😔 DEMO: Grievance Filing with Error Recovery (English)")
    print("Demonstrating empathetic responses and error recovery")
    print_separator()
    
    processor = LanguageProcessor()
    session_id = str(uuid.uuid4())
    
    # User filing grievance with some unclear inputs
    conversations = [
        ("I have a problem", "en"),  # Vague input - should trigger error recovery
        ("My pension payment is delayed for 3 months", "en"),  # Clear grievance
        ("My phone number is 9876543210", "en"),  # Providing contact info
        ("When will this be resolved?", "en")  # Follow-up question
    ]
    
    for i, (text, lang) in enumerate(conversations, 1):
        print(f"User: {text}")
        result = processor.process_input(text, session_id, language=lang)
        print_conversation_result(result, i)


def demo_status_tracking_flow():
    """Demo status tracking conversation flow."""
    print("📋 DEMO: Status Tracking Flow (English)")
    print("Demonstrating supportive responses for status inquiries")
    print_separator()
    
    processor = LanguageProcessor()
    session_id = str(uuid.uuid4())
    
    # User checking application status
    conversations = [
        ("I want to check my application status", "en"),
        ("My reference number is APP123456", "en"),
        ("How long will it take for approval?", "en")
    ]
    
    for i, (text, lang) in enumerate(conversations, 1):
        print(f"User: {text}")
        result = processor.process_input(text, session_id, language=lang)
        print_conversation_result(result, i)


def demo_multilingual_conversation():
    """Demo multilingual conversation with language switching."""
    print("🌍 DEMO: Multilingual Conversation (Hindi to English)")
    print("Demonstrating language consistency and cultural adaptation")
    print_separator()
    
    processor = LanguageProcessor()
    session_id = str(uuid.uuid4())
    
    # Mixed language conversation
    conversations = [
        ("नमस्ते, मुझे सरकारी योजना चाहिए", "hi"),  # Start in Hindi
        ("What documents do I need?", "en"),  # Switch to English
        ("मेरी उम्र 45 साल है", "hi"),  # Back to Hindi
        ("Thank you for your help", "en")  # End in English
    ]
    
    for i, (text, lang) in enumerate(conversations, 1):
        print(f"User: {text}")
        # Don't specify language to test auto-detection
        result = processor.process_input(text, session_id)
        print_conversation_result(result, i)


def demo_conversation_context_persistence():
    """Demo conversation context persistence."""
    print("💾 DEMO: Context Persistence")
    print("Demonstrating how context is maintained across conversation turns")
    print_separator()
    
    processor = LanguageProcessor()
    session_id = str(uuid.uuid4())
    
    # First, establish context
    print("User: I am 65 years old and need help with pension schemes")
    result1 = processor.process_input(
        "I am 65 years old and need help with pension schemes", 
        session_id, 
        language='en'
    )
    print_conversation_result(result1, 1)
    
    # Show context information
    context = processor.get_conversation_context(session_id)
    print("📊 Context Information:")
    print(f"  Session ID: {context.session_id}")
    print(f"  Language: {context.language}")
    print(f"  Current State: {context.current_state.value}")
    print(f"  Turn Count: {len(context.turns)}")
    print(f"  Persistent Data: {context.persistent_data}")
    print(f"  Temporary Data: {context.temporary_data}")
    print()
    
    # Continue conversation - context should be maintained
    print("User: What are the eligibility criteria?")
    result2 = processor.process_input("What are the eligibility criteria?", session_id)
    print_conversation_result(result2, 2)
    
    # Show updated context
    updated_context = processor.get_conversation_context(session_id)
    print("📊 Updated Context Information:")
    print(f"  Turn Count: {len(updated_context.turns)}")
    print(f"  Last Updated: {updated_context.last_updated}")
    print(f"  Time Since Update: {updated_context.last_updated}")


def main():
    """Run all conversation management demos."""
    print("🎯 BHARAT VOICE ASSISTANT - CONVERSATION MANAGEMENT DEMO")
    print("Showcasing cultural adaptation, error recovery, and flow management")
    print_separator()
    
    try:
        # Run all demos
        demo_elderly_user_scheme_discovery()
        demo_grievance_filing_with_error_recovery()
        demo_status_tracking_flow()
        demo_multilingual_conversation()
        demo_conversation_context_persistence()
        
        print("✅ All demos completed successfully!")
        print("\nKey Features Demonstrated:")
        print("• Cultural adaptation based on user age and context")
        print("• Error recovery for unclear or incomplete inputs")
        print("• Conversation flow management across different intents")
        print("• Multilingual support with language consistency")
        print("• Context persistence across conversation turns")
        print("• Appropriate honorifics and politeness levels")
        print("• Empathetic responses for grievance scenarios")
        print("• Supportive responses for status inquiries")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()