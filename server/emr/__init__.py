"""EMR provider abstraction — plug-and-play EMR support."""

from server.emr.base import EMRProvider
from server.emr.ecw import ECWProvider
from server.emr.athena import AthenaProvider
from server.config import get_settings
from functools import lru_cache
from typing import Optional

# Runtime override — set by switch_emr() for UI hot-swap
_emr_override: Optional[str] = None


@lru_cache()
def get_emr() -> EMRProvider:
    """Return the configured EMR provider instance."""
    settings = get_settings()
    provider = _emr_override or settings.emr_provider
    match provider:
        case "ecw":
            return ECWProvider(settings)
        case "athena":
            return AthenaProvider(settings)
        case other:
            raise ValueError(f"Unknown EMR provider: {other}")


def switch_emr(provider: str) -> EMRProvider:
    """Hot-swap the active EMR provider at runtime (no restart needed)."""
    global _emr_override
    if provider not in ("ecw", "athena"):
        raise ValueError(f"Unknown EMR provider: {provider}")
    _emr_override = provider
    get_emr.cache_clear()
    return get_emr()


def get_active_emr_key() -> str:
    """Return the currently active EMR provider key."""
    return _emr_override or get_settings().emr_provider
