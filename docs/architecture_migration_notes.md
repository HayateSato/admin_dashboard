# Architecture Migration Notes

## Current State (Before Hardening)

### Flutter Android App → PostgreSQL Direct Connection

**The Flutter/Android app currently connects directly to PostgreSQL on port 5433 (host-mapped from internal 5432).**

- Connection: `<server-host>:5433`
- Purpose: Writes user records and session information directly into the database
- Auth: PostgreSQL username/password only

This is the reason `ports: "5433:5432"` existed in `docker-compose.yml`.

**This is a known security risk** (direct DB exposure) that was accepted as a temporary measure while the Flutter app was being developed. It needs a follow-up fix on the app side.

---

## Target State (After Hardening — Implemented)

PostgreSQL port is **no longer exposed** on the host. The Flutter app **must be updated** to write data through the REST API instead.

### Required Flutter App Changes

1. **Replace direct DB calls** with HTTP requests to the admin dashboard API (`http://<server>:80/api/...` or via Nginx)
2. **Create API endpoints** in the Flask app to handle what the Flutter app was doing directly:
   - User registration / lookup
   - Session creation / validation
   - Any other record writes the app was doing
3. **Authentication**: Use JWT tokens or session cookies via the API — not raw DB credentials

### Suggested API Endpoints to Add (Flask side)

```
POST /api/v1/sessions          # Create a new session
POST /api/v1/users/register    # Register a user from the mobile app
GET  /api/v1/users/<id>        # Fetch user info
```

These should be secured with an API key or JWT, scoped to mobile app access only.

---

## What Changed in docker-compose.yml

| Service | Before | After |
|---------|--------|-------|
| postgres | `ports: "5433:5432"` | No port binding — internal only |
| fl_server | `ports: "50051:50051"` | No port binding — internal only |
| admin_dashboard | `ports: "5000:5000"` | No port binding — Nginx handles public traffic |
| nginx | (did not exist) | Added — listens on 80 (and 443 when certs are added) |

---

## Rollback (Temporary, If Flutter App Is Not Ready)

If the Flutter app hasn't been updated yet and you need to restore DB access temporarily:

```yaml
# In docker-compose.yml, under postgres:
ports:
  - "127.0.0.1:5433:5432"  # Safer: binds to localhost only, not 0.0.0.0
```

Using `127.0.0.1:5433:5432` instead of `5433:5432` restricts access to the local machine only (no remote exposure), which is safer than the original while still allowing local connections.

---

## Timeline

- **Current**: Flutter app needs to be updated to use API instead of direct DB
- **After Flutter update**: The rollback section above becomes permanently unnecessary
