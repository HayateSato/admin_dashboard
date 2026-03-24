"""
Admin Dashboard (API Gateway)

Thin Flask frontend that:
  - Handles session-based authentication
  - Serves Jinja2 HTML pages
  - Proxies all /api/* calls to the appropriate backend microservices

It does NOT connect to any database or broker directly.

Port: 5000

Service URLs (configure via .env):
  PATIENT_REGISTRY_URL    = http://localhost:7001
  FEDERATED_LEARNING_URL  = http://localhost:7002
  RECORD_LINKAGE_URL      = http://localhost:7003
  CENTRAL_ANON_URL        = http://localhost:6000
"""

import os
import sys
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from functools import wraps

import redis as _redis
import requests as _requests
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session, flash)
from flask_cors import CORS
from flask_session import Session
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.FileHandler('logs/dashboard.log'), logging.StreamHandler()],
)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SECRET_KEY             = os.getenv('SECRET_KEY', secrets.token_hex(32))
SESSION_TIMEOUT_HOURS  = int(os.getenv('SESSION_TIMEOUT_HOURS', 8))
REDIS_URL              = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

PATIENT_REGISTRY_URL   = os.getenv('PATIENT_REGISTRY_URL',   'http://localhost:7001')
FEDERATED_LEARNING_URL = os.getenv('FEDERATED_LEARNING_URL', 'http://localhost:7002')
RECORD_LINKAGE_URL     = os.getenv('RECORD_LINKAGE_URL',      'http://localhost:7003')
CENTRAL_ANON_URL       = os.getenv('CENTRAL_ANON_URL',        'http://localhost:6000')

# Hardcoded default admin — replace with DB-backed user management for production
_ADMIN_PASSWORD_HASH = hashlib.sha256(
    os.getenv('ADMIN_PASSWORD', 'admin123').encode()
).hexdigest()

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=SESSION_TIMEOUT_HOURS)

# Redis-backed server-side sessions
# Session data is stored in Redis; the browser only holds an opaque session ID cookie.
app.config['SESSION_TYPE']             = 'redis'
app.config['SESSION_REDIS']            = _redis.from_url(REDIS_URL)
app.config['SESSION_PERMANENT']        = True
app.config['SESSION_USE_SIGNER']       = True   # signs the cookie so it can't be forged
app.config['SESSION_KEY_PREFIX']       = 'pu_session:'
Session(app)

# Separate Redis client used only for caching (DB 1, so cache and sessions don't share a namespace)
_cache = _redis.from_url(REDIS_URL.rstrip('/0').rstrip('/') + '/1')
HEALTH_CACHE_TTL = 10  # seconds

CORS(app)

# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session or session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# ---------------------------------------------------------------------------
# Service proxy helper
# ---------------------------------------------------------------------------

def _proxy(method: str, service_url: str, path: str, **kwargs):
    """Forward a request to a backend service and return its JSON response."""
    url = service_url.rstrip('/') + path
    try:
        resp = getattr(_requests, method)(url, timeout=120, **kwargs)
        return jsonify(resp.json()), resp.status_code
    except _requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': f'Service unavailable: {service_url}'}), 503
    except Exception as exc:
        logger.error(f"Proxy error [{method.upper()} {url}]: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500

# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        pw_hash  = hashlib.sha256(password.encode()).hexdigest()

        if username == os.getenv('ADMIN_USERNAME', 'admin') and pw_hash == _ADMIN_PASSWORD_HASH:
            session.permanent = True
            session['user']   = username
            session['role']   = 'admin'
            logger.info(f"Login: {username}")
            return redirect(url_for('dashboard'))

        flash('Invalid username or password', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    user = session.pop('user', None)
    session.clear()
    logger.info(f"Logout: {user}")
    return redirect(url_for('login'))

# ---------------------------------------------------------------------------
# Page routes (serve HTML)
# ---------------------------------------------------------------------------

def _cached_health(url: str):
    """
    Fetch /health for a service, caching the result in Redis for HEALTH_CACHE_TTL seconds.

    Cache key:  health:<url>
    Cache value: JSON string {"status": "ok"|"error"|"unreachable", "data": {...}}

    Returns (status_str, detail_dict).
    """
    import json
    cache_key = f'health:{url}'

    # 1. Try the cache first
    cached = _cache.get(cache_key)
    if cached:
        payload = json.loads(cached)
        logger.debug(f"Cache HIT  {cache_key}")
        return payload['status'], payload['data']

    # 2. Cache miss — call the real service
    logger.debug(f"Cache MISS {cache_key}")
    try:
        r = _requests.get(url + '/health', timeout=3)
        data = r.json()
        status = 'ok' if r.ok else 'error'
    except Exception:
        status, data = 'unreachable', {}

    # 3. Store result in Redis with TTL
    _cache.set(cache_key, json.dumps({'status': status, 'data': data}), ex=HEALTH_CACHE_TTL)
    return status, data


@app.route('/dashboard')
@login_required
def dashboard():
    fl_status,       fl_data       = _cached_health(FEDERATED_LEARNING_URL)
    patient_status,  _             = _cached_health(PATIENT_REGISTRY_URL)
    record_status,   _             = _cached_health(RECORD_LINKAGE_URL)
    anon_status,     _             = _cached_health(CENTRAL_ANON_URL)

    fl_server_running = fl_data.get('fl_server_running', False)

    services = [
        {'name': 'Patient Registry',      'status': patient_status,  'port': 7001, 'icon': 'bi-people-fill'},
        {'name': 'Federated Learning',    'status': fl_status,       'port': 7002, 'icon': 'bi-diagram-3'},
        {'name': 'Record Linkage',        'status': record_status,   'port': 7003, 'icon': 'bi-link-45deg'},
        {'name': 'Central Anonymization', 'status': anon_status,     'port': 6000, 'icon': 'bi-incognito'},
    ]

    healthy_count = sum(1 for s in services if s['status'] == 'ok')

    # Try to fetch recent anonymization jobs
    recent_jobs = []
    try:
        r = _requests.get(CENTRAL_ANON_URL + '/api/v1/anonymize/jobs', timeout=3)
        if r.ok:
            recent_jobs = r.json().get('jobs', [])[:5]
    except Exception:
        pass

    system_status = {
        'services_healthy': healthy_count,
        'influxdb_status': 'external',
        'postgres_status': 'internal',
        'fl_server_status': 'running' if fl_server_running else ('stopped' if fl_status == 'ok' else 'unknown'),
    }

    return render_template(
        'dashboard.html',
        user=session.get('user'),
        role=session.get('role'),
        system_status=system_status,
        services=services,
        recent_jobs=recent_jobs,
        recent_audits=[],
    )


@app.route('/registered-patients')
@login_required
@admin_required
def registered_patients():
    return render_template('registered_patients.html', user=session.get('user'), role=session.get('role'))


@app.route('/federated-learning')
@login_required
def federated_learning():
    return render_template('fl_orchestration.html', user=session.get('user'), role=session.get('role'))


@app.route('/record-linkage')
@login_required
def record_linkage():
    return render_template('record_linkage.html', user=session.get('user'), role=session.get('role'))


@app.route('/anonymization')
@login_required
def anonymization():
    return render_template('anonymization.html', user=session.get('user'), role=session.get('role'))


@app.route('/settings')
@login_required
@admin_required
def settings():
    return render_template('settings.html', user=session.get('user'), role=session.get('role'))

# ---------------------------------------------------------------------------
# API proxy routes — Patient Registry
# ---------------------------------------------------------------------------

@app.route('/api/patients/list', methods=['GET'])
@login_required
def api_patients_list():
    return _proxy('get', PATIENT_REGISTRY_URL, '/api/patients')


@app.route('/api/patients/<unique_key>/update-settings', methods=['POST'])
@login_required
def api_patients_update_settings(unique_key):
    return _proxy('post', PATIENT_REGISTRY_URL,
                  f'/api/patients/{unique_key}/settings',
                  json=request.get_json(silent=True) or {})


@app.route('/api/patients/<unique_key>/toggle-remote-anon', methods=['POST'])
@login_required
def api_patients_toggle_remote_anon(unique_key):
    return _proxy('post', PATIENT_REGISTRY_URL,
                  f'/api/patients/{unique_key}/toggle-remote-anon',
                  json=request.get_json(silent=True) or {})


@app.route('/api/mqtt/status', methods=['GET'])
@login_required
def api_mqtt_status():
    return _proxy('get', PATIENT_REGISTRY_URL, '/api/mqtt/status')

# ---------------------------------------------------------------------------
# API proxy routes — Federated Learning
# ---------------------------------------------------------------------------

@app.route('/api/fl/status', methods=['GET'])
@login_required
def api_fl_status():
    return _proxy('get', FEDERATED_LEARNING_URL, '/api/fl/status')


@app.route('/api/fl/clients', methods=['GET'])
@login_required
def api_fl_clients():
    return _proxy('get', FEDERATED_LEARNING_URL, '/api/fl/clients')


@app.route('/api/fl/global-model', methods=['GET'])
@login_required
def api_fl_global_model():
    return _proxy('get', FEDERATED_LEARNING_URL, '/api/fl/global-model')


@app.route('/api/fl/start-training', methods=['POST'])
@login_required
@admin_required
def api_fl_start_training():
    return _proxy('post', FEDERATED_LEARNING_URL, '/api/fl/training/start',
                  json=request.get_json(silent=True) or {})


@app.route('/api/fl/stop-training', methods=['POST'])
@login_required
@admin_required
def api_fl_stop_training():
    return _proxy('post', FEDERATED_LEARNING_URL, '/api/fl/training/stop')


@app.route('/api/fl/training-history', methods=['GET'])
@login_required
def api_fl_training_history():
    return _proxy('get', FEDERATED_LEARNING_URL, '/api/fl/training/history')


@app.route('/api/fl/server/start', methods=['POST'])
@login_required
@admin_required
def api_fl_server_start():
    return _proxy('post', FEDERATED_LEARNING_URL, '/api/fl/server/start',
                  json=request.get_json(silent=True) or {})


@app.route('/api/fl/server/stop', methods=['POST'])
@login_required
@admin_required
def api_fl_server_stop():
    return _proxy('post', FEDERATED_LEARNING_URL, '/api/fl/server/stop')


@app.route('/api/fl/server/status', methods=['GET'])
@login_required
def api_fl_server_status():
    return _proxy('get', FEDERATED_LEARNING_URL, '/api/fl/server/status')


@app.route('/api/fl/server/status-details', methods=['GET'])
@login_required
def api_fl_server_status_details():
    return _proxy('get', FEDERATED_LEARNING_URL, '/api/fl/server/status-details')


@app.route('/api/fl/training/stats', methods=['GET'])
@login_required
def api_fl_training_stats():
    return _proxy('get', FEDERATED_LEARNING_URL, '/api/fl/training/stats')

# ---------------------------------------------------------------------------
# API proxy routes — Record Linkage
# ---------------------------------------------------------------------------

@app.route('/api/record-linkage/fetch', methods=['POST'])
@login_required
def api_record_linkage_fetch():
    return _proxy('post', RECORD_LINKAGE_URL, '/api/fetch',
                  json=request.get_json(silent=True) or {})


@app.route('/api/record-linkage/fetch-by-key', methods=['POST'])
@login_required
def api_record_linkage_fetch_by_key():
    return _proxy('post', RECORD_LINKAGE_URL, '/api/fetch-by-key',
                  json=request.get_json(silent=True) or {})


@app.route('/api/record-linkage/export-csv', methods=['POST'])
@login_required
def api_record_linkage_export_csv():
    return _proxy('post', RECORD_LINKAGE_URL, '/api/export/csv',
                  json=request.get_json(silent=True) or {})


@app.route('/api/record-linkage/export-json', methods=['POST'])
@login_required
def api_record_linkage_export_json():
    return _proxy('post', RECORD_LINKAGE_URL, '/api/export/json',
                  json=request.get_json(silent=True) or {})

# ---------------------------------------------------------------------------
# API proxy routes — Central Anonymization
# ---------------------------------------------------------------------------

@app.route('/api/anonymization/jobs', methods=['GET'])
@login_required
def api_anon_jobs():
    params = request.args.to_dict()
    return _proxy('get', CENTRAL_ANON_URL, '/api/v1/anonymize/jobs', params=params)


@app.route('/api/anonymization/verify-patient', methods=['POST'])
@login_required
def api_anon_verify_patient():
    return _proxy('post', RECORD_LINKAGE_URL, '/api/verify-patient',
                  json=request.get_json(silent=True) or {})


@app.route('/api/anonymization/verify-unique-key', methods=['POST'])
@login_required
def api_anon_verify_unique_key():
    return _proxy('post', RECORD_LINKAGE_URL, '/api/verify-unique-key',
                  json=request.get_json(silent=True) or {})


@app.route('/api/anonymization/trigger', methods=['POST'])
@login_required
def api_anon_trigger():
    return _proxy('post', CENTRAL_ANON_URL, '/api/v1/anonymize',
                  json=request.get_json(silent=True) or {})


@app.route('/api/anonymization/jobs/<job_id>/status', methods=['GET'])
@login_required
def api_anon_job_status(job_id):
    return _proxy('get', CENTRAL_ANON_URL, f'/api/v1/anonymize/jobs/{job_id}/status')


@app.route('/api/anonymization/jobs/<job_id>/cancel', methods=['POST'])
@login_required
def api_anon_job_cancel(job_id):
    return _proxy('post', CENTRAL_ANON_URL, f'/api/v1/anonymize/jobs/{job_id}/cancel')

# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
    return render_template('500.html'), 500

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port  = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f"Admin Dashboard starting on port {port}")
    logger.info(f"  Patient Registry : {PATIENT_REGISTRY_URL}")
    logger.info(f"  Federated Learning: {FEDERATED_LEARNING_URL}")
    logger.info(f"  Record Linkage   : {RECORD_LINKAGE_URL}")
    logger.info(f"  Central Anon     : {CENTRAL_ANON_URL}")
    app.run(host='0.0.0.0', port=port, debug=debug)
