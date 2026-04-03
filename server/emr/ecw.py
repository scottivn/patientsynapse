"""eClinicalWorks (eCW) EMR provider."""

from server.emr.base import EMRProvider, AuthMethod
from typing import Optional


class ECWProvider(EMRProvider):
    """eClinicalWorks FHIR R4 via SMART Backend - Single Patient API.

    Auth: asymmetric JWT (private_key_jwt) with RS384, 2-legged client_credentials.
    Scopes: system-level read (no user login required).
    """

    def __init__(self, settings):
        self._s = settings

    @property
    def name(self) -> str:
        return "eClinicalWorks"

    @property
    def fhir_base_url(self) -> str:
        return self._s.ecw_fhir_base_url

    @property
    def authorize_url(self) -> str:
        return self._s.ecw_authorize_url

    @property
    def token_url(self) -> str:
        return self._s.ecw_token_url

    @property
    def client_id(self) -> str:
        return self._s.ecw_client_id

    @property
    def redirect_uri(self) -> str:
        return self._s.emr_redirect_uri

    @property
    def scopes(self) -> list[str]:
        # Read scopes — matches eCW sandbox configuration.
        # Write scopes and offline_access require production contract.
        return [
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
            "user/Device.read",
        ]

    @property
    def production_scopes(self) -> list[str]:
        """Full scope set for production (after contract is signed)."""
        return self.scopes + [
            "openid",
            "fhirUser",
            "offline_access",
            "user/Patient.write",
            "user/Condition.write",
            "user/DocumentReference.write",
            "user/ServiceRequest.write",
            "user/Encounter.write",
            "user/Task.write",
            "user/Communication.write",
        ]

    @property
    def auth_method(self) -> AuthMethod:
        return AuthMethod.ASYMMETRIC_JWT

    @property
    def jwks_url(self) -> Optional[str]:
        return self._s.ecw_jwks_url

    @property
    def supported_resources(self) -> list[str]:
        return [
            "Patient", "Condition", "Coverage", "Encounter",
            "DocumentReference", "ServiceRequest", "Practitioner",
            "PractitionerRole", "Location", "Organization",
            "Procedure", "Provenance", "Device", "Task", "Communication",
        ]

    @property
    def system_scopes(self) -> list[str]:
        """2-legged scopes for client_credentials (no user login).
        Requires Backend - Single Patient API registration in eCW developer portal.
        system/ scopes grant server-to-server access without provider login."""
        return [
            "system/Patient.read",
            "system/Condition.read",
            "system/Coverage.read",
            "system/Encounter.read",
            "system/DocumentReference.read",
            "system/ServiceRequest.read",
            "system/Practitioner.read",
            "system/PractitionerRole.read",
            "system/Location.read",
            "system/Organization.read",
            "system/Procedure.read",
            "system/Provenance.read",
            "system/Device.read",
        ]

    @property
    def notes(self) -> str:
        return (
            "Appointment booking requires healow Open Access API. "
            "Claim submission requires clearinghouse integration."
        )
