# Federated Learning gRPC Server

## Overview

This module implements the **server-side** of the Privacy Umbrella Federated Learning system. It receives model weights from Flutter mobile clients, aggregates them using bagging ensemble, and maintains the global model.

**Note**: Local Differential Privacy (LDP) is applied on the client side (Flutter app) before model weights are transmitted. See [FEDERATED_LEARNING_DOCUMENTATION.md](../../document/FEDERATED_LEARNING_DOCUMENTATION.md) for theoretical details and LDP implementation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Flutter Mobile Clients                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Client 1 │    │ Client 2 │    │ Client 3 │              │
│  │  (LDP)   │    │  (LDP)   │    │  (LDP)   │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                     │
│       └───────────────┼───────────────┘                     │
│                       │ gRPC (port 50051)                   │
└───────────────────────┼─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    FL gRPC Server                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  FederatedLearningServicer                           │   │
│  │  - JoinTraining()      → Client registration        │   │
│  │  - SendModelWeights()  → Receive client models      │   │
│  │  - SendMetrics()       → Receive evaluation metrics │   │
│  │  - GetGlobalModel()    → Distribute aggregated model│   │
│  │  - GetServerStatus()   → Admin monitoring           │   │
│  └─────────────────────────────────────────────────────┘   │
│                        │                                    │
│                        ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  XGBoostAggregator                                   │   │
│  │  - Bagging ensemble aggregation                     │   │
│  │  - Feature importance averaging                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                        │                                    │
│                        ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  GlobalModelManager                                  │   │
│  │  - Model persistence (JSON)                         │   │
│  │  - Model history tracking                           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
utils_fl/
├── fl_grpc_server.py          # Main gRPC server implementation
├── aggregator.py              # XGBoost bagging aggregation logic
├── global_model.py            # Global model persistence manager
├── Dockerfile                 # Container build for FL server
├── requirements_fl.txt        # Python dependencies
├── global_model_latest.json   # Persisted global model
│
├── grpc_utils/                # gRPC protocol definitions
│   ├── federated_learning.proto       # Protocol buffer definitions
│   ├── federated_learning_pb2.py      # Generated Python classes
│   └── federated_learning_pb2_grpc.py # Generated gRPC stubs
│
├── utility/                   # Helper modules
│   ├── logger.py              # Logging configuration
│   └── utils.py               # Utility functions
│
└── logs/                      # Server log files
    └── federated_server_*.log
```

---

## gRPC Service Methods

### Client-Side RPCs

| Method | Description |
|--------|-------------|
| `JoinTraining` | Client registration with capabilities |
| `SendModelWeights` | Submit trained model weights (with LDP already applied) |
| `SendMetrics` | Submit local evaluation metrics (accuracy, F1, etc.) |
| `GetGlobalModel` | Retrieve aggregated global model |

### Admin Monitoring RPCs

| Method | Description |
|--------|-------------|
| `GetServerStatus` | Server health, connected clients, session info |
| `GetConnectedClients` | List of connected clients with status |
| `GetTrainingStats` | Aggregation statistics and client metrics |

---

## Aggregation Method

The server uses **Bagging (Bootstrap Aggregating)** to combine client models:

1. **Collect Trees**: All decision trees from all clients are collected
2. **Ensemble**: Trees are combined into a single ensemble model
3. **Average Feature Importance**: Feature importance values are averaged across clients
4. **Metadata**: Client contributions and timestamps are tracked

```python
# Aggregation result structure
{
  'trees': [
    {'tree_structure': {...}, 'client_id': 1, 'original_tree_id': 0},
    {'tree_structure': {...}, 'client_id': 2, 'original_tree_id': 0},
    {'tree_structure': {...}, 'client_id': 3, 'original_tree_id': 0}
  ],
  'feature_importance': {'hr': 0.30, 'spo2': 0.20, ...},
  'aggregation_metadata': {
    'method': 'bagging',
    'num_clients': 3,
    'timestamp': '2025-01-27T10:30:00'
  }
}
```

---

## Docker Deployment

The FL server runs as a separate container in the Docker Compose stack.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FL_SERVER_HOST` | Server bind address | `0.0.0.0` |
| `FL_SERVER_PORT` | gRPC port | `50051` |
| `MODEL_SAVE_PATH` | Path to save global model | `/app/models/global_model_latest.json` |

### Docker Compose Configuration

```yaml
fl_server:
  build:
    context: ./modules/utils_fl
    dockerfile: Dockerfile
  container_name: privacy_umbrella_fl_server
  ports:
    - "50051:50051"
  volumes:
    - fl_models:/app/models
    - fl_logs:/app/logs
  environment:
    FL_SERVER_HOST: 0.0.0.0
    FL_SERVER_PORT: 50051
    MODEL_SAVE_PATH: /app/models/global_model_latest.json
```

---

## Local Development

### Install Dependencies

```bash
pip install -r requirements_fl.txt
```

### Run Server

```bash
cd modules/utils_fl
python fl_grpc_server.py
```

### Regenerate gRPC Stubs (if proto changes)

```bash
cd grpc_utils
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. federated_learning.proto
```

---

## Integration with Admin Dashboard

The FL server status is monitored via `modules/fl_orchestrator.py` which:
- Connects to the gRPC server
- Retrieves server status and client information
- Displays training progress in the dashboard UI

---

## Model Persistence

The global model is persisted to JSON:
- **Location**: `global_model_latest.json` (configurable via `MODEL_SAVE_PATH`)
- **Contents**: Current model, model history, round number
- **Auto-load**: Server loads existing model on startup

---

## Logging

Logs are written to `logs/` directory:
- `federated_server_YYYYMMDD.log` - General server logs
- `federated_server_errors_YYYYMMDD.log` - Error logs

Log level can be configured via environment or code.

---

## Related Documentation

- [FEDERATED_LEARNING_DOCUMENTATION.md](../../document/FEDERATED_LEARNING_DOCUMENTATION.md) - Theoretical documentation (LDP, algorithm details, performance evaluation)
