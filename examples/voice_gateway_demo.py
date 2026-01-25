#!/usr/bin/env python3
"""
Voice Interface Gateway Demonstration

This script demonstrates the basic functionality of the Voice Interface Gateway
including WebSocket connections, audio processing, and connection management.
"""

import asyncio
import json
import websockets
from bharat_voice_assistant.voice import VoiceInterfaceGateway


async def demo_client():
    """Demonstrate a simple WebSocket client connecting to the voice gateway."""
    uri = "ws://localhost:8001"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to voice gateway")
            
            # Start a session
            start_session_msg = {
                "type": "start_session",
                "config": {
                    "language": "hi",
                    "audio_format": "raw"
                }
            }
            
            await websocket.send(json.dumps(start_session_msg))
            response = await websocket.recv()
            print(f"Session started: {response}")
            
            # Send client info
            client_info_msg = {
                "type": "client_info",
                "info": {
                    "language": "hi",
                    "device_type": "demo",
                    "app_version": "1.0.0"
                }
            }
            
            await websocket.send(json.dumps(client_info_msg))
            response = await websocket.recv()
            print(f"Client info sent: {response}")
            
            # Send test audio data
            test_audio = b'\x00' * 1000  # 1000 bytes of silence
            audio_msg = {
                "type": "audio_data",
                "data": test_audio.hex(),
                "metadata": {"format": "raw", "sample_rate": 16000}
            }
            
            await websocket.send(json.dumps(audio_msg))
            response = await websocket.recv()
            print(f"Audio processed: {response}")
            
            # Send ping
            ping_msg = {
                "type": "ping",
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await websocket.send(json.dumps(ping_msg))
            response = await websocket.recv()
            print(f"Ping response: {response}")
            
            # End session
            end_session_msg = {"type": "end_session"}
            await websocket.send(json.dumps(end_session_msg))
            response = await websocket.recv()
            print(f"Session ended: {response}")
            
    except Exception as e:
        print(f"Demo client error: {e}")


async def run_demo():
    """Run the voice gateway demonstration."""
    print("Starting Voice Interface Gateway Demo")
    print("=" * 50)
    
    # Create and start the voice gateway
    gateway = VoiceInterfaceGateway(host="localhost", port=8001)
    
    try:
        print("Starting voice gateway...")
        await gateway.start()
        print("Voice gateway started successfully!")
        
        # Wait a moment for the server to be ready
        await asyncio.sleep(1)
        
        # Run demo client
        print("\nRunning demo client...")
        await demo_client()
        
        # Show server stats
        print("\nServer Statistics:")
        stats = gateway.get_server_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Keep server running for a moment
        print("\nKeeping server running for 5 seconds...")
        await asyncio.sleep(5)
        
    except Exception as e:
        print(f"Demo error: {e}")
    finally:
        print("\nStopping voice gateway...")
        await gateway.stop()
        print("Voice gateway stopped.")
    
    print("\nDemo completed!")


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(run_demo())