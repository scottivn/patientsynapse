"""Scheduling service — provider matching and appointment prep."""

import logging
from typing import Optional, List
from dataclasses import dataclass

from server.fhir.client import FHIRClient
from server.fhir.resources import (
    PractitionerResource,
    PractitionerRoleResource,
    LocationResource,
    CoverageResource,
)
from server.fhir import models

logger = logging.getLogger(__name__)


@dataclass
class ProviderMatch:
    """A provider that matches a referral request."""
    practitioner_id: str
    practitioner_name: str
    specialty: str
    location_name: Optional[str] = None
    location_id: Optional[str] = None
    score: float = 0.0  # Match confidence


@dataclass
class SchedulingContext:
    """Everything needed to book an appointment."""
    patient_id: str
    patient_name: str
    reason: str
    urgency: str
    insurance_verified: bool
    insurance_name: Optional[str] = None
    matched_providers: List[ProviderMatch] = None
    selected_provider: Optional[ProviderMatch] = None

    def __post_init__(self):
        if self.matched_providers is None:
            self.matched_providers = []


class SchedulingService:
    """Matches referrals to providers and prepares scheduling context.

    Note: Actual appointment booking requires the healow Open Access API,
    not the eCW FHIR API. This service handles the pre-booking workflow:
    provider matching, insurance verification, and scheduling prep.
    """

    def __init__(self, fhir_client: FHIRClient):
        self.practitioners = PractitionerResource(fhir_client)
        self.roles = PractitionerRoleResource(fhir_client)
        self.locations = LocationResource(fhir_client)
        self.coverage = CoverageResource(fhir_client)

    async def find_providers(self, specialty: str) -> List[ProviderMatch]:
        """Find providers by specialty."""
        roles = await self.roles.search_by_specialty(specialty)
        matches = []
        for role in roles:
            name = role.practitioner.display if role.practitioner else "Unknown"
            prac_id = ""
            if role.practitioner and role.practitioner.reference:
                prac_id = role.practitioner.reference.split("/")[-1]

            spec_display = ""
            if role.specialty:
                spec_display = role.specialty[0].text or (
                    role.specialty[0].coding[0].display if role.specialty[0].coding else ""
                )

            loc_name = None
            loc_id = None
            if role.location:
                loc_name = role.location[0].display
                if role.location[0].reference:
                    loc_id = role.location[0].reference.split("/")[-1]

            matches.append(ProviderMatch(
                practitioner_id=prac_id,
                practitioner_name=name,
                specialty=spec_display,
                location_name=loc_name,
                location_id=loc_id,
            ))
        return matches

    async def verify_insurance(self, patient_id: str) -> dict:
        """Check if patient has active insurance coverage."""
        coverages = await self.coverage.search_by_patient(patient_id)
        if not coverages:
            return {"verified": False, "reason": "No coverage on file"}

        active = [c for c in coverages if c.status == "active"]
        if not active:
            return {"verified": False, "reason": "No active coverage found"}

        cov = active[0]
        payor_name = cov.payor[0].display if cov.payor else "Unknown"
        return {
            "verified": True,
            "coverage_id": cov.id,
            "payor": payor_name,
            "status": cov.status,
        }

    async def prepare_scheduling(
        self, patient_id: str, patient_name: str, reason: str,
        urgency: str, specialty: Optional[str] = None
    ) -> SchedulingContext:
        """Build full scheduling context for a referral."""
        # Verify insurance
        insurance = await self.verify_insurance(patient_id)

        # Find matching providers
        providers = []
        if specialty:
            providers = await self.find_providers(specialty)

        return SchedulingContext(
            patient_id=patient_id,
            patient_name=patient_name,
            reason=reason,
            urgency=urgency,
            insurance_verified=insurance["verified"],
            insurance_name=insurance.get("payor"),
            matched_providers=providers,
        )

    async def get_locations(self) -> List[models.Location]:
        """Get all practice locations."""
        return await self.locations.search_all()
