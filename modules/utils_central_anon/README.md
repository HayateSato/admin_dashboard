# Central ECG Anonymization System

## Overview

This system performs **central anonymization** of ECG data using the **level-by-level hierarchy-based k-anonymity algorithm**.

### Key Features

- ✅ Configurable batch-based anonymization (similar to Flutter app's "buffer size")
- ✅ All configuration via `.env` file (no command-line arguments needed)
- ✅ Streaming mode for continuous processing
- ✅ Multiple output destinations (InfluxDB, CSV, API)
- ✅ Production-ready with comprehensive error handling

---

## Quick Start (For DevOps)

### 1. Install Dependencies

```bash
cd _backend_component/central_anonymization
pip install -r requirements.txt
```

### 2. Configure Settings

```bash
# Copy example configuration
cp .env.example .env

# Edit .env and configure your InfluxDB credentials
nano .env  # or use your preferred editor
```

**Required settings in `.env`:**
```env
INFLUX_URL=http://your-influxdb-server:8086
INFLUX_TOKEN=your-influxdb-token-here
INFLUX_ORG=your-organization-name
```

### 3. Run

```bash
# Process last hour of data
python central_anonymizer.py

# Or run in streaming mode (continuous processing)
# First, set STREAMING_MODE=true in .env, then:
python central_anonymizer.py
```

That's it! The system will:
- Fetch raw ECG data from InfluxDB
- Anonymize in 5-second batches (configurable via `BATCH_SIZE_SECONDS`)
- Output to configured destinations

---

## Architecture

```
┌─────────────────┐
│   InfluxDB      │
│  "raw_data"     │  ← Raw ECG data from devices
│     bucket      │
└────────┬────────┘
         │
         │ Query in batches (BATCH_SIZE_SECONDS)
         │
         ▼
┌─────────────────────────────────────────┐
│  Central Anonymization Service          │
│                                          │
│  1. Fetch batch (e.g., 5 seconds)      │
│  2. Apply k-anonymity anonymization     │
│  3. Apply mean imputation               │
│  4. Output to selected destinations     │
└────────┬────────────────────────────────┘
         │
         │ Output Options (configurable):
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼                  ▼
┌────────────────┐  ┌──────────────┐  ┌──────────────┐
│   InfluxDB     │  │  CSV Files   │  │  Python API  │
│ "anonymized-   │  │  (./output/) │  │  Endpoint    │
│  data" bucket  │  │              │  │              │
└────────────────┘  └──────────────┘  └──────────────┘
```

---

## Configuration (.env File)

All settings are configured via the `.env` file. See [`.env.example`](.env.example) for all available options.

### Essential Settings

| Setting | Description | Default | Example |
|---------|-------------|---------|---------|
| `INFLUX_URL` | InfluxDB server URL | `http://localhost:8086` | `https://influx.example.com` |
| `INFLUX_TOKEN` | InfluxDB authentication token | (required) | `your-token-here` |
| `INFLUX_ORG` | InfluxDB organization | (required) | `my-organization` |
| `K_VALUE` | K-anonymity parameter | `5` | `10` (higher = more privacy) |
| `BATCH_SIZE_SECONDS` | Time window for each anonymization batch | `5` | `10` |

### Understanding Batch Size

**`BATCH_SIZE_SECONDS`** is the **anonymization batch size** (similar to "buffer size" or "time window" in Flutter app):

- **Purpose**: Groups ECG measurements into time-based batches for anonymization
- **How it works**:
  - Collects all ECG measurements within each N-second window
  - Anonymizes that batch as a group to satisfy k-anonymity
  - Outputs the anonymized batch
  - Moves to next N-second window

- **Trade-offs**:
  - **Smaller batches** (e.g., 1-5s): Lower latency, more suppression (worse utility)
  - **Larger batches** (e.g., 30-60s): Higher latency, less suppression (better utility)

- **Recommended**: 5-10 seconds for good balance

**Example with BATCH_SIZE_SECONDS=5:**
```
12:00:00 - 12:00:05 → Batch 1 → Anonymize → Output
12:00:05 - 12:00:10 → Batch 2 → Anonymize → Output
12:00:10 - 12:00:15 → Batch 3 → Anonymize → Output
```

**This is different from:**
- **Query time window** (`DEFAULT_QUERY_HOURS`): How much historical data to fetch initially
- **Streaming interval** (`STREAMING_INTERVAL`): How often to check for new data in streaming mode

### Output Configuration

```env
# Enable/disable outputs
OUTPUT_TO_CSV=true
OUTPUT_TO_INFLUX=true
OUTPUT_TO_API=false

# CSV settings
CSV_OUTPUT_DIR=./output
CSV_FILENAME_PATTERN=ecg_anonymized_%Y%m%d_%H%M%S.csv

# API settings (if OUTPUT_TO_API=true)
API_ENDPOINT=http://localhost:5000/api/data
API_TOKEN=optional-bearer-token
```

### Processing Modes

```env
# One-time mode (process historical data once)
STREAMING_MODE=false
DEFAULT_QUERY_HOURS=1  # Process last 1 hour

# Streaming mode (continuous processing)
STREAMING_MODE=true
STREAMING_INTERVAL=5  # Check for new data every 5 seconds
```

---

## Installation

### Prerequisites

- Python 3.8 or higher
- Access to InfluxDB instance with raw ECG data
- Network connectivity to InfluxDB server

### Setup Steps

1. **Navigate to directory:**
   ```bash
   cd _backend_component/central_anonymization
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - `python-dotenv` - Environment configuration
   - `influxdb-client` - InfluxDB integration
   - `requests` - HTTP client for API output

3. **Copy and configure .env:**
   ```bash
   cp .env.example .env
   ```

4. **Edit .env file:**
   ```bash
   nano .env  # Linux/Mac
   notepad .env  # Windows
   ```

   **Minimum required configuration:**
   ```env
   INFLUX_URL=http://localhost:8086
   INFLUX_TOKEN=your-actual-token-here
   INFLUX_ORG=your-org-name
   ```

5. **Get InfluxDB token:**
   - Open InfluxDB UI
   - Go to: Settings → Tokens
   - Copy an existing token or create new one
   - Paste into `.env` file

6. **Verify setup:**
   ```bash
   python central_anonymizer.py
   ```

   You should see:
   ```
   🚀 Central ECG Anonymization Service
   ============================================================
   Configuration Summary:
   ...
   ✅ Connected to InfluxDB at http://localhost:8086
   ```

---

## Usage

### One-Time Processing

Process historical data once and exit:

```bash
# Make sure STREAMING_MODE=false in .env
python central_anonymizer.py
```

This will:
1. Fetch data from last `DEFAULT_QUERY_HOURS` hours
2. Split into batches of `BATCH_SIZE_SECONDS` seconds
3. Anonymize each batch
4. Output to configured destinations
5. Exit

### Continuous Streaming

Process new data continuously:

```bash
# Set STREAMING_MODE=true in .env
python central_anonymizer.py
```

This will:
1. Start from current time
2. Every `STREAMING_INTERVAL` seconds, check for new data
3. Process complete batches as they become available
4. Run until stopped (Ctrl+C)

**Use case**: Deploy as a background service to continuously anonymize incoming data

### Output Locations

**CSV files:**
- Directory: Configured by `CSV_OUTPUT_DIR` (default: `./output/`)
- Filename: Uses `CSV_FILENAME_PATTERN` with timestamp
- Example: `output/ecg_anonymized_20251103_143000.csv`

**InfluxDB:**
- Bucket: `INFLUX_OUTPUT_BUCKET` (default: `anonymized-data`)
- Measurement: `<INFLUX_MEASUREMENT>_anonymized` (e.g., `ecg_anonymized`)

---

## Understanding the Algorithm

The level-by-level k-anonymity algorithm processes data in batches:

1. **Collect batch**: Gather all ECG measurements in the time window (e.g., 5 seconds)
2. **Sort**: Order measurements by ECG value
3. **Anonymize**: Apply level-by-level hierarchy to satisfy k-anonymity
4. **Impute**: Convert ranges to single values
5. **Output**: Save/send anonymized batch

For detailed explanation, see [documentation/ALGORITHM.md](documentation/ALGORITHM.md)

### Key Parameters

**K-Anonymity (`K_VALUE`):**
- k=5: General use, moderate privacy
- k=10: Sensitive data, strong privacy
- k=20: Public datasets, maximum privacy

**Batch Size (`BATCH_SIZE_SECONDS`):**
- Determines anonymization quality and latency
- Larger batches → better k-anonymity satisfaction → less information loss
- Recommended: 5-10 seconds

---

## Deployment

### As a Systemd Service (Linux)

1. Create service file: `/etc/systemd/system/ecg-anonymizer.service`

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

2. Enable and start:
```bash
sudo systemctl enable ecg-anonymizer
sudo systemctl start ecg-anonymizer
sudo systemctl status ecg-anonymizer
```

3. View logs:
```bash
sudo journalctl -u ecg-anonymizer -f
```

### As a Docker Container

1. Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "central_anonymizer.py"]
```

2. Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  ecg-anonymizer:
    build: .
    container_name: ecg-anonymizer
    env_file:
      - .env
    volumes:
      - ./output:/app/output
    restart: unless-stopped
    depends_on:
      - influxdb
```

3. Run:
```bash
docker-compose up -d
docker-compose logs -f ecg-anonymizer
```

### As a Windows Service

Use [NSSM (Non-Sucking Service Manager)](https://nssm.cc/):

```cmd
nssm install ECGAnonymizer "C:\Python311\python.exe" "C:\path\to\central_anonymizer.py"
nssm set ECGAnonymizer AppDirectory "C:\path\to\central_anonymization"
nssm start ECGAnonymizer
```

---

## Monitoring and Logging

### Log Levels

Configure in `.env`:
```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
VERBOSE_LOGGING=true  # Show detailed anonymization stats
```

### Log Output

**Successful batch processing:**
```
2025-11-03 14:30:00 - INFO - 📦 Processing batch: 14:30:00 - 14:30:05
2025-11-03 14:30:00 - INFO -   Fetched 640 records from batch
2025-11-03 14:30:00 - INFO - 🔒 Anonymizing batch: 640 records (K=5)
2025-11-03 14:30:00 - INFO -   ✅ All records satisfied at level 3
2025-11-03 14:30:00 - INFO -   Anonymization complete: 640 records
2025-11-03 14:30:00 - INFO - 📈 Level distribution: {2: 180, 3: 320, 4: 140}
2025-11-03 14:30:01 - INFO - 💾 Saving 640 records to CSV: ./output/ecg_anonymized_20251103_143000.csv
2025-11-03 14:30:01 - INFO -   ✅ CSV saved
2025-11-03 14:30:01 - INFO - 📤 Pushing 640 records to InfluxDB: anonymized-data
2025-11-03 14:30:02 - INFO -   ✅ Successfully pushed 640 points
```

### Health Monitoring

Monitor these indicators:

- **Batch processing time**: Should be < 1 second for batches of 1000-2000 records
- **Suppression rate**: Should be < 15% (check level distribution)
- **Average level**: Lower is better (2-4 is good, 6-8 indicates issues)

---

## Troubleshooting

### Issue: "❌ .env file not found!"

**Solution:**
```bash
cp .env.example .env
# Then edit .env with your settings
```

### Issue: "❌ Failed to connect to InfluxDB"

**Possible causes:**
1. Wrong `INFLUX_URL`
2. Invalid `INFLUX_TOKEN`
3. Wrong `INFLUX_ORG`
4. InfluxDB server not running
5. Network/firewall blocking connection

**Solution:**
1. Verify InfluxDB is running:
   ```bash
   curl http://localhost:8086/health
   # Should return: {"status":"pass"}
   ```

2. Test credentials:
   - Open InfluxDB UI
   - Check Settings → About for organization name
   - Check Settings → Tokens for valid token

3. Update `.env` with correct values

### Issue: "No data in this batch, skipping..."

**Cause**: No ECG measurements in the time window

**Solution:**
1. Check data exists in InfluxDB:
   ```flux
   from(bucket: "raw_data")
     |> range(start: -1h)
     |> filter(fn: (r) => r._measurement == "ecg")
     |> limit(n: 10)
   ```

2. Verify bucket name in `.env` matches your InfluxDB bucket
3. Check `DEVICE_FILTER` if set - might be excluding all data

### Issue: High suppression rate (many level 9)

**Cause**: Batch size too small for the k-value

**Solution:**
1. Increase `BATCH_SIZE_SECONDS` (e.g., from 5 to 10 seconds)
2. Or decrease `K_VALUE` (e.g., from 10 to 5)
3. Check if enough devices are sending data

### Issue: Memory usage growing

**Cause**: Processing very large batches

**Solution:**
Set `MAX_RECORDS_PER_QUERY` in `.env`:
```env
MAX_RECORDS_PER_QUERY=10000
```

---

## File Structure

```
central_anonymization/
├── .env                          ← Your configuration (DO NOT commit!)
├── .env.example                  ← Example configuration template
├── .gitignore                    ← Git ignore file
├── README.md                     ← This file
├── requirements.txt              ← Python dependencies
├── central_anonymizer.py         ← Main service script
├── example_usage.py              ← Programmatic usage examples
│
├── anonymizer/                   ← Core anonymization modules
│   ├── level_hierarchy_anonymizer.py
│   ├── mean_imputation.py
│   └── smarko_hierarchy_ecg.csv  ← ECG hierarchy data
│
├── documentation/                ← Additional documentation
│   ├── ALGORITHM.md              ← Algorithm deep-dive
│   ├── QUICKSTART.md             ← Quick start guide
│   └── description.txt           ← Original requirements
│
└── output/                       ← CSV output directory (created automatically)
    └── ecg_anonymized_*.csv
```

---

## Security Considerations

1. **Never commit .env file:**
   - `.gitignore` is configured to exclude it
   - Contains sensitive credentials

2. **InfluxDB token security:**
   - Use read-only token for input bucket if possible
   - Use write-only token for output bucket
   - Rotate tokens periodically

3. **Network security:**
   - Use HTTPS for production InfluxDB (`INFLUX_URL=https://...`)
   - Restrict network access to InfluxDB server
   - Use VPN or private network when possible

4. **File permissions:**
   ```bash
   chmod 600 .env  # Only owner can read/write
   ```

5. **Data retention:**
   - Set InfluxDB retention policies on buckets
   - Consider deleting raw data after anonymization
   - Regularly clean up old CSV files

---

## Performance

**Typical performance** (standard hardware):
- Loading hierarchy: ~100ms (one-time)
- Anonymizing 1000 records: ~50-100ms
- Anonymizing 10000 records: ~500ms-1s
- Writing to InfluxDB: ~100-500ms per 1000 points

**Bottlenecks:**
- InfluxDB query time (network latency)
- Batch size vs. k-value (larger batches process faster per record)

**Optimization:**
- Run on same server/network as InfluxDB
- Use appropriate `BATCH_SIZE_SECONDS` (5-10s recommended)
- Process during off-peak hours if doing large historical processing

---

## Support

### Documentation

- [QUICKSTART.md](documentation/QUICKSTART.md) - 5-minute quick start
- [ALGORITHM.md](documentation/ALGORITHM.md) - Algorithm details
- [.env.example](.env.example) - All configuration options

### Common Tasks

**Change k-value:**
```env
K_VALUE=10  # in .env
```

**Change batch size:**
```env
BATCH_SIZE_SECONDS=10  # in .env
```

**Enable streaming mode:**
```env
STREAMING_MODE=true  # in .env
```

**Change output directory:**
```env
CSV_OUTPUT_DIR=/var/data/anonymized  # in .env
```

---

## Version History

- **v2.0.0** (2025-11-03): Environment-based configuration
  - All settings via .env file
  - Configurable batch size (BATCH_SIZE_SECONDS)
  - Streaming mode support
  - Removed command-line arguments
  - Updated folder structure

- **v1.0.0** (2025-11-03): Initial release
  - Level-by-level k-anonymity algorithm
  - InfluxDB integration
  - CSV input/output
  - API endpoint support

---

## License

[Specify your license here]
