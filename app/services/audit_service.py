"""
AuditService — fairness metrics via IBM AIF360.
"""

import io
import uuid
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any

# In-memory session store (replace with Redis / DB in production)
_sessions: Dict[str, pd.DataFrame] = {}


class AuditService:
    # ------------------------------------------------------------------
    # Dataset management
    # ------------------------------------------------------------------
    def store_dataset(self, raw_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Parse CSV bytes, perform smart mapping, store in memory."""
        from app.utils.data_utils import normalize_dataframe_headers
        df = pd.read_csv(io.BytesIO(raw_bytes))
        df = normalize_dataframe_headers(df, fast_mode=True) # Fast mode for UI preview
        session_id = str(uuid.uuid4())
        _sessions[session_id] = df
        
        # Return summary info for the UI preview
        return {
            "session_id": session_id,
            "headers": list(df.columns),
            "preview_rows": df.head(100).values.tolist(),
            "total_rows": len(df)
        }

    def get_dataset(self, session_id: str) -> pd.DataFrame:
        if session_id not in _sessions:
            raise KeyError(f"Session '{session_id}' not found. Please upload the dataset first.")
        return _sessions[session_id]

    # ------------------------------------------------------------------
    # Fairness audit
    # ------------------------------------------------------------------
    def run_audit(self, request) -> Dict[str, Any]:
        """
        Run AIF360 fairness metrics on the stored dataset.
        """
        from aif360.datasets import BinaryLabelDataset  # type: ignore
        from aif360.metrics import BinaryLabelDatasetMetric  # type: ignore
        from app.utils.data_utils import normalize_string

        df = self.get_dataset(request.session_id)
        
        # Normalize request parameters to match our smart-mapped columns
        target_col = normalize_string(request.target_column)
        protected_attrs = [normalize_string(attr) for attr in request.protected_attributes]

        # Build AIF360 BinaryLabelDataset
        bld = BinaryLabelDataset(
            df=df,
            label_names=[target_col],
            protected_attribute_names=protected_attrs,
            favorable_label=request.favorable_label,
            unfavorable_label=request.unfavorable_label,
        )

        # Normalize privileged/unprivileged groups as well
        unprivileged = [{normalize_string(k): v for k, v in g.items()} for g in request.unprivileged_groups]
        privileged = [{normalize_string(k): v for k, v in g.items()} for g in request.privileged_groups]

        metric = BinaryLabelDatasetMetric(
            bld,
            unprivileged_groups=unprivileged,
            privileged_groups=privileged,
        )

        results = {
            "session_id": request.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "protected_attributes": request.protected_attributes,
            "metrics": {
                "disparate_impact": round(metric.disparate_impact(), 4),
                "statistical_parity_difference": round(metric.statistical_parity_difference(), 4),
                "base_rate_privileged": round(metric.base_rate(privileged=True), 4),
                "base_rate_unprivileged": round(metric.base_rate(privileged=False), 4),
                "num_positives_privileged": int(metric.num_positives(privileged=True)),
                "num_positives_unprivileged": int(metric.num_positives(privileged=False)),
            },
            "fairness_assessment": self._assess_fairness(metric.disparate_impact()),
        }

        # Persist results to Firestore with Local Fallback
        try:
            from app.db import db
            db.collection("audit_history").document(request.session_id).set(results)
        except Exception as e:
            print(f"[Warning] Failed to save to Firestore: {e}. Saving to local JSON.")
            self._save_to_local_history(results)

        return results

    def get_history(self) -> list:
        """Fetch all audits from Firestore, with local JSON fallback."""
        history = []
        try:
            from app.db import db
            docs = db.collection("audit_history").order_by("timestamp", direction="DESCENDING").stream()
            history = [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"[Warning] Firestore fetch failed: {e}. Trying local history.")
            history = self._get_local_history()
            
        return history

    def _save_to_local_history(self, record: dict):
        """Helper to save audit to a local JSON file."""
        import json
        import os
        filename = "fairsight_history.json"
        history = self._get_local_history()
        history.insert(0, record) # Newest first
        with open(filename, "w") as f:
            json.dump(history, f, indent=2)

    def _get_local_history(self) -> list:
        """Helper to read audit history from a local JSON file."""
        import json
        import os
        filename = "fairsight_history.json"
        if os.path.exists(filename):
            with open(filename, "r") as f:
                try:
                    return json.load(f)
                except:
                    return []
        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _assess_fairness(disparate_impact: float) -> str:
        """80% rule-of-thumb for disparate impact."""
        if 0.8 <= disparate_impact <= 1.25:
            return "FAIR — passes the 80% rule"
        elif disparate_impact < 0.8:
            return "BIASED — disparate impact below 0.8 (unprivileged group disadvantaged)"
        else:
            return "BIASED — disparate impact above 1.25 (privileged group disadvantaged)"
