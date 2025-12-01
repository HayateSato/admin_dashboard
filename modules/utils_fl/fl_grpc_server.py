import grpc
from concurrent import futures
import threading
import time
import json
import os
import argparse
from grpc_utils import federated_learning_pb2_grpc
from grpc_utils import federated_learning_pb2
from aggregator import XGBoostAggregator
from global_model import GlobalModelManager
from utility.logger import setup_logger

logger = setup_logger(__name__)

class FederatedLearningServicer(federated_learning_pb2_grpc.FederatedLearningServiceServicer):
    def __init__(self, expected_clients=3):
        self.aggregator = XGBoostAggregator()

        # Get model save path from environment variable
        model_save_path = os.getenv('MODEL_SAVE_PATH', 'global_model_latest.json')
        logger.info(f"Using model save path: {model_save_path}")
        self.model_manager = GlobalModelManager(model_save_path=model_save_path)
        self.connected_clients = {}
        self.client_weights = {}
        self.client_metrics = {}
        self.session_id = f"session_{int(time.time())}"
        self.expected_clients = expected_clients  # Configurable via parameter
        self.lock = threading.Lock()

        # Admin monitoring tracking
        self.server_start_time = time.time()
        self.total_rounds_completed = 0
        self.total_weights_received = 0
        self.total_metrics_received = 0
        self.aggregations_completed = 0
        self.last_aggregation_time = 0
        self.aggregation_in_progress = False

        # Persistent metrics history (survives session resets)
        self.client_metrics_history = []  # List of {client_id, metrics, timestamp, session_id}

        if self.expected_clients == 1:
            logger.info("gRPC Federated Learning Server initialized (Single Client Mode)")
        else :
            logger.info(f"gRPC Federated Learning Server initialized (Expected Clients: {self.expected_clients})")
        
    def cleanup_old_sessions(self):
        """Clean up old client connections and data"""
        current_time = time.time()
        with self.lock:
            # Remove clients that joined more than 10 minutes ago and haven't sent weights
            clients_to_remove = []
            for client_id, client_info in self.connected_clients.items():
                if current_time - client_info['joined_at'] > 600:  # 10 minutes
                    if client_id not in self.client_weights:
                        clients_to_remove.append(client_id)
            
            for client_id in clients_to_remove:
                logger.warning(f"Removing inactive client {client_id}")
                del self.connected_clients[client_id]
                # Also remove from weights and metrics if present
                self.client_weights.pop(client_id, None)
                self.client_metrics.pop(client_id, None)
    
    def check_client_connections(self):
        """Check status of all connected clients"""
        with self.lock:
            logger.debug(f"Connection status check:")
            logger.debug(f"  - Connected clients: {len(self.connected_clients)}")
            logger.debug(f"  - Clients with weights: {len(self.client_weights)}")
            logger.debug(f"  - Clients with metrics: {len(self.client_metrics)}")
            
            for client_id in self.connected_clients:
                has_weights = client_id in self.client_weights
                has_metrics = client_id in self.client_metrics
                join_time = self.connected_clients[client_id]['joined_at']
                idle_time = time.time() - join_time
                
                logger.debug(f"  - {client_id}: weights={has_weights}, metrics={has_metrics}, idle={idle_time:.1f}s")

    def force_cleanup_all(self):
        """Force cleanup of all client data"""
        with self.lock:
            logger.warning("Forcing cleanup of all client data")
            self.connected_clients.clear()
            self.client_weights.clear()
            self.client_metrics.clear()
            logger.info("All client data cleared")
    
    def _remove_inactive_clients(self):
        """Remove clients that haven't sent weights and appear inactive"""
        current_time = time.time()
        inactive_clients = []
        
        with self.lock:
            for client_id in self.connected_clients:
                if client_id not in self.client_weights:
                    join_time = self.connected_clients[client_id]['joined_at']
                    idle_time = current_time - join_time
                    
                    # If client has been idle for more than 2 minutes, consider it inactive
                    if idle_time > 120:
                        inactive_clients.append(client_id)
            
            # Remove inactive clients
            for client_id in inactive_clients:
                logger.warning(f"Removing inactive client {client_id} (no weights sent)")
                self.connected_clients.pop(client_id, None)
                self.client_weights.pop(client_id, None)
                self.client_metrics.pop(client_id, None)
            
            if inactive_clients:
                logger.info(f"Removed {len(inactive_clients)} inactive clients: {inactive_clients}")
    
    def _reset_session_for_next_round(self):
        """Reset session state for the next training round"""
        logger.info("Resetting session for next round...")
        
        # Clear all client data
        self.connected_clients.clear()
        self.client_weights.clear()
        self.client_metrics.clear()
        
        # Clear received model tracking
        if hasattr(self, 'clients_received_model'):
            self.clients_received_model.clear()
        
        # Generate new session ID
        old_session = self.session_id
        self.session_id = f"session_{int(time.time())}"
        
        logger.info(f"Session reset complete: {old_session} -> {self.session_id}")
        logger.info("Ready for new clients to join!")
    
    def get_session_status(self):
        """Get current session status for debugging"""
        with self.lock:
            status = {
                'session_id': self.session_id,
                'connected_clients': len(self.connected_clients),
                'clients_with_weights': len(self.client_weights),
                'clients_with_metrics': len(self.client_metrics),
                'clients_received_model': len(getattr(self, 'clients_received_model', set())),
                'expected_clients': self.expected_clients
            }
            logger.debug(f"Session status: {status}")
            return status


    def JoinTraining(self, request, context):
        """Handle client join requests"""
        with self.lock:
            client_id = request.client_id
            
            if len(self.connected_clients) >= self.expected_clients:
                logger.warning(f"Client {client_id} rejected - session full")
                return federated_learning_pb2.JoinResponse(
                    accepted=False,
                    session_id="",
                    config=federated_learning_pb2.TrainingConfiguration()
                )
            
            self.connected_clients[client_id] = {
                'capabilities': request.capabilities,
                'joined_at': time.time()
            }
            
            logger.info(f"Client {client_id} joined session {self.session_id}")
            
            # Create training configuration
            config = federated_learning_pb2.TrainingConfiguration(
                num_rounds=1,
                expected_clients=self.expected_clients
            )
            config.hyperparameters["learning_rate"] = "0.1"
            config.hyperparameters["max_depth"] = "6"
            config.hyperparameters["num_trees"] = "100"
            
            return federated_learning_pb2.JoinResponse(
                accepted=True,
                session_id=self.session_id,
                config=config
            )
    
    def SendModelWeights(self, request, context):
        """Receive model weights from clients"""
        client_id = request.client_id
        
        if request.session_id != self.session_id:
            return federated_learning_pb2.ModelWeightsResponse(
                success=False,
                message="Invalid session ID"
            )
        
        try:
            # Deserialize model weights
            # weights_data = pickle.loads(request.model_weights)
            weights_json = request.model_weights.decode('utf-8')
            weights_data = json.loads(weights_json)
            
            with self.lock:
                self.client_weights[client_id] = weights_data
                self.total_weights_received += 1
                logger.info(f"Received weights from {client_id} "
                            f"({request.metadata.model_size_bytes} bytes, "
                            f"{request.metadata.num_trees} trees)")
            
            return federated_learning_pb2.ModelWeightsResponse(
                success=True,
                message="Weights received successfully"
            )
            
        except Exception as e:
            logger.error(f"Error processing weights from {client_id}: {e}")
            return federated_learning_pb2.ModelWeightsResponse(
                success=False,
                message=f"Error processing weights: {str(e)}"
            )

    def GetGlobalModel(self, request, context):
        """Send global model to clients with enhanced error handling and logging"""
        client_id = request.client_id
        
        if request.session_id != self.session_id:
            logger.error(f"Invalid session ID from {client_id}: {request.session_id} != {self.session_id}")
            return federated_learning_pb2.GlobalModelResponse(
                success=False,
                global_model=b"",
                metadata=federated_learning_pb2.ModelMetadata()
            )
        
        try:
            logger.info(f"Client {client_id} requesting global model...")
            
            # Check if client is still connected
            if not context.is_active():
                logger.warning(f"Client {client_id} is no longer active")
                return federated_learning_pb2.GlobalModelResponse(
                    success=False,
                    global_model=b"",
                    metadata=federated_learning_pb2.ModelMetadata()
                )
            
            # Clean up old sessions first
            self.cleanup_old_sessions()
            
            # ENHANCED: Wait for all CONNECTED clients to send weights (not all expected clients)
            max_wait_time = 120  # 2 minutes timeout
            start_time = time.time()
            
            logger.info(f"Waiting for weights from {len(self.connected_clients)} connected clients...")
            logger.info(f"Connected: {list(self.connected_clients.keys())}")
            logger.info(f"Already have weights from: {list(self.client_weights.keys())}")
            
            while len(self.client_weights) < len(self.connected_clients):
                elapsed = time.time() - start_time
                
                # Check if client disconnected during wait
                if not context.is_active():
                    logger.warning(f"Client {client_id} disconnected while waiting for weights")
                    return federated_learning_pb2.GlobalModelResponse(
                        success=False,
                        global_model=b"",
                        metadata=federated_learning_pb2.ModelMetadata()
                    )
                
                # ENHANCED: Check for inactive clients and remove them
                if elapsed > 30:  # After 30 seconds, start checking for inactive clients
                    self._remove_inactive_clients()
                
                if elapsed > max_wait_time:
                    logger.error(f"Timeout waiting for client weights after {elapsed:.1f}s")
                    logger.error(f"Connected clients: {list(self.connected_clients.keys())}")
                    logger.error(f"Clients with weights: {list(self.client_weights.keys())}")
                    missing_clients = set(self.connected_clients.keys()) - set(self.client_weights.keys())
                    logger.error(f"Missing weights from: {missing_clients}")
                    
                    # ENHANCED: Try to proceed with available clients if we have at least 2
                    if len(self.client_weights) >= 2:
                        logger.warning(f"Proceeding with {len(self.client_weights)} clients instead of waiting")
                        # Remove non-responsive clients
                        for missing_client in missing_clients:
                            with self.lock:
                                self.connected_clients.pop(missing_client, None)
                            logger.warning(f"Removed unresponsive client: {missing_client}")
                        break
                    else:
                        # Reset session and try again
                        logger.error("Not enough clients responded - resetting session")
                        self._reset_session_for_next_round()
                        return federated_learning_pb2.GlobalModelResponse(
                            success=False,
                            global_model=b"",
                            metadata=federated_learning_pb2.ModelMetadata()
                        )
                
                if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                    logger.info(f"Waiting for weights... {len(self.client_weights)}/{len(self.connected_clients)} received (elapsed: {elapsed:.1f}s)")
                
                time.sleep(1)
            
            logger.info(f"Proceeding with aggregation using {len(self.client_weights)} clients...")

            # Aggregate weights
            with self.lock:
                client_weights_list = list(self.client_weights.values())
                global_weights = self.aggregator.aggregate_weights_bagging(client_weights_list)

                # Update aggregation stats
                self.aggregations_completed += 1
                self.last_aggregation_time = time.time()
                logger.info(f"Aggregation completed (total: {self.aggregations_completed})")

            if global_weights is None:
                logger.error(f"Failed to aggregate weights for {client_id}")
                return federated_learning_pb2.GlobalModelResponse(
                    success=False,
                    global_model=b"",
                    metadata=federated_learning_pb2.ModelMetadata()
                )
            
            # Create global model
            logger.info(f"Creating ensemble model for {client_id}...")
            global_model = self.model_manager.create_ensemble_model(global_weights)
            
            if global_model is None:
                logger.error(f"Failed to create ensemble model for {client_id}")
                return federated_learning_pb2.GlobalModelResponse(
                    success=False,
                    global_model=b"",
                    metadata=federated_learning_pb2.ModelMetadata()
                )
            
            # Prepare model data
            logger.info(f"Serializing model for {client_id}...")
            model_data = json.dumps(global_weights).encode('utf-8')
            model_size = len(model_data)
            
            # Check model size limits
            max_model_size = 50 * 1024 * 1024  # 50MB limit
            if model_size > max_model_size:
                logger.error(f"Model too large for {client_id}: {model_size} bytes (max: {max_model_size})")
                return federated_learning_pb2.GlobalModelResponse(
                    success=False,
                    global_model=b"",
                    metadata=federated_learning_pb2.ModelMetadata()
                )
            
            metadata = federated_learning_pb2.ModelMetadata(
                num_trees=global_weights.get('num_boosted_rounds', 0),
                num_features=global_weights.get('num_features', 0),
                model_size_bytes=model_size,
                algorithm="xgboost_ensemble",
                timestamp=int(time.time())
            )
            
            logger.info(f"Sending global model to {client_id} ({model_size} bytes)")
            
            # Check client is still active before sending
            if not context.is_active():
                logger.warning(f"Client {client_id} disconnected before model transmission")
                return federated_learning_pb2.GlobalModelResponse(
                    success=False,
                    global_model=b"",
                    metadata=federated_learning_pb2.ModelMetadata()
                )
            
            response = federated_learning_pb2.GlobalModelResponse(
                success=True,
                global_model=model_data,
                metadata=metadata
            )
            
            logger.info(f"Global model response prepared for {client_id}, sending...")
            
            # Add a small delay to help with network transmission
            time.sleep(0.1)
            
            logger.info(f"SUCCESS: Global model sent to {client_id}")
            
            # CRITICAL: Track which clients have received the global model
            with self.lock:
                if not hasattr(self, 'clients_received_model'):
                    self.clients_received_model = set()
                self.clients_received_model.add(client_id)
                
                logger.info(f"Clients received model: {len(self.clients_received_model)}/{len(self.connected_clients)}")
                
                # If all connected clients have received the model, reset the session
                if len(self.clients_received_model) >= len(self.connected_clients):
                    logger.info("All clients have received the global model - resetting session")
                    # Use a delayed reset to allow this response to complete first
                    def delayed_reset():
                        time.sleep(2)  # Wait 2 seconds
                        self._reset_session_for_next_round()
                    
                    reset_thread = threading.Thread(target=delayed_reset, daemon=True)
                    reset_thread.start()
            
            return response
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error sending global model to {client_id}: {e.code()} - {e.details()}")
            return federated_learning_pb2.GlobalModelResponse(
                success=False,
                global_model=b"",
                metadata=federated_learning_pb2.ModelMetadata()
            )
        except Exception as e:
            logger.error(f"Unexpected error creating global model for {client_id}: {e}", exc_info=True)
            return federated_learning_pb2.GlobalModelResponse(
                success=False,
                global_model=b"",
                metadata=federated_learning_pb2.ModelMetadata()
            )
        
    def SendMetrics(self, request, context):
        """Receive evaluation metrics from clients"""
        client_id = request.client_id

        try:
            metrics = {
                'accuracy': request.metrics.accuracy,
                'precision': request.metrics.precision,
                'recall': request.metrics.recall,
                'f1_score': request.metrics.f1_score,
                'roc_auc': request.metrics.roc_auc,
                'log_loss': request.metrics.log_loss,
                'training_samples': request.metrics.training_samples,
                'validation_samples': request.metrics.validation_samples
            }

            with self.lock:
                self.client_metrics[client_id] = metrics
                self.total_metrics_received += 1

                # Save to persistent history (survives session resets)
                self.client_metrics_history.append({
                    'client_id': client_id,
                    'metrics': metrics.copy(),
                    'timestamp': time.time(),
                    'session_id': self.session_id
                })

            logger.info(f"Received metrics from {client_id}: "
                        f"Accuracy={metrics['accuracy']:.4f}, "
                        f"F1={metrics['f1_score']:.4f}")

            return federated_learning_pb2.MetricsResponse(success=True)

        except Exception as e:
            logger.error(f"Error processing metrics from {client_id}: {e}")
            return federated_learning_pb2.MetricsResponse(success=False)

    # Admin monitoring RPC methods
    def GetServerStatus(self, request, context):
        """Get current server status for admin dashboard"""
        try:
            with self.lock:
                response = federated_learning_pb2.ServerStatusResponse(
                    running=True,
                    session_id=self.session_id,
                    connected_clients_count=len(self.connected_clients),
                    expected_clients=self.expected_clients,
                    server_start_time=int(self.server_start_time * 1000),  # Convert to ms
                    total_rounds_completed=self.total_rounds_completed,
                    aggregation_in_progress=self.aggregation_in_progress
                )
            logger.debug(f"Admin: GetServerStatus called - {len(self.connected_clients)} clients connected")
            return response
        except Exception as e:
            logger.error(f"Error in GetServerStatus: {e}")
            return federated_learning_pb2.ServerStatusResponse(running=False)

    def GetConnectedClients(self, request, context):
        """Get list of connected clients for admin dashboard"""
        try:
            clients_list = []
            with self.lock:
                for client_id, client_info in self.connected_clients.items():
                    # Get weight info if available
                    weight_info = self.client_weights.get(client_id, {})
                    has_sent_weights = client_id in self.client_weights
                    has_sent_metrics = client_id in self.client_metrics

                    # Extract metadata if weights were sent
                    model_size = 0
                    num_trees = 0
                    if has_sent_weights and isinstance(weight_info, dict):
                        model_size = weight_info.get('model_size_bytes', 0)
                        num_trees = len(weight_info.get('trees', []))

                    client_info_msg = federated_learning_pb2.ClientInfo(
                        client_id=client_id,
                        joined_at=int(client_info['joined_at'] * 1000),  # Convert to ms
                        has_sent_weights=has_sent_weights,
                        has_sent_metrics=has_sent_metrics,
                        model_size_bytes=model_size,
                        num_trees=num_trees
                    )
                    clients_list.append(client_info_msg)

                response = federated_learning_pb2.ConnectedClientsResponse(
                    clients=clients_list,
                    total_count=len(clients_list)
                )

            logger.debug(f"Admin: GetConnectedClients called - returning {len(clients_list)} clients")
            return response
        except Exception as e:
            logger.error(f"Error in GetConnectedClients: {e}")
            return federated_learning_pb2.ConnectedClientsResponse(total_count=0)

    def GetTrainingStats(self, request, context):
        """Get training statistics for admin dashboard"""
        try:
            client_metrics_list = []
            with self.lock:
                # Use persistent history instead of current session metrics
                # Get the most recent metrics for each client from history
                client_latest_metrics = {}
                for history_entry in self.client_metrics_history:
                    client_id = history_entry['client_id']
                    # Keep only the most recent entry per client
                    if client_id not in client_latest_metrics or history_entry['timestamp'] > client_latest_metrics[client_id]['timestamp']:
                        client_latest_metrics[client_id] = history_entry

                # Convert to protobuf format
                for client_id, entry in client_latest_metrics.items():
                    metrics = entry['metrics']
                    client_metric = federated_learning_pb2.ClientMetricsSummary(
                        client_id=client_id,
                        accuracy=metrics.get('accuracy', 0.0),
                        f1_score=metrics.get('f1_score', 0.0),
                        training_samples=metrics.get('training_samples', 0)
                    )
                    client_metrics_list.append(client_metric)

                response = federated_learning_pb2.TrainingStatsResponse(
                    total_weights_received=self.total_weights_received,
                    total_metrics_received=self.total_metrics_received,
                    aggregations_completed=self.aggregations_completed,
                    last_aggregation_time=int(self.last_aggregation_time * 1000) if self.last_aggregation_time > 0 else 0,
                    client_metrics=client_metrics_list
                )

            logger.debug(f"Admin: GetTrainingStats called - {self.total_weights_received} weights, {self.total_metrics_received} metrics")
            return response
        except Exception as e:
            logger.error(f"Error in GetTrainingStats: {e}")
            return federated_learning_pb2.TrainingStatsResponse()

def serve(expected_clients=3):
    """Enhanced server with proper gRPC options and timeouts

    Args:
        expected_clients: Number of clients expected to participate in FL training
    """

    # Configure gRPC options for better reliability
    options = [
        ('grpc.keepalive_time_ms', 30000),        # Send keepalive every 30 seconds
        ('grpc.keepalive_timeout_ms', 5000),      # Wait 5 seconds for keepalive response
        ('grpc.keepalive_permit_without_calls', True),
        ('grpc.http2.max_pings_without_data', 0),
        ('grpc.http2.min_time_between_pings_ms', 10000),
        ('grpc.http2.min_ping_interval_without_data_ms', 300000),
        ('grpc.max_connection_idle_ms', 300000),   # 5 minutes
        ('grpc.max_connection_age_ms', 1800000),   # 30 minutes
        ('grpc.max_connection_age_grace_ms', 5000),
        ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
        ('grpc.max_send_message_length', 100 * 1024 * 1024),     # 100MB
    ]

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=options
    )

    # Add servicer with expected_clients parameter
    servicer = FederatedLearningServicer(expected_clients=expected_clients)
    federated_learning_pb2_grpc.add_FederatedLearningServiceServicer_to_server(
        servicer, server)
    
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    
    logger.info(f"Starting enhanced gRPC server on {listen_addr}")
    logger.info("gRPC Configuration applied with enhanced timeouts and keepalive")
    
    server.start()
    
    # Add periodic health checks
    def health_check():
        while True:
            try:
                time.sleep(60)  # Check every minute
                logger.debug("Server health check - running normally")
                servicer.check_client_connections()
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    # Start health check in background
    health_thread = threading.Thread(target=health_check, daemon=True)
    health_thread.start()
    
    try:
        logger.info("Server started successfully - waiting for clients...")
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down gRPC server...")
        server.stop(grace=5.0)  # Give 5 seconds for graceful shutdown
        logger.info("Server shutdown complete")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Federated Learning gRPC Server')
    parser.add_argument(
        '--expected-clients',
        type=int,
        default=3,
        help='Number of clients expected to participate in FL training (default: 3)'
    )
    args = parser.parse_args()

    logger.info(f"Starting FL server with expected_clients={args.expected_clients}")
    serve(expected_clients=args.expected_clients)