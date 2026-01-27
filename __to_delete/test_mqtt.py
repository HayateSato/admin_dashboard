"""
MQTT Connection and Privacy Settings Test Script
Run this to test MQTT communication without frontend
"""

import sys
import time
import json
from modules.mqtt_manager import MQTTManager

def test_mqtt_connection():
    """Test basic MQTT connection"""
    print("=" * 60)
    print("TEST 1: MQTT Broker Connection")
    print("=" * 60)

    # Configuration - matches Flutter app MQTT topics
    BROKER_HOST = "localhost"  # Use "localhost" when testing from Windows host
    BROKER_PORT = 1883
    TOPIC_PREFIX = "anonymization"  # Changed from "privacy" to match Flutter

    print(f"\nConnecting to MQTT broker at {BROKER_HOST}:{BROKER_PORT}...")

    # Initialize MQTT Manager
    mqtt = MQTTManager(
        broker_host=BROKER_HOST,
        broker_port=BROKER_PORT,
        topic_prefix=TOPIC_PREFIX
    )

    # Connect to broker
    success = mqtt.connect()

    if not success:
        print("❌ Failed to connect to MQTT broker")
        print("\nTroubleshooting:")
        print("1. Check if Mosquitto is running: docker-compose ps")
        print("2. Check logs: docker-compose logs mosquitto")
        return None

    # Wait a moment for connection to establish
    time.sleep(2)

    # Check connection status
    if mqtt.is_connected():
        print("✅ Successfully connected to MQTT broker!")
        status = mqtt.get_status()
        print(f"\nConnection Status:")
        print(f"  - Connected: {status['connected']}")
        print(f"  - Broker: {status['broker_host']}:{status['broker_port']}")
        print(f"  - Topic Prefix: {status['topic_prefix']}")
        return mqtt
    else:
        print("❌ Connection failed")
        return None


def test_publish_anonymization_command(mqtt, k_value):
    """Test publishing anonymization command (matches Flutter app)"""
    print("\n" + "=" * 60)
    print("TEST 2: Publish Anonymization Command")
    print("=" * 60)

    # Command format that matches Flutter app expectations
    command = {
        'kValue': k_value  # Flutter expects 'kValue' not 'k_value'
    }

    print(f"\nPublishing anonymization command...")
    print(f"Command: {json.dumps(command, indent=2)}")

    # Publish to Flutter's command topic
    topic = f"{mqtt.topic_prefix}/commands"

    try:
        payload = json.dumps(command)
        result = mqtt.client.publish(topic, payload, qos=1)

        if result.rc == 0:  # mqtt.MQTT_ERR_SUCCESS
            print("✅ Command published successfully!")
            print(f"\nTopic: {topic}")
            print(f"Valid K values: 2, 3, 5, 10, 15, 20")
            print("\nTo verify, subscribe in another terminal:")
            print(f'  docker-compose exec mosquitto mosquitto_sub -t "{mqtt.topic_prefix}/commands" -v')
            return True
        else:
            print(f"❌ Failed to publish command (rc={result.rc})")
            return False
    except Exception as e:
        print(f"❌ Error publishing command: {e}")
        return False


def test_subscribe_to_responses(mqtt):
    """Test subscribing to Flutter app responses"""
    print("\n" + "=" * 60)
    print("TEST 3: Subscribe to Flutter App Responses")
    print("=" * 60)

    # Subscribe to responses topic
    topic = f"{mqtt.topic_prefix}/responses"

    print(f"\nSubscribing to topic: {topic}")

    # Store received responses
    responses_received = []

    def on_response(client, userdata, msg):
        payload = msg.payload.decode('utf-8')
        print(f"\n📬 Response received from Flutter app!")
        print(f"Topic: {msg.topic}")
        print(f"Payload: {payload}")

        try:
            data = json.loads(payload)
            print(f"Response type: {data.get('response')}")
            print(f"Message: {data.get('message')}")
            responses_received.append(data)
        except:
            pass

    mqtt.client.on_message = on_response
    mqtt.client.subscribe(topic, qos=1)

    print(f"✅ Subscribed to {topic}")
    print("\nWaiting for responses from Flutter app (10 seconds)...")
    print("Flutter app will respond when it receives anonymization commands")

    time.sleep(10)

    if responses_received:
        print(f"\n✅ Received {len(responses_received)} response(s)")
    else:
        print("\n⏱️  No responses received (this is normal if Flutter app is not connected)")

    return len(responses_received) > 0


def test_full_workflow(mqtt, k_value):
    """Test complete workflow: send command + receive response"""
    print("\n" + "=" * 60)
    print("TEST 4: Complete Command/Response Workflow")
    print("=" * 60)

    # Set up response listener
    response_received = [None]

    def on_message(client, userdata, msg):
        if msg.topic == f"{mqtt.topic_prefix}/responses":
            payload = msg.payload.decode('utf-8')
            print(f"\n📬 Flutter app response received!")
            try:
                data = json.loads(payload)
                response_received[0] = data
                print(f"Response: {json.dumps(data, indent=2)}")
            except Exception as e:
                print(f"Error parsing response: {e}")

    mqtt.client.on_message = on_message
    mqtt.client.subscribe(f"{mqtt.topic_prefix}/responses", qos=1)

    print("\nStep 1: Publishing anonymization command...")
    command = {'kValue': k_value}
    topic = f"{mqtt.topic_prefix}/commands"
    mqtt.client.publish(topic, json.dumps(command), qos=1)
    print(f"✅ Published: {command}")

    print("\nStep 2: Waiting for Flutter app response (15 seconds)...")
    for i in range(15):
        time.sleep(1)
        if response_received[0]:
            break
        if i % 3 == 0 and i > 0:
            print(f"  Waiting... ({i}s elapsed)")

    if response_received[0]:
        print("\n✅ Complete workflow successful!")
        return True
    else:
        print("\n⏱️  No response received")
        print("This is normal if:")
        print("  - Flutter app is not running")
        print("  - Flutter app is not connected to MQTT broker")
        print("  - Anonymization is already enabled on Flutter app")
        return False


def interactive_mode(mqtt):
    """Interactive mode for manual testing"""
    print("\n" + "=" * 60)
    print("INTERACTIVE MODE - Flutter App MQTT Testing")
    print("=" * 60)

    # Set up response listener
    def on_message(client, userdata, msg):
        if msg.topic == f"{mqtt.topic_prefix}/responses":
            payload = msg.payload.decode('utf-8')
            print(f"\n📬 Flutter Response: {payload}\n")

    mqtt.client.on_message = on_message
    mqtt.client.subscribe(f"{mqtt.topic_prefix}/responses", qos=1)
    print("✅ Listening for Flutter app responses on 'anonymization/responses'")

    while True:
        print("\nOptions:")
        print("1. Send anonymization command (enable with K value)")
        print("2. Check connection status")
        print("3. Monitor responses only")
        print("4. Exit")

        choice = input("\nEnter choice (1-4): ").strip()

        if choice == '1':
            print("\nValid K values: 2, 3, 5, 10, 15, 20")
            k_value_str = input("Enter K value (default 5): ").strip() or "5"

            try:
                k_value = int(k_value_str)
                if k_value not in [2, 3, 5, 10, 15, 20]:
                    print(f"⚠️  Warning: {k_value} is not a standard K value")

                command = {'kValue': k_value}
                topic = f"{mqtt.topic_prefix}/commands"
                mqtt.client.publish(topic, json.dumps(command), qos=1)
                print(f"✅ Published command: {command}")
                print("Waiting for Flutter response...")
                time.sleep(3)

            except ValueError:
                print("❌ Invalid K value")
        elif choice == '2':
            print("\nValid Time Windows values: 5, 10, 15, 20, 30")
            time_window_value_str = input("Enter Time Windows value (default 5): ").strip() or "5"

            try:
                time_window_value = int(time_window_value_str)
                if time_window_value not in [2, 3, 5, 10, 15, 20]:
                    print(f"⚠️  Warning: {time_window_value} is not a standard time_window_value")

                command = {'time_window': time_window_value}
                topic = f"{mqtt.topic_prefix}/commands"
                mqtt.client.publish(topic, json.dumps(command), qos=1)
                print(f"✅ Published command: {command}")
                print("Waiting for Flutter response...")
                time.sleep(3)

            except ValueError:
                print("❌ Invalid time_window_value")


        elif choice == '0':
            status = mqtt.get_status()
            print(f"\nConnection Status: {json.dumps(status, indent=2)}")

        elif choice == '3':
            print("\n👂 Monitoring responses... (Press Ctrl+C to stop)")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n✅ Stopped monitoring")

        elif choice == '4':
            print("\nExiting...")
            break
        else:
            print("Invalid choice")


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("MQTT PRIVACY SETTINGS TEST SUITE")
    print("=" * 60)
    print("\nThis script tests MQTT communication for remote privacy settings")
    print("Make sure Docker containers are running: docker-compose up -d")

    # Test 1: Connection
    mqtt = test_mqtt_connection()
    if not mqtt:
        print("\n❌ Cannot proceed without MQTT connection")
        sys.exit(1)

    # Test K value (valid Flutter value)
    test_k_value = 5

    try:
        # Test 2: Publish anonymization command
        test_publish_anonymization_command(mqtt, test_k_value)

        time.sleep(1)

        # Test 3: Subscribe to responses
        test_subscribe_to_responses(mqtt)

        time.sleep(1)

        # Test 4: Full workflow
        test_full_workflow(mqtt, test_k_value)

        # Interactive mode
        print("\n" + "=" * 60)
        print("All automated tests completed!")
        print("=" * 60)

        choice = input("\nEnter interactive mode? (y/n): ").strip().lower()
        if choice == 'y':
            interactive_mode(mqtt)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    finally:
        # Cleanup
        print("\nDisconnecting from MQTT broker...")
        mqtt.disconnect()
        print("✅ Disconnected")
        print("\n" + "=" * 60)
        print("TEST SUITE COMPLETED")
        print("=" * 60)


if __name__ == "__main__":
    main()
