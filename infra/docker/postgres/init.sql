-- =============================================================================
-- Sentinel PostgreSQL Initialization
-- Runs once when the PostgreSQL container is first created.
-- =============================================================================

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Enable pgcrypto for UUID generation at DB level
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Set default timezone to UTC (Django expects this)
ALTER DATABASE sentinel_db SET timezone TO 'UTC';

-- Configure pg_stat_statements
ALTER SYSTEM SET pg_stat_statements.max = 10000;
ALTER SYSTEM SET pg_stat_statements.track = 'all';

-- Optimize for development (NOT suitable for production)
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s
ALTER SYSTEM SET log_checkpoints = on;
