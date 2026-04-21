"""
Pydantic models for the audit pipeline (requests + responses).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AuditRequest(BaseModel):
    session_id: str = Field(..., description="Dataset session ID returned by /audit/upload")
    target_column: str = Field(..., description="Name of the prediction/label column")
    protected_attributes: List[str] = Field(
        ..., description="Column name(s) of protected/sensitive attributes e.g. ['gender','race']"
    )
    privileged_groups: List[Dict[str, Any]] = Field(
        ..., description="List of dicts defining privileged group values e.g. [{'gender': 1}]"
    )
    unprivileged_groups: List[Dict[str, Any]] = Field(
        ..., description="List of dicts defining unprivileged group values e.g. [{'gender': 0}]"
    )
    favorable_label: float = Field(1.0, description="The label value considered favorable/positive")
    unfavorable_label: float = Field(0.0, description="The label value considered unfavorable/negative")


class ExplainRequest(BaseModel):
    session_id: str = Field(..., description="Dataset session ID")
    target_column: str = Field(..., description="Target/label column name")
    feature_columns: Optional[List[str]] = Field(
        None, description="Subset of feature columns to use; defaults to all non-target columns"
    )
    num_samples: int = Field(100, ge=10, le=5000, description="Number of background samples for SHAP")


class CounterfactualRequest(BaseModel):
    session_id: str = Field(..., description="Dataset session ID")
    target_column: str = Field(..., description="Target/label column name")
    query_instance: Dict[str, Any] = Field(
        ..., description="The input instance to generate counterfactuals for"
    )
    num_cfs: int = Field(3, ge=1, le=10, description="Number of counterfactual examples to generate")
    desired_class: str = Field("opposite", description="Desired class for counterfactuals")
    features_to_vary: str = Field("all", description="'all' or comma-separated column names")


# ---------------------------------------------------------------------------
# Demographics response models
# ---------------------------------------------------------------------------

class DemographicsColumnResult(BaseModel):
    """Statistics for a single protected column."""
    value_counts: Dict[str, int] = Field(..., description="Raw count per unique value")
    percentages: Dict[str, float] = Field(..., description="Percentage share per unique value (sums to ~100)")
    representation_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="min_group_pct / max_group_pct — 1.0 means perfectly balanced",
    )
    underrepresented_groups: List[str] = Field(
        ..., description="Groups whose representation is below 10 %"
    )
    has_underrepresentation: bool = Field(
        ..., description="True when at least one group is below 10 %"
    )


class DemographicsResponse(BaseModel):
    """Full response payload for POST /audit/demographics."""
    num_rows: int = Field(..., description="Total rows in the uploaded CSV")
    num_columns: int = Field(..., description="Total columns in the uploaded CSV")
    columns_analyzed: List[str] = Field(..., description="Protected columns that were found and analyzed")
    missing_columns: List[str] = Field(
        ..., description="Requested protected columns that were absent from the CSV"
    )
    results: Dict[str, DemographicsColumnResult] = Field(
        ..., description="Per-column demographic statistics"
    )


# ---------------------------------------------------------------------------
# Performance response models
# ---------------------------------------------------------------------------

class GroupMetrics(BaseModel):
    """sklearn metrics for a single group value."""
    count: int = Field(..., description="Number of rows in this group")
    accuracy: float = Field(..., description="Accuracy score (0–1)")
    precision: float = Field(..., description="Weighted precision score (0–1)")
    recall: float = Field(..., description="Weighted recall score (0–1)")
    f1: float = Field(..., description="Weighted F1 score (0–1)")


class MetricGap(BaseModel):
    """Best-vs-worst gap analysis for one metric."""
    best_group: str
    best_score: float
    worst_group: str
    worst_score: float
    gap: float = Field(..., description="best_score - worst_score")
    flagged: bool = Field(..., description="True when gap exceeds 0.10 (10 pp)")


class PerformanceColumnResult(BaseModel):
    """Per-column performance breakdown."""
    groups: Dict[str, GroupMetrics] = Field(..., description="Metrics keyed by group value")
    skipped_groups: List[str] = Field(
        ..., description="Groups skipped due to insufficient samples (< 5)"
    )
    performance_gaps: Dict[str, Optional[MetricGap]] = Field(
        ..., description="Gap analysis for each metric"
    )
    any_metric_flagged: bool = Field(
        ..., description="True when at least one metric gap exceeds the threshold"
    )


class PerformanceResponse(BaseModel):
    """Full response payload for POST /audit/performance."""
    num_rows: int
    num_columns: int
    columns_analyzed: List[str]
    missing_columns: List[str]
    overall_metrics: Dict[str, float] = Field(
        ..., description="Metrics computed over the full dataset (no grouping)"
    )
    gap_threshold: float = Field(0.10, description="Threshold above which a gap is flagged")
    results: Dict[str, PerformanceColumnResult]


# ---------------------------------------------------------------------------
# Fairness response models
# ---------------------------------------------------------------------------

class GroupStats(BaseModel):
    """Per-group statistics for the binary fairness audit."""
    count: int = Field(..., description="Number of rows in this group")
    approval_rate: float = Field(..., description="Fraction of predictions equal to positive_label")
    tpr: Optional[float] = Field(
        None,
        description="True-Positive Rate (sensitivity); None when no positive ground-truth rows exist",
    )


class FairnessMetric(BaseModel):
    """Result block for a single fairness metric."""
    value: Optional[float] = Field(..., description="Computed metric value; None when not applicable")
    threshold: float = Field(..., description="Threshold used for the pass/fail decision")
    flagged: bool = Field(..., description="True when the metric fails its threshold test")
    result: str = Field(..., description="'PASS', 'FAIL', or 'N/A …' explanation string")
    description: str = Field(..., description="Human-readable formula description")


class FairnessResponse(BaseModel):
    """Full response payload for POST /audit/fairness."""
    num_rows: int
    protected_column: str = Field(..., description="Name of the binary protected attribute column")
    positive_label: Any = Field(..., description="The label value treated as the positive/favourable class")
    groups: List[str] = Field(..., description="The two group labels [A, B] sorted for deterministic ordering")
    group_stats: Dict[str, GroupStats] = Field(..., description="Per-group approval rate and TPR")
    metrics: Dict[str, FairnessMetric] = Field(
        ...,
        description=(
            "Keys: 'demographic_parity_difference', "
            "'equal_opportunity_difference', 'disparate_impact_ratio'"
        ),
    )
    failing_metrics: List[str] = Field(..., description="Names of metrics that failed their threshold")
    overall_pass: bool = Field(..., description="True when all three metrics pass")
    warning: Optional[str] = Field(
        None,
        description="Populated when DPD and EOD both fail — explains the conflicting fairness definitions",
    )


# ---------------------------------------------------------------------------
# Instance-level SHAP explanation response models
# ---------------------------------------------------------------------------

class SHAPFeature(BaseModel):
    """SHAP contribution for a single feature."""
    rank: int = Field(..., description="1 = highest absolute impact")
    feature: str = Field(..., description="Feature name")
    shap_value: float = Field(
        ...,
        description="SHAP value for the positive class: positive → pushes toward approval, negative → toward rejection",
    )
    contribution_percent: float = Field(
        ...,
        description="This feature's share of total absolute SHAP impact (all top-N features sum to ≤ 100 %)",
    )
    direction: str = Field(..., description="'toward approval' or 'toward rejection'")


class InstanceExplainResponse(BaseModel):
    """Full response payload for POST /audit/explain."""
    target_column: str
    model: str = Field(..., description="Model used for SHAP computation")
    predicted_class: Any = Field(..., description="Model prediction for the supplied instance")
    predicted_proba: float = Field(..., description="Confidence of the predicted class (0–1)")
    num_training_rows: int = Field(..., description="Number of rows used to train the model")
    num_features: int = Field(..., description="Total number of feature columns")
    top_n_requested: int = Field(..., description="Number of top features returned")
    top_features: List[SHAPFeature] = Field(
        ..., description="Top-N features ranked by absolute SHAP value"
    )


# ---------------------------------------------------------------------------
# Proxy detection response models
# ---------------------------------------------------------------------------

class PerProtectedColumnProxy(BaseModel):
    """Proxy scores for one feature vs one protected column."""
    pearson_correlation: float = Field(
        ..., description="abs(Pearson r) between feature and protected column (0–1)"
    )
    mutual_information_normalised: float = Field(
        ..., description="MI normalised by H(protected column) so it lies in [0, 1]"
    )
    proxy_risk_score: float = Field(
        ..., description="max(pearson_correlation, mutual_information_normalised)"
    )


class ProxyFeatureResult(BaseModel):
    """Proxy analysis result for a single non-protected feature."""
    feature: str
    proxy_risk_score: float = Field(
        ..., description="Max proxy_risk_score across all protected columns (0–1)"
    )
    risk_level: str = Field(..., description="'HIGH RISK' when score > 0.3, otherwise 'LOW RISK'")
    flagged: bool = Field(..., description="True when proxy_risk_score exceeds 0.3")
    per_protected_column: Dict[str, PerProtectedColumnProxy] = Field(
        ..., description="Breakdown of scores keyed by protected column name"
    )


class ProxyResponse(BaseModel):
    """Full response payload for POST /audit/proxies."""
    num_rows: int
    num_features_analyzed: int = Field(..., description="Number of non-protected columns scored")
    protected_columns_found: List[str] = Field(..., description="Protected columns present in the CSV")
    missing_columns: List[str] = Field(..., description="Requested protected columns absent from the CSV")
    proxy_risk_threshold: float = Field(0.3, description="Score above which a feature is flagged HIGH RISK")
    high_risk_features: List[str] = Field(..., description="Names of flagged HIGH RISK features")
    num_high_risk: int = Field(..., description="Count of HIGH RISK features")
    features: List[ProxyFeatureResult] = Field(
        ..., description="All non-protected features sorted by proxy_risk_score descending"
    )


# ---------------------------------------------------------------------------
# Counterfactual explanation response models
# ---------------------------------------------------------------------------

class FeatureChange(BaseModel):
    """A single feature's original and counterfactual value."""
    original: Any = Field(..., description="Value in the original instance")
    new: Any = Field(..., description="Value in the counterfactual instance")


class CounterfactualExample(BaseModel):
    """One generated counterfactual example."""
    id: int = Field(..., description="1-indexed counterfactual number")
    changed_features: Dict[str, FeatureChange] = Field(
        ..., description="Only the features that differ from the original instance"
    )
    full_instance: Dict[str, Any] = Field(
        ..., description="Complete feature dict for this counterfactual"
    )
    explanation: str = Field(
        ...,
        description=(
            "Plain-English sentence, e.g. "
            "'If employment_gap_months were 2 instead of 8: APPROVED'"
        ),
    )


class CFExplainResponse(BaseModel):
    """Full response payload for POST /audit/counterfactual."""
    target_column: str
    original_instance: Dict[str, Any] = Field(
        ..., description="Original instance (decoded to human-readable values)"
    )
    original_prediction: int = Field(..., description="Model prediction for the original instance")
    original_prediction_label: str = Field(..., description="'APPROVED' or 'REJECTED'")
    desired_class: int = Field(..., description="Target class to flip to (default 1)")
    desired_class_label: str = Field(..., description="Human-readable label for the desired class")
    num_cfs_requested: int
    num_cfs_generated: int = Field(
        ..., description="Actual number of counterfactuals DiCE was able to generate"
    )
    counterfactuals: List[CounterfactualExample]


# ---------------------------------------------------------------------------
# Plain-language (Groq LLM) explanation models
# ---------------------------------------------------------------------------

class TopFeatureInput(BaseModel):
    """One feature's SHAP contribution — mirrors the output from /audit/explain."""
    feature: str = Field(..., description="Feature name")
    shap_value: float = Field(..., description="SHAP value (+ toward approval, - toward rejection)")
    contribution_percent: float = Field(..., description="Share of total absolute SHAP impact (0–100)")


class PlainExplainRequest(BaseModel):
    """Request body for POST /audit/explain-plain."""
    decision: str = Field(
        ...,
        pattern="^(APPROVED|REJECTED)$",
        description="Model decision: 'APPROVED' or 'REJECTED'",
    )
    top_features: List[TopFeatureInput] = Field(
        ...,
        min_length=1,
        description="Top SHAP features from /audit/explain",
    )
    proxy_flags: List[str] = Field(
        default_factory=list,
        description="Feature names flagged as proxies from /audit/proxies",
    )
    counterfactuals: List[str] = Field(
        default_factory=list,
        description="Plain counterfactual strings from /audit/counterfactual",
    )
    audience: str = Field(
        ...,
        pattern="^(hr_manager|developer|executive)$",
        description="Target audience: 'hr_manager', 'developer', or 'executive'",
    )


class PlainExplainResponse(BaseModel):
    """Response payload for POST /audit/explain-plain."""
    explanation: str = Field(
        ..., description="LLM-generated plain-language explanation tailored to the audience"
    )
    audience: str = Field(..., description="Audience the explanation was generated for")
    model: str = Field(..., description="Groq model used for generation")


# ---------------------------------------------------------------------------
# Human review models
# ---------------------------------------------------------------------------

class ReviewRequest(BaseModel):
    """Request body for POST /audit/review."""
    decision: str = Field(
        ...,
        pattern="^(APPROVED|REJECTED)$",
        description="Model decision being reviewed.",
    )
    status: str = Field(
        ...,
        pattern="^(flagged|reviewed)$",
        description="Reviewer verdict: 'flagged' or 'reviewed'.",
    )
    applicant_id: Optional[str] = Field(
        None,
        description="Optional applicant or case identifier.",
    )
    notes: Optional[str] = Field(
        None,
        description="Optional free-text notes from the reviewer.",
    )


class ReviewResponse(BaseModel):
    """Confirmation returned after a review is recorded."""
    review_id: str
    status: str
    decision: str
    applicant_id: Optional[str]
    recorded_at: str
    message: str


# ---------------------------------------------------------------------------
# Audit PDF report request model
# ---------------------------------------------------------------------------

class MitigationData(BaseModel):
    """Optional before/after mitigation metrics for Section 5."""
    method: Optional[str] = Field(None, description="Mitigation algorithm name")
    original_metrics:  Dict[str, Any] = Field(default_factory=dict)
    mitigated_metrics: Dict[str, Any] = Field(default_factory=dict)


class AuditReportRequest(BaseModel):
    """
    Request body for POST /audit/report.
    All audit-result fields are optional — include whichever audits were run.
    """
    # ── Report metadata ────────────────────────────────────────────────
    dataset_name: Optional[str] = Field(
        None, description="Human-readable dataset name shown in the report header."
    )
    dataset_hash: Optional[str] = Field(
        None,
        description=(
            "MD5 hash of the original CSV file (computed client-side). "
            "If omitted, the server derives a hash from the demographics result."
        ),
    )
    auditor_name: Optional[str] = Field(
        None, description="Pre-filled in the sign-off field (leave blank for a blank line)."
    )

    # ── Audit results (pass whichever endpoints were run) ─────────────
    demographics_result: Optional[Dict[str, Any]] = Field(
        None, description="Full JSON response from POST /audit/demographics."
    )
    performance_result: Optional[Dict[str, Any]] = Field(
        None, description="Full JSON response from POST /audit/performance."
    )
    fairness_result: Optional[Dict[str, Any]] = Field(
        None, description="Full JSON response from POST /audit/fairness."
    )
    proxy_result: Optional[Dict[str, Any]] = Field(
        None, description="Full JSON response from POST /audit/proxies."
    )
    mitigation: Optional[MitigationData] = Field(
        None, description="Before/after mitigation metrics (optional)."
    )


# ---------------------------------------------------------------------------
# Mitigation endpoint response models
# ---------------------------------------------------------------------------

class MitigationGroupMetrics(BaseModel):
    """Metrics for one model variant (baseline or reweighed)."""
    accuracy: float = Field(..., description="Accuracy on the held-out test set (80/20 split).")
    demographic_parity_difference: float = Field(
        ..., description="Absolute approval-rate difference between privileged and unprivileged groups."
    )
    equal_opportunity_difference: float = Field(
        ..., description="Absolute TPR difference between privileged and unprivileged groups."
    )


class MitigationResponse(BaseModel):
    """Full before/after comparison returned by POST /audit/mitigate."""
    # ── User-requested fields ────────────────────────────────────────
    before:              MitigationGroupMetrics
    after:               MitigationGroupMetrics
    accuracy_cost:       float = Field(
        ..., description="Accuracy drop from reweighing (before.accuracy − after.accuracy). "
                         "Positive means the reweighed model is slightly less accurate."
    )
    fairness_improvement: float = Field(
        ..., description="DPD decrease from reweighing (before.dpd − after.dpd). "
                         "Positive means bias was reduced."
    )
    # ── Context ──────────────────────────────────────────────────────
    eod_improvement:    float
    num_rows_total:     int
    num_rows_train:     int
    num_rows_test:      int
    algorithm:          str
    target_column:      str
    protected_column:   str
    privileged_group:   Dict[str, Any]
    unprivileged_group: Dict[str, Any]
    # ── MitigationData-compatible (for POST /audit/report) ───────────
    method:             str
    original_metrics:   Dict[str, Any]
    mitigated_metrics:  Dict[str, Any]
