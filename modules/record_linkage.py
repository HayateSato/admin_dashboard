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
        MUST match Flutter app implementation exactly!

        Flutter implementation: lib/src/privacy/bloom_filter.dart
        - Uses pipe-separated format: "givenname|familyname|dob|gender"
        - Applies 3 hash functions with seeds (0, 1, 2)
        - Creates 256-bit bloom filter
        - Converts to hex string

        Args:
            given_name: Patient's given name
            family_name: Patient's family name
            dob: Date of birth (YYYY-MM-DD format)
            gender: Gender (male/female/other)

        Returns:
            Hex-encoded bloom filter hash (64 hex chars)
        """
        # Normalize inputs (same as Flutter: trim + lowercase)
        normalized_given_name = given_name.strip().lower()
        normalized_family_name = family_name.strip().lower()
        normalized_gender = gender.strip().lower()
        normalized_dob = dob.strip()

        # Concatenate with pipe separator (MUST match Flutter format)
        user_data = f"{normalized_given_name}|{normalized_family_name}|{normalized_dob}|{normalized_gender}"

        # Generate bloom filter
        filter_size = 256  # bits
        num_hash_functions = 3
        bit_array = [False] * filter_size

        # Apply multiple hash functions with seeds
        for seed in range(num_hash_functions):
            hash_value = self._hash_function(user_data, seed)
            bit_position = hash_value % filter_size
            bit_array[bit_position] = True

        # Convert bit array to hex string
        unique_key = self._bit_array_to_hex(bit_array)

        logger.info(f"Generated unique_key for {given_name} {family_name}")

        return unique_key

    def _hash_function(self, input_str: str, seed: int) -> int:
        """
        Hash function with seed (matches Flutter implementation)

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

    def _bit_array_to_hex(self, bit_array: List[bool]) -> str:
        """
        Convert bit array to hexadecimal string (matches Flutter implementation)

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

            conn = psycopg2.connect(
                host=self.config.POSTGRES_HOST,
                port=self.config.POSTGRES_PORT,
                database=self.config.POSTGRES_DB,
                user=self.config.POSTGRES_USER,
                password=self.config.POSTGRES_PASSWORD
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
                return {
                    'unique_key': result[0],
                    'created_at': result[1].isoformat() if result[1] else None,
                    'last_session': result[2].isoformat() if result[2] else None,
                    'device_id': result[3],
                    'privacy_settings': result[4]
                }

            return None

        except ImportError:
            logger.warning("psycopg2 not installed, cannot query PostgreSQL")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch patient metadata: {e}")
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

            client = InfluxDBClient(
                url=self.config.INFLUX_URL,
                token=self.config.INFLUX_TOKEN,
                org=self.config.INFLUX_ORG
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

            time_range = f"start: {start_time if start_time else '-24h'}"
            if end_time:
                time_range += f", stop: {end_time}"

            # Query InfluxDB for sensor data
            query = f'''
                from(bucket: "{self.config.INFLUX_BUCKET_RAW}")
                    |> range({time_range})
                    |> filter(fn: (r) => r["unique_key"] == "{unique_key}")
                    |> limit(n: {limit})
            '''

            result = query_api.query(query)

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

            logger.info(f"Fetched {len(data_points)} sensor data points for {unique_key}")

            return data_points

        except ImportError:
            logger.warning("influxdb_client not installed, cannot query InfluxDB")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch sensor data: {e}")
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

            client = InfluxDBClient(
                url=self.config.INFLUX_URL,
                token=self.config.INFLUX_TOKEN,
                org=self.config.INFLUX_ORG
            )

            query_api = client.query_api()

            # Convert datetime-local format to RFC3339 if needed
            if start_time and 'T' in start_time:
                if not start_time.endswith('Z') and '+' not in start_time:
                    start_time = start_time + ':00Z'

            if end_time and 'T' in end_time:
                if not end_time.endswith('Z') and '+' not in end_time:
                    end_time = end_time + ':00Z'

            time_range = f"start: {start_time if start_time else '-24h'}"
            if end_time:
                time_range += f", stop: {end_time}"

            # Query anonymized bucket
            query = f'''
                from(bucket: "{self.config.INFLUX_BUCKET_ANON}")
                    |> range({time_range})
                    |> filter(fn: (r) => r["unique_key"] == "{unique_key}")
                    |> limit(n: {limit})
            '''

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

            logger.info(f"Fetched {len(data_points)} anonymized data points for {unique_key}")

            return data_points

        except ImportError:
            logger.warning("influxdb_client not installed")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch anonymized data: {e}")
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
