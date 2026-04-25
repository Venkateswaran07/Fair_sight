"""
InstanceExplainerService — single-row SHAP explanation using a RandomForestClassifier.

Workflow
--------
1. Read CSV → training DataFrame
2. Separate features (X) from target (y)
3. Encode categorical columns via pandas Categorical + consistent code mapping
4. Train a RandomForestClassifier (fast, tree-based — perfect for TreeExplainer)
5. Transform the user-supplied instance with the *same* encoding
6. Compute SHAP values via shap.TreeExplainer for the instance
7. Return the top-N features sorted by |SHAP value|, with contribution_percent
"""

import io
import json
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier

_DEFAULT_TOP_N = 5
_RF_PARAMS = dict(n_estimators=100, random_state=42, n_jobs=None)


# ── Categorical encoding helpers ───────────────────────────────────────────

def _fit_encoding(X_train: pd.DataFrame):
    """
    For every object/category column build a {label: code} map fitted on
    the training data.  Unknown values at inference time fall back to -1.

    Returns
    -------
    encoding_map : dict[col_name, dict[value, int]]
    """
    encoding_map: Dict[str, Dict[Any, int]] = {}
    for col in X_train.select_dtypes(include=["object", "category"]).columns:
        cats = X_train[col].astype("category").cat.categories.tolist()
        encoding_map[col] = {val: idx for idx, val in enumerate(cats)}
    return encoding_map


def _apply_encoding(X: pd.DataFrame, encoding_map: Dict[str, Dict[Any, int]]) -> pd.DataFrame:
    """Apply a pre-fitted encoding map; missing values → NaN → 0."""
    X = X.copy()
    for col, mapping in encoding_map.items():
        if col in X.columns:
            X[col] = X[col].map(mapping).fillna(-1).astype(int)
    return X.fillna(0)


def _coerce_instance(
    raw: Dict[str, Any],
    feature_cols: List[str],
    encoding_map: Dict[str, Dict[Any, int]],
    df_train: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a single-row DataFrame from *raw*, keeping only *feature_cols*.
    Missing feature values default to 0; categorical encoding is applied.
    """
    from app.utils.data_utils import translate_value_to_numeric
    row = {}
    for col in feature_cols:
        val = raw.get(col, 0)
        # Try to translate string inputs (like 'male') to numeric if needed
        if col in df_train.columns:
            val = translate_value_to_numeric(val, df_train[col])
        row[col] = val
        
    df = pd.DataFrame([row])
    df = _apply_encoding(df, encoding_map)
    return df


# ── Service ────────────────────────────────────────────────────────────────

class InstanceExplainerService:
    def explain(
        self,
        raw_bytes: bytes,
        target_column: str,
        instance_raw: str,          # JSON-encoded dict
        top_n: int = _DEFAULT_TOP_N,
    ) -> Dict[str, Any]:
        """
        Parameters
        ----------
        raw_bytes
            Raw bytes of the uploaded training CSV.
        target_column
            Name of the label/target column.
        instance_raw
            JSON string representing the single row to explain,
            e.g. '{"age": 35, "income": 50000, "gender": "Male"}'.
        top_n
            Number of top features to return (default 5).

        Returns
        -------
        dict
            {
              "target_column": str,
              "model": "RandomForestClassifier",
              "predicted_class": int | str,
              "predicted_proba": float,
              "num_training_rows": int,
              "top_features": [
                {
                  "rank": 1,
                  "feature": "income",
                  "shap_value": 0.123,      # + toward approval, - toward rejection
                  "contribution_percent": 34.5,
                },
                ...
              ]
            }

        Raises
        ------
        ValueError
            On missing target column, bad instance JSON, or mismatched features.
        """
        # --- Re-applying Smart Mapping (Force Reload) ---
        from app.utils.data_utils import normalize_dataframe_headers, normalize_string, normalize_dictionary_keys
        df = pd.read_csv(io.BytesIO(raw_bytes))
        df = normalize_dataframe_headers(df)
        
        # Normalize requested target string
        target_column = normalize_string(target_column)

        if target_column not in df.columns:
            raise ValueError(
                f"Target column '{target_column}' not found in CSV. "
                f"Available columns: {list(df.columns)}"
            )

        # ── Feature Selection (Prevent Leakage) ──────────────────────────
        # Drop the target AND any other columns that look like outcomes
        outcome_keywords = {"ground_truth", "prediction", "outcome", "decision", "label", "target", "status"}
        feature_cols = [
            c for c in df.columns 
            if c != target_column and normalize_string(c) not in outcome_keywords
        ]
        
        if not feature_cols:
            raise ValueError("No feature columns found after removing the target and outcome-like columns.")

        X_train = df[feature_cols].copy()
        
        # ── Target Normalization (Fix Flipping) ──────────────────────────
        _y = df[target_column].copy()
        
        # 1. Auto-bin continuous targets
        if pd.api.types.is_numeric_dtype(_y) and _y.nunique() > 5:
            median_val = _y.median()
            _y = (_y > median_val).astype(int)
            print(f"[InstanceExplainer] Auto-binned continuous target '{target_column}' at median {median_val}")
            
        # 2. Smart-encode string targets (e.g., 'Yes'/'No', 'Approved'/'Rejected')
        elif not pd.api.types.is_numeric_dtype(_y):
            unique_labels = [str(x).strip() for x in _y.dropna().unique()]
            
            # Detect positive label
            pos_keywords = {"yes", "y", "approved", "hired", "true", "1", "pass", "success"}
            pos_label = None
            for lbl in unique_labels:
                if lbl.lower() in pos_keywords:
                    pos_label = lbl
                    break
            
            if pos_label is not None:
                # Map the detected positive label to 1, everything else to 0
                _y = _y.apply(lambda x: 1 if str(x).strip() == pos_label else 0)
                print(f"[InstanceExplainer] Smart-mapped '{pos_label}' to 1 (Positive) for column '{target_column}'")
            else:
                # Fallback to alphabetical if no keywords found
                unique_labels.sort()
                label_map = {lbl: i for i, lbl in enumerate(unique_labels)}
                _y = _y.map(label_map)
                print(f"[InstanceExplainer] Fallback label-encoding for '{target_column}': {label_map}")

        y_train = _y.astype(int)

        # ── Parse instance ───────────────────────────────────────────────
        try:
            instance_dict: Dict[str, Any] = json.loads(instance_raw)
            if not isinstance(instance_dict, dict):
                raise ValueError
            # Smart Map the applicant's columns too!
            instance_dict = normalize_dictionary_keys(instance_dict)
        except (json.JSONDecodeError, ValueError):
            raise ValueError(
                "instance must be a valid JSON object, "
                'e.g. \'{"age": 35, "income": 50000, "gender": "Male"}\''
            )

        # ── Encode categoricals ──────────────────────────────────────────
        encoding_map = _fit_encoding(X_train)
        X_encoded = _apply_encoding(X_train, encoding_map)

        # ── Train RandomForest ───────────────────────────────────────────
        model = RandomForestClassifier(**_RF_PARAMS)
        model.fit(X_encoded, y_train)

        # ── Prepare instance ─────────────────────────────────────────────
        instance_df = _coerce_instance(instance_dict, feature_cols, encoding_map, df)

        # Predict for context
        pred_class = model.predict(instance_df)[0]
        pred_proba = float(model.predict_proba(instance_df)[0].max())

        # ── SHAP TreeExplainer ───────────────────────────────────────────
        explainer = shap.TreeExplainer(model)
        raw_shap = explainer.shap_values(instance_df)

        # For binary classifiers, shap_values structural format varies by shap version
        if isinstance(raw_shap, list):
            # Old format: list [class0_vals, class1_vals] each of shape (n_samples, n_features)
            sv = np.array(raw_shap[1][0], dtype=float)
        elif len(raw_shap.shape) == 3:
            # New format: array of shape (n_samples, n_features, n_classes)
            sv = np.array(raw_shap[0, :, 1], dtype=float)
        else:
            # Fallback
            sv = np.array(raw_shap[0], dtype=float)

        # ── Rank by |SHAP| ───────────────────────────────────────────────
        total_abs = float(np.abs(sv).sum())
        if total_abs == 0:
            total_abs = 1.0  # avoid division by zero for constant models

        ranked = sorted(
            zip(feature_cols, sv.tolist()),
            key=lambda pair: abs(pair[1]),
            reverse=True,
        )
        top_features = []
        for rank, (feat, val) in enumerate(ranked[:top_n], start=1):
            top_features.append(
                {
                    "rank": rank,
                    "feature": feat,
                    "shap_value": round(val, 6),
                    "contribution_percent": round(abs(val) / total_abs * 100, 2),
                    "direction": "toward approval" if val >= 0 else "toward rejection",
                }
            )

        return {
            "target_column": target_column,
            "model": "RandomForestClassifier",
            "predicted_class": (
                int(pred_class)
                if isinstance(pred_class, (np.integer,))
                else str(pred_class)
            ),
            "predicted_proba": round(pred_proba, 4),
            "num_training_rows": len(df),
            "num_features": len(feature_cols),
            "top_n_requested": top_n,
            "top_features": top_features,
        }
