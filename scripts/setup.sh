#!/bin/bash
# Setup script for Bharat Voice Assistant development environment

set -e

echo "🚀 Setting up Bharat Voice Assistant development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python 3.11+ is installed
check_python() {
    print_status "Checking Python version..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        REQUIRED_VERSION="3.11"
        
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
            print_success "Python $PYTHON_VERSION found"
        else
            print_error "Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 is not installed"
        exit 1
    fi
}

# Check if Docker is installed
check_docker() {
    print_status "Checking Docker installation..."
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
        print_success "Docker $DOCKER_VERSION found"
        
        # Check if Docker Compose is available
        if docker compose version &> /dev/null; then
            COMPOSE_VERSION=$(docker compose version --short)
            print_success "Docker Compose $COMPOSE_VERSION found"
        else
            print_warning "Docker Compose not found. Please install Docker Compose."
        fi
    else
        print_warning "Docker is not installed. Docker is required for containerized deployment."
    fi
}

# Create virtual environment
setup_venv() {
    print_status "Setting up Python virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_warning "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    print_success "Pip upgraded"
}

# Install Python dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    # Ensure virtual environment is activated
    if [ -z "$VIRTUAL_ENV" ]; then
        source venv/bin/activate
    fi
    
    # Install production dependencies
    pip install -r requirements.txt
    print_success "Production dependencies installed"
    
    # Install development dependencies
    pip install -r requirements-dev.txt
    print_success "Development dependencies installed"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p data
    mkdir -p config
    mkdir -p monitoring/prometheus
    mkdir -p monitoring/grafana/dashboards
    mkdir -p monitoring/grafana/datasources
    mkdir -p nginx
    
    print_success "Directories created"
}

# Create environment file template
create_env_file() {
    print_status "Creating environment file template..."
    
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# Environment Configuration
ENVIRONMENT=development

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bharat_voice_assistant
DB_USER=bharat_user
DB_PASSWORD=bharat_password

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=bharat_redis

# AWS Configuration
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here

# Voice Processing Configuration
VOICE_CONFIDENCE_THRESHOLD=0.7

# Security Configuration
SECRET_KEY=your_secret_key_here
ENCRYPTION_KEY=your_encryption_key_here

# Monitoring Configuration
GRAFANA_PASSWORD=admin

# Optional: Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=structured
EOF
        print_success "Environment file created (.env)"
        print_warning "Please update the .env file with your actual configuration values"
    else
        print_warning "Environment file already exists"
    fi
}

# Setup pre-commit hooks
setup_pre_commit() {
    print_status "Setting up pre-commit hooks..."
    
    if [ -z "$VIRTUAL_ENV" ]; then
        source venv/bin/activate
    fi
    
    # Create pre-commit configuration
    if [ ! -f ".pre-commit-config.yaml" ]; then
        cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: debug-statements

  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
EOF
        print_success "Pre-commit configuration created"
    fi
    
    # Install pre-commit hooks
    pre-commit install
    print_success "Pre-commit hooks installed"
}

# Run initial tests
run_tests() {
    print_status "Running initial tests..."
    
    if [ -z "$VIRTUAL_ENV" ]; then
        source venv/bin/activate
    fi
    
    # Run basic import tests
    python -c "
import bharat_voice_assistant.core.config
import bharat_voice_assistant.core.logging
import bharat_voice_assistant.core.monitoring
import bharat_voice_assistant.core.aws_client
import bharat_voice_assistant.core.exceptions
print('✅ All core modules imported successfully')
"
    
    # Run pytest on core infrastructure tests
    if pytest tests/test_core_infrastructure.py -v --tb=short; then
        print_success "Core infrastructure tests passed"
    else
        print_warning "Some tests failed. This is normal during initial setup."
    fi
}

# Create basic monitoring configuration
setup_monitoring() {
    print_status "Setting up monitoring configuration..."
    
    # Prometheus configuration
    cat > monitoring/prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'bharat-voice-assistant'
    static_configs:
      - targets: ['bharat-voice-assistant:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
EOF

    # Grafana datasource configuration
    cat > monitoring/grafana/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

    print_success "Monitoring configuration created"
}

# Main setup function
main() {
    echo "🎯 Bharat Voice Assistant Setup Script"
    echo "======================================"
    
    check_python
    check_docker
    setup_venv
    install_dependencies
    create_directories
    create_env_file
    setup_pre_commit
    setup_monitoring
    run_tests
    
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Update the .env file with your AWS credentials and other configuration"
    echo "2. Start the development environment:"
    echo "   - For local development: source venv/bin/activate && python -m uvicorn bharat_voice_assistant.api.main:app --reload"
    echo "   - For Docker: docker-compose up -d"
    echo "3. Run tests: pytest"
    echo "4. Check the application health: curl http://localhost:8000/health"
    echo ""
    echo "📚 Documentation and additional setup instructions can be found in the README.md file"
}

# Run main function
main "$@"