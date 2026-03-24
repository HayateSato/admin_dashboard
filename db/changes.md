**Summary of what changed and why:**

| Change | Reason |
| --- | --- |
| Removed `users.status`, `users.notes` | No service reads or writes them |
| Added `users.updated_at` | `patient_manager.py` tries to SET it on every privacy settings update |
| Removed `privacy_policies.k_value`, `privacy_policies.time_window` | Duplicate — values already live in `users.privacy_settings` JSONB; no service reads them from `privacy_policies` |
| Removed `privacy_policies.updated_at` | Duplicate of `last_updated`; service code uses `last_updated` |
| Removed `sessions` table | Patient ECG sessions live in InfluxDB (`session_id` tag), not Postgres |
| Removed `fl_rounds` table | FL state managed in `global_model_latest.json` |
| Removed `anonymization_jobs` table | Managed in-memory by `central_anonymization_api` |
| Kept `audit_logs` | Clear compliance value — easy to add writes later |