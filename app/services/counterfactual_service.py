"""
CounterfactualService — DiCE-ML counterfactual generation.
"""

import pandas as pd
from typing import Dict, Any, Tuple

from app.services.audit_service import _sessions


class CounterfactualService:
    def generate(self, request) -> Dict[str, Any]:
        """
        Train a scikit-learn model via DiCE and generate counterfactual examples.
        """
        import dice_ml  # type: ignore
        from dice_ml import Dice  # type: ignore
        from sklearn.ensemble import RandomForestClassifier

        df: pd.DataFrame = _sessions.get(request.session_id)
        if df is None:
            raise KeyError(f"Session '{request.session_id}' not found.")

        feature_cols = [c for c in df.columns if c != request.target_column]
        X = df[feature_cols]
        y = df[request.target_column]

        # Encode object columns
        X = X.apply(lambda col: col.astype("category").cat.codes if col.dtype == "object" else col)

        # Resolve features_to_vary
        if request.features_to_vary == "all":
            features_to_vary = feature_cols
        else:
            features_to_vary = [f.strip() for f in request.features_to_vary.split(",")]

        # DiCE data and model wrappers
        dice_data = dice_ml.Data(
            dataframe=pd.concat([X, y.rename(request.target_column)], axis=1),
            continuous_features=[c for c in feature_cols if X[c].dtype != "object"],
            outcome_name=request.target_column,
        )

        rf = RandomForestClassifier(n_estimators=50, random_state=42)
        rf.fit(X, y)

        dice_model = dice_ml.Model(model=rf, backend="sklearn")
        exp = Dice(dice_data, dice_model, method="random")

        query = pd.DataFrame([request.query_instance])
        query = query.apply(lambda col: col.astype("category").cat.codes if col.dtype == "object" else col)

        cf_results = exp.generate_counterfactuals(
            query,
            total_CFs=request.num_cfs,
            desired_class=request.desired_class,
            features_to_vary=features_to_vary,
        )

        cf_df = cf_results.cf_examples_list[0].final_cfs_df
        counterfactuals = cf_df.to_dict(orient="records") if cf_df is not None else []

        return {
            "session_id": request.session_id,
            "query_instance": request.query_instance,
            "num_cfs_generated": len(counterfactuals),
            "counterfactuals": counterfactuals,
        }
