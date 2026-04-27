"""
Audit routes
POST /audit/upload         — upload a CSV dataset
POST /audit/analyze        — run full fairness audit
POST /audit/explain        — SHAP instance explanation (CSV + JSON row)
POST /audit/counterfactual — DiCE counterfactual explanation (CSV + JSON row)
POST /audit/demographics   — protected-column distribution analysis
POST /audit/performance    — per-group ML performance metrics
POST /audit/fairness       — DPD / EOD / DIR fairness metrics (binary attribute)
POST /audit/proxies        — proxy feature detection via Pearson + MI
POST /audit/explain-plain  — LLM plain-language explanation (Gemini)
POST /audit/review         — record a human reviewer's assessment
GET  /audit/reviews        — list all recorded reviews
POST /audit/report         — generate and stream a PDF audit report
POST /audit/mitigate       — AIF360 Reweighing: before/after fairness comparison
"""

import json
from datetime import datetime, timezone
from fastapi.responses import StreamingResponse

import io
import pandas as pd
from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from app.utils.data_utils import normalize_dataframe_headers, normalize_column_list, normalize_string

from app.models.audit_models import (
    AuditRequest,
    ExplainRequest,
    CounterfactualRequest,
    DemographicsResponse,
    PerformanceResponse,
    FairnessResponse,
    InstanceExplainResponse,
    ProxyResponse,
    CFExplainResponse,
    PlainExplainRequest,
    PlainExplainResponse,
    ReviewRequest,
    ReviewResponse,
    AuditReportRequest,
    MitigationResponse,
)
from app.services.audit_service import AuditService
from app.services.explainer_service import ExplainerService
from app.services.counterfactual_service import CounterfactualService
from app.services.demographics_service import DemographicsService
from app.services.performance_service import PerformanceService
from app.services.fairness_service import FairnessService
from app.services.instance_explainer_service import InstanceExplainerService
from app.services.proxy_detection_service import ProxyDetectionService
from app.services.cf_explainer_service import CFExplainerService
from app.services.gemini_explain_service import GeminiExplainService
from app.services.audit_report_service import AuditReportService
from app.services.mitigation_service import MitigationService
from app.services.insights_service import insights_svc

router = APIRouter()
audit_svc = AuditService()
explain_svc = ExplainerService()
cf_svc = CounterfactualService()
demographics_svc = DemographicsService()
performance_svc = PerformanceService()
fairness_svc = FairnessService()
instance_explain_svc = InstanceExplainerService()
proxy_svc = ProxyDetectionService()
cf_explain_svc = CFExplainerService()
report_svc = AuditReportService()
mitigation_svc = MitigationService()

# GeminiExplainService is initialised lazily (first request) so that a missing
# GEMINI_API_KEY does not crash the entire server on startup.
_gemini_svc: GeminiExplainService | None = None


def _get_gemini_svc() -> GeminiExplainService:
    """Return the singleton GeminiExplainService, creating it on first call."""
    global _gemini_svc
    if _gemini_svc is None:
        try:
            _gemini_svc = GeminiExplainService()
        except EnvironmentError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
    return _gemini_svc


# ---------------------------------------------------------------------------
# Dataset upload
# ---------------------------------------------------------------------------
@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """
    Upload a CSV dataset for auditing.
    """
    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

        contents = await file.read()
        result = audit_svc.store_dataset(contents, file.filename)
        return {
            "session_id": result["session_id"],
            "filename": file.filename,
            "status": "uploaded",
            "headers": result["headers"],
            "preview_rows": result["preview_rows"],
            "total_rows": result["total_rows"]
        }
    except Exception as exc:
        print(f"[Critical] Upload Error: {exc}")
        return JSONResponse(
            status_code=400, 
            content={"error": "Failed to process CSV", "detail": str(exc)}
        )


@router.get("/applicants/{session_id}")
async def get_applicants(session_id: str):
    """
    Retrieve the list of applicants for a session to show in the audit log.
    """
    try:
        df = audit_svc.get_dataset(session_id)
        # Limit to first 1000 for performance
        data = df.head(1000).to_dict(orient="records")
        return {"total": len(df), "applicants": data, "headers": list(df.columns)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Full fairness audit
# ---------------------------------------------------------------------------
@router.post("/analyze")
async def analyze(request: AuditRequest):
    """
    Run a full fairness audit using IBM AIF360.
    Returns disparate impact, statistical parity difference, and more.
    """
    result = audit_svc.run_audit(request)
    return JSONResponse(content=result)


@router.get("/history")
async def list_history():
    """
    Fetch the list of all past fairness audits from Firestore.
    """
    try:
        history = audit_svc.get_history()
        return {"total": len(history), "history": history}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {exc}")


@router.post("/history/save")
async def save_history(record: dict):
    """
    Save a full audit result (fairness + performance + demographics) to history.
    """
    from datetime import datetime, timezone
    
    try:
        session_id = record.get("session_id") or f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        record["session_id"] = session_id
        if "timestamp" not in record:
            record["timestamp"] = datetime.now(timezone.utc).isoformat()
            
        try:
            from app.db import db
            db.collection("audit_history").document(session_id).set(record)
        except Exception as e:
            print(f"[Warning] Firestore save failed: {e}. Saving to local history.")
            audit_svc._save_to_local_history(record)
            
        return {"status": "success", "session_id": session_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save history: {exc}")


# ---------------------------------------------------------------------------
# SHAP instance explanation  (CSV upload + single JSON row)
# ---------------------------------------------------------------------------
@router.post("/explain", response_model=InstanceExplainResponse)
async def explain(
    file: UploadFile = File(
        ...,
        description="CSV training dataset. All columns except target_column are used as features.",
    ),
    target_column: str = Form(
        ...,
        description="Name of the label / target column in the CSV.",
    ),
    instance: str = Form(
        ...,
        description=(
            'JSON object representing the single row to explain. '
            'Example: \'{"age": 35, "income": 50000, "gender": "Male"}\''
        ),
    ),
    top_n: int = Form(
        5,
        ge=1,
        le=20,
        description="Number of top features to return, ranked by |SHAP value|. Default: 5.",
    ),
):
    """
    Train a **RandomForestClassifier** on the uploaded CSV and compute SHAP values
    for a single user-supplied instance.

    **Request (multipart/form-data)**
    | Field | Type | Description |
    |---|---|---|
    | `file` | CSV upload | Training dataset |
    | `target_column` | string | Label column name |
    | `instance` | JSON string | Single row to explain |
    | `top_n` | int (1–20) | Features to return (default 5) |

    **Response — per feature**
    | Field | Description |
    |---|---|
    | `shap_value` | Positive → pushes toward approval; negative → toward rejection |
    | `contribution_percent` | Share of total absolute SHAP impact |
    | `direction` | Human-readable direction string |
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    raw = await file.read()

    try:
        result = instance_explain_svc.explain(raw, target_column, instance, top_n)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# DiCE counterfactual explanation  (CSV upload + single JSON row)
# ---------------------------------------------------------------------------
@router.post("/counterfactual", response_model=CFExplainResponse)
async def counterfactual(
    file: UploadFile = File(
        ...,
        description="CSV training dataset. All columns except target_column are used as features.",
    ),
    target_column: str = Form(
        ...,
        description="Name of the label / target column in the CSV.",
    ),
    instance: str = Form(
        ...,
        description=(
            'JSON object representing the instance whose prediction should be flipped. '
            'Example: \'{"age": 45, "income": 30000, "gender": "Female"}\''
        ),
    ),
    num_cfs: int = Form(
        3,
        ge=1,
        le=10,
        description="Number of counterfactuals to generate (default 3, max 10).",
    ),
    desired_class: int = Form(
        1,
        description="Target class to flip the prediction to (default 1 = Approved).",
    ),
):
    """
    Generate **counterfactual explanations** — the minimal feature changes that
    flip the model's prediction from its original class to *desired_class*.

    **Request (multipart/form-data)**
    | Field | Type | Description |
    |---|---|---|
    | `file` | CSV upload | Training dataset |
    | `target_column` | string | Label column name |
    | `instance` | JSON string | Row whose prediction to flip |
    | `num_cfs` | int (1–10) | Counterfactuals to generate (default 3) |
    | `desired_class` | int | Target class, default 1 (Approved) |

    **Per counterfactual**
    | Field | Description |
    |---|---|
    | `changed_features` | Only the features that differ, with `original` and `new` values |
    | `full_instance` | Complete feature dict for this counterfactual |
    | `explanation` | Plain-English sentence, e.g. *"If income were 60000 instead of 30000: APPROVED"* |
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    raw = await file.read()

    try:
        result = cf_explain_svc.generate(raw, target_column, instance, num_cfs, desired_class)
    except Exception as exc:
        print(f"CF ERROR: {exc}")
        raise HTTPException(status_code=422, detail=str(exc))

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Demographics analysis
# ---------------------------------------------------------------------------
@router.post("/demographics", response_model=DemographicsResponse)
async def demographics(
    file: UploadFile = File(None, description="CSV dataset to analyze"),
    session_id: str = Form(None),
    protected_columns: str = Form(
        ...,
        description='JSON array of column names to analyse, e.g. ["gender","race"]',
    ),
):
    """
    Analyse the demographic distribution of one or more protected columns.
    """
    # --- parse and normalize protected_columns from JSON string
    try:
        raw_cols: list = json.loads(protected_columns)
        columns = normalize_column_list(raw_cols)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail='Invalid protected_columns format')

    if session_id:
        try:
            df = audit_svc.get_dataset(session_id)
            result = demographics_svc.analyze_df(df, columns)
            return JSONResponse(content=result)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

    if not file:
        raise HTTPException(status_code=400, detail="Either file or session_id is required")

    raw = await file.read()
    result = demographics_svc.analyze(raw, columns)
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Per-group performance metrics
# ---------------------------------------------------------------------------
@router.post("/performance", response_model=PerformanceResponse)
async def performance(
    file: UploadFile = File(None),
    session_id: str = Form(None),
    protected_columns: str = Form(
        ...,
        description='JSON array of protected column names, e.g. ["gender","race"]',
    ),
):
    """
    Compute per-group ML performance metrics for each protected attribute.
    """
    try:
        raw_cols: list = json.loads(protected_columns)
        columns = normalize_column_list(raw_cols)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail='Invalid protected_columns format')

    if session_id:
        try:
            df = audit_svc.get_dataset(session_id)
            result = performance_svc.analyze_df(df, columns)
            return JSONResponse(content=result)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    if not file:
        raise HTTPException(status_code=400, detail="Either file or session_id is required")

    raw = await file.read()

    try:
        result = performance_svc.analyze(raw, columns)
    except ValueError as exc:
        # Surface missing-column errors (prediction / ground_truth) as 422
        raise HTTPException(status_code=422, detail=str(exc))

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Binary-attribute fairness metrics (DPD / EOD / DIR)
# ---------------------------------------------------------------------------
@router.post("/fairness", response_model=FairnessResponse)
async def fairness(
    file: UploadFile = File(None),
    session_id: str = Form(None),
    protected_column: str = Form(..., description="Name of the binary protected attribute column"),
    positive_label: str = Form("1"),
):
    """Compute fairness metrics for a binary protected attribute."""
    if session_id:
        try:
            df = audit_svc.get_dataset(session_id)
            result = fairness_svc.analyze_df(df, protected_column, positive_label)
            return JSONResponse(content=result)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

    if not file:
        raise HTTPException(status_code=400, detail="Either file or session_id is required")

    raw = await file.read()
    try:
        result = fairness_svc.analyze(raw, protected_column, positive_label)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Proxy feature detection
# ---------------------------------------------------------------------------
@router.post("/proxies", response_model=ProxyResponse)
async def detect_proxies(
    file: UploadFile = File(None),
    session_id: str = Form(None),
    protected_columns: str = Form(
        ...,
        description='JSON array of protected column names, e.g. ["gender","race"]',
    ),
):
    """
    Identify non-protected features that may act as proxy variables.
    """
    try:
        raw_cols: list = json.loads(protected_columns)
        columns = normalize_column_list(raw_cols)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail='Invalid protected_columns format')

    if session_id:
        try:
            df = audit_svc.get_dataset(session_id)
            result = proxy_svc.analyze_df(df, columns)
            return JSONResponse(content=result)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

    if not file:
        raise HTTPException(status_code=400, detail="Either file or session_id is required")

    raw = await file.read()

    try:
        result = proxy_svc.analyze(raw, columns)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Plain-language LLM explanation  (Groq)
# ---------------------------------------------------------------------------
@router.post("/explain-plain", response_model=PlainExplainResponse)
async def explain_plain(request: PlainExplainRequest):
    """
    Generate a **plain-language fairness explanation** using the Google Gemini LLM API
    (`gemini-1.5-flash-latest`).

    Combine the outputs of `/audit/explain`, `/audit/proxies`, and
    `/audit/counterfactual` into a single structured prompt, then ask the model
    to explain the decision in terms suited to the target audience.

    **Audience styles**

    | Audience | Style |
    |---|---|
    | `hr_manager` | 2–3 plain sentences, no jargon, proxy concerns called out |
    | `developer` | Technical tone with feature names, SHAP values, fairness context |
    | `executive` | Exactly 2 sentences: risk summary + recommended action |

    **Prerequisites**
    - `GEMINI_API_KEY` environment variable must be set before starting the server.
    - Optional: `GEMINI_MODEL` to override the default model.

    **Example request body**
    ```json
    {
      "decision": "REJECTED",
      "top_features": [
        {"feature": "credit_score", "shap_value": -0.21, "contribution_percent": 41.2},
        {"feature": "income",       "shap_value": -0.15, "contribution_percent": 29.4}
      ],
      "proxy_flags": ["zip_code"],
      "counterfactuals": ["If income were 55000 instead of 30000: APPROVED"],
      "audience": "hr_manager"
    }
    ```
    """
    gemini_svc = _get_gemini_svc()

    top_features_raw = [
        f.model_dump() for f in request.top_features
    ]

    try:
        explanation = gemini_svc.explain(
            decision=request.decision,
            top_features=top_features_raw,
            proxy_flags=request.proxy_flags,
            counterfactuals=request.counterfactuals,
            audience=request.audience,
        )
    except Exception as exc:
        print(f"GEMINI ERROR: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Gemini API error: {exc}",
        )

    return {
        "explanation": explanation,
        "audience": request.audience,
        "model": getattr(gemini_svc, "_model_name", "gemini-1.5-flash"),
    }


# ---------------------------------------------------------------------------
# Human review log  — POST /audit/review
# ---------------------------------------------------------------------------

# In-memory store (replace with a database in production)
_review_log: list = []


@router.post("/review", response_model=ReviewResponse)
async def record_review(request: ReviewRequest):
    """
    Record a human reviewer's assessment of a model decision.

    **Statuses**
    - `flagged`  — reviewer considers this decision concerning; needs follow-up
    - `reviewed` — reviewer has checked the decision and considers it acceptable

    Reviews are stored in an in-memory log (replace with a database in production).
    """
    import uuid
    review_id = str(uuid.uuid4())[:8]
    recorded_at = datetime.now(timezone.utc).isoformat()

    entry = {
        "review_id":    review_id,
        "status":       request.status,
        "decision":     request.decision,
        "applicant_id": request.applicant_id,
        "notes":        request.notes,
        "recorded_at":  recorded_at,
    }
    _review_log.append(entry)

    verb = "flagged as concerning" if request.status == "flagged" else "marked as reviewed"
    return ReviewResponse(
        review_id=review_id,
        status=request.status,
        decision=request.decision,
        applicant_id=request.applicant_id,
        recorded_at=recorded_at,
        message=f"Decision {request.decision} has been {verb}.",
    )


@router.get("/reviews")
async def list_reviews():
    """Return all recorded reviews (most recent first)."""
    return {
        "total": len(_review_log),
        "reviews": list(reversed(_review_log)),
    }


# ---------------------------------------------------------------------------
# PDF audit report  — POST /audit/report
# ---------------------------------------------------------------------------
@router.post("/report")
async def generate_report(request: AuditReportRequest):
    """
    Generate and stream a **FairSight Audit Report** as a PDF file download.

    Pass the full JSON responses from whichever audit endpoints you ran.
    All fields are optional — omitted sections show a "no data" placeholder.

    **PDF Sections**
    1. Header — title, timestamp, dataset MD5 hash
    2. Dataset Summary — row count, protected columns, group distribution tables
    3. Fairness Metrics — DPD, EOD, DIR with value, threshold, PASS / FAIL
    4. Proxy Findings — ranked feature table with HIGH RISK callouts
    5. Mitigation Applied — before/after metric table (or "not applied")
    6. Limitations — fixed legal / methodological disclaimer
    7. Auditor Sign-Off — blank lines for name, date, signature

    **Tip** — set `dataset_hash` to `md5(file_bytes.hex())` computed in the browser
    before the upload so the hash identifies the exact file audited.
    """
    try:
        mit = request.mitigation.model_dump() if request.mitigation else None
        pdf_bytes = report_svc.generate(
            dataset_name      = request.dataset_name,
            dataset_hash      = request.dataset_hash,
            demographics      = request.demographics_result,
            performance       = request.performance_result,
            fairness          = request.fairness_result,
            proxies           = request.proxy_result,
            mitigation        = mit,
            auditor_name      = request.auditor_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    # Build a filename from dataset name + timestamp
    ts   = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    name = (request.dataset_name or 'audit').replace(' ', '_')
    filename = f"fairsight_{name}_{ts}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# Bias mitigation  — POST /audit/mitigate
# ---------------------------------------------------------------------------

@router.post("/mitigate", response_model=MitigationResponse)
async def mitigate(
    file: UploadFile = File(
        None,
        description="Training dataset CSV. If omitted, session_id must be provided.",
    ),
    session_id: str = Form(
        None,
        description="Session ID from /audit/upload. If omitted, file must be provided.",
    ),
    target_column: str = Form(
        None,
        description="Name of the target/label column. If omitted, will try to auto-detect.",
    ),
    protected_column: str = Form(
        ...,
        description="Name of the protected attribute column (e.g. 'gender', 'race').",
    ),
):
    """
    Apply **IBM AIF360 Reweighing** to the dataset and compare a baseline
    `RandomForestClassifier` with a fairness-reweighed one.
    """
    import io as _io
    import pandas as _pd

    # ── 1. Resolve DataFrame ────────────────────────────────────────────────
    df: _pd.DataFrame = _pd.DataFrame()
    
    if session_id:
        try:
            df = audit_svc.get_dataset(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")
    elif file:
        try:
            contents = await file.read()
            df = _pd.read_csv(_io.BytesIO(contents))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")
    else:
        raise HTTPException(status_code=400, detail="Either file or session_id is required")

    if df.empty:
        raise HTTPException(status_code=400, detail="Dataset is empty.")

    # ── 2. Resolve Target Column ────────────────────────────────────────────
    # If not provided, use the first detected outcome column
    target = target_column
    if not target:
        from app.utils.data_utils import normalize_dataframe_headers
        df = normalize_dataframe_headers(df, fast_mode=True)
        target = "ground_truth"
    
    if not target or target not in df.columns:
        raise HTTPException(
            status_code=422, 
            detail=f"Target column '{target}' not found. Please specify target_column explicitly."
        )

    # ── 3. Run mitigation pipeline ──────────────────────────────────────────
    try:
        # Also normalize the protected_column name so it matches the standardized DF
        from app.utils.data_utils import normalize_string
        normalized_protected = normalize_string(protected_column)
        
        # Check if it exists after normalization
        if normalized_protected not in df.columns:
            # Fallback to the original if normalization changed it too much
            if protected_column not in df.columns:
                raise ValueError(f"Protected column '{protected_column}' not found in dataset headers.")
            normalized_protected = protected_column

        result = mitigation_svc.run(df, target, normalized_protected)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Mitigation failed: {exc}")

    return result

@router.post("/insights")
async def get_insights(
    session_id: str = Form(...),
    protected_column: str = Form(...),
    fairness_json: str = Form(...)
):
    """
    Generate AI recommendations based on fairness results.
    """
    try:
        fairness_data = json.loads(fairness_json)
        explanation = insights_svc.get_fairness_insights(fairness_data, protected_column)
        return {"insights": explanation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
