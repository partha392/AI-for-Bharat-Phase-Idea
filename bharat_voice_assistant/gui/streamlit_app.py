"""
Streamlit GUI for Bharat Voice Assistant
Beautiful, simple interface for voice-first government services
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import asyncio
import logging
from typing import Dict, List, Optional
import base64
import io

# Import core components (commented out for standalone demo)
# try:
#     from ..core.orchestrator import SystemOrchestrator
#     from ..language.conversation_manager import ConversationManager
#     from ..schemes.scheme_manager import SchemeManager
#     from ..grievance.filing_assistant import GrievanceFilingAssistant
#     from ..voice.gateway import VoiceGateway
#     from ..privacy.privacy_manager import PrivacyManager
# except ImportError:
#     # Fallback for direct execution
#     import sys
#     import os
#     sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

class BharatVoiceAssistantGUI:
    """Streamlit GUI for Bharat Voice Assistant"""
    
    def __init__(self):
        self.setup_page_config()
        self.initialize_components()
        self.setup_session_state()
    
    def setup_page_config(self):
        """Configure Streamlit page"""
        st.set_page_config(
            page_title="Bharat Voice Assistant",
            page_icon="🇮🇳",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS for Indian theme
        st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(90deg, #FF9933, #FFFFFF, #138808);
            padding: 1rem;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 2rem;
        }
        .feature-card {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 4px solid #138808;
            margin: 1rem 0;
        }
        .voice-button {
            background: #FF9933;
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: 50px;
            font-size: 1.2rem;
            cursor: pointer;
        }
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 1rem;
            border-radius: 5px;
            border: 1px solid #c3e6cb;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def initialize_components(self):
        """Initialize core system components"""
        # Use mock components for demo - this allows the GUI to work standalone
        self.create_mock_components()
    
    def create_mock_components(self):
        """Create mock components for demonstration"""
        class MockComponent:
            def __init__(self):
                pass
            
            def process_voice_input(self, **kwargs):
                return {
                    'text': 'मुझे कृषि योजनाओं के बारे में बताएं',
                    'audio_url': '/mock/audio.mp3',
                    'intent': 'scheme_inquiry',
                    'entities': {'category': 'agriculture'}
                }
            
            def process_message(self, **kwargs):
                return {
                    'message': 'आपके लिए कुछ मुख्य कृषि योजनाएं हैं: PM-KISAN, Crop Insurance...',
                    'intent': 'scheme_response',
                    'entities': {'schemes': ['PM-KISAN', 'Crop Insurance']},
                    'suggestions': ['Apply for PM-KISAN', 'Check eligibility']
                }
            
            def find_matching_schemes(self, **kwargs):
                return [
                    {
                        'name': 'PM-KISAN',
                        'category': 'Agriculture',
                        'description': 'Financial support to farmers',
                        'eligibility': 'Small and marginal farmers',
                        'benefit': '₹6,000 per year',
                        'match_score': 95
                    }
                ]
            
            def submit_grievance(self, **kwargs):
                import random
                return {
                    'reference_number': f'GRV{random.randint(100000, 999999)}',
                    'status': 'Submitted'
                }
            
            def get_status(self, reference_number):
                return {
                    'reference': reference_number,
                    'status': 'Under Review',
                    'department': 'Revenue Department',
                    'submitted_date': '2024-01-15',
                    'last_updated': '2024-01-20'
                }
        
        self.orchestrator = MockComponent()
        self.conversation_manager = MockComponent()
        self.scheme_manager = MockComponent()
        self.grievance_assistant = MockComponent()
        self.voice_gateway = MockComponent()
        self.privacy_manager = MockComponent()
    
    def setup_session_state(self):
        """Initialize session state variables"""
        if 'language' not in st.session_state:
            st.session_state.language = 'Hindi'
        if 'conversation_history' not in st.session_state:
            st.session_state.conversation_history = []
        if 'user_profile' not in st.session_state:
            st.session_state.user_profile = {}
        if 'current_grievance' not in st.session_state:
            st.session_state.current_grievance = {}
    
    def render_header(self):
        """Render main header"""
        st.markdown("""
        <div class="main-header">
            <h1>🇮🇳 भारत वॉयस असिस्टेंट | Bharat Voice Assistant</h1>
            <p>सरकारी सेवाओं के लिए आपका आवाज़ी सहायक | Your Voice Assistant for Government Services</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """Render sidebar with navigation and settings"""
        with st.sidebar:
            st.image("https://upload.wikimedia.org/wikipedia/en/4/41/Flag_of_India.svg", width=100)
            st.title("Navigation")
            
            # Language selection with callback
            languages = [
                'Hindi', 'English', 'Tamil', 'Telugu', 'Bengali', 
                'Marathi', 'Gujarati', 'Kannada', 'Malayalam', 'Punjabi'
            ]
            
            # Language selection with immediate update
            selected_language = st.selectbox(
                "भाषा चुनें | Select Language",
                languages,
                index=languages.index(st.session_state.language),
                key="language_selector"
            )
            
            # Update session state if language changed
            if selected_language != st.session_state.language:
                st.session_state.language = selected_language
                st.success(f"Language changed to {selected_language} | भाषा बदली गई")
                st.rerun()
            
            st.divider()
            
            # Navigation menu with language-specific labels
            if st.session_state.language == 'Hindi':
                menu_options = [
                    "🏠 होम",
                    "🎯 योजना खोज", 
                    "📝 शिकायत दर्ज करें",
                    "📊 स्थिति ट्रैक करें",
                    "🔊 आवाज़ी चैट",
                    "📈 विश्लेषण"
                ]
            elif st.session_state.language == 'Tamil':
                menu_options = [
                    "🏠 முகப்பு",
                    "🎯 திட்ட தேடல்",
                    "📝 புகார் பதிவு",
                    "📊 நிலை கண்காணிப்பு", 
                    "🔊 குரல் அரட்டை",
                    "📈 பகுப்பாய்வு"
                ]
            else:  # English and others
                menu_options = [
                    "🏠 Home",
                    "🎯 Scheme Discovery",
                    "📝 File Grievance", 
                    "📊 Track Status",
                    "🔊 Voice Chat",
                    "📈 Analytics"
                ]
            
            page = st.radio("सेवाएं | Services", menu_options)
            
            st.divider()
            
            # User profile with language-specific labels
            profile_title = "👤 उपयोगकर्ता प्रोफ़ाइल" if st.session_state.language == 'Hindi' else "👤 User Profile"
            with st.expander(profile_title):
                name_label = "नाम" if st.session_state.language == 'Hindi' else "Name"
                age_label = "आयु" if st.session_state.language == 'Hindi' else "Age"
                state_label = "राज्य" if st.session_state.language == 'Hindi' else "State"
                income_label = "आय श्रेणी" if st.session_state.language == 'Hindi' else "Income Category"
                
                st.session_state.user_profile['name'] = st.text_input(name_label)
                st.session_state.user_profile['age'] = st.number_input(age_label, 18, 100, 30)
                st.session_state.user_profile['state'] = st.selectbox(
                    state_label,
                    ['Delhi', 'Maharashtra', 'Karnataka', 'Tamil Nadu', 'Gujarat', 'Other']
                )
                st.session_state.user_profile['income'] = st.selectbox(
                    income_label,
                    ['Below Poverty Line', 'Low Income', 'Middle Income', 'High Income']
                )
        
        return page
    
    def render_home_page(self):
        """Render home page"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="feature-card">
                <h3>🎯 Scheme Discovery</h3>
                <p>Find government schemes that match your profile and needs</p>
                <p><strong>योजना खोज:</strong> अपनी प्रोफ़ाइल के अनुसार सरकारी योजनाएं खोजें</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="feature-card">
                <h3>📝 File Grievance</h3>
                <p>Submit complaints and grievances through voice or text</p>
                <p><strong>शिकायत दर्ज करें:</strong> आवाज़ या टेक्स्ट के माध्यम से शिकायत दर्ज करें</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="feature-card">
                <h3>📊 Track Status</h3>
                <p>Monitor the progress of your applications and grievances</p>
                <p><strong>स्थिति ट्रैक करें:</strong> अपने आवेदन और शिकायतों की प्रगति देखें</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Quick stats
        st.subheader("📈 System Statistics | सिस्टम आंकड़े")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Active Schemes | सक्रिय योजनाएं", "1,247", "+23")
        with col2:
            st.metric("Grievances Filed | दर्ज शिकायतें", "45,678", "+156")
        with col3:
            st.metric("Success Rate | सफलता दर", "94.2%", "+2.1%")
        with col4:
            st.metric("Languages Supported | समर्थित भाषाएं", "10", "0")
    
    def render_scheme_discovery(self):
        """Render scheme discovery page"""
        st.subheader("🎯 Government Scheme Discovery | सरकारी योजना खोज")
        
        # Search interface
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(
                "Search for schemes | योजनाओं की खोज करें",
                placeholder="e.g., education, healthcare, agriculture"
            )
        with col2:
            if st.button("🔍 Search | खोजें", use_container_width=True):
                self.search_schemes(search_query)
        
        # Filters
        with st.expander("🔧 Filters | फ़िल्टर"):
            col1, col2, col3 = st.columns(3)
            with col1:
                category = st.selectbox(
                    "Category | श्रेणी",
                    ['All', 'Education', 'Healthcare', 'Agriculture', 'Employment', 'Housing']
                )
            with col2:
                eligibility = st.selectbox(
                    "Eligibility | पात्रता",
                    ['All', 'Women', 'Senior Citizens', 'Students', 'Farmers', 'BPL']
                )
            with col3:
                level = st.selectbox(
                    "Government Level | सरकारी स्तर",
                    ['All', 'Central', 'State', 'District']
                )
        
        # Sample schemes display
        self.display_sample_schemes()
    
    def search_schemes(self, query):
        """Search for schemes based on query"""
        # Mock search results
        schemes = [
            {
                'name': 'Pradhan Mantri Kisan Samman Nidhi',
                'category': 'Agriculture',
                'description': 'Financial support to farmers',
                'eligibility': 'Small and marginal farmers',
                'benefit': '₹6,000 per year',
                'match_score': 95
            },
            {
                'name': 'Ayushman Bharat',
                'category': 'Healthcare',
                'description': 'Health insurance scheme',
                'eligibility': 'Economically weaker sections',
                'benefit': '₹5 lakh coverage',
                'match_score': 88
            }
        ]
        
        st.success(f"Found {len(schemes)} matching schemes | {len(schemes)} मैचिंग योजनाएं मिलीं")
        
        for scheme in schemes:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{scheme['name']}**")
                    st.write(f"Category: {scheme['category']} | Benefit: {scheme['benefit']}")
                    st.write(scheme['description'])
                with col2:
                    st.metric("Match Score", f"{scheme['match_score']}%")
                    if st.button(f"Apply | आवेदन करें", key=scheme['name']):
                        st.success("Application process started!")
                st.divider()
    
    def display_sample_schemes(self):
        """Display sample schemes"""
        st.subheader("🌟 Recommended Schemes | अनुशंसित योजनाएं")
        
        # Create sample data
        schemes_data = {
            'Scheme Name': [
                'PM-KISAN', 'Ayushman Bharat', 'Beti Bachao Beti Padhao',
                'MGNREGA', 'Pradhan Mantri Awas Yojana'
            ],
            'Category': ['Agriculture', 'Healthcare', 'Women Welfare', 'Employment', 'Housing'],
            'Benefit Amount': ['₹6,000', '₹5,00,000', 'Variable', '₹200/day', '₹2,50,000'],
            'Match Score': [95, 88, 92, 85, 78]
        }
        
        df = pd.DataFrame(schemes_data)
        
        # Display as interactive table
        st.dataframe(df, use_container_width=True)
        
        # Visualization
        fig = px.bar(df, x='Scheme Name', y='Match Score', 
                    title='Scheme Matching Scores | योजना मैचिंग स्कोर')
        st.plotly_chart(fig, use_container_width=True)
    
    def render_grievance_filing(self):
        """Render grievance filing page"""
        st.subheader("📝 File a Grievance | शिकायत दर्ज करें")
        
        # Grievance form
        with st.form("grievance_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                grievance_type = st.selectbox(
                    "Grievance Type | शिकायत का प्रकार",
                    ['Service Delay', 'Corruption', 'Poor Service Quality', 'Document Issues', 'Other']
                )
                
                department = st.selectbox(
                    "Department | विभाग",
                    ['Revenue', 'Police', 'Health', 'Education', 'Transport', 'Other']
                )
                
                priority = st.selectbox(
                    "Priority | प्राथमिकता",
                    ['High', 'Medium', 'Low']
                )
            
            with col2:
                location = st.text_input("Location | स्थान")
                phone = st.text_input("Phone Number | फ़ोन नंबर")
                email = st.text_input("Email | ईमेल")
            
            description = st.text_area(
                "Describe your grievance | अपनी शिकायत का वर्णन करें",
                height=150,
                placeholder="Please provide detailed information about your grievance..."
            )
            
            # File upload
            uploaded_files = st.file_uploader(
                "Upload supporting documents | सहायक दस्तावेज़ अपलोड करें",
                accept_multiple_files=True,
                type=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
            )
            
            submitted = st.form_submit_button("🚀 Submit Grievance | शिकायत जमा करें")
            
            if submitted:
                # Generate reference number
                import random
                ref_number = f"GRV{random.randint(100000, 999999)}"
                
                st.success(f"""
                ✅ Grievance submitted successfully! | शिकायत सफलतापूर्वक जमा की गई!
                
                **Reference Number | संदर्भ संख्या:** {ref_number}
                
                You will receive updates on your registered phone/email.
                आपको अपने पंजीकृत फ़ोन/ईमेल पर अपडेट मिलेंगे।
                """)
                
                # Store in session state
                st.session_state.current_grievance = {
                    'reference': ref_number,
                    'type': grievance_type,
                    'department': department,
                    'status': 'Submitted',
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
    
    def render_status_tracking(self):
        """Render status tracking page"""
        st.subheader("📊 Track Status | स्थिति ट्रैक करें")
        
        # Reference number input
        col1, col2 = st.columns([3, 1])
        with col1:
            ref_number = st.text_input(
                "Enter Reference Number | संदर्भ संख्या दर्ज करें",
                placeholder="e.g., GRV123456"
            )
        with col2:
            if st.button("🔍 Track | ट्रैक करें", use_container_width=True):
                self.track_status(ref_number)
        
        # Current grievance status (if available)
        if st.session_state.current_grievance:
            st.subheader("📋 Current Grievance | वर्तमान शिकायत")
            
            grievance = st.session_state.current_grievance
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Reference | संदर्भ", grievance['reference'])
            with col2:
                st.metric("Status | स्थिति", grievance['status'])
            with col3:
                st.metric("Department | विभाग", grievance.get('department', 'N/A'))
            
            # Status timeline
            self.render_status_timeline()
    
    def track_status(self, ref_number):
        """Track status of a grievance"""
        if ref_number:
            # Mock status data
            status_data = {
                'reference': ref_number,
                'status': 'Under Review',
                'department': 'Revenue Department',
                'submitted_date': '2024-01-15',
                'last_updated': '2024-01-20',
                'expected_resolution': '2024-01-30'
            }
            
            st.success("Status found! | स्थिति मिली!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Reference:** {status_data['reference']}")
                st.write(f"**Status:** {status_data['status']}")
                st.write(f"**Department:** {status_data['department']}")
            with col2:
                st.write(f"**Submitted:** {status_data['submitted_date']}")
                st.write(f"**Last Updated:** {status_data['last_updated']}")
                st.write(f"**Expected Resolution:** {status_data['expected_resolution']}")
        else:
            st.warning("Please enter a reference number | कृपया संदर्भ संख्या दर्ज करें")
    
    def render_status_timeline(self):
        """Render status timeline"""
        st.subheader("📅 Status Timeline | स्थिति समयरेखा")
        
        # Mock timeline data
        timeline_data = [
            {'date': '2024-01-15', 'status': 'Submitted', 'description': 'Grievance submitted successfully'},
            {'date': '2024-01-16', 'status': 'Acknowledged', 'description': 'Grievance acknowledged by department'},
            {'date': '2024-01-20', 'status': 'Under Review', 'description': 'Case assigned to reviewing officer'},
            {'date': '2024-01-25', 'status': 'In Progress', 'description': 'Investigation in progress'},
        ]
        
        for i, item in enumerate(timeline_data):
            col1, col2 = st.columns([1, 4])
            with col1:
                st.write(f"**{item['date']}**")
            with col2:
                if i == len(timeline_data) - 1:  # Current status
                    st.success(f"🔄 **{item['status']}** - {item['description']}")
                else:
                    st.write(f"✅ **{item['status']}** - {item['description']}")
    
    def render_voice_chat(self):
        """Render voice chat interface"""
        st.subheader("🔊 Voice Chat | आवाज़ी चैट")
        
        # Initialize voice conversation in session state
        if 'voice_conversation' not in st.session_state:
            st.session_state.voice_conversation = []
        if 'voice_active' not in st.session_state:
            st.session_state.voice_active = False
        if 'demo_mode' not in st.session_state:
            st.session_state.demo_mode = True
        
        # Language-specific content
        language_content = {
            'Hindi': {
                'voice_features': """
                🎤 **आवाज़ी सुविधाएं:**
                - अपनी पसंदीदा भाषा में बोलें
                - सरकारी योजनाओं के बारे में पूछें
                - आवाज़ के माध्यम से शिकायत दर्ज करें
                - स्थिति अपडेट प्राप्त करें
                """,
                'start_button': "🎤 आवाज़ी चैट शुरू करें",
                'stop_button': "⏹️ आवाज़ी चैट बंद करें",
                'activated': "✅ आवाज़ी चैट सक्रिय! नीचे बोलें या टाइप करें।",
                'deactivated': "⏹️ आवाज़ी चैट बंद कर दी गई।",
                'demo_voice_inputs': [
                    "मुझे कृषि योजनाओं के बारे में बताएं",
                    "PM-KISAN के लिए कैसे आवेदन करें?",
                    "मैं शिकायत दर्ज करना चाहता हूं",
                    "मेरी शिकायत का स्टेटस क्या है?",
                    "स्वास्थ्य योजनाओं की जानकारी दें"
                ],
                'conversation_history': "💬 बातचीत का इतिहास"
            },
            'English': {
                'voice_features': """
                🎤 **Voice Features:**
                - Speak in your preferred language
                - Ask about government schemes
                - File grievances through voice
                - Get status updates
                """,
                'start_button': "🎤 Start Voice Chat",
                'stop_button': "⏹️ Stop Voice Chat",
                'activated': "✅ Voice chat activated! Speak or type below.",
                'deactivated': "⏹️ Voice chat stopped.",
                'demo_voice_inputs': [
                    "Tell me about agriculture schemes",
                    "How to apply for PM-KISAN?",
                    "I want to file a grievance",
                    "What is the status of my complaint?",
                    "Give me information about health schemes"
                ],
                'conversation_history': "💬 Conversation History"
            },
            'Tamil': {
                'voice_features': """
                🎤 **குரல் அம்சங்கள்:**
                - உங்கள் விருப்பமான மொழியில் பேசுங்கள்
                - அரசாங்க திட்டங்களைப் பற்றி கேளுங்கள்
                - குரல் மூலம் புகார்களை பதிவு செய்யுங்கள்
                - நிலை புதுப்பிப்புகளைப் பெறுங்கள்
                """,
                'start_button': "🎤 குரல் அரட்டையைத் தொடங்கவும்",
                'stop_button': "⏹️ குரல் அரட்டையை நிறுத்தவும்",
                'activated': "✅ குரல் அரட்டை செயல்படுத்தப்பட்டது! பேசுங்கள் அல்லது கீழே தட்டச்சு செய்யுங்கள்।",
                'deactivated': "⏹️ குரல் அரட்டை நிறுத்தப்பட்டது।",
                'demo_voice_inputs': [
                    "விவசாய திட்டங்களைப் பற்றி சொல்லுங்கள்",
                    "PM-KISAN க்கு எப்படி விண்ணப்பிப்பது?",
                    "நான் ஒரு புகார் பதிவு செய்ய விரும்புகிறேன்",
                    "என் புகாரின் நிலை என்ன?",
                    "சுகாதார திட்டங்களைப் பற்றி தகவல் கொடுங்கள்"
                ],
                'conversation_history': "💬 உரையாடல் வரலாறு"
            }
        }
        
        current_lang = st.session_state.language
        content = language_content.get(current_lang, language_content['English'])
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info(content['voice_features'])
        
        with col2:
            # Voice control buttons
            if not st.session_state.voice_active:
                if st.button(content['start_button'], use_container_width=True, type="primary"):
                    st.session_state.voice_active = True
                    st.success(content['activated'])
                    
                    # Add welcome message to conversation
                    welcome_msg = {
                        'Hindi': "नमस्ते! मैं भारत वॉयस असिस्टेंट हूं। मैं आपकी सरकारी योजनाओं और शिकायतों में मदद कर सकता हूं। नीचे दिए गए विकल्पों में से चुनें या अपना सवाल टाइप करें।",
                        'English': "Hello! I'm Bharat Voice Assistant. I can help you with government schemes and grievances. Choose from the options below or type your question.",
                        'Tamil': "வணக்கம்! நான் பாரத் குரல் உதவியாளர். அரசாங்க திட்டங்கள் மற்றும் புகார்களில் உங்களுக்கு உதவ முடியும். கீழே உள்ள விருப்பங்களில் இருந்து தேர்வு செய்யுங்கள் அல்லது உங்கள் கேள்வியை தட்டச்சு செய்யுங்கள்."
                    }
                    
                    st.session_state.voice_conversation.append({
                        "role": "assistant",
                        "message": welcome_msg.get(current_lang, welcome_msg['English']),
                        "time": "Now"
                    })
                    st.rerun()
            else:
                if st.button(content['stop_button'], use_container_width=True, type="secondary"):
                    st.session_state.voice_active = False
                    st.info(content['deactivated'])
                    st.rerun()
        
        # Show voice status and demo options
        if st.session_state.voice_active:
            st.success("🎙️ Voice Assistant Active | आवाज़ी सहायक सक्रिय | குரல் உதவியாளர் செயலில்")
            
            # Demo voice input options
            st.subheader("🎤 Quick Voice Commands | त्वरित आवाज़ी कमांड | விரைவு குரல் கட்டளைகள்")
            
            # Create buttons for each demo voice input
            cols = st.columns(2)
            for i, voice_input in enumerate(content['demo_voice_inputs']):
                col_idx = i % 2
                with cols[col_idx]:
                    if st.button(f"🎙️ {voice_input}", key=f"voice_btn_{i}", use_container_width=True):
                        # Simulate voice processing
                        with st.spinner("🎧 Processing voice... | आवाज़ प्रोसेसिंग... | குரல் செயலாக்கம்..."):
                            import time
                            time.sleep(1.5)
                        
                        # Add user message
                        st.session_state.voice_conversation.append({
                            "role": "user",
                            "message": f"🎤 {voice_input}",
                            "time": "Now"
                        })
                        
                        # Generate AI response
                        response = self.conversation_manager.process_message(
                            message=voice_input,
                            language=current_lang.lower(),
                            session_id="voice_session"
                        )
                        
                        # Add AI response
                        st.session_state.voice_conversation.append({
                            "role": "assistant",
                            "message": response['message'],
                            "time": "Now"
                        })
                        
                        st.rerun()
        
        # Chat input (always available)
        st.subheader("💬 Text Chat | टेक्स्ट चैट | உரை அரட்டை")
        
        # Chat input
        chat_placeholder = {
            'Hindi': "यहाँ अपना संदेश टाइप करें...",
            'English': "Type your message here...",
            'Tamil': "உங்கள் செய்தியை இங்கே தட்டச்சு செய்யுங்கள்..."
        }
        
        if prompt := st.chat_input(chat_placeholder.get(current_lang, chat_placeholder['English'])):
            # Add user message to conversation history
            st.session_state.voice_conversation.append({
                "role": "user",
                "message": prompt,
                "time": "Now"
            })
            
            # Get AI response
            response = self.conversation_manager.process_message(
                message=prompt,
                language=current_lang.lower(),
                session_id="text_session"
            )
            
            # Add AI response to conversation
            st.session_state.voice_conversation.append({
                "role": "assistant",
                "message": response['message'],
                "time": "Now"
            })
            
            st.rerun()
            st.session_state.voice_conversation.append({
                "role": "assistant",
                "message": response['message'],
                "time": "Now"
            })
            
            st.rerun()
        
        # Display conversation history
        st.subheader(content['conversation_history'])
        
        # Show conversation from session state
        if st.session_state.voice_conversation:
            # Display conversation in chat format
            for msg in st.session_state.voice_conversation[-10:]:  # Show last 10 messages
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.write(f"{msg['message']}")
                        st.caption(f"⏰ {msg['time']}")
                else:
                    with st.chat_message("assistant"):
                        st.write(f"{msg['message']}")
                        st.caption(f"⏰ {msg['time']}")
            
            # Clear conversation button
            if st.button("🗑️ Clear Conversation | बातचीत साफ़ करें | உரையாடலை அழிக்கவும்"):
                st.session_state.voice_conversation = []
                st.success("Conversation cleared! | बातचीत साफ़ कर दी गई! | உரையாடல் அழிக்கப்பட்டது!")
                st.rerun()
        else:
            # Show sample conversation when no active conversation
            sample_messages = {
                'Hindi': [
                    {"role": "assistant", "message": "नमस्ते! मैं भारत वॉयस असिस्टेंट हूं। आप मुझसे सरकारी योजनाओं और शिकायतों के बारे में पूछ सकते हैं।", "time": "Demo"},
                    {"role": "user", "message": "🎤 मुझे कृषि योजनाओं के बारे में बताएं", "time": "Demo"},
                    {"role": "assistant", "message": "आपके लिए मुख्य कृषि योजनाएं: PM-KISAN (₹6,000/वर्ष), फसल बीमा योजना, किसान क्रेडिट कार्ड। कौन सी योजना के बारे में विस्तार से जानना चाहते हैं?", "time": "Demo"}
                ],
                'English': [
                    {"role": "assistant", "message": "Hello! I'm Bharat Voice Assistant. You can ask me about government schemes and grievances.", "time": "Demo"},
                    {"role": "user", "message": "🎤 Tell me about agriculture schemes", "time": "Demo"},
                    {"role": "assistant", "message": "Key agriculture schemes for you: PM-KISAN (₹6,000/year), Crop Insurance Scheme, Kisan Credit Card. Which scheme would you like to know more about?", "time": "Demo"}
                ],
                'Tamil': [
                    {"role": "assistant", "message": "வணக்கம்! நான் பாரத் குரல் உதவியாளர். அரசாங்க திட்டங்கள் மற்றும் புகார்களைப் பற்றி என்னிடம் கேட்கலாம்.", "time": "Demo"},
                    {"role": "user", "message": "🎤 விவசாய திட்டங்களைப் பற்றி சொல்லுங்கள்", "time": "Demo"},
                    {"role": "assistant", "message": "உங்களுக்கான முக்கிய விவசாய திட்டங்கள்: PM-KISAN (₹6,000/ஆண்டு), பயிர் காப்பீட்டு திட்டம், கிசான் கிரெடிட் கார்டு. எந்த திட்டத்தைப் பற்றி மேலும் அறிய விரும்புகிறீர்கள்?", "time": "Demo"}
                ]
            }
            
            demo_conversation = sample_messages.get(current_lang, sample_messages['English'])
            
            st.info("👆 Start voice chat above to begin conversation | ऊपर आवाज़ी चैट शुरू करें | மேலே குரல் அரட்டையைத் தொடங்கவும்")
            
            for msg in demo_conversation:
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.write(f"{msg['message']}")
                        st.caption(f"⏰ {msg['time']}")
                else:
                    with st.chat_message("assistant"):
                        st.write(f"{msg['message']}")
                        st.caption(f"⏰ {msg['time']}")
    
    def render_analytics(self):
        """Render analytics dashboard"""
        st.subheader("📈 Analytics Dashboard | विश्लेषण डैशबोर्ड")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Users | कुल उपयोगकर्ता", "1,24,567", "+1,234")
        with col2:
            st.metric("Schemes Applied | आवेदित योजनाएं", "45,678", "+567")
        with col3:
            st.metric("Grievances Resolved | हल की गई शिकायतें", "38,945", "+234")
        with col4:
            st.metric("Success Rate | सफलता दर", "94.2%", "+2.1%")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Usage by language
            lang_data = {
                'Language': ['Hindi', 'English', 'Tamil', 'Telugu', 'Bengali', 'Others'],
                'Users': [45000, 32000, 18000, 15000, 12000, 8000]
            }
            fig1 = px.pie(lang_data, values='Users', names='Language', 
                         title='Usage by Language | भाषा के अनुसार उपयोग')
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Monthly trends
            import pandas as pd
            dates = pd.date_range('2024-01-01', periods=12, freq='M')
            trend_data = {
                'Month': dates,
                'New Users': [5000, 5500, 6000, 6200, 6800, 7200, 7500, 7800, 8000, 8200, 8500, 8800],
                'Grievances': [1200, 1300, 1100, 1400, 1500, 1600, 1450, 1550, 1650, 1700, 1750, 1800]
            }
            fig2 = px.line(trend_data, x='Month', y=['New Users', 'Grievances'],
                          title='Monthly Trends | मासिक रुझान')
            st.plotly_chart(fig2, use_container_width=True)
        
        # State-wise distribution
        st.subheader("🗺️ State-wise Distribution | राज्यवार वितरण")
        
        state_data = {
            'State': ['Uttar Pradesh', 'Maharashtra', 'Bihar', 'West Bengal', 'Madhya Pradesh', 'Tamil Nadu'],
            'Users': [25000, 22000, 18000, 15000, 12000, 10000],
            'Schemes Applied': [8500, 7800, 6200, 5100, 4200, 3800]
        }
        
        fig3 = px.bar(state_data, x='State', y=['Users', 'Schemes Applied'],
                     title='State-wise Usage | राज्यवार उपयोग', barmode='group')
        st.plotly_chart(fig3, use_container_width=True)
    
    def run(self):
        """Main application runner"""
        self.render_header()
        
        # Get current page from sidebar
        current_page = self.render_sidebar()
        
        # Render appropriate page based on selection
        if "Home" in current_page or "होम" in current_page or "முகப்பு" in current_page:
            self.render_home_page()
        elif "Scheme" in current_page or "योजना" in current_page or "திட்ட" in current_page:
            self.render_scheme_discovery()
        elif "Grievance" in current_page or "शिकायत" in current_page or "புகார்" in current_page:
            self.render_grievance_filing()
        elif "Status" in current_page or "स्थिति" in current_page or "நிலை" in current_page:
            self.render_status_tracking()
        elif "Voice" in current_page or "आवाज़ी" in current_page or "குரல்" in current_page:
            self.render_voice_chat()
        elif "Analytics" in current_page or "विश्लेषण" in current_page or "பகுப்பாய்வு" in current_page:
            self.render_analytics()
        
        # Footer
        st.divider()
        st.markdown("""
        <div style='text-align: center; color: #666;'>
            <p>🇮🇳 Bharat Voice Assistant | भारत वॉयस असिस्टेंट</p>
            <p>Empowering Citizens Through Voice Technology | आवाज़ की तकनीक से नागरिकों को सशक्त बनाना</p>
        </div>
        """, unsafe_allow_html=True)

# Create and run the app
def main():
    app = BharatVoiceAssistantGUI()
    app.run()

if __name__ == "__main__":
    main()