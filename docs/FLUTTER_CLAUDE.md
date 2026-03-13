# Flutter App — Backend Connection Guide

This file describes how the Flutter app should connect to the Privacy Umbrella backend.
Drop this file into the Flutter project root as `CLAUDE.md`.

---

## Backend Overview

The backend runs as a set of Docker containers. The Flutter app interacts with two of them:

| Service | Protocol | Address | Purpose |
|---------|----------|---------|---------|
| **nginx → Flask** | HTTPS | `https://<host>` | All REST API calls (user data, sessions, records) |
| **mosquitto** | MQTT/TCP | `<host>:1883` | Real-time messaging / IoT data |

**Important:** The Flutter app must **never connect directly to PostgreSQL**. The database port is not exposed. All data reads and writes go through the REST API (nginx → Flask).

---

## Current Setup: Self-Signed SSL Certificate

The backend currently uses a **self-signed certificate** (not issued by a trusted CA).
This means Flutter's HTTP client will reject the connection by default with a handshake error.

### Why this happens

Flutter (like all HTTP clients) checks that the certificate is signed by a trusted authority. A self-signed cert is signed by the server itself, which Flutter doesn't trust — even though the encryption is equally strong.

### Fix: override the certificate check (development only)

Use a custom `HttpClient` that accepts the self-signed cert for the specific host:

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

Then use it for all API requests:

```dart
final client = createDevHttpClient();

final response = await client.get(
  Uri.parse('https://192.168.x.x/api/v1/sessions'),
  headers: {'Authorization': 'Bearer $token'},
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

Once a domain is registered (e.g. `dashboard.yourhospital.com`) and pointed at the server,
Let's Encrypt issues a trusted certificate automatically. No Flutter code changes are needed
for certificate handling — the standard `http` or `dio` package works out of the box.

### Remove the custom HttpClient

```dart
// PRODUCTION: standard client, no certificate override needed
import 'package:http/http.dart' as http;

final response = await http.get(
  Uri.parse('https://dashboard.yourhospital.com/api/v1/sessions'),
  headers: {'Authorization': 'Bearer $token'},
);
```

Or with Dio:

```dart
import 'package:dio/dio.dart';

final dio = Dio(BaseOptions(
  baseUrl: 'https://dashboard.yourhospital.com',
  headers: {'Authorization': 'Bearer $token'},
));

final response = await dio.get('/api/v1/sessions');
```

### How to switch cleanly

Use an environment-aware factory so you only change one constant:

```dart
// lib/config.dart
const bool kUseSelfSignedCert = true;           // ← change to false for production
const String kApiBaseUrl = 'https://192.168.x.x'; // ← change to domain for production

// lib/network/api_client.dart
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';
import 'config.dart';

http.Client createApiClient() {
  if (kUseSelfSignedCert) {
    final httpClient = HttpClient()
      ..badCertificateCallback = (cert, host, port) {
        const allowedHosts = ['192.168.x.x', 'localhost', '10.0.2.2'];
        return allowedHosts.contains(host);
      };
    return IOClient(httpClient);
  }
  return http.Client(); // standard trusted-CA client
}
```

---

## MQTT Connection (Unchanged)

The Flutter app connects to Mosquitto directly on port `1883` (raw MQTT, not via nginx).
This is unchanged from the previous setup. Mosquitto is still publicly accessible on that port.

```dart
// pubspec.yaml dependency: mqtt_client: ^9.x.x

import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

final client = MqttServerClient('<host>', 'flutter_client_id')
  ..port = 1883
  ..keepAlivePeriod = 30
  ..logging(on: false);

await client.connect();
```

> If you want to secure MQTT in the future, Mosquitto supports MQTT over TLS on port `8883`.
> That would require updating `mosquitto.conf` on the server side and using port `8883` here.

---

## Summary: What Changed vs Old Setup

| | Old | New |
|--|-----|-----|
| PostgreSQL | App connected directly on port `5433` | **Port removed — use REST API** |
| HTTP/HTTPS | Flask on port `5000` directly | nginx on `443` (HTTPS), self-signed cert |
| MQTT | `host:1883` | `host:1883` (unchanged) |
| FL gRPC | Port `50051` accessible | **Port removed — internal only** |
