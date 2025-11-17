"""
Federated Learning Orchestration Module
Integrates with FL gRPC server
"""

import logging
import json
import os
import sys
import subprocess
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Add utils_fl to path to import FL server modules
UTILS_FL_DIR = Path(__file__).parent / "utils_fl"
sys.path.insert(0, str(UTILS_FL_DIR))

try:
    import grpc
    from grpc_utils import federated_learning_pb2, federated_learning_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError as e:
    GRPC_AVAILABLE = False
    logging.warning(f"gRPC not available - FL orchestration will run in simulation mode: {e}")

logger = logging.getLogger(__name__)


class FLOrchestrator:
    """Orchestrate federated learning training"""

    def __init__(self, config):
        self.config = config
        self.training_active = False
        self.training_history = []
        self.fl_server_process = None
        self.grpc_stub = None

        # Check if FL server is already running
        if GRPC_AVAILABLE:
            self._try_connect_to_server()

    def get_fl_status(self) -> Dict:
        """Get FL server status and current training progress"""
        model_path = self.config.FL_MODEL_PATH

        model_info = {}
        if os.path.exists(model_path):
            try:
                with open(model_path, 'r') as f:
                    model_data = json.load(f)
                model_info = {
                    'version': model_data.get('version', 0),
                    'timestamp': model_data.get('timestamp', 'unknown'),
                    'accuracy': model_data.get('accuracy', None)
                }
            except:
                pass

        return {
            'training_active': self.training_active,
            'current_round': len(self.training_history),
            'model_info': model_info,
            'timestamp': datetime.now().isoformat()
        }

    def _try_connect_to_server(self) -> bool:
        """Try to connect to FL gRPC server"""
        try:
            host = self.config.FL_SERVER_HOST
            port = self.config.FL_SERVER_PORT
            logger.info(f"[FL] Attempting to connect to FL server at {host}:{port}...")

            channel = grpc.insecure_channel(f'{host}:{port}')
            self.grpc_stub = federated_learning_pb2_grpc.FederatedLearningServiceStub(channel)

            # Note: This FL server doesn't have admin control methods like GetServerStatus
            # It only has client-side methods: JoinTraining, SendModelWeights, GetGlobalModel, SendMetrics
            # The server works automatically - training starts when clients connect and send weights
            logger.info(f"[FL] gRPC stub created successfully for FL server at {host}:{port}")
            logger.info(f"[FL] Available methods: JoinTraining, SendModelWeights, GetGlobalModel, SendMetrics")
            return True
        except Exception as e:
            logger.error(f"[FL] ERROR: Could not create gRPC stub: {e}")
            logger.error(f"[FL] Make sure FL server is running at {host}:{port}")
            self.grpc_stub = None
            return False

    def start_fl_server(self, expected_clients: int = 3) -> Dict:
        """Start the FL gRPC server as a subprocess

        Args:
            expected_clients: Number of clients expected to participate in FL training
        """
        if self.fl_server_process and self.fl_server_process.poll() is None:
            logger.info(f"[FL] Server already running (PID: {self.fl_server_process.pid})")
            return {'status': 'already_running', 'message': 'FL server is already running'}

        try:
            fl_server_script = UTILS_FL_DIR / "fl_grpc_server.py"
            logger.info(f"[FL] Looking for FL server script at: {fl_server_script}")

            if not fl_server_script.exists():
                logger.error(f"[FL] ERROR: Server script not found at {fl_server_script}")
                return {'status': 'error', 'message': f'FL server script not found at {fl_server_script}'}

            logger.info(f"[FL] Starting FL server subprocess with expected_clients={expected_clients}...")
            # Start FL server in background with expected_clients parameter
            self.fl_server_process = subprocess.Popen(
                [sys.executable, str(fl_server_script), '--expected-clients', str(expected_clients)],
                cwd=str(UTILS_FL_DIR)
            )

            logger.info(f"[FL] Started FL server (PID: {self.fl_server_process.pid})")
            logger.info(f"[FL] Waiting 2 seconds for FL server to initialize...")

            # Wait a bit and try to connect
            import time
            time.sleep(2)

            # Check if process is still running
            if self.fl_server_process.poll() is not None:
                logger.error(f"[FL] ERROR: Server process died immediately (exit code: {self.fl_server_process.returncode})")
                return {'status': 'error', 'message': f'Server process died with exit code {self.fl_server_process.returncode}'}

            connection_success = self._try_connect_to_server()
            if connection_success:
                logger.info(f"[FL] Successfully connected to FL server")
            else:
                logger.warning(f"[FL] WARNING: Server started but connection failed - may still be initializing")

            return {
                'status': 'started',
                'pid': self.fl_server_process.pid,
                'started_at': datetime.now().isoformat(),
                'connected': connection_success
            }
        except Exception as e:
            logger.error(f"[FL] ERROR: Failed to start FL server: {e}")
            return {'status': 'error', 'message': str(e)}

    def stop_fl_server(self) -> Dict:
        """Stop the FL gRPC server"""
        if not self.fl_server_process or self.fl_server_process.poll() is not None:
            return {'status': 'not_running', 'message': 'FL server is not running'}

        try:
            self.fl_server_process.terminate()
            self.fl_server_process.wait(timeout=10)
            self.grpc_stub = None

            logger.info("Stopped FL server")
            return {
                'status': 'stopped',
                'stopped_at': datetime.now().isoformat()
            }
        except subprocess.TimeoutExpired:
            self.fl_server_process.kill()
            return {'status': 'killed', 'message': 'FL server was forcefully terminated'}
        except Exception as e:
            logger.error(f"Failed to stop FL server: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_connected_clients(self) -> List[Dict]:
        """Get list of connected FL clients via gRPC admin method"""
        if not GRPC_AVAILABLE or not self.grpc_stub:
            return []

        try:
            response = self.grpc_stub.GetConnectedClients(
                federated_learning_pb2.Empty(),
                timeout=5
            )

            clients = []
            for client in response.clients:
                clients.append({
                    'client_id': client.client_id,
                    'joined_at': datetime.fromtimestamp(client.joined_at / 1000).isoformat(),
                    'has_sent_weights': client.has_sent_weights,
                    'has_sent_metrics': client.has_sent_metrics,
                    'model_size_bytes': client.model_size_bytes,
                    'num_trees': client.num_trees,
                    'status': 'active' if client.has_sent_weights else 'connected'
                })

            return clients
        except Exception:
            # Suppress connection errors - server might not be running
            return []

    def get_global_model_info(self) -> Dict:
        """Get current global model information"""
        model_path = self.config.FL_MODEL_PATH

        if not os.path.exists(model_path):
            return {'error': 'Model file not found'}

        try:
            with open(model_path, 'r') as f:
                model_data = json.load(f)

            # Parse the actual JSON structure
            current_model = model_data.get('current_model', {})
            aggregated_weights = current_model.get('aggregated_weights', {})

            # Extract round number and client contributions
            round_number = current_model.get('round_number', 0)
            client_contributions = aggregated_weights.get('client_contributions', [])
            num_trees = len(aggregated_weights.get('trees', []))
            num_features = aggregated_weights.get('num_features', 0)

            # Extract accuracy if available (may be in metadata or metrics)
            accuracy = current_model.get('accuracy')
            if accuracy is None:
                # Try to get from aggregated_weights metadata
                accuracy = aggregated_weights.get('accuracy')

            # Get timestamp
            timestamp = current_model.get('timestamp') or model_data.get('timestamp')

            return {
                'version': round_number,  # Use round_number as version
                'round_number': round_number,
                'timestamp': timestamp,
                'accuracy': accuracy,
                'file_size_kb': os.path.getsize(model_path) / 1024,
                'feature_count': num_features,
                'num_trees': num_trees,
                'client_contributions_count': len(client_contributions),
                'client_contributions': client_contributions
            }
        except Exception as e:
            logger.error(f"Failed to read model: {e}")
            return {'error': str(e)}

    def start_training(self, num_rounds: int, min_clients: int) -> Dict:
        """Start FL training

        Note: This FL server works automatically. Training starts when:
        1. Server is running
        2. Clients connect via JoinTraining RPC
        3. Clients send model weights via SendModelWeights RPC
        4. Server aggregates when enough weights received

        This method is kept for compatibility but training is automatic.
        """
        logger.info(f"[FL] start_training called - checking FL server status...")

        if not self.fl_server_process or self.fl_server_process.poll() is not None:
            logger.error(f"[FL] ERROR: Cannot start training - FL server is not running")
            return {
                'status': 'error',
                'message': 'FL server is not running. Start the server first.'
            }

        self.training_active = True
        logger.info(f"[FL] Training mode enabled (automatic)")
        logger.info(f"[FL] Training config: {num_rounds} rounds, {min_clients} minimum clients")
        logger.info(f"[FL] Server will aggregate when clients send weights...")

        training_record = {
            'num_rounds': num_rounds,
            'min_clients': min_clients,
            'started_at': datetime.now().isoformat(),
            'status': 'automatic'
        }
        self.training_history.append(training_record)

        logger.info(f"[FL] Training record added to history (total: {len(self.training_history)} rounds)")

        return {
            'status': 'automatic',
            'message': 'FL server is running in automatic mode. Training will start when clients connect and send weights.',
            'num_rounds': num_rounds,
            'min_clients': min_clients,
            'started_at': training_record['started_at']
        }

    def stop_training(self) -> Dict:
        """Stop FL training

        Note: This FL server doesn't have remote training control.
        To stop training, you need to stop the entire server.
        This method just marks training as inactive in the dashboard.
        """
        self.training_active = False
        logger.info("Training mode disabled")

        return {
            'status': 'stopped',
            'message': 'Training mode disabled. Server remains running. To fully stop, use "Stop Server" button.',
            'stopped_at': datetime.now().isoformat()
        }

    def get_training_history(self, limit: int = 20) -> List[Dict]:
        """Get FL training history"""
        return self.training_history[-limit:]

    def get_server_status_details(self) -> Dict:
        """Get detailed FL server status via gRPC admin method"""
        if not GRPC_AVAILABLE or not self.grpc_stub:
            return {
                'running': False,
                'error': 'gRPC not available or server not connected'
            }

        try:
            response = self.grpc_stub.GetServerStatus(
                federated_learning_pb2.Empty(),
                timeout=5
            )

            return {
                'running': response.running,
                'session_id': response.session_id,
                'connected_clients_count': response.connected_clients_count,
                'expected_clients': response.expected_clients,
                'server_start_time': datetime.fromtimestamp(response.server_start_time / 1000).isoformat() if response.server_start_time > 0 else None,
                'total_rounds_completed': response.total_rounds_completed,
                'aggregation_in_progress': response.aggregation_in_progress
            }
        except Exception:
            # Suppress connection errors - server might not be running
            return {
                'running': False,
                'error': 'Server not connected'
            }

    def get_training_stats(self) -> Dict:
        """Get FL training statistics via gRPC admin method"""
        if not GRPC_AVAILABLE or not self.grpc_stub:
            return {
                'total_weights_received': 0,
                'total_metrics_received': 0,
                'aggregations_completed': 0,
                'client_metrics': []
            }

        try:
            response = self.grpc_stub.GetTrainingStats(
                federated_learning_pb2.Empty(),
                timeout=5
            )

            client_metrics = []
            for metric in response.client_metrics:
                client_metrics.append({
                    'client_id': metric.client_id,
                    'accuracy': metric.accuracy,
                    'f1_score': metric.f1_score,
                    'training_samples': metric.training_samples
                })

            return {
                'total_weights_received': response.total_weights_received,
                'total_metrics_received': response.total_metrics_received,
                'aggregations_completed': response.aggregations_completed,
                'last_aggregation_time': datetime.fromtimestamp(response.last_aggregation_time / 1000).isoformat() if response.last_aggregation_time > 0 else None,
                'client_metrics': client_metrics
            }
        except Exception:
            # Suppress connection errors - server might not be running
            return {
                'total_weights_received': 0,
                'total_metrics_received': 0,
                'aggregations_completed': 0,
                'client_metrics': []
            }
