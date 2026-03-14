"""Pydantic models for FHIR R4 resources used by PatientSynapse."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


# -- Common FHIR types --

class Coding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None

class CodeableConcept(BaseModel):
    coding: List[Coding] = []
    text: Optional[str] = None

class Reference(BaseModel):
    reference: Optional[str] = None
    display: Optional[str] = None

class HumanName(BaseModel):
    use: Optional[str] = None
    family: Optional[str] = None
    given: List[str] = []
    prefix: List[str] = []
    suffix: List[str] = []

    @property
    def full_name(self) -> str:
        parts = self.given + ([self.family] if self.family else [])
        return " ".join(parts)

class Address(BaseModel):
    use: Optional[str] = None
    line: List[str] = []
    city: Optional[str] = None
    state: Optional[str] = None
    postalCode: Optional[str] = None
    country: Optional[str] = None

class ContactPoint(BaseModel):
    system: Optional[str] = None  # phone, email, fax
    value: Optional[str] = None
    use: Optional[str] = None  # home, work, mobile

class Period(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None

class Identifier(BaseModel):
    system: Optional[str] = None
    value: Optional[str] = None
    use: Optional[str] = None


# -- FHIR Resources --

class Patient(BaseModel):
    resourceType: str = "Patient"
    id: Optional[str] = None
    identifier: List[Identifier] = []
    name: List[HumanName] = []
    birthDate: Optional[str] = None
    gender: Optional[str] = None
    address: List[Address] = []
    telecom: List[ContactPoint] = []

    @property
    def primary_name(self) -> Optional[HumanName]:
        return self.name[0] if self.name else None


class Condition(BaseModel):
    resourceType: str = "Condition"
    id: Optional[str] = None
    clinicalStatus: Optional[CodeableConcept] = None
    verificationStatus: Optional[CodeableConcept] = None
    category: List[CodeableConcept] = []
    code: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    onsetDateTime: Optional[str] = None
    recordedDate: Optional[str] = None


class Coverage(BaseModel):
    resourceType: str = "Coverage"
    id: Optional[str] = None
    status: Optional[str] = None
    type: Optional[CodeableConcept] = None
    subscriber: Optional[Reference] = None
    beneficiary: Optional[Reference] = None
    payor: List[Reference] = []
    class_: List[dict] = Field(default=[], alias="class")
    period: Optional[Period] = None


class Encounter(BaseModel):
    resourceType: str = "Encounter"
    id: Optional[str] = None
    status: Optional[str] = None
    class_: Optional[Coding] = Field(default=None, alias="class")
    type: List[CodeableConcept] = []
    subject: Optional[Reference] = None
    participant: List[dict] = []
    period: Optional[Period] = None
    reasonCode: List[CodeableConcept] = []
    diagnosis: List[dict] = []


class DocumentReference(BaseModel):
    resourceType: str = "DocumentReference"
    id: Optional[str] = None
    status: Optional[str] = "current"
    type: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    date: Optional[str] = None
    description: Optional[str] = None
    content: List[dict] = []


class ServiceRequest(BaseModel):
    resourceType: str = "ServiceRequest"
    id: Optional[str] = None
    status: Optional[str] = "active"
    intent: Optional[str] = "order"
    category: List[CodeableConcept] = []
    code: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    requester: Optional[Reference] = None
    performer: List[Reference] = []
    reasonCode: List[CodeableConcept] = []
    priority: Optional[str] = None
    note: List[dict] = []


class Practitioner(BaseModel):
    resourceType: str = "Practitioner"
    id: Optional[str] = None
    identifier: List[Identifier] = []
    name: List[HumanName] = []
    telecom: List[ContactPoint] = []
    qualification: List[dict] = []


class PractitionerRole(BaseModel):
    resourceType: str = "PractitionerRole"
    id: Optional[str] = None
    practitioner: Optional[Reference] = None
    organization: Optional[Reference] = None
    code: List[CodeableConcept] = []
    specialty: List[CodeableConcept] = []
    location: List[Reference] = []


class Location(BaseModel):
    resourceType: str = "Location"
    id: Optional[str] = None
    name: Optional[str] = None
    type: List[CodeableConcept] = []
    telecom: List[ContactPoint] = []
    address: Optional[Address] = None


class Organization(BaseModel):
    resourceType: str = "Organization"
    id: Optional[str] = None
    identifier: List[Identifier] = []
    name: Optional[str] = None
    type: List[CodeableConcept] = []
    telecom: List[ContactPoint] = []
    address: List[Address] = []


class Procedure(BaseModel):
    resourceType: str = "Procedure"
    id: Optional[str] = None
    status: Optional[str] = None
    code: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    performedDateTime: Optional[str] = None
    performer: List[dict] = []


class Task(BaseModel):
    resourceType: str = "Task"
    id: Optional[str] = None
    status: Optional[str] = "requested"
    intent: Optional[str] = "order"
    code: Optional[CodeableConcept] = None
    description: Optional[str] = None
    for_: Optional[Reference] = Field(default=None, alias="for")
    requester: Optional[Reference] = None
    owner: Optional[Reference] = None
    note: List[dict] = []


class Communication(BaseModel):
    resourceType: str = "Communication"
    id: Optional[str] = None
    status: Optional[str] = "completed"
    category: List[CodeableConcept] = []
    subject: Optional[Reference] = None
    sender: Optional[Reference] = None
    recipient: List[Reference] = []
    payload: List[dict] = []
    sent: Optional[str] = None


# -- Bundle for search results --

class BundleEntry(BaseModel):
    resource: Optional[dict] = None
    fullUrl: Optional[str] = None

class Bundle(BaseModel):
    resourceType: str = "Bundle"
    type: Optional[str] = None
    total: Optional[int] = None
    entry: List[BundleEntry] = []
    link: List[dict] = []
