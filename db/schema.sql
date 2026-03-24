-- Privacy Umbrella — PostgreSQL Schema
-- Auto-applied by Docker on first run (docker-entrypoint-initdb.d/01_schema.sql)
-- Run manually: psql -U postgres -d privacy_umbrella -f schema.sql

-- ── Users / Patients ──────────────────────────────────────────────────────────
-- No PII stored. Patients are identified only by their bloom-filter unique_key.
--
-- Written by: Flutter app (on registration)
-- Read/updated by: patient_registry_service, record_linkage_service
CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    unique_key       VARCHAR(512) NOT NULL UNIQUE,  -- base64 bloom-filter hash (500-bit, matches Flutter/PHP)
    device_id        VARCHAR(255),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_session     TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    privacy_settings JSONB                           -- {"k_value": 5, "time_window": 30, "auto_anonymize": true}
);

CREATE INDEX IF NOT EXISTS idx_users_unique_key   ON users(unique_key);
CREATE INDEX IF NOT EXISTS idx_users_last_session ON users(last_session);

COMMENT ON TABLE  users              IS 'Patient metadata — no PII, linked by bloom-filter unique_key';
COMMENT ON COLUMN users.unique_key   IS 'Base64-encoded 500-bit bloom filter. Must match Flutter + PHP implementations.';
COMMENT ON COLUMN users.privacy_settings IS 'Denormalised copy of k_value/time_window/auto_anonymize for fast reads.';

-- ── Privacy Policies ──────────────────────────────────────────────────────────
-- One row per patient. Tracks remote-management consent and who controls settings.
-- k_value / time_window are NOT stored here — they live in users.privacy_settings JSONB.
--
-- Written/updated by: patient_registry_service (admin changes settings or toggles remote anon)
-- Read by: patient_registry_service
CREATE TABLE IF NOT EXISTS privacy_policies (
    id                SERIAL PRIMARY KEY,
    unique_key        VARCHAR(512) NOT NULL,
    is_remote         BOOLEAN   DEFAULT FALSE,       -- TRUE = admin is controlling settings remotely
    consent_given     BOOLEAN   DEFAULT FALSE,       -- patient consented to remote management
    consent_timestamp TIMESTAMP,                     -- when consent was given
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by        VARCHAR(100),                  -- admin username who last changed this
    FOREIGN KEY (unique_key) REFERENCES users(unique_key) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_privacy_policies_unique_key ON privacy_policies(unique_key);

COMMENT ON TABLE  privacy_policies           IS 'Remote-management consent and admin control flag per patient';
COMMENT ON COLUMN privacy_policies.is_remote IS 'TRUE means admin enabled remote anonymization for this patient';

-- ── Audit Logs ────────────────────────────────────────────────────────────────
-- Admin action log for compliance. Not currently written by any service —
-- add writes to patient_registry_service or dashboard when audit trail is needed.
CREATE TABLE IF NOT EXISTS audit_logs (
    id         SERIAL PRIMARY KEY,
    timestamp  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    user_id    VARCHAR(100) NOT NULL,    -- admin username
    action     VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    details    JSONB,
    success    BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_user      ON audit_logs(user_id);

COMMENT ON TABLE audit_logs IS 'Admin action audit trail — not yet written by any service';

-- ── Removed tables (compared to old schema) ───────────────────────────────────
-- sessions        → ECG session data lives in InfluxDB (raw-data bucket, session_id tag)
-- fl_rounds       → FL state is managed in grpc/global_model_latest.json
-- anonymization_jobs → Managed in-memory by central_anonymization_api
