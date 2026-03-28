"""PatientSynapse — FastAPI application entry point."""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from server.config import get_settings
from server.api.routes import router, set_referral_service, set_fax_ingestion_service, set_smart_auth, set_prescription_monitor
from server.emr import get_emr
from server.auth.smart import SMARTAuth
from server.fhir.client import FHIRClient
from server.services.referral import ReferralService
from server.services.fax_ingestion import FaxIngestionService
from server.services.prescription_monitor import PrescriptionMonitorService
from server.auth.users import init_db, seed_default_admin
from server.auth.audit import AuditMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    emr = get_emr()
    logger.info(f"PatientSynapse starting | env={settings.app_env} | emr={emr.name} | llm={settings.llm_provider}")
    logger.info(f"FHIR base: {emr.fhir_base_url}")

    # Ensure upload dir exists
    Path(settings.fax_upload_dir).mkdir(parents=True, exist_ok=True)

    # Validate secret key in production
    if settings.app_env != "development" and settings.app_secret_key == "change-me-in-production":
        logger.critical("FATAL: app_secret_key is still the default. Set a strong secret in .env for production.")
        raise SystemExit(1)

    # Block cloud LLM providers without BAA in production — PHI sent to these APIs
    # violates HIPAA §164.504(e). Only ollama (local) and bedrock (AWS BAA) are safe.
    HIPAA_SAFE_LLM_PROVIDERS = ("ollama", "bedrock")
    if settings.app_env == "production" and settings.llm_provider not in HIPAA_SAFE_LLM_PROVIDERS:
        logger.critical(
            f"FATAL: LLM_PROVIDER={settings.llm_provider} is not HIPAA-safe for production. "
            f"Use one of: {', '.join(HIPAA_SAFE_LLM_PROVIDERS)}. "
            "Cloud providers (grok, openai, anthropic) require a signed BAA before handling PHI."
        )
        raise SystemExit(1)

    # Initialize databases
    await init_db()
    await seed_default_admin(settings.admin_default_username, settings.admin_default_password)

    from server.db import init_all_tables
    await init_all_tables()

    from server.services.allowable_rates import init_rates_table
    await init_rates_table()

    from server.services.dme_products import seed_products, seed_inventory
    await seed_products()
    await seed_inventory()

    # Initialize referral + fax ingestion services (work without OAuth for LLM-only features)
    auth = SMARTAuth(emr)
    set_smart_auth(auth)

    if settings.use_stub_fhir:
        from server.fhir.stub_client import StubFHIRClient
        fhir_client = StubFHIRClient()
        logger.warning("USE_STUB_FHIR=true — using in-memory FHIR store, no EMR connection required")
    else:
        fhir_client = FHIRClient(auth)

    referral_svc = ReferralService(fhir_client)
    set_referral_service(referral_svc)

    inbox_dir = Path(__file__).parent.parent / "IncomingFaxes"
    fax_svc = FaxIngestionService(str(inbox_dir), referral_svc)
    set_fax_ingestion_service(fax_svc)
    pending = await fax_svc._get_pending_files()
    logger.info(f"Fax inbox: {inbox_dir} ({len(pending)} files pending)")

    # Seed DME demo data (idempotent — skips if orders already exist)
    from server.api.routes import _dme_service
    _dme_service.set_fhir_client(fhir_client)
    await _dme_service.seed_demo_data()

    # Process any auto-refills that came due (creates child orders + sends to patients)
    refills = await _dme_service.process_due_refills()
    if refills:
        logger.info(f"Startup: auto-processed {len(refills)} due refills")

    # Prescription monitor — polls eCW for new Rx documents → auto-creates DME orders
    rx_monitor = PrescriptionMonitorService(fhir_client, _dme_service)
    set_prescription_monitor(rx_monitor)
    logger.info("Prescription monitor initialized (manual poll — use /api/prescriptions/poll)")

    # Fax auto-polling disabled — manual fetch only until prod-ready
    # fax_svc.start_polling(interval_seconds=settings.fax_poll_interval_seconds)

    yield

    # fax_svc.stop_polling()
    await fhir_client.close()
    logger.info("PatientSynapse shutting down")


_settings = get_settings()

# Gate interactive docs to development only — don't expose API surface in production
_is_dev = _settings.app_env == "development"

app = FastAPI(
    title="PatientSynapse",
    description="Intelligent referral processing, scheduling, and RCM for medical practices",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,   # We serve custom /docs with local assets below
    redoc_url=None,   # We serve custom /redoc with local assets below
    openapi_tags=[
        {"name": "Auth", "description": "Admin authentication — login, logout, token refresh"},
        {"name": "User Management", "description": "CRUD operations for admin users (admin only)"},
        {"name": "SMART on FHIR", "description": "OAuth2 flows for EMR connectivity"},
        {"name": "Referrals", "description": "Referral processing pipeline — upload, review, approve/reject"},
        {"name": "Fax Ingestion", "description": "Fax inbox polling and processing"},
        {"name": "Scheduling", "description": "Provider search and insurance verification"},
        {"name": "RCM", "description": "Revenue cycle management — billing and analytics"},
        {"name": "DME Orders", "description": "Durable Medical Equipment order workflow (admin)"},
        {"name": "DME Patient Portal", "description": "Public patient-facing DME endpoints — no admin auth required"},
        {"name": "DME Reference Data", "description": "Equipment categories, encounter types (public)"},
        {"name": "Prescriptions", "description": "Prescription monitoring and auto-DME creation"},
        {"name": "Referral Authorizations", "description": "Insurance referral auth tracking and renewal"},
        {"name": "Allowable Rates", "description": "Insurance reimbursement rate management"},
        {"name": "Settings", "description": "EMR and LLM provider configuration (admin only)"},
        {"name": "System", "description": "Health checks and system status"},
        {"name": "Debug", "description": "Development-only diagnostic endpoints"},
    ],
)

# CORS — allow frontend dev server + production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:3000", "https://localhost:8443",
        "https://patientsynapse.com", "https://www.patientsynapse.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# HIPAA audit logging middleware
app.add_middleware(AuditMiddleware)


# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )
    settings = get_settings()
    if settings.app_env != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    # Prevent browser caching of API responses containing PHI
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response

# Global exception handler — prevent PHI leaks in unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# API routes
app.include_router(router)

# Serve Swagger UI + ReDoc with local assets (no CDN — works behind ad blockers/firewalls)
if _is_dev:
    _swagger_ui_dir = Path(__file__).parent / "static" / "swagger-ui"
    app.mount(
        "/swagger-ui-assets",
        StaticFiles(directory=str(_swagger_ui_dir)),
        name="swagger-ui-assets",
    )

    @app.get("/swagger-init.js", include_in_schema=False)
    async def swagger_init_js():
        return Response(
            content="SwaggerUIBundle({url:'/openapi.json',dom_id:'#swagger-ui',layout:'BaseLayout',deepLinking:true,docExpansion:'none',presets:[SwaggerUIBundle.presets.apis,SwaggerUIBundle.SwaggerUIStandalonePreset]})",
            media_type="application/javascript",
        )

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui():
        return HTMLResponse(
            f"<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            f"<title>{app.title} - Swagger UI</title>"
            f"<link rel='stylesheet' href='/swagger-ui-assets/swagger-ui.css'>"
            f"</head><body><div id='swagger-ui'></div>"
            f"<script src='/swagger-ui-assets/swagger-ui-bundle.js'></script>"
            f"<script src='/swagger-init.js'></script>"
            f"</body></html>"
        )


# JWKS endpoint for SMART on FHIR
@app.get("/.well-known/jwks.json")
async def jwks():
    emr = get_emr()
    auth = SMARTAuth(emr)
    return auth.get_jwks()

# Serve frontend (production build)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React SPA — all non-API routes return index.html."""
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
