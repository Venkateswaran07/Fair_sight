"""
AuditService — fairness metrics via IBM AIF360.
"""

import io
import uuid
import pandas as pd
from typing import Dict, Any

# In-memory session store (replace with Redis / DB in production)
_sessions: Dict[str, pd.DataFrame] = {}


class AuditService:
    # ------------------------------------------------------------------
    # Dataset management
    # ------------------------------------------------------------------
    def store_dataset(self, raw_bytes: bytes, filename: str) -> str:
        """Parse CSV bytes, store in memory, return a unique session ID."""
        df = pd.read_csv(io.BytesIO(raw_bytes))
        session_id = str(uuid.uuid4())
        _sessions[session_id] = df
        return session_id

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
        Returns a dict with disparate impact, statistical parity difference,
        equal opportunity difference, and average odds difference.
        """
        from aif360.datasets import BinaryLabelDataset  # type: ignore
        from aif360.metrics import BinaryLabelDatasetMetric, ClassificationMetric  # type: ignore

        df = self.get_dataset(request.session_id)

        # Build AIF360 BinaryLabelDataset
        bld = BinaryLabelDataset(
            df=df,
            label_names=[request.target_column],
            protected_attribute_names=request.protected_attributes,
            favorable_label=request.favorable_label,
            unfavorable_label=request.unfavorable_label,
        )

        metric = BinaryLabelDatasetMetric(
            bld,
            unprivileged_groups=request.unprivileged_groups,
            privileged_groups=request.privileged_groups,
        )

        results = {
            "session_id": request.session_id,
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
        return results

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
