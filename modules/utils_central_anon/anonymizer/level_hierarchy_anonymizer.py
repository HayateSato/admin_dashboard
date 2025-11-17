"""
Level-by-Level Hierarchy-Based ECG Anonymization

Implements the level-by-level approach with predefined hierarchy from CSV.
This approach provides better privacy-utility tradeoff than standard Mondrian.

Algorithm:
1. Load hierarchy from smarko_hierarchy_ecg.csv (one-time setup)
2. For each buffer of ECG values:
   a. Sort by ECG value
   b. Try Level 1 (finest) → Check if groups satisfy k-anonymity
   c. Move satisfied groups to output
   d. For remaining values, try Level 2 → repeat
   e. Continue until all values are anonymized (up to Level 7 or root *)
3. Apply mean imputation to convert ranges to single values
"""

import csv
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EcgAnonymizationRecord:
    """Record for anonymization process"""
    timestamp: int
    original_ecg: int
    anonymized_range: Optional[str] = None
    assigned_level: Optional[int] = None


class EcgHierarchy:
    """Represents the ECG hierarchy loaded from CSV"""

    MAX_LEVEL = 8
    MIN_ECG = -2500
    MAX_ECG = 2500

    def __init__(self):
        # Map: raw_ecg_value → [level1, level2, ..., level7, root]
        self._hierarchy_map: Dict[int, List[str]] = {}
        self._is_loaded = False

    def load_from_csv(self, csv_path: str) -> None:
        """Load hierarchy from CSV file

        Args:
            csv_path: Path to the hierarchy CSV file
        """
        try:
            logger.info(f"📂 Loading ECG hierarchy from: {csv_path}")

            valid_lines = 0
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)

                for line in reader:
                    if not line or len(line) < 9:  # Need: leaf + 7 levels + root
                        continue

                    try:
                        # Parse leaf value (column 0)
                        leaf_value = int(line[0].strip())

                        # Store hierarchy path: [level1, level2, ..., level7, root]
                        # Skip line[0] (leaf value itself) and take next 8 columns
                        hierarchy_path = [col.strip() for col in line[1:9]]

                        self._hierarchy_map[leaf_value] = hierarchy_path
                        valid_lines += 1
                    except ValueError as e:
                        logger.warning(f"⚠️ Failed to parse hierarchy line: {line} - {e}")

            self._is_loaded = True
            logger.info(f"✅ Loaded ECG hierarchy: {valid_lines} values ({self.MIN_ECG} to {self.MAX_ECG})")

            if valid_lines < 5000:
                logger.warning(f"⚠️ Warning: Expected ~5001 values, got {valid_lines}")

        except Exception as e:
            logger.error(f"❌ Failed to load ECG hierarchy: {e}")
            self._is_loaded = False
            raise

    def get_range_at_level(self, ecg_value: int, level: int) -> Optional[str]:
        """Get the range value for a specific ECG value at a specific level

        Args:
            ecg_value: Raw ECG value (-2500 to 2500)
            level: Hierarchy level (1=finest to 8=root)

        Returns:
            Range string (e.g., "-2500;-2499") or "*" for root, None if not found
        """
        if not self._is_loaded:
            return None
        if level < 1 or level > self.MAX_LEVEL:
            return None

        hierarchy_path = self._hierarchy_map.get(ecg_value)
        if hierarchy_path is None:
            return None

        # Level 1 is at index 0, Level 2 at index 1, etc.
        return hierarchy_path[level - 1]

    @property
    def is_loaded(self) -> bool:
        """Check if hierarchy is loaded"""
        return self._is_loaded

    @property
    def size(self) -> int:
        """Get total number of leaf values"""
        return len(self._hierarchy_map)


class LevelHierarchyEcgAnonymizer:
    """Level-by-Level ECG Anonymizer"""

    def __init__(self, k_value: int = 5):
        """Initialize the anonymizer

        Args:
            k_value: k-anonymity parameter (default: 5)
        """
        self.hierarchy = EcgHierarchy()
        self.k_value = k_value
        self._is_enabled = False

    def initialize(self, hierarchy_csv_path: str, k_value: Optional[int] = None, enabled: bool = True) -> None:
        """Initialize with settings and load hierarchy

        Args:
            hierarchy_csv_path: Path to the hierarchy CSV file
            k_value: k-anonymity parameter (optional, uses instance k_value if not provided)
            enabled: Enable/disable anonymization
        """
        if k_value is not None:
            self.k_value = k_value
        self._is_enabled = enabled

        # Load hierarchy from CSV
        self.hierarchy.load_from_csv(hierarchy_csv_path)

        logger.info(f"🔧 Level-by-Level ECG Anonymizer initialized: K={self.k_value}, "
                   f"Enabled={self._is_enabled}, Hierarchy loaded={self.hierarchy.is_loaded}")

    def anonymize_batch(self, records: List[EcgAnonymizationRecord]) -> List[EcgAnonymizationRecord]:
        """Anonymize a batch of ECG records using level-by-level approach

        This implements the logic:
        1. Sort records by ECG value
        2. For each level (1 to 8):
           - Replace raw values with level N ranges
           - Count identical ranges
           - Move records with count >= k to output
           - Continue with remaining records at next level
        3. Apply mean imputation

        Args:
            records: List of ECG anonymization records

        Returns:
            List of anonymized records
        """
        if not self._is_enabled or not self.hierarchy.is_loaded:
            # Return records unchanged
            for record in records:
                record.anonymized_range = str(record.original_ecg)
                record.assigned_level = 0  # No anonymization
            return records

        if not records:
            return records

        logger.info(f"Starting level-by-level anonymization for {len(records)} records (K={self.k_value})")

        # Step 1: Sort records by ECG value (small → large)
        sorted_records = sorted(records, key=lambda r: r.original_ecg)

        # Temporal box: stores records that have been successfully anonymized
        temporal_box: List[EcgAnonymizationRecord] = []

        # Working set: records still waiting to be anonymized
        working_set = sorted_records.copy()

        # Step 2-9: Try each level from 1 to 8
        for level in range(1, EcgHierarchy.MAX_LEVEL + 1):
            if not working_set:  # All records anonymized
                break

            # logger.debug(f"    Level {level}: Processing {len(working_set)} remaining records")

            # Step 3: Replace all raw values with range values of level N
            range_groups: Dict[str, List[EcgAnonymizationRecord]] = {}

            for record in working_set:
                range_value = self.hierarchy.get_range_at_level(record.original_ecg, level)

                if range_value is None:
                    # Value not in hierarchy - use suppression
                    logger.warning(f"⚠️ ECG {record.original_ecg} not found in hierarchy at level {level}")
                    if '*' not in range_groups:
                        range_groups['*'] = []
                    range_groups['*'].append(record)
                else:
                    if range_value not in range_groups:
                        range_groups[range_value] = []
                    range_groups[range_value].append(record)

            # Step 4-5: Count and check k-anonymity
            satisfied_records: List[EcgAnonymizationRecord] = []
            unsatisfied_records: List[EcgAnonymizationRecord] = []

            for range_value, records_in_group in range_groups.items():
                count = len(records_in_group)

                if count >= self.k_value:
                    # Step 6: Satisfies k-anonymity - move to temporal box
                    for record in records_in_group:
                        record.anonymized_range = range_value
                        record.assigned_level = level
                        satisfied_records.append(record)
                else:
                    # Doesn't satisfy k-anonymity yet - try next level
                    unsatisfied_records.extend(records_in_group)

            # Step 6: Move satisfied records to temporal box
            temporal_box.extend(satisfied_records)

            # Step 7-8: Check if any records left, prepare for next level
            working_set = unsatisfied_records

            if not working_set:
                # logger.debug(f"  ✅ All records satisfied at level {level}")
                break

            # Special case: If we reached max level and still have unsatisfied records
            # Suppress them with '*'
            if level == EcgHierarchy.MAX_LEVEL and working_set:
                logger.warning(f"  ⚠️ {len(working_set)} records still unsatisfied at max level - "
                             f"applying suppression (*)")
                for record in working_set:
                    record.anonymized_range = '*'
                    record.assigned_level = EcgHierarchy.MAX_LEVEL + 1  # Root suppression
                    temporal_box.append(record)
                working_set.clear()

        # Step 10: Sort by timestamp (restore original temporal order)
        temporal_box.sort(key=lambda r: r.timestamp)

        logger.info(f"  Anonymization complete: {len(temporal_box)} records anonymized")

        # Level distribution for debugging
        level_counts: Dict[int, int] = {}
        for record in temporal_box:
            level = record.assigned_level or 0
            level_counts[level] = level_counts.get(level, 0) + 1
        logger.info(f"  Level distribution: {level_counts}")

        return temporal_box

    @property
    def is_ready(self) -> bool:
        """Check if anonymizer is ready"""
        return self._is_enabled and self.hierarchy.is_loaded

    def get_settings(self) -> Dict:
        """Get current settings"""
        return {
            'k_value': self.k_value,
            'is_enabled': self._is_enabled,
            'hierarchy_loaded': self.hierarchy.is_loaded,
            'hierarchy_size': self.hierarchy.size,
        }
