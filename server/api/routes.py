"""PatientSynapse REST API routes."""

import logging
import json
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

from server.services.referral import ReferralService, ReferralStatus
from server.services.ocr import extract_text_from_pdf, extract_text_from_image
from server.services.fax_ingestion import FaxIngestionService
from server.emr import get_emr, switch_emr, get_active_emr_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ---- Request/Response models ----

class ReferralApproval(BaseModel):
    overrides: Optional[dict] = None

class ReferralReject(BaseModel):
    reason: Optional[str] = None


# Service instances — injected from main.py
_referral_service: Optional[ReferralService] = None
_fax_ingestion_service: Optional[FaxIngestionService] = None
_smart_auth = None  # Shared SMARTAuth instance

def set_referral_service(svc: ReferralService):
    global _referral_service
    _referral_service = svc

def set_fax_ingestion_service(svc: FaxIngestionService):
    global _fax_ingestion_service
    _fax_ingestion_service = svc

def set_smart_auth(auth):
    global _smart_auth
    _smart_auth = auth

def get_smart_auth():
    if _smart_auth is None:
        from server.auth.smart import SMARTAuth
        return SMARTAuth(get_emr())
    return _smart_auth

def get_referral_service() -> ReferralService:
    if _referral_service is None:
        raise HTTPException(503, "FHIR client not connected. Complete OAuth flow.")
    return _referral_service

def get_fax_ingestion_service() -> FaxIngestionService:
    if _fax_ingestion_service is None:
        raise HTTPException(503, "Fax ingestion service not initialized.")
    return _fax_ingestion_service


# ---- Auth routes ----

@router.get("/auth/status")
async def auth_status():
    """Check if FHIR OAuth is active."""
    auth = get_smart_auth()
    emr = get_emr()
    return {"authenticated": auth.is_authenticated, "emr_provider": emr.name, "fhir_base_url": emr.fhir_base_url}


@router.get("/auth/login")
async def auth_login():
    """Get the OAuth authorization URL to start SMART on FHIR flow (3-legged)."""
    auth = get_smart_auth()
    url = auth.get_authorize_url()
    return {"authorize_url": url}


@router.get("/auth/callback")
async def auth_callback(code: str, state: Optional[str] = None):
    """Handle OAuth callback with authorization code (3-legged)."""
    auth = get_smart_auth()
    try:
        token = await auth.exchange_code(code)
        return {"status": "authenticated", "emr": get_emr().name, "scope": token.scope}
    except Exception as e:
        raise HTTPException(400, f"Token exchange failed: {str(e)}")


@router.post("/auth/connect-service")
async def auth_connect_service():
    """2-legged auth: client_credentials grant (no user login).
    Use for sandbox testing or backend automation."""
    auth = get_smart_auth()
    try:
        token = await auth.client_credentials_connect()
        return {
            "status": "authenticated",
            "emr": get_emr().name,
            "scope": token.scope,
            "expires_in": token.expires_in,
            "flow": "client_credentials",
        }
    except Exception as e:
        raise HTTPException(400, f"Service connect failed: {str(e)}")


# ---- Referral routes ----

@router.post("/referrals/upload")
async def upload_referral(file: UploadFile = File(...)):
    """Upload a fax PDF/image for processing with classification."""
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
    record = await svc.classify_and_process(text, file.filename)
    return _serialize_referral(record)


@router.post("/referrals/upload-text")
async def upload_referral_text(body: dict):
    """Upload raw fax text directly (for testing without OCR)."""
    text = body.get("text", "")
    filename = body.get("filename", "manual-entry.txt")
    if not text.strip():
        raise HTTPException(400, "No text provided")

    svc = get_referral_service()
    record = await svc.classify_and_process(text, filename)
    return _serialize_referral(record)


@router.get("/referrals")
async def list_referrals(status: Optional[str] = Query(None), doc_type: Optional[str] = Query(None)):
    """List referrals, optionally filtered by status and/or document type."""
    svc = get_referral_service()
    filter_status = ReferralStatus(status) if status else None
    records = svc.list_referrals(filter_status)
    if doc_type:
        records = [r for r in records if r.document_type == doc_type]
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


# ---- Fax ingestion routes ----

@router.post("/faxes/poll")
async def poll_faxes():
    """Simulate calling eCW to fetch new incoming faxes.

    Scans the IncomingFaxes/ directory for unprocessed PDFs,
    OCRs them, and runs through the referral pipeline.
    """
    svc = get_fax_ingestion_service()
    records = await svc.poll_once()
    return {
        "fetched": len(records),
        "referrals": [_serialize_referral(r) for r in records],
        "status": svc.get_status(),
    }


@router.get("/faxes/status")
async def fax_inbox_status():
    """Get the current state of the fax inbox."""
    svc = get_fax_ingestion_service()
    return svc.get_status()


@router.post("/faxes/reset")
async def reset_fax_inbox():
    """Reset processed tracking so faxes can be re-ingested."""
    svc = get_fax_ingestion_service()
    svc._processed.clear()
    return {"message": "Fax inbox reset", "status": svc.get_status()}


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


# ---- Settings routes ----

class EMRSwitch(BaseModel):
    provider: str  # "ecw" | "athena"

@router.post("/settings/emr")
async def switch_emr_provider(body: EMRSwitch):
    """Hot-swap the active EMR provider without restarting the server."""
    from server.auth.smart import SMARTAuth
    from server.fhir.client import FHIRClient
    try:
        emr = switch_emr(body.provider)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Reinitialize auth + FHIR chain for new EMR
    auth = SMARTAuth(emr)
    set_smart_auth(auth)
    fhir_client = FHIRClient(auth)
    referral_svc = ReferralService(fhir_client)
    set_referral_service(referral_svc)

    # Rewire fax ingestion to the new referral service
    fax_svc = get_fax_ingestion_service()
    fax_svc.referral_service = referral_svc

    logger.info(f"EMR switched to {emr.name}")
    return {
        "status": "switched",
        "emr_provider": emr.name,
        "emr_provider_key": body.provider,
        "fhir_base_url": emr.fhir_base_url,
    }

@router.get("/settings/emr")
async def get_emr_config():
    """Return current EMR provider info."""
    emr = get_emr()
    return {
        "emr_provider": emr.name,
        "emr_provider_key": get_active_emr_key(),
        "fhir_base_url": emr.fhir_base_url,
        "supported_resources": emr.supported_resources,
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
