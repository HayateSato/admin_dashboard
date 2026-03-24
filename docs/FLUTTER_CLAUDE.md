# Flutter App — Backend Connection Guide

This file describes how the Flutter app should connect to the Privacy Umbrella backend.
Drop this file into the Flutter project root as `CLAUDE.md`.

---

## Backend Overview

The backend runs as a set of Docker containers. The Flutter app interacts with two of them:

| Service | Protocol | Address | Purpose |
|---------|----------|---------|---------|
| **nginx → Flask** | HTTPS | `https://<host>` | All REST API calls (registration, settings, records) |
| **mosquitto** | MQTT/TCP | `<host>:1883` | Privacy settings push from admin to device |

**Important:** The Flutter app must **never connect directly to PostgreSQL**. The database port is not exposed. All data reads and writes go through the REST API (nginx → Flask).

---

## Authentication: X-API-Key

Flutter devices do **not** use session-based login. Instead, every request to a device
route must include a shared API key in the `X-API-Key` header.

```dart
const String kApiKey = 'a86305b6921fb211b53c0102ed7699a8b47df90c4cafb4101499392fd4d2ab2a';

// Include this header on every /api/device/* request
final headers = {
  'Content-Type': 'application/json',
  'X-API-Key': kApiKey,
};
```

The key is set via `DEVICE_API_KEY` in the server's `.env` file. If the key doesn't match,
the server responds with `401 Unauthorized`. If `DEVICE_API_KEY` is empty on the server,
all requests pass (dev-only shortcut).

---

## Device API Routes

All Flutter-facing routes are under `/api/device/*`. These require `X-API-Key` auth.
Admin browser routes (`/api/patients/*`) require a session cookie — Flutter cannot use those.

### Register / update device on app launch

Call this every time the app starts. It is idempotent — safe to call repeatedly.

```
POST https://<host>/api/device/register
X-API-Key: <kApiKey>
Content-Type: application/json

{
  "unique_key": "<64-char bloom filter hash>",
  "device_id":  "6C:1D:EB:06:57:9C",
  "k_value":        5,
  "time_window":    30,
  "auto_anonymize": false
}
```

Response `201` (new patient) or `200` (already existed):
```json
{ "success": true, "registered": true, "already_existed": false }
```

### Fetch current privacy settings

Call after registration to get the latest settings pushed by the admin.

```
GET https://<host>/api/device/patients/<unique_key>
X-API-Key: <kApiKey>
```

Response:
```json
{
  "success": true,
  "patient": {
    "unique_key": "...",
    "device_id": "6C:1D:EB:06:57:9C",
    "k_value": 5,
    "time_window": 30,
    "auto_anonymize": false,
    "remote_anon_enabled": false,
    "consent_given": false,
    "last_session": "2025-11-13T13:05:15",
    "created_at": "2025-11-13T11:42:30"
  }
}
```

### Heartbeat (update last_session)

Call when the app connects to stamp `last_session = NOW()` so the admin dashboard
shows the device as recently active.

```
POST https://<host>/api/device/patients/<unique_key>/heartbeat
X-API-Key: <kApiKey>
```

Response:
```json
{ "success": true }
```

### Dart helper class

```dart
import 'dart:convert';
import 'dart:io';
import 'package:http/io_client.dart';
import 'package:http/http.dart' as http;

class PrivacyUmbrellaApi {
  final String baseUrl;
  final String apiKey;
  final http.Client _client;

  PrivacyUmbrellaApi({
    required this.baseUrl,
    required this.apiKey,
    required http.Client client,
  }) : _client = client;

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
  };

  Future<Map<String, dynamic>> register({
    required String uniqueKey,
    required String deviceId,
    int kValue = 5,
    int timeWindow = 30,
    bool autoAnonymize = false,
  }) async {
    final resp = await _client.post(
      Uri.parse('$baseUrl/api/device/register'),
      headers: _headers,
      body: jsonEncode({
        'unique_key': uniqueKey,
        'device_id': deviceId,
        'k_value': kValue,
        'time_window': timeWindow,
        'auto_anonymize': autoAnonymize,
      }),
    );
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getSettings(String uniqueKey) async {
    final resp = await _client.get(
      Uri.parse('$baseUrl/api/device/patients/$uniqueKey'),
      headers: _headers,
    );
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<void> heartbeat(String uniqueKey) async {
    await _client.post(
      Uri.parse('$baseUrl/api/device/patients/$uniqueKey/heartbeat'),
      headers: _headers,
    );
  }
}
```

---

## Current Setup: Self-Signed SSL Certificate

The backend currently uses a **self-signed certificate** (not issued by a trusted CA).
This means Flutter's HTTP client will reject the connection by default with a handshake error.

### Why this happens

Flutter (like all HTTP clients) checks that the certificate is signed by a trusted authority. A self-signed cert is signed by the server itself, which Flutter doesn't trust — even though the encryption is equally strong.

### Fix: override the certificate check (development only)

```dart
import 'dart:io';
import 'package:http/io_client.dart';

/// Creates an HTTP client that accepts the self-signed cert from the backend.
/// ONLY use this while the backend uses a self-signed certificate.
/// Replace with standardClient() once a real domain + Let's Encrypt cert is used.
IOClient createDevHttpClient() {
  final httpClient = HttpClient()
    ..badCertificateCallback = (X509Certificate cert, String host, int port) {
      // Accept only our known backend host — do not use `return true` blindly
      const allowedHosts = ['192.168.x.x', 'localhost', '10.0.2.2'];
      return allowedHosts.contains(host);
    };
  return IOClient(httpClient);
}
```

### Wiring it together (dev)

```dart
// lib/config.dart
const bool kUseSelfSignedCert = true;              // ← change to false for production
const String kApiBaseUrl      = 'https://192.168.x.x'; // ← change to domain for production
const String kApiKey          = 'a86305b6921fb211b53c0102ed7699a8b47df90c4cafb4101499392fd4d2ab2a';

// lib/main.dart or service locator
final httpClient = kUseSelfSignedCert ? createDevHttpClient() : http.Client();
final api = PrivacyUmbrellaApi(
  baseUrl: kApiBaseUrl,
  apiKey:  kApiKey,
  client:  httpClient,
);
```

> **Android emulator note:** `localhost` on the emulator refers to the emulator itself, not your dev machine.
> Use `10.0.2.2` to reach your host machine from the Android emulator.
> Use the machine's LAN IP (e.g. `192.168.1.x`) from a physical device.

### AndroidManifest.xml — allow cleartext? No.

You do **not** need `android:usesCleartextTraffic="true"` — you are using HTTPS (encrypted).
That flag is only needed for plain HTTP, which you should avoid.

---

## Production Setup: Real Domain + Let's Encrypt Certificate

Once a domain is registered and pointed at the server, Let's Encrypt issues a trusted
certificate automatically. No Flutter code changes are needed for certificate handling —
the standard `http` or `dio` package works out of the box.

```dart
// PRODUCTION
const bool kUseSelfSignedCert = false;
const String kApiBaseUrl      = 'https://dashboard.yourhospital.com';
// kApiKey stays the same — just make sure DEVICE_API_KEY on the server matches
```

---

## MQTT Connection (Unchanged)

The Flutter app connects to Mosquitto directly on port `1883` (raw MQTT, not via nginx).
This is used for the admin to **push** privacy setting changes to the device in real time.
The REST API is used for reads and registration; MQTT is for live updates only.

```dart
// pubspec.yaml dependency: mqtt_client: ^9.x.x

import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

final client = MqttServerClient('<host>', 'flutter_client_id')
  ..port = 1883
  ..keepAlivePeriod = 30
  ..logging(on: false);

await client.connect();

// Subscribe to settings updates for this device
client.subscribe('anonymization/<unique_key>/settings', MqttQos.atLeastOnce);
client.subscribe('anonymization/<unique_key>/remote_anon', MqttQos.atLeastOnce);
```

> If you want to secure MQTT in the future, Mosquitto supports MQTT over TLS on port `8883`.
> That would require updating `mosquitto.conf` on the server side and using port `8883` here.

---

## App Launch Sequence

```
1. Compute unique_key from patient PII (bloom filter — same algorithm as Python/PHP)
2. POST /api/device/register       → creates/updates patient row in PostgreSQL
3. GET  /api/device/patients/<key> → fetch current k_value, time_window, auto_anonymize
4. POST /api/device/patients/<key>/heartbeat  → stamp last_session
5. Connect to MQTT                 → subscribe to anonymization/<key>/settings
                                     and anonymization/<key>/remote_anon
6. Apply settings from step 3; update live when MQTT message arrives
```

---

## Summary: What Changed vs Old Setup

| | Old | New |
|--|-----|-----|
| PostgreSQL | App connected directly on port `5433` | **Port removed — use REST API** |
| HTTP/HTTPS | Flask on port `5000` directly | nginx on `443` (HTTPS), self-signed cert |
| Auth | None / session cookie | `X-API-Key` header on all `/api/device/*` routes |
| Registration | Not implemented | `POST /api/device/register` (idempotent) |
| Settings fetch | Not implemented | `GET /api/device/patients/<key>` |
| Heartbeat | Not implemented | `POST /api/device/patients/<key>/heartbeat` |
| MQTT | `host:1883` | `host:1883` (unchanged) |
| FL gRPC | Port `50051` accessible | **Port removed — internal only** |
