"""
ECG Data Validator

Validates and filters ECG data before anonymization following the same rules
as the Flutter app's async_anonymization_processor.dart.

Validation Rules:
1. Skip anonymization if ECG value is 0, 0.0, or empty
2. Clamp ECG values outside the valid range [-2500, 2500] and skip anonymization
3. Exception: workout_compact rows are always anonymized regardless of ECG value
"""

import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class EcgValidator:
    """Validates and filters ECG data before anonymization"""

    # Valid ECG range (matching Flutter implementation)
    ECG_MIN = -2500
    ECG_MAX = 2500

    def __init__(self):
        """Initialize ECG validator"""
        self.stats = {
            'total_records': 0,
            'zero_ecg_skipped': 0,
            'clamped_ecg_skipped': 0,
            'workout_compact_forced': 0,
            'valid_for_anonymization': 0
        }

    def validate_and_filter(
        self,
        records: List[Dict],
        workout_compact_key: str = 'is_workout_compact'
    ) -> Tuple[List[Dict], Dict]:
        """Validate ECG data and filter for anonymization

        Args:
            records: List of ECG records with format:
                {
                    'timestamp': int (milliseconds),
                    'ecg': int (ECG value),
                    'deviceAddress': str,
                    'field': str,
                    ... other fields
                }
            workout_compact_key: Key name for workout compact flag (default: 'is_workout_compact')

        Returns:
            Tuple of:
            - List of validated records (with modified 'should_anonymize' flag and potentially clamped ECG values)
            - Validation statistics dictionary

        Note:
            Records are NOT removed from the list. Instead, each record gets a
            'should_anonymize' boolean flag that indicates if it should be anonymized.
            This matches the Flutter app behavior where all records are kept but
            only some are anonymized.
        """
        self._reset_stats()
        self.stats['total_records'] = len(records)

        logger.info(f"🔍 Validating {len(records)} ECG records...")

        validated_records = []

        for record in records:
            # Deep copy the record to avoid modifying the original
            validated_record = record.copy()

            # Default: should anonymize
            should_anonymize = True
            is_workout_compact = False

            # Check if this is a workout compact row (always anonymize these)
            if workout_compact_key in record:
                workout_value = record[workout_compact_key]
                if workout_value in [1, '1', 1.0, '1.0', True, 'true']:
                    is_workout_compact = True
                    should_anonymize = True  # Force anonymization for workout compact
                    self.stats['workout_compact_forced'] += 1
                    logger.debug(f"   ✅ Workout compact row - forcing anonymization")

            # Only check ECG validation rules if NOT a workout compact row
            if not is_workout_compact:
                ecg_value = record.get('ecg')

                # Rule 1: Skip if ECG is 0, 0.0, or None
                if ecg_value is None or ecg_value == 0 or ecg_value == 0.0:
                    should_anonymize = False
                    self.stats['zero_ecg_skipped'] += 1
                    logger.debug(f"   ⚠️ Zero ECG value - skipping anonymization")

                # Rule 2: Clamp if outside valid range and skip anonymization
                elif isinstance(ecg_value, (int, float)):
                    if ecg_value < self.ECG_MIN or ecg_value > self.ECG_MAX:
                        # Clamp the value
                        clamped_value = max(self.ECG_MIN, min(self.ECG_MAX, ecg_value))
                        validated_record['ecg'] = int(clamped_value)
                        should_anonymize = False
                        self.stats['clamped_ecg_skipped'] += 1
                        logger.debug(
                            f"   ⚠️ Out-of-range ECG value ({ecg_value}) - "
                            f"clamped to {clamped_value}, skipping anonymization"
                        )

            # Add should_anonymize flag to record
            validated_record['should_anonymize'] = should_anonymize
            if should_anonymize:
                self.stats['valid_for_anonymization'] += 1

            validated_records.append(validated_record)

        # Log summary
        self._log_validation_summary()

        return validated_records, self.stats.copy()

    def _reset_stats(self):
        """Reset validation statistics"""
        self.stats = {
            'total_records': 0,
            'zero_ecg_skipped': 0,
            'clamped_ecg_skipped': 0,
            'workout_compact_forced': 0,
            'valid_for_anonymization': 0
        }

    def _log_validation_summary(self):
        """Log validation statistics summary"""
        logger.info(f"✅ Validation complete:")
        logger.info(f"   Total records: {self.stats['total_records']}")
        logger.info(f"   Valid for anonymization: {self.stats['valid_for_anonymization']}")

        if self.stats['zero_ecg_skipped'] > 0:
            logger.info(
                f"   📋 Skipped {self.stats['zero_ecg_skipped']} records with zero ECG "
                f"(will not anonymize)"
            )

        if self.stats['clamped_ecg_skipped'] > 0:
            logger.info(
                f"   📋 Clamped and skipped {self.stats['clamped_ecg_skipped']} records with "
                f"out-of-range ECG ({self.ECG_MIN} to {self.ECG_MAX}) (will not anonymize)"
            )

        if self.stats['workout_compact_forced'] > 0:
            logger.info(
                f"   📋 Forced anonymization for {self.stats['workout_compact_forced']} "
                f"workout_compact records"
            )

    @staticmethod
    def filter_for_anonymization(records: List[Dict]) -> List[Dict]:
        """Filter records to only include those marked for anonymization

        Args:
            records: List of validated records with 'should_anonymize' flag

        Returns:
            List of records where should_anonymize=True
        """
        return [r for r in records if r.get('should_anonymize', True)]

    @staticmethod
    def filter_excluded_from_anonymization(records: List[Dict]) -> List[Dict]:
        """Filter records to only include those excluded from anonymization

        Args:
            records: List of validated records with 'should_anonymize' flag

        Returns:
            List of records where should_anonymize=False
        """
        return [r for r in records if not r.get('should_anonymize', True)]
