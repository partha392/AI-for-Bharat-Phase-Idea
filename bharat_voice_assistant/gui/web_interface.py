"""
Web-based GUI for Bharat Voice Assistant
Provides visual interface alongside voice-first interaction
"""

from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import json
import asyncio
from datetime import datetime
import logging
from typing import Dict, List, Optional

from ..core.orchestrator import SystemOrchestrator
from ..language.conversation_manager import ConversationManager
from ..schemes.scheme_manager import SchemeManager
from ..grievance.filing_assistant import GrievanceFilingAssistant
from ..voice.gateway import VoiceGateway

logger = logging.getLogger(__name__)

class WebInterface:
    """Web-based GUI for the Bharat Voice Assistant"""
    
    def __init__(self):
        self.app = Flask(__name__, template_folder='templates', static_folder='static')
        self.app.secret_key = 'bharat_voice_assistant_secret_key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Initialize core components
        self.orchestrator = SystemOrchestrator()
        self.conversation_manager = ConversationManager()
        self.scheme_manager = SchemeManager()
        self.grievance_assistant = GrievanceFilingAssistant()
        self.voice_gateway = VoiceGateway()
        
        self.setup_routes()
        self.setup_socket_events()
    
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main dashboard"""
            return render_template('index.html')
        
        @self.app.route('/schemes')
        def schemes():
            """Government schemes discovery page"""
            return render_template('schemes.html')
        
        @self.app.route('/grievance')
        def grievance():
            """Grievance filing page"""
            return render_template('grievance.html')
        
        @self.app.route('/status')
        def status():
            """Status tracking page"""
            return render_template('status.html')
        
        @self.app.route('/api/schemes/search', methods=['POST'])
        def search_schemes():
            """API endpoint for scheme search"""
            try:
                data = request.json
                user_profile = data.get('user_profile', {})
                query = data.get('query', '')
                
                schemes = self.scheme_manager.find_matching_schemes(
                    user_profile=user_profile,
                    query=query
                )
                
                return jsonify({
                    'success': True,
                    'schemes': [scheme.to_dict() for scheme in schemes]
                })
            except Exception as e:
                logger.error(f"Scheme search error: {e}")
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/grievance/submit', methods=['POST'])
        def submit_grievance():
            """API endpoint for grievance submission"""
            try:
                data = request.json
                
                result = self.grievance_assistant.submit_grievance(
                    grievance_data=data.get('grievance_data'),
                    user_info=data.get('user_info')
                )
                
                return jsonify({
                    'success': True,
                    'reference_number': result.get('reference_number'),
                    'status': result.get('status')
                })
            except Exception as e:
                logger.error(f"Grievance submission error: {e}")
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/status/<reference_number>')
        def get_status(reference_number):
            """API endpoint for status tracking"""
            try:
                status_info = self.grievance_assistant.get_status(reference_number)
                return jsonify({
                    'success': True,
                    'status': status_info
                })
            except Exception as e:
                logger.error(f"Status tracking error: {e}")
                return jsonify({'success': False, 'error': str(e)})
    
    def setup_socket_events(self):
        """Setup WebSocket events for real-time communication"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection"""
            logger.info(f"Client connected: {request.sid}")
            emit('connected', {'message': 'Connected to Bharat Voice Assistant'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection"""
            logger.info(f"Client disconnected: {request.sid}")
        
        @self.socketio.on('voice_message')
        def handle_voice_message(data):
            """Handle voice message from client"""
            try:
                audio_data = data.get('audio_data')
                language = data.get('language', 'hindi')
                
                # Process voice input
                response = self.voice_gateway.process_voice_input(
                    audio_data=audio_data,
                    language=language,
                    session_id=request.sid
                )
                
                emit('voice_response', {
                    'text': response.get('text'),
                    'audio_url': response.get('audio_url'),
                    'intent': response.get('intent'),
                    'entities': response.get('entities')
                })
                
            except Exception as e:
                logger.error(f"Voice processing error: {e}")
                emit('error', {'message': str(e)})
        
        @self.socketio.on('text_message')
        def handle_text_message(data):
            """Handle text message from client"""
            try:
                message = data.get('message')
                language = data.get('language', 'hindi')
                
                # Process text input
                response = self.conversation_manager.process_message(
                    message=message,
                    language=language,
                    session_id=request.sid
                )
                
                emit('text_response', {
                    'message': response.get('message'),
                    'intent': response.get('intent'),
                    'entities': response.get('entities'),
                    'suggestions': response.get('suggestions', [])
                })
                
            except Exception as e:
                logger.error(f"Text processing error: {e}")
                emit('error', {'message': str(e)})
        
        @self.socketio.on('language_change')
        def handle_language_change(data):
            """Handle language change request"""
            try:
                language = data.get('language')
                session['language'] = language
                
                emit('language_changed', {
                    'language': language,
                    'message': f'Language changed to {language}'
                })
                
            except Exception as e:
                logger.error(f"Language change error: {e}")
                emit('error', {'message': str(e)})
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run the web interface"""
        logger.info(f"Starting Bharat Voice Assistant Web Interface on {host}:{port}")
        self.socketio.run(self.app, host=host, port=port, debug=debug)

# Create global instance
web_interface = WebInterface()

if __name__ == '__main__':
    web_interface.run(debug=True)