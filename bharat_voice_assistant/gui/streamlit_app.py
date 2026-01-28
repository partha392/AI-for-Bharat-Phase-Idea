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
            
            # Language selection
            languages = [
                'Hindi', 'English', 'Tamil', 'Telugu', 'Bengali', 
                'Marathi', 'Gujarati', 'Kannada', 'Malayalam', 'Punjabi'
            ]
            st.session_state.language = st.selectbox(
                "भाषा चुनें | Select Language",
                languages,
                index=languages.index(st.session_state.language)
            )
            
            st.divider()
            
            # Navigation menu
            page = st.radio(
                "सेवाएं | Services",
                [
                    "🏠 Home | होम",
                    "🎯 Scheme Discovery | योजना खोज",
                    "📝 File Grievance | शिकायत दर्ज करें",
                    "📊 Track Status | स्थिति ट्रैक करें",
                    "🔊 Voice Chat | आवाज़ी चैट",
                    "📈 Analytics | विश्लेषण"
                ]
            )
            
            st.divider()
            
            # User profile
            with st.expander("👤 User Profile | उपयोगकर्ता प्रोफ़ाइल"):
                st.session_state.user_profile['name'] = st.text_input("Name | नाम")
                st.session_state.user_profile['age'] = st.number_input("Age | आयु", 18, 100, 30)
                st.session_state.user_profile['state'] = st.selectbox(
                    "State | राज्य",
                    ['Delhi', 'Maharashtra', 'Karnataka', 'Tamil Nadu', 'Gujarat', 'Other']
                )
                st.session_state.user_profile['income'] = st.selectbox(
                    "Income Category | आय श्रेणी",
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
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info("""
            🎤 **Voice Features | आवाज़ी सुविधाएं:**
            - Speak in your preferred language | अपनी पसंदीदा भाषा में बोलें
            - Ask about government schemes | सरकारी योजनाओं के बारे में पूछें
            - File grievances through voice | आवाज़ के माध्यम से शिकायत दर्ज करें
            - Get status updates | स्थिति अपडेट प्राप्त करें
            """)
        
        with col2:
            if st.button("🎤 Start Voice Chat | आवाज़ी चैट शुरू करें", use_container_width=True):
                st.success("Voice chat activated! | आवाज़ी चैट सक्रिय!")
                st.info("Please speak now... | कृपया अब बोलें...")
        
        # Chat history
        st.subheader("💬 Conversation History | बातचीत का इतिहास")
        
        # Sample conversation
        sample_conversation = [
            {"role": "user", "message": "मुझे कृषि योजनाओं के बारे में बताएं", "time": "10:30 AM"},
            {"role": "assistant", "message": "आपके लिए कुछ मुख्य कृषि योजनाएं हैं: PM-KISAN, Crop Insurance Scheme...", "time": "10:31 AM"},
            {"role": "user", "message": "PM-KISAN के लिए कैसे आवेदन करें?", "time": "10:32 AM"},
            {"role": "assistant", "message": "PM-KISAN के लिए आवेदन करने के लिए आप ऑनलाइन पोर्टल पर जा सकते हैं...", "time": "10:33 AM"}
        ]
        
        for msg in sample_conversation:
            if msg["role"] == "user":
                st.chat_message("user").write(f"{msg['message']} *({msg['time']})*")
            else:
                st.chat_message("assistant").write(f"{msg['message']} *({msg['time']})*")
    
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
        
        # Render appropriate page
        if "Home" in current_page:
            self.render_home_page()
        elif "Scheme Discovery" in current_page:
            self.render_scheme_discovery()
        elif "File Grievance" in current_page:
            self.render_grievance_filing()
        elif "Track Status" in current_page:
            self.render_status_tracking()
        elif "Voice Chat" in current_page:
            self.render_voice_chat()
        elif "Analytics" in current_page:
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