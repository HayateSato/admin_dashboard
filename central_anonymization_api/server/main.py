"""
Central Anonymization API Server

Standalone Flask service that exposes the k-anonymity ECG anonymization algorithm
via a REST API. Any client (Flutter app, Python script, other services) can POST
raw ECG records and receive back anonymized records.

Algorithm: Level-by-level hierarchy k-anonymity (same as admin dashboard)
"""

import os
import sys
import logging

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Add parent directory to sys.path so `core` package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.level_hierarchy_anonymizer import LevelHierarchyEcgAnonymizer, EcgAnonymizationRecord
from core.mean_imputation import EcgMeanImputation
from core.ecg_validator import EcgValidator

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Default: look for the CSV in the parent admin_dashboard project.
# Override with HIERARCHY_CSV_PATH env var when deploying standalone.
_DEFAULT_CSV = os.path.join(
    os.path.dirname(__file__), '..', '..',
    'modules', 'utils_central_anon', 'anonymizer', 'smarko_hierarchy_ecg.csv'
)
HIERARCHY_CSV_PATH = os.getenv('HIERARCHY_CSV_PATH', _DEFAULT_CSV)
DEFAULT_K_VALUE    = int(os.getenv('DEFAULT_K_VALUE', '10'))
API_KEY            = os.getenv('API_KEY', '')   # empty = no auth required
PORT               = int(os.getenv('PORT', '6000'))

VALID_K_VALUES = {5, 10, 20, 50}

# ---------------------------------------------------------------------------
# Anonymizer singleton (loaded once at startup)
# ---------------------------------------------------------------------------
anonymizer = LevelHierarchyEcgAnonymizer(k_value=DEFAULT_K_VALUE)

def _load_hierarchy() -> None:
    try:
        csv_path = os.path.abspath(HIERARCHY_CSV_PATH)
        anonymizer.initialize(csv_path, enabled=True)
        logger.info(f"Hierarchy loaded: {csv_path} ({anonymizer.hierarchy.size} values)")
    except Exception as exc:
        logger.error(f"Failed to load hierarchy: {exc}")
        logger.error("Server will start but /api/v1/anonymize will return 503 until fixed.")

_load_hierarchy()

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
def _auth_error():
    """Returns a 401 response if API key is wrong, None if auth passes."""
    if not API_KEY:
        return None  # auth disabled
    key = request.headers.get('X-API-Key') or request.args.get('api_key', '')
    if key != API_KEY:
        return jsonify({'success': False, 'error': 'Unauthorized — provide X-API-Key header'}), 401
    return None


# ---------------------------------------------------------------------------
# Batch splitting helper
# ---------------------------------------------------------------------------
def _split_into_time_batches(records: list, batch_size_seconds: int) -> list:
    """Split a list of records into time-window batches.

    Records within the same `batch_size_seconds` window are grouped together.
    Each batch is anonymized independently (matching the admin dashboard behaviour).
    """
    if not records or batch_size_seconds <= 0:
        return [records]

    sorted_records = sorted(records, key=lambda r: r.get('timestamp', 0))
    batches, current_batch = [], []
    batch_start = None
    window_ms = batch_size_seconds * 1000

    for record in sorted_records:
        ts = record.get('timestamp', 0)
        if batch_start is None:
            batch_start = ts
        if ts - batch_start >= window_ms:
            if current_batch:
                batches.append(current_batch)
            current_batch = [record]
            batch_start = ts
        else:
            current_batch.append(record)

    if current_batch:
        batches.append(current_batch)

    return batches


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health():
    """Public health check — no auth required."""
    return jsonify({
        'status': 'ok',
        'hierarchy_loaded': anonymizer.hierarchy.is_loaded,
        'hierarchy_size':   anonymizer.hierarchy.size,
        'default_k_value':  DEFAULT_K_VALUE,
    })


@app.route('/api/v1/info', methods=['GET'])
def info():
    """Return server configuration and algorithm details."""
    err = _auth_error()
    if err:
        return err
    return jsonify({
        'success':          True,
        'settings':         anonymizer.get_settings(),
        'supported_k':      sorted(VALID_K_VALUES),
        'algorithm':        'level-by-level k-anonymity with ECG hierarchy',
        'ecg_range':        {'min': -2500, 'max': 2500},
        'hierarchy_levels': 8,
    })


@app.route('/api/v1/anonymize', methods=['POST'])
def anonymize():
    """
    Anonymize a batch of ECG records.

    Request body (JSON):
    {
        "records": [
            {
                "timestamp":  <int, milliseconds since epoch>,
                "ecg":        <int, -2500 to 2500>,
                "unique_key": <str, patient identifier>,   // optional extra fields preserved
                ...
            },
            ...
        ],
        "k_value":            <int, one of 5 / 10 / 20 / 50>,   // default: server DEFAULT_K_VALUE
        "batch_size_seconds": <int, time-window width in seconds> // default: 5
    }

    Response (JSON):
    {
        "success": true,
        "anonymized_records": [
            {
                ...original fields...,
                "ecg":                  <float, imputed value after anonymization>,
                "ecg_original":         <int,   raw ECG before anonymization>,
                "ecg_anonymized_range": <str,   hierarchy range e.g. "11;14" or "*">,
                "assigned_level":       <int,   1-8, hierarchy level used>,
                "was_anonymized":       <bool>
            },
            ...
        ],
        "stats": {
            "total_input":        <int>,
            "total_output":       <int>,
            "k_value_used":       <int>,
            "batch_size_seconds": <int>,
            "batches_processed":  <int>,
            "validation":         { ...EcgValidator stats... }
        }
    }
    """
    err = _auth_error()
    if err:
        return err

    if not anonymizer.is_ready:
        return jsonify({
            'success': False,
            'error': 'Anonymizer not ready — hierarchy CSV failed to load at startup',
        }), 503

    data = request.get_json(silent=True)
    if not data or 'records' not in data:
        return jsonify({'success': False, 'error': 'Request body must be JSON with a "records" key'}), 400

    raw_records      = data['records']
    k_value          = int(data.get('k_value', DEFAULT_K_VALUE))
    batch_size_secs  = int(data.get('batch_size_seconds', 5))

    if k_value not in VALID_K_VALUES:
        return jsonify({'success': False, 'error': f'k_value must be one of {sorted(VALID_K_VALUES)}'}), 400

    if not raw_records:
        return jsonify({'success': True, 'anonymized_records': [], 'stats': {
            'total_input': 0, 'total_output': 0,
            'k_value_used': k_value, 'batch_size_seconds': batch_size_secs,
            'batches_processed': 0,
        }}), 200

    # ── Step 1: Validate ────────────────────────────────────────────────────
    validator = EcgValidator()
    validated_records, validation_stats = validator.validate_and_filter(raw_records)

    # ── Step 2: Split into time batches ─────────────────────────────────────
    batches = _split_into_time_batches(validated_records, batch_size_secs)

    # ── Step 3 & 4: Anonymize each batch + mean imputation ──────────────────
    anonymizer.k_value = k_value
    all_output = []

    for batch in batches:
        to_anon    = [r for r in batch if r.get('should_anonymize', True)]
        skip_anon  = [r for r in batch if not r.get('should_anonymize', True)]

        # Records that should NOT be anonymized — pass through unchanged
        for r in skip_anon:
            out = {k: v for k, v in r.items() if k != 'should_anonymize'}
            out.update({
                'ecg_original':         r.get('ecg'),
                'ecg_anonymized_range': str(r.get('ecg', '')),
                'assigned_level':       0,
                'was_anonymized':       False,
            })
            all_output.append(out)

        if not to_anon:
            continue

        # Sort by timestamp so the anonymizer output index matches input index
        to_anon_sorted = sorted(to_anon, key=lambda r: r.get('timestamp', 0))

        anon_input = [
            EcgAnonymizationRecord(
                timestamp=int(r.get('timestamp', 0)),
                original_ecg=int(r['ecg']),
            )
            for r in to_anon_sorted
        ]

        # anonymize_batch returns records sorted by timestamp
        result_records = anonymizer.anonymize_batch(anon_input)

        # Mean imputation: convert ranges → single float values
        ranges = [r.anonymized_range or str(r.original_ecg) for r in result_records]
        imputed = EcgMeanImputation.apply_mean_imputation(ranges)['processed_values']

        for orig, anon_r, imputed_val in zip(to_anon_sorted, result_records, imputed):
            out = {k: v for k, v in orig.items() if k != 'should_anonymize'}
            out.update({
                'ecg':                  round(imputed_val, 4),
                'ecg_original':         anon_r.original_ecg,
                'ecg_anonymized_range': anon_r.anonymized_range,
                'assigned_level':       anon_r.assigned_level,
                'was_anonymized':       True,
            })
            all_output.append(out)

    # Restore original temporal order
    all_output.sort(key=lambda r: r.get('timestamp', 0))

    return jsonify({
        'success': True,
        'anonymized_records': all_output,
        'stats': {
            'total_input':        len(raw_records),
            'total_output':       len(all_output),
            'k_value_used':       k_value,
            'batch_size_seconds': batch_size_secs,
            'batches_processed':  len(batches),
            'validation':         validation_stats,
        },
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f"Starting Central Anonymization API on port {PORT} (debug={debug})")
    app.run(host='0.0.0.0', port=PORT, debug=debug)
