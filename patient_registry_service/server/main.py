"""
Patient Registry Service

Standalone REST API that manages registered patient data (PostgreSQL)
and publishes privacy-settings updates to patient devices via MQTT.

Port: 7001
"""

import os
import sys
import logging
import secrets
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.patient_manager import PatientManager
from core.mqtt_manager import MQTTManager

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

cfg = _Cfg()

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
patient_manager = PatientManager(cfg)

mqtt_manager = MQTTManager(
    broker_host=os.getenv('MQTT_BROKER_HOST', 'localhost'),
    broker_port=int(os.getenv('MQTT_BROKER_PORT', 1883)),
    topic_prefix='anonymization',
)
try:
    mqtt_manager.connect()
except Exception as exc:
    logger.warning(f"MQTT broker not available at startup: {exc}")

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
    return jsonify({
        'status': 'ok',
        'service': 'patient_registry',
        'mqtt_connected': mqtt_manager.is_connected(),
    })

# ── Patients ─────────────────────────────────────────────────────────────────

@app.route('/api/patients', methods=['GET'])
def list_patients():
    err = _auth_error()
    if err: return err
    patients = patient_manager.get_all_patients()
    return jsonify({'success': True, 'patients': patients})


@app.route('/api/patients/<unique_key>', methods=['GET'])
def get_patient(unique_key):
    err = _auth_error()
    if err: return err
    patient = patient_manager.get_patient_by_unique_key(unique_key)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    return jsonify({'success': True, 'patient': patient})


@app.route('/api/patients/<unique_key>/settings', methods=['POST'])
def update_settings(unique_key):
    """Update privacy settings in DB and publish to device via MQTT."""
    err = _auth_error()
    if err: return err

    data = request.get_json(silent=True) or {}
    settings = {
        'k_value':        int(data.get('k_value', 5)),
        'time_window':    int(data.get('time_window', 30)),
        'auto_anonymize': bool(data.get('auto_anonymize', False)),
    }

    db_ok = patient_manager.update_privacy_settings(unique_key, settings)
    mqtt_ok = mqtt_manager.publish_settings_update(unique_key, settings) if mqtt_manager.is_connected() else False

    return jsonify({
        'success': db_ok,
        'db_updated': db_ok,
        'mqtt_published': mqtt_ok,
        'settings': settings,
    })


@app.route('/api/patients/<unique_key>/toggle-remote-anon', methods=['POST'])
def toggle_remote_anon(unique_key):
    """Enable or disable remote anonymization for a patient."""
    err = _auth_error()
    if err: return err

    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', False))

    db_ok   = patient_manager.update_remote_anon_status(unique_key, enabled)
    mqtt_ok = mqtt_manager.publish_remote_anon_activation(unique_key, enabled) if mqtt_manager.is_connected() else False

    return jsonify({
        'success': db_ok,
        'db_updated': db_ok,
        'mqtt_published': mqtt_ok,
        'enabled': enabled,
    })


@app.route('/api/patients/remote-anon-enabled', methods=['GET'])
def patients_with_remote_anon():
    err = _auth_error()
    if err: return err
    patients = patient_manager.get_patients_with_remote_anon_enabled()
    return jsonify({'success': True, 'patients': patients})

# ── MQTT status ───────────────────────────────────────────────────────────────

@app.route('/api/mqtt/status', methods=['GET'])
def mqtt_status():
    err = _auth_error()
    if err: return err
    return jsonify({'success': True, 'status': mqtt_manager.get_status()})

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port  = int(os.getenv('PORT', 7001))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f"Patient Registry Service starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
