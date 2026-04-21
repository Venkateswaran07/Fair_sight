"""
Pydantic models for PDF report generation.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    session_id: str = Field(..., description="Dataset session ID")
    audit_results: Optional[Dict[str, Any]] = Field(
        None, description="Pre-computed audit result dict; if None the service will re-run the audit"
    )
    title: str = Field("FairSight Audit Report", description="Report title")
    author: str = Field("FairSight", description="Report author / organisation name")
    notes: Optional[str] = Field(None, description="Optional free-text notes appended to the report")
