# Frontend Dockerfile for Next.js application
FROM node:20-alpine

WORKDIR /app

# Install curl for healthcheck
RUN apk add --no-cache curl

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy application files
COPY frontend/ .

# Expose port
EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

# Start the development server
CMD ["npm", "run", "dev"]
