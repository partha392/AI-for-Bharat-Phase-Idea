#!/usr/bin/env python3
"""
Privacy Manager Demo

This script demonstrates the privacy management capabilities of the Bharat Voice Assistant,
including voice data encryption, consent management, and automatic data deletion.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bharat_voice_assistant.privacy import PrivacyManager
from bharat_voice_assistant.privacy.models import ConsentType, DataType


async def main():
    """Demonstrate privacy manager functionality."""
    print("🔒 Bharat Voice Assistant - Privacy Manager Demo")
    print("=" * 60)
    
    # Initialize privacy manager
    privacy_manager = PrivacyManager()
    
    # Start background tasks
    await privacy_manager.start_background_tasks()
    
    try:
        # Demo user
        user_id = "demo_user_123"
        
        print(f"\n1. 🎤 Voice Data Encryption Demo")
        print("-" * 40)
        
        # Simulate voice data
        voice_data = b"Namaste, main ek government scheme ke baare mein jaanna chahta hun"
        print(f"Original voice data size: {len(voice_data)} bytes")
        
        # Encrypt voice data (automatically collects consent)
        encrypted_data, data_id = privacy_manager.ensure_voice_data_compliance(user_id, voice_data)
        print(f"Encrypted voice data size: {len(encrypted_data)} bytes")
        print(f"Data registration ID: {data_id}")
        
        print(f"\n2. 📋 Consent Management Demo")
        print("-" * 40)
        
        # Check consent status
        consents = privacy_manager.get_user_consents(user_id)
        print(f"Total consents for user: {len(consents)}")
        
        for consent in consents:
            print(f"  - {consent.consent_type.value}: {consent.status.value}")
            print(f"    Purpose: {consent.purpose}")
            print(f"    Granted: {consent.granted_at}")
            if consent.expires_at:
                print(f"    Expires: {consent.expires_at}")
        
        print(f"\n3. 🗑️ Data Retention Demo")
        print("-" * 40)
        
        # Mark voice processing as complete (starts deletion countdown)
        success = privacy_manager.mark_voice_processing_complete(data_id)
        print(f"Voice processing marked complete: {success}")
        
        # Get user data summary
        data_summary = privacy_manager.data_retention_manager.get_user_data_summary(user_id)
        print(f"Total data items for user: {data_summary['total_items']}")
        print(f"Scheduled deletions: {data_summary['scheduled_deletions']}")
        print(f"Data types: {list(data_summary['data_types'].keys())}")
        
        print(f"\n4. 📊 Privacy Summary Demo")
        print("-" * 40)
        
        # Get comprehensive privacy summary
        privacy_summary = privacy_manager.get_user_privacy_summary(user_id)
        print(f"Privacy Summary for {user_id}:")
        print(f"  - Active consents: {privacy_summary['consents']['active']}")
        print(f"  - Total data items: {privacy_summary['data_storage']['total_items']}")
        print(f"  - Can withdraw consent: {privacy_summary['privacy_rights']['can_withdraw_consent']}")
        print(f"  - Can request deletion: {privacy_summary['privacy_rights']['can_request_deletion']}")
        
        print(f"\n5. 🚫 Consent Withdrawal Demo")
        print("-" * 40)
        
        # Withdraw consent
        if consents:
            consent_to_withdraw = consents[0]
            success = privacy_manager.withdraw_user_consent(
                user_id, consent_to_withdraw.consent_id, "User requested withdrawal"
            )
            print(f"Consent withdrawal successful: {success}")
            
            # Check updated consent status
            updated_consents = privacy_manager.get_user_consents(user_id)
            withdrawn_consent = next(
                c for c in updated_consents if c.consent_id == consent_to_withdraw.consent_id
            )
            print(f"Updated consent status: {withdrawn_consent.status.value}")
        
        print(f"\n6. 🗂️ Data Export Demo")
        print("-" * 40)
        
        # Export user data for portability
        export_data = privacy_manager.export_user_data(user_id)
        print(f"Data export generated at: {export_data['exported_at']}")
        print(f"Export includes:")
        print(f"  - Consent data: {len(export_data['consent_data']['consents'])} records")
        print(f"  - Privacy summary: ✓")
        print(f"  - Data retention info: ✓")
        
        print(f"\n7. 🗑️ User Data Deletion Request Demo")
        print("-" * 40)
        
        # Request complete data deletion
        deletion_request = privacy_manager.request_user_data_deletion(
            user_id, reason="User requested account deletion"
        )
        print(f"Deletion request created: {deletion_request.request_id}")
        print(f"Deletion deadline: {deletion_request.get_deadline()}")
        print(f"Status: {deletion_request.status}")
        
        print(f"\n8. 🔍 Compliance Report Demo")
        print("-" * 40)
        
        # Generate compliance report
        compliance_report = privacy_manager.get_compliance_report()
        print(f"Compliance Report Generated: {compliance_report['report_generated_at']}")
        print(f"Configuration valid: {compliance_report['privacy_configuration']['valid']}")
        
        print(f"\nCompliance Features:")
        for feature, enabled in compliance_report['compliance_features'].items():
            status = "✓" if enabled else "✗"
            print(f"  {status} {feature.replace('_', ' ').title()}")
        
        print(f"\nStatistics:")
        stats = compliance_report['statistics']
        print(f"  - Users with consents: {stats['total_users_with_consents']}")
        print(f"  - Total consent records: {stats['total_consent_records']}")
        print(f"  - Data items tracked: {stats['total_data_items_tracked']}")
        print(f"  - Active deletion requests: {stats['active_deletion_requests']}")
        
        print(f"\n9. 🧹 Automatic Cleanup Demo")
        print("-" * 40)
        
        # Process scheduled deletions
        deleted_count = await privacy_manager.data_retention_manager.process_scheduled_deletions()
        print(f"Items processed for deletion: {deleted_count}")
        
        # Clean up expired consents
        expired_count = privacy_manager.consent_manager.cleanup_expired_consents()
        print(f"Expired consents cleaned up: {expired_count}")
        
        print(f"\n✅ Privacy Manager Demo Complete!")
        print("=" * 60)
        print("The privacy manager successfully demonstrated:")
        print("  ✓ Voice data encryption with AES-256-GCM")
        print("  ✓ Explicit consent collection and management")
        print("  ✓ Automatic deletion of voice recordings after processing")
        print("  ✓ User data deletion within 30 days of request")
        print("  ✓ Comprehensive privacy compliance reporting")
        print("  ✓ Data export for portability")
        print("  ✓ Consent withdrawal capabilities")
        print("  ✓ Automatic cleanup of expired data and consents")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Stop background tasks
        await privacy_manager.stop_background_tasks()


if __name__ == "__main__":
    # Set environment for demo
    os.environ["ENVIRONMENT"] = "development"
    
    # Run the demo
    asyncio.run(main())