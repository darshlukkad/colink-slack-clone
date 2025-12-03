# Use Python 3.11 slim image
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
COPY backend/services/reactions/requirements.txt ./services/reactions/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r services/reactions/requirements.txt

# Copy shared module
COPY backend/shared/ ./shared/

# Copy service code
COPY backend/services/reactions/ ./services/reactions/

# Expose port
EXPOSE 8006

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8006/health')"

# Run the application
CMD ["uvicorn", "services.reactions.main:app", "--host", "0.0.0.0", "--port", "8006"]
