-- Privacy Umbrella — Seed Data
-- Auto-applied by Docker on first run (docker-entrypoint-initdb.d/02_seed.sql)
-- Applied after schema.sql. Safe to re-run (ON CONFLICT DO NOTHING).

-- ── Test patients ─────────────────────────────────────────────────────────────
-- Real unique_keys from the original database (bloom-filter hashes, no PII).

INSERT INTO users (unique_key, device_id, created_at, last_session, privacy_settings)
VALUES
    (
        '575e50b792ce26d6b7e7b155fbd7e502a96091b659ba226d7c17a96481561935',
        'test_device_001',
        '2025-11-06 14:36:39.214089',
        '2025-11-06 14:36:39.214089',
        '{"k_value": 5, "time_window": 5, "auto_anonymize": true}'
    ),
    (
        '0000000000000000000008008000000000000000000000000000000100000000',
        '6c:1d:eb:06:57:9c',
        '2025-11-09 18:05:40.038288',
        '2025-11-11 14:09:58.396988',
        '{"k_value": 3, "time_window": 30, "auto_anonymize": true}'
    ),
    (
        '0000004000000000000000000080000000010000000000000000000000000000',
        '6C:1D:EB:06:57:9C',
        '2025-11-13 11:42:30.287983',
        '2025-11-13 13:05:15.180567',
        '{"k_value": 5, "time_window": 5, "auto_anonymize": true}'
    )
ON CONFLICT (unique_key) DO NOTHING;

-- ── Corresponding privacy policies ────────────────────────────────────────────
INSERT INTO privacy_policies (unique_key, is_remote, created_at, last_updated)
VALUES
    (
        '575e50b792ce26d6b7e7b155fbd7e502a96091b659ba226d7c17a96481561935',
        FALSE,
        '2025-11-06 14:36:39.218844',
        '2025-11-06 14:36:39.218844'
    ),
    (
        '0000004000000000000000000080000000010000000000000000000000000000',
        TRUE,
        '2025-11-13 13:04:49.954001',
        '2025-11-13 13:04:49.954002'
    )
ON CONFLICT DO NOTHING;
