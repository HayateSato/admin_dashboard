# CLAUDE.md — Privacy Umbrella Admin Platform

Quick orientation for a new Claude Code session. Read README.md first for the full
architecture overview, service list, quickstart, and port reference. This file covers
implementation decisions, non-obvious patterns, and gotchas that aren't in the README.

---

## Project in one sentence

Five independent Flask microservices behind nginx. The `dashboard` is the only public
entry point — it authenticates users and HTTP-proxies every `/api/*` call to the correct
backend service. No backend service talks to the browser directly.

---

## Key implementation decisions

### Dashboard has zero direct connections
`dashboard/server/main.py` imports only `requests` and `redis`. No psycopg2, no MQTT,
no gRPC. All data comes from the backend services via HTTP proxy. If you need new data
on a dashboard page, add a proxy route — never a direct DB query.

### All services follow the same pattern
```
my_service/
├── server/main.py      Flask app, reads config from os.getenv(), entry point
├── core/               Business logic (no Flask imports)
├── requirements.txt
└── Dockerfile
```
`server/main.py` builds a `_Cfg` dataclass from env vars and passes it to the core
classes. Core classes have no knowledge of Flask. This makes them testable standalone.

### Proxy helper in dashboard
```python
def _proxy(method, service_url, path, **kwargs):
    resp = requests.get(service_url + path, timeout=120, **kwargs)
    return jsonify(resp.json()), resp.status_code
```
Every `/api/*` route in `dashboard/server/main.py` calls this. Returns 503 if the
backend service is unreachable. Do not add business logic here.

---

## Redis usage (dashboard only)

Two logical databases on the same Redis instance (`redis:6379`):

| DB | Prefix | Purpose | TTL |
|----|--------|---------|-----|
| 0 | `pu_session:` | Flask server-side sessions (flask-session) | 8 hours |
| 1 | `health:` | Cached `/health` responses for the overview page | 10 seconds |

Sessions: configured via `app.config['SESSION_TYPE'] = 'redis'` — browser holds only
an opaque random ID, actual session data lives in Redis.

Health cache: `_cached_health(url)` in `main.py` — cache-aside pattern. Prevents the
dashboard overview page from hitting all 4 backend `/health` endpoints on every load.

To inspect live sessions:
```bash
docker exec -it privacy_umbrella_redis redis-cli
KEYS pu_session:*       # active sessions
KEYS health:*           # cached health results (DB 1: redis-cli -n 1)
```

---

## SSL / HTTPS

**Current setup:** self-signed certificate in `nginx/certs/` (gitignored).
Generate with:
```bash
mkdir -p nginx/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/certs/privkey.pem -out nginx/certs/fullchain.pem -subj "/CN=localhost"
```
Browser will show a security warning — click Advanced → Proceed.

**nginx.conf proxies to `dashboard:5000`** (Docker service name, not container name).
If you see `host not found in upstream` in nginx logs, check this name matches the
service name in `docker-compose.yml`.

**Flutter app:** must use `badCertificateCallback` to bypass cert validation with
self-signed. See `docs/FLUTTER_CLAUDE.md` for code examples and the production
(Let's Encrypt) equivalent.

---

## Central Anonymization — CSV dependency

`central_anonymization_api` requires `smarko_hierarchy_ecg.csv` at runtime.
The file is **not in the repo** (large data file).

- Docker: place at `central_anonymization_api/data/smarko_hierarchy_ecg.csv` — it is
  bind-mounted into the container at `/app/data/smarko_hierarchy_ecg.csv`
- Env var: `HIERARCHY_CSV_PATH` (set in docker-compose, defaults to the mount path)
- Without the CSV the service starts but `/api/v1/anonymize` returns 503

---

## Bloom filter / unique_key

Patient PII (name, DOB, gender) is never stored. Instead a 500-bit bloom filter hash
is computed and stored as `unique_key` (base64). The same algorithm runs in:
- Python (`record_linkage_service/core/record_linkage.py`)
- Dart (Flutter app)
- PHP (partner registration system)

**Do not change the seeds or hash parameters** — all three implementations must stay
identical or patient lookup breaks.

---

## Federated Learning

The FL service manages a gRPC subprocess. `fl_orchestrator.py` spawns
`grpc/fl_grpc_server.py` as a child process on port 50051 (internal only).
The REST API on 7002 controls and monitors that subprocess.

Training is automatic — it starts when enough clients send weights. The
`/api/fl/training/start` endpoint only records intent, it does not trigger training.

Global model is persisted to `grpc/global_model_latest.json` (volume-mounted in Docker).

---

## Common gotchas

**nginx 502 after rebuilding a service:** nginx caches the container's IP at startup.
Rebuilding a container assigns a new IP. Fix: `docker compose restart nginx`.

**nginx `host not found in upstream`:** nginx.conf had the old container name
`admin_dashboard` — was corrected to `dashboard` (the docker-compose service name).
If this recurs, check `nginx/nginx.conf` line with `proxy_pass`.

**Dashboard 500 on page load:** usually a Jinja2 `url_for('endpoint_name')` call in a
template that doesn't match the function name in `main.py`. The function name is the
endpoint name, not the URL path.

**`session` variable undefined in template:** all page routes must pass
`user=session.get('user'), role=session.get('role')` to `render_template`. The base
template uses both.

---

## Docs folder (gitignored, personal notes)

| File | Contents |
|------|----------|
| `docs/rest_api_notes.md` | REST API crash course with curl examples for this project |
| `docs/redis_sessions.md` | Redis deep-dive: sessions, caching, cookie vs Redis comparison |
| `docs/FLUTTER_CLAUDE.md` | Flutter connection guide: self-signed cert bypass + MQTT |

---

## Environment variables

Root `.env` is shared via docker-compose. Each service also has `server/.env.example`.
Minimum required in `.env` to run:
```
POSTGRES_PASSWORD=...
SECRET_KEY=...          # long random string for Flask session signing
INFLUX_TOKEN=...        # InfluxDB remote instance token
```

---

## What does NOT exist yet (known gaps)

- No user management UI — credentials are hardcoded env vars (`ADMIN_USERNAME`, `ADMIN_PASSWORD`). `_before_restructuring/` has a `user_manager.py` showing the intended DB-backed design.
- No rate limiting on login endpoint
- `smarko_hierarchy_ecg.csv` must be supplied manually (not in repo)
