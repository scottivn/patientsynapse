"""SMART on FHIR OAuth2 authentication for eCW."""

import time
import json
import uuid
import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from server.config import get_settings


@dataclass
class TokenSet:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: str = ""
    id_token: Optional[str] = None
    issued_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.issued_at + self.expires_in - 60)


class SMARTAuth:
    """SMART on FHIR standalone launch with asymmetric key auth."""

    SCOPES = [
        "openid",
        "fhirUser",
        "offline_access",
        # Read scopes
        "user/Patient.read",
        "user/Condition.read",
        "user/Coverage.read",
        "user/Encounter.read",
        "user/DocumentReference.read",
        "user/ServiceRequest.read",
        "user/Practitioner.read",
        "user/PractitionerRole.read",
        "user/Location.read",
        "user/Organization.read",
        "user/Procedure.read",
        "user/Provenance.read",
        # Write scopes
        "user/Patient.write",
        "user/Condition.write",
        "user/DocumentReference.write",
        "user/ServiceRequest.write",
        "user/Encounter.write",
        "user/Task.write",
        "user/Communication.write",
    ]

    def __init__(self):
        self.settings = get_settings()
        self._token: Optional[TokenSet] = None
        self._key_path = Path("keys")
        self._key_path.mkdir(exist_ok=True)
        self._private_key = self._load_or_generate_key()

    def _load_or_generate_key(self) -> rsa.RSAPrivateKey:
        """Load existing RSA key or generate a new one."""
        key_file = self._key_path / "private_key.pem"
        if key_file.exists():
            return serialization.load_pem_private_key(
                key_file.read_bytes(), password=None
            )
        # Generate new RSA-384 key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        key_file.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        # Also save public key for JWKS
        pub_file = self._key_path / "public_key.pem"
        pub_file.write_bytes(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        return private_key

    def get_jwks(self) -> dict:
        """Return JWKS JSON for the public key (served at /.well-known/jwks.json)."""
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
        import base64

        pub = self._private_key.public_key()
        pub_numbers: RSAPublicNumbers = pub.public_numbers()

        def _b64url(num: int, length: int) -> str:
            return base64.urlsafe_b64encode(
                num.to_bytes(length, byteorder="big")
            ).decode().rstrip("=")

        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS384",
                    "kid": "patientbridge-1",
                    "n": _b64url(pub_numbers.n, 256),
                    "e": _b64url(pub_numbers.e, 3),
                }
            ]
        }

    def get_authorize_url(self, state: Optional[str] = None) -> str:
        """Build the authorization URL for SMART standalone launch."""
        state = state or str(uuid.uuid4())
        params = {
            "response_type": "code",
            "client_id": self.settings.ecw_client_id,
            "redirect_uri": self.settings.ecw_redirect_uri,
            "scope": " ".join(self.SCOPES),
            "state": state,
            "aud": self.settings.ecw_fhir_base_url,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.settings.ecw_authorize_url}?{query}"

    def _build_client_assertion(self) -> str:
        """Build a signed JWT for client authentication (asymmetric)."""
        now = int(time.time())
        payload = {
            "iss": self.settings.ecw_client_id,
            "sub": self.settings.ecw_client_id,
            "aud": self.settings.ecw_token_url,
            "exp": now + 300,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="RS384",
            headers={"kid": "patientbridge-1"},
        )

    async def exchange_code(self, code: str) -> TokenSet:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.settings.ecw_token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.settings.ecw_redirect_uri,
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": self._build_client_assertion(),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = TokenSet(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_in=data.get("expires_in", 3600),
                refresh_token=data.get("refresh_token"),
                scope=data.get("scope", ""),
                id_token=data.get("id_token"),
            )
            return self._token

    async def refresh(self) -> TokenSet:
        """Use refresh token to get a new access token."""
        if not self._token or not self._token.refresh_token:
            raise ValueError("No refresh token available. Re-authorize.")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.settings.ecw_token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._token.refresh_token,
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": self._build_client_assertion(),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = TokenSet(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_in=data.get("expires_in", 3600),
                refresh_token=data.get("refresh_token", self._token.refresh_token),
                scope=data.get("scope", self._token.scope),
                id_token=data.get("id_token"),
            )
            return self._token

    async def get_valid_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        if not self._token:
            raise ValueError("Not authenticated. Complete OAuth flow first.")
        if self._token.is_expired:
            await self.refresh()
        return self._token.access_token

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None
