"""Demo role middleware — enforces read-only access for demo users.

Demo users can view all pages and data but cannot create, modify, or delete
anything. This is the single enforcement point; no per-route changes needed.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from server.auth.jwt_auth import decode_token

logger = logging.getLogger(__name__)

# Routes that demo users ARE allowed to POST to (login, refresh, logout)
_DEMO_WRITE_ALLOWLIST = (
    "/api/admin/login",
    "/api/admin/refresh",
    "/api/admin/logout",
)


class DemoReadOnlyMiddleware(BaseHTTPMiddleware):
    """Block all write operations (POST/PUT/DELETE/PATCH) for demo-role users.

    GET and OPTIONS always pass through. Write requests to login/refresh/logout
    are also allowed so the demo user can authenticate.
    """

    async def dispatch(self, request: Request, call_next):
        # Only intercept write methods on API routes
        if request.method in ("GET", "OPTIONS", "HEAD"):
            return await call_next(request)

        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Allow auth endpoints so demo user can log in/out
        if request.url.path in _DEMO_WRITE_ALLOWLIST:
            return await call_next(request)

        # Check if the current user is a demo user
        token = request.cookies.get("access_token")
        if not token:
            return await call_next(request)

        try:
            claims = decode_token(token)
        except Exception:
            return await call_next(request)

        if claims.get("role") != "demo":
            return await call_next(request)

        # Demo user trying to write — block it
        logger.info(f"Demo user blocked: {request.method} {request.url.path}")
        return JSONResponse(
            status_code=403,
            content={"detail": "Demo mode is read-only. This action is disabled."},
        )
