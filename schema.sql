-- PostgreSQL Schema for Privacy Umbrella Admin Dashboard
-- This script creates the necessary database tables for patient metadata storage
--
-- IMPORTANT: This script is designed to work with the existing 'pu' database
-- It will NOT modify the existing user_sessions table which contains PII
-- New tables use only hashed unique_key for privacy compliance

-- Connect to existing database
-- Run this script with: psql -U postgres -d pu -f schema.sql
-- Or in psql: \c pu
--             \i schema.sql

-- Users/Patients table -----------------------------------------------------------------------
-- Stores patient metadata linked by hashed unique_key (NO PII stored)
-- This table should be populated by Flutter app on first use
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    unique_key VARCHAR(512) NOT NULL UNIQUE,  -- SHA256 hash of personal identifiers (matches user_sessions)
    device_id VARCHAR(255),                    -- Patient's device identifier
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_session TIMESTAMP,
    privacy_settings JSONB,                    -- JSON object with K-value, time_window, etc.
    status VARCHAR(50) DEFAULT 'active',       -- active, inactive, archived
    notes TEXT
);

-- Create index on unique_key for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_unique_key ON users(unique_key);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_last_session ON users(last_session);

-- Admin users table -----------------------------------------------------------------------
-- Stores admin dashboard users (separate from patients)
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,     -- SHA256 hashed password
    role VARCHAR(50) DEFAULT 'user',          -- admin, user, auditor
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create default admin user (password: admin123 - CHANGE IN PRODUCTION!)
INSERT INTO admin_users (username, password_hash, role)
VALUES ('admin',
        '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',  -- SHA256 of 'admin123'
        'admin')
ON CONFLICT (username) DO NOTHING;

-- -- Sessions table -----------------------------------------------------------------------
-- -- Track patient sessions for analytics (NO PII stored)
-- CREATE TABLE IF NOT EXISTS sessions (
--     id SERIAL PRIMARY KEY,
--     unique_key VARCHAR(512) NOT NULL,
--     session_id VARCHAR(255),                  -- Links to user_sessions.session_id if needed
--     session_start TIMESTAMP NOT NULL,
--     session_end TIMESTAMP,
--     duration_seconds INTEGER,
--     data_points_collected INTEGER,
--     anonymization_applied BOOLEAN DEFAULT FALSE,
--     k_value INTEGER,
--     time_window INTEGER,
--     FOREIGN KEY (unique_key) REFERENCES users(unique_key) ON DELETE CASCADE
-- );

-- CREATE INDEX IF NOT EXISTS idx_sessions_unique_key ON sessions(unique_key);
-- CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(session_start);

-- Privacy policies table -----------------------------------------------------------------------
-- Store privacy policy configurations (NO PII stored)
CREATE TABLE IF NOT EXISTS privacy_policies (
    id SERIAL PRIMARY KEY,
    unique_key VARCHAR(512) NOT NULL,
    k_value INTEGER NOT NULL DEFAULT 5,
    time_window INTEGER NOT NULL DEFAULT 5,  -- seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),                  -- admin username who created/updated
    is_remote BOOLEAN DEFAULT FALSE,          -- TRUE if set remotely by admin
    FOREIGN KEY (unique_key) REFERENCES users(unique_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policies_unique_key ON privacy_policies(unique_key);

-- -- Audit log table -----------------------------------------------------------------------
-- -- Track all admin actions for compliance
-- CREATE TABLE IF NOT EXISTS audit_logs (
--     id SERIAL PRIMARY KEY,
--     timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     user_id VARCHAR(100) NOT NULL,
--     action VARCHAR(255) NOT NULL,
--     ip_address VARCHAR(45),
--     details JSONB,
--     success BOOLEAN DEFAULT TRUE
-- );

-- CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
-- CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);

-- -- Federated learning rounds table -----------------------------------------------------------------------
-- -- Track FL training rounds
-- CREATE TABLE IF NOT EXISTS fl_rounds (
--     id SERIAL PRIMARY KEY,
--     round_number INTEGER NOT NULL,
--     start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     end_time TIMESTAMP,
--     status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed
--     clients_participated INTEGER DEFAULT 0,
--     global_model_accuracy FLOAT,
--     notes TEXT
-- );

-- CREATE INDEX IF NOT EXISTS idx_fl_rounds_status ON fl_rounds(status);
-- CREATE INDEX IF NOT EXISTS idx_fl_rounds_start ON fl_rounds(start_time);

-- -- Anonymization jobs table -----------------------------------------------------------------------
-- -- Track central anonymization batch jobs
-- CREATE TABLE IF NOT EXISTS anonymization_jobs (
--     id SERIAL PRIMARY KEY,
--     job_id VARCHAR(100) NOT NULL UNIQUE,
--     k_value INTEGER NOT NULL,
--     time_window INTEGER NOT NULL,
--     start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     end_time TIMESTAMP,
--     status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed
--     records_processed INTEGER,
--     error_message TEXT
-- );

-- CREATE INDEX IF NOT EXISTS idx_anon_jobs_status ON anonymization_jobs(status);
-- CREATE INDEX IF NOT EXISTS idx_anon_jobs_start ON anonymization_jobs(start_time);

-- Sample data insertion for testing -----------------------------------------------------------------------
-- Insert a test patient record
INSERT INTO users (unique_key, device_id, privacy_settings, last_session)
VALUES (
    '0000000000000000000008008000000000000000000000000000000100000000',  -- SHA256 of 'Patient_1|Test|1980-10-31|female'
    'test_device_001',
    '{"k_value": 5, "time_window": 5, "auto_anonymize": true}',
    CURRENT_TIMESTAMP
)
ON CONFLICT (unique_key) DO NOTHING;

-- Insert corresponding privacy policy
INSERT INTO privacy_policies (unique_key, k_value, time_window)
VALUES (
    '0000000000000000000008008000000000000000000000000000000100000000',
    5,
    5
)
ON CONFLICT DO NOTHING;

-- Grant permissions (adjust as needed for your PostgreSQL setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO privacy_umbrella_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO privacy_umbrella_user;

COMMENT ON TABLE users IS 'Patient metadata linked by SHA256-hashed unique_key';
COMMENT ON TABLE admin_users IS 'Admin dashboard users with role-based access';
-- COMMENT ON TABLE sessions IS 'Patient session tracking for analytics';
COMMENT ON TABLE privacy_policies IS 'Privacy policy configurations per patient';
-- COMMENT ON TABLE audit_logs IS 'Audit trail of all admin actions';
-- COMMENT ON TABLE fl_rounds IS 'Federated learning training round history';
-- COMMENT ON TABLE anonymization_jobs IS 'Central anonymization batch job tracking';
