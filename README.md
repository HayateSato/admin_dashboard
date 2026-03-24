# Privacy Umbrella — Admin Platform

A privacy-preserving healthcare data platform built as independent microservices. Each component can be run, tested, and deployed on its own, or all together via `docker compose up`.

---

## What This System Does

Patients wear ECG devices (Flutter mobile app). Their raw sensor data flows into InfluxDB. This platform lets clinicians and researchers:

- **Inspect** which patients are registered and manage their privacy settings
- **Anonymize** raw ECG data using k-anonymity before sharing it
- **Link** patient identities to their sensor data without storing PII (via bloom filter hashing)
- **Train** a federated XGBoost model across patient devices without centralising raw data

---

## Project Structure

```
admin_dashboard/
│
├── dashboard/                   ← Web UI + API gateway (port 5000)
├── patient_registry_service/    ← Patient data + MQTT device control (port 7001)
├── federated_learning_server/   ← FL gRPC server management (port 7002)
├── record_linkage_service/      ← Bloom-filter hashing + data fetching (port 7003)
├── central_anonymization_api/   ← k-anonymity algorithm (port 6000)
│
├── nginx/                       ← Reverse proxy config + SSL certs
├── mosquitto/                   ← MQTT broker config
├── db/                          ← PostgreSQL schema + seed data
├── docs/                        ← Architecture and dev notes
│
├── docker-compose.yml           ← Starts everything
├── .env.example                 ← Environment variable template
└── _before_restructuring/       ← Original monolithic app (kept for reference)
```

---

## Architecture

```
Browser / Flutter app
        │
        │  HTTPS :443
        ▼
   [ nginx ]  ──── HTTP :80 → 301 redirect to HTTPS
        │
        │  HTTP :5000 (internal)
        ▼
   [ dashboard ]          ← Only public web entry point
   Flask UI + auth           Proxies every /api/* call to a backend service
        │  ↕ Redis :6379 (sessions DB0, health cache DB1)
        │
        ├─── :7001 ──→  [ patient_registry_service ]
        │                  PostgreSQL · MQTT → IoT devices
        │
        ├─── :7002 ──→  [ federated_learning_server ]
        │                  FL gRPC server (port 50051 internal)
        │
        ├─── :7003 ──→  [ record_linkage_service ]
        │                  PostgreSQL · InfluxDB (remote)
        │
        └─── :6000 ──→  [ central_anonymization_api ]
                           k-anonymity algorithm (no DB)

External:
  IoT devices  ──── MQTT :1883 ──→ [ mosquitto ] ←── patient_registry_service
  InfluxDB (remote) ← https://pu-influxdb.smarko-health.de
```

**Key principle:** The dashboard never talks to a database directly. It is a thin gateway — it handles login sessions and forwards every data request to the appropriate service over plain HTTP on the internal Docker network.

---

## Services at a Glance

| Service | Port | README | Core responsibility |
|---------|------|--------|---------------------|
| [dashboard](dashboard/) | 5000 | [→](dashboard/README.md) | Web UI, session auth, API proxy |
| [patient_registry_service](patient_registry_service/) | 7001 | [→](patient_registry_service/README.md) | Patient CRUD, privacy settings, MQTT publish |
| [federated_learning_server](federated_learning_server/) | 7002 | [→](federated_learning_server/README.md) | FL gRPC server lifecycle, training status |
| [record_linkage_service](record_linkage_service/) | 7003 | [→](record_linkage_service/README.md) | PII hashing, InfluxDB + Postgres data fetch |
| [central_anonymization_api](central_anonymization_api/) | 6000 | [→](central_anonymization_api/README.md) | k-anonymity on ECG records |

### Infrastructure

| Component | Exposed ports | What it does |
|-----------|--------------|-------------|
| PostgreSQL 15 | internal only | Patient metadata, privacy policies |
| Redis 7 | internal only | Dashboard sessions (DB 0) + health check cache (DB 1) |
| Mosquitto MQTT | 1883 (TCP), 9001 (WS) | Message broker between server and IoT devices |
| nginx | 80, 443 | TLS termination, HTTP→HTTPS redirect |
| InfluxDB | remote | Raw and anonymized ECG time-series data |

---

## Quickstart

### Prerequisites
- Docker Desktop (or Docker Engine + Compose plugin)
- `openssl` (for generating the self-signed dev certificate)

### 1 — Environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

| Variable | Why it's needed |
|----------|----------------|
| `POSTGRES_PASSWORD` | PostgreSQL access |
| `SECRET_KEY` | Flask session signing (use a long random string) |
| `INFLUX_TOKEN` | InfluxDB read/write access |

### 2 — SSL certificate (development)

```bash
mkdir -p nginx/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/certs/privkey.pem \
  -out nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

Your browser will show a security warning — this is expected with a self-signed cert. Click "Advanced → Proceed".

### 3 — Start everything

```bash
docker compose up --build
```

Services start in dependency order. The dashboard becomes available once all backend services pass their health checks (~60 seconds on first run).

### 4 — Open the dashboard

```
https://localhost
```

Default credentials: `admin` / `admin123`
**Change these in `.env` before any real use.**

---

## Running Without Docker

Each service is a plain Python Flask app. You can run any one independently:

```bash
cd patient_registry_service          # or any other service folder
pip install -r requirements.txt
cp server/.env.example server/.env   # fill in the values
python server/main.py                # starts on the configured port
```

The same pattern works for all five services. Just make sure the services they depend on are also running and reachable at the URLs in their `.env`.

---

## Use-Case Subsets

You do not need to run all services at once. Start only what you need:

| Goal | Services to run |
|------|----------------|
| Full platform | all |
| Manage patients + send MQTT settings | `patient_registry_service` + PostgreSQL + mosquitto |
| Run federated learning only | `federated_learning_server` |
| Inspect / export patient sensor data | `record_linkage_service` + PostgreSQL + InfluxDB |
| Anonymize ECG records | `central_anonymization_api` |
| Dashboard UI only (read-only, no DB) | `dashboard` + any services it needs to call |

---

## Port Reference

| What | Host port | Protocol | Accessible from |
|------|-----------|----------|----------------|
| nginx HTTPS | **443** | HTTPS | Browser, Flutter app |
| nginx HTTP redirect | **80** | HTTP | Browser (redirects to 443) |
| MQTT (IoT devices) | **1883** | MQTT/TCP | Flutter app, IoT devices |
| MQTT WebSocket | **9001** | WS | Browser-based MQTT clients |
| dashboard | — (internal) | HTTP | nginx only |
| central_anon | — (internal) | HTTP | dashboard only |
| patient_registry | — (internal) | HTTP | dashboard only |
| federated_learning | — (internal) | HTTP | dashboard only |
| record_linkage | — (internal) | HTTP | dashboard only |
| FL gRPC | — (internal) | gRPC | federated_learning_server only |
| PostgreSQL | — (internal) | TCP | patient_registry, record_linkage |
| Redis | — (internal) | TCP | dashboard only |

---

## Adding a New Service

1. Create `my_service/server/main.py` (Flask app), `my_service/requirements.txt`, `my_service/server/.env.example`
2. Copy any business-logic files into `my_service/core/`
3. Add a service entry to `docker-compose.yml`
4. Add proxy routes in `dashboard/server/main.py` pointing to the new service URL

---

## Original Monolithic Version

Before this restructuring the entire platform ran as a single `app.py`. That version (along with all original modules, templates, and config) is preserved verbatim at [_before_restructuring/](_before_restructuring/).
