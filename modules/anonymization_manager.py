"""
Anonymization Configuration and Job Management Module
Integrates with central_anonymizer.py
"""

import logging
import subprocess
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# ============================================================================
# PERFORMANCE TRACKING CONFIGURATION
# Set to True to enable performance metrics logging to file
# ============================================================================
ENABLE_PERFORMANCE_TRACKING = False
PERFORMANCE_LOG_FILE = "logs/central_anonymization_performance.txt"
# ============================================================================

# ============================================================================
# TESTING CONFIGURATION - RECORD LIMIT
# Set MAX_RECORDS_FOR_TESTING to a positive number to limit total records processed
# Useful for testing with smaller datasets (e.g., 10000, 50000, 100000, 500000)
# Set to None or 0 for unlimited (production mode)
# This limits the total cumulative records across all batches
# ============================================================================
MAX_RECORDS_FOR_TESTING = None  # Change to e.g., 10000 for testing
# ============================================================================

# Add utils_central_anon to path to import anonymization modules
UTILS_ANON_DIR = Path(__file__).parent / "utils_central_anon"
sys.path.insert(0, str(UTILS_ANON_DIR))

# Import record linkage for unique key generation
from modules.record_linkage import RecordLinkage

logger = logging.getLogger(__name__)


class AnonymizationManager:
    """Manage central anonymization jobs"""

    def __init__(self, config):
        self.config = config
        self.jobs = []
        self.job_id_counter = 1
        self.anonymizer_script = UTILS_ANON_DIR / "central_anonymizer.py"
        self.record_linkage = RecordLinkage(config)

        # Performance tracking
        if ENABLE_PERFORMANCE_TRACKING:
            # Ensure logs directory exists
            log_dir = Path(__file__).parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            self.performance_log_path = log_dir / Path(PERFORMANCE_LOG_FILE).name
            logger.info(f"[Performance Tracking] Enabled - logging to {self.performance_log_path}")

        # Verify script exists
        if not self.anonymizer_script.exists():
            logger.error(f"Central anonymizer script not found at {self.anonymizer_script}")
            logger.error("Please run copy_central_anon_scripts.py to set up the scripts")

    def get_recent_jobs(self, limit: int = 5) -> List[Dict]:
        """Get recent anonymization jobs"""
        return sorted(self.jobs, key=lambda x: x['created_at'], reverse=True)[:limit]

    def get_jobs(self, status: str = 'all', limit: int = 50) -> List[Dict]:
        """Get anonymization jobs filtered by status"""
        if status == 'all':
            filtered = self.jobs
        else:
            filtered = [j for j in self.jobs if j['status'] == status]

        return sorted(filtered, key=lambda x: x['created_at'], reverse=True)[:limit]

    def verify_patient(self, given_name: str, family_name: str, dob: str, gender: str) -> Dict:
        """
        Verify if patient exists in InfluxDB and return available data dates

        Args:
            given_name: Patient's first name
            family_name: Patient's last name
            dob: Date of birth (YYYY-MM-DD format)
            gender: Gender (M/F)

        Returns:
            Dict with verification result and available dates if patient exists
        """
        unique_key = None
        patient_name = f"{given_name} {family_name}"

        try:
            # Generate unique key from patient info
            unique_key = self.record_linkage.generate_unique_key(
                given_name=given_name,
                family_name=family_name,
                dob=dob,
                gender=gender
            )

            logger.info(f"Generated unique key for {given_name} {family_name}: {unique_key[:16]}...")

            # Try to import InfluxDB fetcher to check data availability
            try:
                from modules.utils_central_anon.data_fetcher.influx_fetcher import InfluxDataFetcher

                # Initialize InfluxDB fetcher (bucket is NOT a parameter for __init__)
                fetcher = InfluxDataFetcher(
                    url=self.config.INFLUX_URL,
                    token=self.config.INFLUX_TOKEN,
                    org=self.config.INFLUX_ORG
                )

                # Query available dates for this unique key
                available_dates = fetcher.get_available_dates(
                    bucket=self.config.INFLUX_BUCKET,
                    unique_key=unique_key
                )

                if available_dates:
                    return {
                        'exists': True,
                        'unique_key': unique_key,
                        'patient_name': patient_name,
                        'available_dates': available_dates,
                        'total_records': len(available_dates)
                    }
                else:
                    return {
                        'exists': False,
                        'unique_key': unique_key,
                        'patient_name': patient_name,
                        'message': 'No data found for this patient in InfluxDB'
                    }

            except ImportError as e:
                logger.warning(f"InfluxDB fetcher not available: {e}")
                # Return unique key without verification
                return {
                    'exists': None,  # Unknown
                    'unique_key': unique_key,
                    'patient_name': patient_name,
                    'message': 'InfluxDB verification unavailable - unique key generated but not verified'
                }
            except Exception as influx_error:
                logger.warning(f"InfluxDB query failed: {influx_error}")
                # Return unique key but indicate InfluxDB is unavailable
                return {
                    'exists': None,  # Unknown
                    'unique_key': unique_key,
                    'patient_name': patient_name,
                    'message': f'InfluxDB check failed: {str(influx_error)}'
                }

        except Exception as e:
            logger.error(f"Error verifying patient: {e}")
            # Return error but include any generated unique key
            result = {
                'exists': False,
                'patient_name': patient_name,
                'error': str(e),
                'message': f'Failed to verify patient: {str(e)}'
            }
            if unique_key:
                result['unique_key'] = unique_key
            return result

    def verify_unique_key(self, unique_key: str) -> Dict:
        """
        Verify if data exists for a given unique key
        (Alternative to verify_patient when patient name is unknown)

        Args:
            unique_key: Hashed unique identifier (64 hex characters)

        Returns:
            Dict with data availability information
        """
        try:
            logger.info(f"Verifying data for unique key: {unique_key[:16]}...")

            # Try to check InfluxDB for data availability
            try:
                from modules.utils_central_anon.data_fetcher.influx_fetcher import InfluxDataFetcher

                # Initialize InfluxDB fetcher
                fetcher = InfluxDataFetcher(
                    url=self.config.INFLUX_URL,
                    token=self.config.INFLUX_TOKEN,
                    org=self.config.INFLUX_ORG
                )

                # Query available dates for this unique key
                available_dates = fetcher.get_available_dates(
                    bucket=self.config.INFLUX_BUCKET,
                    unique_key=unique_key
                )

                if available_dates:
                    return {
                        'exists': True,
                        'unique_key': unique_key,
                        'available_dates': available_dates,
                        'total_records': len(available_dates)
                    }
                else:
                    return {
                        'exists': False,
                        'unique_key': unique_key,
                        'message': 'No data found for this unique key in InfluxDB'
                    }

            except ImportError as e:
                logger.warning(f"InfluxDB fetcher not available: {e}")
                return {
                    'exists': None,  # Unknown
                    'unique_key': unique_key,
                    'message': 'InfluxDB verification unavailable'
                }
            except Exception as influx_error:
                logger.warning(f"InfluxDB query failed: {influx_error}")
                return {
                    'exists': None,  # Unknown
                    'unique_key': unique_key,
                    'message': f'InfluxDB check failed: {str(influx_error)}'
                }

        except Exception as e:
            logger.error(f"Error verifying unique key: {e}")
            return {
                'exists': False,
                'unique_key': unique_key,
                'error': str(e),
                'message': f'Failed to verify unique key: {str(e)}'
            }

    def create_job(self, unique_key: str, k_value: int, batch_size_seconds: int,
                  output_format: str, start_time: Optional[str], end_time: Optional[str],
                  created_by: int, api_server_ip: Optional[str] = None,
                  api_server_port: Optional[int] = None, patient_name: Optional[str] = None) -> Dict:
        """Create and trigger anonymization job

        Args:
            unique_key: Patient's hashed unique key
            k_value: K-anonymity level (5, 10, 20, or 50)
            batch_size_seconds: Batch size in seconds
            output_format: Output format (csv, influx, or api)
            start_time: Optional start time for data range
            end_time: Optional end time for data range
            created_by: User ID who created the job
            api_server_ip: API server IP (required if output_format is 'api')
            api_server_port: API server port (required if output_format is 'api')
            patient_name: Patient's name for display purposes

        Returns:
            Dict containing job information
        """
        job_id = self.job_id_counter
        self.job_id_counter += 1

        job = {
            'id': job_id,
            'unique_key': unique_key,
            'patient_name': patient_name,
            'k_value': k_value,
            'batch_size_seconds': batch_size_seconds,
            'output_format': output_format,
            'start_time': start_time,
            'end_time': end_time,
            'status': 'pending',
            'created_by': created_by,
            'created_at': datetime.now().isoformat(),
            'progress': 0
        }

        # Add API server info if using API output
        if output_format == 'api':
            if not api_server_ip or not api_server_port:
                raise ValueError("API server IP and port are required for API output format")
            job['api_server_ip'] = api_server_ip
            job['api_server_port'] = api_server_port

        self.jobs.append(job)

        # Trigger anonymization in background
        self._trigger_anonymization(job)

        logger.info(f"Created anonymization job {job_id} for {unique_key} (K={k_value}, output={output_format})")

        return job

    def get_job_status(self, job_id: int) -> Optional[Dict]:
        """Get status of specific job"""
        return next((j for j in self.jobs if j['id'] == job_id), None)

    def cancel_job(self, job_id: int) -> Dict:
        """Cancel running job"""
        job = next((j for j in self.jobs if j['id'] == job_id), None)

        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job['status'] in ['completed', 'failed', 'cancelled']:
            raise ValueError(f"Cannot cancel job in {job['status']} state")

        job['status'] = 'cancelled'
        job['cancelled_at'] = datetime.now().isoformat()

        logger.info(f"Cancelled job {job_id}")

        return job

    def _log_performance_metrics(self, job: Dict, records_processed: int, processing_time: float):
        """Log performance metrics to file for analysis"""
        if not ENABLE_PERFORMANCE_TRACKING:
            return

        try:
            throughput = records_processed / processing_time if processing_time > 0 else 0

            # Create performance entry
            entry = f"""
{'='*80}
CENTRAL ANONYMIZATION PERFORMANCE METRICS
{'='*80}
Job ID:              {job['id']}
Timestamp:           {datetime.now().isoformat()}
Patient:             {job.get('patient_name', 'Unknown')} (Key: {job['unique_key'][:16]}...)
K-Value:             {job['k_value']}
Time Window:         {job['batch_size_seconds']}s
Output Format:       {job['output_format']}
{'='*80}
Records Processed:   {records_processed:,}
Processing Time:     {processing_time:.2f} seconds
Throughput:          {throughput:.2f} records/second
{'='*80}
Status:              {job['status']}
Started:             {job.get('started_at', 'N/A')}
Completed:           {job.get('completed_at', 'N/A')}
{'='*80}

"""

            # Append to performance log file
            with open(self.performance_log_path, 'a', encoding='utf-8') as f:
                f.write(entry)

            logger.info(f"[Performance Tracking] Logged metrics for job {job['id']}: "
                       f"{records_processed:,} records in {processing_time:.2f}s "
                       f"({throughput:.2f} records/sec)")

        except Exception as e:
            logger.error(f"[Performance Tracking] Failed to log metrics: {e}")

    def _trigger_anonymization(self, job: Dict):
        """Trigger central anonymization script"""
        try:
            if not self.anonymizer_script.exists():
                raise FileNotFoundError(f"Central anonymizer script not found at {self.anonymizer_script}")

            # Build command with all required arguments
            cmd = [
                sys.executable,  # Use current Python interpreter
                str(self.anonymizer_script),
                '--k-value', str(job['k_value']),
                '--time-window', str(job['batch_size_seconds']),
                '--unique-key', job['unique_key']
            ]

            # Add optional time range arguments
            if job.get('start_time'):
                cmd.extend(['--start-time', job['start_time']])
            if job.get('end_time'):
                cmd.extend(['--end_time', job['end_time']])

            # Set output format
            if job.get('output_format'):
                cmd.extend(['--output-format', job['output_format']])

            # Add API server info if using API output
            if job.get('output_format') == 'api':
                if job.get('api_server_ip'):
                    cmd.extend(['--api-server', job['api_server_ip']])
                if job.get('api_server_port'):
                    cmd.extend(['--api-port', str(job['api_server_port'])])

            # Add max records limit if configured (for testing)
            if MAX_RECORDS_FOR_TESTING:
                cmd.extend(['--max-records', str(MAX_RECORDS_FOR_TESTING)])
                logger.info(f"[TESTING MODE] Max records limit: {MAX_RECORDS_FOR_TESTING:,}")

            # Set working directory to utils_central_anon
            cwd = str(UTILS_ANON_DIR)

            # Set up output directory
            # Check if running in Docker (environment variable set by docker-compose)
            # In Docker: /app/modules/utils_central_anon/output (mounted to ./output/centrally_anonymized_records)
            # Locally: Use centralized output directory structure
            if os.getenv('DOCKER_CONTAINER'):
                # Running in Docker - use the path that will be mounted
                output_dir = UTILS_ANON_DIR / "output"
            else:
                # Running locally - use centralized output structure
                output_dir = Path(__file__).parent.parent / "output" / "centrally_anonymized_records"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Set environment variables for script
            env = os.environ.copy()
            env['OUTPUT_DIR'] = str(output_dir)

            # Pass InfluxDB configuration from config to subprocess
            # This ensures central_anonymizer.py can access InfluxDB without .env file
            env['INFLUX_URL'] = self.config.INFLUX_URL
            env['INFLUX_TOKEN'] = self.config.INFLUX_TOKEN
            env['INFLUX_ORG'] = self.config.INFLUX_ORG
            env['INFLUX_BUCKET_RAW'] = getattr(self.config, 'INFLUX_BUCKET_RAW', 'raw-data')
            env['INFLUX_BUCKET_ANON'] = getattr(self.config, 'INFLUX_BUCKET_ANON', 'anonymized-data')
            env['INFLUX_INPUT_BUCKET'] = getattr(self.config, 'INFLUX_BUCKET_RAW', 'raw-data')
            env['INFLUX_OUTPUT_BUCKET'] = getattr(self.config, 'INFLUX_BUCKET_ANON', 'anonymized-data')

            # Pass other configuration that central_anonymizer might need
            env['LOG_LEVEL'] = getattr(self.config, 'LOG_LEVEL', 'INFO')

            # Performance tracking: Start timer
            if ENABLE_PERFORMANCE_TRACKING:
                start_time = time.time()
                job['perf_start_time'] = start_time

            # Run in background with output capture
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                cwd=cwd,
                env=env,
                universal_newlines=True,  # Text mode for easier reading
                bufsize=1  # Line buffered
            )

            job['status'] = 'running'
            job['started_at'] = datetime.now().isoformat()
            job['process_id'] = process.pid
            job['output_dir'] = str(output_dir)

            logger.info(f"Triggered anonymization job {job['id']} (PID: {process.pid})")
            logger.info(f"Command: {' '.join(cmd)}")
            logger.info(f"=" * 80)
            logger.info(f"[Job {job['id']}] Script output (streaming):")
            logger.info(f"=" * 80)

            # Monitor process completion in a separate thread with real-time output
            import threading
            def monitor_job():
                records_processed = 0
                output_lines = []

                # Stream output line by line in real-time
                for line in iter(process.stdout.readline, ''):
                    if line:
                        logger.info(f"[Job {job['id']}] {line.rstrip()}")
                        output_lines.append(line)

                        # Try to extract record count from output
                        # Look for "Time window complete: X total records processed"
                        # or "Total records processed: X"
                        if 'total records processed' in line.lower():
                            try:
                                # Extract all numbers from the line (including comma-separated)
                                import re
                                # Remove commas from numbers first, then extract
                                line_no_commas = line.replace(',', '')
                                numbers = re.findall(r'\d+', line_no_commas)
                                if numbers:
                                    # Take the largest number (likely the total count)
                                    records_processed = max(records_processed, max(int(n) for n in numbers))
                            except:
                                pass

                # Wait for process to complete
                process.wait()

                # Performance tracking: Calculate metrics
                if ENABLE_PERFORMANCE_TRACKING and job.get('perf_start_time'):
                    end_time = time.time()
                    processing_time = end_time - job['perf_start_time']
                    job['perf_processing_time'] = processing_time
                    job['perf_records_processed'] = records_processed

                    # Try to get actual record count from output CSV if available
                    if records_processed == 0:
                        try:
                            # Check output directory for CSV files
                            csv_files = list(output_dir.glob(f"*{job['unique_key'][:16]}*.csv"))
                            if csv_files:
                                # Count lines in CSV (excluding header)
                                with open(csv_files[0], 'r') as f:
                                    records_processed = sum(1 for _ in f) - 1  # Subtract header
                        except:
                            pass
                if MAX_RECORDS_FOR_TESTING is not None and MAX_RECORDS_FOR_TESTING > 0:
                    records_processed = MAX_RECORDS_FOR_TESTING


                    # Log performance metrics
                    self._log_performance_metrics(job, records_processed, processing_time)

                if process.returncode == 0:
                    job['status'] = 'completed'
                    job['completed_at'] = datetime.now().isoformat()
                    logger.info(f"=" * 80)
                    logger.info(f"[Job {job['id']}] Completed successfully")
                    logger.info(f"=" * 80)
                else:
                    job['status'] = 'failed'
                    job['error'] = f"Process exited with code {process.returncode}"
                    job['failed_at'] = datetime.now().isoformat()
                    logger.error(f"=" * 80)
                    logger.error(f"[Job {job['id']}] Failed with exit code {process.returncode}")
                    logger.error(f"=" * 80)

            monitor_thread = threading.Thread(target=monitor_job, daemon=True)
            monitor_thread.start()

        except Exception as e:
            logger.error(f"Failed to trigger anonymization: {e}")
            job['status'] = 'failed'
            job['error'] = str(e)
            job['failed_at'] = datetime.now().isoformat()
