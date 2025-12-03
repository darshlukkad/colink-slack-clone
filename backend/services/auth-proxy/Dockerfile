# Auth Proxy Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY backend/requirements.txt backend/requirements-dev.txt ./
COPY backend/services/auth-proxy/requirements.txt ./services/auth-proxy/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r services/auth-proxy/requirements.txt

# Copy shared module
COPY backend/shared/ ./shared/

# Copy auth-proxy service
COPY backend/services/auth-proxy/ ./services/auth-proxy/

# Set Python path to include app directory
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/health')"

# Run the application
CMD ["uvicorn", "services.auth-proxy.main:app", "--host", "0.0.0.0", "--port", "8001"]
