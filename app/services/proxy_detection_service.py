"""
ProxyDetectionService — identify non-protected features that act as proxies
for protected attributes.

For every non-protected column the service computes, against each protected column:

  Pearson correlation
      abs(r)  — only meaningful for numeric × numeric pairs.
      Categorical columns are label-encoded before the correlation is taken.

  Mutual Information (MI, normalised)
      Uses sklearn.feature_selection.mutual_info_classif.
      Raw MI is normalised by H(protected_col) so the result lies in [0, 1].
      A value of 1.0 means the feature perfectly predicts the protected attribute.

  proxy_risk_score (per protected column)
      max(abs_pearson, normalised_MI)

  Overall proxy_risk_score (per feature)
      max across all protected columns

  Risk flag
      proxy_risk_score > 0.3  →  HIGH RISK
"""

import io
import warnings
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import entropy as scipy_entropy
from sklearn.feature_selection import mutual_info_classif

_PROXY_THRESHOLD = 0.3


# ── Encoding helper ────────────────────────────────────────────────────────

def _to_numeric(series: pd.Series) -> pd.Series:
    """
    Convert a series to numeric codes.
    Numeric series are returned as-is (NaN → 0).
    Object/bool series are label-encoded.
    """
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float)
    
    # Force to series if it's a single-column DataFrame
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
        
    return series.astype("category").cat.codes.astype(float)


# ── Entropy helper (for MI normalisation) ─────────────────────────────────

def _column_entropy(series: pd.Series) -> float:
    """Compute Shannon entropy (nats) of a discrete series."""
    counts = series.value_counts(normalize=True).values
    return float(scipy_entropy(counts))       # scipy uses natural log by default


# ── Service ────────────────────────────────────────────────────────────────

class ProxyDetectionService:
    def analyze(self, raw_bytes: bytes, protected_columns: List[str]) -> Dict[str, Any]:
        from app.utils.data_utils import normalize_dataframe_headers
        df = pd.read_csv(io.BytesIO(raw_bytes))
        df = normalize_dataframe_headers(df)
        return self.analyze_df(df, protected_columns)

    def analyze_df(self, df: pd.DataFrame, protected_columns: List[str]) -> Dict[str, Any]:
        """Detect proxy features in a normalized DataFrame."""
        from app.utils.data_utils import normalize_string
        
        # Normalize requested column names
        norm_protected_cols = [normalize_string(c) for c in protected_columns]
        present_protected = [c for c in norm_protected_cols if c in df.columns]
        missing_protected = [c for c in norm_protected_cols if c not in df.columns]

        if not present_protected:
            return {"missing_protected": missing_protected, "features": [], "high_risk_features": []}

        non_protected_cols = [c for c in df.columns if c not in norm_protected_cols and c not in ("prediction", "ground_truth")]

        # Limit mutual information to first 10k rows to avoid memory/timeout crashes on large datasets
        # This still provides a very strong statistical signal.
        sample_df = df.head(10000) if len(df) > 10000 else df

        encoded = {col: _to_numeric(sample_df[col]) for col in sample_df.columns}
        prot_entropy = {col: _column_entropy(sample_df[col]) for col in present_protected}

        feature_rows = []
        for feat in non_protected_cols:
            feat_enc = encoded[feat].values.reshape(-1, 1)
            feat_series = encoded[feat]
            per_protected = {}
            all_scores = []

            for prot in present_protected:
                prot_enc = encoded[prot]
                pearson = abs(float(feat_series.corr(prot_enc)))
                if np.isnan(pearson): pearson = 0.0

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    mi_raw = float(mutual_info_classif(feat_enc, prot_enc.values, discrete_features=False, random_state=42)[0])

                h = prot_entropy[prot]
                mi_norm = max(0.0, min(mi_raw / h, 1.0)) if h > 0 else 0.0
                pair_score = round(max(pearson, mi_norm), 4)
                all_scores.append(pair_score)

                per_protected[prot] = {
                    "pearson_correlation": round(pearson, 4),
                    "mutual_information_normalised": round(mi_norm, 4),
                    "proxy_risk_score": pair_score,
                }

            overall_score = round(max(all_scores) if all_scores else 0.0, 4)
            flagged = overall_score > _PROXY_THRESHOLD
            feature_rows.append({
                "feature": feat,
                "proxy_risk_score": overall_score,
                "risk_level": "HIGH RISK" if flagged else "LOW RISK",
                "flagged": flagged,
                "per_protected_column": per_protected,
            })

        feature_rows.sort(key=lambda r: r["proxy_risk_score"], reverse=True)
        high_risk = [r["feature"] for r in feature_rows if r["flagged"]]

        return {
            "num_rows": len(df),
            "num_features_analyzed": len(non_protected_cols),
            "protected_columns_found": present_protected,
            "missing_columns": missing_protected,
            "proxy_risk_threshold": _PROXY_THRESHOLD,
            "high_risk_features": high_risk,
            "num_high_risk": len(high_risk),
            "features": feature_rows,
        }
