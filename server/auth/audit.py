"""HIPAA audit logging for PHI access."""

import logging
import aiosqlite

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from server.config import get_settings
from server.auth.jwt_auth import decode_token

logger = logging.getLogger(__name__)

# Routes that access PHI and should be audit-logged
PHI_ROUTE_PREFIXES = (
    "/api/referrals",
    "/api/faxes",
    "/api/referral-auths",
    "/api/dme/orders",
    "/api/dme/admin",
    "/api/dme/patients",
    "/api/dme/patient-verify",
    "/api/dme/dashboard",
    "/api/dme/confirm",
    "/api/prescriptions",
    "/api/scheduling",
    "/api/rcm",
    "/api/admin/users",
    "/api/debug/patients",
    "/api/debug/fhir-store",
)


async def log_phi_access(
    user_type: str,
    user_id: str,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    ip_address: str = "",
    user_agent: str = "",
):
    """Write an entry to the phi_audit_log table."""
    settings = get_settings()
    db_path = settings.database_url.replace("sqlite:///", "")
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """INSERT INTO phi_audit_log
                   (user_type, user_id, action, resource_type, resource_id, ip_address, user_agent)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_type, user_id, action, resource_type, resource_id, ip_address, user_agent),
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")


class AuditMiddleware(BaseHTTPMiddleware):
    """Log PHI-accessing requests to the audit table."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Refresh access token cookie on any authenticated request
        # (not just PHI routes — prevents premature session expiry)
        if hasattr(request.state, "refreshed_access_token"):
            settings = get_settings()
            is_prod = settings.app_env != "development"
            response.set_cookie(
                key="access_token",
                value=request.state.refreshed_access_token,
                httponly=True,
                samesite="lax",
                secure=is_prod,
                max_age=settings.jwt_access_token_expire_minutes * 60,
                path="/",
            )

        # Only audit PHI routes with successful responses
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in PHI_ROUTE_PREFIXES):
            return response
        if response.status_code >= 400:
            return response

        # Extract user info from cookie (best effort, don't block on failure)
        user_type = "anonymous"
        user_id = ""
        token = request.cookies.get("access_token")
        if token:
            try:
                claims = decode_token(token)
                user_type = claims.get("role", "admin")
                user_id = claims.get("username", claims.get("sub", ""))
            except Exception:
                user_type = "invalid_token"

        # Determine resource type from path
        resource_type = ""
        if "/referrals" in path:
            resource_type = "referral"
        elif "/faxes" in path:
            resource_type = "fax"
        elif "/dme" in path:
            resource_type = "dme_order"
        elif "/referral-auths" in path:
            resource_type = "referral_auth"
        elif "/scheduling" in path:
            resource_type = "scheduling"
        elif "/rcm" in path:
            resource_type = "rcm"

        # Extract resource ID from path if present (e.g., /api/referrals/abc123)
        parts = path.rstrip("/").split("/")
        resource_id = ""
        if len(parts) >= 4 and not parts[-1].startswith(("upload", "poll", "status", "reset", "dashboard")):
            resource_id = parts[-1]

        ip = request.client.host if request.client else ""
        ua = request.headers.get("user-agent", "")[:200]

        # Fire and forget — don't slow down the response
        import asyncio
        asyncio.create_task(log_phi_access(
            user_type=user_type,
            user_id=user_id,
            action=f"{request.method} {path}",
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip,
            user_agent=ua,
        ))

        return response
