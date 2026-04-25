"""
Report routes
POST /report/generate  — generate a PDF fairness audit report
GET  /report/{report_id} — download a previously generated report
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.report_models import ReportRequest
from app.services.report_service import ReportService

router = APIRouter(redirect_slashes=False)
report_svc = ReportService()


@router.post("/generate")
async def generate_report(request: ReportRequest):
    """
    Generate a PDF fairness audit report using ReportLab.
    Returns the report ID and download URL.
    """
    report_id, path = report_svc.generate_pdf(request)
    return {
        "report_id": report_id,
        "download_url": f"/report/{report_id}",
        "status": "generated",
    }


@router.get("/{report_id}")
async def download_report(report_id: str):
    """Download a previously generated PDF report."""
    path = report_svc.get_report_path(report_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(path, media_type="application/pdf", filename=f"fairsight_report_{report_id}.pdf")
