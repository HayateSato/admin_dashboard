"""
Central ECG Anonymization Service

This script fetches raw ECG data from InfluxDB, applies level-by-level hierarchy-based
anonymization in configurable time batches, and outputs anonymized data.

Configuration: All settings are loaded from .env file
Run: python central_anonymizer.py (or use --streaming for continuous mode)
"""

import os
import sys
import csv
import logging
import time
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv, find_dotenv

# Try to find and load .env file (searches current dir and parent dirs)
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    # If find_dotenv fails, try explicit paths
    from pathlib import Path
    env_candidates = [Path('.env'), Path('../../.env')]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path)
            break

# Import anonymization modules (updated paths for new folder structure)
from anonymizer.level_hierarchy_anonymizer import LevelHierarchyEcgAnonymizer, EcgAnonymizationRecord
from anonymizer.mean_imputation import EcgMeanImputation

# Import data fetcher and validator
from data_fetcher import InfluxDataFetcher
from data_fetcher.ecg_validator import EcgValidator

# InfluxDB imports (for output only)
try:
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """Configuration loaded from .env file"""

    def __init__(self):
        # InfluxDB Configuration
        self.influx_url = os.getenv('INFLUX_URL', 'http://localhost:8086')
        self.influx_token = os.getenv('INFLUX_TOKEN', '')
        self.influx_org = os.getenv('INFLUX_ORG', '')
        self.influx_input_bucket = os.getenv('INFLUX_INPUT_BUCKET', 'raw_data')
        self.influx_output_bucket = os.getenv('INFLUX_OUTPUT_BUCKET', 'anonymized-data')
        # Note: In InfluxDB, measurement is the table (e.g., SMART_DATA), field is the column (e.g., ecg)
        self.influx_measurement_name = os.getenv('INFLUX_MEASUREMENT_NAME', 'SMART_DATA')
        self.influx_field_name = os.getenv('INFLUX_FIELD_NAME', 'ecg')

        # Anonymization Settings
        self.k_value = int(os.getenv('K_VALUE', '5'))
        self.batch_size_seconds = int(os.getenv('BATCH_SIZE_SECONDS', '5'))
        self.hierarchy_csv_path = os.getenv('HIERARCHY_CSV_PATH', 'anonymizer/smarko_hierarchy_ecg.csv')

        # Output Configuration
        self.output_to_csv = os.getenv('OUTPUT_TO_CSV', 'true').lower() == 'true'
        self.output_to_influx = os.getenv('OUTPUT_TO_INFLUX', 'true').lower() == 'true'
        self.output_to_api = os.getenv('OUTPUT_TO_API', 'false').lower() == 'true'
        self.csv_output_dir = os.getenv('CSV_OUTPUT_DIR', './output')
        self.csv_filename_pattern = os.getenv('CSV_FILENAME_PATTERN', 'kvalue_ecg_anonymized_%Y%m%d_%H%M%S.csv')
        self.api_endpoint = os.getenv('API_ENDPOINT', '')
        self.api_token = os.getenv('API_TOKEN', '')

        # Query Settings
        self.default_query_hours = int(os.getenv('DEFAULT_QUERY_HOURS', '1'))
        self.query_start_time = os.getenv('QUERY_START_TIME', '')  # ISO format: 2025-10-27T09:00:00
        self.query_end_time = os.getenv('QUERY_END_TIME', '')      # ISO format: 2025-10-27T12:00:00
        self.unique_key_filter = os.getenv('UNIQUE_KEY_FILTER', '')  # Optional: filter by specific user's unique_key

        # Processing Settings
        self.streaming_mode = os.getenv('STREAMING_MODE', 'false').lower() == 'true'
        self.streaming_interval = int(os.getenv('STREAMING_INTERVAL', '5'))
        self.max_records_per_query = int(os.getenv('MAX_RECORDS_PER_QUERY', '100000'))

        # Advanced Settings
        self.anonymization_enabled = os.getenv('ANONYMIZATION_ENABLED', 'true').lower() == 'true'
        self.influx_query_timeout = int(os.getenv('INFLUX_QUERY_TIMEOUT', '30'))
        self.influx_write_batch_size = int(os.getenv('INFLUX_WRITE_BATCH_SIZE', '1000'))
        self.verbose_logging = os.getenv('VERBOSE_LOGGING', 'true').lower() == 'true'

    def validate(self):
        """Validate configuration"""
        errors = []

        if not self.influx_url:
            errors.append("INFLUX_URL is required")
        if not self.influx_token:
            errors.append("INFLUX_TOKEN is required")
        if not self.influx_org:
            errors.append("INFLUX_ORG is required")
        if self.k_value < 2:
            errors.append("K_VALUE must be >= 2")
        if self.batch_size_seconds < 1:
            errors.append("BATCH_SIZE_SECONDS must be >= 1")

        if not any([self.output_to_csv, self.output_to_influx, self.output_to_api]):
            errors.append("At least one output destination must be enabled")

        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False

        return True

    def log_summary(self):
        """Log configuration summary"""
        logger.info("="*60)
        logger.info("Configuration Summary:")
        logger.info("="*60)
        logger.info(f"InfluxDB URL: {self.influx_url}")
        logger.info(f"Input Bucket: {self.influx_input_bucket}")
        logger.info(f"Output Bucket: {self.influx_output_bucket}")
        logger.info(f"K-Anonymity: k={self.k_value}")
        logger.info(f"Batch Size: {self.batch_size_seconds} seconds")
        logger.info(f"Output → CSV: {self.output_to_csv}")
        logger.info(f"Output → InfluxDB: {self.output_to_influx}")
        logger.info(f"Output → API: {self.output_to_api}")
        if self.output_to_csv:
            logger.info(f"CSV Directory: {self.csv_output_dir}")
        logger.info(f"Streaming Mode: {self.streaming_mode}")
        logger.info("="*60)


class CentralEcgAnonymizer:
    """Central ECG Anonymization Service"""

    def __init__(self, config: Config):
        """Initialize with configuration from .env file"""
        self.config = config
        self.influx_client = None  # For output only
        self.influx_fetcher = None  # For input
        self.last_processed_timestamp = None
        self.run_output_dir = None  # Timestamped directory for this run's CSV outputs

        # Initialize anonymizer and validator
        self.anonymizer = LevelHierarchyEcgAnonymizer(k_value=config.k_value)
        self.validator = EcgValidator()

        # Resolve hierarchy path
        hierarchy_path = Path(config.hierarchy_csv_path)
        if not hierarchy_path.is_absolute():
            # Relative to script directory
            script_dir = Path(__file__).parent
            hierarchy_path = script_dir / config.hierarchy_csv_path

        logger.info(f"[Central Anonymizer] Loading hierarchy from: {hierarchy_path}")
        self.anonymizer.initialize(str(hierarchy_path), enabled=config.anonymization_enabled)

        # Initialize InfluxDB fetcher (for input)
        if config.influx_url and config.influx_token:
            logger.info("[Central Anonymizer] Initializing InfluxDB data fetcher...")
            try:
                self.influx_fetcher = InfluxDataFetcher(
                    url=config.influx_url,
                    token=config.influx_token,
                    org=config.influx_org,
                    timeout=config.influx_query_timeout * 1000
                )
            except Exception as e:
                logger.error(f"[Central Anonymizer] ERROR: Failed to initialize data fetcher: {e}")
                raise
        else:
            logger.error("[Central Anonymizer] ERROR: InfluxDB configuration incomplete")
            raise RuntimeError("InfluxDB credentials required")

        # Initialize InfluxDB client for output (if needed)
        if config.output_to_influx and INFLUX_AVAILABLE:
            self._init_influx_output_client()

        # Create output directory if needed
        if config.output_to_csv:
            Path(config.csv_output_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"[Central Anonymizer] CSV output directory: {config.csv_output_dir}")

    def _init_influx_output_client(self):
        """Initialize InfluxDB client for output"""
        try:
            logger.info("[Central Anonymizer] Initializing InfluxDB output client...")
            self.influx_client = InfluxDBClient(
                url=self.config.influx_url,
                token=self.config.influx_token,
                org=self.config.influx_org,
                timeout=self.config.influx_query_timeout * 1000  # Convert to ms
            )
            # Test connection
            self.influx_client.ping()
            logger.info(f"[Central Anonymizer] InfluxDB output client ready")
        except Exception as e:
            logger.error(f"[Central Anonymizer] ERROR: Failed to connect InfluxDB output client: {e}")
            raise

    def fetch_batch_from_influx(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Fetch a single batch of ECG data from InfluxDB using the data fetcher

        Args:
            start_time: Start of batch time window
            end_time: End of batch time window

        Returns:
            List of dictionaries with ECG data
        """
        if not self.influx_fetcher:
            raise RuntimeError("InfluxDB fetcher not initialized")

        # Use the dedicated fetcher module
        return self.influx_fetcher.fetch_batch(
            bucket=self.config.influx_input_bucket,
            measurement_name=self.config.influx_measurement_name,
            field_name=self.config.influx_field_name,
            start_time=start_time,
            end_time=end_time,
            unique_key_filter=self.config.unique_key_filter,
            max_records=self.config.max_records_per_query
        )

    def anonymize_batch(self, raw_data: List[Dict]) -> List[Dict]:
        """Anonymize a batch of ECG data

        Args:
            raw_data: List of dictionaries with 'timestamp' and 'ecg' fields

        Returns:
            List of dictionaries with anonymized ECG data
            (includes both anonymized and non-anonymized records based on validation)
        """
        if not raw_data:
            return []

        if self.config.verbose_logging:
            logger.info(f"[Anonymizer] Processing batch: {len(raw_data)} records (K={self.config.k_value})")

        # Step 1: Validate data (apply ECG value checks and clamping)
        validated_data, validation_stats = self.validator.validate_and_filter(raw_data)

        # Step 2: Separate records that should/shouldn't be anonymized
        records_to_anonymize = [r for r in validated_data if r.get('should_anonymize', True)]
        records_to_skip = [r for r in validated_data if not r.get('should_anonymize', True)]

        if self.config.verbose_logging:
            logger.info(f"   Records to anonymize: {len(records_to_anonymize)}")
            logger.info(f"   Records to skip: {len(records_to_skip)}")

        result = []

        # Step 3: Anonymize records marked for anonymization
        if records_to_anonymize:
            # Convert to anonymization records
            anon_records = [
                EcgAnonymizationRecord(
                    timestamp=record['timestamp'],
                    original_ecg=record['ecg']
                )
                for record in records_to_anonymize
            ]

            # Anonymize
            anonymized_records = self.anonymizer.anonymize_batch(anon_records)

            # Collect all anonymized ranges for batch mean imputation
            anonymized_ranges = [anon_record.anonymized_range or "0"
                                for anon_record in anonymized_records]

            # Apply batch mean imputation (suppressed values get batch mean)
            imputation_result = EcgMeanImputation.apply_mean_imputation(anonymized_ranges)
            imputed_values = imputation_result['processed_values']
            batch_mean = imputation_result.get('batch_mean', 0.0)

            # Build result records with imputed values
            for i, anon_record in enumerate(anonymized_records):
                result_record = records_to_anonymize[i].copy()
                result_record['ecg_anonymized'] = imputed_values[i]
                result_record['ecg_original'] = result_record['ecg']
                result_record['ecg'] = imputed_values[i]  # Replace with anonymized value
                result_record['anonymized_range'] = anon_record.anonymized_range
                result_record['assigned_level'] = anon_record.assigned_level
                result_record['was_anonymized'] = True
                result_record['batch_mean'] = batch_mean  # Include batch mean for reference

                result.append(result_record)

        # Step 4: Add non-anonymized records (zero ECG, clamped, etc.)
        for record in records_to_skip:
            result_record = record.copy()
            result_record['ecg_anonymized'] = record['ecg']  # Keep original (or clamped) value
            result_record['ecg_original'] = record['ecg']
            result_record['anonymized_range'] = 'N/A'
            result_record['assigned_level'] = 0
            result_record['was_anonymized'] = False
            result_record['batch_mean'] = 0.0  # No batch mean for non-anonymized records
            result.append(result_record)

        if self.config.verbose_logging:
            logger.info(f"  [Anonymizer] Batch processing complete: {len(result)} total records")
            logger.info(f"     - Anonymized: {len(records_to_anonymize)}")
            logger.info(f"     - Kept as-is: {len(records_to_skip)}")

        return result

    def save_to_csv(self, data: List[Dict], batch_timestamp: datetime) -> None:
        """Save anonymized batch to CSV file

        Args:
            data: List of dictionaries with anonymized ECG data
            batch_timestamp: Timestamp for this batch (used in filename)
        """
        if not data:
            return

        # Use run-specific output directory
        if self.run_output_dir is None:
            # Fallback to base directory if run_output_dir not set
            output_dir = Path(self.config.csv_output_dir)
        else:
            output_dir = self.run_output_dir

        # Generate filename with K-value prefix and timestamp
        # Format: k5_ecg_anonymized_20251109_180600.csv
        timestamp_str = batch_timestamp.strftime('%Y%m%d_%H%M%S')
        filename = f"k{self.config.k_value}_ecg_anonymized_{timestamp_str}.csv"
        output_path = output_dir / filename

        logger.info(f"[CSV] Saving {len(data)} records to CSV: {output_path}")

        # Get all unique keys
        fieldnames = set()
        for record in data:
            fieldnames.update(record.keys())
        fieldnames = sorted(list(fieldnames))

        try:
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            logger.info(f"  [CSV] CSV saved: {output_path}")

        except Exception as e:
            logger.error(f"[CSV] ERROR: Failed to save CSV: {e}")
            raise

    def push_to_influx(self, data: List[Dict]) -> None:
        """Push anonymized batch to InfluxDB

        Args:
            data: List of dictionaries with anonymized ECG data
        """
        if not data or not self.influx_client:
            return

        logger.info(f"[InfluxDB] Pushing {len(data)} records to InfluxDB: {self.config.influx_output_bucket}")

        try:
            write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

            # Write in batches
            batch_size = self.config.influx_write_batch_size
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                points = []

                for record in batch:
                    point = Point(self.config.influx_field_name + "_anonymized") \
                        .time(datetime.fromtimestamp(record['timestamp'] / 1000)) \
                        .field("ecg", record['ecg']) \
                        .field("ecg_anonymized", record.get('ecg_anonymized', 0)) \
                        .field("ecg_original", record.get('ecg_original', 0)) \
                        .field("assigned_level", record.get('assigned_level', 0)) \
                        .field("batch_mean", record.get('batch_mean', 0.0)) \
                        .field("was_anonymized", record.get('was_anonymized', False)) \
                        .field("should_anonymize", record.get('should_anonymize', True)) \
                        .tag("unique_key", record.get('unique_key', 'unknown')) \
                        .tag("anonymized_range", record.get('anonymized_range', '*')) \
                        .tag("field", record.get('field', 'ecg'))

                    points.append(point)

                write_api.write(bucket=self.config.influx_output_bucket, record=points)

            logger.info(f"  [InfluxDB] Successfully pushed {len(data)} points to InfluxDB")

        except Exception as e:
            logger.error(f"[InfluxDB] ERROR: Failed to push to InfluxDB: {e}")
            raise

    def send_to_api(self, data: List[Dict]) -> None:
        """Send anonymized batch to API endpoint

        Args:
            data: List of dictionaries with anonymized ECG data
        """
        if not data or not self.config.api_endpoint:
            return

        import requests

        logger.info(f"[API] Sending {len(data)} records to API: {self.config.api_endpoint}")

        headers = {'Content-Type': 'application/json'}
        if self.config.api_token:
            headers['Authorization'] = f'Bearer {self.config.api_token}'

        try:
            response = requests.post(
                self.config.api_endpoint,
                json={'data': data, 'batch_size_seconds': self.config.batch_size_seconds},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            logger.info(f"  [API] API response: {response.status_code}")

        except Exception as e:
            logger.error(f"[API] ERROR: Failed to send to API: {e}")
            raise

    def _create_run_output_directory(self, start_time: datetime) -> Path:
        """Create a timestamped output directory for this run

        Args:
            start_time: The start time of the query window (used for directory name)

        Returns:
            Path to the created directory
        """
        # Format: YYYYMMDD_HHMM (based on query start time)
        dir_name = start_time.strftime("%Y%m%d_%H%M")
        run_dir = Path(self.config.csv_output_dir) / dir_name

        # Create the directory
        run_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[Central Anonymizer] Created run output directory: {run_dir}")

        return run_dir

    def process_time_window(
        self,
        start_time: datetime,
        end_time: datetime,
        max_records_limit: Optional[int] = None
    ) -> int:
        """Process data in batches within a time window

        Args:
            start_time: Start of overall time window
            end_time: End of overall time window
            max_records_limit: Optional maximum total records to process (for testing)

        Returns:
            Total number of records processed
        """
        logger.info(f"[Central Anonymizer] Processing time window: {start_time.isoformat()} to {end_time.isoformat()}")
        logger.info(f"   Batch size: {self.config.batch_size_seconds} seconds")
        if max_records_limit:
            logger.info(f"   [TESTING MODE] Will stop at {max_records_limit:,} records")

        # Create timestamped output directory for this run
        if self.config.output_to_csv:
            self.run_output_dir = self._create_run_output_directory(start_time)

        total_processed = 0
        batch_start = start_time

        while batch_start < end_time:
            # Check if we've reached the max records limit
            if max_records_limit and total_processed >= max_records_limit:
                logger.info(f"\n[TESTING MODE] Stopped processing - reached max records limit ({max_records_limit:,})")
                logger.info(f"   Total processed so far: {total_processed:,}")
                break

            batch_end = batch_start + timedelta(seconds=self.config.batch_size_seconds)
            if batch_end > end_time:
                batch_end = end_time

            logger.info(f"\n[Batch] Processing batch: {batch_start.strftime('%H:%M:%S')} - {batch_end.strftime('%H:%M:%S')}")
            if max_records_limit:
                remaining = max_records_limit - total_processed
                logger.info(f"   [TESTING MODE] Records remaining: {remaining:,}")

            try:
                # Fetch batch
                raw_data = self.fetch_batch_from_influx(batch_start, batch_end)

                if not raw_data:
                    # logger.info("   ⏭️  No data in this batch, skipping...")
                    batch_start = batch_end
                    continue

                # Anonymize batch
                anonymized_data = self.anonymize_batch(raw_data)

                # If adding this batch would exceed limit, only process up to limit
                if max_records_limit and (total_processed + len(anonymized_data) > max_records_limit):
                    records_to_take = max_records_limit - total_processed
                    logger.info(f"   [TESTING MODE] Trimming batch to {records_to_take} records (would exceed limit)")
                    anonymized_data = anonymized_data[:records_to_take]

                # Output to selected destinations
                if self.config.output_to_csv:
                    self.save_to_csv(anonymized_data, batch_start)

                if self.config.output_to_influx:
                    self.push_to_influx(anonymized_data)

                if self.config.output_to_api:
                    self.send_to_api(anonymized_data)

                total_processed += len(anonymized_data)
                self.last_processed_timestamp = batch_end

                # Stop if we've reached the limit
                if max_records_limit and total_processed >= max_records_limit:
                    logger.info(f"   [TESTING MODE] Reached max records limit: {total_processed:,}/{max_records_limit:,}")
                    break

            except Exception as e:
                logger.error(f"[Batch] ERROR: Error processing batch: {e}")
                # Continue with next batch instead of failing completely

            batch_start = batch_end

        # Final summary with clear record count
        logger.info(f"\n" + "="*60)
        logger.info(f"TIME WINDOW PROCESSING COMPLETE")
        logger.info(f"="*60)
        logger.info(f"Total records processed: {total_processed}")
        if max_records_limit and total_processed >= max_records_limit:
            logger.info(f"[TESTING MODE] Stopped at max records limit: {max_records_limit:,}")
        logger.info(f"="*60)
        return total_processed

    def run_streaming_mode(self):
        """Run in continuous streaming mode"""
        logger.info("[Streaming] Starting streaming mode (continuous processing)...")
        logger.info(f"   Checking for new data every {self.config.streaming_interval} seconds")
        logger.info("   Press Ctrl+C to stop")

        # Start from current time
        if not self.last_processed_timestamp:
            self.last_processed_timestamp = datetime.utcnow()

        try:
            while True:
                # Calculate next batch window
                batch_start = self.last_processed_timestamp
                batch_end = batch_start + timedelta(seconds=self.config.batch_size_seconds)
                current_time = datetime.utcnow()

                # Only process if batch is complete
                if batch_end <= current_time:
                    logger.info(f"\n📦 Processing new batch...")
                    self.process_time_window(batch_start, batch_end, k_value=self.config.k_value)
                else:
                    logger.debug(f"⏳ Waiting for batch to complete (next at {batch_end.isoformat()})")

                # Sleep until next check
                time.sleep(self.config.streaming_interval)

        except KeyboardInterrupt:
            logger.info("\n[Streaming] Streaming mode stopped by user")
        except Exception as e:
            logger.error(f"[Streaming] ERROR: Streaming mode error: {e}")
            raise

    def close(self):
        """Clean up resources"""
        if self.influx_fetcher:
            self.influx_fetcher.close()
        if self.influx_client:
            self.influx_client.close()
            logger.info("[Central Anonymizer] InfluxDB connections closed")


def parse_datetime(datetime_str: str) -> Optional[datetime]:
    """Parse datetime string in ISO format

    Args:
        datetime_str: Datetime string in ISO format (e.g., "2025-10-27T09:00:00")

    Returns:
        Parsed datetime object or None if invalid
    """
    if not datetime_str:
        return None

    try:
        # Try parsing with timezone info first
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            # Try without timezone
            return datetime.fromisoformat(datetime_str)
        except ValueError as e:
            logger.error(f"[Parser] ERROR: Invalid datetime format: {datetime_str}")
            logger.error(f"   Expected format: YYYY-MM-DDTHH:MM:SS (e.g., 2025-10-27T09:00:00)")
            logger.error(f"   Error: {e}")
            return None


def main():
    """Main entry point"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Central ECG Anonymization Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default settings from .env
  python central_anonymizer.py

  # Specify custom time window
  python central_anonymizer.py --start-time 2025-10-27T09:00:00 --end-time 2025-10-27T12:00:00

  # Process last 24 hours
  python central_anonymizer.py --hours 24

  # Enable streaming mode
  python central_anonymizer.py --streaming
        """
    )

    parser.add_argument(
        '--start-time',
        type=str,
        help='Query start time in ISO format (e.g., 2025-10-27T09:00:00). Overrides .env QUERY_START_TIME.'
    )

    parser.add_argument(
        '--end-time',
        type=str,
        help='Query end time in ISO format (e.g., 2025-10-27T12:00:00). Overrides .env QUERY_END_TIME.'
    )

    parser.add_argument(
        '--hours',
        type=int,
        help='Number of hours to query from current time (e.g., --hours 24). Overrides DEFAULT_QUERY_HOURS.'
    )

    parser.add_argument(
        '--streaming',
        action='store_true',
        help='Enable streaming mode (continuous processing)'
    )

    parser.add_argument(
        '--k-value',
        type=int,
        help='K-anonymity value (e.g., 5). Overrides .env K_VALUE.'
    )

    parser.add_argument(
        '--time-window',
        type=int,
        help='Time window for batching in seconds (e.g., 30). Overrides .env BATCH_SIZE_SECONDS.'
    )

    parser.add_argument(
        '--unique-key',
        type=str,
        help='Filter data for specific unique key. Overrides .env UNIQUE_KEY_FILTER.'
    )

    parser.add_argument(
        '--output-format',
        type=str,
        choices=['csv', 'influx', 'api'],
        help='Output format: csv, influx, or api'
    )

    parser.add_argument(
        '--max-records',
        type=int,
        help='Maximum total records to process (for testing). Stops processing when limit reached.'
    )

    args = parser.parse_args()

    logger.info("[Central Anonymizer] Central ECG Anonymization Service")
    logger.info("="*60)

    # Check for .env file (search current dir and parent directories)
    # Note: In Docker, environment variables are passed directly, so .env file is optional
    env_path = Path('.env')
    env_file_found = False
    if not env_path.exists():
        # Try parent directory (for when script is run from modules/utils_central_anon)
        env_path = Path('../../.env')
        if not env_path.exists():
            logger.warning("[Config] WARNING: .env file not found")
            logger.warning("   Searched in:")
            logger.warning("     - Current directory")
            logger.warning("     - ../../ (admin dashboard root)")
            logger.info("   Continuing with environment variables passed from parent process")
            env_file_found = False
        else:
            logger.info(f"   Using .env from: {env_path.resolve()}")
            env_file_found = True
    else:
        logger.info(f"   Using .env from: {env_path.resolve()}")
        env_file_found = True

    # Load configuration from .env
    config = Config()

    # Override config values with CLI arguments (if provided)
    if args.streaming:
        config.streaming_mode = True
        logger.info("   CLI override: streaming mode enabled")

    if args.k_value is not None:
        config.k_value = args.k_value
        logger.info(f"   CLI override: K-value = {args.k_value}")

    if args.time_window is not None:
        config.batch_size_seconds = args.time_window
        logger.info(f"   CLI override: Time window = {args.time_window}s")

    if args.unique_key:
        config.unique_key_filter = args.unique_key
        logger.info(f"   CLI override: Unique key filter = {args.unique_key[:16]}...")

    if args.output_format:
        # Set output flags based on format
        config.output_to_csv = (args.output_format == 'csv')
        config.output_to_influx = (args.output_format == 'influx')
        config.output_to_api = (args.output_format == 'api')
        logger.info(f"   CLI override: Output format = {args.output_format}")

    # Store max_records limit for testing
    max_records_limit = args.max_records if args.max_records else None
    if max_records_limit:
        logger.info(f"   [TESTING MODE] Max records limit: {max_records_limit:,}")

    # Validate configuration
    if not config.validate():
        logger.error("❌ Configuration validation failed. Please check your .env file")
        sys.exit(1)

    # Log configuration summary
    config.log_summary()

    # Check InfluxDB availability
    if not INFLUX_AVAILABLE:
        logger.error("[Config] ERROR: InfluxDB client not installed")
        logger.error("   Install with: pip install influxdb-client")
        sys.exit(1)

    # Initialize service
    try:
        anonymizer = CentralEcgAnonymizer(config)
    except Exception as e:
        logger.error(f"[Config] ERROR: Failed to initialize service: {e}")
        sys.exit(1)

    try:
        if config.streaming_mode:
            # Continuous streaming mode
            logger.info("🔄 Streaming mode enabled")
            anonymizer.run_streaming_mode()
        else:
            # One-time processing mode
            logger.info("📊 One-time processing mode")

            # Determine time window (priority: CLI args > .env > default)
            start_time = None
            end_time = None

            # 1. Check CLI arguments
            if args.start_time:
                start_time = parse_datetime(args.start_time)
                if start_time is None:
                    sys.exit(1)
                logger.info(f"   Using CLI start time: {start_time.isoformat()}")

            if args.end_time:
                end_time = parse_datetime(args.end_time)
                if end_time is None:
                    sys.exit(1)
                logger.info(f"   Using CLI end time: {end_time.isoformat()}")

            # 2. Check .env configuration
            if start_time is None and config.query_start_time:
                start_time = parse_datetime(config.query_start_time)
                if start_time is None:
                    sys.exit(1)
                logger.info(f"   Using .env start time: {start_time.isoformat()}")

            if end_time is None and config.query_end_time:
                end_time = parse_datetime(config.query_end_time)
                if end_time is None:
                    sys.exit(1)
                logger.info(f"   Using .env end time: {end_time.isoformat()}")

            # 3. Use default calculation (relative to current time)
            if end_time is None:
                end_time = datetime.utcnow()
                logger.info(f"   Using current time as end: {end_time.isoformat()}")

            if start_time is None:
                # Use hours from CLI or config
                hours = args.hours if args.hours else config.default_query_hours
                start_time = end_time - timedelta(hours=hours)
                logger.info(f"   Calculating start time: {hours} hours before end = {start_time.isoformat()}")

            # Validate time window
            if start_time >= end_time:
                logger.error("[Config] ERROR: Invalid time window: start_time must be before end_time")
                logger.error(f"   Start: {start_time.isoformat()}")
                logger.error(f"   End: {end_time.isoformat()}")
                sys.exit(1)

            logger.info(f"\n[Central Anonymizer] Time window: {start_time.isoformat()} to {end_time.isoformat()}")
            duration = end_time - start_time
            logger.info(f"   Duration: {duration.total_seconds() / 3600:.2f} hours")

            # Process the time window in batches
            total_records = anonymizer.process_time_window(start_time, end_time, max_records_limit=max_records_limit)

            # Final summary
            logger.info("\n" + "="*60)
            logger.info("CENTRAL ANONYMIZATION COMPLETED")
            logger.info("="*60)
            logger.info(f"Total records processed: {total_records}")
            if max_records_limit and total_records >= max_records_limit:
                logger.info(f"[TESTING MODE] Stopped at limit: {max_records_limit:,}")
            logger.info("="*60)

    except Exception as e:
        logger.error(f"\n[Central Anonymizer] ERROR: Service failed: {e}")
        sys.exit(1)

    finally:
        anonymizer.close()


if __name__ == '__main__':
    main()
