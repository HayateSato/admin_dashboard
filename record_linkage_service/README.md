# Record Linkage Service

Generates privacy-preserving bloom-filter hashes from patient personal identifiers and fetches linked ECG data from PostgreSQL (metadata) and InfluxDB (sensor data).

**Port:** `7003`

---

## Responsibility

Patient PII (name, date of birth, gender) is never stored in the database. Instead, on registration the Flutter app hashes those fields into a fixed-length bloom filter and stores only the hash (`unique_key`). This service:

- **Replicates that exact hashing algorithm** so the dashboard can look up a patient by entering their PII
- **Fetches linked data** — once the `unique_key` is known, it queries PostgreSQL for metadata and InfluxDB for raw + anonymized ECG records
- **Exports** the combined result to CSV or JSON

---

## Folder Structure

```
record_linkage_service/
├── server/
│   ├── main.py          Flask REST API (entry point)
│   └── .env.example     Environment variable template
├── core/
│   └── record_linkage.py    Bloom-filter hashing + PostgreSQL + InfluxDB queries
└── requirements.txt
```

---

## The Bloom Filter Algorithm

The `unique_key` is a **500-bit bloom filter** encoded as base64. It is generated identically by:
- This service (Python)
- The Flutter app (Dart)
- The partner registration system (PHP)

The algorithm uses SHA-256 with field-specific seeds:

```
for each field (given_name, family_name, dob, gender):
    for i in 0..24:  (25 hash functions)
        hash = SHA256(f"{global_seed}:{field_seed}:{i}:{value}")
        position = hex_to_int(hash[:15]) % 500
        bit_array[position] = 1

unique_key = base64(bit_array)
```

Seeds are fixed constants shared with the Flutter and PHP implementations — **do not change them**.

---

## Data Sources

| Source | What it provides |
|--------|-----------------|
| **PostgreSQL** `users` table | `unique_key`, `device_id`, `created_at`, `last_session`, `privacy_settings` |
| **InfluxDB** `raw-data` bucket | Raw ECG time-series filtered by `unique_key` tag |
| **InfluxDB** `anonymized-data` bucket | Anonymized ECG time-series with `k_value` and `time_window` tags |

---

## API Endpoints

### `GET /health`
Public.

```json
{ "status": "ok", "service": "record_linkage" }
```

---

### `POST /api/fetch`
Fetch all patient data using personal identifiers (PII → hash → data).

Request body:
```json
{
  "given_name":   "Max",
  "family_name":  "Mustermann",
  "dob":          "1990-05-15",
  "gender":       "male",
  "start_time":   "2025-01-01T00:00:00",
  "end_time":     "2025-12-31T23:59:59",
  "include_raw":        true,
  "include_anonymized": true,
  "limit":        1000
}
```

Response:
```json
{
  "success": true,
  "data": {
    "query_info": {
      "given_name": "Max",
      "family_name": "Mustermann",
      "unique_key": "ABC123...",
      "timestamp": "2025-06-01T10:00:00"
    },
    "metadata": {
      "unique_key": "ABC123...",
      "device_id": "device_xyz",
      "created_at": "2024-01-15T08:00:00",
      "privacy_settings": { "k_value": 10, "time_window": 30 }
    },
    "raw_sensor_data":  { "count": 500, "data": [ ... ] },
    "anonymized_data":  { "count": 500, "data": [ ... ] },
    "summary": {
      "metadata_found": true,
      "raw_data_points": 500,
      "anonymized_data_points": 500,
      "total_data_points": 1000
    }
  }
}
```

---

### `POST /api/fetch-by-key`
Same as above but skips the hashing step — use when you already have the `unique_key`.

Request body:
```json
{
  "unique_key": "ABC123...",
  "start_time": "2025-01-01T00:00:00",
  "end_time":   "2025-12-31T23:59:59",
  "include_raw": true,
  "include_anonymized": true,
  "limit": 1000
}
```

---

### `POST /api/verify-patient`
Check if a patient exists in PostgreSQL by PII. Returns the `unique_key` and metadata if found. Does not return sensor data.

Request body: same as `/api/fetch` (PII fields).

Response:
```json
{ "success": true, "found": true, "unique_key": "ABC123...", "metadata": { ... } }
```

---

### `POST /api/verify-unique-key`
Check if a `unique_key` exists in PostgreSQL.

Request body:
```json
{ "unique_key": "ABC123..." }
```

---

### `POST /api/export/csv`
Export a previously fetched patient data object to a CSV file on the server.

Request body:
```json
{ "patient_data": { ... } }
```

Response:
```json
{ "success": true, "filepath": "./output/linked_records/patient_data_Max_Mustermann_20250601_100000.csv" }
```

---

### `POST /api/export/json`
Same as CSV export but outputs a JSON file.

---

## Configuration

Copy `server/.env.example` to `server/.env`:

| Variable | Default | Required |
|----------|---------|---------|
| `POSTGRES_HOST` | `localhost` | Yes |
| `POSTGRES_PORT` | `5432` | |
| `POSTGRES_DB` | `privacy_umbrella` | |
| `POSTGRES_USER` | `postgres` | |
| `POSTGRES_PASSWORD` | — | **Yes** |
| `INFLUX_URL` | — | **Yes** |
| `INFLUX_TOKEN` | — | **Yes** |
| `INFLUX_ORG` | `mcs-data-labs` | |
| `INFLUX_BUCKET_RAW` | `raw-data` | |
| `INFLUX_BUCKET_ANON` | `anonymized-data` | |
| `LINKED_OUTPUT_DIR` | `./output/linked_records` | |
| `PORT` | `7003` | |
| `FLASK_DEBUG` | `false` | |
| `API_KEY` | *(empty = no auth)* | |

---

## Quickstart (standalone)

```bash
cd record_linkage_service
pip install -r requirements.txt
cp server/.env.example server/.env   # fill in POSTGRES_PASSWORD, INFLUX_TOKEN, INFLUX_URL
python server/main.py
# → http://localhost:7003
```

---

## Dependencies

- PostgreSQL (patient metadata)
- InfluxDB remote instance (`INFLUX_URL`) — for ECG time-series queries
- No MQTT, no gRPC
