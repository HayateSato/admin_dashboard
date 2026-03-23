"""
MQTT Manager for Remote Privacy Settings Control

Handles MQTT communication between admin dashboard and patient devices
for remote privacy settings updates and anonymization control.
"""

import paho.mqtt.client as mqtt
import json
import logging
from typing import Dict, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class MQTTManager:
    """Manages MQTT connections and message publishing for remote device control"""

    def __init__(self, broker_host: str, broker_port: int, topic_prefix: str = "anonymization"):
        """
        Initialize MQTT Manager

        Args:
            broker_host: MQTT broker hostname or IP
            broker_port: MQTT broker port (default: 1883)
            topic_prefix: Topic prefix for all messages (default: "anonymization")
                         IMPORTANT: Must match Flutter app's topic prefix
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        self.client = None
        self.connected = False
        self.ack_callbacks = {}  # Store callbacks for acknowledgments
        self.response_callbacks = {}  # Store callbacks for Flutter responses

        logger.info(f"MQTT Manager initialized: {broker_host}:{broker_port}, prefix='{topic_prefix}'")

    def connect(self) -> bool:
        """
        Connect to MQTT broker

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.client = mqtt.Client(client_id=f"admin_dashboard_{datetime.now().timestamp()}")
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()

            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.info("Disconnected from MQTT broker")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            logger.info("[MQTT] Connected to MQTT broker successfully")

            # Subscribe to acknowledgment topics (legacy)
            ack_topic = f"{self.topic_prefix}/+/ack"
            client.subscribe(ack_topic)
            logger.info(f"[MQTT] Subscribed to acknowledgment topic: {ack_topic}")

            # Subscribe to responses topic (Flutter app responses)
            response_topic = f"{self.topic_prefix}/responses"
            client.subscribe(response_topic)
            logger.info(f"[MQTT] Subscribed to responses topic: {response_topic}")
        else:
            self.connected = False
            logger.error(f"[MQTT] ERROR: Connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"[MQTT] WARNING: Unexpected disconnection (code: {rc})")
        else:
            logger.info("[MQTT] Disconnected normally")

    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            logger.info(f"📬 Received MQTT message on {topic}: {payload}")

            # Parse acknowledgment messages (legacy format)
            if '/ack' in topic:
                data = json.loads(payload)
                unique_key = data.get('unique_key')

                # Call registered callback if exists
                if unique_key in self.ack_callbacks:
                    self.ack_callbacks[unique_key](data)
                    del self.ack_callbacks[unique_key]  # Remove after calling

            # Parse Flutter app responses
            elif '/responses' in topic:
                data = json.loads(payload)
                response_type = data.get('response', 'unknown')
                message = data.get('message', 'No message')
                k_value = data.get('kValue')

                logger.info(f"[MQTT] Flutter app response: {response_type} - {message}")

                if response_type == 'success':
                    logger.info(f"[MQTT] ✅ Settings applied successfully (K={k_value})")
                elif response_type == 'error':
                    logger.error(f"[MQTT] ❌ Settings application failed: {message}")
                elif response_type == 'unauthorized':
                    logger.warning(f"[MQTT] ⚠️  Unauthorized: {message}")

                # Call registered callback if exists
                unique_key = data.get('unique_key')
                if unique_key and unique_key in self.response_callbacks:
                    self.response_callbacks[unique_key](data)
                    del self.response_callbacks[unique_key]

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def publish_settings_update(self, unique_key: str, settings: Dict) -> bool:
        """
        Publish privacy settings update to device

        Args:
            unique_key: Patient's unique identifier (64 hex chars)
            settings: Dictionary with privacy settings
                {
                    'k_value': int,
                    'time_window': int,
                    'auto_anonymize': bool
                }

        Returns:
            bool: True if published successfully, False otherwise
        """
        if not self.connected:
            logger.error("Cannot publish: Not connected to MQTT broker")
            return False

        try:
            # IMPORTANT: Must use 'commands' topic to match Flutter app subscription
            # Flutter app subscribes to: anonymization/commands
            topic = f"{self.topic_prefix}/commands"

            # Format message to match Flutter app expectations
            # Flutter app expects: kValue, timeWindow (not k_value, time_window)
            message = {
                'unique_key': unique_key,
                'kValue': settings.get('k_value'),  # camelCase for Flutter
                'timeWindow': settings.get('time_window'),  # camelCase for Flutter
                'autoAnonymize': settings.get('auto_anonymize'),  # camelCase for Flutter
                'timestamp': datetime.now().isoformat(),
                'source': 'admin_dashboard'
            }

            payload = json.dumps(message)

            result = self.client.publish(topic, payload, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"✅ Published settings update to {topic}")
                logger.info(f"   Settings: K={settings.get('k_value')}, TimeWindow={settings.get('time_window')}s, AutoAnon={settings.get('auto_anonymize')}")
                logger.info(f"   Target: {unique_key[:16]}...")
                logger.info(f"   Waiting for response on {self.topic_prefix}/responses...")
                return True
            else:
                logger.error(f"❌ Failed to publish settings update (rc={result.rc})")
                return False

        except Exception as e:
            logger.error(f"❌ Error publishing settings update: {e}")
            return False

    def publish_remote_anon_activation(self, unique_key: str, enabled: bool) -> bool:
        """
        Publish remote anonymization activation/deactivation

        Args:
            unique_key: Patient's unique identifier
            enabled: True to enable, False to disable

        Returns:
            bool: True if published successfully, False otherwise
        """
        if not self.connected:
            logger.error("Cannot publish: Not connected to MQTT broker")
            return False

        try:
            topic = f"{self.topic_prefix}/remote_anon/{unique_key}"

            message = {
                'unique_key': unique_key,
                'enabled': enabled,
                'timestamp': datetime.now().isoformat(),
                'source': 'admin_dashboard'
            }

            payload = json.dumps(message)

            result = self.client.publish(topic, payload, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                status = "ENABLED" if enabled else "DISABLED"
                logger.info(f"Published remote anonymization {status} to {topic}")
                return True
            else:
                logger.error(f"Failed to publish remote anon activation (rc={result.rc})")
                return False

        except Exception as e:
            logger.error(f"Error publishing remote anon activation: {e}")
            return False

    def register_ack_callback(self, unique_key: str, callback: Callable):
        """
        Register callback to be called when acknowledgment received

        Args:
            unique_key: Patient's unique identifier
            callback: Function to call when ack received, takes Dict parameter
        """
        self.ack_callbacks[unique_key] = callback
        logger.info(f"Registered acknowledgment callback for {unique_key[:16]}...")

    def is_connected(self) -> bool:
        """Check if currently connected to MQTT broker"""
        return self.connected

    def get_status(self) -> Dict:
        """
        Get current MQTT connection status

        Returns:
            Dict with status information
        """
        return {
            'connected': self.connected,
            'broker_host': self.broker_host,
            'broker_port': self.broker_port,
            'topic_prefix': self.topic_prefix,
            'pending_acks': len(self.ack_callbacks)
        }
