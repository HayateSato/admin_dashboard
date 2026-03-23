"""
Record Linkage Service

Standalone REST API that generates bloom-filter patient hashes and fetches
linked ECG data from PostgreSQL (metadata) and InfluxDB (sensor data).

Port: 7003
"""

import os
import sys
import logging

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.record_linkage import RecordLinkage

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class _Cfg:
    POSTGRES_HOST     = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT     = int(os.getenv('POSTGRES_PORT', 5432))
    POSTGRES_DB       = os.getenv('POSTGRES_DB', 'privacy_umbrella')
    POSTGRES_USER     = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

    INFLUX_URL        = os.getenv('INFLUX_URL', 'http://localhost:8086')
    INFLUX_TOKEN      = os.getenv('INFLUX_TOKEN', '')
    INFLUX_ORG        = os.getenv('INFLUX_ORG', 'mcs-data-labs')
    INFLUX_BUCKET_RAW = os.getenv('INFLUX_BUCKET_RAW', 'raw-data')
    INFLUX_BUCKET_ANON= os.getenv('INFLUX_BUCKET_ANON', 'anonymized-data')

    LINKED_OUTPUT_DIR = os.getenv('LINKED_OUTPUT_DIR', './output/linked_records')

cfg = _Cfg()

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
record_linkage = RecordLinkage(cfg)

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
API_KEY = os.getenv('API_KEY', '')

def _auth_error():
    if not API_KEY:
        return None
    if request.headers.get('X-API-Key') != API_KEY:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    return None

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# ── Health ──────────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'record_linkage'})

# ── Linkage ──────────────────────────────────────────────────────────────────

@app.route('/api/fetch', methods=['POST'])
def fetch_by_pii():
    """Fetch patient data by personal identifiers (name, DOB, gender)."""
    err = _auth_error()
    if err: return err

    data = request.get_json(silent=True) or {}
    required = ['given_name', 'family_name', 'dob', 'gender']
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'success': False, 'error': f'Missing fields: {missing}'}), 400

    result = record_linkage.link_patient_data(
        given_name=data['given_name'],
        family_name=data['family_name'],
        dob=data['dob'],
        gender=data['gender'],
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        include_raw=data.get('include_raw', True),
        include_anonymized=data.get('include_anonymized', True),
        limit=int(data.get('limit', 1000)),
    )
    return jsonify({'success': True, 'data': result})


@app.route('/api/fetch-by-key', methods=['POST'])
def fetch_by_key():
    """Fetch patient data by unique_key directly."""
    err = _auth_error()
    if err: return err

    data = request.get_json(silent=True) or {}
    unique_key = data.get('unique_key', '').strip()
    if not unique_key:
        return jsonify({'success': False, 'error': 'unique_key is required'}), 400

    result = record_linkage.link_patient_data_by_key(
        unique_key=unique_key,
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        include_raw=data.get('include_raw', True),
        include_anonymized=data.get('include_anonymized', True),
        limit=int(data.get('limit', 1000)),
    )
    return jsonify({'success': True, 'data': result})


@app.route('/api/verify-patient', methods=['POST'])
def verify_patient():
    """Check if a patient exists in PostgreSQL by PII."""
    err = _auth_error()
    if err: return err

    data = request.get_json(silent=True) or {}
    required = ['given_name', 'family_name', 'dob', 'gender']
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'success': False, 'error': f'Missing fields: {missing}'}), 400

    unique_key = record_linkage.generate_unique_key(
        data['given_name'], data['family_name'], data['dob'], data['gender']
    )
    metadata = record_linkage.fetch_patient_metadata(unique_key)
    return jsonify({
        'success': True,
        'found': metadata is not None,
        'unique_key': unique_key,
        'metadata': metadata,
    })


@app.route('/api/verify-unique-key', methods=['POST'])
def verify_unique_key():
    """Check if a unique_key exists in PostgreSQL."""
    err = _auth_error()
    if err: return err

    data = request.get_json(silent=True) or {}
    unique_key = data.get('unique_key', '').strip()
    if not unique_key:
        return jsonify({'success': False, 'error': 'unique_key is required'}), 400

    metadata = record_linkage.fetch_patient_metadata(unique_key)
    return jsonify({
        'success': True,
        'found': metadata is not None,
        'unique_key': unique_key,
        'metadata': metadata,
    })


# ── Export ───────────────────────────────────────────────────────────────────

@app.route('/api/export/csv', methods=['POST'])
def export_csv():
    err = _auth_error()
    if err: return err

    data = request.get_json(silent=True) or {}
    patient_data = data.get('patient_data')
    if not patient_data:
        return jsonify({'success': False, 'error': 'patient_data is required'}), 400

    filepath = record_linkage.export_to_csv(patient_data, cfg.LINKED_OUTPUT_DIR)
    return jsonify({'success': True, 'filepath': filepath})


@app.route('/api/export/json', methods=['POST'])
def export_json():
    err = _auth_error()
    if err: return err

    data = request.get_json(silent=True) or {}
    patient_data = data.get('patient_data')
    if not patient_data:
        return jsonify({'success': False, 'error': 'patient_data is required'}), 400

    filepath = record_linkage.export_to_json(patient_data, cfg.LINKED_OUTPUT_DIR)
    return jsonify({'success': True, 'filepath': filepath})

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port  = int(os.getenv('PORT', 7003))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f"Record Linkage Service starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
