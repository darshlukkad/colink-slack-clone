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

# Copy requirements first for better caching
COPY backend/services/files-service/requirements.txt ./services/files-service/

# Install Python dependencies
RUN pip install --no-cache-dir -r services/files-service/requirements.txt

# Copy shared module
COPY backend/shared/ /app/shared

# Copy service code
COPY backend/services/files-service /app/services/files-service

# Expose port
EXPOSE 8007

# Run the application
CMD ["uvicorn", "services.files-service.main:app", "--host", "0.0.0.0", "--port", "8007"]
