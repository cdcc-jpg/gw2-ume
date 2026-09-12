"""Stage 2: Value-Based Column Classification.

Zero Domain Semantics in Python: Rules operate purely on cell VALUES, never on header names.
Computes column statistics:
- uniqueness_ratio: unique_non_empty / total_non_empty
- id_shape_ratio: UUID or structured ID pattern match ratio
- numeric_ratio: parseable as integer or float ratio
- avg_str_len: mean string length
- cardinality: distinct count of non-empty values
- timestamp_ratio: datetime parseable ratio
- measurement_ratio: number + unit patterns

Assigns one structural role per column:
- Entity ID
- Foreign Key
- Measurement value/unit pair
- Numeric property
- Categorical
- Text
- Timestamp
- Skip
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


@dataclass
class ColumnStats:
    """Statistical summary of column values with zero header bias."""
    column_name: str
    total_count: int
    non_empty_count: int
    cardinality: int
    uniqueness_ratio: float
    id_shape_ratio: float
    numeric_ratio: float
    avg_str_len: float
    timestamp_ratio: float
    measurement_ratio: float
    sample_values: List[str] = field(default_factory=list)


@dataclass
class ColumnRole:
    """Assigned structural role and supporting statistics for a column."""
    column_name: str
    role: str  # Entity ID, Foreign Key, Measurement, Numeric property, Categorical, Text, Timestamp, Skip
    confidence: float
    stats: ColumnStats
    unit: Optional[str] = None


# Regex patterns for value shapes
UUID_REGEX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
STRUCTURED_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]+[:#_-][A-Za-z0-9_-]+$|^\d{4,12}$|^[&\[][A-Za-z0-9+/=]{4,}[&\]]?$")
MEASUREMENT_REGEX = re.compile(r"^-?\d+(?:\.\d+)?\s*([A-Za-z%°/]+)$")
ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$")


def is_id_shaped(val: str) -> bool:
    """Check if value has ID-like structure."""
    s = val.strip()
    if not s:
        return False
    if UUID_REGEX.match(s):
        return True
    if STRUCTURED_ID_REGEX.match(s):
        return True
    # Pure integer code with leading zeros or fixed digits
    if s.isdigit() and len(s) >= 4:
        return True
    return False


def is_numeric_value(val: str) -> bool:
    """Check if string represents an int or float."""
    s = val.strip().replace(",", "")
    try:
        float(s)
        return True
    except ValueError:
        return False


def is_timestamp_value(val: str) -> bool:
    """Check if value is parseable as date or datetime."""
    s = val.strip()
    if not s or len(s) < 8:
        return False
    if ISO_DATE_REGEX.match(s):
        return True
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            pass
    return False


def is_measurement_value(val: str) -> Tuple[bool, Optional[str]]:
    """Check if value is a number + unit string (e.g. '100 kg', '25.4 eV')."""
    s = val.strip()
    m = MEASUREMENT_REGEX.match(s)
    if m:
        unit = m.group(1)
        # Exclude common false positives like hex or pure words
        if len(unit) <= 8 and not unit.isdigit():
            return True, unit
    return False, None


def compute_column_stats(col_name: str, values: Sequence[Any]) -> ColumnStats:
    """Compute value-only statistics for a column."""
    str_values = []
    for v in values:
        if pd.isna(v) or v is None:
            continue
        s = str(v).strip()
        if s and s.lower() not in ("nan", "none", "null", ""):
            str_values.append(s)

    total_count = len(values)
    non_empty_count = len(str_values)
    if non_empty_count == 0:
        return ColumnStats(
            column_name=col_name,
            total_count=total_count,
            non_empty_count=0,
            cardinality=0,
            uniqueness_ratio=0.0,
            id_shape_ratio=0.0,
            numeric_ratio=0.0,
            avg_str_len=0.0,
            timestamp_ratio=0.0,
            measurement_ratio=0.0,
            sample_values=[],
        )

    unique_vals = set(str_values)
    cardinality = len(unique_vals)
    uniqueness_ratio = cardinality / non_empty_count

    id_count = sum(1 for v in str_values if is_id_shaped(v))
    num_count = sum(1 for v in str_values if is_numeric_value(v))
    ts_count = sum(1 for v in str_values if is_timestamp_value(v))
    meas_count = sum(1 for v in str_values if is_measurement_value(v)[0])

    avg_len = sum(len(v) for v in str_values) / non_empty_count
    sample_values = list(unique_vals)[:5]

    return ColumnStats(
        column_name=col_name,
        total_count=total_count,
        non_empty_count=non_empty_count,
        cardinality=cardinality,
        uniqueness_ratio=uniqueness_ratio,
        id_shape_ratio=id_count / non_empty_count,
        numeric_ratio=num_count / non_empty_count,
        avg_str_len=avg_len,
        timestamp_ratio=ts_count / non_empty_count,
        measurement_ratio=meas_count / non_empty_count,
        sample_values=sample_values,
    )


class ValueClassifier:
    """Stage 2 Column Classifier: assigns structural roles with zero header bias."""

    def classify_table(self, df: pd.DataFrame) -> Dict[str, ColumnRole]:
        """Classifies each column in a DataFrame."""
        stats_map = {col: compute_column_stats(str(col), df[col].tolist()) for col in df.columns}
        
        # Identify candidate Entity IDs
        # Highest-uniqueness ID-shaped or unique integer column is prioritized as Entity ID
        candidate_pks = []
        for col, s in stats_map.items():
            if s.non_empty_count > 0 and s.uniqueness_ratio >= 0.85:
                if s.id_shape_ratio >= 0.70:
                    candidate_pks.append((col, s.uniqueness_ratio, 2.0))
                elif s.numeric_ratio >= 0.85 and s.avg_str_len <= 12:
                    candidate_pks.append((col, s.uniqueness_ratio, 1.5))
                elif s.avg_str_len <= 60:
                    candidate_pks.append((col, s.uniqueness_ratio, 1.0))

        # Sort candidate PKs by priority score then uniqueness descending
        candidate_pks.sort(key=lambda x: (x[2], x[1]), reverse=True)
        primary_entity_col = candidate_pks[0][0] if candidate_pks else None

        results: Dict[str, ColumnRole] = {}
        for col, s in stats_map.items():
            role_obj = self._assign_role(s, is_primary_id=(col == primary_entity_col))
            results[col] = role_obj

        return results

    def _assign_role(self, s: ColumnStats, is_primary_id: bool) -> ColumnRole:
        """Assign role based on statistical value thresholds."""
        if s.non_empty_count == 0:
            return ColumnRole(s.column_name, "Skip", 1.0, s)

        # Constant value column or massive blob
        if s.cardinality == 1 and s.total_count > 3:
            return ColumnRole(s.column_name, "Skip", 0.95, s)
        if s.avg_str_len > 300:
            return ColumnRole(s.column_name, "Skip", 0.85, s)

        # Primary Entity ID
        if is_primary_id:
            return ColumnRole(s.column_name, "Entity ID", 0.98, s)

        # Repeating ID-shaped column -> Foreign Key
        if s.id_shape_ratio >= 0.70:
            if s.uniqueness_ratio >= 0.85:
                # Another high uniqueness ID column
                return ColumnRole(s.column_name, "Entity ID", 0.90, s)
            return ColumnRole(s.column_name, "Foreign Key", 0.92, s)

        # Timestamp
        if s.timestamp_ratio >= 0.80:
            return ColumnRole(s.column_name, "Timestamp", 0.95, s)

        # Measurement with explicit units
        if s.measurement_ratio >= 0.70:
            # Extract common unit
            units = [is_measurement_value(v)[1] for v in s.sample_values if is_measurement_value(v)[0]]
            common_unit = units[0] if units else None
            return ColumnRole(s.column_name, "Measurement value/unit pair", 0.90, s, unit=common_unit)

        # Numeric property
        if s.numeric_ratio >= 0.85:
            return ColumnRole(s.column_name, "Numeric property", 0.95, s)

        # Categorical: low cardinality (<= 25 or <= 35% of rows), reasonable string length
        # Must not be high uniqueness text (uniqueness > 0.50 with total_count >= 5 indicates distinct names/text)
        if s.avg_str_len <= 50:
            if s.uniqueness_ratio <= 0.35:
                return ColumnRole(s.column_name, "Categorical", 0.90, s)
            if s.cardinality <= 25 and (s.total_count < 5 or s.uniqueness_ratio <= 0.50):
                return ColumnRole(s.column_name, "Categorical", 0.90, s)

        # Free-form text
        return ColumnRole(s.column_name, "Text", 0.85, s)
