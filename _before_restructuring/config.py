"""
Configuration for Admin Dashboard
Load settings from environment variables with defaults
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if exists
load_dotenv()


class Config:
    """Dashboard configuration"""

    def __init__(self):
        # Flask settings
        self.SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-secret-key-in-production')
        self.FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
        self.FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
        self.FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

        # Database settings
        self.POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
        self.POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
        self.POSTGRES_DB = os.getenv('POSTGRES_DB', 'privacy_umbrella')
        self.POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
        self.POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

        # InfluxDB settings
        self.INFLUX_URL = os.getenv('INFLUX_URL', 'http://localhost:8086')
        self.INFLUX_TOKEN = os.getenv('INFLUX_TOKEN', '')
        self.INFLUX_ORG = os.getenv('INFLUX_ORG', 'mcs-data-labs')
        # INFLUX_BUCKET defaults to INFLUX_BUCKET_RAW if not set explicitly
        self.INFLUX_BUCKET_RAW = os.getenv('INFLUX_BUCKET_RAW', 'raw-data')
        self.INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', self.INFLUX_BUCKET_RAW)  # Use RAW bucket as default
        self.INFLUX_BUCKET_ANON = os.getenv('INFLUX_BUCKET_ANON', 'anonymized-data')

        # FL Server settings
        self.FL_SERVER_HOST = os.getenv('FL_SERVER_HOST', 'localhost')
        self.FL_SERVER_PORT = int(os.getenv('FL_SERVER_PORT', 50051))
        self.FL_MODEL_PATH = os.getenv('FL_MODEL_PATH', '../fl_server/global_model_latest.json')

        # Central Anonymization settings
        self.CENTRAL_ANON_SCRIPT = os.getenv(
            'CENTRAL_ANON_SCRIPT',
            '../central_anonymization/central_anonymizer.py'
        )
        self.ANON_OUTPUT_DIR = os.getenv('ANON_OUTPUT_DIR', '../output/centrally_anonymized_records')
        # Record Linkage settings
        self.RECORD_LINKAGE_SCRIPT = os.getenv(
            'RECORD_LINKAGE_SCRIPT',
            '../record_linkage/main.py'
        )
        self.LINKED_OUTPUT_DIR = os.getenv('LINKED_OUTPUT_DIR', '../output/linked_records')

        # MQTT settings
        self.MQTT_BROKER_HOST = os.getenv('MQTT_BROKER_HOST', 'localhost')
        self.MQTT_BROKER_PORT = int(os.getenv('MQTT_BROKER_PORT', 1883))
        self.MQTT_TOPIC_PRIVACY = os.getenv('MQTT_TOPIC_PRIVACY', 'privacy/settings')

        # Logging settings
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_DIR = os.getenv('LOG_DIR', 'logs')

        # Session settings
        self.SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', 8))

    def get_postgres_connection_string(self):
        """Get PostgreSQL connection string"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def validate(self):
        """Validate configuration"""
        errors = []

        if not self.POSTGRES_PASSWORD:
            errors.append("POSTGRES_PASSWORD is not set")

        if not self.INFLUX_TOKEN:
            errors.append("INFLUX_TOKEN is not set")

        # Create log directory if not exists
        Path(self.LOG_DIR).mkdir(parents=True, exist_ok=True)

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        return True
