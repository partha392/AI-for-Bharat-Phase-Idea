#!/usr/bin/env python3
"""
AWS Polly Text-to-Speech Demo for Bharat Voice Assistant

This script demonstrates the text-to-speech functionality using AWS Polly
with Indian voices, regional accents, and bandwidth optimization.

Usage:
    python examples/polly_tts_demo.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bharat_voice_assistant.voice.text_to_speech import (
    TextToSpeechSynthesizer,
    SynthesisConfig,
    AudioFormat,
    SpeechRate,
    VoiceEngine
)
from bharat_voice_assistant.core.logging import get_logger

logger = get_logger(__name__)


async def demo_basic_synthesis():
    """Demonstrate basic text-to-speech synthesis."""
    print("\n=== Basic Text-to-Speech Synthesis Demo ===")
    
    try:
        synthesizer = TextToSpeechSynthesizer()
        
        # Test texts in different languages
        test_texts = {
            "hi": "नमस्ते! मैं भारत वॉयस असिस्टेंट हूँ। मैं आपकी सरकारी योजनाओं में मदद कर सकता हूँ।",
            "en": "Hello! I am the Bharat Voice Assistant. I can help you with government schemes.",
            "ta": "வணக்கம்! நான் பாரத் குரல் உதவியாளர். அரசு திட்டங்களில் உங்களுக்கு உதவ முடியும்.",
            "te": "నమస్కారం! నేను భారత్ వాయిస్ అసిస్టెంట్. ప్రభుత్వ పథకాలలో మీకు సహాయం చేయగలను.",
            "bn": "নমস্কার! আমি ভারত ভয়েস অ্যাসিস্ট্যান্ট। সরকারি প্রকল্পে আপনাকে সাহায্য করতে পারি।"
        }
        
        for lang, text in test_texts.items():
            print(f"\nSynthesizing {lang.upper()} text...")
            print(f"Text: {text}")
            
            # Create synthesis configuration
            config = synthesizer.create_synthesis_config(
                language=lang,
                connection_speed="good",
                prefer_neural=True
            )
            
            # Synthesize speech
            result = await synthesizer.synthesize_speech(text, config)
            
            print(f"✓ Synthesis successful!")
            print(f"  Voice: {result.voice_id}")
            print(f"  Language: {result.language}")
            print(f"  Duration: {result.duration_ms}ms")
            print(f"  Audio size: {len(result.audio_data)} bytes")
            print(f"  Processing time: {result.processing_time_ms}ms")
            
            # Save audio file
            output_file = f"output_{lang}_demo.mp3"
            with open(output_file, "wb") as f:
                f.write(result.audio_data)
            print(f"  Saved to: {output_file}")
            
    except Exception as e:
        print(f"❌ Error in basic synthesis demo: {e}")
        logger.error(f"Basic synthesis demo failed: {e}")


async def demo_bandwidth_optimization():
    """Demonstrate bandwidth optimization features."""
    print("\n=== Bandwidth Optimization Demo ===")
    
    try:
        synthesizer = TextToSpeechSynthesizer()
        
        text = "यह बैंडविड्थ ऑप्टिमाइज़ेशन का परीक्षण है। विभिन्न कनेक्शन गुणवत्ता के लिए ऑडियो गुणवत्ता समायोजित की जाती है।"
        
        connection_speeds = ["excellent", "good", "medium", "slow", "poor", "very_poor"]
        
        for speed in connection_speeds:
            print(f"\nTesting {speed} connection...")
            
            # Create optimized configuration
            config = synthesizer.create_synthesis_config("hi", speed)
            
            # Synthesize with optimization
            result = await synthesizer.synthesize_speech(text, config, speed)
            
            print(f"  Connection: {speed}")
            print(f"  Audio format: {result.audio_format}")
            print(f"  Sample rate: {config.sample_rate}")
            print(f"  Compression quality: {config.compression_quality}")
            print(f"  Audio size: {len(result.audio_data)} bytes")
            print(f"  Compression ratio: {result.compression_ratio:.2f}x" if result.compression_ratio else "No compression")
            
            # Save optimized audio
            output_file = f"output_hi_{speed}_optimized.mp3"
            with open(output_file, "wb") as f:
                f.write(result.audio_data)
            print(f"  Saved to: {output_file}")
            
    except Exception as e:
        print(f"❌ Error in bandwidth optimization demo: {e}")
        logger.error(f"Bandwidth optimization demo failed: {e}")


async def demo_voice_comparison():
    """Demonstrate different Indian voices and accents."""
    print("\n=== Indian Voices and Accents Demo ===")
    
    try:
        synthesizer = TextToSpeechSynthesizer()
        
        # Get available voices
        all_voices = synthesizer.get_available_voices()
        
        print(f"Available voices: {len(all_voices)}")
        for voice in all_voices[:5]:  # Show first 5 voices
            print(f"  {voice.voice_id}: {voice.language_name} ({voice.gender.value}) - {voice.regional_accent}")
        
        # Test different voices for Hindi
        hindi_text = "मैं भारत की विविधता में एकता का प्रतिनिधित्व करता हूँ।"
        
        hindi_voices = synthesizer.get_available_voices("hi")
        for voice in hindi_voices:
            print(f"\nTesting voice: {voice.voice_id}")
            
            config = SynthesisConfig(
                voice_id=voice.voice_id,
                language_code=voice.language_code,
                audio_format=AudioFormat.MP3,
                engine=VoiceEngine.NEURAL if voice.supports_neural else VoiceEngine.STANDARD
            )
            
            result = await synthesizer.synthesize_speech(hindi_text, config)
            
            print(f"  ✓ Voice: {voice.voice_id}")
            print(f"    Engine: {config.engine.value}")
            print(f"    Accent: {voice.regional_accent}")
            print(f"    Duration: {result.duration_ms}ms")
            
            # Save voice sample
            output_file = f"output_voice_{voice.voice_id.lower()}.mp3"
            with open(output_file, "wb") as f:
                f.write(result.audio_data)
            print(f"    Saved to: {output_file}")
            
    except Exception as e:
        print(f"❌ Error in voice comparison demo: {e}")
        logger.error(f"Voice comparison demo failed: {e}")


async def demo_ssml_features():
    """Demonstrate SSML (Speech Synthesis Markup Language) features."""
    print("\n=== SSML Features Demo ===")
    
    try:
        synthesizer = TextToSpeechSynthesizer()
        
        # Test different speech rates
        base_text = "यह भाषण दर का परीक्षण है।"
        speech_rates = [SpeechRate.X_SLOW, SpeechRate.SLOW, SpeechRate.MEDIUM, SpeechRate.FAST, SpeechRate.X_FAST]
        
        for rate in speech_rates:
            print(f"\nTesting speech rate: {rate.value}")
            
            config = SynthesisConfig(
                voice_id="Aditi",
                language_code="hi-IN",
                speech_rate=rate,
                enable_ssml=True
            )
            
            result = await synthesizer.synthesize_speech(base_text, config)
            
            print(f"  Rate: {rate.value}")
            print(f"  Duration: {result.duration_ms}ms")
            
            # Save rate sample
            output_file = f"output_rate_{rate.value}.mp3"
            with open(output_file, "wb") as f:
                f.write(result.audio_data)
            print(f"  Saved to: {output_file}")
        
        # Test with government-specific terms
        govt_text = "सरकार की नई योजना के लिए आवेदन करें। शिकायत दर्ज करने के लिए हेल्पलाइन पर कॉल करें।"
        
        config = SynthesisConfig(
            voice_id="Aditi",
            language_code="hi-IN",
            enable_ssml=True
        )
        
        result = await synthesizer.synthesize_speech(govt_text, config)
        
        print(f"\nGovernment terms synthesis:")
        print(f"  Text: {govt_text}")
        print(f"  Duration: {result.duration_ms}ms")
        
        with open("output_govt_terms.mp3", "wb") as f:
            f.write(result.audio_data)
        print(f"  Saved to: output_govt_terms.mp3")
        
    except Exception as e:
        print(f"❌ Error in SSML features demo: {e}")
        logger.error(f"SSML features demo failed: {e}")


async def demo_voice_testing():
    """Demonstrate voice testing functionality."""
    print("\n=== Voice Testing Demo ===")
    
    try:
        synthesizer = TextToSpeechSynthesizer()
        
        # Test different voices
        test_voices = [
            ("Aditi", "hi-IN"),
            ("Raveena", "en-IN"),
            ("Kajal", "hi-IN"),
            ("Aria", "en-IN")
        ]
        
        for voice_id, language_code in test_voices:
            print(f"\nTesting voice: {voice_id} ({language_code})")
            
            success = await synthesizer.test_voice_synthesis(voice_id, language_code)
            
            if success:
                print(f"  ✓ Voice {voice_id} test passed")
            else:
                print(f"  ❌ Voice {voice_id} test failed")
        
        # Test all available voices
        print(f"\nTesting all available voices...")
        all_voices = synthesizer.get_available_voices()
        
        passed = 0
        failed = 0
        
        for voice in all_voices[:3]:  # Test first 3 to avoid too many API calls
            success = await synthesizer.test_voice_synthesis(voice.voice_id, voice.language_code)
            if success:
                passed += 1
            else:
                failed += 1
        
        print(f"Voice testing results: {passed} passed, {failed} failed")
        
    except Exception as e:
        print(f"❌ Error in voice testing demo: {e}")
        logger.error(f"Voice testing demo failed: {e}")


async def main():
    """Run all demo functions."""
    print("🎤 Bharat Voice Assistant - AWS Polly TTS Demo")
    print("=" * 50)
    
    # Check if AWS credentials are available
    try:
        from bharat_voice_assistant.core.aws_client import aws_clients
        aws_clients.polly.describe_voices(LanguageCode='hi-IN', MaxResults=1)
        print("✓ AWS Polly connectivity verified")
    except Exception as e:
        print(f"❌ AWS Polly connectivity failed: {e}")
        print("Please ensure AWS credentials are configured properly.")
        return
    
    # Create output directory
    os.makedirs("tts_demo_output", exist_ok=True)
    os.chdir("tts_demo_output")
    
    try:
        # Run all demos
        await demo_basic_synthesis()
        await demo_bandwidth_optimization()
        await demo_voice_comparison()
        await demo_ssml_features()
        await demo_voice_testing()
        
        print("\n🎉 All demos completed successfully!")
        print(f"Audio files saved in: {os.getcwd()}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logger.error(f"Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())