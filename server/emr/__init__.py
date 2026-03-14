"""EMR provider abstraction — plug-and-play EMR support."""

from server.emr.base import EMRProvider
from server.emr.ecw import ECWProvider
from server.emr.athena import AthenaProvider
from server.config import get_settings
from functools import lru_cache


@lru_cache()
def get_emr() -> EMRProvider:
    """Return the configured EMR provider instance."""
    settings = get_settings()
    match settings.emr_provider:
        case "ecw":
            return ECWProvider(settings)
        case "athena":
            return AthenaProvider(settings)
        case other:
            raise ValueError(f"Unknown EMR provider: {other}")
