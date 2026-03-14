"""Athena Health EMR provider."""

from server.emr.base import EMRProvider, AuthMethod
from typing import Optional


class AthenaProvider(EMRProvider):
    """athenahealth FHIR R4 via SMART on FHIR.

    Auth: client_secret_basic (Athena uses client ID + secret, not JWT).
    API base: https://api.platform.athenahealth.com/fhir/r4
    Developer portal: https://developer.athenahealth.com
    """

    def __init__(self, settings):
        self._s = settings

    @property
    def name(self) -> str:
        return "athenahealth"

    @property
    def fhir_base_url(self) -> str:
        return self._s.athena_fhir_base_url

    @property
    def authorize_url(self) -> str:
        return self._s.athena_authorize_url

    @property
    def token_url(self) -> str:
        return self._s.athena_token_url

    @property
    def client_id(self) -> str:
        return self._s.athena_client_id

    @property
    def client_secret(self) -> Optional[str]:
        return self._s.athena_client_secret

    @property
    def redirect_uri(self) -> str:
        return self._s.emr_redirect_uri

    @property
    def scopes(self) -> list[str]:
        # Athena uses the same SMART v2 style scopes but with some differences.
        # They support both user/ and patient/ launch scopes.
        # For a back-office automation app, user/ is correct.
        return [
            "openid",
            "fhirUser",
            "offline_access",
            # Read
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
            "user/AllergyIntolerance.read",
            "user/MedicationRequest.read",
            "user/Observation.read",
            "user/DiagnosticReport.read",
            # Write
            "user/Patient.write",
            "user/Condition.write",
            "user/DocumentReference.write",
            "user/ServiceRequest.write",
            "user/Encounter.write",
        ]

    @property
    def auth_method(self) -> AuthMethod:
        return AuthMethod.CLIENT_SECRET

    @property
    def system_scopes(self) -> list[str]:
        """2-legged scopes for client_credentials (no user login).
        SMART v2 granular format: .rs = read+search.
        NOTE: Add 'athena/service/Athenanet.MDP' here once it propagates
        in the Athena developer portal (can take 15-30 min after saving)."""
        return [
            "system/Patient.rs",
            "system/AllergyIntolerance.rs",
            "system/Condition.rs",
            "system/Coverage.rs",
            "system/DiagnosticReport.rs",
            "system/DocumentReference.rs",
            "system/Encounter.rs",
            "system/Immunization.rs",
            "system/Location.rs",
            "system/MedicationRequest.rs",
            "system/Observation.rs",
            "system/Organization.rs",
            "system/Practitioner.rs",
            "system/Procedure.rs",
            "system/ServiceRequest.rs",
        ]

    @property
    def supports_refresh(self) -> bool:
        return True

    @property
    def supported_resources(self) -> list[str]:
        return [
            "Patient", "Condition", "Coverage", "Encounter",
            "DocumentReference", "ServiceRequest", "Practitioner",
            "PractitionerRole", "Location", "Organization",
            "Procedure", "AllergyIntolerance", "MedicationRequest",
            "Observation", "DiagnosticReport", "Immunization",
        ]

    @property
    def notes(self) -> str:
        return (
            "Athena uses client_secret auth (not JWT). "
            "Appointment scheduling is available via the Athena Scheduling API. "
            "Task and Communication resources may have limited support."
        )
