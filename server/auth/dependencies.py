"""FastAPI dependencies for route authentication."""

import time
import logging

from fastapi import Request, HTTPException, Depends

from server.config import get_settings
from server.auth.jwt_auth import decode_token, create_access_token

logger = logging.getLogger(__name__)


async def get_current_user(request: Request) -> dict:
    """Read JWT from access_token cookie, validate, enforce inactivity timeout.

    Returns dict with keys: user_id, username, role.
    Sets a new access_token cookie with updated last_activity on success.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        claims = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if claims.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Check inactivity timeout
    settings = get_settings()
    last_activity = claims.get("last_activity", 0)
    if time.time() - last_activity > (settings.session_inactivity_timeout_minutes * 60):
        raise HTTPException(
            status_code=401,
            detail="Session expired due to inactivity",
            headers={"X-Session-Expired": "inactivity"},
        )

    user = {
        "user_id": claims["sub"],
        "username": claims["username"],
        "role": claims["role"],
    }

    # Verify user is still active in DB (prevents deactivated users from using existing JWTs)
    from server.auth.users import get_user_by_id
    db_user = await get_user_by_id(int(claims["sub"]))
    if not db_user or not db_user.get("is_active", 1):
        raise HTTPException(status_code=401, detail="Account deactivated")

    # Use the DB role (may have changed since token was issued)
    user["role"] = db_user["role"]

    # Store refreshed token on request state so the middleware can set the cookie
    request.state.refreshed_access_token = create_access_token(
        user_id=int(claims["sub"]),
        username=claims["username"],
        role=db_user["role"],
    )

    return user


def require_role(*allowed_roles: str):
    """Factory that returns a dependency checking the user's role against allowed roles.

    Usage: dependencies=[Depends(require_role("admin", "dme"))]
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Requires one of: {', '.join(allowed_roles)}")
        return user
    return _check


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Ensure the authenticated user has admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_dev_env():
    """Gate routes to development environment only."""
    settings = get_settings()
    if settings.app_env != "development":
        raise HTTPException(status_code=404, detail="Not found")
