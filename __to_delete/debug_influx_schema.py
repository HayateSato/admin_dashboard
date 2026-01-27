#!/usr/bin/env python3
"""
Debug script to check InfluxDB schema (measurements, fields, tags)
"""
import os
from influxdb_client import InfluxDBClient

# InfluxDB connection from environment or defaults
INFLUX_URL = os.getenv('INFLUX_URL', 'https://pu-influxdb.smarko-health.de/')
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN', '')
INFLUX_ORG = os.getenv('INFLUX_ORG', 'MCS Datalabs GmbH')
INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', 'raw-data')

print("=" * 80)
print("InfluxDB Schema Debug Script")
print("=" * 80)
print(f"URL: {INFLUX_URL}")
print(f"Org: {INFLUX_ORG}")
print(f"Bucket: {INFLUX_BUCKET}")
print("=" * 80)

# Connect to InfluxDB
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=30000)
query_api = client.query_api()

print("\n1. Checking measurements in bucket...")
query_measurements = f'''
import "influxdata/influxdb/schema"
schema.measurements(bucket: "{INFLUX_BUCKET}")
'''

try:
    tables = query_api.query(query_measurements)
    measurements = []
    for table in tables:
        for record in table.records:
            measurement = record.get_value()
            if measurement:
                measurements.append(measurement)

    print(f"   Found {len(measurements)} measurement(s):")
    for m in measurements:
        print(f"   - {m}")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n2. Checking fields in measurement 'SMART_DATA'...")
query_fields = f'''
import "influxdata/influxdb/schema"
schema.measurementFieldKeys(
  bucket: "{INFLUX_BUCKET}",
  measurement: "SMART_DATA"
)
'''

try:
    tables = query_api.query(query_fields)
    fields = []
    for table in tables:
        for record in table.records:
            field = record.get_value()
            if field:
                fields.append(field)

    print(f"   Found {len(fields)} field(s):")
    for f in fields:
        print(f"   - {f}")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n3. Checking tags in measurement 'SMART_DATA'...")
query_tags = f'''
import "influxdata/influxdb/schema"
schema.measurementTagKeys(
  bucket: "{INFLUX_BUCKET}",
  measurement: "SMART_DATA"
)
'''

try:
    tables = query_api.query(query_tags)
    tags = []
    for table in tables:
        for record in table.records:
            tag = record.get_value()
            if tag:
                tags.append(tag)

    print(f"   Found {len(tags)} tag(s):")
    for t in tags:
        print(f"   - {t}")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n4. Checking sample data with unique_key...")
query_sample = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -90d)
  |> filter(fn: (r) => r._measurement == "SMART_DATA")
  |> limit(n: 1)
'''

try:
    tables = query_api.query(query_sample)
    print("   Sample record:")
    for table in tables:
        for record in table.records:
            print(f"   - Measurement: {record.get_measurement()}")
            print(f"   - Field: {record.get_field()}")
            print(f"   - Time: {record.get_time()}")
            print(f"   - Value: {record.get_value()}")
            print(f"   - Tags: {record.values}")
            if 'unique_key' in record.values:
                print(f"   - unique_key: {record.values['unique_key']}")
            break
        break
except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "=" * 80)
print("Debug complete!")
print("=" * 80)

client.close()
