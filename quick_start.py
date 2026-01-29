#!/usr/bin/env python3
"""
BHARAT VOICE ASSISTANT - INSTANT DEMO
Get running in 30 seconds
"""

import subprocess
import sys
import os
import time

def check_python():
    """Ensure Python 3.11+"""
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ required. Current:", sys.version)
        return False
    print("✅ Python version OK")
    return True

def install_deps():
    """Install minimal dependencies"""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "streamlit", "plotly", "pandas", "fastapi", "uvicorn"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ Dependencies installed")
        return True
    except:
        print("❌ Failed to install dependencies")
        return False

def launch_demo():
    """Launch the demo"""
    print("🚀 Launching Bharat Voice Assistant...")
    print("🌐 Opening browser at: http://localhost:8501")
    print("🛑 Press Ctrl+C to stop")
    
    try:
        gui_path = "bharat_voice_assistant/gui/streamlit_app.py"
        subprocess.run([
            "streamlit", "run", gui_path,
            "--server.port", "8501",
            "--server.headless", "true"
        ])
    except KeyboardInterrupt:
        print("\n👋 Demo stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Try: python demos/run_gui.py")

def main():
    print("🇮🇳 BHARAT VOICE ASSISTANT - QUICK START")
    print("=" * 45)
    
    if not check_python():
        sys.exit(1)
    
    if not install_deps():
        sys.exit(1)
    
    print("\n🎯 DEMO READY!")
    print("Try saying: 'मुझे कृषि योजनाओं के बारे में बताएं'")
    print("(Tell me about agriculture schemes)")
    
    time.sleep(2)
    launch_demo()

if __name__ == "__main__":
    main()