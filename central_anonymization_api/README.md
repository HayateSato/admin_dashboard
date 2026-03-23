# Central Anonymization API

A standalone REST API service that exposes the ECG k-anonymity algorithm used by the admin dashboard. Any client — Flutter app, Python script, IoT device backend, or external service — can send raw ECG records and receive back anonymized records.

---

## How It Fits in the System

```
Flutter app / IoT device
        │  HTTPS
        ▼
central_anonymization_api   ← this component
  server/main.py (Flask)
        │  imports
        ▼
  core/  (k-anonymity algorithm)
        │  reads
        ▼
  smarko_hierarchy_ecg.csv   (ECG value → hierarchy ranges)
```

This service is **independent** of the main admin dashboard. It can run as its own Docker container or as a plain Python process. It does **not** connect to a database — it receives records over HTTP and returns anonymized records in the same HTTP response.

---

## Folder Structure

```
central_anonymization_api/
├── server/
│   ├── main.py          Flask REST API server (entry point)
│   └── .env.example     Environment variable template
├── client/
│   ├── anon_client.py   Reusable Python client class
│   └── example_usage.py Runnable demo showing all API calls
├── core/                Algorithm files (copied from admin dashboard)
│   ├── level_hierarchy_anonymizer.py   k-anonymity engine
│   ├── mean_imputation.py              range → imputed float value
│   └── ecg_validator.py               zero / out-of-range rules
└── requirements.txt
```

### What `core/` contains

The three files in `core/` are exact copies of the algorithm used inside the admin dashboard (`modules/utils_central_anon/`). They use only Python standard library — no external packages. If the algorithm is updated in the admin dashboard, copy the updated files here too.

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp server/.env.example server/.env
# Edit server/.env if needed (see Configuration section below)
```

### 3. Start the server

```bash
cd server
python main.py
# Listening on http://0.0.0.0:6000
```

### 4. Test with the example client

```bash
cd client
python example_usage.py
```

---

## API Endpoints

### `GET /health`
Public — no authentication required.

**Response:**
```json
{
  "status": "ok",
  "hierarchy_loaded": true,
  "hierarchy_size": 5001,
  "default_k_value": 10
}
```

---

### `GET /api/v1/info`
Returns algorithm details and server configuration. Requires auth if `API_KEY` is set.

---

### `POST /api/v1/anonymize`
Anonymize a batch of ECG records.

**Request body:**
```json
{
  "records": [
    {
      "timestamp":  1700000000000,
      "ecg":        150,
      "unique_key": "patient_abc"
    }
  ],
  "k_value":            10,
  "batch_size_seconds": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `records` | array | yes | ECG records (see below) |
| `k_value` | int | no | Privacy level: `5`, `10`, `20`, or `50` (default: server setting) |
| `batch_size_seconds` | int | no | Time-window for grouping records (default: `5`) |

Each record must have:
- `timestamp` — milliseconds since epoch
- `ecg` — integer value, valid range −2500 to 2500

Any extra fields (`unique_key`, `deviceAddress`, etc.) are preserved and returned unchanged.

**Response:**
```json
{
  "success": true,
  "anonymized_records": [
    {
      "timestamp":            1700000000000,
      "ecg":                  148.5,
      "ecg_original":         150,
      "ecg_anonymized_range": "147;151",
      "assigned_level":       2,
      "was_anonymized":       true,
      "unique_key":           "patient_abc"
    }
  ],
  "stats": {
    "total_input":        100,
    "total_output":       100,
    "k_value_used":       10,
    "batch_size_seconds": 5,
    "batches_processed":  3,
    "validation": {
      "total_records":          100,
      "valid_for_anonymization": 96,
      "zero_ecg_skipped":        2,
      "clamped_ecg_skipped":     1,
      "workout_compact_forced":  1
    }
  }
}
```

**Output fields per record:**

| Field | Description |
|-------|-------------|
| `ecg` | Final usable value after anonymization + mean imputation |
| `ecg_original` | Raw input ECG value |
| `ecg_anonymized_range` | Hierarchy range (e.g. `"147;151"`) or `"*"` if suppressed |
| `assigned_level` | Hierarchy level used (1 = finest, 8 = root `*`, 0 = not anonymized) |
| `was_anonymized` | `true` if k-anonymity was applied, `false` if record was skipped by validation |

---

## Algorithm Summary

The algorithm is **level-by-level k-anonymity** using a predefined ECG hierarchy.

1. **Validate** — records with ECG = 0 or outside [−2500, 2500] are flagged as `was_anonymized: false` and passed through unchanged.
2. **Batch** — records are grouped into time windows of `batch_size_seconds`. Each window is anonymized independently.
3. **Anonymize** — within each batch, records are sorted by ECG value. Starting at hierarchy level 1 (finest), groups that have ≥ k records satisfy k-anonymity and are locked in. Remaining records move to level 2, and so on up to level 8. Any records still unsatisfied at level 8 are suppressed (`*`).
4. **Impute** — ranges (e.g. `"147;151"`) are replaced with their midpoint. Suppressed values (`*`) are replaced with the batch mean.

**k-value guide:**

| k | Privacy level | Utility |
|---|---------------|---------|
| 5 | Moderate | High |
| 10 | High (default) | Good |
| 20 | Very high | Reduced |
| 50 | Maximum | Low |

---

## Using the Python Client

Copy `client/anon_client.py` into any Python project:

```python
from anon_client import CentralAnonClient

client = CentralAnonClient(
    base_url='https://your-server:6000',
    api_key='your-api-key',   # omit if no API_KEY is set on the server
    verify_ssl=False,         # False = self-signed cert; True = Let's Encrypt
)

# Health check
print(client.is_healthy())

# Anonymize
records = [
    {'timestamp': 1700000000000, 'ecg': 150, 'unique_key': 'patient_abc'},
    {'timestamp': 1700000000010, 'ecg': -230, 'unique_key': 'patient_abc'},
]
result = client.anonymize(records, k_value=10)
print(result['anonymized_records'])
```

---

## Configuration

All settings are in `server/.env` (copy from `server/.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HIERARCHY_CSV_PATH` | auto-detected | Absolute path to `smarko_hierarchy_ecg.csv`. Auto-resolves to the admin dashboard's copy when running inside this repo. |
| `DEFAULT_K_VALUE` | `10` | k used when the client doesn't specify one. Must be `5`, `10`, `20`, or `50`. |
| `API_KEY` | *(empty)* | If set, every request must include `X-API-Key: <value>` header. Leave empty for open access on a private network. |
| `PORT` | `6000` | Port the server listens on. |
| `FLASK_DEBUG` | `false` | Set `true` only in development. |

---

## Deploying Standalone (without the admin dashboard repo)

If deploying this service on its own machine:

1. Copy the entire `central_anonymization_api/` folder.
2. Copy `smarko_hierarchy_ecg.csv` from `modules/utils_central_anon/anonymizer/` alongside it.
3. Set `HIERARCHY_CSV_PATH` in `server/.env` to the absolute path of the CSV.
4. Install deps and start: `pip install -r requirements.txt && python server/main.py`.

---

## HTTPS / TLS

The server itself runs plain HTTP. For HTTPS, place it behind nginx the same way the admin dashboard is:

**Self-signed cert (development):**
- Browser will show a warning — this is expected and harmless on a private network.
- Set `verify_ssl=False` in the Python client.

**Let's Encrypt (production):**
- Requires a domain name pointing at your server.
- Run Certbot to obtain `fullchain.pem` + `privkey.pem`.
- Add an nginx `server { listen 443 ssl; ... proxy_pass http://central_anon_api:6000; }` block.
- Set `verify_ssl=True` in the client.
