"""
Explore InfluxDB Bucket

This script explores what data actually exists in the InfluxDB bucket
to help diagnose why queries are returning 0 records.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.ERROR,  # Only show errors, not all the INFO logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from influxdb_client import InfluxDBClient
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False
    logger.error("[FAIL] influxdb-client not installed. Run: pip install influxdb-client")
    exit(1)


def explore_bucket():
    """Explore what data exists in the bucket"""

    # Load config
    url = os.getenv('INFLUX_URL', 'http://localhost:8086')
    token = os.getenv('INFLUX_TOKEN', '')
    org = os.getenv('INFLUX_ORG', '')
    bucket = os.getenv('INFLUX_INPUT_BUCKET', 'raw-data')

    print("="*70)
    print("  InfluxDB Bucket Explorer")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"   URL: {url}")
    print(f"   Org: {org}")
    print(f"   Bucket: {bucket}")
    print()

    # Connect
    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    # Test 1: List all measurements in the bucket
    print("="*70)
    print("  TEST 1: List All Measurements in Bucket")
    print("="*70)

    query = f'''
import "influxdata/influxdb/schema"

schema.measurements(bucket: "{bucket}")
'''

    try:
        tables = query_api.query(query)
        measurements = []
        for table in tables:
            for record in table.records:
                measurement_name = record.get_value()
                measurements.append(measurement_name)

        if measurements:
            print(f"\n[OK] Found {len(measurements)} measurement(s):")
            for m in measurements:
                print(f"   - {m}")
        else:
            print("\n[FAIL] No measurements found in bucket")
            print("   This might mean the bucket is empty!")
    except Exception as e:
        print(f"\n[FAIL] Failed to list measurements: {e}")

    # Test 2: Get sample of ANY data (last 10 records, any measurement)
    print("\n" + "="*70)
    print("  TEST 2: Sample ANY Data (Last 10 Records)")
    print("="*70)

    query = f'''
from(bucket: "{bucket}")
  |> range(start: -30d)
  |> limit(n: 10)
  |> sort(columns: ["_time"], desc: true)
'''

    try:
        tables = query_api.query(query)
        record_count = 0

        for table in tables:
            for record in table.records:
                record_count += 1
                if record_count <= 5:  # Show first 5 in detail
                    print(f"\n[DATA] Record #{record_count}:")
                    print(f"   Time: {record.get_time()}")
                    print(f"   Measurement: {record.get_measurement()}")
                    print(f"   Field: {record.get_field()}")
                    print(f"   Value: {record.get_value()}")
                    print(f"   Tags: {record.values.get('deviceAddress', 'N/A')}")

        if record_count > 0:
            print(f"\n[OK] Found {record_count} record(s) in last 30 days")
        else:
            print("\n[FAIL] No data found in last 30 days")
            print("   The bucket might be empty or data is older than 30 days")
    except Exception as e:
        print(f"\n[FAIL] Failed to fetch sample data: {e}")

    # Test 3: Check for specific ECG measurement
    print("\n" + "="*70)
    print("  TEST 3: Check for 'ecg' Measurement")
    print("="*70)

    query = f'''
from(bucket: "{bucket}")
  |> range(start: -1d)
  |> filter(fn: (r) => r._field == "ecg")
  |> limit(n: 5)
'''

    try:
        tables = query_api.query(query)
        record_count = 0

        for table in tables:
            for record in table.records:
                record_count += 1
                print(f"\n[DATA] ECG Record #{record_count}:")
                print(f"   Time: {record.get_time()}")
                print(f"   Field: {record.get_field()}")
                print(f"   Value: {record.get_value()}")
                print(f"   All values: {record.values}")

        if record_count > 0:
            print(f"\n[OK] Found {record_count} 'ecg' record(s)")
        else:
            print("\n[FAIL] No 'ecg' measurement found")
            print("   Try checking the measurement names from TEST 1")
    except Exception as e:
        print(f"\n[FAIL] Failed to query ecg measurement: {e}")

    # Test 4: Check tags (e.g., deviceAddress, unique_key)
    print("\n" + "="*70)
    print("  TEST 4: List Unique Tags")
    print("="*70)

    # Check for deviceAddress tag
    query = f'''
import "influxdata/influxdb/schema"

schema.tagValues(
  bucket: "{bucket}",
  tag: "deviceAddress",
  start: -30d
)
'''

    try:
        tables = query_api.query(query)
        devices = []
        for table in tables:
            for record in table.records:
                device = record.get_value()
                devices.append(device)

        if devices:
            print(f"\n[OK] Found {len(devices)} device(s):")
            for d in devices[:10]:  # Show first 10
                print(f"   - {d}")
            if len(devices) > 10:
                print(f"   ... and {len(devices) - 10} more")
        else:
            print("\n[WARN] No 'deviceAddress' tag found")
    except Exception as e:
        print(f"\n[WARN] Could not check deviceAddress tag: {e}")

    # Check for unique_key tag (from record_linkage.py pattern)
    query = f'''
import "influxdata/influxdb/schema"

schema.tagValues(
  bucket: "{bucket}",
  tag: "unique_key",
  start: -30d
)
'''

    try:
        tables = query_api.query(query)
        keys = []
        for table in tables:
            for record in table.records:
                key = record.get_value()
                keys.append(key)

        if keys:
            print(f"\n[OK] Found {len(keys)} unique_key(s):")
            for k in keys[:5]:  # Show first 5
                print(f"   - {k}")
            if len(keys) > 5:
                print(f"   ... and {len(keys) - 5} more")
        else:
            print("\n[WARN] No 'unique_key' tag found")
    except Exception as e:
        print(f"\n[WARN] Could not check unique_key tag: {e}")

    # Test 5: Check time range of data
    print("\n" + "="*70)
    print("  TEST 5: Data Time Range")
    print("="*70)

    # Get oldest record
    query = f'''
from(bucket: "{bucket}")
  |> range(start: -365d)
  |> limit(n: 1)
  |> sort(columns: ["_time"])
'''

    try:
        tables = query_api.query(query)
        oldest_time = None
        for table in tables:
            for record in table.records:
                oldest_time = record.get_time()
                break

        if oldest_time:
            print(f"\n[DATE] Oldest record: {oldest_time}")
        else:
            print("\n[WARN] Could not find oldest record")
    except Exception as e:
        print(f"\n[WARN] Could not check oldest record: {e}")

    # Get newest record
    query = f'''
from(bucket: "{bucket}")
  |> range(start: -30d)
  |> limit(n: 1)
  |> sort(columns: ["_time"], desc: true)
'''

    try:
        tables = query_api.query(query)
        newest_time = None
        for table in tables:
            for record in table.records:
                newest_time = record.get_time()
                break

        if newest_time:
            print(f"[DATE] Newest record: {newest_time}")
            print(f"[DATE] Time since newest: {datetime.now(newest_time.tzinfo) - newest_time}")
        else:
            print("\n[WARN] Could not find newest record")
    except Exception as e:
        print(f"\n[WARN] Could not check newest record: {e}")

    # Summary
    print("\n" + "="*70)
    print("  RECOMMENDATIONS")
    print("="*70)
    print("\n[INFO] Based on the results above:")
    print("   1. Check TEST 1 for the actual measurement names")
    print("   2. Update INFLUX_MEASUREMENT in .env if 'ecg' is not correct")
    print("   3. Check TEST 5 for data time range - adjust query window if needed")
    print("   4. If no data found, verify devices are sending data to this bucket")
    print("\n" + "="*70)

    client.close()


if __name__ == '__main__':
    explore_bucket()
