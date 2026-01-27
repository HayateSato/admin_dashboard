# MQTT Testing Guide - Command Line

This guide shows how to test MQTT anonymization commands with your Flutter app without implementing the frontend.

## Flutter App MQTT Topics

Your Flutter app uses these MQTT topics:
- **Subscribes to**: `anonymization/commands` - Receives anonymization commands from admin
- **Publishes to**: `anonymization/responses` - Sends acknowledgments back to admin
- **Expected payload**: `{"kValue": 5}` - Valid K values: 2, 3, 5, 10, 15, 20

## Prerequisites

1. **Docker containers must be running**:
   ```bash
   docker-compose up -d
   ```

2. **Verify Mosquitto is running**:
   ```bash
   docker-compose ps | grep mosquitto
   ```

   Expected output:
   ```
   privacy_umbrella_mqtt    Up (healthy)
   ```

---

## Testing Methods

### Method 1: Full Test Suite (Recommended)

Run the comprehensive test script with all automated tests + interactive mode:

```bash
python test_mqtt.py
```

**What it does**:
- ✅ Test MQTT broker connection
- ✅ Publish anonymization command to Flutter app
- ✅ Subscribe to Flutter app responses
- ✅ Test complete command/response workflow
- ✅ Interactive mode for manual testing

**Expected output**:
```
============================================================
MQTT PRIVACY SETTINGS TEST SUITE
============================================================

============================================================
TEST 1: MQTT Broker Connection
============================================================

Connecting to MQTT broker at localhost:1883...
✅ Successfully connected to MQTT broker!

Connection Status:
  - Connected: True
  - Broker: localhost:1883
  - Topic Prefix: anonymization

============================================================
TEST 2: Publish Anonymization Command
============================================================

Publishing anonymization command...
Command: {
  "kValue": 5
}
✅ Command published successfully!

Topic: anonymization/commands
Valid K values: 2, 3, 5, 10, 15, 20
...
```

---
<!-- 
### Method 2: Quick Test (Fastest)

Run a simple one-liner test:

```bash
cd C:\Users\HayateSato\AndroidStudioProjects\Demonstrator\admin_dashbaord
python quick_mqtt_test.py
```

**Optional - specify K value**:
```bash
# Use different K values (valid: 2, 3, 5, 10, 15, 20)
python quick_mqtt_test.py 10
```

**Expected output**:
```
🔌 Connecting to MQTT broker at localhost:1883...
✅ Connected to MQTT broker!
📡 Subscribed to: anonymization/responses

📤 Publishing anonymization command...
   Topic: anonymization/commands
   Command: {'kValue': 5}
✅ Command published!

⏳ Waiting for Flutter app response (10 seconds)...
   Waiting... (2s)
   Waiting... (4s)

📬 Response from Flutter app:
   Topic: anonymization/responses
   Payload: {"response":"success","message":"Anonymization enabled successfully with K=5",...}
   Response type: success
   Message: Anonymization enabled successfully with K=5

============================================================
✅ SUCCESS - Received 1 response(s) from Flutter app!
============================================================
```

--- -->

### Method 2: Direct Command Line (No Python Script)

Use raw MQTT commands directly:

#### A. Subscribe to all privacy topics (Listener)

Open **Terminal 1** and listen for messages:

```bash
# Listen to all anonymization topics (matches Flutter)
docker-compose exec mosquitto mosquitto_sub -t "anonymization/#" -v
```

Keep this terminal open - you'll see messages here.

#### B. Publish anonymization commands (Publisher)

Open **Terminal 2** and publish messages:

**Send anonymization command with K=5**:
```bash
docker-compose exec mosquitto mosquitto_pub \
  -t "anonymization/commands" \
  -m '{"kValue": 5}'
```

**Send anonymization command with K=10**:
```bash
docker-compose exec mosquitto mosquitto_pub \
  -t "anonymization/commands" \
  -m '{"kValue": 10}'
```

**Send test response (simulate Flutter app response)**:
```bash
docker-compose exec mosquitto mosquitto_pub \
  -t "anonymization/responses" \
  -m '{"response":"success","message":"Anonymization enabled successfully with K=5","timestamp":"2025-01-14T12:00:00"}'
```

**Expected in Terminal 1**:
```
anonymization/commands {"kValue": 5}
anonymization/responses {"response":"success","message":"Anonymization enabled successfully with K=5","timestamp":"2025-01-14T12:00:00"}
```

---

### Method 4: Python Interactive Shell

Test directly in Python shell:


```python
# Import required libraries
import paho.mqtt.client as mqtt
import json
import time

# Create MQTT client
client = mqtt.Client(client_id="admin_test")
client.connect("localhost", 1883, 60)
client.loop_start()

time.sleep(2)

# Subscribe to responses
def on_message(client, userdata, msg):
    print(f"Response: {msg.payload.decode()}")

client.on_message = on_message
client.subscribe("anonymization/responses", qos=1)

# Publish anonymization command
command = {"kValue": 5}
client.publish("anonymization/commands", json.dumps(command), qos=1)
print("Command sent!")

# Wait for response
time.sleep(5)

# Cleanup
client.loop_stop()
client.disconnect()
exit()
```

---

## Testing with Flutter App

If you want to test the complete flow with your Flutter app:

### 1. Start Flutter app MQTT service

In your Flutter app, ensure the MQTT service is initialized:
- Connected to `192.168.X.XXX:1883` (your Windows LAN IP)
- Subscribed to `anonymization/commands`
- Ready to publish to `anonymization/responses`

<!-- ### 2. Publish anonymization command from Python

Run the quick test:
```bash
python quick_mqtt_test.py 5
```

This sends: `{"kValue": 5}` to topic `anonymization/commands` -->

### 3. Verify Flutter app receives and processes the command

Check Flutter app logs - you should see:
```
📨 Received MQTT message on anonymization/commands: {"kValue":5}
🔒 Processing anonymization command: K=5
✅ Anonymization enabled remotely with K=5
📤 Sent response: success
```

### 4. Flutter app sends response

Flutter app automatically publishes response to:
- Topic: `anonymization/responses`
- Payload: `{"response":"success","message":"Anonymization enabled successfully with K=5",...}`

### 5. Dashboard receives response

The Python test script automatically listens for responses and displays:
```
📬 Response from Flutter app:
   Response type: success
   Message: Anonymization enabled successfully with K=5
```

---

## Troubleshooting

### Problem: "Failed to connect to MQTT broker"

**Solution**:
```bash
# Check if Mosquitto is running
docker-compose ps | grep mosquitto

# If not running, start it
docker-compose up -d mosquitto

# Check logs
docker-compose logs mosquitto
```

### Problem: "Published but no message received"

**Solution**:
```bash
# Open two terminals

# Terminal 1 - Subscribe to all topics
docker-compose exec mosquitto mosquitto_sub -t "#" -v

# Terminal 2 - Publish test message
docker-compose exec mosquitto mosquitto_pub -t "test" -m "hello"

# You should see the message in Terminal 1
```

### Problem: "Connection refused (port 1883)"

**Solution**:
```bash
# Check if port is exposed
docker-compose ps

# Should show:
# privacy_umbrella_mqtt  ...  0.0.0.0:1883->1883/tcp

# If not, check docker-compose.yml ports section
```

### Problem: "Module not found: paho.mqtt"

**Solution**:
```bash
# Install required packages
pip install paho-mqtt
```

---

## MQTT Topic Structure

Your MQTT topics follow this structure (matches Flutter app):

```
anonymization/
├── commands                # Admin → Flutter: Anonymization commands
│   └── Payload: {"kValue": 5}
│
└── responses              # Flutter → Admin: Command responses
    └── Payload: {"response": "success", "message": "...", "kValue": 5, ...}
```

**Examples**:
- Command: `anonymization/commands` with `{"kValue": 5}`
- Response: `anonymization/responses` with `{"response":"success","message":"Anonymization enabled successfully with K=5"}`

**Valid K Values** (must match Flutter app):
- 2, 3, 5, 10, 15, 20

**Response Types** (from Flutter app):
- `success` - Anonymization enabled successfully
- `error` - Internal error occurred
- `unauthorized` - Unauthorized command
- `invalidKValue` - Invalid K value provided
- `alreadyEnabled` - Anonymization already enabled (cannot change remotely)

---

## Quick Reference

| Task | Command |
|------|---------|
| Run full test suite | `python test_mqtt.py` |
| Quick test (K=5) | `python quick_mqtt_test.py` |
| Quick test (K=10) | `python quick_mqtt_test.py 10` |
| Subscribe to all | `docker-compose exec mosquitto mosquitto_sub -t "anonymization/#" -v` |
| Send command | `docker-compose exec mosquitto mosquitto_pub -t "anonymization/commands" -m '{"kValue":5}'` |
| Check Mosquitto status | `docker-compose ps \| grep mosquitto` |
| View Mosquitto logs | `docker-compose logs mosquitto` |
| Restart Mosquitto | `docker-compose restart mosquitto` |


---

**Last Updated**: 2025-01-14
