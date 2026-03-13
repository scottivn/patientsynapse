"""Referral fax processing service — the core of PatientBridge."""

import logging
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from server.llm import get_llm
from server.fhir.client import FHIRClient
from server.fhir.resources import (
    PatientResource,
    ConditionResource,
    DocumentReferenceResource,
    ServiceRequestResource,
    TaskResource,
    CommunicationResource,
    CoverageResource,
)
from server.fhir import models

logger = logging.getLogger(__name__)


class ReferralStatus(str, Enum):
    PENDING = "pending"          # Just uploaded, not yet processed
    PROCESSING = "processing"    # AI is extracting data
    REVIEW = "review"           # Awaiting human review
    APPROVED = "approved"       # Reviewed, ready to push to eCW
    COMPLETED = "completed"      # Pushed to eCW successfully
    FAILED = "failed"           # Error during processing
    REJECTED = "rejected"       # Manually rejected


@dataclass
class ExtractedReferral:
    """Data extracted from a referral fax by the LLM."""
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    patient_dob: Optional[str] = None
    patient_gender: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_address_line: Optional[str] = None
    patient_address_city: Optional[str] = None
    patient_address_state: Optional[str] = None
    patient_address_zip: Optional[str] = None
    insurance_id: Optional[str] = None
    insurance_name: Optional[str] = None
    referring_provider: Optional[str] = None
    referring_practice: Optional[str] = None
    referring_phone: Optional[str] = None
    referring_fax: Optional[str] = None
    reason: Optional[str] = None
    diagnosis_codes: list = field(default_factory=list)
    urgency: str = "routine"
    notes: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ReferralRecord:
    """A referral tracked through the system."""
    id: str
    filename: str
    status: ReferralStatus
    uploaded_at: str
    extracted_data: Optional[ExtractedReferral] = None
    patient_id: Optional[str] = None
    service_request_id: Optional[str] = None
    error: Optional[str] = None
    reviewed_by: Optional[str] = None
    completed_at: Optional[str] = None


class ReferralService:
    """Processes referral faxes: OCR -> LLM extract -> FHIR create."""

    def __init__(self, fhir_client: FHIRClient):
        self.fhir = fhir_client
        self.patients = PatientResource(fhir_client)
        self.conditions = ConditionResource(fhir_client)
        self.documents = DocumentReferenceResource(fhir_client)
        self.service_requests = ServiceRequestResource(fhir_client)
        self.tasks = TaskResource(fhir_client)
        self.communications = CommunicationResource(fhir_client)
        self.coverage = CoverageResource(fhir_client)
        self.llm = get_llm()
        # In-memory store (swap with DB later)
        self._referrals: dict[str, ReferralRecord] = {}

    async def process_fax(self, fax_text: str, filename: str) -> ReferralRecord:
        """Full pipeline: extract -> match -> create."""
        import uuid
        ref_id = str(uuid.uuid4())[:8]
        record = ReferralRecord(
            id=ref_id,
            filename=filename,
            status=ReferralStatus.PROCESSING,
            uploaded_at=datetime.utcnow().isoformat(),
        )
        self._referrals[ref_id] = record

        try:
            # Step 1: LLM extraction
            logger.info(f"[{ref_id}] Extracting data from {filename}")
            raw = await self.llm.extract_referral_data(fax_text)
            record.extracted_data = self._parse_extracted(raw)
            record.status = ReferralStatus.REVIEW
            logger.info(f"[{ref_id}] Extraction complete, awaiting review")
        except Exception as e:
            logger.error(f"[{ref_id}] Extraction failed: {e}")
            record.status = ReferralStatus.FAILED
            record.error = str(e)

        return record

    async def approve_and_push(self, ref_id: str, overrides: Optional[dict] = None) -> ReferralRecord:
        """After human review, push extracted data to eCW via FHIR."""
        record = self._referrals.get(ref_id)
        if not record:
            raise ValueError(f"Referral {ref_id} not found")
        if record.status not in (ReferralStatus.REVIEW, ReferralStatus.APPROVED):
            raise ValueError(f"Referral {ref_id} is in status {record.status}, cannot approve")

        data = record.extracted_data
        if not data:
            raise ValueError("No extracted data to push")

        # Apply any manual overrides from review
        if overrides:
            for key, val in overrides.items():
                if hasattr(data, key) and val is not None:
                    setattr(data, key, val)

        record.status = ReferralStatus.APPROVED

        try:
            # Step 2: Patient match or create
            patient = await self._match_or_create_patient(data)
            record.patient_id = patient.id
            logger.info(f"[{ref_id}] Patient: {patient.id}")

            # Step 3: Add conditions from diagnosis codes
            for dx in data.diagnosis_codes:
                await self.conditions.create_problem(
                    patient_id=patient.id,
                    code=dx.get("code", ""),
                    system="http://hl7.org/fhir/sid/icd-10-cm",
                    display=dx.get("display", ""),
                )
            logger.info(f"[{ref_id}] Added {len(data.diagnosis_codes)} conditions")

            # Step 4: Create service request (the referral itself)
            sr = await self.service_requests.create_referral(
                patient_id=patient.id,
                referring_provider=data.referring_provider or "Unknown",
                reason=data.reason or "Referral",
                priority=data.urgency,
            )
            record.service_request_id = sr.id
            logger.info(f"[{ref_id}] ServiceRequest: {sr.id}")

            # Step 5: Notify staff
            await self.communications.send_notification(
                patient_id=patient.id,
                message=f"New referral from {data.referring_provider}: {data.reason}",
            )

            record.status = ReferralStatus.COMPLETED
            record.completed_at = datetime.utcnow().isoformat()
            logger.info(f"[{ref_id}] Referral completed successfully")

        except Exception as e:
            logger.error(f"[{ref_id}] Push to eCW failed: {e}")
            record.status = ReferralStatus.FAILED
            record.error = str(e)
            # Create a review task for manual handling
            try:
                await self.tasks.create_review_task(
                    patient_id=record.patient_id or "unknown",
                    description=f"Failed referral {ref_id}: {str(e)}",
                )
            except Exception:
                pass  # Best effort

        return record

    async def _match_or_create_patient(self, data: ExtractedReferral) -> models.Patient:
        """Search for existing patient, create if not found."""
        if data.patient_last_name and data.patient_first_name and data.patient_dob:
            matches = await self.patients.search_by_name_dob(
                family=data.patient_last_name,
                given=data.patient_first_name,
                birthdate=data.patient_dob,
            )
            if matches:
                logger.info(f"Patient match found: {matches[0].id}")
                return matches[0]

        # No match — create new patient
        patient = models.Patient(
            name=[models.HumanName(
                use="official",
                family=data.patient_last_name,
                given=[data.patient_first_name] if data.patient_first_name else [],
            )],
            birthDate=data.patient_dob,
            gender=data.patient_gender,
            telecom=[models.ContactPoint(system="phone", value=data.patient_phone, use="home")]
            if data.patient_phone else [],
            address=[models.Address(
                line=[data.patient_address_line] if data.patient_address_line else [],
                city=data.patient_address_city,
                state=data.patient_address_state,
                postalCode=data.patient_address_zip,
            )] if data.patient_address_city else [],
        )
        result = await self.patients.create(patient)
        logger.info(f"Created new patient: {result.id}")
        return result

    def _parse_extracted(self, raw: dict) -> ExtractedReferral:
        """Convert LLM JSON output to ExtractedReferral."""
        p = raw.get("patient", {})
        r = raw.get("referral", {})
        addr = p.get("address", {}) or {}
        return ExtractedReferral(
            patient_first_name=p.get("first_name"),
            patient_last_name=p.get("last_name"),
            patient_dob=p.get("date_of_birth"),
            patient_gender=p.get("gender"),
            patient_phone=p.get("phone"),
            patient_address_line=addr.get("line"),
            patient_address_city=addr.get("city"),
            patient_address_state=addr.get("state"),
            patient_address_zip=addr.get("zip"),
            insurance_id=p.get("insurance_id"),
            insurance_name=p.get("insurance_name"),
            referring_provider=r.get("referring_provider"),
            referring_practice=r.get("referring_practice"),
            referring_phone=r.get("referring_phone"),
            referring_fax=r.get("referring_fax"),
            reason=r.get("reason"),
            diagnosis_codes=r.get("diagnosis_codes", []),
            urgency=r.get("urgency", "routine"),
            notes=r.get("notes"),
        )

    def get_referral(self, ref_id: str) -> Optional[ReferralRecord]:
        return self._referrals.get(ref_id)

    def list_referrals(self, status: Optional[ReferralStatus] = None) -> list[ReferralRecord]:
        refs = list(self._referrals.values())
        if status:
            refs = [r for r in refs if r.status == status]
        return sorted(refs, key=lambda r: r.uploaded_at, reverse=True)
