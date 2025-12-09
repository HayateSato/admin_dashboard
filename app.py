"""
Privacy Umbrella Admin Dashboard
Main Flask application for orchestrating backend services

Features:
- System monitoring interface
- User and policy management
- Federated learning orchestration
- Anonymization configuration and batch job triggering
- Data access controls and audit viewing
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from functools import wraps
import os
import sys
import logging
from datetime import datetime, timedelta
import hashlib
import secrets

# Add parent directory to path for importing backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import dashboard modules
from modules.system_monitor import SystemMonitor
from modules.user_manager import UserManager
from modules.fl_orchestrator import FLOrchestrator
from modules.anonymization_manager import AnonymizationManager
from modules.audit_logger import AuditLogger
from modules.record_linkage import RecordLinkage
from modules.patient_manager import PatientManager
from modules.mqtt_manager import MQTTManager
from config import Config

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# Enable CORS
CORS(app)

# Configure logging
# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Set up main logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/admin_dashboard.log'),
        logging.StreamHandler()
    ]
)

# Set up FL operations logger (separate file, no Flask HTTP logs)
fl_logger = logging.getLogger('modules.fl_orchestrator')
fl_logger.setLevel(logging.INFO)
fl_file_handler = logging.FileHandler('logs/fl_operations.txt')
fl_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
fl_logger.addHandler(fl_file_handler)

# Suppress Flask HTTP request logs from console and FL log file
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)  # Only show warnings/errors, not INFO (GET/POST)

logger = logging.getLogger(__name__)

# Load configuration
config = Config()

# Initialize modules
system_monitor = SystemMonitor(config)
user_manager = UserManager(config)
fl_orchestrator = FLOrchestrator(config)
anonymization_manager = AnonymizationManager(config)
audit_logger = AuditLogger(config)
record_linkage = RecordLinkage(config)
patient_manager = PatientManager(config)

# Initialize MQTT manager
# IMPORTANT: topic_prefix must match Flutter app (anonymization)
mqtt_manager = MQTTManager(
    broker_host=config.MQTT_BROKER_HOST,
    broker_port=config.MQTT_BROKER_PORT,
    topic_prefix='anonymization'  # Changed from 'privacy' to match Flutter app
)
# Connect to MQTT broker (will log error if broker not available)
try:
    mqtt_manager.connect()
except Exception as e:
    logger.warning(f"MQTT broker not available: {e}")


# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/')
def index():
    """Redirect to dashboard or login"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Authenticate user
        user = user_manager.authenticate(username, password)

        if user:
            session['user'] = user['username']
            session['role'] = user['role']
            session['user_id'] = user['id']

            # Log audit event
            audit_logger.log_event(
                user_id=user['id'],
                event_type='login',
                description=f"User {username} logged in",
                ip_address=request.remote_addr
            )

            flash(f'Welcome, {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout user"""
    user = session.get('user')
    user_id = session.get('user_id')

    if user:
        # Log audit event
        audit_logger.log_event(
            user_id=user_id,
            event_type='logout',
            description=f"User {user} logged out",
            ip_address=request.remote_addr
        )

    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


# ============================================================================
# DASHBOARD ROUTES
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard overview"""
    # Get system status summary
    system_status = system_monitor.get_system_status()
    recent_jobs = anonymization_manager.get_recent_jobs(limit=5)
    fl_status = fl_orchestrator.get_fl_status()
    recent_audits = audit_logger.get_recent_events(limit=10)

    return render_template(
        'dashboard.html',
        system_status=system_status,
        recent_jobs=recent_jobs,
        fl_status=fl_status,
        recent_audits=recent_audits,
        user=session.get('user'),
        role=session.get('role')
    )


# # ============================================================================
# # SYSTEM MONITORING ROUTES
# # ============================================================================

# @app.route('/monitoring')
# @login_required
# def monitoring():
#     """System monitoring interface"""
#     return render_template('monitoring.html', user=session.get('user'), role=session.get('role'))


# @app.route('/api/monitoring/system-stats')
# @login_required
# def get_system_stats():
#     """Get real-time system statistics"""
#     stats = system_monitor.get_detailed_stats()
#     return jsonify(stats)


# @app.route('/api/monitoring/influxdb-status')
# @login_required
# def get_influxdb_status():
#     """Get InfluxDB connection status and metrics"""
#     status = system_monitor.check_influxdb()
#     return jsonify(status)


# @app.route('/api/monitoring/postgres-status')
# @login_required
# def get_postgres_status():
#     """Get PostgreSQL connection status and metrics"""
#     status = system_monitor.check_postgres()
#     return jsonify(status)


# @app.route('/api/monitoring/fl-server-status')
# @login_required
# def get_fl_server_status():
#     """Get FL server status"""
#     status = system_monitor.check_fl_server()
#     return jsonify(status)


# @app.route('/api/monitoring/logs')
# @login_required
# def get_system_logs():
#     """Get system logs"""
#     service = request.args.get('service', 'all')
#     limit = int(request.args.get('limit', 100))

#     logs = system_monitor.get_logs(service=service, limit=limit)
#     return jsonify(logs)


# # ============================================================================
# # USER MANAGEMENT ROUTES
# # ============================================================================

# @app.route('/users')
# @login_required
# @admin_required
# def users():
#     """User management interface"""
#     all_users = user_manager.get_all_users()
#     return render_template('users.html', users=all_users, user=session.get('user'), role=session.get('role'))


# @app.route('/api/users/list')
# @login_required
# @admin_required
# def list_users():
#     """Get list of all users"""
#     users = user_manager.get_all_users()
#     return jsonify(users)


# @app.route('/api/users/create', methods=['POST'])
# @login_required
# @admin_required
# def create_user():
#     """Create new user"""
#     data = request.json
#     username = data.get('username')
#     password = data.get('password')
#     role = data.get('role', 'user')
#     email = data.get('email')

#     try:
#         user = user_manager.create_user(username, password, role, email)

#         # Log audit event
#         audit_logger.log_event(
#             user_id=session.get('user_id'),
#             event_type='user_create',
#             description=f"Created user {username} with role {role}",
#             ip_address=request.remote_addr
#         )

#         return jsonify({'success': True, 'user': user})
#     except Exception as e:
#         logger.error(f"Failed to create user: {e}")
#         return jsonify({'success': False, 'error': str(e)}), 400


# @app.route('/api/users/<int:user_id>/update', methods=['PUT'])
# @login_required
# @admin_required
# def update_user(user_id):
#     """Update user details"""
#     data = request.json

#     try:
#         user = user_manager.update_user(user_id, data)

#         # Log audit event
#         audit_logger.log_event(
#             user_id=session.get('user_id'),
#             event_type='user_update',
#             description=f"Updated user {user_id}",
#             ip_address=request.remote_addr,
#             metadata=data
#         )

#         return jsonify({'success': True, 'user': user})
#     except Exception as e:
#         logger.error(f"Failed to update user: {e}")
#         return jsonify({'success': False, 'error': str(e)}), 400


# @app.route('/api/users/<int:user_id>/delete', methods=['DELETE'])
# @login_required
# @admin_required
# def delete_user(user_id):
#     """Delete user"""
#     try:
#         user_manager.delete_user(user_id)

#         # Log audit event
#         audit_logger.log_event(
#             user_id=session.get('user_id'),
#             event_type='user_delete',
#             description=f"Deleted user {user_id}",
#             ip_address=request.remote_addr
#         )

#         return jsonify({'success': True})
#     except Exception as e:
#         logger.error(f"Failed to delete user: {e}")
#         return jsonify({'success': False, 'error': str(e)}), 400


# ============================================================================
# REGISTERED PATIENTS MANAGEMENT ROUTES
# ============================================================================

@app.route('/registered-patients')
@login_required
@admin_required
def registered_patients():
    """Registered patients management page"""
    return render_template(
        'registered_patients.html',
        user=session.get('user'),
        role=session.get('role')
    )


@app.route('/api/patients/list')
@login_required
def get_patients_list():
    """Get list of all registered patients with privacy settings"""
    try:
        patients = patient_manager.get_all_patients()
        return jsonify({'success': True, 'patients': patients})
    except Exception as e:
        logger.error(f"Error getting patients list: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/patients/<unique_key>/update-settings', methods=['POST'])
@login_required
@admin_required
def update_patient_settings(unique_key):
    """Update patient privacy settings via MQTT"""
    try:
        data = request.json
        settings = {
            'k_value': data.get('k_value'),
            'time_window': data.get('time_window'),
            'auto_anonymize': data.get('auto_anonymize')
        }

        logger.info(f"Admin {session.get('user')} updating settings for patient {unique_key[:16]}...")
        logger.info(f"New settings: K={settings['k_value']}, TimeWindow={settings['time_window']}s, AutoAnon={settings['auto_anonymize']}")

        # Publish settings update to MQTT
        mqtt_success = mqtt_manager.publish_settings_update(unique_key, settings)

        if mqtt_success:
            # Also update database
            db_success = patient_manager.update_privacy_settings(unique_key, settings)

            # Log audit event
            audit_logger.log_event(
                user_id=session.get('user_id'),
                event_type='privacy_settings_update',
                description=f"Updated privacy settings for patient {unique_key[:16]}... via MQTT",
                ip_address=request.remote_addr,
                metadata=settings
            )

            return jsonify({
                'success': True,
                'message': 'Settings sent to device via MQTT',
                'mqtt_published': mqtt_success,
                'database_updated': db_success
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to publish settings to MQTT. Is the broker running?'
            }), 500

    except Exception as e:
        logger.error(f"Error updating patient settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/patients/<unique_key>/toggle-remote-anon', methods=['POST'])
@login_required
@admin_required
def toggle_remote_anonymization(unique_key):
    """Toggle remote anonymization activation for patient"""
    try:
        data = request.json
        enabled = data.get('enabled', False)

        logger.info(f"Admin {session.get('user')} {'enabling' if enabled else 'disabling'} remote anon for {unique_key[:16]}...")

        # Publish remote anon activation to MQTT
        mqtt_success = mqtt_manager.publish_remote_anon_activation(unique_key, enabled)

        if mqtt_success:
            # Update database
            db_success = patient_manager.update_remote_anon_status(unique_key, enabled)

            # Log audit event
            audit_logger.log_event(
                user_id=session.get('user_id'),
                event_type='remote_anon_toggle',
                description=f"{'Enabled' if enabled else 'Disabled'} remote anonymization for patient {unique_key[:16]}...",
                ip_address=request.remote_addr,
                metadata={'enabled': enabled, 'unique_key': unique_key[:16] + '...'}
            )

            return jsonify({
                'success': True,
                'message': f"Remote anonymization {'enabled' if enabled else 'disabled'}",
                'mqtt_published': mqtt_success,
                'database_updated': db_success
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to publish to MQTT. Is the broker running?'
            }), 500

    except Exception as e:
        logger.error(f"Error toggling remote anonymization: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/mqtt/status')
@login_required
def mqtt_status():
    """Get MQTT connection status"""
    try:
        status = mqtt_manager.get_status()
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        logger.error(f"Error getting MQTT status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# # ============================================================================
# # REMOTE POLICY MANAGEMENT ROUTES
# # ============================================================================

# @app.route('/remote-policy')
# @login_required
# def remote_policy():
#     """Remote privacy policy management interface"""
#     return render_template('remote_policy.html', user=session.get('user'), role=session.get('role'))

# # Redirect old /policies route to /remote-policy for compatibility
# @app.route('/policies')
# @login_required
# def policies():
#     """Redirect to remote_policy"""
#     return redirect(url_for('remote_policy'))


# @app.route('/api/policies/list')
# @login_required
# def list_policies():
#     """Get all privacy policies"""
#     policies = user_manager.get_all_policies()
#     return jsonify(policies)


# @app.route('/api/policies/<unique_key>')
# @login_required
# def get_user_policy(unique_key):
#     """Get privacy policy for specific user"""
#     policy = user_manager.get_user_policy(unique_key)

#     if policy:
#         return jsonify({'success': True, 'policy': policy})
#     else:
#         return jsonify({'success': False, 'error': 'User not found'}), 404


# @app.route('/api/policies/<unique_key>/update', methods=['PUT'])
# @login_required
# @admin_required
# def update_policy(unique_key):
#     """Update privacy policy for user (remote anonymization activation)"""
#     data = request.json
#     k_value = data.get('k_value')
#     time_window = data.get('time_window')
#     override_consent = data.get('override_consent', False)

#     try:
#         result = user_manager.update_user_policy(
#             unique_key=unique_key,
#             k_value=k_value,
#             time_window=time_window,
#             override_consent=override_consent,
#             admin_user_id=session.get('user_id')
#         )

#         # Log audit event
#         audit_logger.log_event(
#             user_id=session.get('user_id'),
#             event_type='policy_update',
#             description=f"Updated privacy policy for user {unique_key}: K={k_value}, window={time_window}s",
#             ip_address=request.remote_addr,
#             metadata=data
#         )

#         return jsonify({'success': True, 'policy': result})
#     except Exception as e:
#         logger.error(f"Failed to update policy: {e}")
#         return jsonify({'success': False, 'error': str(e)}), 400


# ============================================================================
# FEDERATED LEARNING ORCHESTRATION ROUTES
# ============================================================================

@app.route('/federated-learning')
@login_required
def federated_learning():
    """FL orchestration interface"""
    return render_template('fl_orchestration.html', user=session.get('user'), role=session.get('role'))


@app.route('/api/fl/status')
@login_required
def get_fl_status():
    """Get FL server status and training progress"""
    status = fl_orchestrator.get_fl_status()
    return jsonify(status)


@app.route('/api/fl/clients')
@login_required
def get_fl_clients():
    """Get list of connected FL clients"""
    clients = fl_orchestrator.get_connected_clients()
    return jsonify(clients)


@app.route('/api/fl/global-model')
@login_required
def get_global_model():
    """Get current global model information"""
    model_info = fl_orchestrator.get_global_model_info()
    return jsonify(model_info)


@app.route('/api/fl/start-training', methods=['POST'])
@login_required
@admin_required
def start_fl_training():
    """Start FL training round"""
    data = request.json
    num_rounds = data.get('num_rounds', 1)
    min_clients = data.get('min_clients', 2)

    try:
        result = fl_orchestrator.start_training(
            num_rounds=num_rounds,
            min_clients=min_clients
        )

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='fl_training_start',
            description=f"Started FL training: {num_rounds} rounds, min {min_clients} clients",
            ip_address=request.remote_addr,
            metadata=data
        )

        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Failed to start FL training: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/fl/stop-training', methods=['POST'])
@login_required
@admin_required
def stop_fl_training():
    """Stop FL training"""
    try:
        result = fl_orchestrator.stop_training()

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='fl_training_stop',
            description="Stopped FL training",
            ip_address=request.remote_addr
        )

        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Failed to stop FL training: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/fl/training-history')
@login_required
def get_fl_training_history():
    """Get FL training history"""
    limit = int(request.args.get('limit', 20))
    history = fl_orchestrator.get_training_history(limit=limit)
    return jsonify(history)


@app.route('/api/fl/server/start', methods=['POST'])
@login_required
@admin_required
def start_fl_server():
    """Start FL gRPC server as subprocess"""
    try:
        # Get expected_clients from request body (default to 3)
        data = request.get_json() or {}
        expected_clients = data.get('expected_clients', 3)

        # Validate expected_clients
        if not isinstance(expected_clients, int) or expected_clients < 1:
            return jsonify({'status': 'error', 'message': 'expected_clients must be a positive integer'}), 400

        result = fl_orchestrator.start_fl_server(expected_clients=expected_clients)

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='fl_server_start',
            description=f"Started FL gRPC server with {expected_clients} expected clients: {result.get('status')}",
            ip_address=request.remote_addr,
            metadata={'pid': result.get('pid'), 'status': result.get('status'), 'expected_clients': expected_clients}
        )

        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to start FL server: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/fl/server/stop', methods=['POST'])
@login_required
@admin_required
def stop_fl_server():
    """Stop FL gRPC server"""
    try:
        result = fl_orchestrator.stop_fl_server()

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='fl_server_stop',
            description=f"Stopped FL gRPC server: {result.get('status')}",
            ip_address=request.remote_addr,
            metadata={'status': result.get('status')}
        )

        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to stop FL server: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/fl/server/status')
@login_required
def get_fl_server_process_status():
    """Get FL server process status"""
    try:
        # Check if server process is running
        if fl_orchestrator.fl_server_process and fl_orchestrator.fl_server_process.poll() is None:
            status = {
                'running': True,
                'pid': fl_orchestrator.fl_server_process.pid,
                'grpc_connected': fl_orchestrator.grpc_stub is not None
            }
        else:
            status = {
                'running': False,
                'pid': None,
                'grpc_connected': False
            }

        return jsonify(status)
    except Exception as e:
        logger.error(f"Failed to get FL server process status: {e}")
        return jsonify({'running': False, 'error': str(e)}), 500

@app.route('/api/fl/server/status-details')
@login_required
def get_fl_server_status_details():
    """Get detailed FL server status via gRPC"""
    try:
        status = fl_orchestrator.get_server_status_details()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Failed to get FL server status details: {e}")
        return jsonify({'running': False, 'error': str(e)}), 500

@app.route('/api/fl/training/stats')
@login_required
def get_fl_training_stats():
    """Get FL training statistics"""
    try:
        stats = fl_orchestrator.get_training_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get FL training stats: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ANONYMIZATION MANAGEMENT ROUTES
# ============================================================================

@app.route('/anonymization')
@login_required
def anonymization():
    """Anonymization configuration and batch job interface"""
    return render_template('anonymization.html', user=session.get('user'), role=session.get('role'))


@app.route('/api/anonymization/jobs')
@login_required
def get_anonymization_jobs():
    """Get list of anonymization jobs"""
    status = request.args.get('status', 'all')
    limit = int(request.args.get('limit', 50))

    jobs = anonymization_manager.get_jobs(status=status, limit=limit)
    return jsonify(jobs)


@app.route('/api/anonymization/verify-patient', methods=['POST'])
@login_required
def verify_patient():
    """Verify patient exists and get available data dates"""
    data = request.json
    given_name = data.get('given_name')
    family_name = data.get('family_name')
    dob = data.get('dob')
    gender = data.get('gender')

    if not all([given_name, family_name, dob, gender]):
        return jsonify({
            'success': False,
            'error': 'All patient information fields are required'
        }), 400

    try:
        result = anonymization_manager.verify_patient(
            given_name=given_name,
            family_name=family_name,
            dob=dob,
            gender=gender
        )

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='patient_verification',
            description=f"Verified patient: {given_name} {family_name}",
            ip_address=request.remote_addr,
            metadata={'exists': result.get('exists'), 'total_records': result.get('total_records', 0)}
        )

        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Failed to verify patient: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/anonymization/verify-unique-key', methods=['POST'])
@login_required
def verify_unique_key():
    """Verify unique key exists and get available data dates"""
    data = request.json
    unique_key = data.get('unique_key')

    if not unique_key:
        return jsonify({
            'success': False,
            'error': 'Unique key is required'
        }), 400

    # Validate unique key format (base64, minimum 64 characters)
    if not isinstance(unique_key, str) or len(unique_key) < 64:
        return jsonify({
            'success': False,
            'error': 'Invalid unique key format. Must be a base64-encoded string (at least 64 characters).'
        }), 400

    try:
        # Use the anonymization manager to check data availability for this unique key
        result = anonymization_manager.verify_unique_key(unique_key)

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='unique_key_verification',
            description=f"Verified unique key: {unique_key[:16]}...",
            ip_address=request.remote_addr,
            metadata={'exists': result.get('exists'), 'total_records': result.get('total_records', 0)}
        )

        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Failed to verify unique key: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/anonymization/trigger', methods=['POST'])
@login_required
def trigger_anonymization():
    """Trigger central anonymization job"""
    data = request.json
    unique_key = data.get('unique_key')
    patient_name = data.get('patient_name')
    k_value = data.get('k_value', 5)
    batch_size_seconds = data.get('batch_size_seconds', 5)
    output_format = data.get('output_format', 'csv')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    api_server_ip = data.get('api_server_ip')
    api_server_port = data.get('api_server_port')

    if not unique_key:
        return jsonify({'success': False, 'error': 'Unique key is required'}), 400

    # Validate K-value
    valid_k_values = [5, 10, 20, 50]
    if k_value not in valid_k_values:
        return jsonify({
            'success': False,
            'error': f'Invalid K-value. Must be one of: {valid_k_values}'
        }), 400

    # Validate output format
    valid_formats = ['csv', 'influx', 'api']
    if output_format not in valid_formats:
        return jsonify({
            'success': False,
            'error': f'Invalid output format. Must be one of: {valid_formats}'
        }), 400

    # Validate API parameters if using API output
    if output_format == 'api':
        if not api_server_ip or not api_server_port:
            return jsonify({
                'success': False,
                'error': 'API server IP and port are required for API output'
            }), 400

    try:
        job = anonymization_manager.create_job(
            unique_key=unique_key,
            patient_name=patient_name,
            k_value=k_value,
            batch_size_seconds=batch_size_seconds,
            output_format=output_format,
            start_time=start_time,
            end_time=end_time,
            api_server_ip=api_server_ip,
            api_server_port=api_server_port,
            created_by=session.get('user_id')
        )

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='anonymization_trigger',
            description=f"Triggered anonymization for {patient_name or unique_key}: K={k_value}, output={output_format}",
            ip_address=request.remote_addr,
            metadata=data
        )

        return jsonify({'success': True, 'job': job})
    except Exception as e:
        logger.error(f"Failed to trigger anonymization: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/anonymization/jobs/<int:job_id>/status')
@login_required
def get_job_status(job_id):
    """Get status of specific anonymization job"""
    job = anonymization_manager.get_job_status(job_id)

    if job:
        return jsonify({'success': True, 'job': job})
    else:
        return jsonify({'success': False, 'error': 'Job not found'}), 404


@app.route('/api/anonymization/jobs/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel running anonymization job"""
    try:
        result = anonymization_manager.cancel_job(job_id)

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='anonymization_cancel',
            description=f"Cancelled anonymization job {job_id}",
            ip_address=request.remote_addr
        )

        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


# ============================================================================
# RECORD LINKAGE ROUTES
# ============================================================================

@app.route('/record-linkage')
@login_required
def record_linkage_page():
    """Record linkage interface for fetching patient data"""
    return render_template('record_linkage.html', user=session.get('user'), role=session.get('role'))


@app.route('/api/record-linkage/fetch', methods=['POST'])
@login_required
def fetch_patient_data():
    """Fetch patient data by personal identifiers (name, DoB, gender)"""
    data = request.json
    given_name = data.get('given_name')
    family_name = data.get('family_name')
    dob = data.get('dob')  # Format: YYYY-MM-DD
    gender = data.get('gender')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    include_raw = data.get('include_raw', True)
    include_anonymized = data.get('include_anonymized', True)
    limit = int(data.get('limit', 1000))

    try:
        # Perform record linkage
        patient_data = record_linkage.link_patient_data(
            given_name=given_name,
            family_name=family_name,
            dob=dob,
            gender=gender,
            start_time=start_time,
            end_time=end_time,
            include_raw=include_raw,
            include_anonymized=include_anonymized,
            limit=limit
        )

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='record_linkage',
            description=f"Fetched data for {given_name} {family_name} (DoB: {dob})",
            ip_address=request.remote_addr,
            metadata={
                'unique_key': patient_data['query_info']['unique_key'],
                'total_data_points': patient_data['summary']['total_data_points']
            }
        )

        return jsonify({'success': True, 'data': patient_data})

    except Exception as e:
        logger.error(f"Record linkage failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/record-linkage/fetch-by-key', methods=['POST'])
@login_required
def fetch_patient_data_by_key():
    """Fetch patient data by unique key directly"""
    data = request.json
    unique_key = data.get('unique_key')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    include_raw = data.get('include_raw', True)
    include_anonymized = data.get('include_anonymized', True)
    limit = int(data.get('limit', 1000))
    skip_count = data.get('skip_count', True)  # Skip count queries by default for faster response

    if not unique_key:
        return jsonify({'success': False, 'error': 'Unique key is required'}), 400

    # Validate unique key format (base64, minimum 64 characters)
    if not isinstance(unique_key, str) or len(unique_key) < 64:
        return jsonify({'success': False, 'error': 'Invalid unique key format (must be base64-encoded, at least 64 characters)'}), 400

    try:
        logger.info(f"Record linkage request for unique_key: {unique_key[:16]}...")
        logger.info(f"   Time window: {start_time} to {end_time}")
        logger.info(f"   Limit: {limit}, Skip count: {skip_count}")

        # Fetch data using the unique key directly
        patient_data = record_linkage.link_patient_data_by_key(
            unique_key=unique_key,
            start_time=start_time,
            end_time=end_time,
            include_raw=include_raw,
            include_anonymized=include_anonymized,
            limit=limit,
            skip_count=skip_count
        )

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='record_linkage',
            description=f"Fetched data for unique_key: {unique_key[:16]}...",
            ip_address=request.remote_addr,
            metadata={
                'unique_key': unique_key,
                'total_data_points': patient_data['summary']['total_data_points']
            }
        )

        return jsonify({'success': True, 'data': patient_data})

    except Exception as e:
        logger.error(f"Record linkage by key failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/record-linkage/export-csv', methods=['POST'])
@login_required
def export_patient_data_csv():
    """Export patient data to CSV"""
    data = request.json
    patient_data = data.get('patient_data')

    try:
        output_dir = os.path.join(os.path.dirname(__file__), 'output', 'linked_records')
        filepath = record_linkage.export_to_csv(patient_data, output_dir)

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='data_export',
            description=f"Exported patient data to CSV: {os.path.basename(filepath)}",
            ip_address=request.remote_addr
        )

        return jsonify({'success': True, 'filepath': filepath, 'filename': os.path.basename(filepath)})

    except Exception as e:
        logger.error(f"CSV export failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/record-linkage/export-json', methods=['POST'])
@login_required
def export_patient_data_json():
    """Export patient data to JSON"""
    data = request.json
    patient_data = data.get('patient_data')

    try:
        output_dir = os.path.join(os.path.dirname(__file__), 'output', 'linked_records')
        filepath = record_linkage.export_to_json(patient_data, output_dir)

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='data_export',
            description=f"Exported patient data to JSON: {os.path.basename(filepath)}",
            ip_address=request.remote_addr
        )

        return jsonify({'success': True, 'filepath': filepath, 'filename': os.path.basename(filepath)})

    except Exception as e:
        logger.error(f"JSON export failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


# # ============================================================================
# # AUDIT AND DATA ACCESS ROUTES
# # ============================================================================

# @app.route('/audit')
# @login_required
# def audit():
#     """Audit log viewing interface"""
#     return render_template('audit.html', user=session.get('user'), role=session.get('role'))


# @app.route('/api/audit/events')
# @login_required
# def get_audit_events():
#     """Get audit events"""
#     event_type = request.args.get('event_type', 'all')
#     user_id = request.args.get('user_id')
#     start_date = request.args.get('start_date')
#     end_date = request.args.get('end_date')
#     limit = int(request.args.get('limit', 100))

#     events = audit_logger.get_events(
#         event_type=event_type,
#         user_id=user_id,
#         start_date=start_date,
#         end_date=end_date,
#         limit=limit
#     )

#     return jsonify(events)


# @app.route('/api/audit/export')
# @login_required
# @admin_required
# def export_audit_log():
#     """Export audit log as CSV"""
#     start_date = request.args.get('start_date')
#     end_date = request.args.get('end_date')

#     try:
#         csv_path = audit_logger.export_to_csv(start_date, end_date)

#         # Log audit event
#         audit_logger.log_event(
#             user_id=session.get('user_id'),
#             event_type='audit_export',
#             description=f"Exported audit log from {start_date} to {end_date}",
#             ip_address=request.remote_addr
#         )

#         return jsonify({'success': True, 'file': csv_path})
#     except Exception as e:
#         logger.error(f"Failed to export audit log: {e}")
#         return jsonify({'success': False, 'error': str(e)}), 400


# @app.route('/data-access')
# @login_required
# def data_access():
#     """Data access controls interface"""
#     return render_template('data_access.html', user=session.get('user'), role=session.get('role'))


# @app.route('/api/data-access/permissions')
# @login_required
# def get_data_permissions():
#     """Get data access permissions"""
#     permissions = user_manager.get_data_access_permissions()
#     return jsonify(permissions)


# @app.route('/api/data-access/grant', methods=['POST'])
# @login_required
# @admin_required
# def grant_data_access():
#     """Grant data access permission"""
#     data = request.json
#     user_id = data.get('user_id')
#     resource_type = data.get('resource_type')
#     resource_id = data.get('resource_id')
#     permission_level = data.get('permission_level', 'read')

#     try:
#         result = user_manager.grant_permission(
#             user_id=user_id,
#             resource_type=resource_type,
#             resource_id=resource_id,
#             permission_level=permission_level,
#             granted_by=session.get('user_id')
#         )

#         # Log audit event
#         audit_logger.log_event(
#             user_id=session.get('user_id'),
#             event_type='permission_grant',
#             description=f"Granted {permission_level} access to {resource_type}/{resource_id} for user {user_id}",
#             ip_address=request.remote_addr,
#             metadata=data
#         )

#         return jsonify({'success': True, 'result': result})
#     except Exception as e:
#         logger.error(f"Failed to grant permission: {e}")
#         return jsonify({'success': False, 'error': str(e)}), 400


# ============================================================================
# SETTINGS ROUTES
# ============================================================================

@app.route('/settings')
@login_required
@admin_required
def settings():
    """System settings page"""
    return render_template(
        'settings.html',
        user=session.get('user'),
        role=session.get('role'),
        config=config
    )


@app.route('/api/settings/test-influx', methods=['POST'])
@login_required
@admin_required
def test_influx_connection():
    """Test InfluxDB connection"""
    try:
        data = request.json
        from influxdb_client import InfluxDBClient

        client = InfluxDBClient(
            url=data.get('url'),
            token=data.get('token'),
            org=data.get('org')
        )

        # Test connection by pinging
        health = client.health()
        client.close()

        if health.status == "pass":
            return jsonify({'success': True, 'message': 'InfluxDB connection successful'})
        else:
            return jsonify({'success': False, 'error': 'InfluxDB health check failed'}), 400

    except Exception as e:
        logger.error(f"InfluxDB connection test failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/save-influx', methods=['POST'])
@login_required
@admin_required
def save_influx_settings():
    """Save InfluxDB settings to .env file"""
    try:
        data = request.json

        # Update .env file
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        env_lines = []

        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_lines = f.readlines()

        # Update or add settings
        settings_map = {
            'INFLUX_URL': data.get('url'),
            'INFLUX_TOKEN': data.get('token'),
            'INFLUX_ORG': data.get('org'),
            'INFLUX_BUCKET_RAW': data.get('bucket_raw'),
            'INFLUX_BUCKET_ANONYMIZED': data.get('bucket_anonymized')
        }

        for key, value in settings_map.items():
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f'{key}='):
                    env_lines[i] = f'{key}={value}\n'
                    found = True
                    break
            if not found:
                env_lines.append(f'{key}={value}\n')

        with open(env_path, 'w') as f:
            f.writelines(env_lines)

        # Log audit event
        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='settings_update',
            description='Updated InfluxDB settings',
            ip_address=request.remote_addr
        )

        return jsonify({'success': True, 'message': 'InfluxDB settings saved. Please restart the server.'})
    except Exception as e:
        logger.error(f"Failed to save InfluxDB settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/test-postgres', methods=['POST'])
@login_required
@admin_required
def test_postgres_connection():
    """Test PostgreSQL connection"""
    try:
        data = request.json
        import psycopg2

        conn = psycopg2.connect(
            host=data.get('host'),
            port=data.get('port'),
            database=data.get('database'),
            user=data.get('user'),
            password=data.get('password')
        )
        conn.close()

        return jsonify({'success': True, 'message': 'PostgreSQL connection successful'})
    except Exception as e:
        logger.error(f"PostgreSQL connection test failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/save-postgres', methods=['POST'])
@login_required
@admin_required
def save_postgres_settings():
    """Save PostgreSQL settings to .env file"""
    try:
        data = request.json

        env_path = os.path.join(os.path.dirname(__file__), '.env')
        env_lines = []

        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_lines = f.readlines()

        settings_map = {
            'POSTGRES_HOST': data.get('host'),
            'POSTGRES_PORT': str(data.get('port')),
            'POSTGRES_DB': data.get('database'),
            'POSTGRES_USER': data.get('user'),
            'POSTGRES_PASSWORD': data.get('password')
        }

        for key, value in settings_map.items():
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f'{key}='):
                    env_lines[i] = f'{key}={value}\n'
                    found = True
                    break
            if not found:
                env_lines.append(f'{key}={value}\n')

        with open(env_path, 'w') as f:
            f.writelines(env_lines)

        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='settings_update',
            description='Updated PostgreSQL settings',
            ip_address=request.remote_addr
        )

        return jsonify({'success': True, 'message': 'PostgreSQL settings saved. Please restart the server.'})
    except Exception as e:
        logger.error(f"Failed to save PostgreSQL settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/test-mqtt', methods=['POST'])
@login_required
@admin_required
def test_mqtt_connection():
    """Test MQTT connection"""
    try:
        data = request.json
        import paho.mqtt.client as mqtt

        test_client = mqtt.Client()
        test_client.connect(data.get('host'), data.get('port'), 60)
        test_client.disconnect()

        return jsonify({'success': True, 'message': 'MQTT connection successful'})
    except Exception as e:
        logger.error(f"MQTT connection test failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/save-mqtt', methods=['POST'])
@login_required
@admin_required
def save_mqtt_settings():
    """Save MQTT settings to .env file"""
    try:
        data = request.json

        env_path = os.path.join(os.path.dirname(__file__), '.env')
        env_lines = []

        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_lines = f.readlines()

        settings_map = {
            'MQTT_BROKER_HOST': data.get('host'),
            'MQTT_BROKER_PORT': str(data.get('port')),
            'MQTT_TOPIC_PREFIX': data.get('topic_prefix')
        }

        for key, value in settings_map.items():
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f'{key}='):
                    env_lines[i] = f'{key}={value}\n'
                    found = True
                    break
            if not found:
                env_lines.append(f'{key}={value}\n')

        with open(env_path, 'w') as f:
            f.writelines(env_lines)

        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='settings_update',
            description='Updated MQTT settings',
            ip_address=request.remote_addr
        )

        return jsonify({'success': True, 'message': 'MQTT settings saved. Please restart the server.'})
    except Exception as e:
        logger.error(f"Failed to save MQTT settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/test-fl', methods=['POST'])
@login_required
@admin_required
def test_fl_connection():
    """Test FL Server connection"""
    try:
        data = request.json
        import requests

        url = f"http://{data.get('host')}:{data.get('port')}/health"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            return jsonify({'success': True, 'message': 'FL Server connection successful'})
        else:
            return jsonify({'success': False, 'error': f'FL Server returned status {response.status_code}'}), 400
    except Exception as e:
        logger.error(f"FL Server connection test failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/save-fl', methods=['POST'])
@login_required
@admin_required
def save_fl_settings():
    """Save FL Server settings to .env file"""
    try:
        data = request.json

        env_path = os.path.join(os.path.dirname(__file__), '.env')
        env_lines = []

        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_lines = f.readlines()

        settings_map = {
            'FL_SERVER_HOST': data.get('host'),
            'FL_SERVER_PORT': str(data.get('port')),
            'FL_MODEL_PATH': data.get('model_path')
        }

        for key, value in settings_map.items():
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f'{key}='):
                    env_lines[i] = f'{key}={value}\n'
                    found = True
                    break
            if not found:
                env_lines.append(f'{key}={value}\n')

        with open(env_path, 'w') as f:
            f.writelines(env_lines)

        audit_logger.log_event(
            user_id=session.get('user_id'),
            event_type='settings_update',
            description='Updated FL Server settings',
            ip_address=request.remote_addr
        )

        return jsonify({'success': True, 'message': 'FL Server settings saved. Please restart the server.'})
    except Exception as e:
        logger.error(f"Failed to save FL Server settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    logger.error(f"Internal error: {error}")
    return render_template('500.html'), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Create logs directory if not exists
    os.makedirs('logs', exist_ok=True)

    # Run Flask app
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    logger.info(f"Starting Privacy Umbrella Admin Dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
