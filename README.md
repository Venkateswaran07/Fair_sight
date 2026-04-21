# FairSight — AI Fairness Auditing Tool

## Project Structure

```text
biased decision glass box/
├── main.py                        # FastAPI app entry point (port 8000)
├── requirements.txt               # All dependencies
├── reports/                       # Auto-created: PDF report output directory
└── app/
    ├── __init__.py
    ├── routes/
    │   ├── __init__.py
    │   ├── health.py              # GET  /health
    │   ├── audit.py               # POST /audit/upload|analyze|explain|counterfactual
    │   └── report.py              # POST /report/generate  GET /report/{id}
    ├── models/
    │   ├── __init__.py
    │   ├── audit_models.py        # Pydantic schemas: AuditRequest, ExplainRequest, CounterfactualRequest
    │   └── report_models.py       # Pydantic schema: ReportRequest
    └── services/
        ├── __init__.py
        ├── audit_service.py       # AIF360 fairness metrics
        ├── explainer_service.py   # SHAP feature importance
        ├── counterfactual_service.py  # DiCE-ML counterfactuals
        └── report_service.py      # ReportLab PDF generation
```

## Quick Start

```bash
# 1. Create & activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
python main.py
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

## API Endpoints

| Method | Path | Description |
| -------- | ------ | ------------- |
| GET | `/health` | Liveness probe → `{"status": "ok"}` |
| GET | `/` | Root info |
| POST | `/audit/upload` | Upload a CSV dataset |
| POST | `/audit/analyze` | Run AIF360 fairness audit |
| POST | `/audit/explain` | SHAP feature importance |
| POST | `/audit/counterfactual` | DiCE-ML counterfactual examples |
| POST | `/report/generate` | Generate a PDF report |
| GET | `/report/{report_id}` | Download a PDF report |
