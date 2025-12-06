# Frontend Dockerfile for Next.js application
FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy package files
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

# Accept build arguments for Next.js public environment variables
ARG NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:8080
ARG NEXT_PUBLIC_KEYCLOAK_REALM=colink
ARG NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=web-app
ARG NEXT_PUBLIC_AUTH_PROXY_URL=http://localhost:8001
ARG NEXT_PUBLIC_CHANNEL_SERVICE_URL=http://localhost:8003
ARG NEXT_PUBLIC_MESSAGE_SERVICE_URL=http://localhost:8002
ARG NEXT_PUBLIC_THREADS_SERVICE_URL=http://localhost:8005
ARG NEXT_PUBLIC_REACTIONS_SERVICE_URL=http://localhost:8006
ARG NEXT_PUBLIC_FILES_SERVICE_URL=http://localhost:8007
ARG NEXT_PUBLIC_NOTIFICATIONS_SERVICE_URL=http://localhost:8008
ARG NEXT_PUBLIC_WEBSOCKET_URL=http://localhost:8009

# Set environment variables for build (Next.js bakes these in at build time)
ENV NEXT_PUBLIC_KEYCLOAK_URL=$NEXT_PUBLIC_KEYCLOAK_URL
ENV NEXT_PUBLIC_KEYCLOAK_REALM=$NEXT_PUBLIC_KEYCLOAK_REALM
ENV NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=$NEXT_PUBLIC_KEYCLOAK_CLIENT_ID
ENV NEXT_PUBLIC_AUTH_PROXY_URL=$NEXT_PUBLIC_AUTH_PROXY_URL
ENV NEXT_PUBLIC_CHANNEL_SERVICE_URL=$NEXT_PUBLIC_CHANNEL_SERVICE_URL
ENV NEXT_PUBLIC_MESSAGE_SERVICE_URL=$NEXT_PUBLIC_MESSAGE_SERVICE_URL
ENV NEXT_PUBLIC_THREADS_SERVICE_URL=$NEXT_PUBLIC_THREADS_SERVICE_URL
ENV NEXT_PUBLIC_REACTIONS_SERVICE_URL=$NEXT_PUBLIC_REACTIONS_SERVICE_URL
ENV NEXT_PUBLIC_FILES_SERVICE_URL=$NEXT_PUBLIC_FILES_SERVICE_URL
ENV NEXT_PUBLIC_NOTIFICATIONS_SERVICE_URL=$NEXT_PUBLIC_NOTIFICATIONS_SERVICE_URL
ENV NEXT_PUBLIC_WEBSOCKET_URL=$NEXT_PUBLIC_WEBSOCKET_URL
ENV NEXT_TELEMETRY_DISABLED=1

# Build the application
RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Install wget for healthcheck
RUN apk add --no-cache wget

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Create public directory (will be empty if source doesn't have one)
RUN mkdir -p public

# Set the correct permission for prerender cache
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Automatically leverage output traces to reduce image size
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Run the application
CMD ["node", "server.js"]
