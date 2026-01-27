# Privacy Umbrella Admin Dashboard - Docker Deployment Guide

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Detailed Setup](#detailed-setup)
5. [Configuration](#configuration)
6. [Service Management](#service-management)
7. [Troubleshooting](#troubleshooting)
8. [Production Deployment](#production-deployment)
9. [Backup and Recovery](#backup-and-recovery)

---

Additional documents avaiable from 

- document\To DO.txt
- document\ARCHITECTURE_EXPLAINED.md
- document\MQTT_TESTING_GUIDE.md
- document\postgres_table_schema.txt


## Overview

This guide explains how to deploy the Privacy Umbrella Admin Dashboard and all related services using Docker and Docker Compose.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       REMOTE SERVICE (External)                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  InfluxDB (Remote - https://pu-influxdb.smarko-health.de/)       │   │
│  │  - Raw biometric data (raw-data bucket)                          │   │
│  │  - Anonymized biometric data (anonymized-data bucket)            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ HTTPS
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│              LOCAL DOCKER COMPOSE NETWORK (privacy_umbrella_network)    │
│                                                                         │
│  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │   PostgreSQL      │  │    Mosquitto     │  │  FL gRPC Server  │      │
│  │  (Port 5432)      │  │  (Port 1883)     │  │   (Port 50051)   │      │
│  │                   │  │  WebSocket 9001  │  │                  │      │
│  │ - users           │  │                  │  │ - Model training │      │
│  │ - admin_users     │  │ - Privacy policy │  │ - Aggregation    │      │
│  │ - privacy_policies│  │   updates        │  │                  │      │
│  └───────────────────┘  └──────────────────┘  └──────────────────┘      │
│           ▲                     ▲                      ▲                │
│           │                     │                      │                │
│           └─────────────────────┴──────────────────────┘                │
│                                 │                                       │
│                    ┌────────────────────────┐                           │
│                    │   Admin Dashboard      │                           │
│                    │   (Flask - Port 5000)  │                           │
│                    │                        │                           │
│                    │ Modules:               │                           │
│                    │ - Record Linkage       │                           │
│                    │ - Central Anonymization│                           │
│                    │ - FL Orchestration     │                           │
│                    │ - Patient Management   │                           │
│                    │ - MQTT Manager         │                           │
│                    └────────────────────────┘                           │
│                                 │                                       │
└─────────────────────────────────│───────────────────────────────────────┘
                                  │
                                  ▼
                          Browser (localhost:5000)
                         
```

### Services

**Remote Service (Pre-configured - NO SETUP NEEDED):**
1. **SmarKo App (flutter app)** (https://gitlab.com/mcs-datalabs/mcs-smart-data.git)
   - c_synchro_ano branch  --> clone this one 
   - c_asynchro_ano branch  --> anonymization happens non-real time, only after the app stops recording

2. **InfluxDB** - Time-series biometric data storage (https://pu-influxdb.smarko-health.de/)
   - Organization: `MCS Datalabs GmbH`
   - Buckets: `raw-data`, `anonymized-data`

**Local Docker Services:**
1. **PostgreSQL** - User metadata, privacy policies
   - Tables: `users`, `admin_users`, `privacy_policies`
   <!-- - Commented Out: `sessions`, `audit_logs`, `fl_rounds`, `anonymization_jobs` -->
2. **Mosquitto** - MQTT broker for remote privacy policy updates
3. **FL gRPC Server** - Federated learning model aggregation
4. **Admin Dashboard** - Flask web application orchestrating all services

### Data Flow 

##### remote anonymization setting

```
Flutter App → PostgreSQL (user registration, privacy settings)
          ↓
Dashboard reads PostgreSQL → Displays patient list
          ↓
Admin updates privacy policy → MQTT publish → Flutter App receives update
```

##### Central anonymization
```
Flutter App → data is stored in InfluxDB
          ↓
Dashboard triggers Central Anonymization → Reads InfluxDB → applies anonymization 
          ↓
Dashboard Send to selected output channel (back to InfluxDB/save locally - CSV/Send via API)
```
##### Record Linkage
```
Flutter App → data is stored in InfluxDB
          ↓
Dashboard triggers Record Linkage → Reads InfluxDB + Postgres → merge the matached data  
          ↓
Dashboard Send to selected output channel (back to InfluxDB/save locally - CSV/Send via API)
```
##### FL Orhcestration
```
Flutter App → data is stored in Mobile app
          ↓
Dashboard open FL server → listens any joining clients  
          ↓
Flutter App → process collected data locally → execute local training → send model update
          ↓
Dashboard receives model updates from all clietns and aggregate them → send back the new model to clients 
```

### Output Directory Structure

```
admin_dashbaord/
└── output/
    ├── linked_records/                   # Record linkage CSV/JSON exports
    │    └── patient_data_*.csv
    │ 
    └── centrally_anonymized_records/     # Central anonymization outputs
         └── YYYYMMDD_HHMM/
            ├── anonymized_data.csv
            └── summary.json
```

---

## Prerequisites

### Required Software

- **Docker** 20.10 or higher
- **Docker Compose** 2.0 or higher
- **Git** (to clone repository)

---

## Quick Start

### 1. Clone Repository
```bash
git clone git@gitlab.com:hayatesato/admin_dashboard.git
```

### 2. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit followings
# - SECRET_KEY
# - POSTGRES_PASSWORD
# - INFLUX_TOKEN 
```

**Generate secure values**:
```bash
# Generate SECRET_KEY (Python)
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Start All Services
```bash
# Build and start all containers
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### 4. Access Dashboard
Open browser: `http://localhost:5000`

Default credentials:
- **Username**: `admin`
- **Password**: `admin123` 

---

## Detailed Setup

### Step 1: Prepare Configuration

#### Create `.env` File
```bash
cp .env.example .env
```

Edit `.env`:
```env
SECRET_KEY=<your-generated-secret-key>
POSTGRES_PASSWORD=<strong-password>
INFLUX_URL=https://pu-influxdb.smarko-health.de/
INFLUX_TOKEN=<TOKEN>
```

### Step 2: Build Images

```bash
# Build all images
docker-compose build --no-cache

# Verify images
docker images | grep privacy_umbrella
```

### Step 3: Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

Expected output:
```
NAME                                                STATUS
Network admin_dashbaord_privacy_umbrella_network    Created
privacy_umbrella_postgres                           Up (healthy)
privacy_umbrella_mqtt_broker                        Up (healthy)
privacy_umbrella_fl_server                          Up (healthy)
privacy_umbrella_dashboard                          Up (healthy)
```
Note: InfluxDB is not listed - it's running remotely!

### Step 4: Verify Deployment

### Verify Remote InfluxDB Connection

```bash
# from project root, run this 
docker exec -it privacy_umbrella_dashboard sh

# now you're inside the container. check that correct Influx credential is loaded from .env 
env | grep INFLUX

# Run this to check the connection to Influx
curl -v https://pu-influxdb.smarko-health.de/ping
```


#### Test PostgreSQL
```bash
# Go to inside the postgres container, and access the privacy_umbrella db 
docker exec -it privacy_umbrella_postgres psql -U postgres -d privacy_umbrella

# Run SQL command to verify the data 
SELECT * FROM users LIMIT 5;
```
<!--  docker-compose exec postgres psql -U postgres -d pu -c "SELECT COUNT(*) FROM users;" -->

<!-- #### Test Remote InfluxDB Connection
```bash
# Check dashboard logs for InfluxDB connection
docker-compose logs admin_dashboard | grep -i "influx"
# Should see successful connection messages, no errors
``` -->

#### Test MQTT
```bash
docker-compose exec mosquitto mosquitto_sub -t "test/#" -v &
docker-compose exec mosquitto mosquitto_pub -t "test/message" -m "Hello"
```

#### Test Dashboard
```bash
curl http://localhost:5000/login
```

---

## Configuration

### Environment Variables

Key configuration in `.env`:

```env
# Flask
SECRET_KEY=<required>
FLASK_PORT=5000
FLASK_DEBUG=False

# PostgreSQL
POSTGRES_PASSWORD=password_123
POSTGRES_PORT=5432

# InfluxDB (Remote)
INFLUX_URL=https://pu-influxdb.smarko-health.de/
INFLUX_TOKEN=<required>
# NOTE: INFLUX_ADMIN_PASSWORD and INFLUX_PORT not needed for remote instance

# MQTT
MQTT_BROKER_PORT=1883

# FL Server
FL_SERVER_PORT=50051
```

### Port Mapping

| Service | Internal Port (Container-to-Container) | External Port (Host Access) | Notes |
|---------|---------------------------------------|----------------------------|--------|
| Dashboard | 5000 | 5000 | Access via `http://localhost:5000` |
| PostgreSQL | 5432 | 5433 | Internal: `postgres:5432`,<br> External: `localhost:5433` |
| MQTT | 1883 | 1883 | Internal: `mosquitto:1883`,<br> External: `localhost:1883` |
| FL Server | 50051 | 50051 | Internal: `fl_server:50051`,<br> External: `localhost:50051` |

**Important Port Configuration Notes:**

- **Internal Port (Container-to-Container)**: Used when services communicate within Docker network
  - Example: Dashboard connects to PostgreSQL using `postgres:5432`
  - Example: Dashboard connects to FL Server using `fl_server:50051`

- **External Port (Host Access)**: Used when accessing from Windows host machine
  - Example: Flutter app connects to PostgreSQL using `192.168.X.XXX:5433`
  - Example: Dashboard accessed from browser using `localhost:5000`

- **PostgreSQL Special Case**: Port mapping is `5433:5432`
  - Inside Docker: All containers use `postgres:5432`
  - Outside Docker: Host machine uses `localhost:5433`
  - Flutter app on phone uses `192.168.X.XXX:5433` (LAN IP)

**Note:** InfluxDB not listed - it's hosted remotely at https://pu-influxdb.smarko-health.de/

### Volume Configuration

| Volume | Purpose |
|--------|---------|
| `postgres_data` | Database files |
| `mosquitto_data` | MQTT persistence |
| `fl_models` | Global models |
| `dashboard_logs` | Application logs |

**Note:** InfluxDB volumes not needed - data stored remotely

---

## Service Management

### Start/Stop Services

```bash
# Start all
docker-compose up -d

# Stop all
docker-compose down

# Restart all
docker-compose restart

# Restart specific service
docker-compose restart admin_dashboard
```

### View Logs

```bash
# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f admin_dashboard

# Last 100 lines
docker-compose logs --tail=100
```

### Execute Commands

```bash
# Open shell
docker-compose exec admin_dashboard bash

# Access PostgreSQL
docker-compose exec postgres psql -U postgres -d privacy_umbrella

# Access remote InfluxDB (if needed)
# Use the web UI at https://pu-influxdb.smarko-health.de/
# Or use influx CLI with remote URL
```

---

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Find process
netstat -ano | findstr :5000  # Windows
lsof -i :5000                 # Linux/Mac

# Change port in .env
FLASK_PORT=8080
```

#### PostgreSQL Won't Start
```bash
# Check logs
docker-compose logs postgres

# Reset volume
docker-compose down -v
docker-compose up -d postgres
```

#### InfluxDB Connection Failed
```bash
# Check connection to remote InfluxDB
docker-compose logs admin_dashboard | grep -i influx

# Verify .env settings:
# - INFLUX_URL=https://pu-influxdb.smarko-health.de/
# - INFLUX_TOKEN is correct 

# Restart dashboard after fixing .env
docker-compose restart admin_dashboard
```

#### MQTT Connection Failed
```bash
# Check logs
docker-compose logs mosquitto

# Test
docker-compose exec mosquitto mosquitto_sub -t '$SYS/#'
```

### Debug Mode

```bash
# Edit .env
FLASK_DEBUG=True
LOG_LEVEL=DEBUG

# Restart
docker-compose restart admin_dashboard

# View logs
docker-compose logs -f admin_dashboard
```

---

## Production Deployment

### Security Checklist

- [ ] Change default admin password
- [ ] Generate strong SECRET_KEY
- [ ] Use strong database passwords
- [ ] Enable MQTT authentication
- [ ] Set FLASK_DEBUG=False
- [ ] Enable HTTPS (reverse proxy)
- [ ] Configure firewall
- [ ] Enable audit logging
- [ ] Set up backups
- [ ] Configure monitoring

### Enable HTTPS (Nginx)

Create `nginx.conf`:
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Add to `docker-compose.yml`:
```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - admin_dashboard
```

### Resource Limits

```yaml
services:
  postgres:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```

---

## Backup and Recovery

### Backup Script

Create `backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="./backups/$(date +%Y-%m-%d)"
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker-compose exec -T postgres pg_dump -U postgres pu > $BACKUP_DIR/postgres.sql

# Backup volumes
docker run --rm \
  -v admin_dashbaord_postgres_data:/data \
  -v $(pwd)/$BACKUP_DIR:/backup \
  alpine tar czf /backup/postgres_data.tar.gz -C /data .

echo "Backup completed: $BACKUP_DIR"
```

### Schedule Backups

```bash
# Crontab
0 2 * * * /path/to/backup.sh
```

### Restore

```bash

# Accessing Postgres inside Docker
docker exec -it privacy_umbrella_postgres psql -U postgres -d privacy_umbrella

# Stop services
docker-compose down

# Restore PostgreSQL
docker-compose up -d postgres
cat backup/postgres.sql | docker-compose exec -T postgres psql -U postgres pu

# Restart all
docker-compose up -d
```

---

## Additional Resources

- document\To DO.txt
- document\ARCHITECTURE_EXPLAINED.md
- document\MQTT_TESTING_GUIDE.md
- document\postgres_table_schema.txt

---

**Document Version**: 1.0
**Last Updated**: 2025-11-12
