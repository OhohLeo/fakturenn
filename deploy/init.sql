-- Fakturenn Database Initialization
-- This script is automatically executed when PostgreSQL starts

-- Create database if not exists
-- Note: The database is already created by POSTGRES_DB environment variable

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schema from migrations
-- In production, use Alembic migrations instead
-- This is a placeholder for development/testing

COMMENT ON DATABASE fakturenn IS 'Fakturenn - Invoice automation and accounting integration';
