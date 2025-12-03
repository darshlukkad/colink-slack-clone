# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared code first
COPY backend/shared/ /app/shared/

# Copy service requirements
COPY backend/services/channel/requirements.txt /app/services/channel/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/services/channel/requirements.txt

# Copy service code
COPY backend/services/channel/ /app/services/channel/

# Set Python path to include /app so 'shared' module can be imported
ENV PYTHONPATH=/app

# Set working directory to service
WORKDIR /app/services/channel

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Run the service
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
