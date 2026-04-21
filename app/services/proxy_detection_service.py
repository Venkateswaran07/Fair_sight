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
    return series.astype("category").cat.codes.astype(float)


# ── Entropy helper (for MI normalisation) ─────────────────────────────────

def _column_entropy(series: pd.Series) -> float:
    """Compute Shannon entropy (nats) of a discrete series."""
    counts = series.value_counts(normalize=True).values
    return float(scipy_entropy(counts))       # scipy uses natural log by default


# ── Service ────────────────────────────────────────────────────────────────

class ProxyDetectionService:
    def analyze(
        self,
        raw_bytes: bytes,
        protected_columns: List[str],
    ) -> Dict[str, Any]:
        """
        Parameters
        ----------
        raw_bytes
            Raw bytes of the uploaded CSV.
        protected_columns
            List of column names to treat as protected attributes.

        Returns
        -------
        dict  (see module docstring for full schema)

        Raises
        ------
        ValueError
            When all requested protected columns are absent from the CSV.
        """
        df = pd.read_csv(io.BytesIO(raw_bytes))

        present_protected = [c for c in protected_columns if c in df.columns]
        missing_protected = [c for c in protected_columns if c not in df.columns]

        if not present_protected:
            raise ValueError(
                f"None of the requested protected columns were found in the CSV. "
                f"Requested: {protected_columns}. "
                f"Available: {list(df.columns)}"
            )

        non_protected_cols = [c for c in df.columns if c not in protected_columns]

        # Pre-compute numeric representations for every column used
        encoded: Dict[str, pd.Series] = {
            col: _to_numeric(df[col]) for col in df.columns
        }

        # Pre-compute entropy for each protected column (for MI normalisation)
        prot_entropy: Dict[str, float] = {
            col: _column_entropy(df[col]) for col in present_protected
        }

        feature_rows: List[Dict[str, Any]] = []

        for feat in non_protected_cols:
            feat_enc = encoded[feat].values.reshape(-1, 1)   # shape (n, 1)
            feat_series = encoded[feat]

            per_protected: Dict[str, Any] = {}
            all_scores: List[float] = []

            for prot in present_protected:
                prot_enc = encoded[prot]

                # ── Pearson correlation ─────────────────────────────────
                pearson = abs(float(feat_series.corr(prot_enc)))
                if np.isnan(pearson):
                    pearson = 0.0

                # ── Mutual Information ──────────────────────────────────
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    mi_raw = float(
                        mutual_info_classif(
                            feat_enc,
                            prot_enc.values,
                            discrete_features=False,
                            random_state=42,
                        )[0]
                    )

                # Normalise MI by H(protected); clamp to [0, 1]
                h = prot_entropy[prot]
                mi_norm = min(mi_raw / h, 1.0) if h > 0 else 0.0
                mi_norm = max(mi_norm, 0.0)

                # ── Per-protected proxy score ───────────────────────────
                pair_score = round(max(pearson, mi_norm), 4)
                all_scores.append(pair_score)

                per_protected[prot] = {
                    "pearson_correlation": round(pearson, 4),
                    "mutual_information_normalised": round(mi_norm, 4),
                    "proxy_risk_score": pair_score,
                }

            # ── Overall feature proxy score ─────────────────────────────
            overall_score = round(max(all_scores) if all_scores else 0.0, 4)
            flagged = overall_score > _PROXY_THRESHOLD

            feature_rows.append(
                {
                    "feature": feat,
                    "proxy_risk_score": overall_score,
                    "risk_level": "HIGH RISK" if flagged else "LOW RISK",
                    "flagged": flagged,
                    "per_protected_column": per_protected,
                }
            )

        # Sort descending by proxy_risk_score
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
