# Federated Learning Server

Manages the FL gRPC server lifecycle and exposes training status, connected clients, and global model information over a REST API.

**Port:** `7002` (REST API) · `50051` (gRPC server, internal only)

---

## Responsibility

Federated learning allows patient devices (Flutter app) to train a local XGBoost model on their own data and share only the model weights — never the raw data. This service:

- Starts and stops the gRPC server that coordinates client training
- Monitors which clients are connected and their training state
- Tracks training rounds and the aggregated global model
- Exposes all of the above over a REST API so the dashboard can display it

It does **not** connect to any database. Model state is stored in a JSON file (`grpc/global_model_latest.json`).

---

## Folder Structure

```
federated_learning_server/
├── server/
│   ├── main.py          Flask REST API (entry point)
│   └── .env.example     Environment variable template
├── core/
│   └── fl_orchestrator.py   Manages the gRPC server subprocess + gRPC stub calls
├── grpc/                    Full FL gRPC server (copied from original modules/utils_fl/)
│   ├── fl_grpc_server.py    gRPC server implementation
│   ├── aggregator.py        XGBoost model aggregation (bagging strategy)
│   ├── global_model.py      Global model persistence
│   ├── global_model_latest.json
│   ├── grpc_utils/          Generated protobuf stubs
│   │   ├── federated_learning_pb2.py
│   │   └── federated_learning_pb2_grpc.py
│   └── utility/             Logging helpers
└── requirements.txt
```

---

## How Federated Learning Works Here

```
1. Admin clicks "Start Server" in the dashboard
   → REST API calls fl_orchestrator.start_fl_server(expected_clients=3)
   → Spawns fl_grpc_server.py as a subprocess on port 50051

2. Patient devices (Flutter) connect via gRPC:
   → JoinTraining(client_id)        — register with the session
   → SendModelWeights(weights_json) — upload locally trained XGBoost
   → GetGlobalModel()               — receive aggregated model (blocks until ready)
   → SendMetrics(accuracy, f1, ...) — report performance

3. Server aggregates when all expected clients have sent weights:
   → XGBoostAggregator.aggregate_weights_bagging()
   → Saves result to global_model_latest.json
   → Unblocks all GetGlobalModel() calls
   → Session resets, ready for next round

4. Dashboard polls the REST API for status and displays it.
```

---

## API Endpoints

### `GET /health`
Public.

```json
{ "status": "ok", "service": "federated_learning", "fl_server_running": false }
```

---

### Server lifecycle

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/fl/server/start` | Start the gRPC server. Body: `{ "expected_clients": 3 }` |
| `POST` | `/api/fl/server/stop` | Stop the gRPC server (SIGTERM) |
| `GET` | `/api/fl/server/status` | Is the process running? PID? gRPC connected? |
| `GET` | `/api/fl/server/status-details` | Detailed status via gRPC admin RPC (session_id, rounds completed, etc.) |

**Start response:**
```json
{
  "success": true,
  "status": "started",
  "pid": 12345,
  "started_at": "2025-01-01T12:00:00",
  "connected": true
}
```

---

### Training

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/fl/training/start` | Mark training as active. Body: `{ "num_rounds": 5, "min_clients": 2 }` |
| `POST` | `/api/fl/training/stop` | Mark training as inactive (server keeps running) |
| `GET` | `/api/fl/training/stats` | Aggregations completed, client metrics, weights received |
| `GET` | `/api/fl/training/history` | List of past training rounds. Query: `?limit=20` |

> **Note:** Training is automatic — it starts the moment enough clients connect and send weights. The `training/start` endpoint just records intent in the dashboard state.

---

### Clients and model

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/fl/clients` | List connected clients with status (has_sent_weights, num_trees, etc.) |
| `GET` | `/api/fl/global-model` | Current global model info (round number, accuracy, tree count, file size) |
| `GET` | `/api/fl/status` | Combined training status + model info |

**Clients response:**
```json
{
  "success": true,
  "clients": [
    {
      "client_id": "device_abc",
      "joined_at": "2025-01-01T12:01:00",
      "has_sent_weights": true,
      "has_sent_metrics": false,
      "num_trees": 10,
      "status": "active"
    }
  ]
}
```

---

## Configuration

Copy `server/.env.example` to `server/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `FL_SERVER_HOST` | `localhost` | Where the gRPC server binds (always localhost inside the container) |
| `FL_SERVER_PORT` | `50051` | gRPC server port |
| `FL_MODEL_PATH` | `../grpc/global_model_latest.json` | Path to the global model JSON file |
| `PORT` | `7002` | REST API port |
| `FLASK_DEBUG` | `false` | |
| `API_KEY` | *(empty = no auth)* | |

---

## Quickstart (standalone)

```bash
cd federated_learning_server
pip install -r requirements.txt
cp server/.env.example server/.env
python server/main.py
# → REST API on http://localhost:7002
# Start the gRPC server via POST /api/fl/server/start
```

---

## Dependencies

- No database required
- `grpcio`, `xgboost` for the FL server subprocess
- The gRPC server (`grpc/fl_grpc_server.py`) runs as a child process managed by `fl_orchestrator.py`
