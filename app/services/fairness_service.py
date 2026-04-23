"""
FairnessService — group-level fairness metrics for a binary protected attribute.

Metrics computed
----------------
- Demographic Parity Difference (DPD) : abs(approval_rate_A – approval_rate_B)
- Equal Opportunity Difference  (EOD) : abs(TPR_A – TPR_B)
- Disparate Impact Ratio        (DIR) : min_approval_rate / max_approval_rate

Thresholds (configurable at top of file)
-----------------------------------------
- DPD > 0.10 → FAIL
- EOD > 0.10 → FAIL
- DIR < 0.80 → FAIL
"""

import io
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ── Fairness thresholds ────────────────────────────────────────────────────
_DPD_THRESHOLD = 0.10   # Demographic Parity Difference
_EOD_THRESHOLD = 0.10   # Equal Opportunity Difference
_DIR_THRESHOLD = 0.80   # Disparate Impact Ratio (lower-bound)

_REQUIRED_COLS = {"prediction", "ground_truth"}

_CONFLICT_WARNING = (
    "Both Demographic Parity Difference (DPD) and Equal Opportunity Difference (EOD) "
    "are failing simultaneously. This indicates a tension between two different fairness "
    "definitions: DPD requires equal positive-prediction rates across groups regardless of "
    "actual outcomes, while EOD requires equal true-positive rates (sensitivity) across groups. "
    "Satisfying both simultaneously is mathematically impossible when base rates differ between "
    "groups (Chouldechova 2017 / Kleinberg et al. 2016). Review which fairness criterion is "
    "most appropriate for your use-case before taking corrective action."
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _coerce_label(raw: str, series: pd.Series):
    """
    Try to cast *raw* (a form string) to match the dtype of *series*.
    Handles int, float, bool, and string labels gracefully.
    """
    if pd.api.types.is_integer_dtype(series):
        return int(raw)
    if pd.api.types.is_float_dtype(series):
        return float(raw)
    if pd.api.types.is_bool_dtype(series):
        return raw.lower() in ("1", "true", "yes")
    return raw   # string


def _approval_rate(subset: pd.DataFrame, pos_label) -> float:
    """Fraction of rows where prediction == pos_label."""
    return float((subset["prediction"] == pos_label).mean())


def _tpr(subset: pd.DataFrame, pos_label) -> Optional[float]:
    """
    True-Positive Rate = TP / (TP + FN).
    Returns None when no positive ground-truth rows exist in the subset.
    """
    positives = subset[subset["ground_truth"] == pos_label]
    if len(positives) == 0:
        return None
    return float((positives["prediction"] == pos_label).mean())


def _metric_block(value: float, threshold: float, flag_above: bool) -> Dict[str, Any]:
    """Build the standard metric sub-dict."""
    rounded = round(value, 4)
    flagged = (rounded > threshold) if flag_above else (rounded < threshold)
    return {
        "value": rounded,
        "threshold": threshold,
        "flagged": flagged,
        "result": "FAIL" if flagged else "PASS",
    }


# ── Service ────────────────────────────────────────────────────────────────

class FairnessService:
    def analyze(
        self,
        raw_bytes: bytes,
        protected_column: str,
        positive_label_raw: str = "1",
    ) -> Dict[str, Any]:
        """
        Parameters
        ----------
        raw_bytes
            Raw bytes of the uploaded CSV.
        protected_column
            Name of the column containing the binary protected attribute.
        positive_label_raw
            String form of the positive (favourable) class label.
            Converted to match the actual column dtype automatically.

        Returns
        -------
        dict
            Full fairness audit result ready for JSON serialisation.

        Raises
        ------
        ValueError
            On missing/invalid columns or non-binary protected attribute.
        """
        from app.utils.data_utils import normalize_dataframe_headers, normalize_string
        df = pd.read_csv(io.BytesIO(raw_bytes))
        df = normalize_dataframe_headers(df)

        # Normalize requested column names
        norm_protected_cols = [normalize_string(c) for c in [protected_column]]

        present_cols = [c for c in norm_protected_cols if c in df.columns]
        missing_cols = [c for c in norm_protected_cols if c not in df.columns]

        # ── Validate required columns ───────────────────────────────────
        missing_req = _REQUIRED_COLS - set(df.columns)
        if missing_req:
            raise ValueError(
                f"CSV is missing required column(s): {sorted(missing_req)}. "
                "The file must contain 'prediction' and 'ground_truth' columns."
            )
        
        # ── Flexible Column Lookup ──────────────────────────────────────
        # The SmartMapper might have renamed 'sex' to 'gender' or 'dob' to 'age'.
        # We need to find the column the user *meant* even if it was renamed.
        available_cols = list(df.columns)
        actual_col = None
        
        # 1. Try exact match (normalized)
        norm_requested = normalize_string(protected_column)
        if norm_requested in available_cols:
            actual_col = norm_requested
        
        # 2. Try common mappings if not found
        if not actual_col:
            mappings_map = {
                "gender": ["sex", "m_f", "gender"],
                "age": ["dob", "birth", "age"],
                "race": ["ethnicity", "race"]
            }
            for std, synonyms in mappings_map.items():
                if norm_requested in synonyms and std in available_cols:
                    actual_col = std
                    break
        
        # 3. Fallback: search for any column that contains the requested name
        if not actual_col:
            for col in available_cols:
                if norm_requested in col:
                    actual_col = col
                    break
                    
        if not actual_col:
            raise ValueError(
                f"Protected column '{protected_column}' not found in CSV. "
                f"Available columns: {available_cols}"
            )
        
        protected_column = actual_col

        # ── Group Protected Attribute ───────────────────────────────────
        unique_vals = df[protected_column].dropna().unique().tolist()
        
        # 1. Auto-bin continuous numeric attributes at the median
        if len(unique_vals) > 2 and pd.api.types.is_numeric_dtype(df[protected_column]):
            median_val = df[protected_column].median()
            df[protected_column] = df[protected_column].apply(
                lambda x: f"≤{int(median_val)}" if x <= median_val else f">{int(median_val)}"
            )
            print(f"[FairnessService] Auto-binned numeric '{protected_column}' at median {median_val}")
            unique_vals = df[protected_column].unique().tolist()

        # 2. For non-numeric categoricals with > 2 groups, pick Top-1 vs Rest
        elif len(unique_vals) > 2:
            counts = df[protected_column].value_counts()
            majority_val = counts.index[0]
            df[protected_column] = df[protected_column].apply(
                lambda x: str(x) if x == majority_val else "Other"
            )
            print(f"[FairnessService] Grouped categorical '{protected_column}' as '{majority_val}' vs 'Other'")
            unique_vals = df[protected_column].unique().tolist()

        # ── Validate result is binary ───────────────────────────────────
        if len(unique_vals) < 2:
             raise ValueError(f"Protected column '{protected_column}' must have at least 2 groups to compare.")

        # ── Coerce positive label ───────────────────────────────────────
        # Try to find the provided label; if missing, look for common positives (Approved, Yes, 1)
        potential_positives = [positive_label_raw, "Approved", "Yes", "Status_1", "1", 1]
        pos_label = None
        
        for p in potential_positives:
            try:
                coerced = _coerce_label(str(p), df["prediction"])
                if coerced in df["prediction"].values:
                    pos_label = coerced
                    break
            except: continue
            
        if pos_label is None:
            # Last resort: just pick the label that appears in predictions
            pos_label = df["prediction"].mode()[0]
            print(f"[FairnessService] Could not find requested positive label. Auto-selected '{pos_label}'.")

        # Sort group labels for deterministic ordering
        group_labels = sorted([str(v) for v in unique_vals])
        group_a_label, group_b_label = group_labels[0], group_labels[1]

        grp_a = df[df[protected_column] == group_a_label]
        grp_b = df[df[protected_column] == group_b_label]

        # ── Per-group statistics ────────────────────────────────────────
        ar_a = _approval_rate(grp_a, pos_label)
        ar_b = _approval_rate(grp_b, pos_label)
        tpr_a = _tpr(grp_a, pos_label)
        tpr_b = _tpr(grp_b, pos_label)

        group_stats: Dict[str, Any] = {
            str(group_a_label): {
                "count": len(grp_a),
                "approval_rate": round(ar_a, 4),
                "tpr": round(tpr_a, 4) if tpr_a is not None else None,
            },
            str(group_b_label): {
                "count": len(grp_b),
                "approval_rate": round(ar_b, 4),
                "tpr": round(tpr_b, 4) if tpr_b is not None else None,
            },
        }

        # ── Compute metrics ─────────────────────────────────────────────
        dpd_value = abs(ar_a - ar_b)
        dir_value = (min(ar_a, ar_b) / max(ar_a, ar_b)) if max(ar_a, ar_b) > 0 else 1.0

        dpd = _metric_block(dpd_value, _DPD_THRESHOLD, flag_above=True)
        dpd["description"] = "abs(approval_rate_GroupA − approval_rate_GroupB)"

        dir_metric = _metric_block(dir_value, _DIR_THRESHOLD, flag_above=False)
        dir_metric["description"] = "min_approval_rate / max_approval_rate"

        # EOD requires non-None TPRs
        eod: Dict[str, Any]
        if tpr_a is not None and tpr_b is not None:
            eod_value = abs(tpr_a - tpr_b)
            eod = _metric_block(eod_value, _EOD_THRESHOLD, flag_above=True)
            eod["description"] = "abs(TPR_GroupA − TPR_GroupB)"
        else:
            eod = {
                "value": None,
                "threshold": _EOD_THRESHOLD,
                "flagged": False,
                "result": "N/A — no positive ground-truth rows in one or both groups",
                "description": "abs(TPR_GroupA − TPR_GroupB)",
            }

        # ── Overall pass/fail ───────────────────────────────────────────
        failing_metrics = [
            name
            for name, m in [("DPD", dpd), ("EOD", eod), ("DIR", dir_metric)]
            if m.get("flagged")
        ]
        overall_pass = len(failing_metrics) == 0

        # ── Conflict warning ────────────────────────────────────────────
        dpd_fails = dpd.get("flagged", False)
        eod_fails = eod.get("flagged", False)
        warning: Optional[str] = _CONFLICT_WARNING if (dpd_fails and eod_fails) else None

        return {
            "num_rows": len(df),
            "protected_column": protected_column,
            "positive_label": pos_label,
            "groups": [str(g) for g in group_labels],
            "group_stats": group_stats,
            "metrics": {
                "demographic_parity_difference": dpd,
                "equal_opportunity_difference": eod,
                "disparate_impact_ratio": dir_metric,
            },
            "failing_metrics": failing_metrics,
            "overall_pass": overall_pass,
            "warning": warning,
        }
