"""
Record Linkage Module
Fetch patient data from InfluxDB and PostgreSQL by hashing personal identifiers
"""

import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class RecordLinkage:
    """Record Linkage for fetching patient data"""

    def __init__(self, config):
        self.config = config

    def generate_unique_key(self, given_name: str, family_name: str, dob: str, gender: str) -> str:
        """
        Generate unique_key using Bloom Filter with SHA256 hashing
        MUST match PHP privacyUmbrella implementation exactly!

        PHP implementation: privacyUmbrella_bloomfilter_f-pprl/bloomfilter.php
        - Uses field-specific seeds (vorname, nachname, geburtsdatum, geschlecht)
        - Global seed for additional entropy
        - Applies 25 hash functions per field
        - Creates 500-bit bloom filter
        - Converts to base64 string

        Args:
            given_name: Patient's given name
            family_name: Patient's family name
            dob: Date of birth (YYYY-MM-DD format)
            gender: Gender (male/female/other) - will be converted to m/f format

        Returns:
            Base64-encoded bloom filter hash
        """
        # Convert gender format: "male" -> "m", "female" -> "f"
        # This ensures compatibility with PHP partner implementation
        normalized_gender = gender.strip().lower()
        if normalized_gender in ['male', 'männlich', 'maennlich']:
            normalized_gender = 'm'
        elif normalized_gender in ['female', 'weiblich']:
            normalized_gender = 'f'
        # Keep other values as-is (already 'm', 'f', or 'other')

        # Normalize other inputs (trim + lowercase)
        normalized_given_name = given_name.strip().lower()
        normalized_family_name = family_name.strip().lower()
        normalized_dob = dob.strip()

        logger.info(f"[Bloom Filter] Generating unique key (PHP-compatible)")
        logger.info(f"   Given Name: '{normalized_given_name}'")
        logger.info(f"   Family Name: '{normalized_family_name}'")
        logger.info(f"   DOB: '{normalized_dob}'")
        logger.info(f"   Gender: '{normalized_gender}'")

        # Generate bloom filter with PHP-compatible algorithm
        filter_size = 500  # bits (m)
        num_hash_functions = 25  # k

        # Field-specific seeds (MUST match PHP and Dart implementations)
        field_seeds = {
            'vorname': 123124567,
            'nachname': 674532674,
            'geburtsdatum': 345386767,
            'geschlecht': 566744456,
        }
        global_seed = 567895675

        # Initialize bit array
        bit_array = [0] * filter_size

        # Create person map with German field names (matches PHP)
        person = {
            'vorname': normalized_given_name,
            'nachname': normalized_family_name,
            'geburtsdatum': normalized_dob,
            'geschlecht': normalized_gender,
        }

        # Process each field independently
        for field, value in person.items():
            if field not in field_seeds:
                continue

            field_seed = field_seeds[field]

            # Apply hash functions for this field
            for i in range(num_hash_functions):
                position = self._hash_function_php(value, global_seed, field_seed, i, filter_size)
                bit_array[position] = 1

        # Convert bit array to base64 string
        unique_key = self._bit_array_to_base64(bit_array)

        logger.info(f"Generated unique_key for {given_name} {family_name}: {unique_key[:20]}...")

        return unique_key

    def _hash_function_php(self, value: str, global_seed: int, field_seed: int, i: int, filter_size: int) -> int:
        """
        Hash function that matches PHP implementation exactly:
        hash('sha256', globalSeed + ':' + fieldSeed + ':' + i + ':' + value)

        Args:
            value: Field value to hash
            global_seed: Global seed for entire bloom filter
            field_seed: Field-specific seed
            i: Iteration number (0 to k-1)
            filter_size: Size of bloom filter (m)

        Returns:
            Bit position in bloom filter (0 to m-1)
        """
        # Construct data string exactly like PHP
        data = f"{global_seed}:{field_seed}:{i}:{value}"

        # SHA-256 hash
        hash_digest = hashlib.sha256(data.encode('utf-8')).hexdigest()

        # Take first 15 hex characters and convert to integer (matches PHP hexdec(substr($hash, 0, 15)))
        num = int(hash_digest[:15], 16)

        # Modulo to get position in bit array
        return num % filter_size

    def _hash_function(self, input_str: str, seed: int) -> int:
        """
        OLD hash function - kept for backward compatibility
        (This is the old Flutter implementation, not used anymore)

        Args:
            input_str: Input string to hash
            seed: Seed value for generating different hashes

        Returns:
            Integer hash value
        """
        # Create unique input by appending seed (same as Flutter)
        seed_input = f"{input_str}:{seed}"

        # Use SHA-256 for cryptographic hashing
        hash_bytes = hashlib.sha256(seed_input.encode('utf-8')).digest()

        # Convert first 4 bytes to unsigned 32-bit integer (same as Flutter)
        hash_value = int.from_bytes(hash_bytes[:4], byteorder='big', signed=False)

        return abs(hash_value)

    def _bit_array_to_base64(self, bit_array: List[int]) -> str:
        """
        Convert bit array to base64 string (matches PHP implementation)

        Args:
            bit_array: List of integers (0 or 1) representing bits

        Returns:
            Base64-encoded string
        """
        import base64

        # Convert bit array to bit string
        bit_string = ''.join(str(bit) for bit in bit_array)

        # Convert to bytes (8 bits per byte)
        bytes_list = []
        for i in range(0, len(bit_string), 8):
            # Get 8 bits (or remaining bits)
            byte_bits = bit_string[i:i+8]

            # Pad with zeros if necessary (matches PHP str_pad)
            if len(byte_bits) < 8:
                byte_bits = byte_bits.ljust(8, '0')

            # Convert to byte value
            byte_value = int(byte_bits, 2)
            bytes_list.append(byte_value)

        # Convert to bytes object and encode as base64
        bytes_obj = bytes(bytes_list)
        base64_str = base64.b64encode(bytes_obj).decode('ascii')

        return base64_str

    def _bit_array_to_hex(self, bit_array: List[bool]) -> str:
        """
        OLD conversion function - kept for backward compatibility
        Convert bit array to hexadecimal string (old Flutter implementation)

        Args:
            bit_array: List of boolean values representing bits

        Returns:
            Hex string (2 hex chars per byte)
        """
        bytes_list = []

        # Convert bits to bytes (8 bits per byte)
        for i in range(0, len(bit_array), 8):
            byte_value = 0
            for j in range(8):
                if i + j < len(bit_array) and bit_array[i + j]:
                    # Set bit from left (MSB to LSB)
                    byte_value |= (1 << (7 - j))
            bytes_list.append(byte_value)

        # Convert bytes to hex string (2 chars per byte, lowercase)
        hex_string = ''.join(f'{byte:02x}' for byte in bytes_list)

        return hex_string

    def fetch_patient_metadata(self, unique_key: str) -> Optional[Dict]:
        """
        Fetch patient metadata from PostgreSQL

        Args:
            unique_key: Hashed unique identifier

        Returns:
            Patient metadata dict or None
        """
        try:
            import psycopg2

            logger.info(f"Fetching metadata from PostgreSQL for unique_key: {unique_key[:16]}...")

            conn = psycopg2.connect(
                host=self.config.POSTGRES_HOST,
                port=self.config.POSTGRES_PORT,
                database=self.config.POSTGRES_DB,
                user=self.config.POSTGRES_USER,
                password=self.config.POSTGRES_PASSWORD,
                connect_timeout=10
            )

            cursor = conn.cursor()

            # Query for user metadata
            # Note: Adjust table/column names based on your actual schema
            query = """
                SELECT unique_key, created_at, last_session, device_id, privacy_settings
                FROM users
                WHERE unique_key = %s
            """

            cursor.execute(query, (unique_key,))
            result = cursor.fetchone()

            cursor.close()
            conn.close()

            if result:
                logger.info(f"   Metadata found in PostgreSQL for {unique_key[:16]}...")
                return {
                    'unique_key': result[0],
                    'created_at': result[1].isoformat() if result[1] else None,
                    'last_session': result[2].isoformat() if result[2] else None,
                    'device_id': result[3],
                    'privacy_settings': result[4]
                }
            else:
                logger.info(f"   No metadata found in PostgreSQL for {unique_key[:16]}...")

            return None

        except ImportError:
            logger.warning("psycopg2 not installed, cannot query PostgreSQL")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch patient metadata: {e}", exc_info=True)
            return None

    def fetch_patient_sensor_data(self, unique_key: str, start_time: Optional[str] = None,
                                  end_time: Optional[str] = None, limit: int = 1000) -> List[Dict]:
        """
        Fetch patient sensor data from InfluxDB

        Args:
            unique_key: Hashed unique identifier
            start_time: Start time (ISO format) - default: last 24 hours
            end_time: End time (ISO format) - default: now
            limit: Maximum number of records to return

        Returns:
            List of sensor data records
        """
        try:
            from influxdb_client import InfluxDBClient

            logger.info(f"Fetching raw sensor data for unique_key: {unique_key[:16]}...")

            client = InfluxDBClient(
                url=self.config.INFLUX_URL,
                token=self.config.INFLUX_TOKEN,
                org=self.config.INFLUX_ORG,
                timeout=60000  # 60 second timeout for data fetch
            )

            query_api = client.query_api()

            # Build time range query
            # Convert datetime-local format to RFC3339 if needed
            if start_time and 'T' in start_time:
                # Convert from datetime-local (YYYY-MM-DDTHH:MM) to RFC3339
                if not start_time.endswith('Z') and '+' not in start_time:
                    start_time = start_time + ':00Z'

            if end_time and 'T' in end_time:
                if not end_time.endswith('Z') and '+' not in end_time:
                    end_time = end_time + ':00Z'

            time_range = f"start: {start_time if start_time else '-365d'}"
            if end_time:
                time_range += f", stop: {end_time}"

            logger.info(f"   Time range: {time_range}")
            logger.info(f"   Bucket: {self.config.INFLUX_BUCKET_RAW}")

            # Query InfluxDB for sensor data - improved query to handle tag-based filtering
            # Filter only ECG data to reduce data volume
            query = f'''
                from(bucket: "{self.config.INFLUX_BUCKET_RAW}")
                    |> range({time_range})
                    |> filter(fn: (r) => r["unique_key"] == "{unique_key}")
                    |> filter(fn: (r) => r["_field"] == "ecg")
                    |> limit(n: {limit})
            '''

            logger.info(f"   Executing raw data query (limit: {limit})...")
            logger.info(f"   Query: {query}")
            result = query_api.query(query)
            logger.info(f"   Query execution completed, parsing results...")

            # Parse results
            data_points = []
            for table in result:
                for record in table.records:
                    data_points.append({
                        'timestamp': record.get_time().isoformat(),
                        'measurement': record.get_measurement(),
                        'field': record.get_field(),
                        'value': record.get_value(),
                        'unique_key': record.values.get('unique_key')
                    })

            client.close()

            logger.info(f"   Raw data query complete: Found {len(data_points)} data points")

            return data_points

        except ImportError:
            logger.warning("influxdb_client not installed, cannot query InfluxDB")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch sensor data: {e}", exc_info=True)
            return []

    def fetch_patient_anonymized_data(self, unique_key: str, start_time: Optional[str] = None,
                                      end_time: Optional[str] = None, limit: int = 1000) -> List[Dict]:
        """
        Fetch patient anonymized data from InfluxDB

        Args:
            unique_key: Hashed unique identifier
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            limit: Maximum number of records

        Returns:
            List of anonymized data records
        """
        try:
            from influxdb_client import InfluxDBClient

            logger.info(f"Fetching anonymized data for unique_key: {unique_key[:16]}...")

            client = InfluxDBClient(
                url=self.config.INFLUX_URL,
                token=self.config.INFLUX_TOKEN,
                org=self.config.INFLUX_ORG,
                timeout=60000  # 60 second timeout for data fetch
            )

            query_api = client.query_api()

            # Convert datetime-local format to RFC3339 if needed
            if start_time and 'T' in start_time:
                if not start_time.endswith('Z') and '+' not in start_time:
                    start_time = start_time + ':00Z'

            if end_time and 'T' in end_time:
                if not end_time.endswith('Z') and '+' not in end_time:
                    end_time = end_time + ':00Z'

            time_range = f"start: {start_time if start_time else '-365d'}"
            if end_time:
                time_range += f", stop: {end_time}"

            logger.info(f"   Time range: {time_range}")
            logger.info(f"   Bucket: {self.config.INFLUX_BUCKET_ANON}")

            # Query anonymized bucket
            # Filter only ECG data to reduce data volume
            query = f'''
                from(bucket: "{self.config.INFLUX_BUCKET_ANON}")
                    |> range({time_range})
                    |> filter(fn: (r) => r["unique_key"] == "{unique_key}")
                    |> filter(fn: (r) => r["_field"] == "ecg")
                    |> limit(n: {limit})
            '''

            logger.info(f"   Executing anonymized data query...")
            result = query_api.query(query)

            data_points = []
            for table in result:
                for record in table.records:
                    data_points.append({
                        'timestamp': record.get_time().isoformat(),
                        'measurement': record.get_measurement(),
                        'field': record.get_field(),
                        'value': record.get_value(),
                        'k_value': record.values.get('k_value'),
                        'time_window': record.values.get('time_window')
                    })

            client.close()

            logger.info(f"   Anonymized data query complete: Found {len(data_points)} data points")

            return data_points

        except ImportError:
            logger.warning("influxdb_client not installed")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch anonymized data: {e}", exc_info=True)
            return []

    def link_patient_data(self, given_name: str, family_name: str, dob: str, gender: str,
                         start_time: Optional[str] = None, end_time: Optional[str] = None,
                         include_raw: bool = True, include_anonymized: bool = True,
                         limit: int = 1000) -> Dict:
        """
        Complete record linkage: Generate unique_key and fetch all patient data

        Args:
            given_name: Patient's given name
            family_name: Patient's family name
            dob: Date of birth (YYYY-MM-DD)
            gender: Gender
            start_time: Start time for sensor data
            end_time: End time for sensor data
            include_raw: Include raw sensor data
            include_anonymized: Include anonymized sensor data
            limit: Max records per data source

        Returns:
            Complete patient data package
        """
        # Generate unique_key
        unique_key = self.generate_unique_key(given_name, family_name, dob, gender)

        # Fetch metadata
        metadata = self.fetch_patient_metadata(unique_key)

        # Fetch sensor data
        raw_data = []
        if include_raw:
            raw_data = self.fetch_patient_sensor_data(unique_key, start_time, end_time, limit)

        # Fetch anonymized data
        anonymized_data = []
        if include_anonymized:
            anonymized_data = self.fetch_patient_anonymized_data(unique_key, start_time, end_time, limit)

        # Compile complete record
        result = {
            'query_info': {
                'given_name': given_name,
                'family_name': family_name,
                'dob': dob,
                'gender': gender,
                'unique_key': unique_key,
                'timestamp': datetime.now().isoformat()
            },
            'metadata': metadata,
            'raw_sensor_data': {
                'count': len(raw_data),
                'data': raw_data
            },
            'anonymized_data': {
                'count': len(anonymized_data),
                'data': anonymized_data
            },
            'summary': {
                'metadata_found': metadata is not None,
                'raw_data_points': len(raw_data),
                'anonymized_data_points': len(anonymized_data),
                'total_data_points': len(raw_data) + len(anonymized_data)
            }
        }

        logger.info(f"Record linkage complete for {given_name} {family_name}: "
                   f"{result['summary']['total_data_points']} total data points")

        return result

    def count_recording_sessions(self, unique_key: str, start_time: Optional[str] = None,
                                 end_time: Optional[str] = None) -> Dict[str, int]:
        """
        Count unique recording sessions (not individual data points) in InfluxDB
        Uses session_id tag to count distinct recording sessions

        Args:
            unique_key: Hashed unique identifier
            start_time: Start time (ISO format)
            end_time: End time (ISO format)

        Returns:
            Dictionary with counts: {'raw_sessions': int, 'anonymized_sessions': int}
        """
        try:
            from influxdb_client import InfluxDBClient

            logger.info(f"Counting recording sessions for unique_key: {unique_key[:16]}...")

            client = InfluxDBClient(
                url=self.config.INFLUX_URL,
                token=self.config.INFLUX_TOKEN,
                org=self.config.INFLUX_ORG,
                timeout=30000
            )

            query_api = client.query_api()

            # Convert datetime-local format to RFC3339 if needed
            if start_time and 'T' in start_time:
                if not start_time.endswith('Z') and '+' not in start_time:
                    start_time = start_time + ':00Z'

            if end_time and 'T' in end_time:
                if not end_time.endswith('Z') and '+' not in end_time:
                    end_time = end_time + ':00Z'

            time_range = f"start: {start_time if start_time else '-365d'}"
            if end_time:
                time_range += f", stop: {end_time}"

            # Count unique raw data sessions using session_id tag
            # Use distinct() to count unique session_ids
            raw_count_query = f'''
                from(bucket: "{self.config.INFLUX_BUCKET_RAW}")
                    |> range({time_range})
                    |> filter(fn: (r) => r["unique_key"] == "{unique_key}")
                    |> filter(fn: (r) => r["_field"] == "ecg")
                    |> keep(columns: ["session_id"])
                    |> distinct(column: "session_id")
                    |> count()
            '''

            logger.info(f"   Counting unique raw recording sessions...")
            raw_result = query_api.query(raw_count_query)
            raw_sessions = 0
            for table in raw_result:
                for record in table.records:
                    raw_sessions += record.get_value()

            # Count unique anonymized data sessions
            anon_count_query = f'''
                from(bucket: "{self.config.INFLUX_BUCKET_ANON}")
                    |> range({time_range})
                    |> filter(fn: (r) => r["unique_key"] == "{unique_key}")
                    |> filter(fn: (r) => r["_field"] == "ecg")
                    |> keep(columns: ["session_id"])
                    |> distinct(column: "session_id")
                    |> count()
            '''

            logger.info(f"   Counting unique anonymized recording sessions...")
            anon_result = query_api.query(anon_count_query)
            anon_sessions = 0
            for table in anon_result:
                for record in table.records:
                    anon_sessions += record.get_value()

            client.close()

            logger.info(f"   Found {raw_sessions} raw sessions and {anon_sessions} anonymized sessions")

            return {
                'raw_count': raw_sessions,
                'anonymized_count': anon_sessions,
                'total_count': raw_sessions + anon_sessions
            }

        except Exception as e:
            logger.error(f"Failed to count recording sessions: {e}", exc_info=True)
            return {'raw_count': 0, 'anonymized_count': 0, 'total_count': 0}

    def link_patient_data_by_key(self, unique_key: str,
                                 start_time: Optional[str] = None, end_time: Optional[str] = None,
                                 include_raw: bool = True, include_anonymized: bool = True,
                                 limit: int = 1000, skip_count: bool = True) -> Dict:
        """
        Complete record linkage using unique_key directly

        Args:
            unique_key: Patient's unique key (64 hex characters)
            start_time: Start time for sensor data
            end_time: End time for sensor data
            include_raw: Include raw sensor data
            include_anonymized: Include anonymized sensor data
            limit: Max records per data source
            skip_count: Deprecated parameter (kept for compatibility)

        Returns:
            Complete patient data package with ECG data counts
        """
        logger.info(f"=== Starting Record Linkage for unique_key: {unique_key[:16]}... ===")
        logger.info(f"   Time range: {start_time or 'default'} to {end_time or 'now'}")
        logger.info(f"   Include raw: {include_raw}, Include anonymized: {include_anonymized}")
        logger.info(f"   Data limit: {limit} ECG points per source")

        # Fetch metadata
        logger.info("   Fetching metadata from PostgreSQL...")
        metadata = self.fetch_patient_metadata(unique_key)

        # Fetch sensor data
        raw_data = []
        if include_raw:
            logger.info("   Fetching raw sensor data from InfluxDB...")
            raw_data = self.fetch_patient_sensor_data(unique_key, start_time, end_time, limit)

        # Fetch anonymized data
        anonymized_data = []
        if include_anonymized:
            logger.info("   Fetching anonymized data from InfluxDB...")
            anonymized_data = self.fetch_patient_anonymized_data(unique_key, start_time, end_time, limit)

        # Compile complete record
        # Use actual fetched counts for display (simpler and more reliable)
        result = {
            'query_info': {
                'given_name': 'Unknown',
                'family_name': '(Searched by unique key)',
                'dob': 'N/A',
                'gender': 'N/A',
                'unique_key': unique_key,
                'timestamp': datetime.now().isoformat()
            },
            'metadata': metadata,
            'raw_sensor_data': {
                'count': len(raw_data),
                'data': raw_data
            },
            'anonymized_data': {
                'count': len(anonymized_data),
                'data': anonymized_data
            },
            'summary': {
                'metadata_found': metadata is not None,
                'raw_data_points': len(raw_data),
                'raw_data_total': len(raw_data),  # Show actual fetched count
                'anonymized_data_points': len(anonymized_data),
                'anonymized_data_total': len(anonymized_data),  # Show actual fetched count
                'total_data_points': len(raw_data) + len(anonymized_data),
                'total_data_in_db': len(raw_data) + len(anonymized_data)  # Show actual fetched count
            }
        }

        logger.info(f"=== Record linkage complete for unique_key {unique_key[:16]}... ===")
        logger.info(f"   Fetched: {result['summary']['total_data_points']} ECG data points")
        logger.info(f"   Raw: {len(raw_data)}, Anonymized: {len(anonymized_data)}")

        return result

    def export_to_csv(self, patient_data: Dict, output_path: str) -> str:
        """
        Export linked patient data to CSV file

        Args:
            patient_data: Patient data dict from link_patient_data()
            output_path: Output directory path

        Returns:
            Path to generated CSV file
        """
        import csv
        import os
        from pathlib import Path

        Path(output_path).mkdir(parents=True, exist_ok=True)

        # Generate filename
        query_info = patient_data['query_info']
        filename = f"patient_data_{query_info['given_name']}_{query_info['family_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(output_path, filename)

        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['Data Type', 'Timestamp', 'Measurement', 'Field', 'Value', 'K-Value', 'Time Window'])

            # Raw data
            for point in patient_data['raw_sensor_data']['data']:
                writer.writerow([
                    'Raw',
                    point['timestamp'],
                    point['measurement'],
                    point['field'],
                    point['value'],
                    '',
                    ''
                ])

            # Anonymized data
            for point in patient_data['anonymized_data']['data']:
                writer.writerow([
                    'Anonymized',
                    point['timestamp'],
                    point['measurement'],
                    point['field'],
                    point['value'],
                    point.get('k_value', ''),
                    point.get('time_window', '')
                ])

        logger.info(f"Exported patient data to {filepath}")

        return filepath

    def export_to_json(self, patient_data: Dict, output_path: str) -> str:
        """
        Export linked patient data to JSON file

        Args:
            patient_data: Patient data dict from link_patient_data()
            output_path: Output directory path

        Returns:
            Path to generated JSON file
        """
        import os
        from pathlib import Path

        Path(output_path).mkdir(parents=True, exist_ok=True)

        # Generate filename
        query_info = patient_data['query_info']
        filename = f"patient_data_{query_info['given_name']}_{query_info['family_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(output_path, filename)

        # Write JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(patient_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported patient data to {filepath}")

        return filepath
