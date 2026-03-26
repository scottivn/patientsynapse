"""JWT token creation and validation for app-level auth."""

import time
import jwt
import logging

from server.config import get_settings

logger = logging.getLogger(__name__)


def create_access_token(user_id: int, username: str, role: str = "admin") -> str:
    settings = get_settings()
    now = time.time()
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "last_activity": now,
        "iat": now,
        "exp": now + (settings.jwt_access_token_expire_minutes * 60),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    settings = get_settings()
    now = time.time()
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + (settings.jwt_refresh_token_expire_days * 86400),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
