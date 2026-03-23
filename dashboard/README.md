# Dashboard (Admin UI + API Gateway)

The web interface for the Privacy Umbrella platform. Handles user authentication and serves HTML pages. Every data operation is forwarded to the appropriate backend microservice over HTTP — the dashboard has no direct database or broker connections.

**Port:** `5000`

---

## Responsibility

The dashboard has two roles:

1. **Authentication gateway** — manages admin login sessions (Flask session cookies). All pages and API routes require a valid session.
2. **API proxy** — every `/api/*` request the browser makes is forwarded to the correct backend service and the response is returned to the browser unchanged.

```
Browser
  │  GET /registered-patients        → returns HTML page
  │  GET /api/patients/list          → proxied to patient_registry:7001/api/patients
  │  POST /api/fl/server/start       → proxied to federated_learning:7002/api/fl/server/start
  │  POST /api/record-linkage/fetch  → proxied to record_linkage:7003/api/fetch
  │  POST /api/anonymization/trigger → proxied to central_anon:6000/api/v1/anonymize
  ▼
dashboard (Flask)
```

This design means the dashboard can be replaced, redesigned, or scaled without touching any backend service.

---

## Folder Structure

```
dashboard/
├── server/
│   ├── main.py          Flask app — auth, page routes, proxy routes (entry point)
│   ├── .env.example     Environment variable template
│   ├── templates/       Jinja2 HTML templates (one per page)
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── registered_patients.html
│   │   ├── fl_orchestration.html
│   │   ├── record_linkage.html
│   │   ├── anonymization.html
│   │   ├── settings.html
│   │   ├── 404.html
│   │   └── 500.html
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
└── requirements.txt
```

---

## Pages

| URL | Template | Access |
|-----|----------|--------|
| `/login` | `login.html` | Public |
| `/dashboard` | `dashboard.html` | Login required |
| `/registered-patients` | `registered_patients.html` | Admin only |
| `/federated-learning` | `fl_orchestration.html` | Login required |
| `/record-linkage` | `record_linkage.html` | Login required |
| `/anonymization` | `anonymization.html` | Login required |
| `/settings` | `settings.html` | Admin only |

---

## API Proxy Routes

All routes under `/api/*` require login. They proxy to backend services:

### Patient Registry (`→ patient_registry:7001`)

| Method | Dashboard route | Proxied to |
|--------|----------------|-----------|
| `GET` | `/api/patients/list` | `/api/patients` |
| `POST` | `/api/patients/<key>/update-settings` | `/api/patients/<key>/settings` |
| `POST` | `/api/patients/<key>/toggle-remote-anon` | `/api/patients/<key>/toggle-remote-anon` |
| `GET` | `/api/mqtt/status` | `/api/mqtt/status` |

### Federated Learning (`→ federated_learning:7002`)

| Method | Dashboard route | Proxied to |
|--------|----------------|-----------|
| `GET` | `/api/fl/status` | `/api/fl/status` |
| `GET` | `/api/fl/clients` | `/api/fl/clients` |
| `GET` | `/api/fl/global-model` | `/api/fl/global-model` |
| `POST` | `/api/fl/start-training` | `/api/fl/training/start` |
| `POST` | `/api/fl/stop-training` | `/api/fl/training/stop` |
| `GET` | `/api/fl/training-history` | `/api/fl/training/history` |
| `POST` | `/api/fl/server/start` | `/api/fl/server/start` |
| `POST` | `/api/fl/server/stop` | `/api/fl/server/stop` |
| `GET` | `/api/fl/server/status` | `/api/fl/server/status` |
| `GET` | `/api/fl/server/status-details` | `/api/fl/server/status-details` |
| `GET` | `/api/fl/training/stats` | `/api/fl/training/stats` |

### Record Linkage (`→ record_linkage:7003`)

| Method | Dashboard route | Proxied to |
|--------|----------------|-----------|
| `POST` | `/api/record-linkage/fetch` | `/api/fetch` |
| `POST` | `/api/record-linkage/fetch-by-key` | `/api/fetch-by-key` |
| `POST` | `/api/record-linkage/export-csv` | `/api/export/csv` |
| `POST` | `/api/record-linkage/export-json` | `/api/export/json` |

### Central Anonymization (`→ central_anon:6000`)

| Method | Dashboard route | Proxied to |
|--------|----------------|-----------|
| `GET` | `/api/anonymization/jobs` | `/api/v1/anonymize/jobs` |
| `POST` | `/api/anonymization/verify-patient` | proxied to `record_linkage/api/verify-patient` |
| `POST` | `/api/anonymization/verify-unique-key` | proxied to `record_linkage/api/verify-unique-key` |
| `POST` | `/api/anonymization/trigger` | `/api/v1/anonymize` |
| `GET` | `/api/anonymization/jobs/<id>/status` | `/api/v1/anonymize/jobs/<id>/status` |
| `POST` | `/api/anonymization/jobs/<id>/cancel` | `/api/v1/anonymize/jobs/<id>/cancel` |

---

## Authentication

Session-based (Flask cookie sessions). Credentials are set via environment variables:

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

There are two access levels:
- **login required** — any logged-in user can access the page
- **admin required** — only the admin user (set in `.env`) can access the page

> For production, replace the hardcoded single-user auth with a proper database-backed user table. The `user_manager.py` module in `_before_restructuring/` shows the intended design.

---

## Configuration

Copy `server/.env.example` to `server/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | — | **Required.** Flask session signing key — use a long random string |
| `SESSION_TIMEOUT_HOURS` | `8` | How long a session stays valid |
| `ADMIN_USERNAME` | `admin` | Login username |
| `ADMIN_PASSWORD` | `admin123` | Login password — **change this** |
| `PATIENT_REGISTRY_URL` | `http://localhost:7001` | URL of the patient registry service |
| `FEDERATED_LEARNING_URL` | `http://localhost:7002` | URL of the FL service |
| `RECORD_LINKAGE_URL` | `http://localhost:7003` | URL of the record linkage service |
| `CENTRAL_ANON_URL` | `http://localhost:6000` | URL of the central anonymization API |
| `PORT` | `5000` | Dashboard port |
| `FLASK_DEBUG` | `false` | |

When running in Docker, service URLs automatically resolve to container names (e.g. `http://patient_registry:7001`).

---

## Quickstart (standalone)

```bash
cd dashboard
pip install -r requirements.txt
cp server/.env.example server/.env   # fill in SECRET_KEY and service URLs
python server/main.py
# → http://localhost:5000
```

The dashboard will start even if no backend services are running. Pages will load but API calls will return `503 Service Unavailable` until the respective service is up.

---

## Adding a New Page

1. Create `server/templates/my_page.html` (extend `base.html`)
2. Add a page route in `server/main.py` that calls `render_template('my_page.html', ...)`
3. Add proxy routes for any new API calls the page needs
4. Add the relevant service URL to `.env` if calling a new service

---

## Dependencies

- No database or MQTT connection
- `requests` library for proxying to backend services
- All other data comes from the backend services
