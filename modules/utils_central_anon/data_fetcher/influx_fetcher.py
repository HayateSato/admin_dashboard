"""
InfluxDB Data Fetcher

Fetches raw ECG data from InfluxDB with detailed debugging and error handling.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional

try:
    from influxdb_client import InfluxDBClient
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False

logger = logging.getLogger(__name__)


class InfluxDataFetcher:
    """Fetches ECG data from InfluxDB with debugging support"""

    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        timeout: int = 30000
    ):
        """Initialize InfluxDB fetcher

        Args:
            url: InfluxDB URL
            token: Authentication token
            org: Organization name
            timeout: Query timeout in milliseconds
        """
        self.url = url
        self.token = token
        self.org = org
        self.timeout = timeout
        self.client = None

        if not INFLUX_AVAILABLE:
            raise RuntimeError("influxdb-client not installed. Run: pip install influxdb-client")

        self._connect()

    def _connect(self):
        """Establish connection to InfluxDB with detailed error reporting"""
        try:
            logger.info(f"[InfluxDB] Connecting to InfluxDB...")
            logger.info(f"   URL: {self.url}")
            logger.info(f"   Org: {self.org}")
            logger.info(f"   Timeout: {self.timeout}ms")

            self.client = InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org,
                timeout=self.timeout
            )

            # Test connection
            logger.info("[InfluxDB] Testing connection with ping...")
            ping_result = self.client.ping()
            logger.info(f"   Ping successful: {ping_result}")

            # Get health status
            health = self.client.health()
            logger.info(f"   Health check: {health.status}")

            logger.info(f"[InfluxDB] Connected to InfluxDB successfully")

        except Exception as e:
            logger.error(f"[InfluxDB] ERROR: Failed to connect to InfluxDB: {e}")
            logger.error(f"   URL: {self.url}")
            logger.error(f"   Org: {self.org}")
            logger.error(f"   Error type: {type(e).__name__}")
            raise

    # def test_connection(self) -> Dict:
    #     """Test connection and return status info

    #     Returns:
    #         Dictionary with connection status
    #     """
    #     try:
    #         ping = self.client.ping()
    #         health = self.client.health()

    #         return {
    #             'connected': True,
    #             'ping': ping,
    #             'health': health.status,
    #             'url': self.url,
    #             'org': self.org
    #         }
    #     except Exception as e:
    #         return {
    #             'connected': False,
    #             'error': str(e),
    #             'url': self.url,
    #             'org': self.org
    #         }

    # def list_buckets(self) -> List[str]:
    #     """List all available buckets

    #     Returns:
    #         List of bucket names
    #     """
    #     try:
    #         logger.info("📂 Listing available buckets...")
    #         buckets_api = self.client.buckets_api()
    #         buckets = buckets_api.find_buckets().buckets

    #         bucket_names = [bucket.name for bucket in buckets]
    #         logger.info(f"   Found {len(bucket_names)} buckets:")
    #         for name in bucket_names:
    #             logger.info(f"     - {name}")

    #         return bucket_names

    #     except Exception as e:
    #         logger.error(f"❌ Failed to list buckets: {e}")
    #         return []

#     def test_query(
#         self,
#         bucket: str,
#         measurement_name: str = "SMART_DATA",
#         field_name: str = "ecg",
#         limit: int = 5
#     ) -> List[Dict]:
#         """Test query to fetch a few records

#         Args:
#             bucket: Bucket name
#             measurement_name: Measurement name (e.g., "SMART_DATA")
#             field_name: Field name (e.g., "ecg")
#             limit: Number of records to fetch

#         Returns:
#             List of sample records
#         """
#         try:
#             logger.info(f"🧪 Testing query...")
#             logger.info(f"   Bucket: {bucket}")
#             logger.info(f"   Measurement: {measurement_name}")
#             logger.info(f"   Field: {field_name}")
#             logger.info(f"   Limit: {limit}")

#             # Simplified query matching working example from record_linkage.py
#             # Filter by both _measurement (table) AND _field (column)
#             query = f'''
# from(bucket: "{bucket}")
#   |> range(start: -1d)
#   |> filter(fn: (r) => r._measurement == "{measurement_name}")
#   |> filter(fn: (r) => r._field == "{field_name}")
#   |> limit(n: {limit})
#   |> sort(columns: ["_time"])
# '''

#             logger.debug(f"   Query:\n{query}")

#             query_api = self.client.query_api()
#             tables = query_api.query(query)

#             records = []
#             record_count = 0

#             for table in tables:
#                 logger.info(f"   📊 Table: {table}")
#                 for record in table.records:
#                     record_count += 1
#                     logger.info(f"      Record #{record_count}:")
#                     logger.info(f"        Time: {record.get_time()}")
#                     logger.info(f"        Field: {record.get_field()}")
#                     logger.info(f"        Value: {record.get_value()}")
#                     logger.info(f"        Tags: {record.values}")

#                     records.append({
#                         'time': record.get_time(),
#                         'field': record.get_field(),
#                         'value': record.get_value(),
#                         'tags': dict(record.values)
#                     })

#             logger.info(f"   ✅ Query returned {len(records)} records")
#             return records

#         except Exception as e:
#             logger.error(f"❌ Query failed: {e}")
#             logger.error(f"   Error type: {type(e).__name__}")
#             import traceback
#             logger.error(f"   Traceback:\n{traceback.format_exc()}")
#             return []

    def get_available_dates(
        self,
        bucket: str,
        unique_key: str,
        measurement_name: str = "SMART_DATA",
        field_name: str = "ecg"
    ) -> List[str]:
        """Get list of dates where data exists for a specific unique_key

        Args:
            bucket: InfluxDB bucket name
            unique_key: Patient's unique key
            measurement_name: Measurement name (default: "SMART_DATA")
            field_name: Field name (default: "ecg")

        Returns:
            List of date strings (YYYY-MM-DD) where data exists
        """
        if not self.client:
            raise RuntimeError("InfluxDB client not initialized")

        logger.info(f"[InfluxDB] Checking available dates for unique_key: {unique_key[:16]}...")
        logger.info(f"   Bucket: {bucket}")
        logger.info(f"   Measurement: {measurement_name}")

        query_api = self.client.query_api()

        # Query to get distinct dates for this unique_key
        # Using aggregateWindow to group by day instead of truncateTimeColumn
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

        logger.info(f"   Full unique_key being queried: {unique_key}")
        logger.info(f"   Unique key length: {len(unique_key)} characters")
        logger.debug(f"   Flux query:\n{query}")

        try:
            tables = query_api.query(query)

            dates = []
            for table in tables:
                for record in table.records:
                    # Try to get _time field
                    if '_time' in record.values:
                        timestamp = record.get_time()
                        date_str = timestamp.strftime('%Y-%m-%d')
                        if date_str not in dates:
                            dates.append(date_str)
                    else:
                        logger.warning(f"   WARNING: Record missing '_time' field: {record.values}")

            if len(dates) == 0:
                logger.warning(f"   WARNING: No dates found for unique_key: {unique_key[:16]}...")
                logger.warning(f"   This could mean:")
                logger.warning(f"     1. No data exists for this unique key in the last 90 days")
                logger.warning(f"     2. The bucket name is incorrect: {bucket}")
                logger.warning(f"     3. The measurement/field names are incorrect: {measurement_name}/{field_name}")
            else:
                logger.info(f"   Found {len(dates)} dates with data")

            return sorted(dates, reverse=True)  # Most recent first

        except KeyError as e:
            logger.error(f"[InfluxDB] ERROR: Query returned records without _time field: {e}")
            logger.warning(f"   This usually means the Flux query needs adjustment")
            logger.warning(f"   Returning empty list (no dates found)")
            return []
        except Exception as e:
            logger.error(f"[InfluxDB] ERROR: Failed to query available dates: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            # Return empty list instead of raising - let caller handle gracefully
            return []

    def fetch_batch(
        self,
        bucket: str,
        measurement_name: str,
        field_name: str,
        start_time: datetime,
        end_time: datetime,
        unique_key_filter: Optional[str] = None,
        max_records: int = 10000
    ) -> List[Dict]:
        """Fetch a batch of ECG data from InfluxDB

        Args:
            bucket: InfluxDB bucket name
            measurement_name: Measurement name (e.g., "SMART_DATA")
            field_name: Field name (e.g., "ecg")
            start_time: Start of time window
            end_time: End of time window
            unique_key_filter: Optional unique_key filter for specific user
            max_records: Maximum records to fetch

        Returns:
            List of dictionaries with ECG data (includes unique_key)
        """
        if not self.client:
            raise RuntimeError("InfluxDB client not initialized")

        logger.debug(f"[InfluxDB] Fetching batch from InfluxDB...")
        logger.debug(f"   Bucket: {bucket}")
        logger.debug(f"   Measurement: {measurement_name}")
        logger.debug(f"   Field: {field_name}")
        logger.debug(f"   Start: {start_time.isoformat()}")
        logger.debug(f"   End: {end_time.isoformat()}")
        logger.debug(f"   Unique key filter: {unique_key_filter or 'None'}")
        logger.debug(f"   Max records: {max_records}")

        query_api = self.client.query_api()

        # Build Flux query using simplified syntax (matching record_linkage.py approach)
        # Filter by both _measurement (table) AND _field (column)
        query = f'''
from(bucket: "{bucket}")
  |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
  |> filter(fn: (r) => r._measurement == "{measurement_name}")
  |> filter(fn: (r) => r._field == "{field_name}")
'''

        # Add unique_key filter if specified
        if unique_key_filter:
            query += f'''
  |> filter(fn: (r) => r.unique_key == "{unique_key_filter}")
'''

        # Add limit and sort
        query += f'''
  |> limit(n: {max_records})
  |> sort(columns: ["_time"])
'''

        logger.debug(f"   Flux query:\n{query}")

        try:
            tables = query_api.query(query)

            logger.debug(f"   Query executed, processing results...")
            logger.debug(f"   Number of tables: {len(tables) if tables else 0}")

            records = []
            field_count = {}

            for table_idx, table in enumerate(tables):
                logger.debug(f"   📊 Processing table {table_idx + 1}...")

                for record_idx, record in enumerate(table.records):
                    # Track which fields we're seeing
                    field_name = record.get_field()
                    field_count[field_name] = field_count.get(field_name, 0) + 1

                    # For ECG, we're looking for the "value" field or similar
                    # Log first few records to understand structure
                    if record_idx < 3:
                        logger.debug(f"      Record {record_idx + 1}:")
                        logger.debug(f"        Time: {record.get_time()}")
                        logger.debug(f"        Field: {record.get_field()}")
                        logger.debug(f"        Value: {record.get_value()}")
                        logger.debug(f"        Measurement: {record.get_measurement()}")
                        logger.debug(f"        All values: {record.values}")

                    # Extract timestamp and value
                    timestamp_ms = int(record.get_time().timestamp() * 1000)
                    ecg_value = record.get_value()

                    if ecg_value is None:
                        logger.debug(f"      ⚠️ Skipping record with None value")
                        continue

                    # Build record
                    data = {
                        'timestamp': timestamp_ms,
                        'ecg': int(ecg_value) if isinstance(ecg_value, (int, float)) else 0,
                        'unique_key': record.values.get('unique_key', 'unknown'),
                        'field': field_name,  # Include field name for debugging
                    }
                    records.append(data)

            logger.info(f"   Fetched {len(records)} records")
            if field_count:
                logger.info(f"   Fields found: {field_count}")

            # if len(records) == 0:
                # logger.warning("   ⚠️ No records returned from query!")
                # logger.warning("   Possible reasons:")
                # logger.warning("     1. No data in the time window")
                # logger.warning("     2. Wrong bucket name")
                # logger.warning("     3. Wrong measurement name")
                # logger.warning("     4. Device filter excluding all data")
                # logger.warning("   Try running test_query() to check data structure")

            return records

        except Exception as e:
            logger.error(f"[InfluxDB] ERROR: Failed to query InfluxDB: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            raise

    def close(self):
        """Close InfluxDB connection"""
        if self.client:
            self.client.close()
            logger.info("[InfluxDB] InfluxDB connection closed")
