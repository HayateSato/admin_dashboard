"""
System Monitoring Module
Monitors backend services (InfluxDB, PostgreSQL, FL Server, etc.)
"""

import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import subprocess
import json

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitor backend services and system resources"""

    def __init__(self, config):
        self.config = config

    def get_system_status(self) -> Dict:
        """Get overall system status summary"""
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'influxdb_status': self._check_service_simple('influxdb'),
            'postgres_status': self._check_service_simple('postgres'),
            'fl_server_status': self._check_service_simple('fl_server'),
            'services_healthy': self._count_healthy_services(),
            'uptime_hours': self._get_system_uptime()
        }

    def get_detailed_stats(self) -> Dict:
        """Get detailed system statistics"""
        cpu_info = psutil.cpu_percent(interval=1, percpu=True)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()

        return {
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'overall_percent': psutil.cpu_percent(interval=1),
                'per_core': cpu_info,
                'core_count': psutil.cpu_count(),
                'frequency_mhz': psutil.cpu_freq().current if psutil.cpu_freq() else None
            },
            'memory': {
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3),
                'used_gb': memory.used / (1024**3),
                'percent': memory.percent
            },
            'disk': {
                'total_gb': disk.total / (1024**3),
                'used_gb': disk.used / (1024**3),
                'free_gb': disk.free / (1024**3),
                'percent': disk.percent
            },
            'network': {
                'bytes_sent_mb': network.bytes_sent / (1024**2),
                'bytes_recv_mb': network.bytes_recv / (1024**2),
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            }
        }

    def check_influxdb(self) -> Dict:
        """Check InfluxDB connection and get metrics"""
        try:
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.health_check_service import HealthCheckService

            client = InfluxDBClient(
                url=self.config.INFLUX_URL,
                token=self.config.INFLUX_TOKEN,
                org=self.config.INFLUX_ORG
            )

            # Check health
            health = client.health()

            # Get bucket info
            buckets_api = client.buckets_api()
            buckets = buckets_api.find_buckets().buckets

            # Get data point count (approximate)
            query_api = client.query_api()

            raw_count_query = f'''
                from(bucket: "{self.config.INFLUX_BUCKET_RAW}")
                    |> range(start: -24h)
                    |> count()
            '''

            anon_count_query = f'''
                from(bucket: "{self.config.INFLUX_BUCKET_ANON}")
                    |> range(start: -24h)
                    |> count()
            '''

            try:
                raw_result = query_api.query(raw_count_query)
                raw_count = sum(record.get_value() for table in raw_result for record in table.records)
            except:
                raw_count = 0

            try:
                anon_result = query_api.query(anon_count_query)
                anon_count = sum(record.get_value() for table in anon_result for record in table.records)
            except:
                anon_count = 0

            client.close()

            return {
                'status': 'healthy' if health.status == 'pass' else 'unhealthy',
                'message': health.message,
                'url': self.config.INFLUX_URL,
                'buckets': [b.name for b in buckets],
                'data_points_24h': {
                    'raw': raw_count,
                    'anonymized': anon_count
                },
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"InfluxDB health check failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'url': self.config.INFLUX_URL,
                'timestamp': datetime.now().isoformat()
            }

    def check_postgres(self) -> Dict:
        """Check PostgreSQL connection and get metrics"""
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

            # Get database size
            cursor.execute(f"SELECT pg_database_size('{self.config.POSTGRES_DB}');")
            db_size = cursor.fetchone()[0]

            # Get table count
            cursor.execute("""
                SELECT count(*)
                FROM information_schema.tables
                WHERE table_schema = 'public';
            """)
            table_count = cursor.fetchone()[0]

            # Get active connections
            cursor.execute("SELECT count(*) FROM pg_stat_activity;")
            active_connections = cursor.fetchone()[0]

            # Get user count (if users table exists)
            try:
                cursor.execute("SELECT count(*) FROM users;")
                user_count = cursor.fetchone()[0]
            except:
                user_count = 0

            cursor.close()
            conn.close()

            return {
                'status': 'healthy',
                'host': self.config.POSTGRES_HOST,
                'port': self.config.POSTGRES_PORT,
                'database': self.config.POSTGRES_DB,
                'size_mb': db_size / (1024**2),
                'table_count': table_count,
                'active_connections': active_connections,
                'user_count': user_count,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'host': self.config.POSTGRES_HOST,
                'port': self.config.POSTGRES_PORT,
                'timestamp': datetime.now().isoformat()
            }

    def check_fl_server(self) -> Dict:
        """Check FL server status"""
        try:
            # Check if FL server process is running
            fl_running = self._is_process_running('python', 'fl_grpc_server.py')

            # Try to read global model file
            model_path = self.config.FL_MODEL_PATH
            model_info = {}

            if os.path.exists(model_path):
                with open(model_path, 'r') as f:
                    model_data = json.load(f)

                model_info = {
                    'version': model_data.get('version', 'unknown'),
                    'last_updated': model_data.get('timestamp', 'unknown'),
                    'num_features': len(model_data.get('model', {}).get('learner', {}).get('feature_names', [])),
                    'file_size_kb': os.path.getsize(model_path) / 1024
                }

            return {
                'status': 'running' if fl_running else 'stopped',
                'host': self.config.FL_SERVER_HOST,
                'port': self.config.FL_SERVER_PORT,
                'model_info': model_info,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"FL server health check failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def get_logs(self, service='all', limit=100) -> List[Dict]:
        """Get system logs"""
        logs = []

        try:
            log_files = {
                'dashboard': os.path.join(self.config.LOG_DIR, 'admin_dashboard.log'),
                'anonymization': os.path.join(self.config.LOG_DIR, 'anonymization.log'),
                'fl_server': os.path.join('../fl_server/logs', 'fl_server.log')
            }

            if service == 'all':
                files_to_read = log_files.values()
            elif service in log_files:
                files_to_read = [log_files[service]]
            else:
                files_to_read = []

            for log_file in files_to_read:
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        lines = f.readlines()[-limit:]
                        for line in lines:
                            logs.append({
                                'service': os.path.basename(log_file).replace('.log', ''),
                                'message': line.strip(),
                                'timestamp': datetime.now().isoformat()
                            })

        except Exception as e:
            logger.error(f"Failed to read logs: {e}")

        return logs[-limit:]

    def _check_service_simple(self, service_name: str) -> str:
        """Simple service health check"""
        if service_name == 'influxdb':
            try:
                from influxdb_client import InfluxDBClient
                client = InfluxDBClient(url=self.config.INFLUX_URL, token=self.config.INFLUX_TOKEN)
                health = client.health()
                client.close()
                return 'healthy' if health.status == 'pass' else 'unhealthy'
            except:
                return 'error'

        elif service_name == 'postgres':
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host=self.config.POSTGRES_HOST,
                    port=self.config.POSTGRES_PORT,
                    database=self.config.POSTGRES_DB,
                    user=self.config.POSTGRES_USER,
                    password=self.config.POSTGRES_PASSWORD,
                    connect_timeout=5
                )
                conn.close()
                return 'healthy'
            except:
                return 'error'

        elif service_name == 'fl_server':
            return 'running' if self._is_process_running('python', 'fl_grpc_server.py') else 'stopped'

        return 'unknown'

    def _count_healthy_services(self) -> int:
        """Count number of healthy services"""
        count = 0
        if self._check_service_simple('influxdb') == 'healthy':
            count += 1
        if self._check_service_simple('postgres') == 'healthy':
            count += 1
        if self._check_service_simple('fl_server') in ['healthy', 'running']:
            count += 1
        return count

    def _get_system_uptime(self) -> float:
        """Get system uptime in hours"""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            return uptime.total_seconds() / 3600
        except:
            return 0.0

    def _is_process_running(self, process_name: str, script_name: Optional[str] = None) -> bool:
        """Check if a process is running"""
        try:
            for proc in psutil.process_iter(['name', 'cmdline']):
                if process_name.lower() in proc.info['name'].lower():
                    if script_name:
                        cmdline = ' '.join(proc.info['cmdline'])
                        if script_name in cmdline:
                            return True
                    else:
                        return True
        except:
            pass
        return False
