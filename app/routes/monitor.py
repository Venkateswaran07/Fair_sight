"""
Monitor routes
POST /monitor/ingest    — bulk-insert new predictions into the log
GET  /monitor/status    — live DPD + drift alert vs. stored baseline
POST /monitor/baseline  — store a reference DPD at audit time
GET  /monitor/baseline  — retrieve the current baseline config
GET  /monitor/recent    — last N raw log entries (debug / admin)
DELETE /monitor/log     — clear the prediction log (test / reset)
"""

from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.models.monitor_models import (
    BaselineRequest,
    BaselineResponse,
    IngestResponse,
    MonitorStatus,
    PredictionEntry,
)
from app.services.monitor_service import monitor_service

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /monitor/ingest
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=IngestResponse)
async def ingest_predictions(batch: List[PredictionEntry]):
    """
    Append a batch of model predictions to the persistent log.

    **Request body** — a JSON array of prediction records:
    ```json
    [
      {"prediction": 1, "ground_truth": 0, "protected_attribute_value": "Female"},
      {"prediction": 0, "ground_truth": 0, "protected_attribute_value": "Male"}
    ]
    ```

    | Field | Type | Required | Notes |
    |---|---|---|---|
    | `prediction` | 0 or 1 | ✓ | Model output |
    | `ground_truth` | 0 or 1 | — | Actual label if known |
    | `protected_attribute_value` | string | ✓ | Raw group label, e.g. `"Female"` |

    Returns the number of records written and the running total in the log.
    """
    if not batch:
        raise HTTPException(status_code=400, detail="Batch must not be empty.")

    raw = [p.model_dump() for p in batch]

    try:
        result = monitor_service.ingest(raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# GET /monitor/status
# ---------------------------------------------------------------------------

@router.get("/status", response_model=MonitorStatus)
async def monitor_status(
    window: int = Query(
        500,
        ge=10,
        le=100_000,
        description="Number of most recent predictions to use for DPD computation.",
    )
):
    """
    Compute the **live Demographic Parity Difference** over the last `window`
    predictions and compare it against the stored baseline.

    **Drift alert logic**

    ```
    drift   = current_dpd − baseline_dpd
    alert   = drift > drift_threshold          (default threshold: 0.05)
    ```

    **Alert response** (when drift is detected):
    ```json
    {
      "alert": true,
      "current_dpd": 0.21,
      "baseline_dpd": 0.12,
      "drift": 0.09,
      "drift_threshold": 0.05,
      "num_predictions": 500,
      "group_stats": [...]
    }
    ```

    **No alert response**:
    ```json
    {
      "alert": false,
      "current_dpd": 0.14,
      "baseline_dpd": 0.12,
      "drift": 0.02,
      ...
    }
    ```

    **No baseline set** — returns `alert: false` with a reminder to call
    `POST /monitor/baseline` first.

    **No predictions yet** — returns `alert: false, current_dpd: 0.0` with
    an explanatory message.
    """
    try:
        result = monitor_service.get_status(window=window)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Status check failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# POST /monitor/baseline
# ---------------------------------------------------------------------------

@router.post("/baseline", response_model=BaselineResponse)
async def set_baseline(request: BaselineRequest):
    """
    Store the **reference Demographic Parity Difference** captured at audit time.

    This value is used by `GET /monitor/status` to detect when live predictions
    have drifted beyond the acceptable fairness threshold.

    **Typical workflow**

    1. Run `POST /audit/fairness` on your labelled dataset.
    2. Read `metrics.demographic_parity_difference.value` from the response.
    3. POST that value here before deploying the model.
    4. Call `GET /monitor/status` periodically from your production pipeline.

    The most recently stored baseline is always used; previous baselines are
    retained in the database for auditing purposes.
    """
    try:
        result = monitor_service.set_baseline(
            baseline_dpd=request.baseline_dpd,
            protected_attribute=request.protected_attribute,
            drift_threshold=request.drift_threshold,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not store baseline: {exc}")

    return result


# ---------------------------------------------------------------------------
# GET /monitor/baseline
# ---------------------------------------------------------------------------

@router.get("/baseline", response_model=BaselineResponse)
async def get_baseline():
    """Retrieve the currently active baseline configuration."""
    result = monitor_service.get_baseline()
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No baseline has been set. POST to /monitor/baseline first.",
        )
    return result


# ---------------------------------------------------------------------------
# GET /monitor/recent  (debug / admin)
# ---------------------------------------------------------------------------

@router.get("/recent")
async def recent_predictions(
    limit: int = Query(100, ge=1, le=1000, description="Maximum rows to return.")
):
    """Return the most recent raw prediction log entries (for debugging)."""
    try:
        rows = monitor_service.get_recent(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"count": len(rows), "predictions": rows}


# ---------------------------------------------------------------------------
# DELETE /monitor/log  (test / reset)
# ---------------------------------------------------------------------------

@router.delete("/log")
async def clear_log():
    """
    Truncate the predictions log.

    ⚠ **Irreversible** — use only in development / testing environments.
    The baseline configuration is preserved.
    """
    try:
        monitor_service.clear_log()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"message": "Prediction log cleared.", "total_in_log": 0}
