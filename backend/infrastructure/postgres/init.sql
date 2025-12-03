-- Colink PostgreSQL Initialization Script
-- This script runs on first database creation

-- Create keycloak database for Keycloak
CREATE DATABASE keycloak;

-- Enable required extensions for main database
\c colink;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- Create application user (if running as different user in production)
-- Note: In production, use separate users with limited permissions per service

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE colink TO colink;

-- Set timezone
SET timezone = 'UTC';

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Colink database initialized successfully';
END $$;
