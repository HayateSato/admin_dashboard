"""
Mean Value Imputation for ECG Data

Implements mean value imputation feature from the distributed anonymization.
Converts anonymized ECG values (ranges or suppressed) into analytically useful values.
"""

import re
from typing import List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class EcgMeanImputation:
    """ECG Mean Value Imputation Utility"""

    @staticmethod
    def apply_mean_imputation(ecg_values: List[str]) -> Dict:
        """Apply mean imputation to a list of ECG values

        Replaces:
        - "*" (suppressed values) with the mean of non-suppressed values in the batch
        - Range values like "11;14" or "-5;-3" with their mean (12.5, -4.0)
        - Single values remain unchanged

        Args:
            ecg_values: List of ECG value strings (ranges, single values, or "*")

        Returns:
            Dictionary with 'processed_values', 'suppression_counter', 'original_count', 'batch_mean'
        """
        # First pass: Process non-suppressed values and calculate batch mean
        temp_values: List[float] = []
        suppression_indices: List[int] = []
        suppression_counter = 0

        for i, value in enumerate(ecg_values):
            if value == "*":
                # Mark for later replacement with batch mean
                suppression_indices.append(i)
                suppression_counter += 1
                temp_values.append(0.0)  # Placeholder
            else:
                numerical_values = EcgMeanImputation.extract_numerical_values(value)

                if not numerical_values:
                    logger.warning(f"Could not extract numerical values from '{value}' at index {i}")
                    suppression_indices.append(i)
                    suppression_counter += 1
                    temp_values.append(0.0)  # Placeholder
                    continue

                if len(numerical_values) == 1:
                    # Single value - keep as is
                    temp_values.append(numerical_values[0])
                else:
                    # Range value - calculate mean
                    min_val = min(numerical_values)
                    max_val = max(numerical_values)
                    mean = (min_val + max_val) / 2
                    temp_values.append(mean)

        # Calculate batch mean from non-suppressed values
        non_suppressed_values = [temp_values[i] for i in range(len(temp_values))
                                 if i not in suppression_indices]

        if non_suppressed_values:
            batch_mean = sum(non_suppressed_values) / len(non_suppressed_values)
        else:
            # If all values are suppressed, use 0 as fallback
            batch_mean = 0.0
            logger.warning("All values in batch are suppressed, using 0 as batch mean")

        # Second pass: Replace suppressed values with batch mean
        processed_values = temp_values.copy()
        for idx in suppression_indices:
            processed_values[idx] = batch_mean

        return {
            'processed_values': processed_values,
            'suppression_counter': suppression_counter,
            'original_count': len(ecg_values),
            'batch_mean': batch_mean,
        }

    @staticmethod
    def apply_single_mean_imputation(value: str) -> float:
        """Apply mean imputation to a single ECG value string

        Args:
            value: ECG value string (range, single value, or "*")

        Returns:
            Processed value as float
        """
        if value == "*":
            return 0.0

        numerical_values = EcgMeanImputation.extract_numerical_values(value)

        if not numerical_values:
            logger.warning(f"Could not extract numerical values from '{value}'")
            return 0.0

        if len(numerical_values) == 1:
            return numerical_values[0]
        else:
            # Range value - calculate mean
            min_val = min(numerical_values)
            max_val = max(numerical_values)
            return (min_val + max_val) / 2

    @staticmethod
    def extract_numerical_values(value_str: str) -> List[float]:
        """Extract numerical values from various range formats

        Supports formats:
        - Normal form: "53" -> [53.0]
        - Range with semicolon: "51;52" -> [51.0, 52.0]
        - Range with dash: "51-52" -> [51.0, 52.0]
        - Range with tilde: "51~52" -> [51.0, 52.0]
        - Range with comma: "51,52" -> [51.0, 52.0]
        - Zero: "0" -> [0.0]
        - Negative: "-25" -> [-25.0]
        - Negative range: "-25;-20" -> [-25.0, -20.0]

        Args:
            value_str: Value string to parse

        Returns:
            List of extracted numerical values
        """
        if not value_str:
            return []

        # Remove any whitespace
        value_str = value_str.strip()

        # Handle different range separators
        parts: List[str] = []

        if ';' in value_str:
            parts = value_str.split(';')
        elif '~' in value_str:
            parts = value_str.split('~')
        elif ',' in value_str:
            parts = value_str.split(',')
        elif '-' in value_str and not value_str.startswith('-'):
            # Handle dash ranges, but not negative numbers starting with -
            parts = value_str.split('-')
        elif '-' in value_str and value_str.count('-') > 1:
            # Handle negative ranges like "-25--20" or "-25;-20"
            pattern = r'^(-?\d+(?:\.\d+)?)[-;~,](-?\d+(?:\.\d+)?)$'
            match = re.match(pattern, value_str)
            if match:
                parts = [match.group(1), match.group(2)]
            else:
                parts = [value_str]
        else:
            # Single value (including negative numbers)
            parts = [value_str]

        # Convert to floats
        result: List[float] = []
        for part in parts:
            try:
                result.append(float(part.strip()))
            except ValueError:
                logger.warning(f"Could not convert '{part}' to numerical value in '{value_str}'")

        return result

    @staticmethod
    def process_ecg_data_from_records(
        records: List[Dict],
        ecg_column_name: str = 'ecg'
    ) -> List[Dict]:
        """Process ECG data from list of dictionaries and apply mean imputation

        Takes a list of dictionaries representing data rows and applies mean imputation
        to the ECG column specified by ecg_column_name

        Args:
            records: List of dictionaries (e.g., from CSV/InfluxDB)
            ecg_column_name: Name of the ECG column

        Returns:
            List of processed dictionaries with imputed ECG values
        """
        if not records:
            return records

        processed_data: List[Dict] = []
        total_suppressions = 0

        for row in records:
            new_row = row.copy()

            if ecg_column_name in row:
                ecg_value = str(row[ecg_column_name])
                processed_value = EcgMeanImputation.apply_single_mean_imputation(ecg_value)

                new_row[ecg_column_name] = processed_value
                new_row[f'{ecg_column_name}_original'] = ecg_value  # Keep original for reference

                if ecg_value == "*":
                    total_suppressions += 1

            processed_data.append(new_row)

        logger.info(f"Mean imputation applied to {len(records)} ECG values, "
                   f"{total_suppressions} suppressions replaced with batch mean")
        return processed_data

    @staticmethod
    def get_imputation_stats(
        original_values: List[str],
        processed_values: List[float]
    ) -> Dict:
        """Get statistics about mean imputation results

        Args:
            original_values: List of original ECG value strings
            processed_values: List of processed ECG values

        Returns:
            Dictionary with statistics
        """
        suppressed_count = 0
        range_imputed_count = 0
        unchanged_count = 0

        for original in original_values:
            if original == "*":
                suppressed_count += 1
            else:
                numericals = EcgMeanImputation.extract_numerical_values(original)
                if len(numericals) > 1:
                    range_imputed_count += 1
                else:
                    unchanged_count += 1

        mean_processed = sum(processed_values) / len(processed_values) if processed_values else 0.0

        return {
            'total': len(original_values),
            'suppressed_to_zero': suppressed_count,
            'range_imputed': range_imputed_count,
            'unchanged': unchanged_count,
            'mean_processed_value': mean_processed,
        }
