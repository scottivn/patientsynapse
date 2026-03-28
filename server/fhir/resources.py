"""High-level FHIR resource operations — EMR-agnostic."""

import base64
import logging
from typing import Optional, List
from server.fhir.client import FHIRClient
from server.fhir import models

logger = logging.getLogger(__name__)


class PatientResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_name_dob(
        self, family: str, given: str, birthdate: str = ""
    ) -> List[models.Patient]:
        """Search for patient by name and DOB. Returns match candidates."""
        params = {}
        if family:
            params["family"] = family
        if given:
            params["given"] = given
        if birthdate:
            params["birthdate"] = birthdate
        bundle = await self.client.search("Patient", params)
        return [
            models.Patient(**entry["resource"])
            for entry in bundle.get("entry", [])
            if entry.get("resource", {}).get("resourceType") == "Patient"
        ]

    async def search_by_identifier(self, identifier: str) -> List[models.Patient]:
        bundle = await self.client.search("Patient", {"identifier": identifier})
        return [
            models.Patient(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def get(self, patient_id: str) -> models.Patient:
        data = await self.client.read("Patient", patient_id)
        return models.Patient(**data)

    async def create(self, patient: models.Patient) -> models.Patient:
        data = await self.client.create("Patient", patient.model_dump(exclude_none=True))
        return models.Patient(**data)

    async def update(self, patient: models.Patient) -> models.Patient:
        data = await self.client.update(
            "Patient", patient.id, patient.model_dump(exclude_none=True)
        )
        return models.Patient(**data)


class ConditionResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_patient(self, patient_id: str) -> List[models.Condition]:
        bundle = await self.client.search("Condition", {"patient": patient_id})
        return [
            models.Condition(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def create_problem(
        self, patient_id: str, code: str, system: str, display: str
    ) -> models.Condition:
        condition = models.Condition(
            clinicalStatus=models.CodeableConcept(
                coding=[models.Coding(system="http://terminology.hl7.org/CodeSystem/condition-clinical", code="active")]
            ),
            verificationStatus=models.CodeableConcept(
                coding=[models.Coding(system="http://terminology.hl7.org/CodeSystem/condition-ver-status", code="confirmed")]
            ),
            category=[models.CodeableConcept(
                coding=[models.Coding(system="http://terminology.hl7.org/CodeSystem/condition-category", code="problem-list-item", display="Problem List Item")]
            )],
            code=models.CodeableConcept(
                coding=[models.Coding(system=system, code=code, display=display)]
            ),
            subject=models.Reference(reference=f"Patient/{patient_id}"),
        )
        data = await self.client.create("Condition", condition.model_dump(exclude_none=True))
        return models.Condition(**data)

    async def create_encounter_diagnosis(
        self, patient_id: str, encounter_id: str, code: str, system: str, display: str
    ) -> models.Condition:
        condition = models.Condition(
            clinicalStatus=models.CodeableConcept(
                coding=[models.Coding(system="http://terminology.hl7.org/CodeSystem/condition-clinical", code="active")]
            ),
            category=[models.CodeableConcept(
                coding=[models.Coding(system="http://terminology.hl7.org/CodeSystem/condition-category", code="encounter-diagnosis", display="Encounter Diagnosis")]
            )],
            code=models.CodeableConcept(
                coding=[models.Coding(system=system, code=code, display=display)]
            ),
            subject=models.Reference(reference=f"Patient/{patient_id}"),
            encounter=models.Reference(reference=f"Encounter/{encounter_id}"),
        )
        data = await self.client.create("Condition", condition.model_dump(exclude_none=True))
        return models.Condition(**data)


class CoverageResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_patient(self, patient_id: str) -> List[models.Coverage]:
        bundle = await self.client.search("Coverage", {"patient": patient_id})
        return [
            models.Coverage(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]


class DeviceResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_patient(self, patient_id: str) -> List[models.Device]:
        bundle = await self.client.search("Device", {"patient": patient_id})
        return [
            models.Device(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]


class EncounterResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_patient(self, patient_id: str) -> List[models.Encounter]:
        bundle = await self.client.search("Encounter", {"patient": patient_id})
        return [
            models.Encounter(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def create_telephone_encounter(
        self, patient_id: str, reason: str
    ) -> models.Encounter:
        encounter = {
            "resourceType": "Encounter",
            "status": "finished",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "VR",
                "display": "virtual",
            },
            "type": [{"coding": [{"system": "http://snomed.info/sct", "code": "185317003", "display": "Telephone encounter"}]}],
            "subject": {"reference": f"Patient/{patient_id}"},
            "reasonCode": [{"text": reason}],
        }
        data = await self.client.create("Encounter", encounter)
        return models.Encounter(**data)


class DocumentReferenceResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_patient(self, patient_id: str) -> List[models.DocumentReference]:
        bundle = await self.client.search("DocumentReference", {"patient": patient_id})
        return [
            models.DocumentReference(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def attach_pdf(
        self, patient_id: str, pdf_bytes: bytes, description: str
    ) -> models.DocumentReference:
        doc = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [{"system": "http://loinc.org", "code": "57133-1", "display": "Referral note"}]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "description": description,
            "content": [{
                "attachment": {
                    "contentType": "application/pdf",
                    "data": base64.b64encode(pdf_bytes).decode("utf-8"),
                    "title": description,
                }
            }],
        }
        data = await self.client.create("DocumentReference", doc)
        return models.DocumentReference(**data)


class ServiceRequestResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_patient(self, patient_id: str) -> List[models.ServiceRequest]:
        bundle = await self.client.search("ServiceRequest", {"patient": patient_id})
        return [
            models.ServiceRequest(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def create_referral(
        self,
        patient_id: str,
        referring_provider: str,
        reason: str,
        priority: str = "routine",
    ) -> models.ServiceRequest:
        sr = {
            "resourceType": "ServiceRequest",
            "status": "active",
            "intent": "order",
            "category": [{"coding": [{"system": "http://snomed.info/sct", "code": "3457005", "display": "Patient referral"}]}],
            "subject": {"reference": f"Patient/{patient_id}"},
            "requester": {"display": referring_provider},
            "priority": priority,
            "reasonCode": [{"text": reason}],
        }
        data = await self.client.create("ServiceRequest", sr)
        return models.ServiceRequest(**data)


class PractitionerResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_name(self, name: str) -> List[models.Practitioner]:
        bundle = await self.client.search("Practitioner", {"name": name})
        return [
            models.Practitioner(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def get(self, practitioner_id: str) -> models.Practitioner:
        data = await self.client.read("Practitioner", practitioner_id)
        return models.Practitioner(**data)


class PractitionerRoleResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_specialty(self, specialty: str) -> List[models.PractitionerRole]:
        bundle = await self.client.search("PractitionerRole", {"specialty": specialty})
        return [
            models.PractitionerRole(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def search_by_practitioner(self, practitioner_id: str) -> List[models.PractitionerRole]:
        bundle = await self.client.search("PractitionerRole", {"practitioner": practitioner_id})
        return [
            models.PractitionerRole(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]


class LocationResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_all(self) -> List[models.Location]:
        bundle = await self.client.search("Location", {})
        return [
            models.Location(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def get(self, location_id: str) -> models.Location:
        data = await self.client.read("Location", location_id)
        return models.Location(**data)


class OrganizationResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_name(self, name: str) -> List[models.Organization]:
        bundle = await self.client.search("Organization", {"name": name})
        return [
            models.Organization(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]

    async def search_payors(self) -> List[models.Organization]:
        bundle = await self.client.search("Organization", {"type": "pay"})
        return [
            models.Organization(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]


class ProcedureResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def search_by_patient(self, patient_id: str) -> List[models.Procedure]:
        bundle = await self.client.search("Procedure", {"patient": patient_id})
        return [
            models.Procedure(**entry["resource"])
            for entry in bundle.get("entry", [])
        ]


class TaskResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def create_review_task(
        self, patient_id: str, description: str, owner: Optional[str] = None
    ) -> models.Task:
        task = {
            "resourceType": "Task",
            "status": "requested",
            "intent": "order",
            "code": {"coding": [{"system": "http://hl7.org/fhir/CodeSystem/task-code", "code": "review"}]},
            "description": description,
            "for": {"reference": f"Patient/{patient_id}"},
        }
        if owner:
            task["owner"] = {"display": owner}
        data = await self.client.create("Task", task)
        return models.Task(**data)


class CommunicationResource:
    def __init__(self, client: FHIRClient):
        self.client = client

    async def send_notification(
        self, patient_id: str, message: str, recipient: Optional[str] = None
    ) -> models.Communication:
        comm = {
            "resourceType": "Communication",
            "status": "completed",
            "subject": {"reference": f"Patient/{patient_id}"},
            "payload": [{"contentString": message}],
        }
        if recipient:
            comm["recipient"] = [{"display": recipient}]
        data = await self.client.create("Communication", comm)
        return models.Communication(**data)
