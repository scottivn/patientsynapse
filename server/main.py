"""PatientBridge — FastAPI application entry point."""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from server.config import get_settings
from server.api.routes import router
from server.auth.smart import SMARTAuth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"PatientBridge starting | env={settings.app_env} | llm={settings.llm_provider}")
    logger.info(f"FHIR base: {settings.ecw_fhir_base_url}")

    # Ensure upload dir exists
    Path(settings.fax_upload_dir).mkdir(parents=True, exist_ok=True)

    yield
    logger.info("PatientBridge shutting down")


app = FastAPI(
    title="PatientBridge",
    description="Intelligent referral processing, scheduling, and RCM for eCW practices",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://localhost:8443"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(router)

# JWKS endpoint for SMART on FHIR
@app.get("/.well-known/jwks.json")
async def jwks():
    auth = SMARTAuth()
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
