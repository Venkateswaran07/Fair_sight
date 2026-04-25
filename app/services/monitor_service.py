"""
MonitorService
==============
Manages the prediction log and drift detection for live model monitoring using Google Cloud Firestore.

Storage
-------
Google Cloud Firestore:
- Collection 'predictions': Stores every ingested prediction.
- Collection 'monitoring_settings': Stores baseline configs.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from google.cloud import firestore
from app.db import db


class MonitorService:

    def __init__(self) -> None:
        self.db = db
        # Collections
        self.predictions_ref = self.db.collection("predictions")
        self.settings_ref    = self.db.collection("monitoring_settings")

    # ── Ingest ───────────────────────────────────────────────────────────────

    def ingest(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk-insert a batch of predictions into Firestore.
        """
        if not batch:
            return {"ingested": 0, "total_in_log": self._count(), "ingested_at": _utcnow()}

        ingested_at = datetime.now(timezone.utc)
        
        # Firestore batch write for efficiency
        batch_op = self.db.batch()
        for r in batch:
            doc_ref = self.predictions_ref.document()
            batch_op.set(doc_ref, {
                "prediction": int(r["prediction"]),
                "ground_truth": int(r["ground_truth"]) if r.get("ground_truth") is not None else None,
                "protected_attribute_value": str(r["protected_attribute_value"]).strip(),
                "ingested_at": ingested_at
            })
        
        batch_op.commit()

        return {
            "ingested":     len(batch),
            "total_in_log": self._count(),
            "ingested_at":  ingested_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _count(self) -> int:
        """Count total predictions in Firestore."""
        # Note: In production with millions of rows, use an aggregation query or a counter doc.
        # For the Solution Challenge, this is fine.
        return len(list(self.predictions_ref.stream()))

    # ── Baseline ────────────────────────────────────────────────────────────

    def set_baseline(
        self,
        baseline_dpd:        float,
        protected_attribute: Optional[str] = None,
        drift_threshold:     float         = 0.05,
    ) -> Dict[str, Any]:
        """Store a new baseline DPD in 'monitoring_settings'."""
        set_at = datetime.now(timezone.utc)
        
        data = {
            "baseline_dpd":        float(baseline_dpd),
            "protected_attribute": protected_attribute,
            "drift_threshold":     float(drift_threshold),
            "set_at":              set_at
        }
        
        # We store with a fixed ID 'active_baseline' to easily retrieve the latest
        self.settings_ref.document("active_baseline").set(data)

        return {
            "baseline_dpd":        data["baseline_dpd"],
            "protected_attribute": data["protected_attribute"],
            "drift_threshold":     data["drift_threshold"],
            "set_at":              set_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def get_baseline(self) -> Optional[Dict[str, Any]]:
        """Return the most recently stored baseline, or None if not set."""
        doc = self.settings_ref.document("active_baseline").get()
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        # Convert timestamp to string if needed
        if isinstance(data.get("set_at"), datetime):
            data["set_at"] = data["set_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            
        return data

    # ── Status / drift detection ─────────────────────────────────────────────

    def get_status(self, window: int = 500) -> Dict[str, Any]:
        """
        Fetch the last ``window`` predictions from Firestore, compute live DPD, 
        and compare against the stored baseline.
        """
        # Fetch recent predictions ordered by timestamp
        query = self.predictions_ref.order_by("ingested_at", direction=firestore.Query.DESCENDING).limit(window)
        docs = query.stream()
        
        rows = [d.to_dict() for d in docs]
        num = len(rows)

        if num == 0:
            return {
                "alert":           False,
                "current_dpd":     0.0,
                "baseline_dpd":    None,
                "drift":           None,
                "drift_threshold": None,
                "num_predictions": 0,
                "window":          window,
                "group_stats":     [],
                "message":         "No predictions in the log yet.",
            }

        # ── Compute live DPD ─────────────────────────────────────────────────
        current_dpd, group_stats = self._compute_dpd(rows)

        # ── Compare against baseline ─────────────────────────────────────────
        baseline = self.get_baseline()

        if baseline is None:
            return {
                "alert":           False,
                "current_dpd":     round(current_dpd, 4),
                "baseline_dpd":    None,
                "drift":           None,
                "drift_threshold": None,
                "num_predictions": num,
                "window":          window,
                "group_stats":     group_stats,
                "message":         "No baseline set. POST to /monitor/baseline to enable drift alerts.",
            }

        baseline_dpd    = baseline["baseline_dpd"]
        drift_threshold = baseline["drift_threshold"]
        drift           = current_dpd - baseline_dpd
        alert           = drift > drift_threshold

        result: Dict[str, Any] = {
            "alert":           alert,
            "current_dpd":     round(current_dpd, 4),
            "baseline_dpd":    round(baseline_dpd, 4),
            "drift":           round(drift, 4),
            "drift_threshold": drift_threshold,
            "num_predictions": num,
            "window":          window,
            "group_stats":     group_stats,
        }

        if alert:
            result["message"] = (
                f"⚠ Fairness drift detected! Live DPD ({current_dpd:.4f}) exceeds "
                f"baseline ({baseline_dpd:.4f}) by {drift:.4f}, "
                f"threshold is {drift_threshold}."
            )
        else:
            result["message"] = (
                f"Model within acceptable fairness bounds. "
                f"Drift from baseline: {drift:+.4f} (threshold ±{drift_threshold})."
            )

        return result

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _compute_dpd(
        self, rows: List[Dict[str, Any]]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Compute Demographic Parity Difference (DPD) from Firestore rows.
        """
        buckets: Dict[str, List[int]] = defaultdict(list)
        for row in rows:
            buckets[row["protected_attribute_value"]].append(int(row["prediction"]))

        if len(buckets) < 2:
            only_group = list(buckets.keys())[0]
            vals        = buckets[only_group]
            return 0.0, [
                {
                    "group":         only_group,
                    "count":         len(vals),
                    "approval_rate": round(sum(vals) / len(vals), 4) if vals else 0.0,
                }
            ]

        approval_rates    = {g: sum(v) / len(v) for g, v in buckets.items()}
        dpd               = abs(max(approval_rates.values()) - min(approval_rates.values()))

        group_stats = [
            {
                "group":         g,
                "count":         len(buckets[g]),
                "approval_rate": round(ar, 4),
            }
            for g, ar in sorted(approval_rates.items(), key=lambda x: -x[1])
        ]

        return dpd, group_stats

    # ── Admin helpers ────────────────────────────────────────────────────────

    def clear_log(self) -> Dict[str, int]:
        """Delete all predictions from Firestore (batch delete)."""
        docs = self.predictions_ref.list_documents()
        deleted = 0
        for doc in docs:
            doc.delete()
            deleted += 1
        return {"deleted": deleted}

    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent predictions for debugging."""
        query = self.predictions_ref.order_by("ingested_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()
        results = []
        for d in docs:
            data = d.to_dict()
            data["id"] = d.id
            if isinstance(data.get("ingested_at"), datetime):
                data["ingested_at"] = data["ingested_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            results.append(data)
        return results


# ── Singleton ─────────────────────────────────────────────────────────────────
monitor_service = MonitorService()


# ── Utility ───────────────────────────────────────────────────────────────────
def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
