"""
MonitorService
==============
Manages the prediction log and drift detection for live model monitoring.

Storage
-------
SQLite database at the path given by the MONITOR_DB_PATH environment variable,
defaulting to ``./fairsight_monitor.db`` in the current working directory.

Two tables
----------
predictions_log
    Stores every ingested prediction with its protected-attribute value and
    an automatic UTC timestamp.

baseline_config
    Stores the reference DPD set at audit time, along with the drift
    threshold. Only the most-recently-inserted row is used by /monitor/status.

Thread safety
-------------
A new SQLite connection is opened for each operation and closed immediately
after (context manager). WAL journal mode is enabled so concurrent reads do
not block concurrent writes.
"""

import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ── Database location ─────────────────────────────────────────────────────────
_DEFAULT_DB = os.path.join(os.getcwd(), "fairsight_monitor.db")
_DB_PATH    = os.environ.get("MONITOR_DB_PATH", _DEFAULT_DB)

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS predictions_log (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction                INTEGER NOT NULL CHECK (prediction IN (0, 1)),
    ground_truth              INTEGER          CHECK (ground_truth IN (0, 1)),
    protected_attribute_value TEXT    NOT NULL,
    ingested_at               DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_predictions_log_ingested
    ON predictions_log (ingested_at DESC);

CREATE TABLE IF NOT EXISTS baseline_config (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_dpd         REAL    NOT NULL,
    protected_attribute  TEXT,
    drift_threshold      REAL    NOT NULL DEFAULT 0.05,
    set_at               DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


class MonitorService:

    def __init__(self, db_path: str = _DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create tables and indexes on first use."""
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        """Open a WAL-mode connection with row_factory set."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Ingest ───────────────────────────────────────────────────────────────

    def ingest(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk-insert a batch of predictions into predictions_log.

        Parameters
        ----------
        batch : list of dicts with keys:
            prediction               (int 0|1)
            ground_truth             (int 0|1 | None)
            protected_attribute_value (str)

        Returns
        -------
        dict  { ingested, total_in_log, ingested_at }
        """
        if not batch:
            return {"ingested": 0, "total_in_log": self._count(), "ingested_at": _utcnow()}

        rows = [
            (
                int(r["prediction"]),
                int(r["ground_truth"]) if r.get("ground_truth") is not None else None,
                str(r["protected_attribute_value"]).strip(),
            )
            for r in batch
        ]

        with self._connect() as conn:
            conn.executemany(
                """INSERT INTO predictions_log
                       (prediction, ground_truth, protected_attribute_value)
                   VALUES (?, ?, ?)""",
                rows,
            )
            conn.commit()

        return {
            "ingested":     len(rows),
            "total_in_log": self._count(),
            "ingested_at":  _utcnow(),
        }

    def _count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM predictions_log").fetchone()
            return int(row[0])

    # ── Baseline ────────────────────────────────────────────────────────────

    def set_baseline(
        self,
        baseline_dpd:        float,
        protected_attribute: Optional[str] = None,
        drift_threshold:     float         = 0.05,
    ) -> Dict[str, Any]:
        """Store a new baseline DPD (replaces the previous one in effect)."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO baseline_config
                       (baseline_dpd, protected_attribute, drift_threshold)
                   VALUES (?, ?, ?)""",
                (baseline_dpd, protected_attribute, drift_threshold),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM baseline_config ORDER BY id DESC LIMIT 1"
            ).fetchone()

        return {
            "baseline_dpd":        float(row["baseline_dpd"]),
            "protected_attribute": row["protected_attribute"],
            "drift_threshold":     float(row["drift_threshold"]),
            "set_at":              row["set_at"],
        }

    def get_baseline(self) -> Optional[Dict[str, Any]]:
        """Return the most recently stored baseline, or None if not set."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM baseline_config ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "baseline_dpd":        float(row["baseline_dpd"]),
            "protected_attribute": row["protected_attribute"],
            "drift_threshold":     float(row["drift_threshold"]),
            "set_at":              row["set_at"],
        }

    # ── Status / drift detection ─────────────────────────────────────────────

    def get_status(self, window: int = 500) -> Dict[str, Any]:
        """
        Fetch the last ``window`` predictions, compute live DPD, and compare
        against the stored baseline.

        Returns
        -------
        dict matching ``MonitorStatus``
        """
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT prediction, protected_attribute_value
                   FROM   predictions_log
                   ORDER  BY id DESC
                   LIMIT  ?""",
                (window,),
            ).fetchall()

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
        self, rows: List[sqlite3.Row]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Compute Demographic Parity Difference (DPD) from raw prediction rows.

        DPD = max(approval_rate per group) − min(approval_rate per group)

        Returns
        -------
        (dpd_value, group_stats_list)
        """
        buckets: Dict[str, List[int]] = defaultdict(list)
        for row in rows:
            buckets[row["protected_attribute_value"]].append(int(row["prediction"]))

        if len(buckets) < 2:
            # Only one group visible — cannot compute DPD
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
        """Truncate the predictions log (useful for testing)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM predictions_log")
            conn.commit()
        return {"deleted": 0}  # SQLite DELETE without WHERE returns 0 for changes

    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent predictions for debugging."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, prediction, ground_truth,
                          protected_attribute_value, ingested_at
                   FROM   predictions_log
                   ORDER  BY id DESC
                   LIMIT  ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


# ── Singleton ─────────────────────────────────────────────────────────────────
# Instantiated once at import time; shared across all requests.
monitor_service = MonitorService()


# ── Utility ───────────────────────────────────────────────────────────────────
def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
