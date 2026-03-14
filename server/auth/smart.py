"""SMART on FHIR OAuth2 authentication — EMR-agnostic."""

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

from server.emr.base import EMRProvider, AuthMethod


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
    """SMART on FHIR standalone launch — supports both asymmetric JWT
    and client-secret auth depending on the EMR provider."""

    def __init__(self, emr: EMRProvider):
        self.emr = emr
        self._token: Optional[TokenSet] = None
        self._key_path = Path("keys")
        self._key_path.mkdir(exist_ok=True)
        # Only load/generate RSA key when using JWT auth
        self._private_key = (
            self._load_or_generate_key()
            if emr.auth_method == AuthMethod.ASYMMETRIC_JWT
            else None
        )

    # ---- Key management (asymmetric JWT auth only) ----

    def _load_or_generate_key(self) -> rsa.RSAPrivateKey:
        key_file = self._key_path / "private_key.pem"
        if key_file.exists():
            return serialization.load_pem_private_key(
                key_file.read_bytes(), password=None
            )
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
        pub_file = self._key_path / "public_key.pem"
        pub_file.write_bytes(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        return private_key

    def get_jwks(self) -> dict:
        """Return JWKS JSON for the public key. Only meaningful for JWT auth."""
        if self._private_key is None:
            return {"keys": []}

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
                    "kid": "patientsynapse-1",
                    "n": _b64url(pub_numbers.n, 256),
                    "e": _b64url(pub_numbers.e, 3),
                }
            ]
        }

    # ---- OAuth2 URL / token helpers ----

    def get_authorize_url(self, state: Optional[str] = None) -> str:
        from urllib.parse import urlencode
        state = state or str(uuid.uuid4())
        params = {
            "response_type": "code",
            "client_id": self.emr.client_id,
            "redirect_uri": self.emr.redirect_uri,
            "scope": " ".join(self.emr.scopes),
            "state": state,
            "aud": self.emr.fhir_base_url,
        }
        return f"{self.emr.authorize_url}?{urlencode(params)}"

    def _build_token_data(self, **extra) -> dict:
        """Build token endpoint POST body with the correct auth method."""
        data = {**extra}
        if self.emr.auth_method == AuthMethod.ASYMMETRIC_JWT:
            data["client_assertion_type"] = (
                "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
            )
            data["client_assertion"] = self._build_client_assertion()
        elif self.emr.auth_method == AuthMethod.CLIENT_SECRET_POST:
            data["client_id"] = self.emr.client_id
            data["client_secret"] = self.emr.client_secret
        # CLIENT_SECRET (basic) uses HTTP auth header instead
        return data

    def _build_auth_header(self) -> Optional[tuple[str, str]]:
        """Return HTTP Basic auth tuple for client_secret_basic, else None."""
        if self.emr.auth_method == AuthMethod.CLIENT_SECRET:
            return (self.emr.client_id, self.emr.client_secret)
        return None

    def _build_client_assertion(self) -> str:
        """JWT client assertion for private_key_jwt auth."""
        now = int(time.time())
        payload = {
            "iss": self.emr.client_id,
            "sub": self.emr.client_id,
            "aud": self.emr.token_url,
            "exp": now + 300,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="RS384",
            headers={"kid": "patientsynapse-1"},
        )

    # ---- Token exchange/refresh ----

    async def client_credentials_connect(self) -> TokenSet:
        """2-legged auth: obtain a token using client_credentials grant.
        No user login required — uses system/ scopes."""
        scopes = self.emr.system_scopes
        if not scopes:
            raise ValueError(f"{self.emr.name} does not define system_scopes for 2-legged auth.")
        data = {
            "grant_type": "client_credentials",
            "scope": " ".join(scopes),
        }
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"2-legged auth: token_url={self.emr.token_url} scopes={scopes}")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.emr.token_url,
                data=data,
                auth=(self.emr.client_id, self.emr.client_secret),
            )
            if not resp.is_success:
                logger.error(f"2-legged auth failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()
            body = resp.json()
            self._token = TokenSet(
                access_token=body["access_token"],
                token_type=body.get("token_type", "Bearer"),
                expires_in=body.get("expires_in", 3600),
                scope=body.get("scope", ""),
            )
            return self._token

    async def exchange_code(self, code: str) -> TokenSet:
        data = self._build_token_data(
            grant_type="authorization_code",
            code=code,
            redirect_uri=self.emr.redirect_uri,
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.emr.token_url,
                data=data,
                auth=self._build_auth_header(),
            )
            resp.raise_for_status()
            body = resp.json()
            self._token = TokenSet(
                access_token=body["access_token"],
                token_type=body.get("token_type", "Bearer"),
                expires_in=body.get("expires_in", 3600),
                refresh_token=body.get("refresh_token"),
                scope=body.get("scope", ""),
                id_token=body.get("id_token"),
            )
            return self._token

    async def refresh(self) -> TokenSet:
        if not self._token or not self._token.refresh_token:
            raise ValueError("No refresh token available. Re-authorize.")
        data = self._build_token_data(
            grant_type="refresh_token",
            refresh_token=self._token.refresh_token,
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.emr.token_url,
                data=data,
                auth=self._build_auth_header(),
            )
            resp.raise_for_status()
            body = resp.json()
            self._token = TokenSet(
                access_token=body["access_token"],
                token_type=body.get("token_type", "Bearer"),
                expires_in=body.get("expires_in", 3600),
                refresh_token=body.get("refresh_token", self._token.refresh_token),
                scope=body.get("scope", self._token.scope),
                id_token=body.get("id_token"),
            )
            return self._token

    async def get_valid_token(self) -> str:
        if not self._token:
            raise ValueError("Not authenticated. Complete OAuth flow first.")
        if self._token.is_expired:
            await self.refresh()
        return self._token.access_token

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None
