"""
PerformanceService — per-group ML performance metrics using scikit-learn.
"""

import io
from typing import Any, Dict, List

import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

_GAP_THRESHOLD = 0.10          # flag when best-group minus worst-group > 10 pp
_REQUIRED_COLS = {"prediction", "ground_truth"}
_MIN_GROUP_SAMPLES = 5         # skip groups with fewer samples to avoid noisy metrics


def _safe_metrics(y_true, y_pred) -> Dict[str, float]:
    """Compute the four metrics; return NaN-safe rounded floats."""
    kw = dict(zero_division=0, average="weighted")
    return {
        "accuracy":  round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, **kw)), 4),
        "recall":    round(float(recall_score(y_true, y_pred, **kw)), 4),
        "f1":        round(float(f1_score(y_true, y_pred, **kw)), 4),
    }


def _gap_analysis(group_metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    """
    For each metric, find best and worst group, compute the gap, and flag if
    it exceeds *_GAP_THRESHOLD*.

    Returns a dict keyed by metric name.
    """
    metric_names = ["accuracy", "precision", "recall", "f1"]
    gaps: Dict[str, Any] = {}

    for metric in metric_names:
        scores = {
            grp: stats[metric]
            for grp, stats in group_metrics.items()
            if stats[metric] is not None
        }
        if not scores:
            gaps[metric] = None
            continue

        best_grp  = max(scores, key=lambda g: scores[g])
        worst_grp = min(scores, key=lambda g: scores[g])
        gap = round(scores[best_grp] - scores[worst_grp], 4)

        gaps[metric] = {
            "best_group":  best_grp,
            "best_score":  scores[best_grp],
            "worst_group": worst_grp,
            "worst_score": scores[worst_grp],
            "gap":         gap,
            "flagged":     gap > _GAP_THRESHOLD,
        }

    return gaps


class PerformanceService:
    def analyze(self, raw_bytes: bytes, protected_columns: List[str]) -> Dict[str, Any]:
        from app.utils.data_utils import normalize_dataframe_headers
        df = pd.read_csv(io.BytesIO(raw_bytes))
        df = normalize_dataframe_headers(df)
        return self.analyze_df(df, protected_columns)

    def analyze_df(self, df: pd.DataFrame, protected_columns: List[str]) -> Dict[str, Any]:
        """Compute performance metrics for a normalized DataFrame."""
        from app.utils.data_utils import normalize_string
        
        # --- validate required columns
        missing_required = _REQUIRED_COLS - set(df.columns)
        if missing_required:
            raise ValueError(f"Missing required columns: {sorted(missing_required)}")

        present_cols = []
        missing_cols = []
        available_cols = set(df.columns)
        
        for requested in protected_columns:
            norm_requested = normalize_string(requested)
            if norm_requested in available_cols:
                present_cols.append(norm_requested)
            else:
                # Substring fallback
                found = False
                for col in available_cols:
                    if norm_requested in col:
                        present_cols.append(col)
                        found = True
                        break
                if not found:
                    missing_cols.append(requested)

        overall_metrics = _safe_metrics(df["ground_truth"], df["prediction"])
        column_results: Dict[str, Any] = {}

        for col in present_cols:
            groups: Dict[str, Any] = {}
            skipped_groups: List[str] = []

            for group_val, subset in df.groupby(col, observed=True):
                label = str(group_val)
                n = len(subset)
                if n < _MIN_GROUP_SAMPLES:
                    skipped_groups.append(label)
                    continue

                metrics = _safe_metrics(subset["ground_truth"], subset["prediction"])
                groups[label] = {"count": n, **metrics}

            gaps = _gap_analysis(groups)
            any_flagged = any(info["flagged"] for info in gaps.values() if info is not None)

            column_results[col] = {
                "groups": groups,
                "skipped_groups": skipped_groups,
                "performance_gaps": gaps,
                "any_metric_flagged": any_flagged,
            }

        return {
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "columns_analyzed": present_cols,
            "missing_columns": missing_cols,
            "overall_metrics": overall_metrics,
            "gap_threshold": _GAP_THRESHOLD,
            "results": column_results,
        }
