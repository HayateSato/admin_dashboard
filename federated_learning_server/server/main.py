"""
Federated Learning Server Service

Standalone REST API that manages the FL gRPC server lifecycle and
exposes training status, connected clients, and global model information.

Port: 7002  (gRPC server itself runs on 50051 internally)
"""

import os
import sys
import logging

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Add parent dir so `core` and `grpc` packages are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# The fl_orchestrator expects sys.path to include the grpc utils directory
grpc_dir = os.path.join(os.path.dirname(__file__), '..', 'grpc')
sys.path.insert(0, grpc_dir)

from core.fl_orchestrator import FLOrchestrator

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
    FL_SERVER_HOST = os.getenv('FL_SERVER_HOST', 'localhost')
    FL_SERVER_PORT = int(os.getenv('FL_SERVER_PORT', 50051))
    FL_MODEL_PATH  = os.getenv(
        'FL_MODEL_PATH',
        os.path.join(os.path.dirname(__file__), '..', 'grpc', 'global_model_latest.json')
    )

cfg = _Cfg()

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
fl_orchestrator = FLOrchestrator(cfg)

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
    server_running = (
        fl_orchestrator.fl_server_process is not None and
        fl_orchestrator.fl_server_process.poll() is None
    )
    return jsonify({
        'status': 'ok',
        'service': 'federated_learning',
        'fl_server_running': server_running,
    })

# ── Server lifecycle ─────────────────────────────────────────────────────────

@app.route('/api/fl/server/start', methods=['POST'])
def start_server():
    err = _auth_error()
    if err: return err
    data = request.get_json(silent=True) or {}
    expected_clients = int(data.get('expected_clients', 3))
    result = fl_orchestrator.start_fl_server(expected_clients=expected_clients)
    return jsonify({'success': result.get('status') not in ('error',), **result})


@app.route('/api/fl/server/stop', methods=['POST'])
def stop_server():
    err = _auth_error()
    if err: return err
    result = fl_orchestrator.stop_fl_server()
    return jsonify({'success': result.get('status') not in ('error',), **result})


@app.route('/api/fl/server/status', methods=['GET'])
def server_status():
    err = _auth_error()
    if err: return err
    running = (
        fl_orchestrator.fl_server_process is not None and
        fl_orchestrator.fl_server_process.poll() is None
    )
    pid = fl_orchestrator.fl_server_process.pid if running else None
    return jsonify({
        'success': True,
        'running': running,
        'pid': pid,
        'grpc_connected': fl_orchestrator.grpc_stub is not None,
    })


@app.route('/api/fl/server/status-details', methods=['GET'])
def server_status_details():
    err = _auth_error()
    if err: return err
    details = fl_orchestrator.get_server_status_details()
    return jsonify({'success': True, **details})

# ── Training ─────────────────────────────────────────────────────────────────

@app.route('/api/fl/training/start', methods=['POST'])
def start_training():
    err = _auth_error()
    if err: return err
    data = request.get_json(silent=True) or {}
    result = fl_orchestrator.start_training(
        num_rounds=int(data.get('num_rounds', 5)),
        min_clients=int(data.get('min_clients', 2)),
    )
    return jsonify({'success': result.get('status') not in ('error',), **result})


@app.route('/api/fl/training/stop', methods=['POST'])
def stop_training():
    err = _auth_error()
    if err: return err
    result = fl_orchestrator.stop_training()
    return jsonify({'success': True, **result})


@app.route('/api/fl/training/stats', methods=['GET'])
def training_stats():
    err = _auth_error()
    if err: return err
    stats = fl_orchestrator.get_training_stats()
    return jsonify({'success': True, **stats})


@app.route('/api/fl/training/history', methods=['GET'])
def training_history():
    err = _auth_error()
    if err: return err
    limit = int(request.args.get('limit', 20))
    history = fl_orchestrator.get_training_history(limit=limit)
    return jsonify({'success': True, 'history': history})

# ── Clients & model ──────────────────────────────────────────────────────────

@app.route('/api/fl/clients', methods=['GET'])
def connected_clients():
    err = _auth_error()
    if err: return err
    clients = fl_orchestrator.get_connected_clients()
    return jsonify({'success': True, 'clients': clients})


@app.route('/api/fl/global-model', methods=['GET'])
def global_model():
    err = _auth_error()
    if err: return err
    info = fl_orchestrator.get_global_model_info()
    return jsonify({'success': True, 'model': info})


@app.route('/api/fl/status', methods=['GET'])
def fl_status():
    err = _auth_error()
    if err: return err
    status = fl_orchestrator.get_fl_status()
    return jsonify({'success': True, **status})

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port  = int(os.getenv('PORT', 7002))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f"Federated Learning Server Service starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
