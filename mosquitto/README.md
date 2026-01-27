# Mosquitto MQTT Broker Configuration

This folder contains the configuration for the Eclipse Mosquitto MQTT broker used by the Privacy Umbrella system.

## Files

| File | Description |
|------|-------------|
| `mosquitto.conf` | Main broker configuration file |

## Purpose

The MQTT broker facilitates communication between:
- **Flutter mobile apps** (ECG data publishers)
- **Admin dashboard** (subscriber for monitoring)

## Docker Usage

This configuration is automatically mounted when running via Docker Compose:
```yaml
volumes:
  - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
```

The broker runs on:
- **Port 1883** - Standard MQTT protocol
- **Port 9001** - WebSocket connections

## Current Configuration

- **Anonymous access**: Enabled (for development)
- **Persistence**: Enabled (messages saved to disk)
- **Logging**: Error, warning, and notice levels

## Production Considerations

Before deploying to production, review `mosquitto.conf` and enable:

1. **Authentication** - Uncomment `password_file` and set `allow_anonymous false`
2. **TLS/SSL** - Configure certificates for encrypted connections on port 8883
3. **ACLs** - Restrict topic access per user

See the detailed comments in `mosquitto.conf` for configuration instructions.
