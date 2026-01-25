-- Database initialization script for Bharat Voice Assistant
-- This script sets up the initial database schema and configuration

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Create custom types
CREATE TYPE user_language AS ENUM (
    'hi', 'en', 'ta', 'te', 'bn', 'mr', 'gu', 'kn', 'ml', 'pa'
);

CREATE TYPE grievance_status AS ENUM (
    'draft', 'submitted', 'acknowledged', 'in_progress', 
    'under_review', 'resolved', 'closed', 'rejected'
);

CREATE TYPE scheme_category AS ENUM (
    'agriculture', 'education', 'health', 'housing', 'employment',
    'social_security', 'rural_development', 'women_empowerment',
    'disability', 'senior_citizen', 'financial_inclusion'
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number VARCHAR(15) UNIQUE NOT NULL,
    preferred_language user_language NOT NULL DEFAULT 'hi',
    state VARCHAR(100),
    district VARCHAR(100),
    block VARCHAR(100),
    village VARCHAR(100),
    age_group VARCHAR(20),
    income_category VARCHAR(50),
    education_level VARCHAR(50),
    occupation VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create government schemes table
CREATE TABLE IF NOT EXISTS government_schemes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scheme_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    name_hi VARCHAR(500),
    name_regional JSONB, -- For other regional language names
    department VARCHAR(200) NOT NULL,
    ministry VARCHAR(200),
    category scheme_category NOT NULL,
    subcategory VARCHAR(100),
    description TEXT NOT NULL,
    description_hi TEXT,
    description_regional JSONB,
    eligibility_criteria JSONB NOT NULL,
    benefits JSONB NOT NULL,
    required_documents JSONB NOT NULL,
    application_process JSONB NOT NULL,
    target_states JSONB, -- Array of state codes
    target_districts JSONB, -- Array of district codes
    is_active BOOLEAN DEFAULT TRUE,
    launch_date DATE,
    end_date DATE,
    budget_allocated DECIMAL(15,2),
    beneficiaries_target INTEGER,
    beneficiaries_current INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    average_processing_days INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(100),
    last_verified_at TIMESTAMP WITH TIME ZONE
);

-- Create grievances table
CREATE TABLE IF NOT EXISTS grievances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference_number VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    description_hi TEXT,
    priority VARCHAR(20) DEFAULT 'medium',
    status grievance_status DEFAULT 'draft',
    submitted_at TIMESTAMP WITH TIME ZONE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    expected_resolution_date DATE,
    actual_resolution_date DATE,
    resolution_description TEXT,
    satisfaction_rating INTEGER CHECK (satisfaction_rating >= 1 AND satisfaction_rating <= 5),
    supporting_documents JSONB,
    government_portal_id VARCHAR(100),
    assigned_officer VARCHAR(200),
    assigned_department VARCHAR(200),
    escalation_level INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create grievance status history table
CREATE TABLE IF NOT EXISTS grievance_status_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grievance_id UUID NOT NULL REFERENCES grievances(id) ON DELETE CASCADE,
    old_status grievance_status,
    new_status grievance_status NOT NULL,
    changed_by VARCHAR(200),
    change_reason TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create user interactions table for conversation history
CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) NOT NULL,
    interaction_type VARCHAR(50) NOT NULL, -- 'voice_input', 'voice_output', 'scheme_search', etc.
    language user_language NOT NULL,
    input_text TEXT,
    output_text TEXT,
    confidence_score DECIMAL(3,2),
    processing_time_ms INTEGER,
    intent VARCHAR(100),
    entities JSONB,
    context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create scheme recommendations table
CREATE TABLE IF NOT EXISTS scheme_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scheme_id UUID NOT NULL REFERENCES government_schemes(id) ON DELETE CASCADE,
    relevance_score DECIMAL(3,2) NOT NULL,
    eligibility_match DECIMAL(3,2) NOT NULL,
    recommendation_reason TEXT,
    recommended_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_feedback VARCHAR(20), -- 'helpful', 'not_helpful', 'applied'
    feedback_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id, scheme_id)
);

-- Create system metrics table
CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(20),
    dimensions JSONB,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number);
CREATE INDEX IF NOT EXISTS idx_users_location ON users(state, district, block);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active, last_active_at);

CREATE INDEX IF NOT EXISTS idx_schemes_category ON government_schemes(category);
CREATE INDEX IF NOT EXISTS idx_schemes_active ON government_schemes(is_active);
CREATE INDEX IF NOT EXISTS idx_schemes_states ON government_schemes USING GIN(target_states);
CREATE INDEX IF NOT EXISTS idx_schemes_search ON government_schemes USING GIN(to_tsvector('english', name || ' ' || description));

CREATE INDEX IF NOT EXISTS idx_grievances_user ON grievances(user_id);
CREATE INDEX IF NOT EXISTS idx_grievances_status ON grievances(status);
CREATE INDEX IF NOT EXISTS idx_grievances_reference ON grievances(reference_number);
CREATE INDEX IF NOT EXISTS idx_grievances_submitted ON grievances(submitted_at);

CREATE INDEX IF NOT EXISTS idx_interactions_user ON user_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_session ON user_interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON user_interactions(created_at);

CREATE INDEX IF NOT EXISTS idx_recommendations_user ON scheme_recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_scheme ON scheme_recommendations(scheme_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_score ON scheme_recommendations(relevance_score DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_name ON system_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded ON system_metrics(recorded_at);

-- Create functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for automatic timestamp updates
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schemes_updated_at BEFORE UPDATE ON government_schemes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_grievances_updated_at BEFORE UPDATE ON grievances
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for testing
INSERT INTO government_schemes (
    scheme_id, name, name_hi, department, category, description, description_hi,
    eligibility_criteria, benefits, required_documents, application_process,
    target_states, is_active
) VALUES (
    'pmay-g-001',
    'Pradhan Mantri Awas Yojana - Gramin',
    'प्रधान मंत्री आवास योजना - ग्रामीण',
    'Ministry of Rural Development',
    'housing',
    'Financial assistance for construction of pucca houses in rural areas',
    'ग्रामीण क्षेत्रों में पक्के मकान के निर्माण के लिए वित्तीय सहायता',
    '{"income_limit": 200000, "location_type": "rural", "housing_status": "homeless_or_inadequate"}',
    '{"financial_assistance": 120000, "description": "Financial assistance for construction of pucca house"}',
    '["aadhaar_card", "income_certificate", "bank_account_details", "land_documents"]',
    '["Visit Common Service Center", "Fill application form", "Submit required documents", "Wait for verification", "Receive approval and funds"]',
    '["MH", "UP", "MP", "RJ", "GJ", "AP", "TN", "KA", "WB", "OR"]',
    true
) ON CONFLICT (scheme_id) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bharat_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bharat_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO bharat_user;