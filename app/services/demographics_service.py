"""
DemographicsService — per-column distribution analysis for protected attributes.
"""

import io
import json
from typing import Any, Dict, List

import pandas as pd

_UNDERREP_THRESHOLD = 10.0  # percentage


class DemographicsService:
    def analyze(self, raw_bytes: bytes, protected_columns: List[str]) -> Dict[str, Any]:
        from app.utils.data_utils import normalize_dataframe_headers
        df = pd.read_csv(io.BytesIO(raw_bytes))
        df = normalize_dataframe_headers(df)
        return self.analyze_df(df, protected_columns)

    def analyze_df(self, df: pd.DataFrame, protected_columns: List[str]) -> Dict[str, Any]:
        """Compute demographic statistics for each column in protected_columns."""
        from app.utils.data_utils import normalize_string
        
        # Normalize requested column names
        norm_protected_cols = [normalize_string(c) for c in protected_columns]

        present_cols = [c for c in norm_protected_cols if c in df.columns]
        missing_cols = [c for c in norm_protected_cols if c not in df.columns]

        results: Dict[str, Any] = {}

        for col in present_cols:
            series = df[col].dropna()
            total = len(series)
            if total == 0: continue

            # Raw counts
            vc = series.value_counts()
            value_counts = {str(k): int(v) for k, v in vc.items()}

            # Percentages
            pct = (vc / total * 100).round(2)
            percentages = {str(k): float(v) for k, v in pct.items()}

            # Representation score
            pct_values = list(percentages.values())
            rep_score = round(min(pct_values) / max(pct_values), 4) if len(pct_values) >= 2 else 1.0

            underrep_groups = [grp for grp, p in percentages.items() if p < _UNDERREP_THRESHOLD]

            results[col] = {
                "value_counts": value_counts,
                "percentages": percentages,
                "representation_score": rep_score,
                "underrepresented_groups": underrep_groups,
                "has_underrepresentation": len(underrep_groups) > 0,
            }

        return {
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "columns_analyzed": present_cols,
            "missing_columns": missing_cols,
            "results": results,
        }
