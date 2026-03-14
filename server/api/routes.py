"""PatientBridge REST API routes."""

import logging
import json
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

from server.services.referral import ReferralService, ReferralStatus
from server.services.ocr import extract_text_from_pdf, extract_text_from_image
from server.emr import get_emr

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ---- Request/Response models ----

class ReferralApproval(BaseModel):
    overrides: Optional[dict] = None

class ReferralReject(BaseModel):
    reason: Optional[str] = None


# Service instance — injected from main.py
_referral_service: Optional[ReferralService] = None

def set_referral_service(svc: ReferralService):
    global _referral_service
    _referral_service = svc

def get_referral_service() -> ReferralService:
    if _referral_service is None:
        raise HTTPException(503, "FHIR client not connected. Complete OAuth flow.")
    return _referral_service


# ---- Auth routes ----

@router.get("/auth/status")
async def auth_status():
    """Check if FHIR OAuth is active."""
    from server.auth.smart import SMARTAuth
    emr = get_emr()
    auth = SMARTAuth(emr)
    return {"authenticated": auth.is_authenticated, "emr_provider": emr.name, "fhir_base_url": emr.fhir_base_url}


@router.get("/auth/login")
async def auth_login():
    """Get the OAuth authorization URL to start SMART on FHIR flow."""
    from server.auth.smart import SMARTAuth
    emr = get_emr()
    auth = SMARTAuth(emr)
    url = auth.get_authorize_url()
    return {"authorize_url": url}


@router.get("/auth/callback")
async def auth_callback(code: str, state: Optional[str] = None):
    """Handle OAuth callback with authorization code."""
    from server.auth.smart import SMARTAuth
    emr = get_emr()
    auth = SMARTAuth(emr)
    try:
        token = await auth.exchange_code(code)
        return {"status": "authenticated", "emr": emr.name, "scope": token.scope}
    except Exception as e:
        raise HTTPException(400, f"Token exchange failed: {str(e)}")


# ---- Referral routes ----

@router.post("/referrals/upload")
async def upload_referral(file: UploadFile = File(...)):
    """Upload a fax PDF/image for processing."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    content = await file.read()
    ext = Path(file.filename).suffix.lower()

    # Extract text via OCR
    if ext == ".pdf":
        text = await extract_text_from_pdf(content)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        text = await extract_text_from_image(content)
    else:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    if not text.strip():
        raise HTTPException(422, "Could not extract text from file")

    svc = get_referral_service()
    record = await svc.process_fax(text, file.filename)
    return _serialize_referral(record)


@router.post("/referrals/upload-text")
async def upload_referral_text(body: dict):
    """Upload raw fax text directly (for testing without OCR)."""
    text = body.get("text", "")
    filename = body.get("filename", "manual-entry.txt")
    if not text.strip():
        raise HTTPException(400, "No text provided")

    svc = get_referral_service()
    record = await svc.process_fax(text, filename)
    return _serialize_referral(record)


@router.get("/referrals")
async def list_referrals(status: Optional[str] = Query(None)):
    """List referrals, optionally filtered by status."""
    svc = get_referral_service()
    filter_status = ReferralStatus(status) if status else None
    records = svc.list_referrals(filter_status)
    return [_serialize_referral(r) for r in records]


@router.get("/referrals/{ref_id}")
async def get_referral(ref_id: str):
    """Get a specific referral by ID."""
    svc = get_referral_service()
    record = svc.get_referral(ref_id)
    if not record:
        raise HTTPException(404, f"Referral {ref_id} not found")
    return _serialize_referral(record)


@router.post("/referrals/{ref_id}/approve")
async def approve_referral(ref_id: str, body: ReferralApproval = ReferralApproval()):
    """Approve a referral and push to eCW."""
    svc = get_referral_service()
    record = await svc.approve_and_push(ref_id, body.overrides)
    return _serialize_referral(record)


@router.post("/referrals/{ref_id}/reject")
async def reject_referral(ref_id: str, body: ReferralReject = ReferralReject()):
    """Reject a referral."""
    svc = get_referral_service()
    record = svc.get_referral(ref_id)
    if not record:
        raise HTTPException(404, f"Referral {ref_id} not found")
    record.status = ReferralStatus.REJECTED
    record.error = body.reason
    return _serialize_referral(record)


# ---- Scheduling routes ----

@router.get("/scheduling/providers")
async def search_providers(specialty: Optional[str] = Query(None)):
    """Search for providers, optionally by specialty."""
    return {"status": "not_connected", "message": "Complete OAuth flow to search providers"}


@router.get("/scheduling/insurance/{patient_id}")
async def verify_insurance(patient_id: str):
    """Verify patient insurance coverage."""
    return {"status": "not_connected", "message": "Complete OAuth flow to verify insurance"}


# ---- RCM routes ----

@router.get("/rcm/patient/{patient_id}")
async def patient_billing(patient_id: str):
    """Get billing context for a patient."""
    return {"status": "not_connected", "message": "Complete OAuth flow for RCM data"}


@router.get("/rcm/dashboard")
async def rcm_dashboard():
    """Get RCM dashboard summary."""
    emr = get_emr()
    return {
        "total_referrals": 0,
        "pending_review": 0,
        "completed_today": 0,
        "revenue_this_month": 0,
        "message": f"Connect to {emr.name} for live data",
    }


# ---- System routes ----

@router.get("/status")
async def system_status():
    """System health check."""
    from server.config import get_settings
    settings = get_settings()
    emr = get_emr()
    return {
        "status": "running",
        "emr_provider": emr.name,
        "emr_provider_key": settings.emr_provider,
        "llm_provider": settings.llm_provider,
        "fhir_connected": _referral_service is not None,
        "app_env": settings.app_env,
    }


# ---- Helpers ----

def _serialize_referral(record) -> dict:
    """Convert ReferralRecord to JSON-safe dict."""
    d = asdict(record)
    d["status"] = record.status.value
    return d
