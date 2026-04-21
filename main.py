"""
FairSight - AI Fairness Auditing Tool
Main application entry point
"""


import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Auto-load the .env file so you never have to type the API key in the terminal again!
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'\"")

from app.routes import health, audit, report, monitor

app = FastAPI(
    title="FairSight",
    description="AI Fairness Auditing Tool — bias detection, explainability, and counterfactual analysis.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, tags=["Health"])
app.include_router(audit.router,   prefix="/audit",   tags=["Audit"])
app.include_router(report.router,  prefix="/report",  tags=["Report"])
app.include_router(monitor.router, prefix="/monitor", tags=["Monitor"])


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/", tags=["Root"])
async def root():
    return {
        "tool":        "FairSight",
        "version":     "1.0.0",
        "description": "AI Fairness Auditing API",
        "docs":        "/docs",
        "endpoints": {
            "audit":   "/audit",
            "report":  "/report",
            "monitor": "/monitor",
        },
    }


# ---------------------------------------------------------------------------
# Dev server
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
