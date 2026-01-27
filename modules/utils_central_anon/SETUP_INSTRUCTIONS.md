# Central ECG Anonymization - Setup Instructions

## Overview

This module anonymizes ECG data from InfluxDB using batch-based k-anonymity algorithm.

**Configuration**: Settings are loaded from the project root `.env` file.

---

## Quick Setup (3 Steps)

### 1. Install Dependencies

```bash
pip install -r modules/utils_central_anon/requirements_anon.txt
```

### 2. Configure .env File

Add the following to your project root `.env` file:

```env
# InfluxDB Configuration
INFLUX_URL=https://pu-influxdb.smarko-health.de
INFLUX_TOKEN=your-token-here
INFLUX_ORG=mcs-data-labs
INFLUX_BUCKET_RAW=raw-data
INFLUX_BUCKET_ANON=anonymized-data

# Anonymization Settings
K_VALUE=5
BATCH_SIZE_SECONDS=5
```

### 3. Run

```bash
cd modules/utils_central_anon
python central_anonymizer.py
```

---

## Key Configuration Parameters

### InfluxDB Settings

```env
INFLUX_URL=https://pu-influxdb.smarko-health.de
INFLUX_TOKEN=your-token                   # From InfluxDB UI → Settings → Tokens
INFLUX_ORG=mcs-data-labs                  # From InfluxDB UI → Settings → About
INFLUX_BUCKET_RAW=raw-data                # Bucket with raw ECG data
INFLUX_BUCKET_ANON=anonymized-data        # Bucket for anonymized output
```

### Anonymization Settings

```env
K_VALUE=5                    # Privacy level: 5 (moderate), 10 (high), 20 (maximum)
BATCH_SIZE_SECONDS=5         # Anonymization window (see below)
```

**BATCH_SIZE_SECONDS** - The time window for grouping ECG measurements:

- **Purpose**: Groups measurements into batches to satisfy k-anonymity
- **How it works**:
  ```
  12:00:00-12:00:05 → Batch 1 → Anonymize → Output
  12:00:05-12:00:10 → Batch 2 → Anonymize → Output
  ```
- **Trade-offs**:
  - Smaller (1-5s): Lower latency, more data suppression
  - Larger (30-60s): Higher latency, better data quality
- **Recommended**: 5-10 seconds

### Output Settings

```env
OUTPUT_TO_CSV=true                              # Save to CSV files
OUTPUT_TO_INFLUX=true                           # Push to InfluxDB
CSV_OUTPUT_DIR=./output                         # CSV output directory
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
cd modules/utils_central_anon
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

Runs continuously until stopped (Ctrl+C).

---

## Monitoring

### Log Output

```
Central ECG Anonymization Service
============================================================
Configuration Summary:
InfluxDB URL: https://pu-influxdb.smarko-health.de
Input Bucket: raw-data
Output Bucket: anonymized-data
K-Anonymity: k=5
Batch Size: 5 seconds
============================================================
Connected to InfluxDB
Processing batch: 14:30:00 - 14:30:05
  Fetched 640 records
Anonymizing batch: 640 records (K=5)
  All records satisfied at level 3
Level distribution: {2: 180, 3: 320, 4: 140}
Saving to CSV
Pushing to InfluxDB
  Successfully pushed 640 points
```

### Health Indicators

- **Level distribution**: Lower levels (2-4) = good quality
- **Suppression rate** (level 9): Should be < 15%
- **Batch processing time**: Should be < 1 second per batch

**Warning signs:**
- Many level 9 (suppressed) → Increase `BATCH_SIZE_SECONDS`
- Slow processing → Check network latency to InfluxDB

---

## Troubleshooting

### "Failed to connect to InfluxDB"

1. Check InfluxDB is accessible
2. Verify credentials in `.env`:
   - Check token in InfluxDB UI (Settings → Tokens)
   - Check org name (Settings → About)

### "No data in this batch"

1. Check data exists in InfluxDB
2. Verify bucket name in `.env` matches InfluxDB

### High suppression rate

If logs show many level 9:
```
Level distribution: {9: 450, 3: 100}  ← Too much suppression!
```

Solution: Increase batch size
```env
BATCH_SIZE_SECONDS=10  # Was 5
```

---

## File Structure

```
utils_central_anon/
├── central_anonymizer.py     # Main script
├── requirements_anon.txt     # Dependencies
├── README.md                 # Full documentation
├── SETUP_INSTRUCTIONS.md     # This file
│
├── anonymizer/               # Core modules
│   ├── level_hierarchy_anonymizer.py
│   ├── mean_imputation.py
│   └── smarko_hierarchy_ecg.csv
│
└── data_fetcher/             # Data retrieval
    ├── influx_fetcher.py
    ├── ecg_validator.py
    └── test_influx_connection.py
```

---

## Security Notes

1. **Never commit .env file** - Contains credentials
2. **Use HTTPS** for production InfluxDB
3. **Rotate tokens** periodically
