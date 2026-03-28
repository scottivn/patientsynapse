"""PatientSynapse REST API routes."""

import logging
import json
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import asdict
from collections import defaultdict

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends, Response, Request
from pydantic import BaseModel, Field as PydanticField

from server.auth.dependencies import get_current_user, require_admin, require_role, require_dev_env

from server.services.referral import ReferralService, ReferralStatus
from server.services.ocr import extract_text_from_pdf, extract_text_from_image
from server.services.fax_ingestion import FaxIngestionService
from server.services.dme import DMEService, DMEOrderStatus
from server.services.referral_auth import ReferralAuthService, ReferralAuthStatus
from server.services.prescription_monitor import PrescriptionMonitorService
from server.emr import get_emr, switch_emr, get_active_emr_key
from server.llm import get_llm, switch_llm, get_active_llm_key
from server.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ---- Request/Response models ----

class ReferralApproval(BaseModel):
    overrides: Optional[dict] = None

class ReferralReject(BaseModel):
    reason: Optional[str] = None


class DMEOrderCreate(BaseModel):
    """Validated input for DME order creation (public patient portal)."""
    patient_first_name: str = PydanticField(..., min_length=1, max_length=100)
    patient_last_name: str = PydanticField(..., min_length=1, max_length=100)
    patient_dob: str = PydanticField(default="", max_length=10)
    patient_phone: str = PydanticField(default="", max_length=20)
    patient_email: str = PydanticField(default="", max_length=254)
    patient_address: str = PydanticField(default="", max_length=200)
    patient_city: str = PydanticField(default="", max_length=100)
    patient_state: str = PydanticField(default="", max_length=2)
    patient_zip: str = PydanticField(default="", max_length=10)
    patient_id: str = PydanticField(default="", max_length=100)
    insurance_payer: str = PydanticField(default="", max_length=200)
    insurance_member_id: str = PydanticField(default="", max_length=100)
    insurance_group: str = PydanticField(default="", max_length=100)
    equipment_category: str = PydanticField(default="", max_length=200)
    equipment_description: str = PydanticField(default="", max_length=500)
    quantity: int = PydanticField(default=1, ge=1, le=100)
    diagnosis_code: str = PydanticField(default="", max_length=20)
    diagnosis_description: str = PydanticField(default="", max_length=500)
    referring_physician: str = PydanticField(default="", max_length=200)
    referring_npi: str = PydanticField(default="", max_length=10)
    clinical_notes: str = PydanticField(default="", max_length=2000)
    hcpcs_codes: list[str] = PydanticField(default=[])
    supply_months: int = PydanticField(default=6, ge=1, le=36)


class DMEAdminOrderCreate(DMEOrderCreate):
    """Admin-only order creation — includes auto-refill and origin fields."""
    auto_replace: bool = False
    auto_replace_frequency: Optional[str] = PydanticField(default=None, max_length=20)
    origin: str = PydanticField(default="staff_initiated", max_length=50)


class DMERefillToggle(BaseModel):
    """Patient auto-refill opt-in/out via confirmation token."""
    auto_replace: bool
    frequency: str = PydanticField(default="quarterly", max_length=20)


# ---- Login rate limiter ----

class _LoginRateLimiter:
    """IP-based rate limiter for login attempts. Locks out after max_attempts
    failed logins within the window. Thread-safe via GIL for in-memory use."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # {ip: [(timestamp, success), ...]}
        self._attempts: dict[str, list[tuple[float, bool]]] = defaultdict(list)

    def _prune(self, ip: str) -> None:
        cutoff = time.time() - self.window_seconds
        self._attempts[ip] = [
            (ts, ok) for ts, ok in self._attempts[ip] if ts > cutoff
        ]
        if not self._attempts[ip]:
            del self._attempts[ip]

    def check(self, ip: str) -> None:
        """Raise 429 if the IP has exceeded the failure limit."""
        self._prune(ip)
        failures = sum(1 for _, ok in self._attempts.get(ip, []) if not ok)
        if failures >= self.max_attempts:
            logger.warning(f"Login rate limit reached for IP {ip}")
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Try again later.",
                headers={"Retry-After": str(self.window_seconds)},
            )

    def record(self, ip: str, success: bool) -> None:
        self._attempts[ip].append((time.time(), success))
        if success:
            # Clear history on successful login
            self._attempts.pop(ip, None)


_login_limiter = _LoginRateLimiter()
_referral_service: Optional[ReferralService] = None
_fax_ingestion_service: Optional[FaxIngestionService] = None
_dme_service: DMEService = DMEService()
_referral_auth_service: ReferralAuthService = ReferralAuthService()
_prescription_monitor: Optional[PrescriptionMonitorService] = None
_smart_auth = None  # Shared SMARTAuth instance

def set_prescription_monitor(svc: PrescriptionMonitorService):
    global _prescription_monitor
    _prescription_monitor = svc

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


# ---- Admin auth routes ----

class AdminLogin(BaseModel):
    username: str
    password: str


@router.post("/admin/login", tags=["Auth"])
async def admin_login(body: AdminLogin, request: Request, response: Response):
    """Authenticate admin user, set HttpOnly JWT cookies."""
    from server.auth.users import get_user_by_username, verify_password, update_last_login
    from server.auth.jwt_auth import create_access_token, create_refresh_token
    from server.config import get_settings

    client_ip = request.client.host if request.client else "unknown"
    _login_limiter.check(client_ip)

    user = await get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        _login_limiter.record(client_ip, success=False)
        # Persist failed login to audit log for HIPAA compliance
        from server.auth.audit import log_phi_access
        import asyncio
        asyncio.create_task(log_phi_access(
            user_type="unauthenticated",
            user_id=body.username,
            action="LOGIN_FAILED",
            resource_type="auth",
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent", "")[:200],
        ))
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.get("is_active", 1):
        raise HTTPException(status_code=403, detail="Account deactivated")

    _login_limiter.record(client_ip, success=True)

    user_role = user["role"]
    access_token = create_access_token(user["id"], user["username"], user_role)
    refresh_token = create_refresh_token(user["id"])
    await update_last_login(user["id"])

    settings = get_settings()
    is_prod = settings.app_env != "development"

    response.set_cookie(
        key="access_token", value=access_token,
        httponly=True, samesite="lax", secure=is_prod,
        max_age=settings.jwt_access_token_expire_minutes * 60, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, samesite="lax", secure=is_prod,
        max_age=settings.jwt_refresh_token_expire_days * 86400, path="/api/admin/refresh",
    )
    return {"authenticated": True, "username": user["username"], "role": user_role, "user_id": str(user["id"])}


@router.post("/admin/refresh", tags=["Auth"])
async def admin_refresh(request: Request, response: Response):
    """Refresh access token using refresh cookie."""
    from server.auth.jwt_auth import decode_token, create_access_token
    from server.auth.users import get_user_by_username
    from server.config import get_settings

    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        claims = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Refresh token only has sub (user_id) — look up user by ID
    from server.auth.users import get_user_by_id
    user = await get_user_by_id(int(claims["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", 1):
        raise HTTPException(status_code=403, detail="Account deactivated")
    access_token = create_access_token(user["id"], user["username"], user["role"])

    settings = get_settings()
    is_prod = settings.app_env != "development"
    response.set_cookie(
        key="access_token", value=access_token,
        httponly=True, samesite="lax", secure=is_prod,
        max_age=settings.jwt_access_token_expire_minutes * 60, path="/",
    )
    return {"refreshed": True}


@router.post("/admin/logout", tags=["Auth"])
async def admin_logout(response: Response):
    """Clear auth cookies."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/admin/refresh")
    return {"logged_out": True}


@router.get("/admin/me", tags=["Auth"])
async def admin_me(user: dict = Depends(get_current_user)):
    """Return current authenticated user info."""
    return {"username": user["username"], "role": user["role"], "user_id": user["user_id"]}


# ---- User management routes (admin only) ----

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "dme"

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

class PasswordReset(BaseModel):
    password: str


@router.get("/admin/users", tags=["User Management"], dependencies=[Depends(require_admin)])
async def get_users():
    """List all users (admin only)."""
    from server.auth.users import list_users
    return await list_users()


@router.post("/admin/users", tags=["User Management"], dependencies=[Depends(require_admin)])
async def create_user_route(body: UserCreate):
    """Create a new user (admin only)."""
    from server.auth.users import create_user
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    try:
        user = await create_user(body.username, body.password, body.role)
        return user
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/admin/users/{user_id}", tags=["User Management"], dependencies=[Depends(require_admin)])
async def update_user_route(user_id: int, body: UserUpdate, user: dict = Depends(get_current_user)):
    """Update a user's role or active status (admin only)."""
    from server.auth.users import update_user
    if body.role is None and body.is_active is None:
        raise HTTPException(400, "Nothing to update — provide role and/or is_active")
    # Prevent self-deactivation
    if body.is_active is False and str(user_id) == user["user_id"]:
        raise HTTPException(400, "Cannot deactivate your own account")
    try:
        result = await update_user(user_id, role=body.role, is_active=body.is_active)
        if not result:
            raise HTTPException(404, "User not found")
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/admin/users/{user_id}/reset-password", tags=["User Management"], dependencies=[Depends(require_admin)])
async def reset_password_route(user_id: int, body: PasswordReset):
    """Reset a user's password (admin only)."""
    from server.auth.users import reset_password
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    success = await reset_password(user_id, body.password)
    if not success:
        raise HTTPException(404, "User not found")
    return {"reset": True}


@router.delete("/admin/users/{user_id}", tags=["User Management"], dependencies=[Depends(require_admin)])
async def delete_user_route(user_id: int, user: dict = Depends(get_current_user)):
    """Delete a user (admin only). Cannot delete yourself."""
    from server.auth.users import delete_user
    if str(user_id) == user["user_id"]:
        raise HTTPException(400, "Cannot delete your own account")
    success = await delete_user(user_id)
    if not success:
        raise HTTPException(404, "User not found")
    return {"deleted": True}


@router.get("/admin/roles", tags=["User Management"])
async def get_roles(user: dict = Depends(get_current_user)):
    """Return available roles and their descriptions."""
    return [
        {"key": "admin", "label": "Admin", "description": "Full access to all features"},
        {"key": "front_office", "label": "Front Office", "description": "Faxes, referrals, referral auths, scheduling"},
        {"key": "dme", "label": "DME", "description": "DME workflow, prescriptions, allowable rates"},
    ]


# ---- SMART on FHIR auth routes ----

@router.get("/auth/status", tags=["SMART on FHIR"], dependencies=[Depends(require_admin)])
async def auth_status():
    """Check if FHIR OAuth is active."""
    auth = get_smart_auth()
    emr = get_emr()
    return {"authenticated": auth.is_authenticated, "emr_provider": emr.name, "fhir_base_url": emr.fhir_base_url}


@router.get("/auth/login", tags=["SMART on FHIR"], dependencies=[Depends(require_admin)])
async def auth_login():
    """Get the OAuth authorization URL to start SMART on FHIR flow (3-legged)."""
    auth = get_smart_auth()
    url = auth.get_authorize_url()
    return {"authorize_url": url}


@router.get("/auth/callback", tags=["SMART on FHIR"], dependencies=[Depends(require_admin)])
async def auth_callback(code: str, state: Optional[str] = None):
    """Handle OAuth callback with authorization code (3-legged)."""
    auth = get_smart_auth()
    try:
        token = await auth.exchange_code(code)
        return {"status": "authenticated", "emr": get_emr().name, "scope": token.scope}
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        raise HTTPException(400, "Token exchange failed. Check server logs.")


@router.post("/auth/connect-service", tags=["SMART on FHIR"], dependencies=[Depends(require_admin)])
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
        logger.error(f"Service connect failed: {e}")
        raise HTTPException(400, "Service connect failed. Check server logs.")


# ---- Referral routes (admin + front_office) ----

@router.post("/referrals/upload", tags=["Referrals"], dependencies=[Depends(require_role("admin", "front_office"))])
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


@router.post("/referrals/upload-text", tags=["Referrals"], dependencies=[Depends(require_role("admin", "front_office"))])
async def upload_referral_text(body: dict):
    """Upload raw fax text directly (for testing without OCR)."""
    text = body.get("text", "")
    filename = body.get("filename", "manual-entry.txt")
    if not text.strip():
        raise HTTPException(400, "No text provided")

    svc = get_referral_service()
    record = await svc.classify_and_process(text, filename)
    return _serialize_referral(record)


@router.get("/referrals", tags=["Referrals"], dependencies=[Depends(require_role("admin", "front_office"))])
async def list_referrals(status: Optional[str] = Query(None), doc_type: Optional[str] = Query(None)):
    """List referrals, optionally filtered by status and/or document type."""
    svc = get_referral_service()
    filter_status = ReferralStatus(status) if status else None
    records = await svc.list_referrals(filter_status)
    if doc_type:
        records = [r for r in records if r.document_type == doc_type]
    return [_serialize_referral(r) for r in records]


@router.get("/referrals/{ref_id}", tags=["Referrals"], dependencies=[Depends(require_role("admin", "front_office"))])
async def get_referral(ref_id: str):
    """Get a specific referral by ID."""
    svc = get_referral_service()
    record = await svc.get_referral(ref_id)
    if not record:
        raise HTTPException(404, f"Referral {ref_id} not found")
    return _serialize_referral(record)


@router.post("/referrals/{ref_id}/approve", tags=["Referrals"], dependencies=[Depends(require_role("admin", "front_office"))])
async def approve_referral(ref_id: str, body: ReferralApproval = ReferralApproval()):
    """Approve a referral and push to eCW."""
    svc = get_referral_service()
    record = await svc.approve_and_push(ref_id, body.overrides)
    return _serialize_referral(record)


@router.post("/referrals/{ref_id}/reject", tags=["Referrals"], dependencies=[Depends(require_role("admin", "front_office"))])
async def reject_referral(ref_id: str, body: ReferralReject = ReferralReject()):
    """Reject a referral."""
    svc = get_referral_service()
    record = await svc.get_referral(ref_id)
    if not record:
        raise HTTPException(404, f"Referral {ref_id} not found")
    record.status = ReferralStatus.REJECTED
    record.error = body.reason
    from server.services.referral import _save_record
    await _save_record(record)
    return _serialize_referral(record)


# ---- Fax ingestion routes ----

@router.post("/faxes/poll", tags=["Fax Ingestion"], dependencies=[Depends(require_role("admin", "front_office"))])
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
        "status": await svc.get_status(),
    }


@router.get("/faxes/status", tags=["Fax Ingestion"], dependencies=[Depends(require_role("admin", "front_office"))])
async def fax_inbox_status():
    """Get the current state of the fax inbox."""
    svc = get_fax_ingestion_service()
    return await svc.get_status()


@router.post("/faxes/reset", tags=["Fax Ingestion"], dependencies=[Depends(require_role("admin", "front_office"))])
async def reset_fax_inbox():
    """Reset processed tracking so faxes can be re-ingested."""
    from server.db import db_execute
    await db_execute("DELETE FROM fax_processed")
    svc = get_fax_ingestion_service()
    return {"message": "Fax inbox reset", "status": await svc.get_status()}


@router.post("/faxes/retry-failed", tags=["Fax Ingestion"], dependencies=[Depends(require_role("admin", "front_office"))])
async def retry_failed_faxes():
    """Clear failed fax entries and reprocess them."""
    svc = get_fax_ingestion_service()
    records = await svc.retry_failed()
    return {
        "retried": len(records),
        "referrals": [_serialize_referral(r) for r in records],
        "status": await svc.get_status(),
    }


@router.get("/faxes/file/{filename}/info", tags=["Fax Ingestion"], dependencies=[Depends(require_role("admin", "front_office"))])
async def fax_file_info(filename: str):
    """Get metadata about a fax file (page count, content type, size)."""
    svc = get_fax_ingestion_service()
    file_path = _resolve_fax_path(svc.inbox_dir, filename)

    ext = file_path.suffix.lower()
    content_type = _fax_content_type(ext)
    size_bytes = file_path.stat().st_size
    pages = 1

    if ext == ".pdf":
        import fitz
        doc = fitz.open(str(file_path))
        pages = len(doc)
        doc.close()
    elif ext in (".tiff", ".tif"):
        from PIL import Image
        img = Image.open(file_path)
        try:
            pages = img.n_frames
        except Exception:
            pages = 1
        img.close()

    return {"pages": pages, "content_type": content_type, "size_bytes": size_bytes}


@router.get("/faxes/file/{filename}/page/{page_num}", tags=["Fax Ingestion"], dependencies=[Depends(require_role("admin", "front_office"))])
async def fax_file_page(filename: str, page_num: int):
    """Render a specific page of a fax file as PNG (for TIFF/PDF viewing in browser)."""
    svc = get_fax_ingestion_service()
    file_path = _resolve_fax_path(svc.inbox_dir, filename)

    ext = file_path.suffix.lower()
    import io

    if ext == ".pdf":
        import fitz
        doc = fitz.open(str(file_path))
        num_pages = len(doc)
        if page_num < 0 or page_num >= num_pages:
            doc.close()
            raise HTTPException(404, f"Page {page_num} not found (document has {num_pages} pages)")
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)
        png_bytes = pix.tobytes("png")
        doc.close()
        return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "no-store"})

    elif ext in (".tiff", ".tif"):
        from PIL import Image
        img = Image.open(file_path)
        try:
            img.seek(page_num)
        except EOFError:
            raise HTTPException(404, f"Page {page_num} not found")
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})

    elif ext in (".png", ".jpg", ".jpeg"):
        if page_num != 0:
            raise HTTPException(404, "Single-page image, only page 0 exists")
        return Response(
            content=file_path.read_bytes(),
            media_type=_fax_content_type(ext),
            headers={"Cache-Control": "no-store"},
        )

    raise HTTPException(400, f"Unsupported file type: {ext}")


@router.get("/faxes/file/{filename}", tags=["Fax Ingestion"], dependencies=[Depends(require_role("admin", "front_office"))])
async def serve_fax_file(filename: str):
    """Serve an original fax file for viewing. Path traversal protected."""
    from fastapi.responses import FileResponse
    svc = get_fax_ingestion_service()
    file_path = _resolve_fax_path(svc.inbox_dir, filename)

    ext = file_path.suffix.lower()
    return FileResponse(
        path=str(file_path),
        media_type=_fax_content_type(ext),
        headers={"Cache-Control": "no-store"},
    )


def _resolve_fax_path(inbox_dir: Path, filename: str) -> Path:
    """Resolve a fax filename against inbox_dir with path traversal protection."""
    if "/" in filename or "\\" in filename or ".." in filename or "\x00" in filename:
        raise HTTPException(400, "Invalid filename")
    file_path = (inbox_dir / filename).resolve()
    if not str(file_path).startswith(str(inbox_dir.resolve())):
        raise HTTPException(400, "Invalid filename")
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    return file_path


def _fax_content_type(ext: str) -> str:
    """Map file extension to content type."""
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }.get(ext, "application/octet-stream")


# ---- Scheduling routes ----

@router.get("/scheduling/providers", tags=["Scheduling"], dependencies=[Depends(require_role("admin", "front_office"))])
async def search_providers(specialty: Optional[str] = Query(None)):
    """Search for providers, optionally by specialty."""
    settings = get_settings()
    if settings.use_stub_fhir:
        providers = [
            {"name": "Dr. Sarah Chen", "specialty": "Pulmonology", "location": "Main Office - Suite 200", "phone": "(555) 234-5678"},
            {"name": "Dr. Michael Torres", "specialty": "Pulmonology", "location": "East Campus Clinic", "phone": "(555) 345-6789"},
            {"name": "Dr. Lisa Patel", "specialty": "Sleep Medicine", "location": "Sleep Center - Bldg B", "phone": "(555) 456-7890"},
            {"name": "Dr. James Wright", "specialty": "Internal Medicine", "location": "Main Office - Suite 100", "phone": "(555) 567-8901"},
            {"name": "Dr. Maria Gonzalez", "specialty": "Cardiology", "location": "Heart Center", "phone": "(555) 678-9012"},
        ]
        if specialty:
            s = specialty.lower()
            providers = [p for p in providers if s in p["specialty"].lower()]
        return {"providers": providers}
    return {"status": "not_connected", "message": "Complete OAuth flow to search providers"}


@router.get("/scheduling/insurance/{patient_id}", tags=["Scheduling"], dependencies=[Depends(require_role("admin", "front_office"))])
async def verify_insurance(patient_id: str):
    """Verify patient insurance coverage."""
    settings = get_settings()
    if settings.use_stub_fhir:
        return {
            "coverages": [
                {
                    "payor": "Blue Cross Blue Shield",
                    "status": "active",
                    "subscriber_id": "XWB123456789",
                    "period_start": "2025-01-01",
                    "period_end": "2026-12-31",
                },
            ]
        }
    return {"status": "not_connected", "message": "Complete OAuth flow to verify insurance"}


# ---- RCM routes ----

@router.get("/rcm/patient/{patient_id}", tags=["RCM"], dependencies=[Depends(require_admin)])
async def patient_billing(patient_id: str):
    """Get billing context for a patient."""
    settings = get_settings()
    if settings.use_stub_fhir:
        return {
            "encounters": [
                {"type": "Office Visit", "class": "ambulatory", "date": "2026-03-15"},
                {"type": "Follow-up", "class": "ambulatory", "date": "2026-02-28"},
                {"type": "Sleep Study", "class": "ambulatory", "date": "2026-01-10"},
            ],
            "conditions": [
                {"code": "G47.33", "display": "Obstructive sleep apnea"},
                {"code": "I10", "display": "Essential hypertension"},
                {"code": "E11.9", "display": "Type 2 diabetes mellitus"},
            ],
            "procedures": [
                {"code": "95810", "display": "Polysomnography", "status": "completed", "date": "2026-01-10"},
            ],
            "insurance": {"id": "cov-demo-001", "payor": "Blue Cross Blue Shield", "status": "active"},
        }
    return {"status": "not_connected", "message": "Complete OAuth flow for RCM data"}


@router.get("/rcm/dashboard", tags=["RCM"], dependencies=[Depends(require_admin)])
async def rcm_dashboard():
    """Get RCM dashboard summary."""
    settings = get_settings()
    # Pull live DME order stats from DB
    dme_stats = await _dme_service.get_dashboard()

    if settings.use_stub_fhir:
        return {
            # Referral pipeline
            "referrals_processed": 142,
            "referrals_pending": 17,
            "referrals_approved": 118,
            "referrals_rejected": 7,
            # Live DME stats from DB
            "dme_orders_total": dme_stats.get("total", 0),
            "dme_orders_fulfilled": dme_stats.get("fulfilled", 0),
            "dme_orders_in_progress": dme_stats.get("in_progress", 0),
            # Revenue estimates
            "revenue": {
                "collected_mtd": 28_450.00,
                "collected_ytd": 187_320.00,
                "outstanding": 42_180.00,
                "avg_reimbursement": 312.50,
            },
            # A/R aging buckets
            "ar_aging": [
                {"bucket": "0-30 days", "amount": 18_200.00, "count": 42},
                {"bucket": "31-60 days", "amount": 12_450.00, "count": 28},
                {"bucket": "61-90 days", "amount": 7_830.00, "count": 15},
                {"bucket": "90+ days", "amount": 3_700.00, "count": 8},
            ],
            # Claims pipeline
            "claims": {
                "submitted": 89,
                "paid": 72,
                "denied": 11,
                "pending": 6,
                "denial_rate": 12.4,
            },
            # Top denial reasons
            "denial_reasons": [
                {"reason": "Missing prior authorization", "count": 4, "percent": 36.4},
                {"reason": "Non-covered service", "count": 3, "percent": 27.3},
                {"reason": "Patient not eligible on DOS", "count": 2, "percent": 18.2},
                {"reason": "Duplicate claim", "count": 1, "percent": 9.1},
                {"reason": "Timely filing exceeded", "count": 1, "percent": 9.1},
            ],
            # Revenue by payer
            "revenue_by_payer": [
                {"payer": "Blue Cross Blue Shield", "amount": 63_780.00, "claims": 31},
                {"payer": "Medicare", "amount": 48_250.00, "claims": 26},
                {"payer": "UnitedHealthcare", "amount": 32_100.00, "claims": 18},
                {"payer": "Aetna", "amount": 24_890.00, "claims": 14},
                {"payer": "Humana", "amount": 18_300.00, "claims": 11},
            ],
            "payer_mix": [
                {"payer": "Blue Cross Blue Shield", "percent": 34.2},
                {"payer": "UnitedHealthcare", "percent": 22.5},
                {"payer": "Aetna", "percent": 18.1},
                {"payer": "Medicare", "percent": 15.8},
                {"payer": "Medicaid", "percent": 9.4},
            ],
            "top_diagnoses": [
                {"code": "G47.33", "display": "Obstructive sleep apnea", "count": 38},
                {"code": "J44.1", "display": "COPD with acute exacerbation", "count": 22},
                {"code": "E11.9", "display": "Type 2 diabetes mellitus", "count": 19},
                {"code": "I10", "display": "Essential hypertension", "count": 15},
                {"code": "M54.5", "display": "Low back pain", "count": 12},
            ],
            # Monthly trend (last 6 months)
            "monthly_trend": [
                {"month": "Oct 2025", "revenue": 26_100.00, "claims": 68},
                {"month": "Nov 2025", "revenue": 29_800.00, "claims": 74},
                {"month": "Dec 2025", "revenue": 31_200.00, "claims": 79},
                {"month": "Jan 2026", "revenue": 33_450.00, "claims": 82},
                {"month": "Feb 2026", "revenue": 38_320.00, "claims": 91},
                {"month": "Mar 2026", "revenue": 28_450.00, "claims": 76},
            ],
        }
    emr = get_emr()
    return {
        "referrals_processed": 0,
        "referrals_pending": 0,
        "referrals_approved": 0,
        "referrals_rejected": 0,
        "dme_orders_total": dme_stats.get("total", 0),
        "dme_orders_fulfilled": dme_stats.get("fulfilled", 0),
        "dme_orders_in_progress": dme_stats.get("in_progress", 0),
        "revenue": {"collected_mtd": 0, "collected_ytd": 0, "outstanding": 0, "avg_reimbursement": 0},
        "ar_aging": [],
        "claims": {"submitted": 0, "paid": 0, "denied": 0, "pending": 0, "denial_rate": 0},
        "denial_reasons": [],
        "revenue_by_payer": [],
        "payer_mix": [],
        "top_diagnoses": [],
        "monthly_trend": [],
        "message": f"Connect to {emr.name} for live data",
    }


# ---- Settings routes ----

class EMRSwitch(BaseModel):
    provider: str  # "ecw" | "athena"

@router.post("/settings/emr", tags=["Settings"], dependencies=[Depends(require_admin)])
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

    # Rewire referral auth service
    _referral_auth_service.set_fhir_client(fhir_client)

    # Rewire DME service
    _dme_service.set_fhir_client(fhir_client)

    logger.info(f"EMR switched to {emr.name}")
    return {
        "status": "switched",
        "emr_provider": emr.name,
        "emr_provider_key": body.provider,
        "fhir_base_url": emr.fhir_base_url,
    }

@router.get("/settings/emr", tags=["Settings"], dependencies=[Depends(require_admin)])
async def get_emr_config():
    """Return current EMR provider info."""
    emr = get_emr()
    return {
        "emr_provider": emr.name,
        "emr_provider_key": get_active_emr_key(),
        "fhir_base_url": emr.fhir_base_url,
        "supported_resources": emr.supported_resources,
    }


class LLMSwitch(BaseModel):
    provider: str  # "grok" | "openai" | "anthropic" | "ollama"

@router.post("/settings/llm", tags=["Settings"], dependencies=[Depends(require_admin)])
async def switch_llm_provider(body: LLMSwitch):
    """Hot-swap the active LLM provider without restarting the server."""
    try:
        llm = switch_llm(body.provider)
    except ValueError as e:
        raise HTTPException(400, str(e))
    logger.info(f"LLM switched to {body.provider}")
    return {
        "status": "switched",
        "llm_provider": body.provider,
    }

@router.get("/settings/llm", tags=["Settings"], dependencies=[Depends(require_admin)])
async def get_llm_config():
    """Return current LLM provider info."""
    return {
        "llm_provider": get_active_llm_key(),
    }


# ---- System routes ----

@router.get("/status", tags=["System"])
async def system_status():
    """System health check."""
    from server.config import get_settings
    settings = get_settings()
    emr = get_emr()
    return {
        "status": "running",
        "emr_provider": emr.name,
        "emr_provider_key": get_active_emr_key(),
        "llm_provider": get_active_llm_key(),
        "fhir_connected": _referral_service is not None,
        "app_env": settings.app_env,
    }


# ---- DME routes ----

class DMEPatientVerify(BaseModel):
    patient_id: str
    dob: str  # YYYY-MM-DD

class DMEOrderApproval(BaseModel):
    notes: Optional[str] = None

class DMEOrderReject(BaseModel):
    reason: Optional[str] = None

class DMEHoldOrder(BaseModel):
    reason: str = ""

class DMESendConfirmation(BaseModel):
    send_via: str = "sms"  # "sms", "email", or "both"

class DMEPatientConfirm(BaseModel):
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    fulfillment_method: str = "not_selected"  # "pickup" or "ship"
    patient_notes: Optional[str] = None
    selected_items: Optional[List[str]] = None  # for bundle orders
    skip: bool = False

class DMEPatientReject(BaseModel):
    reason: str = ""
    callback_requested: bool = False

class DMEMarkOrdered(BaseModel):
    vendor_name: str = ""
    vendor_order_id: str = ""

class DMEMarkShipped(BaseModel):
    tracking_number: str = ""
    carrier: str = ""
    estimated_delivery: str = ""


@router.post("/dme/patient-verify", tags=["DME Patient Portal"])
async def dme_patient_verify(body: DMEPatientVerify):
    """Verify a patient's identity against EMR records for DME portal access.

    Attempts FHIR Patient lookup; falls back to stub if EMR not connected.
    """
    auth = get_smart_auth()
    if auth.is_authenticated and _referral_service:
        try:
            from server.fhir.resources import PatientResource
            patients_res = PatientResource(_referral_service.fhir)
            # Search by patient ID
            from server.fhir.client import FHIRClient
            patient = await _referral_service.fhir.read("Patient", body.patient_id)
            if patient:
                p_dob = patient.get("birthDate", "")
                if p_dob == body.dob:
                    name = patient.get("name", [{}])[0]
                    given = name.get("given", [""])[0] if name.get("given") else ""
                    family = name.get("family", "")
                    phone = ""
                    for t in patient.get("telecom", []):
                        if t.get("system") == "phone":
                            phone = t.get("value", "")
                            break
                    addr = patient.get("address", [{}])[0] if patient.get("address") else {}
                    return {
                        "verified": True,
                        "patient": {
                            "id": body.patient_id,
                            "first_name": given,
                            "last_name": family,
                            "dob": p_dob,
                            "phone": phone,
                            "address": (addr.get("line", [""])[0] if addr.get("line") else ""),
                            "city": addr.get("city", ""),
                            "state": addr.get("state", ""),
                            "zip": addr.get("postalCode", ""),
                            "insurance_name": "",
                            "insurance_id": "",
                        }
                    }
                else:
                    return {"verified": False, "message": "Date of birth does not match our records."}
        except Exception as e:
            logger.warning(f"FHIR patient verify failed: {e}")
            # Fall through to stub

    # Stub: accept any patient_id + dob for demo/dev (EMR not connected)
    return {
        "verified": True,
        "patient": {
            "id": body.patient_id,
            "first_name": "",
            "last_name": "",
            "dob": body.dob,
            "phone": "",
            "address": "",
            "city": "",
            "state": "",
            "zip": "",
            "insurance_name": "",
            "insurance_id": "",
        },
        "message": "EMR not connected — verified in demo mode. Patient info not pre-filled.",
    }


@router.get("/dme/patients/search", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_patient_search(
    family: str = Query("", min_length=0, max_length=100),
    given: str = Query("", min_length=0, max_length=100),
    dob: str = Query("", max_length=10),
    mrn: str = Query("", max_length=100),
):
    """Search EMR for patients by name/DOB or MRN. Returns demographics, insurance, devices, and order history."""
    if mrn:
        return await _dme_service.search_patients_by_mrn(mrn)
    if not family and not given:
        raise HTTPException(400, "Provide at least a first or last name, or an MRN")
    return await _dme_service.search_patients(family=family, given=given, dob=dob)


@router.post("/dme/admin/orders", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def create_admin_dme_order(body: DMEAdminOrderCreate):
    """Staff-initiated DME order creation with auto-refill support."""
    order = await _dme_service.create_order(body.model_dump())
    return _serialize_dme_order(order)


@router.post("/dme/orders", tags=["DME Patient Portal"])
async def create_dme_order(body: DMEOrderCreate):
    """Submit a new DME order from the patient portal."""
    order = await _dme_service.create_order(body.model_dump())
    return _serialize_dme_order(order)


@router.get("/dme/orders", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def list_dme_orders(status: Optional[str] = Query(None)):
    """List DME orders for the admin portal."""
    filter_status = DMEOrderStatus(status) if status else None
    orders = await _dme_service.list_orders(filter_status)
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/auto-replace-due", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_auto_replace_due():
    """Get fulfilled orders with auto-replace due today or past due."""
    orders = await _dme_service.get_auto_replace_due()
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/incoming", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_incoming_requests():
    """Get new patient requests (pending, non-auto-refill)."""
    orders = await _dme_service.get_incoming_requests()
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/auto-refill-pending", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_auto_refill_pending():
    """Get auto-refill orders pending action (due or past due + pending auto-refills)."""
    orders = await _dme_service.get_auto_refill_pending()
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/in-progress", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_in_progress():
    """Get orders currently being worked (verifying, verified, approved)."""
    orders = await _dme_service.get_in_progress()
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/awaiting-patient", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_awaiting_patient():
    """Get orders where confirmation was sent but patient hasn't responded."""
    orders = await _dme_service.get_awaiting_patient()
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/patient-confirmed", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_patient_confirmed():
    """Get orders confirmed by patient — ready for vendor ordering."""
    orders = await _dme_service.get_patient_confirmed()
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/on-hold", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_on_hold():
    """Get orders currently on hold."""
    orders = await _dme_service.get_on_hold()
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/encounter-expired", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_encounter_expired():
    """Get active orders where the patient's last provider encounter is expired or missing."""
    orders = await _dme_service.get_encounter_expired()
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/encounter-types", tags=["DME Reference Data"])
async def dme_encounter_types():
    """Return available encounter types for the encounter tracking form."""
    from server.services.dme import ENCOUNTER_TYPE_LABELS
    return {"types": ENCOUNTER_TYPE_LABELS}


@router.get("/dme/equipment-categories", tags=["DME Reference Data"])
async def dme_equipment_categories():
    """Return available equipment categories and supply bundles."""
    from server.services.dme import EQUIPMENT_CATEGORIES, SUPPLY_BUNDLES, CATEGORY_HCPCS_MAP
    return {
        "categories": EQUIPMENT_CATEGORIES,
        "bundles": SUPPLY_BUNDLES,
        "hcpcs_map": CATEGORY_HCPCS_MAP,
    }


@router.get("/dme/dashboard", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_dashboard():
    """DME summary stats for the admin portal. Also triggers auto-refill processing."""
    await _dme_service.process_due_refills()
    return await _dme_service.get_dashboard()


@router.get("/dme/orders/expiring-encounters", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_expiring_encounters(days: int = 14):
    """Get orders with encounters expiring within the threshold."""
    orders = await _dme_service.get_expiring_encounter_orders(days)
    return [_serialize_dme_order(o) for o in orders]


@router.get("/dme/orders/{order_id}", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def get_dme_order(order_id: str):
    """Get a specific DME order."""
    order = await _dme_service.get_order(order_id)
    if not order:
        raise HTTPException(404, f"DME order {order_id} not found")
    return _serialize_dme_order(order)


@router.post("/dme/orders/{order_id}/verify-insurance", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_verify_insurance(order_id: str):
    """Run insurance verification for a DME order."""
    try:
        order = await _dme_service.verify_insurance(order_id)
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/dme/orders/{order_id}/approve", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def approve_dme_order(order_id: str, body: DMEOrderApproval = DMEOrderApproval()):
    """Approve a DME order."""
    try:
        order = await _dme_service.approve_order(order_id, body.notes or "")
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/dme/orders/{order_id}/reject", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def reject_dme_order(order_id: str, body: DMEOrderReject = DMEOrderReject()):
    """Reject a DME order."""
    try:
        order = await _dme_service.reject_order(order_id, body.reason or "")
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/dme/orders/{order_id}/fulfill", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def fulfill_dme_order(order_id: str):
    """Mark a DME order as fulfilled and schedule next auto-replace if applicable."""
    try:
        order = await _dme_service.fulfill_order(order_id)
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


class DMEEncounterUpdate(BaseModel):
    encounter_date: str             # YYYY-MM-DD
    encounter_type: str             # EncounterType value
    encounter_provider: str = ""
    encounter_provider_npi: str = ""


@router.post("/dme/orders/{order_id}/encounter", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def update_dme_encounter(order_id: str, body: DMEEncounterUpdate):
    """Record or update the patient's last provider encounter for a DME order."""
    try:
        order = await _dme_service.update_encounter(order_id, body.model_dump())
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


class DMEComplianceUpdate(BaseModel):
    status: str  # compliant, non_compliant, unknown, not_applicable
    avg_hours: Optional[float] = None
    days_met: Optional[int] = None
    total_days: Optional[int] = None


@router.post("/dme/orders/{order_id}/compliance", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def update_dme_compliance(order_id: str, body: DMEComplianceUpdate):
    """Update compliance data for a DME order (from AirPM or manual entry)."""
    try:
        order = await _dme_service.update_compliance(order_id, body.model_dump())
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


class DMEDocumentAdd(BaseModel):
    filename: str
    document_type: str  # rx, progress_notes, compliance_report, cmnform


@router.post("/dme/orders/{order_id}/documents", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def add_dme_document(order_id: str, body: DMEDocumentAdd):
    """Attach a document to a DME order for insurance approval."""
    try:
        order = await _dme_service.add_document(order_id, body.filename, body.document_type)
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/dme/orders/{order_id}/documents/{doc_id}", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def remove_dme_document(order_id: str, doc_id: str):
    """Remove a document from a DME order."""
    try:
        order = await _dme_service.remove_document(order_id, doc_id)
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ---- DME Staff Workflow Routes (admin) ----

@router.post("/dme/orders/{order_id}/hold", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def hold_dme_order(order_id: str, body: DMEHoldOrder = DMEHoldOrder()):
    """Place a DME order on hold."""
    try:
        order = await _dme_service.hold_order(order_id, body.reason)
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/dme/orders/{order_id}/resume", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def resume_dme_order(order_id: str):
    """Resume a held DME order."""
    try:
        order = await _dme_service.resume_order(order_id)
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/dme/orders/{order_id}/send-confirmation", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def send_dme_confirmation(order_id: str, body: DMESendConfirmation = DMESendConfirmation()):
    """Generate a patient confirmation token and mark order as patient_contacted.

    Returns the confirmation URL. In production, this would trigger an
    SMS/email via Twilio or similar. For now, returns the link for manual sending.
    """
    try:
        order = await _dme_service.generate_confirmation_token(order_id, body.send_via)
        from server.config import get_settings
        settings = get_settings()
        base_url = settings.app_base_url if hasattr(settings, 'app_base_url') else "http://localhost:5173"
        confirmation_url = f"{base_url}/dme/confirm/{order.confirmation_token}"
        return {
            "order": _serialize_dme_order(order),
            "confirmation_url": confirmation_url,
            "send_via": body.send_via,
            "expires_at": order.confirmation_token_expires,
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/dme/orders/{order_id}/mark-ordered", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def mark_dme_ordered(order_id: str, body: DMEMarkOrdered = DMEMarkOrdered()):
    """Record that supplies were ordered from vendor."""
    try:
        order = await _dme_service.mark_ordered(order_id, body.vendor_name, body.vendor_order_id)
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/dme/orders/{order_id}/mark-shipped", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def mark_dme_shipped(order_id: str, body: DMEMarkShipped = DMEMarkShipped()):
    """Record shipping/pickup-ready info."""
    try:
        order = await _dme_service.mark_shipped(
            order_id, body.tracking_number, body.carrier, body.estimated_delivery
        )
        return _serialize_dme_order(order)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ---- DME Patient Confirmation Routes (public, token-gated) ----

@router.get("/dme/confirm/{token}", tags=["DME Patient Portal"])
async def validate_dme_confirmation(token: str):
    """Validate a patient confirmation token and return safe order info.

    This is a PUBLIC endpoint — no admin auth required.
    The token itself is the auth mechanism (cryptographically random, time-limited).
    """
    order = await _dme_service.validate_confirmation_token(token)
    if not order:
        raise HTTPException(404, "This link is invalid or has expired. Please contact our office.")
    return _dme_service.get_patient_safe_order(order)


@router.post("/dme/confirm/{token}", tags=["DME Patient Portal"])
async def submit_dme_confirmation(token: str, body: DMEPatientConfirm):
    """Patient submits their confirmation (address, fulfillment choice).

    PUBLIC endpoint — token-gated.
    """
    order = await _dme_service.patient_confirm(token, body.model_dump())
    if not order:
        raise HTTPException(404, "This link is invalid or has expired. Please contact our office.")
    return _dme_service.get_patient_safe_order(order)


@router.post("/dme/confirm/{token}/reject", tags=["DME Patient Portal"])
async def reject_dme_confirmation(token: str, body: DMEPatientReject):
    """Patient flags an issue with their order. PUBLIC endpoint — token-gated."""
    order = await _dme_service.patient_reject_order(
        token, body.reason, body.callback_requested,
    )
    if not order:
        raise HTTPException(404, "This link is invalid or has expired. Please contact our office.")
    return {"status": "received", "message": "We'll review this and get back to you."}


@router.post("/dme/confirm/{token}/toggle-refill", tags=["DME Patient Portal"])
async def toggle_dme_refill(token: str, body: DMERefillToggle):
    """Patient opts in or out of auto-refill. PUBLIC endpoint — token-gated."""
    order = await _dme_service.patient_toggle_refill(
        token, body.auto_replace, body.frequency,
    )
    if not order:
        raise HTTPException(404, "This link is invalid or has expired. Please contact our office.")
    status = "enabled" if body.auto_replace else "disabled"
    return {"status": status, "auto_replace": order.auto_replace, "frequency": order.auto_replace_frequency}


@router.post("/dme/process-auto-refills", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_process_auto_refills():
    """Process due auto-refill orders: create child orders and send confirmation to patients."""
    created = await _dme_service.process_due_refills()
    return {"processed": len(created), "order_ids": [o.id for o in created]}


@router.post("/dme/process-auto-deliveries", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_process_auto_deliveries():
    """Fulfill orders whose auto-deliver timer has expired."""
    fulfilled = await _dme_service.process_auto_deliveries()
    return {"fulfilled": len(fulfilled), "order_ids": [o.id for o in fulfilled]}


@router.get("/dme/orders/{order_id}/receipt", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_order_receipt(order_id: str):
    """Generate receipt data for a fulfilled order."""
    data = await _dme_service.generate_receipt(order_id)
    if not data:
        raise HTTPException(404, "Order not found")
    return data


@router.get("/dme/orders/{order_id}/delivery-ticket", tags=["DME Orders"], dependencies=[Depends(require_role("admin", "dme"))])
async def dme_order_delivery_ticket(order_id: str):
    """Generate delivery ticket data for shipping/pickup."""
    data = await _dme_service.generate_delivery_ticket(order_id)
    if not data:
        raise HTTPException(404, "Order not found")
    return data


# ---- Helpers ----

def _serialize_dme_order(order) -> dict:
    from dataclasses import asdict
    d = asdict(order)
    d["status"] = order.status.value
    # Computed encounter properties
    d["encounter_current"] = order.encounter_current
    d["encounter_days_ago"] = order.encounter_days_ago
    d["encounter_expires_in_days"] = order.encounter_expires_in_days
    return d


def _serialize_referral(record) -> dict:
    """Convert ReferralRecord to JSON-safe dict."""
    d = asdict(record)
    d["status"] = record.status.value
    return d


# ---- Prescription Monitor routes ----

@router.post("/prescriptions/poll", tags=["Prescriptions"], dependencies=[Depends(require_role("admin", "dme"))])
async def poll_prescriptions():
    """Poll FHIR for new DME prescriptions and process them into orders."""
    if not _prescription_monitor:
        raise HTTPException(503, "Prescription monitor not initialized — FHIR client required")
    result = await _prescription_monitor.poll_and_process()
    return result


@router.get("/prescriptions/status", tags=["Prescriptions"], dependencies=[Depends(require_role("admin", "dme"))])
async def get_prescription_status():
    """Return current prescription monitor status."""
    if not _prescription_monitor:
        return {"polling_active": False, "last_check": None, "total_detected": 0, "by_status": {}, "available": False}
    status = await _prescription_monitor.get_status()
    status["available"] = True
    return status


@router.get("/prescriptions", tags=["Prescriptions"], dependencies=[Depends(require_role("admin", "dme"))])
async def list_prescriptions(status: Optional[str] = None):
    """List all detected prescriptions."""
    if not _prescription_monitor:
        return []
    from server.services.prescription_monitor import RxStatus
    rx_status = RxStatus(status) if status else None
    rxs = await _prescription_monitor.list_prescriptions(rx_status)
    return [_prescription_monitor._serialize(rx) for rx in rxs]


@router.get("/prescriptions/{doc_id}", tags=["Prescriptions"], dependencies=[Depends(require_role("admin", "dme"))])
async def get_prescription(doc_id: str):
    """Get details for a single detected prescription."""
    if not _prescription_monitor:
        raise HTTPException(503, "Prescription monitor not initialized")
    rx = await _prescription_monitor.get_prescription(doc_id)
    if not rx:
        raise HTTPException(404, "Prescription not found")
    return _prescription_monitor._serialize(rx)


class PrescriptionReject(BaseModel):
    reason: Optional[str] = None


@router.post("/prescriptions/{doc_id}/approve", tags=["Prescriptions"], dependencies=[Depends(require_role("admin", "dme"))])
async def approve_prescription(doc_id: str):
    """Approve a reviewed prescription and create the DME order."""
    if not _prescription_monitor:
        raise HTTPException(503, "Prescription monitor not initialized")
    try:
        rx = await _prescription_monitor.approve_prescription(doc_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _prescription_monitor._serialize(rx)


@router.post("/prescriptions/{doc_id}/reject", tags=["Prescriptions"], dependencies=[Depends(require_role("admin", "dme"))])
async def reject_prescription(doc_id: str, body: PrescriptionReject):
    """Reject a reviewed prescription — no DME order will be created."""
    if not _prescription_monitor:
        raise HTTPException(503, "Prescription monitor not initialized")
    try:
        rx = await _prescription_monitor.reject_prescription(doc_id, body.reason or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _prescription_monitor._serialize(rx)


@router.post("/prescriptions/reset", tags=["Prescriptions"], dependencies=[Depends(require_admin)])
async def reset_prescription_monitor():
    """Reset the prescription monitor — clear all tracked prescriptions."""
    if not _prescription_monitor:
        raise HTTPException(503, "Prescription monitor not initialized")
    await _prescription_monitor.reset()
    return {"status": "reset"}


def _serialize_referral_auth(auth) -> dict:
    from dataclasses import asdict as _asdict
    d = _asdict(auth)
    d["status"] = auth.status.value
    d["visits_remaining"] = auth.visits_remaining
    d["days_until_expiry"] = auth.days_until_expiry
    return d


# ---- Referral Authorization routes ----

class ReferralAuthCreate(BaseModel):
    patient_id: str
    patient_first_name: str
    patient_last_name: str
    insurance_name: str = ""
    insurance_type: str = "unknown"
    insurance_member_id: str = ""
    insurance_npi: str = ""
    copay: str = ""
    referral_number: str = ""
    referring_pcp_name: str = ""
    referring_pcp_npi: str = ""
    referring_pcp_phone: str = ""
    referring_pcp_fax: str = ""
    start_date: str = ""
    end_date: str = ""
    visits_allowed: int = 0
    notes: str = ""


class ReferralAuthUpdate(BaseModel):
    referral_number: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    visits_allowed: Optional[int] = None
    visits_used: Optional[int] = None
    copay: Optional[str] = None
    referring_pcp_name: Optional[str] = None
    referring_pcp_npi: Optional[str] = None
    referring_pcp_phone: Optional[str] = None
    referring_pcp_fax: Optional[str] = None
    notes: Optional[str] = None
    insurance_name: Optional[str] = None
    insurance_type: Optional[str] = None
    insurance_member_id: Optional[str] = None
    insurance_npi: Optional[str] = None


@router.post("/referral-auths", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def create_referral_auth(body: ReferralAuthCreate):
    """Create a new referral authorization record."""
    auth = await _referral_auth_service.create_auth(body.model_dump())
    return _serialize_referral_auth(auth)


@router.get("/referral-auths", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def list_referral_auths(
    status: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
):
    """List referral authorizations with optional filters."""
    filter_status = ReferralAuthStatus(status) if status else None
    auths = await _referral_auth_service.list_auths(filter_status, patient_id)
    return [_serialize_referral_auth(a) for a in auths]


@router.get("/referral-auths/dashboard", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def referral_auth_dashboard():
    """Dashboard summary stats for referral authorizations."""
    return await _referral_auth_service.get_dashboard()


@router.get("/referral-auths/expiring", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def referral_auths_expiring(days: int = Query(14)):
    """Get referral authorizations expiring within N days."""
    auths = await _referral_auth_service.get_expiring_soon(days)
    return [_serialize_referral_auth(a) for a in auths]


@router.get("/referral-auths/{auth_id}", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def get_referral_auth(auth_id: str):
    """Get a specific referral authorization."""
    auth = await _referral_auth_service.get_auth(auth_id)
    if not auth:
        raise HTTPException(404, f"Referral auth {auth_id} not found")
    return _serialize_referral_auth(auth)


@router.put("/referral-auths/{auth_id}", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def update_referral_auth(auth_id: str, body: ReferralAuthUpdate):
    """Update referral authorization fields."""
    try:
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        auth = await _referral_auth_service.update_auth(auth_id, data)
        return _serialize_referral_auth(auth)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/referral-auths/{auth_id}/record-visit", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def record_referral_auth_visit(auth_id: str):
    """Record a visit against a referral authorization."""
    try:
        auth = await _referral_auth_service.record_visit(auth_id)
        return _serialize_referral_auth(auth)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/referral-auths/{auth_id}/request-renewal", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def request_referral_auth_renewal(auth_id: str):
    """Request renewal from PCP for a referral authorization."""
    try:
        auth = await _referral_auth_service.request_renewal(auth_id)
        return _serialize_referral_auth(auth)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/referral-auths/{auth_id}/renewal-content", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def get_referral_renewal_content(auth_id: str):
    """Get fax content for PCP renewal request."""
    try:
        return await _referral_auth_service.get_renewal_content(auth_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/referral-auths/{auth_id}/cancel", tags=["Referral Authorizations"], dependencies=[Depends(require_role("admin", "front_office"))])
async def cancel_referral_auth(auth_id: str):
    """Cancel a referral authorization."""
    try:
        auth = await _referral_auth_service.cancel_auth(auth_id)
        return _serialize_referral_auth(auth)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/scheduling/referral-check/{patient_id}", tags=["Scheduling"], dependencies=[Depends(require_role("admin", "front_office"))])
async def check_referral_for_scheduling(patient_id: str):
    """Check if a patient has a valid referral authorization for scheduling."""
    return await _referral_auth_service.check_scheduling_eligibility(patient_id)


# ---- Allowable Rates routes ----

class RateUpsert(BaseModel):
    payer: str
    payer_plan: str = ""
    hcpcs_code: str
    description: str = ""
    supply_months: int = 6
    allowed_amount: float
    effective_year: int
    notes: str = ""


@router.get("/allowable-rates", tags=["Allowable Rates"], dependencies=[Depends(require_role("admin", "dme"))])
async def get_allowable_rates(
    payer: Optional[str] = Query(None),
    hcpcs_code: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    """List allowable rates with optional filters."""
    from server.services.allowable_rates import list_rates, HCPCS_CODES
    rates = await list_rates(payer, hcpcs_code, year)
    return {
        "rates": [_serialize_rate(r) for r in rates],
        "total": len(rates),
        "hcpcs_reference": HCPCS_CODES,
    }


@router.get("/allowable-rates/payers", tags=["Allowable Rates"], dependencies=[Depends(require_role("admin", "dme"))])
async def get_rate_payers(year: Optional[int] = Query(None)):
    """List distinct payers with rate counts."""
    from server.services.allowable_rates import list_payers
    return await list_payers(year)


@router.get("/allowable-rates/lookup", tags=["Allowable Rates"], dependencies=[Depends(require_role("admin", "dme"))])
async def lookup_rate(
    payer: str = Query(...),
    hcpcs_code: str = Query(...),
    supply_months: int = Query(6),
    year: Optional[int] = Query(None),
    payer_plan: str = Query(""),
):
    """Look up a single allowable rate by payer + HCPCS code."""
    from server.services.allowable_rates import get_rate
    rate = await get_rate(payer, hcpcs_code, supply_months, year, payer_plan)
    if not rate:
        raise HTTPException(404, "Rate not found for this payer/code/supply combination")
    return _serialize_rate(rate)


@router.post("/allowable-rates/bundle-pricing", tags=["Allowable Rates"], dependencies=[Depends(require_role("admin", "dme"))])
async def bundle_pricing(body: dict):
    """Calculate total expected reimbursement for a bundle of HCPCS codes."""
    from server.services.allowable_rates import get_bundle_pricing
    payer = body.get("payer", "")
    codes = body.get("hcpcs_codes", [])
    supply_months = body.get("supply_months", 6)
    year = body.get("year")
    payer_plan = body.get("payer_plan", "")
    if not payer or not codes:
        raise HTTPException(400, "payer and hcpcs_codes are required")
    return await get_bundle_pricing(payer, codes, supply_months, year, payer_plan)


@router.post("/allowable-rates", tags=["Allowable Rates"], dependencies=[Depends(require_role("admin", "dme"))])
async def create_rate(body: RateUpsert):
    """Create or update a single allowable rate."""
    from server.services.allowable_rates import upsert_rate, AllowableRate
    rate = AllowableRate(**body.model_dump())
    result = await upsert_rate(rate)
    return _serialize_rate(result)


@router.put("/allowable-rates/{rate_id}", tags=["Allowable Rates"], dependencies=[Depends(require_role("admin", "dme"))])
async def update_rate(rate_id: int, body: RateUpsert):
    """Update an existing rate."""
    from server.services.allowable_rates import upsert_rate, AllowableRate
    rate = AllowableRate(id=rate_id, **body.model_dump())
    result = await upsert_rate(rate)
    return _serialize_rate(result)


@router.delete("/allowable-rates/{rate_id}", tags=["Allowable Rates"], dependencies=[Depends(require_role("admin", "dme"))])
async def delete_rate_endpoint(rate_id: int):
    """Delete a rate by ID."""
    from server.services.allowable_rates import delete_rate
    deleted = await delete_rate(rate_id)
    if not deleted:
        raise HTTPException(404, "Rate not found")
    return {"deleted": True}


@router.post("/allowable-rates/import", tags=["Allowable Rates"], dependencies=[Depends(require_admin)])
async def import_rates(year: Optional[int] = Query(None)):
    """Import rates from the bundled Excel file (assets/InsuranceAllowablesForCPAP2026.xlsx)."""
    from server.services.allowable_rates import import_from_excel
    from pathlib import Path
    excel_path = Path(__file__).parent.parent.parent / "assets" / "InsuranceAllowablesForCPAP2026.xlsx"
    if not excel_path.exists():
        raise HTTPException(404, "Allowables Excel file not found in assets/")
    result = await import_from_excel(str(excel_path), year)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/allowable-rates/import-upload", tags=["Allowable Rates"], dependencies=[Depends(require_admin)])
async def import_rates_upload(file: UploadFile = File(...), year: Optional[int] = Query(None)):
    """Upload and import a new allowables Excel file."""
    from server.services.allowable_rates import import_from_excel
    import tempfile
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "File must be .xlsx or .xls")
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = await import_from_excel(tmp_path, year)
    finally:
        import os
        os.unlink(tmp_path)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


def _serialize_rate(rate) -> dict:
    from dataclasses import asdict as _asdict
    return _asdict(rate)


# ---- Debug / sandbox routes ----

@router.get("/debug/fhir-store", tags=["Debug"], dependencies=[Depends(require_dev_env)])
async def debug_fhir_store():
    """Return summary of stub FHIR store (only available when USE_STUB_FHIR=true)."""
    from server.config import get_settings
    settings = get_settings()
    if not settings.use_stub_fhir:
        raise HTTPException(403, "Debug FHIR store is only available when USE_STUB_FHIR=true")
    svc = get_referral_service()
    client = svc.fhir
    if not hasattr(client, "summary"):
        raise HTTPException(403, "Connected to live EMR — stub store not active")
    return {
        "mode": "stub",
        "store_summary": client.summary(),
        "patients": client.list_resources("Patient"),
        "coverages": client.list_resources("Coverage"),
        "service_requests": client.list_resources("ServiceRequest"),
        "conditions": client.list_resources("Condition"),
    }


@router.get("/debug/patients", tags=["Debug"], dependencies=[Depends(require_dev_env)])
async def debug_patients(
    family: Optional[str] = Query(None),
    given: Optional[str] = Query(None),
    count: int = Query(20),
):
    """Pull patients from the connected FHIR endpoint (stub or live EMR sandbox).

    For athena sandbox: set ATHENA_SANDBOX=true and ATHENA_CLIENT_ID / ATHENA_CLIENT_SECRET
    in .env, then call POST /api/auth/connect-service before using this endpoint.
    """
    svc = get_referral_service()
    params: dict = {"_count": str(count)}
    if family:
        params["family"] = family
    if given:
        params["given"] = given

    try:
        bundle = await svc.fhir.search("Patient", params)
    except Exception as e:
        logger.error(f"FHIR Patient search failed: {e}")
        raise HTTPException(502, "FHIR Patient search failed. Check server logs.")

    entries = bundle.get("entry", [])
    patients = []
    for entry in entries:
        r = entry.get("resource", {})
        name = r.get("name", [{}])[0]
        given_names = name.get("given", [])
        patients.append({
            "id": r.get("id"),
            "name": f"{' '.join(given_names)} {name.get('family', '')}".strip(),
            "dob": r.get("birthDate"),
            "gender": r.get("gender"),
            "phone": next(
                (t.get("value") for t in r.get("telecom", []) if t.get("system") == "phone"),
                None,
            ),
            "address": r.get("address", [{}])[0].get("line", [""])[0] if r.get("address") else None,
        })

    from server.config import get_settings
    settings = get_settings()
    emr = get_emr()
    return {
        "source": "stub" if settings.use_stub_fhir else emr.name,
        "sandbox": getattr(emr, "is_sandbox", False),
        "fhir_base": emr.fhir_base_url,
        "total": bundle.get("total", len(patients)),
        "returned": len(patients),
        "patients": patients,
    }


@router.get("/debug/connection", tags=["Debug"], dependencies=[Depends(require_dev_env)])
async def debug_connection():
    """Test FHIR connectivity — useful for verifying athena sandbox credentials."""
    from server.config import get_settings
    settings = get_settings()
    emr = get_emr()

    if settings.use_stub_fhir:
        svc = get_referral_service()
        client = svc.fhir
        return {
            "mode": "stub",
            "status": "ok",
            "store_summary": client.summary() if hasattr(client, "summary") else {},
        }

    # Try a lightweight FHIR metadata call (no auth needed) to verify base URL
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{emr.fhir_base_url}/metadata")
            meta = resp.json() if resp.status_code == 200 else {}
        base_ok = resp.status_code in (200, 401)  # 401 = reachable but needs auth
    except Exception as e:
        logger.error(f"FHIR metadata check failed: {e}")
        return {"mode": "live", "status": "unreachable", "error": "Connection failed"}

    # Try an authenticated Patient search to test credentials
    auth_ok = False
    auth_error = None
    patient_count = None
    try:
        svc = get_referral_service()
        bundle = await svc.fhir.search("Patient", {"_count": "1"})
        auth_ok = True
        patient_count = bundle.get("total")
    except Exception as e:
        logger.error(f"FHIR auth test failed: {e}")
        auth_error = "Authentication failed"

    return {
        "mode": "live",
        "emr": emr.name,
        "sandbox": getattr(emr, "is_sandbox", False),
        "fhir_base": emr.fhir_base_url,
        "fhir_base_reachable": base_ok,
        "fhir_server_version": meta.get("fhirVersion") if base_ok else None,
        "authenticated": auth_ok,
        "auth_error": auth_error,
        "patient_count": patient_count,
    }
