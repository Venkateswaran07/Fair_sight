"""
MonitorModels — Pydantic schemas for the /monitor/* endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

class PredictionEntry(BaseModel):
    """One prediction record to log."""
    prediction: int = Field(
        ...,
        ge=0, le=1,
        description="Model's predicted label: 0 = unfavourable, 1 = favourable.",
    )
    ground_truth: Optional[int] = Field(
        None,
        ge=0, le=1,
        description="Actual label if known (for future accuracy drift detection).",
    )
    protected_attribute_value: str = Field(
        ...,
        min_length=1,
        description="Value of the protected attribute for this prediction (e.g. 'Female', 'Male').",
    )

    @field_validator("protected_attribute_value")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class IngestResponse(BaseModel):
    ingested:        int  = Field(..., description="Number of records written in this request.")
    total_in_log:    int  = Field(..., description="Total records in the log after this write.")
    ingested_at:     str  = Field(..., description="UTC timestamp of this ingest call.")


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

class BaselineRequest(BaseModel):
    """Set the reference DPD to compare against during drift monitoring."""
    baseline_dpd: float = Field(
        ..., ge=0.0, le=1.0,
        description="Demographic Parity Difference at audit time (from POST /audit/fairness).",
    )
    protected_attribute: Optional[str] = Field(
        None,
        description="Name of the protected attribute this baseline is for (informational).",
    )
    drift_threshold: float = Field(
        0.05, ge=0.0, le=1.0,
        description="How much the live DPD must exceed the baseline before an alert fires. Default 0.05.",
    )


class BaselineResponse(BaseModel):
    baseline_dpd:        float
    protected_attribute: Optional[str]
    drift_threshold:     float
    set_at:              str


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class GroupStats(BaseModel):
    group:          str
    count:          int
    approval_rate:  float


class MonitorStatus(BaseModel):
    """Full response from GET /monitor/status."""
    alert:           bool
    current_dpd:     float  = Field(..., description="DPD computed over the last `window` predictions.")
    baseline_dpd:    Optional[float] = None
    drift:           Optional[float] = Field(None, description="current_dpd − baseline_dpd (positive = drifted toward more bias).")
    drift_threshold: Optional[float] = None
    num_predictions: int    = Field(..., description="Number of predictions used in this computation.")
    window:          int    = Field(..., description="Window size requested.")
    group_stats:     List[GroupStats] = Field(default_factory=list)
    message:         Optional[str]   = None
