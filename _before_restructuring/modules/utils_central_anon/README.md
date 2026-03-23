# Central ECG Anonymization Module

## Overview

This module performs **central anonymization** of ECG data using the **level-by-level hierarchy-based k-anonymity algorithm**. It is integrated into the Admin Dashboard and can also be run standalone.

### Key Features

- Configurable batch-based anonymization (time window)
- Configuration via project root `.env` file
- Streaming mode for continuous processing
- Multiple output destinations (InfluxDB, CSV)

---

## File Structure

```
utils_central_anon/
├── central_anonymizer.py          # Main service script
├── requirements_anon.txt          # Python dependencies
├── README.md                      # This file
├── SETUP_INSTRUCTIONS.md          # Quick setup guide
│
├── anonymizer/                    # Core anonymization modules
│   ├── level_hierarchy_anonymizer.py  # K-anonymity algorithm
│   ├── mean_imputation.py             # Range to value conversion
│   └── smarko_hierarchy_ecg.csv       # ECG hierarchy data
│
└── data_fetcher/                  # Data retrieval modules
    ├── __init__.py
    ├── influx_fetcher.py          # InfluxDB data fetching
    ├── ecg_validator.py           # ECG data validation
    ├── check_fields.py            # Field inspection utility
    ├── explore_bucket.py          # Bucket exploration utility
    └── test_influx_connection.py  # Connection test utility
```

---

## Integration with Admin Dashboard

This module is used by `modules/anonymization_manager.py` to provide central anonymization functionality in the Admin Dashboard. Configuration is read from the project root `.env` file.

### Required Environment Variables

Add these to the project root `.env` file:

```env
# InfluxDB Configuration
INFLUX_URL=https://pu-influxdb.smarko-health.de
INFLUX_TOKEN=your-token-here
INFLUX_ORG=mcs-data-labs
INFLUX_BUCKET_RAW=raw-data
INFLUX_BUCKET_ANON=anonymized-data

# Anonymization Settings (optional - defaults shown)
K_VALUE=5                    # Privacy level: 5 (moderate), 10 (high)
BATCH_SIZE_SECONDS=5         # Time window for each anonymization batch
```

---

## Standalone Usage

### Install Dependencies

```bash
pip install -r modules/utils_central_anon/requirements_anon.txt
```

### Run Anonymization

```bash
cd modules/utils_central_anon
python central_anonymizer.py
```

---

## Configuration Parameters

### Anonymization Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `K_VALUE` | K-anonymity parameter (higher = more privacy) | `5` |
| `BATCH_SIZE_SECONDS` | Time window for grouping ECG measurements | `5` |

### Understanding Batch Size

**`BATCH_SIZE_SECONDS`** groups ECG measurements into time-based batches for anonymization:

- **Smaller batches** (1-5s): Lower latency, more data suppression
- **Larger batches** (30-60s): Higher latency, better data quality
- **Recommended**: 5-10 seconds

Example with `BATCH_SIZE_SECONDS=5`:
```
12:00:00 - 12:00:05 → Batch 1 → Anonymize → Output
12:00:05 - 12:00:10 → Batch 2 → Anonymize → Output
```

---

## Algorithm

The level-by-level k-anonymity algorithm:

1. **Collect batch**: Gather all ECG measurements in the time window
2. **Sort**: Order measurements by ECG value
3. **Anonymize**: Apply level-by-level hierarchy to satisfy k-anonymity
4. **Impute**: Convert ranges to single values (mean imputation)
5. **Output**: Save/send anonymized batch

### Key Parameters

- **k=5**: General use, moderate privacy
- **k=10**: Sensitive data, strong privacy
- **k=20**: Public datasets, maximum privacy

---

## Troubleshooting

### No data in batch

Check that data exists in InfluxDB and bucket name matches configuration.

### High suppression rate (many level 9)

Increase `BATCH_SIZE_SECONDS` to allow more records per batch.

---

## Additional Documentation

- [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) - Quick setup guide for DevOps
