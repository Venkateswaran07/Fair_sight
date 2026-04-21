"""
Health check route
GET /health → {"status": "ok"}
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Liveness probe — returns 200 OK when the server is running."""
    return {"status": "ok"}
