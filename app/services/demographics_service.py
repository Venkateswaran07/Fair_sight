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
        """
        Read a CSV from *raw_bytes* and compute demographic statistics for each
        column listed in *protected_columns*.

        Returns
        -------
        {
          "num_rows": int,
          "num_columns": int,
          "columns_analyzed": [...],
          "missing_columns": [...],          # requested cols absent in CSV
          "results": {
            "<col>": {
              "value_counts": {"val": count, ...},
              "percentages":  {"val": 12.34, ...},
              "representation_score": 0.xx,  # min% / max%  (0..1, 1 = perfect balance)
              "underrepresented_groups": ["val", ...],
              "has_underrepresentation": bool
            }
          }
        }
        """
        df = pd.read_csv(io.BytesIO(raw_bytes))

        present_cols = [c for c in protected_columns if c in df.columns]
        missing_cols = [c for c in protected_columns if c not in df.columns]

        results: Dict[str, Any] = {}

        for col in present_cols:
            series = df[col].dropna()
            total = len(series)

            # Raw counts
            vc = series.value_counts()
            value_counts = {str(k): int(v) for k, v in vc.items()}

            # Percentages (rounded to 2 dp)
            pct = (vc / total * 100).round(2)
            percentages = {str(k): float(v) for k, v in pct.items()}

            # Representation score: min% / max%  → 1.0 means perfectly balanced
            pct_values = list(percentages.values())
            if len(pct_values) >= 2:
                rep_score = round(min(pct_values) / max(pct_values), 4)
            else:
                rep_score = 1.0  # only one group — trivially "equal"

            # Under-representation flag
            underrep_groups = [
                grp for grp, p in percentages.items() if p < _UNDERREP_THRESHOLD
            ]

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
