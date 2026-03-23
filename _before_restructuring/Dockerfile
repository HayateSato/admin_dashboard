# Privacy Umbrella Admin Dashboard Dockerfile
# Multi-stage build for optimized production image

# ============================================================================
# Stage 1: Builder - Install dependencies
# ============================================================================
FROM python:3.11-slim as builder

LABEL maintainer="MCS Smart Data Team"
LABEL description="Privacy Umbrella Admin Dashboard - Flask Application"

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies in a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Production - Minimal runtime image
# ============================================================================
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash dashboarduser && \
    chown -R dashboarduser:dashboarduser /app

# Create necessary directories
RUN mkdir -p /app/logs /app/exports /app/anonymization_output && \
    chown -R dashboarduser:dashboarduser /app/logs /app/exports /app/anonymization_output

# Copy application code
COPY --chown=dashboarduser:dashboarduser . /app/

# Switch to non-root user
USER dashboarduser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/login || exit 1

# Start Flask application
CMD ["python", "app.py"]
