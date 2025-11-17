"""
InfluxDB Connection Test Script

This script tests your InfluxDB connection and helps debug data fetching issues.
Run this before using the main anonymization service.

Usage:
    python test_influx_connection.py
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from data_fetcher.influx_fetcher import InfluxDataFetcher

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_1_load_config():
    """Test 1: Load configuration from .env"""
    print_section("TEST 1: Configuration Loading")

    config = {
        'url': os.getenv('INFLUX_URL'),
        'token': os.getenv('INFLUX_TOKEN'),
        'org': os.getenv('INFLUX_ORG'),
        'input_bucket': os.getenv('INFLUX_INPUT_BUCKET', 'raw_data'),
        'measurement_name': os.getenv('INFLUX_MEASUREMENT_NAME', 'SMART_DATA'),
        'field_name': os.getenv('INFLUX_FIELD_NAME', 'ecg'),
    }

    print("\n📋 Configuration loaded from .env:")
    print(f"   URL: {config['url']}")
    print(f"   Token: {'*' * 20 if config['token'] else 'NOT SET'}")
    print(f"   Org: {config['org']}")
    print(f"   Input Bucket: {config['input_bucket']}")
    print(f"   Measurement Name: {config['measurement_name']}")
    print(f"   Field Name: {config['field_name']}")

    # Validate
    missing = []
    if not config['url']:
        missing.append('INFLUX_URL')
    if not config['token']:
        missing.append('INFLUX_TOKEN')
    if not config['org']:
        missing.append('INFLUX_ORG')

    if missing:
        print(f"\n❌ FAILED: Missing configuration:")
        for key in missing:
            print(f"   - {key}")
        print("\n💡 Fix: Edit your .env file and set these values")
        return None

    print("\n✅ PASSED: All required configuration present")
    return config


def test_2_connection(config):
    """Test 2: Test InfluxDB connection"""
    print_section("TEST 2: InfluxDB Connection")

    try:
        print("\n🔗 Attempting to connect to InfluxDB...")
        fetcher = InfluxDataFetcher(
            url=config['url'],
            token=config['token'],
            org=config['org']
        )

        print("\n✅ PASSED: Connected to InfluxDB successfully")
        return fetcher

    except Exception as e:
        print(f"\n❌ FAILED: Could not connect to InfluxDB")
        print(f"   Error: {e}")
        print(f"\n💡 Troubleshooting:")
        print(f"   1. Check if InfluxDB is running: curl {config['url']}/health")
        print(f"   2. Verify INFLUX_URL is correct in .env")
        print(f"   3. Verify INFLUX_TOKEN is valid (check InfluxDB UI → Settings → Tokens)")
        print(f"   4. Verify INFLUX_ORG matches your organization (check InfluxDB UI → Settings → About)")
        return None


def test_3_list_buckets(fetcher):
    """Test 3: List available buckets"""
    print_section("TEST 3: List Buckets")

    try:
        print("\n📂 Fetching list of buckets...")
        buckets = fetcher.list_buckets()

        if buckets:
            print(f"\n✅ PASSED: Found {len(buckets)} bucket(s)")
            return buckets
        else:
            print("\n⚠️ WARNING: No buckets found")
            print("   This might indicate a permission issue with your token")
            return []

    except Exception as e:
        print(f"\n❌ FAILED: Could not list buckets")
        print(f"   Error: {e}")
        return []


def test_4_verify_bucket(fetcher, config, available_buckets):
    """Test 4: Verify input bucket exists"""
    print_section("TEST 4: Verify Input Bucket")

    bucket_name = config['input_bucket']
    print(f"\n🔍 Looking for bucket: '{bucket_name}'")

    if bucket_name in available_buckets:
        print(f"\n✅ PASSED: Bucket '{bucket_name}' exists")
        return True
    else:
        print(f"\n❌ FAILED: Bucket '{bucket_name}' not found")
        print(f"\n💡 Available buckets:")
        for bucket in available_buckets:
            print(f"   - {bucket}")
        print(f"\n💡 Fix: Update INFLUX_INPUT_BUCKET in .env to one of the available buckets")
        return False


def test_5_sample_query(fetcher, config):
    """Test 5: Try to fetch sample data"""
    print_section("TEST 5: Sample Data Query")

    print(f"\n🧪 Attempting to fetch last 5 records...")
    print(f"   Bucket: {config['input_bucket']}")
    print(f"   Measurement: {config['measurement_name']}")
    print(f"   Field: {config['field_name']}")
    print(f"   Time range: Last 7 days")

    try:
        records = fetcher.test_query(
            bucket=config['input_bucket'],
            measurement_name=config['measurement_name'],
            field_name=config['field_name'],
            limit=5
        )

        if records:
            print(f"\n✅ PASSED: Successfully fetched {len(records)} sample record(s)")
            return True
        else:
            print(f"\n❌ FAILED: Query returned 0 records")
            print(f"\n💡 Possible reasons:")
            print(f"   1. No data in bucket '{config['input_bucket']}'")
            print(f"   2. Wrong measurement name (current: '{config['measurement_name']}')")
            print(f"   3. Wrong field name (current: '{config['field_name']}')")
            print(f"   4. No data in last 7 days")
            print(f"\n💡 Next steps:")
            print(f"   1. Check if data exists in InfluxDB UI")
            print(f"   2. Update INFLUX_MEASUREMENT_NAME in .env (e.g., 'SMART_DATA')")
            print(f"   3. Update INFLUX_FIELD_NAME in .env (e.g., 'ecg')")
            print(f"   4. Verify devices are sending data to this bucket")
            return False

    except Exception as e:
        print(f"\n❌ FAILED: Query error")
        print(f"   Error: {e}")
        return False


def test_6_batch_query(fetcher, config):
    """Test 6: Try batch query (like the main service does)"""
    print_section("TEST 6: Batch Query (Main Service Method)")

    # Test with last 1 hour
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    print(f"\n🧪 Testing batch query method...")
    print(f"   Start: {start_time.isoformat()}")
    print(f"   End: {end_time.isoformat()}")

    try:
        records = fetcher.fetch_batch(
            bucket=config['input_bucket'],
            measurement_name=config['measurement_name'],
            field_name=config['field_name'],
            start_time=start_time,
            end_time=end_time
        )

        if records:
            print(f"\n✅ PASSED: Batch query returned {len(records)} records")
            print(f"\n📊 Sample record:")
            sample = records[0]
            for key, value in sample.items():
                print(f"   {key}: {value}")
            return True
        else:
            print(f"\n❌ FAILED: Batch query returned 0 records")
            print(f"\n💡 The main service will fail with the same issue")
            print(f"💡 Focus on fixing Tests 5 and 6 first")
            return False

    except Exception as e:
        print(f"\n❌ FAILED: Batch query error")
        print(f"   Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("  InfluxDB Connection Test Suite")
    print("  This will help diagnose data fetching issues")
    print("="*70)

    # Test 1: Load config
    config = test_1_load_config()
    if not config:
        print("\n⛔ Cannot continue without proper configuration")
        print("   Please fix your .env file and try again")
        sys.exit(1)

    # Test 2: Connection
    fetcher = test_2_connection(config)
    if not fetcher:
        print("\n⛔ Cannot continue without InfluxDB connection")
        sys.exit(1)

    # Test 3: List buckets
    buckets = test_3_list_buckets(fetcher)

    # Test 4: Verify bucket
    bucket_exists = test_4_verify_bucket(fetcher, config, buckets)
    if not bucket_exists:
        print("\n⚠️ Continuing with tests, but bucket issue needs to be fixed")

    # Test 5: Sample query
    sample_success = test_5_sample_query(fetcher, config)

    # Test 6: Batch query
    batch_success = test_6_batch_query(fetcher, config)

    # Summary
    print_section("TEST SUMMARY")

    results = {
        'Configuration': config is not None,
        'Connection': fetcher is not None,
        'Bucket Exists': bucket_exists,
        'Sample Query': sample_success,
        'Batch Query': batch_success,
    }

    print("\n📊 Test Results:")
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {test_name:<20} {status}")
        if not passed:
            all_passed = False

    print("\n" + "="*70)

    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("\nYour InfluxDB connection is working correctly.")
        print("The main anonymization service should work now.")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nPlease fix the failed tests before running the main service.")
        print("\nCommon fixes:")
        print("  1. Check .env file has correct InfluxDB credentials")
        print("  2. Verify InfluxDB is running and accessible")
        print("  3. Ensure bucket name matches exactly (case-sensitive)")
        print("  4. Verify measurement name is correct")
        print("  5. Check if there's actually data in the specified time range")

    print("="*70 + "\n")

    # Close connection
    fetcher.close()

    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
