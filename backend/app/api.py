"""FastAPI routes for the EOD Billing & Analytics Agent.

This module is the only layer that touches HTTP, storage, and the LLM call —
reconciliation.py and analytics.py stay pure, narrative.py stays the sole
LLM boundary.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.analytics import compute_analytics
from app.narrative import generate_narrative
from app.reconciliation import compute_reconciliation
from app.validation import BillingLogValidationError, parse_billing_log

router = APIRouter(prefix="/api")


@router.post("/billing-log", status_code=201)
def ingest_billing_log(payload: list[dict[str, Any]]) -> dict:
    try:
        rows = parse_billing_log(payload)
    except BillingLogValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict()) from exc

    if not rows:
        raise HTTPException(
            status_code=422,
            detail={"errors": [{"row_index": -1, "message": "payload must contain at least one row"}]},
        )

    clinic_id = rows[0].clinic_id
    log_date = rows[0].timestamp.date()
    rows_ingested = db.save_billing_log(clinic_id, log_date, rows)

    return {"clinic_id": clinic_id, "date": log_date.isoformat(), "rows_ingested": rows_ingested}


@router.get("/reconciliation/{clinic_id}/{log_date}")
def get_reconciliation(clinic_id: str, log_date: date) -> dict:
    rows = db.load_billing_log(clinic_id, log_date)
    return compute_reconciliation(rows)


@router.get("/analytics/{clinic_id}/{log_date}")
def get_analytics(clinic_id: str, log_date: date) -> dict:
    rows = db.load_billing_log(clinic_id, log_date)
    return compute_analytics(rows)


@router.get("/narrative/{clinic_id}/{log_date}")
def get_narrative(clinic_id: str, log_date: date) -> dict:
    rows = db.load_billing_log(clinic_id, log_date)
    report = {
        "reconciliation": compute_reconciliation(rows),
        "analytics": compute_analytics(rows),
    }
    result = generate_narrative(report)
    return {
        "narrative": result.narrative,
        "traced_figures": result.traced_figures,
        "error": result.error,
        "report": report,
    }


def create_app() -> FastAPI:
    app = FastAPI(title="EOD Billing & Analytics Agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app
