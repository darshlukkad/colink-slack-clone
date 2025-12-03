FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY backend/services/websocket/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY backend/services/websocket/ /app/

# Expose WebSocket port
EXPOSE 8009

# Run the application
CMD ["python", "-m", "uvicorn", "main:socket_app", "--host", "0.0.0.0", "--port", "8009", "--reload"]
