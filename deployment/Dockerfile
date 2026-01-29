# Multi-stage Docker build for Bharat Voice Assistant
# Stage 1: Build stage with all dependencies
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for building
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    libasound2-dev \
    portaudio19-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim as runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    libasound2 \
    portaudio19-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create non-root user for security
RUN groupadd -r bharat && useradd -r -g bharat -d /app -s /bin/bash bharat

# Create application directory and set ownership
RUN mkdir -p /app/logs /app/data /app/config && \
    chown -R bharat:bharat /app

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=bharat:bharat bharat_voice_assistant/ ./bharat_voice_assistant/
COPY --chown=bharat:bharat config/ ./config/
COPY --chown=bharat:bharat scripts/ ./scripts/

# Copy configuration files
COPY --chown=bharat:bharat pytest.ini ./
COPY --chown=bharat:bharat requirements.txt ./

# Create startup script
COPY --chown=bharat:bharat <<EOF /app/start.sh
#!/bin/bash
set -e

# Wait for database if DB_HOST is set
if [ -n "\$DB_HOST" ]; then
    echo "Waiting for database at \$DB_HOST:\$DB_PORT..."
    while ! nc -z \$DB_HOST \$DB_PORT; do
        sleep 1
    done
    echo "Database is ready!"
fi

# Run database migrations if needed
if [ "\$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    python -m alembic upgrade head
fi

# Start the application
echo "Starting Bharat Voice Assistant..."
exec "\$@"
EOF

RUN chmod +x /app/start.sh

# Switch to non-root user
USER bharat

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Set entrypoint and default command
ENTRYPOINT ["/app/start.sh"]
CMD ["python", "-m", "uvicorn", "bharat_voice_assistant.api.main:app", "--host", "0.0.0.0", "--port", "8000"]