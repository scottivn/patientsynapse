"""Stub FHIR client — in-memory store for testing without a live EMR connection.

Activated by setting USE_STUB_FHIR=true in .env.
Implements the same interface as FHIRClient so the full pipeline runs
end-to-end: OCR → LLM extraction → patient match/create → ServiceRequest.
"""

import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StubFHIRClient:
    """Drop-in replacement for FHIRClient that stores resources in memory."""

    def __init__(self):
        self._store: dict[str, dict[str, dict]] = {}  # {ResourceType: {id: resource}}
        # Seed with a handful of test patients matching dummy fax data
        self._seed_patients()
        self._seed_prescriptions()
        self._seed_devices()
        logger.info("StubFHIRClient initialized (in-memory, no EMR connection)")

    # ------------------------------------------------------------------
    # Public interface — matches FHIRClient exactly
    # ------------------------------------------------------------------

    async def read(self, resource_type: str, resource_id: str) -> dict:
        resource = self._store.get(resource_type, {}).get(resource_id)
        if not resource:
            raise ValueError(f"{resource_type}/{resource_id} not found in stub store")
        logger.info(f"STUB READ {resource_type}/{resource_id}")
        return resource

    async def search(self, resource_type: str, params: Optional[dict] = None) -> dict:
        params = params or {}
        resources = list(self._store.get(resource_type, {}).values())

        # Apply simple equality filters for common search params
        for key, value in params.items():
            value_lower = str(value).lower()
            if key == "family":
                resources = [r for r in resources if self._name_match(r, "family", value_lower)]
            elif key == "given":
                resources = [r for r in resources if self._name_match(r, "given", value_lower)]
            elif key == "birthdate":
                resources = [r for r in resources if r.get("birthDate", "") == value]
            elif key == "patient":
                patient_ref = f"Patient/{value}" if not value.startswith("Patient/") else value
                resources = [
                    r for r in resources
                    if r.get("subject", {}).get("reference") == patient_ref
                    or r.get("patient", {}).get("reference") == patient_ref
                    or r.get("beneficiary", {}).get("reference") == patient_ref
                ]
            elif key == "identifier":
                resources = [
                    r for r in resources
                    if any(i.get("value") == value for i in r.get("identifier", []))
                ]
            elif key == "type":
                # Match on type.coding[].code
                resources = [
                    r for r in resources
                    if any(c.get("code") == value for c in r.get("type", {}).get("coding", []))
                ]
            elif key.startswith("date=gt") or key == "date" and str(value).startswith("gt"):
                # Support date greater-than filter (e.g. date=gt2024-01-01)
                threshold = str(value).replace("gt", "")
                resources = [r for r in resources if (r.get("date", "") > threshold)]

        bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": len(resources),
            "entry": [{"resource": r} for r in resources],
        }
        logger.info(f"STUB SEARCH {resource_type} params={params} -> {len(resources)} results")
        return bundle

    async def create(self, resource_type: str, resource: dict) -> dict:
        resource_id = str(uuid.uuid4())[:8].upper()
        resource = {**resource, "id": resource_id, "resourceType": resource_type}
        if resource_type not in self._store:
            self._store[resource_type] = {}
        self._store[resource_type][resource_id] = resource
        logger.info(f"STUB CREATE {resource_type}/{resource_id}")
        return resource

    async def update(self, resource_type: str, resource_id: str, resource: dict) -> dict:
        if resource_type not in self._store or resource_id not in self._store[resource_type]:
            raise ValueError(f"{resource_type}/{resource_id} not found")
        self._store[resource_type][resource_id] = {**resource, "id": resource_id}
        logger.info(f"STUB UPDATE {resource_type}/{resource_id}")
        return self._store[resource_type][resource_id]

    async def close(self):
        pass  # Nothing to close

    # ------------------------------------------------------------------
    # Inspection helpers (used by debug endpoints)
    # ------------------------------------------------------------------

    def list_resources(self, resource_type: str) -> list[dict]:
        return list(self._store.get(resource_type, {}).values())

    def summary(self) -> dict:
        return {rt: len(resources) for rt, resources in self._store.items()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _name_match(self, resource: dict, field: str, value: str) -> bool:
        for name_entry in resource.get("name", []):
            if field == "family" and value in name_entry.get("family", "").lower():
                return True
            if field == "given":
                for g in name_entry.get("given", []):
                    if value in g.lower():
                        return True
        return False

    def _seed_prescriptions(self):
        """Pre-populate DocumentReference store with sleep study Rx documents."""
        from datetime import datetime, timedelta
        now = datetime.now()
        prescriptions = [
            {
                "resourceType": "DocumentReference", "id": "DOC001",
                "status": "current",
                "type": {"coding": [{"system": "http://loinc.org", "code": "57833-6", "display": "Prescription for durable medical equipment"}]},
                "category": [{"coding": [{"system": "http://loinc.org", "code": "57833-6", "display": "Prescription"}]}],
                "subject": {"reference": "Patient/PT001"},
                "date": (now - timedelta(hours=2)).isoformat(),
                "description": "CPAP Rx — Maria Garcia — Home sleep study completed, AHI 18.4, recommend CPAP at 10 cmH2O",
                "author": [{"display": "Dr. Alejandro Reyes", "identifier": {"value": "1234567890"}}],
                "content": [{"attachment": {"contentType": "text/plain", "data": "",
                    "title": "CPAP Prescription — Garcia, Maria"}}],
                "_prescription_text": (
                    "PRESCRIPTION FOR DURABLE MEDICAL EQUIPMENT\n\n"
                    "Patient: Maria Garcia  DOB: 06/15/1975\n"
                    "Date: " + now.strftime("%m/%d/%Y") + "\n\n"
                    "Diagnosis: G47.33 — Obstructive Sleep Apnea\n"
                    "AHI: 18.4 events/hour (moderate)\n\n"
                    "Equipment Ordered:\n"
                    "  1. CPAP Machine (E0601) — continuous positive airway pressure device\n"
                    "  2. Full Face Mask (A7030) — with headgear\n"
                    "  3. Heated Tubing (A4604)\n"
                    "  4. Humidifier Water Chamber (A7046)\n\n"
                    "Settings: 10 cmH2O, EPR 2, ramp 20 min\n"
                    "Duration: 99 months (lifetime need)\n\n"
                    "Prescribing Physician: Dr. Alejandro Reyes\n"
                    "NPI: 1234567890\n"
                    "Sleep Center of South Texas\n"
                    "Phone: (210) 555-8000  Fax: (210) 555-8001"
                ),
            },
            {
                "resourceType": "DocumentReference", "id": "DOC002",
                "status": "current",
                "type": {"coding": [{"system": "http://loinc.org", "code": "57833-6", "display": "Prescription for durable medical equipment"}]},
                "category": [{"coding": [{"system": "http://loinc.org", "code": "57833-6", "display": "Prescription"}]}],
                "subject": {"reference": "Patient/PT003"},
                "date": (now - timedelta(hours=6)).isoformat(),
                "description": "BiPAP Rx — Rosa Rodriguez — Complex sleep apnea, failed CPAP trial",
                "author": [{"display": "Dr. Alejandro Reyes", "identifier": {"value": "1234567890"}}],
                "content": [{"attachment": {"contentType": "text/plain", "data": "",
                    "title": "BiPAP Prescription — Rodriguez, Rosa"}}],
                "_prescription_text": (
                    "PRESCRIPTION FOR DURABLE MEDICAL EQUIPMENT\n\n"
                    "Patient: Rosa Rodriguez  DOB: 11/30/1962\n"
                    "Date: " + now.strftime("%m/%d/%Y") + "\n\n"
                    "Diagnosis: G47.31 — Central Sleep Apnea\n"
                    "AHI: 34.2 events/hour (severe), central apneas 12/hr\n"
                    "Previous trial: CPAP failed — persistent central events\n\n"
                    "Equipment Ordered:\n"
                    "  1. BiPAP Auto-SV Machine (E0470)\n"
                    "  2. Nasal Pillow Mask (A7033) — with headgear\n"
                    "  3. Heated Tubing (A4604)\n"
                    "  4. Humidifier Water Chamber (A7046)\n"
                    "  5. Disposable Filters x6 (A7038)\n\n"
                    "Settings: IPAP 14, EPAP 8, auto-SV backup rate 12\n"
                    "Duration: 99 months\n\n"
                    "Prescribing Physician: Dr. Alejandro Reyes\n"
                    "NPI: 1234567890\n"
                    "Sleep Center of South Texas\n"
                    "Phone: (210) 555-8000  Fax: (210) 555-8001"
                ),
            },
            {
                "resourceType": "DocumentReference", "id": "DOC003",
                "status": "current",
                "type": {"coding": [{"system": "http://loinc.org", "code": "57833-6", "display": "Prescription for durable medical equipment"}]},
                "category": [{"coding": [{"system": "http://loinc.org", "code": "57833-6", "display": "Prescription"}]}],
                "subject": {"reference": "Patient/PT004"},
                "date": (now - timedelta(days=3)).isoformat(),
                "description": "CPAP Resupply Rx — Carlos Hernandez — Annual resupply, compliant",
                "author": [{"display": "Dr. Marta Espinoza", "identifier": {"value": "9876543210"}}],
                "content": [{"attachment": {"contentType": "text/plain", "data": "",
                    "title": "CPAP Resupply Prescription — Hernandez, Carlos"}}],
                "_prescription_text": (
                    "PRESCRIPTION FOR DURABLE MEDICAL EQUIPMENT\n\n"
                    "Patient: Carlos Hernandez  DOB: 03/22/1985\n"
                    "Date: " + (now - timedelta(days=3)).strftime("%m/%d/%Y") + "\n\n"
                    "Diagnosis: G47.33 — Obstructive Sleep Apnea\n"
                    "Compliance: Avg 6.8 hrs/night, 28/30 days >4hrs — COMPLIANT\n\n"
                    "Equipment Ordered (Annual Resupply):\n"
                    "  1. Full Face Mask (A7030)\n"
                    "  2. Mask Cushion Replacement (A7031)\n"
                    "  3. Headgear (A7035)\n"
                    "  4. Heated Tubing (A4604)\n"
                    "  5. Humidifier Water Chamber (A7046)\n"
                    "  6. Disposable Filters x6 (A7038)\n"
                    "  7. Reusable Filter x1 (A7039)\n\n"
                    "Prescribing Physician: Dr. Marta Espinoza\n"
                    "NPI: 9876543210\n"
                    "Pulmonary & Sleep Associates\n"
                    "Phone: (210) 555-9100  Fax: (210) 555-9101"
                ),
            },
        ]
        self._store["DocumentReference"] = {d["id"]: d for d in prescriptions}

    def _seed_patients(self):
        """Pre-populate store with test patients matching dummy fax name pools."""
        seed_patients = [
            {
                "resourceType": "Patient", "id": "PT001",
                "name": [{"use": "official", "family": "Garcia", "given": ["Maria"]}],
                "birthDate": "1975-06-15", "gender": "female",
                "telecom": [{"system": "phone", "value": "(210) 555-0101", "use": "home"}],
                "address": [{"line": ["1234 Medical Dr"], "city": "San Antonio", "state": "TX", "postalCode": "78229"}],
                "identifier": [{"system": "urn:patientsynapse:pid", "value": "PT001"}],
            },
            {
                "resourceType": "Patient", "id": "PT002",
                "name": [{"use": "official", "family": "Martinez", "given": ["Jose"]}],
                "birthDate": "1948-05-02", "gender": "male",
                "telecom": [{"system": "phone", "value": "(210) 219-8237", "use": "home"}],
                "address": [{"line": ["268 Bank St"], "city": "San Antonio", "state": "TX", "postalCode": "78204"}],
                "identifier": [{"system": "urn:patientsynapse:pid", "value": "PT002"}],
            },
            {
                "resourceType": "Patient", "id": "PT003",
                "name": [{"use": "official", "family": "Rodriguez", "given": ["Rosa"]}],
                "birthDate": "1962-11-30", "gender": "female",
                "telecom": [{"system": "phone", "value": "(210) 555-0303", "use": "home"}],
                "address": [{"line": ["5678 Babcock Rd"], "city": "San Antonio", "state": "TX", "postalCode": "78240"}],
                "identifier": [{"system": "urn:patientsynapse:pid", "value": "PT003"}],
            },
            {
                "resourceType": "Patient", "id": "PT004",
                "name": [{"use": "official", "family": "Hernandez", "given": ["Carlos"]}],
                "birthDate": "1985-03-22", "gender": "male",
                "telecom": [{"system": "phone", "value": "(210) 555-0404", "use": "home"}],
                "address": [{"line": ["910 Pleasanton Rd"], "city": "San Antonio", "state": "TX", "postalCode": "78214"}],
                "identifier": [{"system": "urn:patientsynapse:pid", "value": "PT004"}],
            },
            {
                "resourceType": "Patient", "id": "PT005",
                "name": [{"use": "official", "family": "Wilson", "given": ["Patricia"]}],
                "birthDate": "1967-12-13", "gender": "female",
                "telecom": [{"system": "phone", "value": "(210) 962-9830", "use": "home"}],
                "address": [{"line": ["16458 Nacogdoches Rd"], "city": "Boerne", "state": "TX", "postalCode": "78006"}],
                "identifier": [{"system": "urn:patientsynapse:pid", "value": "PT005"}],
            },
        ]
        self._store["Patient"] = {p["id"]: p for p in seed_patients}

        # Seed Coverage for each patient
        insurances = [
            ("BCBS of Texas PPO", "ppo", "MBR123456", "GRP001"),
            ("UHC Complete Care (HMO)", "hmo", "987574043", "90732"),
            ("Aetna Better Health (HMO)", "hmo", "MBR789012", "GRP003"),
            ("Humana Gold Plus (HMO)", "hmo", "384412919", "28301"),
            ("Curative First Health (PPO)", "ppo", "CUR2612515", "GRP005"),
        ]
        self._store["Coverage"] = {}
        for i, (patient_id, ins) in enumerate(zip(["PT001", "PT002", "PT003", "PT004", "PT005"], insurances)):
            name, plan_type, member_id, group = ins
            cov_id = f"COV00{i+1}"
            self._store["Coverage"][cov_id] = {
                "resourceType": "Coverage", "id": cov_id,
                "status": "active",
                "beneficiary": {"reference": f"Patient/{patient_id}"},
                "payor": [{"display": name}],
                "subscriberId": member_id,
                "grouping": {"group": group, "plan": plan_type.upper()},
                "period": {"start": "2024-01-01", "end": "2026-12-31"},
            }

    def _seed_devices(self):
        """Pre-populate Device store with DME equipment for test patients."""
        devices = [
            {
                "resourceType": "Device", "id": "DEV001",
                "status": "active",
                "type": {"coding": [{"system": "http://snomed.info/sct", "code": "702172008", "display": "CPAP device"}], "text": "CPAP Machine"},
                "manufacturer": "ResMed",
                "modelNumber": "AirSense 11 AutoSet",
                "serialNumber": "RS11-2024-00147",
                "patient": {"reference": "Patient/PT001"},
                "note": [{"text": "Settings: pressure 10 cmH2O, EPR 2, ramp 20 min"}],
            },
            {
                "resourceType": "Device", "id": "DEV002",
                "status": "active",
                "type": {"coding": [{"system": "http://snomed.info/sct", "code": "467141004", "display": "Nasal mask"}], "text": "CPAP Mask — Nasal"},
                "manufacturer": "ResMed",
                "modelNumber": "AirFit N30i",
                "patient": {"reference": "Patient/PT001"},
                "note": [{"text": "Size: Medium, Standard frame"}],
            },
            {
                "resourceType": "Device", "id": "DEV003",
                "status": "active",
                "type": {"coding": [{"system": "http://snomed.info/sct", "code": "702172008", "display": "BiPAP device"}], "text": "BiPAP / ASV Machine"},
                "manufacturer": "ResMed",
                "modelNumber": "AirCurve 10 ASV",
                "serialNumber": "AC10-2025-00382",
                "patient": {"reference": "Patient/PT003"},
                "note": [{"text": "Settings: IPAP 15, EPAP 8, auto-SV mode"}],
            },
            {
                "resourceType": "Device", "id": "DEV004",
                "status": "active",
                "type": {"coding": [{"system": "http://snomed.info/sct", "code": "702172008", "display": "CPAP device"}], "text": "CPAP Machine"},
                "manufacturer": "Philips Respironics",
                "modelNumber": "DreamStation 2 Auto",
                "serialNumber": "DS2-2025-01044",
                "patient": {"reference": "Patient/PT004"},
                "note": [{"text": "Settings: pressure 12 cmH2O, A-Flex 3"}],
            },
            {
                "resourceType": "Device", "id": "DEV005",
                "status": "active",
                "type": {"coding": [{"system": "http://snomed.info/sct", "code": "467141004", "display": "Full face mask"}], "text": "CPAP Mask — Full Face"},
                "manufacturer": "Philips Respironics",
                "modelNumber": "DreamWear Full Face",
                "patient": {"reference": "Patient/PT004"},
                "note": [{"text": "Size: Large"}],
            },
        ]
        self._store["Device"] = {d["id"]: d for d in devices}
