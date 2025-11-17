"""
Patient Manager for Registered Patients Data Access

Handles queries for patient data from PostgreSQL database,
including users table and privacy_policies table.
"""

import logging
import psycopg2
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PatientManager:
    """Manages patient data access and updates"""

    def __init__(self, config):
        """
        Initialize Patient Manager

        Args:
            config: Configuration object with PostgreSQL settings
        """
        self.config = config
        self.connection = None
        logger.info("Patient Manager initialized")

    def _get_connection(self):
        """Get or create PostgreSQL connection"""
        if self.connection is None or self.connection.closed:
            try:
                self.connection = psycopg2.connect(
                    host=self.config.POSTGRES_HOST,
                    port=self.config.POSTGRES_PORT,
                    database=self.config.POSTGRES_DB,
                    user=self.config.POSTGRES_USER,
                    password=self.config.POSTGRES_PASSWORD
                )
                logger.info("✅ Connected to PostgreSQL")
            except Exception as e:
                logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
                raise
        return self.connection

    def get_all_patients(self) -> List[Dict]:
        """
        Get list of all registered patients with privacy settings and policy info

        Returns:
            List of patient dictionaries with fields:
            - id: User ID
            - unique_key: Hashed unique identifier (64 hex chars)
            - device_id: Device identifier
            - last_session: Last session timestamp
            - privacy_settings: JSON with k_value, time_window, auto_anonymize
            - remote_anon_enabled: Whether remote anonymization is enabled
            - consent_given: Whether user gave consent for remote control
            - last_updated: Last update timestamp for privacy policy
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    u.id,
                    u.unique_key,
                    u.device_id,
                    u.last_session,
                    u.privacy_settings,
                    u.created_at,
                    COALESCE(pp.is_remote, false) as remote_anon_enabled,
                    COALESCE(pp.consent_given, false) as consent_given,
                    pp.consent_timestamp,
                    pp.last_updated as policy_last_updated
                FROM users u
                LEFT JOIN privacy_policies pp ON u.unique_key = pp.unique_key
                ORDER BY u.last_session DESC NULLS LAST;
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            patients = []
            for row in rows:
                patient = {
                    'id': row[0],
                    'unique_key': row[1],
                    'unique_key_short': row[1][:16] + '...' if row[1] else 'N/A',  # Shortened for display
                    'device_id': row[2] or 'N/A',
                    'last_session': row[3].isoformat() if row[3] else None,
                    'privacy_settings': row[4] or {},
                    'created_at': row[5].isoformat() if row[5] else None,
                    'remote_anon_enabled': row[6],
                    'consent_given': row[7],
                    'consent_timestamp': row[8].isoformat() if row[8] else None,
                    'policy_last_updated': row[9].isoformat() if row[9] else None
                }

                # Extract privacy settings for easy access
                if patient['privacy_settings']:
                    patient['k_value'] = patient['privacy_settings'].get('k_value', 5)
                    patient['time_window'] = patient['privacy_settings'].get('time_window', 30)
                    patient['auto_anonymize'] = patient['privacy_settings'].get('auto_anonymize', False)
                else:
                    patient['k_value'] = 5
                    patient['time_window'] = 30
                    patient['auto_anonymize'] = False

                patients.append(patient)

            cursor.close()
            logger.info(f"✅ Retrieved {len(patients)} patients from database")
            return patients

        except Exception as e:
            logger.error(f"❌ Error retrieving patients: {e}")
            return []

    def get_patient_by_unique_key(self, unique_key: str) -> Optional[Dict]:
        """
        Get single patient by unique key

        Args:
            unique_key: Patient's 64-character hex unique identifier

        Returns:
            Patient dictionary or None if not found
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    u.id,
                    u.unique_key,
                    u.device_id,
                    u.last_session,
                    u.privacy_settings,
                    u.created_at,
                    COALESCE(pp.is_remote, false) as remote_anon_enabled,
                    COALESCE(pp.consent_given, false) as consent_given,
                    pp.consent_timestamp,
                    pp.last_updated as policy_last_updated
                FROM users u
                LEFT JOIN privacy_policies pp ON u.unique_key = pp.unique_key
                WHERE u.unique_key = %s;
            """

            cursor.execute(query, (unique_key,))
            row = cursor.fetchone()

            if not row:
                cursor.close()
                return None

            patient = {
                'id': row[0],
                'unique_key': row[1],
                'device_id': row[2] or 'N/A',
                'last_session': row[3].isoformat() if row[3] else None,
                'privacy_settings': row[4] or {},
                'created_at': row[5].isoformat() if row[5] else None,
                'remote_anon_enabled': row[6],
                'consent_given': row[7],
                'consent_timestamp': row[8].isoformat() if row[8] else None,
                'policy_last_updated': row[9].isoformat() if row[9] else None
            }

            cursor.close()
            return patient

        except Exception as e:
            logger.error(f"❌ Error retrieving patient {unique_key[:16]}...: {e}")
            return None

    def update_privacy_settings(self, unique_key: str, settings: Dict) -> bool:
        """
        Update privacy settings for a patient in users table

        Args:
            unique_key: Patient's unique identifier
            settings: Dictionary with privacy settings

        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            import json
            settings_json = json.dumps(settings)

            query = """
                UPDATE users
                SET privacy_settings = %s::jsonb,
                    updated_at = NOW()
                WHERE unique_key = %s;
            """

            cursor.execute(query, (settings_json, unique_key))
            conn.commit()

            affected = cursor.rowcount
            cursor.close()

            if affected > 0:
                logger.info(f"✅ Updated privacy settings for {unique_key[:16]}...")
                return True
            else:
                logger.warning(f"⚠️  No patient found with unique_key {unique_key[:16]}...")
                return False

        except Exception as e:
            logger.error(f"❌ Error updating privacy settings: {e}")
            if conn:
                conn.rollback()
            return False

    def update_remote_anon_status(self, unique_key: str, enabled: bool, consent: bool = None) -> bool:
        """
        Update remote anonymization status in privacy_policies table

        Args:
            unique_key: Patient's unique identifier
            enabled: Whether remote anonymization is enabled
            consent: Optional consent status update

        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if consent is not None:
                query = """
                    INSERT INTO privacy_policies (unique_key, is_remote, consent_given, consent_timestamp, last_updated)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    ON CONFLICT (unique_key)
                    DO UPDATE SET
                        is_remote = EXCLUDED.is_remote,
                        consent_given = EXCLUDED.consent_given,
                        consent_timestamp = EXCLUDED.consent_timestamp,
                        last_updated = NOW();
                """
                cursor.execute(query, (unique_key, enabled, consent))
            else:
                query = """
                    INSERT INTO privacy_policies (unique_key, is_remote, last_updated)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (unique_key)
                    DO UPDATE SET
                        is_remote = EXCLUDED.is_remote,
                        last_updated = NOW();
                """
                cursor.execute(query, (unique_key, enabled))

            conn.commit()
            cursor.close()

            logger.info(f"✅ Updated remote anonymization status for {unique_key[:16]}... to {enabled}")
            return True

        except Exception as e:
            logger.error(f"❌ Error updating remote anon status: {e}")
            if conn:
                conn.rollback()
            return False

    def get_patients_with_remote_anon_enabled(self) -> List[Dict]:
        """
        Get list of patients who have remote anonymization enabled

        Returns:
            List of patient dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    u.id,
                    u.unique_key,
                    u.device_id,
                    u.privacy_settings,
                    pp.is_remote,
                    pp.last_updated
                FROM users u
                INNER JOIN privacy_policies pp ON u.unique_key = pp.unique_key
                WHERE pp.is_remote = true
                ORDER BY pp.last_updated DESC;
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            patients = []
            for row in rows:
                patients.append({
                    'id': row[0],
                    'unique_key': row[1],
                    'device_id': row[2],
                    'privacy_settings': row[3] or {},
                    'remote_anon_enabled': row[4],
                    'last_updated': row[5].isoformat() if row[5] else None
                })

            cursor.close()
            logger.info(f"✅ Found {len(patients)} patients with remote anonymization enabled")
            return patients

        except Exception as e:
            logger.error(f"❌ Error retrieving patients with remote anon enabled: {e}")
            return []

    def close(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.info("PostgreSQL connection closed")
