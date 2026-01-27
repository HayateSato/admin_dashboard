#!/usr/bin/env python3
"""
Test the exact query that get_available_dates() uses
"""
import os
from influxdb_client import InfluxDBClient

# InfluxDB connection
INFLUX_URL = os.getenv('INFLUX_URL', 'https://pu-influxdb.smarko-health.de/')
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN', '')
INFLUX_ORG = os.getenv('INFLUX_ORG', 'MCS Datalabs GmbH')
INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', 'raw-data')

# Test with the actual unique key
unique_key = "0000000000000000000000000000040040000000000000008000000000000000"
bucket = "raw-data"
measurement_name = "SMART_DATA"
field_name = "ecg"

print("=" * 80)
print("Testing get_available_dates() query")
print("=" * 80)
print(f"Unique Key: {unique_key}")
print(f"Bucket: {bucket}")
print(f"Measurement: {measurement_name}")
print(f"Field: {field_name}")
print("=" * 80)

# Connect
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=30000)
query_api = client.query_api()

# Build the exact query used in get_available_dates()
query = f'''
from(bucket: "{bucket}")
  |> range(start: -90d)
  |> filter(fn: (r) => r._measurement == "{measurement_name}")
  |> filter(fn: (r) => r._field == "{field_name}")
  |> filter(fn: (r) => r.unique_key == "{unique_key}")
  |> aggregateWindow(every: 1d, fn: count)
  |> filter(fn: (r) => r._value > 0)
  |> keep(columns: ["_time"])
  |> group()
  |> sort(columns: ["_time"], desc: true)
'''

print("\nQuery:")
print(query)
print("\n" + "=" * 80)

try:
    print("Executing query...")
    tables = query_api.query(query)

    print(f"Number of tables returned: {len(tables) if tables else 0}")

    if tables:
        for table_idx, table in enumerate(tables):
            print(f"\n📊 Table {table_idx + 1}:")
            print(f"   Columns: {[col.label for col in table.columns]}")
            print(f"   Records: {len(table.records)}")

            for record_idx, record in enumerate(table.records):
                print(f"\n   Record {record_idx + 1}:")
                print(f"      Time: {record.get_time()}")
                print(f"      Values: {record.values}")
    else:
        print("\n⚠️ No tables returned!")

    # Now test without aggregateWindow to see raw data
    print("\n" + "=" * 80)
    print("Testing simpler query WITHOUT aggregateWindow...")
    print("=" * 80)

    simple_query = f'''
from(bucket: "{bucket}")
  |> range(start: -90d)
  |> filter(fn: (r) => r._measurement == "{measurement_name}")
  |> filter(fn: (r) => r._field == "{field_name}")
  |> filter(fn: (r) => r.unique_key == "{unique_key}")
  |> limit(n: 10)
'''

    print("\nSimple Query:")
    print(simple_query)
    print()

    tables2 = query_api.query(simple_query)
    print(f"Number of tables returned: {len(tables2) if tables2 else 0}")

    if tables2:
        record_count = 0
        for table in tables2:
            for record in table.records:
                record_count += 1
                if record_count <= 3:
                    print(f"\n   Record {record_count}:")
                    print(f"      Time: {record.get_time()}")
                    print(f"      Field: {record.get_field()}")
                    print(f"      Value: {record.get_value()}")
                    print(f"      unique_key: {record.values.get('unique_key')}")
        print(f"\n   Total records found: {record_count}")

        if record_count > 0:
            print("\n✅ RAW DATA EXISTS! The issue is with aggregateWindow query.")
        else:
            print("\n❌ No ECG data found for this unique key in last 90 days")
    else:
        print("\n❌ No data returned even with simple query")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    print(traceback.format_exc())

print("\n" + "=" * 80)
print("Test complete!")
print("=" * 80)

client.close()
