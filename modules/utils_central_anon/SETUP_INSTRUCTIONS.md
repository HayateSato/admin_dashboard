# Central ECG Anonymization - Setup Instructions for DevOps

## Overview

This service anonymizes ECG data from InfluxDB using batch-based k-anonymity algorithm.

**Configuration**: Everything is configured via `.env` file - no command-line arguments needed.

---

## Quick Setup (3 Steps)

### 1. Install Dependencies

```bash
cd _backend_component/central_anonymization
pip install -r requirements.txt
```

### 2. Configure .env File

```bash
cp .env.example .env
nano .env  # or your preferred editor
```

**Required settings:**
```env
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=your-token-here
INFLUX_ORG=your-organization
```

### 3. Run

```bash
python central_anonymizer.py
```

---

## Key Configuration Parameters

### InfluxDB Settings

```env
INFLUX_URL=http://localhost:8086          # Your InfluxDB server
INFLUX_TOKEN=your-token                   # From InfluxDB UI → Settings → Tokens
INFLUX_ORG=your-org                       # From InfluxDB UI → Settings → About
INFLUX_INPUT_BUCKET=raw_data              # Bucket with raw ECG data
INFLUX_OUTPUT_BUCKET=anonymized-data      # Bucket for anonymized output
```

### Anonymization Settings

```env
K_VALUE=5                    # Privacy level: 5 (moderate), 10 (high), 20 (maximum)
BATCH_SIZE_SECONDS=5         # Anonymization window (CRITICAL - see below)
```

**BATCH_SIZE_SECONDS** - The time window for grouping ECG measurements for anonymization:
- This is similar to "buffer size" or "time window" in the Flutter app
- **Purpose**: Groups measurements into batches to satisfy k-anonymity
- **How it works**:
  ```
  12:00:00-12:00:05 → Batch 1 → Anonymize → Output
  12:00:05-12:00:10 → Batch 2 → Anonymize → Output
  12:00:10-12:00:15 → Batch 3 → Anonymize → Output
  ```
- **Trade-offs**:
  - Smaller (1-5s): Lower latency, more data suppression
  - Larger (30-60s): Higher latency, less data suppression (better quality)
- **Recommended**: 5-10 seconds

**BATCH_SIZE_SECONDS vs other time settings:**
- `BATCH_SIZE_SECONDS` = Anonymization batch window
- `DEFAULT_QUERY_HOURS` = How much historical data to fetch (query window)
- `STREAMING_INTERVAL` = How often to check for new data in streaming mode

### Output Settings

```env
OUTPUT_TO_CSV=true                              # Save to CSV files
OUTPUT_TO_INFLUX=true                           # Push to InfluxDB
OUTPUT_TO_API=false                             # Send to API endpoint

CSV_OUTPUT_DIR=./output                         # CSV output directory
CSV_FILENAME_PATTERN=ecg_anonymized_%Y%m%d_%H%M%S.csv
```

### Processing Modes

```env
# One-time mode: Process historical data once and exit
STREAMING_MODE=false
DEFAULT_QUERY_HOURS=1

# Streaming mode: Continuous processing
STREAMING_MODE=true
STREAMING_INTERVAL=5  # Check for new data every 5 seconds
```

---

## Running the Service

### One-Time Processing (Default)

```bash
python central_anonymizer.py
```

This will:
1. Fetch last `DEFAULT_QUERY_HOURS` hours of data
2. Split into batches of `BATCH_SIZE_SECONDS`
3. Anonymize each batch
4. Output to configured destinations
5. Exit

### Continuous Streaming

Set in `.env`:
```env
STREAMING_MODE=true
```

Then run:
```bash
python central_anonymizer.py
```

This runs continuously until stopped (Ctrl+C).

---

## Deployment as a Service

### Linux (Systemd)

Create `/etc/systemd/system/ecg-anonymizer.service`:

```ini
[Unit]
Description=Central ECG Anonymization Service
After=network.target influxdb.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/central_anonymization
ExecStart=/usr/bin/python3 central_anonymizer.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ecg-anonymizer
sudo systemctl start ecg-anonymizer
sudo systemctl status ecg-anonymizer
sudo journalctl -u ecg-anonymizer -f  # View logs
```

### Docker

See [README.md](README.md#as-a-docker-container) for Docker and docker-compose setup.

---

## Monitoring

### Log Output

The service provides detailed logging:

```
🚀 Central ECG Anonymization Service
============================================================
Configuration Summary:
InfluxDB URL: http://localhost:8086
Input Bucket: raw_data
Output Bucket: anonymized-data
K-Anonymity: k=5
Batch Size: 5 seconds
Output → CSV: True
Output → InfluxDB: True
============================================================
✅ Connected to InfluxDB
📦 Processing batch: 14:30:00 - 14:30:05
  Fetched 640 records
🔒 Anonymizing batch: 640 records (K=5)
  ✅ All records satisfied at level 3
📈 Level distribution: {2: 180, 3: 320, 4: 140}
💾 Saving to CSV
📤 Pushing to InfluxDB
  ✅ Successfully pushed 640 points
```

### Health Indicators

Monitor these in logs:

- **Level distribution**: Lower levels (2-4) = good quality
- **Suppression rate** (level 9): Should be < 15%
- **Batch processing time**: Should be < 1 second per batch

**Warning signs:**
- Many level 9 (suppressed) → Increase `BATCH_SIZE_SECONDS`
- Slow processing → Check network latency to InfluxDB

---

## Troubleshooting

### ❌ "Failed to connect to InfluxDB"

1. Check InfluxDB is running:
   ```bash
   curl http://localhost:8086/health
   ```

2. Verify credentials in `.env`:
   - Check token in InfluxDB UI (Settings → Tokens)
   - Check org name (Settings → About)

### ⚠️ "No data in this batch"

1. Check data exists in InfluxDB:
   ```flux
   from(bucket: "raw_data")
     |> range(start: -1h)
     |> filter(fn: (r) => r._measurement == "ecg")
     |> limit(n: 5)
   ```

2. Verify bucket name in `.env` matches InfluxDB

### ⚠️ High suppression rate

If logs show many level 9:
```
📈 Level distribution: {9: 450, 3: 100}  ← Too much suppression!
```

Solution: Increase batch size
```env
BATCH_SIZE_SECONDS=10  # Was 5
```

---

## File Structure

```
central_anonymization/
├── .env                      ← Configuration (create from .env.example)
├── .env.example              ← Template
├── central_anonymizer.py     ← Main script
├── requirements.txt          ← Dependencies
├── README.md                 ← Full documentation
│
├── anonymizer/               ← Core modules
│   ├── level_hierarchy_anonymizer.py
│   ├── mean_imputation.py
│   └── smarko_hierarchy_ecg.csv
│
├── documentation/            ← Additional docs
│   ├── QUICKSTART.md
│   └── ALGORITHM.md
│
└── output/                   ← CSV outputs (auto-created)
```

---

## Security Notes

1. **Never commit .env file** - Contains credentials
2. **Use HTTPS** for production InfluxDB
3. **Rotate tokens** periodically
4. **Set file permissions**: `chmod 600 .env`

---

## Support

- **Quick start**: [documentation/QUICKSTART.md](documentation/QUICKSTART.md)
- **Full documentation**: [README.md](README.md)
- **Algorithm details**: [documentation/ALGORITHM.md](documentation/ALGORITHM.md)

---

## Summary

```bash
# Setup (one time)
cd _backend_component/central_anonymization
pip install -r requirements.txt
cp .env.example .env
nano .env  # Configure InfluxDB credentials

# Run
python central_anonymizer.py
```

The service will fetch raw ECG data, anonymize in batches, and output to configured destinations.
