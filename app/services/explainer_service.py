"""
ExplainerService — SHAP-based feature importance.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

from app.services.audit_service import _sessions


class ExplainerService:
    def explain(self, request) -> Dict[str, Any]:
        """
        Train a simple gradient-boosted model and compute SHAP values.
        Returns mean |SHAP| values per feature.
        """
        import shap
        from sklearn.ensemble import GradientBoostingClassifier

        df: pd.DataFrame = _sessions.get(request.session_id)
        if df is None:
            raise KeyError(f"Session '{request.session_id}' not found.")

        feature_cols = request.feature_columns or [
            c for c in df.columns if c != request.target_column
        ]

        X = df[feature_cols].fillna(0)
        y = df[request.target_column]

        # Encode any remaining object columns
        X = X.apply(lambda col: col.astype("category").cat.codes if col.dtype == "object" else col)

        # Train a quick model
        model = GradientBoostingClassifier(n_estimators=50, random_state=42)
        model.fit(X, y)

        # SHAP background sample
        background = shap.sample(X, min(request.num_samples, len(X)))
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(background)

        # For binary classifiers shap_values may be a list
        if isinstance(shap_values, list):
            sv = shap_values[1]
        else:
            sv = shap_values

        mean_abs = np.abs(sv).mean(axis=0).tolist()
        importance = dict(zip(feature_cols, [round(v, 6) for v in mean_abs]))
        sorted_importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        return {
            "session_id": request.session_id,
            "target_column": request.target_column,
            "feature_importance": sorted_importance,
            "method": "SHAP TreeExplainer (GradientBoostingClassifier)",
        }
