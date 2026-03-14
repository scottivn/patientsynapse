"""Abstract base class for EMR providers."""

from abc import ABC, abstractmethod
from typing import Optional
from enum import Enum


class AuthMethod(str, Enum):
    """OAuth2 client authentication method used by the EMR."""
    ASYMMETRIC_JWT = "private_key_jwt"       # eCW, Epic
    CLIENT_SECRET = "client_secret_basic"    # Athena, some others
    CLIENT_SECRET_POST = "client_secret_post"


class EMRProvider(ABC):
    """Contract every EMR integration must implement.

    PatientBridge talks FHIR R4 regardless of EMR. This class captures the
    differences: OAuth endpoints, allowed scopes, auth method, and any
    EMR-specific resource quirks.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable EMR name, e.g. 'eClinicalWorks'."""

    @property
    @abstractmethod
    def fhir_base_url(self) -> str:
        """FHIR R4 base URL for this EMR instance."""

    @property
    @abstractmethod
    def authorize_url(self) -> str:
        """OAuth2 authorization endpoint."""

    @property
    @abstractmethod
    def token_url(self) -> str:
        """OAuth2 token endpoint."""

    @property
    @abstractmethod
    def client_id(self) -> str:
        """Registered OAuth2 client ID."""

    @property
    @abstractmethod
    def redirect_uri(self) -> str:
        """OAuth2 redirect URI."""

    @property
    @abstractmethod
    def scopes(self) -> list[str]:
        """Requested SMART on FHIR scopes."""

    @property
    @abstractmethod
    def auth_method(self) -> AuthMethod:
        """How the client authenticates to the token endpoint."""

    @property
    def client_secret(self) -> Optional[str]:
        """Client secret (for client_secret_basic / client_secret_post)."""
        return None

    @property
    def jwks_url(self) -> Optional[str]:
        """Public JWKS URL (for private_key_jwt auth)."""
        return None

    @property
    def supports_refresh(self) -> bool:
        """Whether the EMR supports offline_access / refresh tokens."""
        return True

    @property
    def supported_resources(self) -> list[str]:
        """FHIR resource types available on this EMR. Empty = assume all."""
        return []

    @property
    def notes(self) -> str:
        """Any human-readable notes about EMR-specific limitations."""
        return ""
