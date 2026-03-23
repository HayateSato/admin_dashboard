"""
Check what fields exist in SMART_DATA measurement
"""

import os
import sys
from dotenv import load_dotenv

# Set UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

from influxdb_client import InfluxDBClient

url = os.getenv('INFLUX_URL')
token = os.getenv('INFLUX_TOKEN')
org = os.getenv('INFLUX_ORG')
bucket = os.getenv('INFLUX_INPUT_BUCKET', 'raw-data')

client = InfluxDBClient(url=url, token=token, org=org)
query_api = client.query_api()

print("="*70)
print("  Checking Fields in SMART_DATA Measurement")
print("="*70)

# Query to get field keys
query = f'''
import "influxdata/influxdb/schema"

schema.fieldKeys(
  bucket: "{bucket}",
  predicate: (r) => r._measurement == "SMART_DATA",
  start: -30d
)
'''

try:
    tables = query_api.query(query)
    fields = []
    for table in tables:
        for record in table.records:
            field_name = record.get_value()
            fields.append(field_name)

    print(f"\n[OK] Found {len(fields)} field(s) in SMART_DATA measurement:")
    for f in sorted(fields):
        print(f"   - {f}")

    print("\n[INFO] Check if 'ecg' or 'value' is in the list above")

except Exception as e:
    print(f"\n[FAIL] Failed to get fields: {e}")

# Also check a sample record with all fields
print("\n" + "="*70)
print("  Sample Record with All Fields")
print("="*70)

query = f'''
from(bucket: "{bucket}")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "SMART_DATA")
  |> limit(n: 1)
'''

try:
    tables = query_api.query(query)
    for table in tables:
        for record in table.records:
            print(f"\n[DATA] Sample record:")
            print(f"   Time: {record.get_time()}")
            print(f"   Measurement: {record.get_measurement()}")
            print(f"   Field: {record.get_field()}")
            print(f"   Value: {record.get_value()}")
            print(f"\n   All attributes:")
            for key, value in record.values.items():
                print(f"      {key}: {value}")
            break
        break

except Exception as e:
    print(f"\n[FAIL] Failed to get sample: {e}")

client.close()
