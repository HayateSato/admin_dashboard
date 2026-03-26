# Client Guide — Using the Anonymization API

---

## Important Context: This Algorithm Was Built for Mobile, Not a Server

The anonymization algorithm in `core/` was specifically designed to run **inside a mobile app** on a resource-constrained device. It requires no network connection, no database, and no server to do its job. The entire `core/` folder — three Python files and one CSV — is a self-contained, portable implementation.

In the actual PrivacyUmbrella system:

```
Wearable sensor
    │ raw ECG stream
    ▼
Mobile app  ← core/ algorithm runs here, entirely on-device
    │ anonymized ECG only (raw data never leaves the device)
    ▼
Remote server / database
```

The same algorithm has been implemented in:
- **Python** — this repository (`core/`)
- **Dart** — inside the Flutter mobile app (not shared, proprietary)
- **PHP** — inside the partner registration system (not shared, proprietary)

All three implementations use identical hierarchy data and parameters to ensure consistent anonymization across platforms.

---

## Why This Repo Uses Flask

The `server/` folder wraps the algorithm in a Flask web server **only for demonstration purposes**. Flask makes it easy to show the algorithm running interactively in a browser. It does not reflect how the algorithm is deployed in production.

Think of Flask here as a "display case" — it lets you interact with the algorithm through a web interface without installing anything except Python.

---

## Using This as an API Server

Although anonymization is designed to run locally on the device, there may be scenarios where you want to host the algorithm as a central API — for example, to process data from multiple sources in batch, or to integrate with a pipeline that cannot run Python locally.

In that case, you can host `server/main.py` and call it over HTTP.

### Authentication

Set the `API_KEY` environment variable on the server. Then include it in every request:

```
X-API-Key: your-api-key-here
```

Leave `API_KEY` empty to run without authentication (only appropriate on a private internal network).

---

### Available Endpoints

#### `GET /health`
Check whether the server is running and the hierarchy is loaded. No authentication required.

```bash
curl http://localhost:8080/health
```

```json
{
  "status": "ok",
  "hierarchy_loaded": true,
  "hierarchy_size": 5001,
  "default_k_value": 5
}
```

---

#### `POST /api/v1/anonymize`
Anonymize a batch of ECG records. Returns anonymized values with per-record metadata.

```bash
curl -X POST http://localhost:8080/api/v1/anonymize \
  -H "Content-Type: application/json" \
  -d '{
    "records": [
      {"timestamp": 1700000000000, "ecg": 150},
      {"timestamp": 1700000000008, "ecg": -230},
      {"timestamp": 1700000000016, "ecg": 88}
    ],
    "k_value": 10,
    "batch_size_seconds": 5
  }'
```

**Request fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `records` | array | yes | ECG records — each needs `timestamp` (ms) and `ecg` (integer μV) |
| `k_value` | int | no | One of: 2, 3, 5, 10, 20, 30. Default: server setting |
| `batch_size_seconds` | int | no | Tumbling window duration. Default: 5 |

**Response:**

```json
{
  "success": true,
  "anonymized_records": [
    {
      "timestamp": 1700000000000,
      "ecg": 149.5,
      "ecg_original": 150,
      "ecg_anonymized_range": "149;150",
      "assigned_level": 1,
      "was_anonymized": true
    }
  ],
  "stats": {
    "total_input": 3,
    "total_output": 3,
    "k_value_used": 10,
    "batch_size_seconds": 5,
    "batches_processed": 1,
    "validation": {
      "total_records": 3,
      "valid_for_anonymization": 3,
      "zero_ecg_skipped": 0,
      "clamped_ecg_skipped": 0
    }
  }
}
```

**Output fields per record:**

| Field | Description |
|-------|-------------|
| `ecg` | Final usable value after anonymization + mean imputation |
| `ecg_original` | The raw ECG value you sent |
| `ecg_anonymized_range` | Hierarchy range used, e.g. `"149;150"` or `"*"` if suppressed |
| `assigned_level` | Hierarchy level (1 = finest range, 8 = fully suppressed, 0 = not anonymized) |
| `was_anonymized` | `false` if the record was skipped by validation (e.g. ecg = 0) |

---

#### `POST /api/v1/visualize`
Anonymize a dataset and return a comparison plot (used by the browser demo).

Accepts `multipart/form-data`:

| Field | Type | Description |
|-------|------|-------------|
| `k_value` | int | K-anonymity level |
| `time_window_seconds` | int | Tumbling window duration |
| `csv_file` | file (optional) | CSV with `timestamp` and `ecg` columns. Uses demo data if omitted |

Returns:
```json
{
  "success": true,
  "plot_base64": "<PNG encoded as base64>",
  "pearson_r": 0.987,
  "stats": { ... }
}
```

---

### Python Client

`anon_client.py` in this folder is a ready-to-use Python wrapper around the API. Copy it into any Python project:

```python
from anon_client import CentralAnonClient

client = CentralAnonClient(
    base_url='http://localhost:8080',
    api_key='your-key',   # omit if no API_KEY set on server
)

if client.is_healthy():
    result = client.anonymize(records, k_value=10, batch_size_seconds=5)
    for r in result['anonymized_records']:
        print(r['ecg_original'], '→', r['ecg'])
```

Run `example_usage.py` for a full walkthrough:

```bash
python example_usage.py
```
