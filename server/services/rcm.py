"""Revenue Cycle Management analytics service."""

import logging
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime, date
from collections import Counter

from server.fhir.client import FHIRClient
from server.fhir.resources import (
    EncounterResource,
    ConditionResource,
    CoverageResource,
    ProcedureResource,
    OrganizationResource,
)
from server.fhir import models

logger = logging.getLogger(__name__)


@dataclass
class RCMSummary:
    """High-level RCM dashboard data."""
    total_encounters: int = 0
    encounters_this_month: int = 0
    top_diagnoses: List[dict] = field(default_factory=list)
    payer_mix: List[dict] = field(default_factory=list)
    procedures_count: int = 0
    generated_at: str = ""


@dataclass
class PatientBillingContext:
    """Billing context for a single patient."""
    patient_id: str
    encounters: List[dict] = field(default_factory=list)
    diagnoses: List[dict] = field(default_factory=list)
    procedures: List[dict] = field(default_factory=list)
    insurance: Optional[dict] = None


class RCMService:
    """Revenue cycle analytics from FHIR data.

    Note: Actual claim submission and clearinghouse integration requires
    a separate clearinghouse API (e.g., Change Healthcare, Availity) or
    eCW's internal billing module. This service gathers data for analytics
    and prepares billing context.
    """

    def __init__(self, fhir_client: FHIRClient):
        self.encounters = EncounterResource(fhir_client)
        self.conditions = ConditionResource(fhir_client)
        self.coverage = CoverageResource(fhir_client)
        self.procedures = ProcedureResource(fhir_client)
        self.organizations = OrganizationResource(fhir_client)

    async def get_patient_billing_context(self, patient_id: str) -> PatientBillingContext:
        """Gather all billing-relevant data for a patient."""
        ctx = PatientBillingContext(patient_id=patient_id)

        # Encounters
        enc_list = await self.encounters.search_by_patient(patient_id)
        ctx.encounters = [
            {
                "id": e.id,
                "status": e.status,
                "type": e.type[0].text if e.type else None,
                "period_start": e.period.start if e.period else None,
                "diagnosis_count": len(e.diagnosis),
            }
            for e in enc_list
        ]

        # Diagnoses
        cond_list = await self.conditions.search_by_patient(patient_id)
        ctx.diagnoses = [
            {
                "id": c.id,
                "code": c.code.coding[0].code if c.code and c.code.coding else None,
                "display": c.code.coding[0].display if c.code and c.code.coding else c.code.text if c.code else None,
                "category": c.category[0].coding[0].code if c.category and c.category[0].coding else None,
            }
            for c in cond_list
        ]

        # Procedures
        proc_list = await self.procedures.search_by_patient(patient_id)
        ctx.procedures = [
            {
                "id": p.id,
                "code": p.code.coding[0].code if p.code and p.code.coding else None,
                "display": p.code.coding[0].display if p.code and p.code.coding else None,
                "status": p.status,
                "date": p.performedDateTime,
            }
            for p in proc_list
        ]

        # Insurance
        cov_list = await self.coverage.search_by_patient(patient_id)
        if cov_list:
            active = next((c for c in cov_list if c.status == "active"), cov_list[0])
            ctx.insurance = {
                "id": active.id,
                "payor": active.payor[0].display if active.payor else None,
                "status": active.status,
            }

        return ctx

    async def get_payer_mix(self, patient_ids: List[str]) -> List[dict]:
        """Analyze payer distribution across patients."""
        payer_counts: Counter = Counter()
        for pid in patient_ids:
            cov_list = await self.coverage.search_by_patient(pid)
            for c in cov_list:
                if c.status == "active" and c.payor:
                    payer_counts[c.payor[0].display or "Unknown"] += 1
        total = sum(payer_counts.values()) or 1
        return [
            {"payor": name, "count": count, "percentage": round(count / total * 100, 1)}
            for name, count in payer_counts.most_common()
        ]

    async def get_top_diagnoses(self, patient_ids: List[str], limit: int = 10) -> List[dict]:
        """Get most common diagnoses across patients."""
        dx_counts: Counter = Counter()
        for pid in patient_ids:
            cond_list = await self.conditions.search_by_patient(pid)
            for c in cond_list:
                if c.code and c.code.coding:
                    key = f"{c.code.coding[0].code}|{c.code.coding[0].display or ''}"
                    dx_counts[key] += 1
        return [
            {"code": k.split("|")[0], "display": k.split("|")[1], "count": v}
            for k, v in dx_counts.most_common(limit)
        ]
