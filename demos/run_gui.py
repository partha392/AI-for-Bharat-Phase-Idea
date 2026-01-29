#!/usr/bin/env python3
"""
Launch script for Bharat Voice Assistant Streamlit GUI
"""

import subprocess
import sys
import os

def install_requirements():
    """Install GUI requirements"""
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements-gui.txt"
        ])
        print("✅ GUI requirements installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing requirements: {e}")
        return False
    return True

def launch_gui():
    """Launch the Streamlit GUI"""
    try:
        # Change to the GUI directory
        gui_path = os.path.join("bharat_voice_assistant", "gui", "streamlit_app.py")
        
        if not os.path.exists(gui_path):
            print(f"❌ GUI file not found: {gui_path}")
            return False
        
        print("🚀 Launching Bharat Voice Assistant GUI...")
        print("🌐 Open your browser and go to: http://localhost:8501")
        print("🛑 Press Ctrl+C to stop the server")
        
        # Launch Streamlit
        subprocess.run([
            "streamlit", "run", gui_path,
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--theme.primaryColor", "#FF9933",
            "--theme.backgroundColor", "#FFFFFF",
            "--theme.secondaryBackgroundColor", "#F0F2F6",
            "--theme.textColor", "#262730"
        ])
        
    except KeyboardInterrupt:
        print("\n👋 GUI stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching GUI: {e}")
        return False
    except FileNotFoundError:
        print("❌ Streamlit not found. Installing...")
        if install_requirements():
            return launch_gui()
        return False
    
    return True

def main():
    """Main function"""
    print("🇮🇳 Bharat Voice Assistant - GUI Launcher")
    print("=" * 50)
    
    # Check if requirements are installed
    try:
        import streamlit
        import plotly
        import pandas
    except ImportError:
        print("📦 Installing GUI requirements...")
        if not install_requirements():
            print("❌ Failed to install requirements. Exiting.")
            sys.exit(1)
    
    # Launch the GUI
    if not launch_gui():
        print("❌ Failed to launch GUI. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    main()