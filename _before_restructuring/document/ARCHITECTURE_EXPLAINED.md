# Privacy Umbrella Admin Dashboard - Architecture Explained

### Single Flask Application (app.py)

**IMPORTANT**: The entry point is app.py (Flask application) that orchestrates 4 main services

```
app.py (Main Flask Server - Port 5000)
│
├── Imports and orchestrates ALL modules:
│   ├── modules/patient_manager.py         ← TO DO
│   ├── modules/mqtt_manager.py            ← TO DO
│   ├── modules/anonymization_manager.py     Complete
│   ├── modules/fl_orchestrator.py           Complete
│   ├── modules/record_linkage.py            Complete
│   └── modules/system_monitor.py            Complete
│
└── External Services (separate processes/containers):
    ├── PostgreSQL (internal: 5432, external: 5433)
    ├── InfluxDB (REMOTE: https://pu-influxdb.smarko-health.de/)
    ├── MQTT Broker/Mosquitto (port 1883)
    └── FL gRPC Server (port 50051) ← Can be subprocess OR container
```

---

## Port Configuration (Docker vs Local)

### Understanding Docker Port Mapping

When running in Docker, services have **two port numbers**:
1. **Internal Port**: Used for communication between containers within Docker network
2. **External Port**: Used for access from the host machine (Windows) or external devices

**Format**: `external:internal` in docker-compose.yml

### Port Configuration Summary

| Service | Internal Port | External Port | Access Examples |
|---------|--------------|---------------|-----------------|
| PostgreSQL | 5432 | 5433 | Internal: `postgres:5432`<br>External: `localhost:5433`<br> |
| Dashboard | 5000 | 5000 | Internal: `admin_dashboard:5000`<br>External: `localhost:5000` |
| MQTT | 1883 | 1883 | Internal: `mosquitto:1883`<br>External: `localhost:1883` |
| FL Server | 50051 | 50051 | Internal: `fl_server:50051`<br>External: `localhost:50051` |

### Key Rules

1. **Container-to-Container Communication**: ALWAYS use internal port
   ```python
   # In docker-compose.yml environment variables for admin_dashboard:
   POSTGRES_HOST: postgres
   POSTGRES_PORT: 5432  # Internal port!
   ```

2. **Host-to-Container Communication**: Use external port
   ```python
   # In Flutter app (postgres_db_config.dart):
   host: '192.168.X.XXX' (IP of hosting machine)
   port: 5433  # External port!
   ```

3. **Why PostgreSQL uses different ports?**
   - External port 5433 avoids conflict with local PostgreSQL (if running on host)
   - Internal port 5432 follows PostgreSQL convention

---

## How Services Work

### 1. Central Anonymization

```python
# In modules/anonymization_manager.py
def create_job(self, ...):
    # Calls central_anonymizer.py as subprocess
    script_path = "modules/utils_central_anon/central_anonymizer.py"
    subprocess.Popen([sys.executable, script_path, ...])
```

**Location**: `modules/utils_central_anon/central_anonymizer.py`
**How it runs**: Called by Flask as subprocess, not separate server

---

### 2. FL gRPC Server
**Can run as subprocess OR separate container**:

#### Option A: Subprocess (Development)
```python
# In modules/fl_orchestrator.py
def start_fl_server(self):
    fl_server_script = "modules/utils_fl/fl_grpc_server.py"
    self.fl_server_process = subprocess.Popen([
        sys.executable, fl_server_script
    ])
```

#### Option B: Separate Container (Production - Docker)
- Better for health checks, scaling, management
- Flask connects via gRPC
- Still controlled from Flask UI (start/stop)

**Location**: `modules/utils_fl/fl_grpc_server.py`
**Port**: 50051

---

### 3. Record Linkage

```python
# In app.py
from modules.record_linkage import RecordLinkage
record_linkage = RecordLinkage(config)

# In route:
@app.route('/api/record-linkage/fetch', methods=['POST'])
def fetch_patient_data():
    data = record_linkage.link_patient_data(...)
```

**Location**: `modules/record_linkage.py`
**How it runs**: Direct import, called from Flask routes

---

### 4. Patient Management (TO DO)

```python
# In app.py
from modules.patient_manager import PatientManager
patient_manager = PatientManager(config)

# In route:
@app.route('/api/patients/list')
def get_patients_list():
    patients = patient_manager.get_all_patients()
    return jsonify(patients)
```

**Location**: `modules/patient_manager.py`
**What you need to do**: Enhance `get_all_patients()` method

---

### 5. MQTT Manager (TO DO)

- MQTT broker(server):  docker pu_mqtt_broker 
                        (automatically runs when you compose all docker container)
- MQTT publisher:       modules\mqtt_manager.py
- MQTT config:          mosquitto\mosquitto.conf
- MQTT subscriber:      flutter app

```python
# In app.py
from modules.mqtt_manager import MQTTManager
mqtt_manager = MQTTManager(
    broker_host=config.MQTT_BROKER_HOST,
    broker_port=1883
)
mqtt_manager.connect()  # Connects to external Mosquitto broker

# In route:
@app.route('/api/patients/<unique_key>/update-settings', methods=['POST'])
def update_patient_settings(unique_key):
    mqtt_manager.publish_settings_update(unique_key, settings)
```

**Location**: `modules/mqtt_manager.py`
**External Service**: Mosquitto MQTT broker (separate container/process)
**What you need to do**: Test message publishing with Flutter app

---

## Deployment Architectures

### Development (Local)
```
Terminal 1: mosquitto -v (MQTT broker)
Terminal 2: psql (PostgreSQL)
Terminal 3: python app.py
            ├── Connects to REMOTE InfluxDB at https://pu-influxdb.smarko-health.de/
            ├── Starts FL server as subprocess
            ├── Calls central_anonymizer.py when needed
            ├── Connects to MQTT broker
            └── Imports all modules
```

### Production (Docker)
```
REMOTE: 
InfluxDB at https://pu-influxdb.smarko-health.de/ (already running)

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

LOCAL CONTAINERS:
Container 1: privacy_umbrella_postgres
Container 2: pu_mqtt_broker
Container 3: privacy_umbrella_fl_server 
Container 4: privacy_umbrella_dashboard (Flask app)
            ├── Connects to REMOTE InfluxDB via HTTPS
            ├── Connects to FL server via gRPC
            ├── Calls central_anonymizer.py script
            ├── Connects to MQTT broker
            └── Imports all modules
```

---

## What This Means for You


- ✅ Complete Python modules (patient_manager.py, mqtt_manager.py)
- ✅ Add JavaScript to HTML template
- ✅ Test with existing Flask application
- ✅ Verify MQTT messages with mosquitto_sub

---

## File Structure Explained

```
admin_dashbaord/
├── app.py                  ← SINGLE ENTRY POINT
│   └── Imports all modules below
│
├── modules/                ← All services as Python modules
│   ├── patient_manager.py      ← YOUR TASK: Module 
│   ├── mqtt_manager.py         ← YOUR TASK: MQTT client (not broker)
│   ├── system_monitor.py
│   ├── user_manager.py
│   ├── audit_logger.py
│   ├── anonymization_manager.py  ← Calls script as subprocess
│   ├── fl_orchestrator.py        ← Starts FL server or connects to it
│   ├── record_linkage.py         ← Direct module import
│   │
│   ├── utils_central_anon/
│   │   └── central_anonymizer.py  ← Python script (subprocess)
│   │
│   └── utils_fl/
│       └── fl_grpc_server.py      ← gRPC server (subprocess or container)
│
└── templates/
    └── registered_patients.html    ← YOUR TASK: Add JavaScript
```

---

## Testing Your Work

just run 

```bash
docker-compose up -d
```

this will
 - initiate MQTT broker
 - initiate FL server
 - run Postgres inside the docker
 - run flask app (admin dashboard)
<!-- 
Since everything runs from ONE Flask application:

```bash
# Start external services
mosquitto -v          # Terminal 1 (MQTT broker)
# PostgreSQL should be running
# InfluxDB is REMOTE - no need to start locally!

# Start Flask app
python app.py         # Terminal 2

# Test your patient management
curl http://localhost:5000/api/patients/list

# Test MQTT
mosquitto_sub -h localhost -t "privacy/#" -v  # Terminal 3
# Edit patient in UI, verify message published
```

**That's it!** No need to start InfluxDB locally - it's already running remotely! -->


---

