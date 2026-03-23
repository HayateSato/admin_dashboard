# Modules

This folder contains the core backend modules for the Privacy Umbrella Admin Dashboard.

## Structure

```
modules/
├── Core Modules (Flask integration)
│   ├── anonymization_manager.py   # Central anonymization job management
│   ├── audit_logger.py            # Audit logging for compliance
│   ├── fl_orchestrator.py         # Federated Learning orchestration
│   ├── mqtt_manager.py            # MQTT broker communication
│   ├── patient_manager.py         # Patient data management
│   ├── record_linkage.py          # Bloom filter record linkage
│   ├── system_monitor.py          # System health monitoring
│   └── user_manager.py            # Admin user authentication
│
├── utils_central_anon/            # Central anonymization utilities
│   └── (see utils_central_anon/README.md)
│
└── utils_fl/                      # Federated Learning gRPC server
    ├── fl_grpc_server.py          # gRPC server for FL
    ├── aggregator.py              # Model aggregation logic
    ├── global_model.py            # Global model management
    └── Dockerfile                 # FL server container
```

## Core Modules

| Module | Description |
|--------|-------------|
| `anonymization_manager.py` | Manages central anonymization jobs, integrates with InfluxDB |
| `audit_logger.py` | Records user actions for GDPR/compliance audit trails |
| `fl_orchestrator.py` | Coordinates federated learning rounds between server and clients |
| `mqtt_manager.py` | Handles MQTT connections for real-time device communication |
| `patient_manager.py` | Patient list management and data operations |
| `record_linkage.py` | Privacy-preserving record linkage using Bloom filters |
| `system_monitor.py` | Monitors system health (database, MQTT, FL server, InfluxDB) |
| `user_manager.py` | Admin user authentication and session management |

## Submodule Documentation

- **`utils_central_anon/`** - See [utils_central_anon/README.md](utils_central_anon/README.md) for the central anonymization system
- **`utils_fl/`** - Federated Learning gRPC server (runs as separate Docker container)
