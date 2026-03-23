# Patient Registry Service

Manages registered patient data stored in PostgreSQL and sends real-time privacy-settings commands to patient devices via MQTT.

**Port:** `7001`

---

## Responsibility

This service is the single source of truth for:
- Which patients are registered in the system
- Their current privacy settings (k-value, time window, auto-anonymize)
- Whether remote anonymization is enabled for each patient
- Publishing settings changes to patient devices (Flutter app) over MQTT

It does **not** handle sensor data — that lives in InfluxDB and is owned by the Record Linkage Service.

---

## Folder Structure

```
patient_registry_service/
├── server/
│   ├── main.py          Flask REST API (entry point)
│   └── .env.example     Environment variable template
├── core/
│   ├── patient_manager.py   PostgreSQL queries for patient + policy tables
│   └── mqtt_manager.py      MQTT publish to patient devices
└── requirements.txt
```

### What `core/` contains

| File | Purpose |
|------|---------|
| `patient_manager.py` | Reads and writes the `users` and `privacy_policies` PostgreSQL tables |
| `mqtt_manager.py` | Connects to the Mosquitto broker and publishes JSON commands to patient devices |

---

## Database Tables Used

| Table | Operations |
|-------|-----------|
| `users` | SELECT (list, single lookup), UPDATE (privacy_settings) |
| `privacy_policies` | SELECT (remote anon status), INSERT / UPDATE (upsert on conflict) |

No tables are created by this service — they are defined in [db/schema.sql](../db/schema.sql).

---

## MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `anonymization/commands` | Publish → device | Privacy settings update (k_value, time_window, auto_anonymize) |
| `anonymization/remote_anon/<unique_key>` | Publish → device | Enable / disable remote anonymization |
| `anonymization/responses` | Subscribe ← device | Acknowledgment from Flutter app |
| `anonymization/+/ack` | Subscribe ← device | Legacy acknowledgment format |

Message format sent to devices:
```json
{
  "unique_key": "...",
  "kValue": 10,
  "timeWindow": 30,
  "autoAnonymize": false,
  "timestamp": "2025-01-01T12:00:00",
  "source": "admin_dashboard"
}
```

---

## API Endpoints

### `GET /health`
Public. Returns service status and MQTT connection state.

```json
{ "status": "ok", "service": "patient_registry", "mqtt_connected": true }
```

---

### `GET /api/patients`
Returns all registered patients with privacy settings and consent info.

```json
{
  "success": true,
  "patients": [
    {
      "id": 1,
      "unique_key": "ABC123...",
      "unique_key_short": "ABC123...(truncated)",
      "device_id": "device_xyz",
      "last_session": "2025-01-01T10:00:00",
      "privacy_settings": { "k_value": 10, "time_window": 30, "auto_anonymize": false },
      "k_value": 10,
      "time_window": 30,
      "auto_anonymize": false,
      "remote_anon_enabled": true,
      "consent_given": true
    }
  ]
}
```

---

### `GET /api/patients/<unique_key>`
Returns a single patient by their unique key.

**404** if not found.

---

### `POST /api/patients/<unique_key>/settings`
Updates privacy settings in PostgreSQL and publishes the new values to the patient's device via MQTT.

Request body:
```json
{ "k_value": 10, "time_window": 30, "auto_anonymize": false }
```

Response:
```json
{ "success": true, "db_updated": true, "mqtt_published": true, "settings": { ... } }
```

---

### `POST /api/patients/<unique_key>/toggle-remote-anon`
Enables or disables remote anonymization for a patient. Updates the `privacy_policies` table and notifies the device.

Request body:
```json
{ "enabled": true }
```

---

### `GET /api/patients/remote-anon-enabled`
Returns only patients who currently have remote anonymization enabled.

---

### `GET /api/mqtt/status`
Returns MQTT broker connection details.

```json
{
  "success": true,
  "status": {
    "connected": true,
    "broker_host": "localhost",
    "broker_port": 1883,
    "topic_prefix": "anonymization",
    "pending_acks": 0
  }
}
```

---

## Configuration

Copy `server/.env.example` to `server/.env` and fill in:

| Variable | Default | Required |
|----------|---------|---------|
| `POSTGRES_HOST` | `localhost` | Yes |
| `POSTGRES_PORT` | `5432` | |
| `POSTGRES_DB` | `privacy_umbrella` | |
| `POSTGRES_USER` | `postgres` | |
| `POSTGRES_PASSWORD` | — | **Yes** |
| `MQTT_BROKER_HOST` | `localhost` | Yes |
| `MQTT_BROKER_PORT` | `1883` | |
| `PORT` | `7001` | |
| `FLASK_DEBUG` | `false` | |
| `API_KEY` | *(empty = no auth)* | |

When running in Docker, `POSTGRES_HOST` becomes `postgres` and `MQTT_BROKER_HOST` becomes `mosquitto` (the container service names).

---

## Quickstart (standalone)

```bash
cd patient_registry_service
pip install -r requirements.txt
cp server/.env.example server/.env   # fill in POSTGRES_PASSWORD
python server/main.py
# → http://localhost:7001
```

---

## Dependencies

- PostgreSQL (must be running and schema applied from `db/schema.sql`)
- Mosquitto MQTT broker (optional — service starts without it, MQTT publishes are skipped if not connected)
