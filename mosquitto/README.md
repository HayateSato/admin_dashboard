# Mosquitto MQTT Broker Configuration

This folder contains the configuration and test scripts for the Eclipse Mosquitto MQTT broker used by the Privacy Umbrella system.

## Files

| File | Description |
|------|-------------|
| `mosquitto.conf` | Main broker configuration file |
| `test_mqtt.py` | Full MQTT test suite with interactive mode |
| `quick_mqtt_test.py` | Quick command-line test script |
| `requirements_mqtt.txt` | Python dependencies for test scripts |

## Purpose

The MQTT broker facilitates communication between:
- **SmarKo apps (Flutter mobile apps)** - Receive anonymization commands (K value, time window)
- **Admin dashboard** - Send privacy settings, monitor responses

### Topic Structure

| Topic | Direction | Description |
|-------|-----------|-------------|
| `anonymization/commands` | Dashboard → App | Send K value and time window settings |
| `anonymization/responses` | App → Dashboard | Receive acknowledgments from apps |

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

## Test Scripts
#### Pre-requisite
> Your SmarKo app needs to subscribe to the IP of your server/PC


### Quick Test

Send a single anonymization command:
```bash
cd mosquitto
pip install -r requirements_mqtt.txt
python quick_mqtt_test.py 5  # Send K=5 command
```

### Full Test Suite

Run comprehensive tests with interactive mode:
```bash
cd mosquitto
python test_mqtt.py
```

The test suite includes:
1. Connection test
2. Publish anonymization command
3. Subscribe to Flutter app responses
4. Full command/response workflow
5. Interactive mode for manual testing

### Manual Testing with Mosquitto CLI

Subscribe to all anonymization topics:
```bash
docker-compose exec mosquitto mosquitto_sub -t "anonymization/#" -v
```

Publish a test command:
```bash
docker-compose exec mosquitto mosquitto_pub -t "anonymization/commands" -m '{"kValue": 5}'
```

## Production Considerations

Before deploying to production, review `mosquitto.conf` and enable:

1. **Authentication** - Uncomment `password_file` and set `allow_anonymous false`
2. **TLS/SSL** - Configure certificates for encrypted connections on port 8883
3. **ACLs** - Restrict topic access per user

See the detailed comments in `mosquitto.conf` for configuration instructions.
