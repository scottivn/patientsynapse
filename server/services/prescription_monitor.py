"""Prescription monitor — polls eCW for new DME prescriptions via FHIR DocumentReference.

Detects when a physician adds a new prescription to a patient's report (home lab or
in-lab study), extracts equipment details via LLM, and auto-creates a DME order that
enters the existing workflow pipeline.

Flow:
  1. Poll FHIR DocumentReference (type=57833-6 "Prescription for DME") for docs newer
     than our last checkpoint.
  2. For each new document, fetch the text content (embedded or via OCR).
  3. Run LLM extract_prescription_data() to get structured patient/equipment/diagnosis.
  4. Match patient to existing FHIR Patient record.
  5. Create a DME order (origin=prescription) and enter the pending workflow.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict

from server.db import db_execute, db_fetch_one, db_fetch_all

logger = logging.getLogger(__name__)

# LOINC code for "Prescription for durable medical equipment"
DME_PRESCRIPTION_TYPE = "57833-6"


class RxStatus(str, Enum):
    DETECTED = "detected"          # Doc found in FHIR, not yet processed
    EXTRACTING = "extracting"      # LLM extraction in progress
    EXTRACTED = "extracted"        # LLM extraction succeeded
    REVIEW = "review"              # Awaiting human review before DME order creation
    ORDER_CREATED = "order_created"  # DME order created from this Rx
    FAILED = "failed"              # Processing failed (extraction or patient match)
    SKIPPED = "skipped"            # Duplicate or irrelevant document


@dataclass
class DetectedPrescription:
    """Tracks a single prescription document through the detection → order pipeline."""
    id: str                         # FHIR DocumentReference ID
    patient_ref: str                # e.g. "Patient/PT001"
    date: str                       # ISO datetime from the DocumentReference
    description: str                # Brief description from the doc
    author: str = ""                # Prescribing physician name
    author_npi: str = ""            # Prescribing physician NPI
    status: RxStatus = RxStatus.DETECTED
    raw_text: str = ""              # Extracted/fetched prescription text
    extracted_data: Optional[dict] = None  # LLM extraction result
    dme_order_id: Optional[str] = None     # Created DME order ID
    error: Optional[str] = None
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    processed_at: Optional[str] = None


def _row_to_rx(row: dict) -> DetectedPrescription:
    """Convert a DB row to a DetectedPrescription."""
    extracted = None
    if row.get("extracted_data"):
        try:
            extracted = json.loads(row["extracted_data"])
        except (json.JSONDecodeError, TypeError):
            pass
    return DetectedPrescription(
        id=row["id"],
        patient_ref=row["patient_ref"],
        date=row["date"],
        description=row["description"],
        author=row.get("author", ""),
        author_npi=row.get("author_npi", ""),
        status=RxStatus(row.get("status", "detected")),
        raw_text=row.get("raw_text", ""),
        extracted_data=extracted,
        dme_order_id=row.get("dme_order_id"),
        error=row.get("error"),
        detected_at=row.get("detected_at", ""),
        processed_at=row.get("processed_at"),
    )


async def _save_rx(rx: DetectedPrescription) -> None:
    """Upsert a prescription record to the database."""
    extracted_json = json.dumps(rx.extracted_data) if rx.extracted_data else None
    await db_execute(
        """INSERT INTO prescriptions (id, patient_ref, date, description, author, author_npi,
               status, raw_text, extracted_data, dme_order_id, error, detected_at, processed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               status=excluded.status, raw_text=excluded.raw_text,
               extracted_data=excluded.extracted_data, dme_order_id=excluded.dme_order_id,
               error=excluded.error, processed_at=excluded.processed_at""",
        (rx.id, rx.patient_ref, rx.date, rx.description, rx.author, rx.author_npi,
         rx.status.value, rx.raw_text, extracted_json, rx.dme_order_id, rx.error,
         rx.detected_at, rx.processed_at),
    )


class PrescriptionMonitorService:
    """Polls FHIR for new DME prescriptions and creates DME orders from them."""

    def __init__(self, fhir_client, dme_service, llm_provider=None):
        self._fhir = fhir_client
        self._dme = dme_service
        self._llm = llm_provider
        # High-water mark — only look for docs newer than this
        self._last_check: Optional[str] = None
        # Polling state
        self._polling: bool = False
        self._poll_task: Optional[asyncio.Task] = None

    def set_llm(self, llm_provider):
        """Update the LLM provider (supports hot-swap)."""
        self._llm = llm_provider

    # ── Polling ────────────────────────────────────────────────────

    async def poll_once(self) -> List[DetectedPrescription]:
        """Check FHIR for new DME prescriptions since last poll."""
        search_params = {"type": DME_PRESCRIPTION_TYPE}
        if self._last_check:
            search_params["date"] = f"gt{self._last_check}"

        try:
            bundle = await self._fhir.search("DocumentReference", search_params)
        except Exception as e:
            logger.error(f"Prescription poll FHIR search failed: {e}")
            return []

        entries = bundle.get("entry", [])
        new_rxs: List[DetectedPrescription] = []

        for entry in entries:
            doc = entry.get("resource", {})
            doc_id = doc.get("id", "")

            # Skip if we've already seen this document
            existing = await db_fetch_one("SELECT id FROM prescriptions WHERE id = ?", (doc_id,))
            if existing:
                continue

            # Extract metadata from the DocumentReference
            patient_ref = doc.get("subject", {}).get("reference", "")
            doc_date = doc.get("date", datetime.now().isoformat())
            description = doc.get("description", "")
            author_name = ""
            author_npi = ""
            for author in doc.get("author", []):
                author_name = author.get("display", "")
                ident = author.get("identifier", {})
                if isinstance(ident, dict):
                    author_npi = ident.get("value", "")

            raw_text = doc.get("_prescription_text", "")
            if not raw_text:
                for content in doc.get("content", []):
                    att = content.get("attachment", {})
                    if att.get("data"):
                        import base64
                        try:
                            raw_text = base64.b64decode(att["data"]).decode("utf-8")
                        except Exception:
                            raw_text = ""
                    if raw_text:
                        break

            rx = DetectedPrescription(
                id=doc_id,
                patient_ref=patient_ref,
                date=doc_date,
                description=description,
                author=author_name,
                author_npi=author_npi,
                raw_text=raw_text,
            )
            await _save_rx(rx)
            new_rxs.append(rx)
            logger.info(f"Detected new prescription {doc_id} for {patient_ref}: {description}")

        self._last_check = datetime.now().isoformat()
        logger.info(f"Prescription poll complete: {len(new_rxs)} new, {len(entries)} total scanned")
        return new_rxs

    async def process_detected(self) -> List[DetectedPrescription]:
        """Process all detected-but-unprocessed prescriptions through the LLM → DME pipeline."""
        from server.llm import get_llm

        llm = self._llm or get_llm()
        rows = await db_fetch_all(
            "SELECT * FROM prescriptions WHERE status = ?",
            (RxStatus.DETECTED.value,),
        )
        pending = [_row_to_rx(r) for r in rows]

        if not pending:
            return []

        processed: List[DetectedPrescription] = []
        for rx in pending:
            try:
                await self._process_single(rx, llm)
            except Exception as e:
                rx.status = RxStatus.FAILED
                rx.error = str(e)
                logger.error(f"Failed to process prescription {rx.id}: {e}")
            rx.processed_at = datetime.now().isoformat()
            await _save_rx(rx)
            processed.append(rx)

        return processed

    async def _process_single(self, rx: DetectedPrescription, llm):
        """Run LLM extraction on a single prescription and queue for human review."""
        if not rx.raw_text:
            rx.status = RxStatus.FAILED
            rx.error = "No prescription text available for extraction"
            return

        # Step 1: LLM extraction
        rx.status = RxStatus.EXTRACTING
        try:
            extracted = await llm.extract_prescription_data(rx.raw_text)
            rx.extracted_data = extracted
            rx.status = RxStatus.EXTRACTED
        except Exception as e:
            rx.status = RxStatus.FAILED
            rx.error = f"LLM extraction failed: {e}"
            return

        equipment_list = extracted.get("equipment", [])
        if not equipment_list:
            rx.status = RxStatus.FAILED
            rx.error = "No equipment found in prescription"
            return

        # Stop at REVIEW — human must approve before DME order creation
        rx.status = RxStatus.REVIEW
        await _save_rx(rx)
        logger.info(f"Prescription {rx.id} queued for review ({equipment_list[0].get('category', 'Unknown')})")

    async def approve_prescription(self, doc_id: str) -> DetectedPrescription:
        """Approve a reviewed prescription and create the DME order."""
        rx = await self.get_prescription(doc_id)
        if not rx:
            raise ValueError(f"Prescription {doc_id} not found")
        if rx.status != RxStatus.REVIEW:
            raise ValueError(f"Prescription {doc_id} is not in review status (current: {rx.status.value})")
        if not rx.extracted_data:
            raise ValueError(f"Prescription {doc_id} has no extracted data")

        extracted = rx.extracted_data
        patient = extracted.get("patient", {})
        prescriber = extracted.get("prescriber", {})
        diagnosis = extracted.get("diagnosis", {})
        equipment_list = extracted.get("equipment", [])
        clinical = extracted.get("clinical", {})

        primary = equipment_list[0]
        hcpcs_codes = [eq.get("hcpcs_code") for eq in equipment_list if eq.get("hcpcs_code")]

        patient_id = rx.patient_ref.replace("Patient/", "") if rx.patient_ref else ""

        equip_desc = "; ".join(
            f"{eq.get('description', eq.get('category', 'Unknown'))}"
            + (f" ({eq['hcpcs_code']})" if eq.get("hcpcs_code") else "")
            for eq in equipment_list
        )

        patient_first = patient.get("first_name", "")
        patient_last = patient.get("last_name", "")
        patient_dob = patient.get("date_of_birth", "")
        patient_phone = patient.get("phone", "")

        if patient_id and self._fhir and (not patient_first or not patient_last):
            try:
                pt_resource = await self._fhir.read("Patient", patient_id)
                names = pt_resource.get("name", [{}])
                if names:
                    patient_first = patient_first or names[0].get("given", [""])[0]
                    patient_last = patient_last or names[0].get("family", "")
                patient_dob = patient_dob or pt_resource.get("birthDate", "")
                telecoms = pt_resource.get("telecom", [])
                for t in telecoms:
                    if t.get("system") == "phone" and not patient_phone:
                        patient_phone = t.get("value", "")
            except Exception:
                pass

        clinical_notes = []
        if clinical.get("ahi"):
            clinical_notes.append(f"AHI: {clinical['ahi']}")
        if clinical.get("pressure_settings"):
            clinical_notes.append(f"Settings: {clinical['pressure_settings']}")
        if clinical.get("compliance_note"):
            clinical_notes.append(f"Compliance: {clinical['compliance_note']}")
        if clinical.get("notes"):
            clinical_notes.append(clinical["notes"])

        order_data = {
            "patient_first_name": patient_first,
            "patient_last_name": patient_last,
            "patient_dob": patient_dob,
            "patient_phone": patient_phone,
            "patient_id": patient_id,
            "equipment_category": primary.get("category", "Other Sleep DME"),
            "equipment_description": equip_desc,
            "quantity": len(equipment_list),
            "hcpcs_codes": hcpcs_codes,
            "diagnosis_code": diagnosis.get("code", ""),
            "diagnosis_description": diagnosis.get("description", ""),
            "referring_physician": rx.author or prescriber.get("name", ""),
            "referring_npi": rx.author_npi or prescriber.get("npi", ""),
            "clinical_notes": " | ".join(clinical_notes) if clinical_notes else "",
            "origin": "prescription",
            "auto_replace": not clinical.get("is_resupply", False),
        }

        order = await self._dme.create_order(order_data)
        rx.dme_order_id = order.id
        rx.status = RxStatus.ORDER_CREATED
        rx.processed_at = datetime.now().isoformat()
        await _save_rx(rx)
        logger.info(f"Approved prescription {rx.id} -> DME order {order.id}")
        return rx

    async def reject_prescription(self, doc_id: str, reason: str = "") -> DetectedPrescription:
        """Reject a reviewed prescription — no DME order will be created."""
        rx = await self.get_prescription(doc_id)
        if not rx:
            raise ValueError(f"Prescription {doc_id} not found")
        if rx.status != RxStatus.REVIEW:
            raise ValueError(f"Prescription {doc_id} is not in review status (current: {rx.status.value})")

        rx.status = RxStatus.SKIPPED
        rx.error = reason or "Rejected during review"
        rx.processed_at = datetime.now().isoformat()
        await _save_rx(rx)
        logger.info(f"Rejected prescription {rx.id}: {reason}")
        return rx

    async def poll_and_process(self) -> Dict:
        """Combined poll + process — convenience method for the API endpoint."""
        new_rxs = await self.poll_once()
        processed = await self.process_detected()
        return {
            "detected": len(new_rxs),
            "processed": len(processed),
            "orders_created": sum(1 for rx in processed if rx.status == RxStatus.ORDER_CREATED),
            "failed": sum(1 for rx in processed if rx.status == RxStatus.FAILED),
            "prescriptions": [self._serialize(rx) for rx in (new_rxs or processed)],
        }

    # ── Background polling ─────────────────────────────────────────

    def start_polling(self, interval_seconds: int = 300):
        """Start background polling loop (default 5 min)."""
        if self._polling:
            logger.info("Prescription polling already active")
            return
        self._polling = True
        self._poll_task = asyncio.create_task(self._poll_loop(interval_seconds))
        logger.info(f"Prescription polling started (every {interval_seconds}s)")

    def stop_polling(self):
        """Stop background polling loop."""
        self._polling = False
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        logger.info("Prescription polling stopped")

    async def _poll_loop(self, interval: int):
        """Background loop that checks for new prescriptions on interval."""
        while self._polling:
            try:
                result = await self.poll_and_process()
                if result["detected"] > 0 or result["processed"] > 0:
                    logger.info(f"Prescription poll cycle: {result}")
            except Exception as e:
                logger.error(f"Prescription poll error: {e}")
            await asyncio.sleep(interval)

    # ── Query methods ──────────────────────────────────────────────

    async def list_prescriptions(self, status: Optional[RxStatus] = None) -> List[DetectedPrescription]:
        if status:
            rows = await db_fetch_all(
                "SELECT * FROM prescriptions WHERE status = ? ORDER BY detected_at DESC",
                (status.value,),
            )
        else:
            rows = await db_fetch_all(
                "SELECT * FROM prescriptions ORDER BY detected_at DESC"
            )
        return [_row_to_rx(r) for r in rows]

    async def get_prescription(self, doc_id: str) -> Optional[DetectedPrescription]:
        row = await db_fetch_one("SELECT * FROM prescriptions WHERE id = ?", (doc_id,))
        return _row_to_rx(row) if row else None

    async def get_status(self) -> dict:
        """Return current monitor status for the API."""
        rows = await db_fetch_all(
            "SELECT status, COUNT(*) as cnt FROM prescriptions GROUP BY status"
        )
        by_status = {r["status"]: r["cnt"] for r in rows}
        total = sum(by_status.values())
        return {
            "polling_active": self._polling,
            "last_check": self._last_check,
            "total_detected": total,
            "by_status": by_status,
        }

    async def reset(self):
        """Clear all tracked prescriptions and reset the checkpoint."""
        await db_execute("DELETE FROM prescriptions")
        self._last_check = None
        self.stop_polling()
        logger.info("Prescription monitor reset")

    # ── Serialization ──────────────────────────────────────────────

    @staticmethod
    def _serialize(rx: DetectedPrescription) -> dict:
        return {
            "id": rx.id,
            "patient_ref": rx.patient_ref,
            "date": rx.date,
            "description": rx.description,
            "author": rx.author,
            "author_npi": rx.author_npi,
            "status": rx.status.value,
            "dme_order_id": rx.dme_order_id,
            "error": rx.error,
            "detected_at": rx.detected_at,
            "processed_at": rx.processed_at,
            "extracted_data": rx.extracted_data,
            "confidence": rx.extracted_data.get("confidence", 0.0) if rx.extracted_data else None,
        }
