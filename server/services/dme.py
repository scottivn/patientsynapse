"""DME (Durable Medical Equipment) order service.

Handles intake, insurance verification, compliance checking,
and auto-replace scheduling for the practice's internal DME operation.
"""

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict

from server.db import db_execute, db_fetch_one, db_fetch_all

logger = logging.getLogger(__name__)


class DMEOrderStatus(str, Enum):
    PENDING = "pending"              # Just created, needs eligibility checks
    VERIFYING = "verifying"          # Insurance/compliance check in progress
    VERIFIED = "verified"            # Eligible — ready for staff review
    AWAITING_APPROVAL = "awaiting_approval"  # Staff reviewed, waiting on internal sign-off
    APPROVED = "approved"            # Approved — ready to send to patient
    PATIENT_CONTACTED = "patient_contacted"  # Confirmation link sent to patient
    PATIENT_CONFIRMED = "patient_confirmed"  # Patient confirmed address + fulfillment
    ORDERING = "ordering"            # Order placed with vendor
    SHIPPED = "shipped"              # Vendor shipped / ready for pickup
    FULFILLED = "fulfilled"          # Patient received equipment
    REJECTED = "rejected"            # Denied (insurance, compliance, or clinical)
    ON_HOLD = "on_hold"              # Paused — waiting on info, patient unreachable, etc.
    CANCELLED = "cancelled"          # Patient declined or order cancelled


class FulfillmentMethod(str, Enum):
    PICKUP = "pickup"
    SHIP = "ship"
    NOT_SELECTED = "not_selected"


class OrderOrigin(str, Enum):
    AUTO_REFILL = "auto_refill"      # Triggered by auto-replace schedule
    PRESCRIPTION = "prescription"    # New Rx from physician
    STAFF_INITIATED = "staff_initiated"  # Staff created manually
    PATIENT_REQUEST = "patient_request"  # Patient called/messaged asking for supplies


class AutoReplaceFrequency(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    BIANNUAL = "biannual"
    ANNUAL = "annual"


class ComplianceStatus(str, Enum):
    UNKNOWN = "unknown"
    CHECKING = "checking"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"


class EncounterType(str, Enum):
    OFFICE_VISIT = "office_visit"              # Routine follow-up
    TELEHEALTH = "telehealth"                  # Virtual visit
    SLEEP_STUDY = "sleep_study"                # PSG / home sleep test
    CPAP_TITRATION = "cpap_titration"          # In-lab titration
    ANNUAL_WELLNESS = "annual_wellness"        # Annual wellness visit
    INITIAL_CONSULTATION = "initial_consultation"
    URGENT_VISIT = "urgent_visit"


ENCOUNTER_TYPE_LABELS = {
    "office_visit": "Office Visit",
    "telehealth": "Telehealth",
    "sleep_study": "Sleep Study (PSG)",
    "cpap_titration": "CPAP Titration",
    "annual_wellness": "Annual Wellness",
    "initial_consultation": "Initial Consultation",
    "urgent_visit": "Urgent Visit",
}

# Max days since last encounter before it's considered expired (payer requirement)
ENCOUNTER_VALIDITY_DAYS = 365


# Sleep medicine DME equipment categories
EQUIPMENT_CATEGORIES = [
    "CPAP Machine",
    "BiPAP / ASV Machine",
    "CPAP Mask — Full Face",
    "CPAP Mask — Nasal",
    "CPAP Mask — Nasal Pillow",
    "Mask Cushion / Pillow Replacement",
    "Headgear",
    "Heated Tubing",
    "Standard Tubing",
    "Water Chamber / Humidifier",
    "Filters — Disposable",
    "Filters — Non-Disposable",
    "Chinstrap",
    "CPAP Travel Case",
    "CPAP Cleaning Supplies",
    "Oral Appliance (MAD)",
    "Positional Therapy Device",
    "Other Sleep DME",
]

# Map categories to their HCPCS codes for automatic pricing lookups
CATEGORY_HCPCS_MAP = {
    "CPAP Machine": ["E0601"],
    "BiPAP / ASV Machine": ["E0470"],
    "CPAP Mask — Full Face": ["A7030"],
    "CPAP Mask — Nasal": ["A7034"],
    "CPAP Mask — Nasal Pillow": ["A7033"],
    "Mask Cushion / Pillow Replacement": ["A7031", "A7032"],
    "Headgear": ["A7035"],
    "Heated Tubing": ["A4604"],
    "Standard Tubing": ["A4604"],
    "Water Chamber / Humidifier": ["A7046"],
    "Filters — Disposable": ["A7038"],
    "Filters — Non-Disposable": ["A7039"],
}

# All sleep DME categories benefit from compliance checks via AirPM
COMPLIANCE_REQUIRED_CATEGORIES = [
    "CPAP Machine",
    "BiPAP / ASV Machine",
    "CPAP Mask — Full Face",
    "CPAP Mask — Nasal",
    "CPAP Mask — Nasal Pillow",
    "Mask Cushion / Pillow Replacement",
    "Headgear",
    "Heated Tubing",
    "Standard Tubing",
    "Water Chamber / Humidifier",
    "Filters — Disposable",
    "Filters — Non-Disposable",
]

# Common supply bundles that get ordered together
VENDOR_OPTIONS = ["In-House", "PPM", "VGM"]

SUPPLY_BUNDLES = {
    "Full Resupply (Full Face)": [
        "CPAP Mask — Full Face", "Mask Cushion / Pillow Replacement",
        "Headgear", "Heated Tubing", "Water Chamber / Humidifier",
        "Filters — Disposable", "Filters — Non-Disposable",
    ],
    "Full Resupply (Nasal)": [
        "CPAP Mask — Nasal", "Mask Cushion / Pillow Replacement",
        "Headgear", "Heated Tubing", "Water Chamber / Humidifier",
        "Filters — Disposable", "Filters — Non-Disposable",
    ],
    "Full Resupply (Nasal Pillow)": [
        "CPAP Mask — Nasal Pillow", "Mask Cushion / Pillow Replacement",
        "Headgear", "Heated Tubing", "Water Chamber / Humidifier",
        "Filters — Disposable", "Filters — Non-Disposable",
    ],
    "Cushion + Filters Only": [
        "Mask Cushion / Pillow Replacement",
        "Filters — Disposable", "Filters — Non-Disposable",
    ],
    "Tubing + Chamber": [
        "Heated Tubing", "Water Chamber / Humidifier",
    ],
}

# Normalized lookup: lowercase key → bundle name for fuzzy matching
_BUNDLE_LOOKUP = {k.lower(): k for k in SUPPLY_BUNDLES}


def _resolve_bundle(description: str, category: str = "") -> List[str]:
    """Resolve bundle items from description or category, using fuzzy matching.

    Handles cases where description is a long string like
    "Full resupply (nasal) — mask, cushion, headgear, tubing, chamber, filters"
    that should still match the "Full Resupply (Nasal)" bundle.
    """
    # Exact match
    if description in SUPPLY_BUNDLES:
        return list(SUPPLY_BUNDLES[description])

    # Case-insensitive exact match
    desc_lower = description.lower()
    if desc_lower in _BUNDLE_LOOKUP:
        return list(SUPPLY_BUNDLES[_BUNDLE_LOOKUP[desc_lower]])

    # Substring match — check if any bundle key appears at the start of the description
    for key_lower, key_original in _BUNDLE_LOOKUP.items():
        if desc_lower.startswith(key_lower):
            return list(SUPPLY_BUNDLES[key_original])

    # Reverse — check if description is contained within a bundle key
    for key_lower, key_original in _BUNDLE_LOOKUP.items():
        if key_lower in desc_lower:
            return list(SUPPLY_BUNDLES[key_original])

    # Category-based fallback: match category to a bundle containing that item
    if category:
        cat_lower = category.lower()
        for key, items in SUPPLY_BUNDLES.items():
            if any(cat_lower == item.lower() for item in items):
                return list(items)

    return []


@dataclass
class DMEDocument:
    """Attached document for insurance approval."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    filename: str = ""
    document_type: str = ""  # e.g. "rx", "progress_notes", "compliance_report", "cmnform"
    uploaded_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DMEOrder:
    # Patient info
    patient_first_name: str
    patient_last_name: str
    patient_dob: str
    patient_phone: str
    patient_address: str
    patient_city: str
    patient_state: str
    patient_zip: str
    patient_email: str = ""
    patient_id: str = ""  # EMR patient ID (for FHIR lookups)

    # Insurance
    insurance_payer: str = ""
    insurance_member_id: str = ""
    insurance_group: str = ""

    # Equipment
    equipment_category: str = ""
    equipment_description: str = ""
    quantity: int = 1
    bundle_items: List[str] = field(default_factory=list)      # individual items in a bundle order
    selected_items: List[str] = field(default_factory=list)    # items patient chose to keep

    # Clinical
    diagnosis_code: str = ""
    diagnosis_description: str = ""
    referring_physician: str = ""
    referring_npi: str = ""
    clinical_notes: str = ""

    # Last provider encounter — payers require a face-to-face within 12 months
    last_encounter_date: Optional[str] = None      # YYYY-MM-DD
    last_encounter_type: Optional[str] = None       # EncounterType value
    last_encounter_provider: Optional[str] = None   # provider name
    last_encounter_provider_npi: Optional[str] = None

    # Order origin & context
    origin: str = OrderOrigin.STAFF_INITIATED
    parent_order_id: Optional[str] = None  # links auto-refill to original fulfilled order

    # Auto-replace
    auto_replace: bool = False
    auto_replace_frequency: Optional[str] = None  # AutoReplaceFrequency value
    next_replace_date: Optional[str] = None

    # Compliance (AirPM integration)
    compliance_status: str = ComplianceStatus.UNKNOWN
    compliance_avg_hours: Optional[float] = None  # avg nightly usage hours
    compliance_days_met: Optional[int] = None  # days meeting >=4hr threshold
    compliance_total_days: Optional[int] = None  # total days in period
    compliance_last_checked: Optional[str] = None

    # Documents for insurance approval
    documents: List[DMEDocument] = field(default_factory=list)

    # Pricing (from allowable rates)
    hcpcs_codes: List[str] = field(default_factory=list)
    expected_reimbursement: Optional[float] = None
    supply_months: int = 6
    pricing_details: List[dict] = field(default_factory=list)

    # Patient confirmation flow
    confirmation_token: Optional[str] = None       # short-lived token for patient link
    confirmation_token_expires: Optional[str] = None
    confirmation_sent_at: Optional[str] = None     # when link was sent
    confirmation_sent_via: Optional[str] = None    # "sms", "email", or "both"
    confirmation_responded_at: Optional[str] = None
    patient_confirmed_address: bool = False        # patient verified their address
    patient_notes: str = ""                        # anything patient typed in response
    patient_rejected: bool = False                 # patient flagged something wrong
    patient_rejection_reason: str = ""             # what the patient said was wrong
    patient_callback_requested: bool = False       # patient wants a call back

    # Fulfillment
    fulfillment_method: str = FulfillmentMethod.NOT_SELECTED
    shipping_fee: Optional[float] = None
    shipping_tracking_number: Optional[str] = None
    shipping_carrier: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_order_id: Optional[str] = None
    vendor_ordered_at: Optional[str] = None
    estimated_delivery_date: Optional[str] = None
    pickup_ready_date: Optional[str] = None
    fulfilled_at: Optional[str] = None
    auto_deliver_after: Optional[str] = None       # ISO datetime to auto-fulfill

    # Staff workflow
    assigned_to: Optional[str] = None              # staff member working this order
    staff_notes: str = ""                          # internal notes (not visible to patient)
    hold_reason: str = ""                          # why order is on hold

    # Internal
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    status: DMEOrderStatus = DMEOrderStatus.PENDING
    insurance_verified: Optional[bool] = None
    insurance_notes: str = ""
    rejection_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def patient_name(self) -> str:
        return f"{self.patient_first_name} {self.patient_last_name}"

    @property
    def requires_compliance_check(self) -> bool:
        return self.equipment_category in COMPLIANCE_REQUIRED_CATEGORIES

    @property
    def is_actionable(self) -> bool:
        """Can staff take the next step on this order right now?"""
        return self.status in (
            DMEOrderStatus.PENDING,
            DMEOrderStatus.VERIFIED,
            DMEOrderStatus.PATIENT_CONFIRMED,
        )

    @property
    def awaiting_patient(self) -> bool:
        return self.status == DMEOrderStatus.PATIENT_CONTACTED

    @property
    def patient_display_status(self) -> str:
        """Human-readable status for the patient-facing confirmation page."""
        status_labels = {
            DMEOrderStatus.PENDING: "Processing your order",
            DMEOrderStatus.VERIFYING: "Checking insurance eligibility",
            DMEOrderStatus.VERIFIED: "Insurance verified — preparing your order",
            DMEOrderStatus.AWAITING_APPROVAL: "Under review",
            DMEOrderStatus.APPROVED: "Approved — we'll reach out shortly",
            DMEOrderStatus.PATIENT_CONTACTED: "Action needed — please confirm your details",
            DMEOrderStatus.PATIENT_CONFIRMED: "Confirmed — preparing your supplies",
            DMEOrderStatus.ORDERING: "In progress — being fulfilled",
            DMEOrderStatus.SHIPPED: "Shipped" if self.fulfillment_method == FulfillmentMethod.SHIP else "Ready for pickup",
            DMEOrderStatus.FULFILLED: "Delivered",
            DMEOrderStatus.REJECTED: "Unable to process — please contact our office",
            DMEOrderStatus.ON_HOLD: "On hold — we may need additional information",
            DMEOrderStatus.CANCELLED: "Cancelled",
        }
        return status_labels.get(self.status, self.status.value)

    @property
    def encounter_current(self) -> bool:
        """True if the patient has a provider encounter within the last 365 days."""
        if not self.last_encounter_date:
            return False
        try:
            enc_date = date.fromisoformat(self.last_encounter_date)
            return (date.today() - enc_date).days <= ENCOUNTER_VALIDITY_DAYS
        except (ValueError, TypeError):
            return False

    @property
    def encounter_days_ago(self) -> Optional[int]:
        """Days since last encounter, or None if no encounter on file."""
        if not self.last_encounter_date:
            return None
        try:
            return (date.today() - date.fromisoformat(self.last_encounter_date)).days
        except (ValueError, TypeError):
            return None

    @property
    def encounter_expires_in_days(self) -> Optional[int]:
        """Days until the encounter expires (negative = already expired)."""
        if not self.last_encounter_date:
            return None
        try:
            enc_date = date.fromisoformat(self.last_encounter_date)
            return ENCOUNTER_VALIDITY_DAYS - (date.today() - enc_date).days
        except (ValueError, TypeError):
            return None


# ── DB serialization ────────────────────────────────────────

def _row_to_order(row: dict) -> DMEOrder:
    """Convert a DB row dict to a DMEOrder dataclass."""
    docs_raw = row.get("documents", "[]")
    docs = []
    try:
        for d in json.loads(docs_raw or "[]"):
            docs.append(DMEDocument(**d))
    except (json.JSONDecodeError, TypeError):
        pass

    hcpcs = []
    try:
        hcpcs = json.loads(row.get("hcpcs_codes", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    pricing = []
    try:
        pricing = json.loads(row.get("pricing_details", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    bundle_items = []
    try:
        bundle_items = json.loads(row.get("bundle_items", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    selected_items = []
    try:
        selected_items = json.loads(row.get("selected_items", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    ins_verified = row.get("insurance_verified")
    if ins_verified is not None:
        ins_verified = bool(ins_verified)

    return DMEOrder(
        id=row["id"],
        status=DMEOrderStatus(row["status"]),
        patient_first_name=row["patient_first_name"],
        patient_last_name=row["patient_last_name"],
        patient_dob=row.get("patient_dob", ""),
        patient_phone=row.get("patient_phone", ""),
        patient_email=row.get("patient_email", ""),
        patient_address=row.get("patient_address", ""),
        patient_city=row.get("patient_city", ""),
        patient_state=row.get("patient_state", ""),
        patient_zip=row.get("patient_zip", ""),
        patient_id=row.get("patient_id", ""),
        insurance_payer=row.get("insurance_payer", ""),
        insurance_member_id=row.get("insurance_member_id", ""),
        insurance_group=row.get("insurance_group", ""),
        equipment_category=row.get("equipment_category", ""),
        equipment_description=row.get("equipment_description", ""),
        quantity=row.get("quantity", 1),
        bundle_items=bundle_items,
        selected_items=selected_items,
        diagnosis_code=row.get("diagnosis_code", ""),
        diagnosis_description=row.get("diagnosis_description", ""),
        referring_physician=row.get("referring_physician", ""),
        referring_npi=row.get("referring_npi", ""),
        clinical_notes=row.get("clinical_notes", ""),
        last_encounter_date=row.get("last_encounter_date"),
        last_encounter_type=row.get("last_encounter_type"),
        last_encounter_provider=row.get("last_encounter_provider"),
        last_encounter_provider_npi=row.get("last_encounter_provider_npi"),
        origin=row.get("origin", OrderOrigin.STAFF_INITIATED),
        parent_order_id=row.get("parent_order_id"),
        auto_replace=bool(row.get("auto_replace", 0)),
        auto_replace_frequency=row.get("auto_replace_frequency"),
        next_replace_date=row.get("next_replace_date"),
        compliance_status=row.get("compliance_status", ComplianceStatus.UNKNOWN),
        compliance_avg_hours=row.get("compliance_avg_hours"),
        compliance_days_met=row.get("compliance_days_met"),
        compliance_total_days=row.get("compliance_total_days"),
        compliance_last_checked=row.get("compliance_last_checked"),
        documents=docs,
        hcpcs_codes=hcpcs,
        expected_reimbursement=row.get("expected_reimbursement"),
        supply_months=row.get("supply_months", 6),
        pricing_details=pricing,
        confirmation_token=row.get("confirmation_token"),
        confirmation_token_expires=row.get("confirmation_token_expires"),
        confirmation_sent_at=row.get("confirmation_sent_at"),
        confirmation_sent_via=row.get("confirmation_sent_via"),
        confirmation_responded_at=row.get("confirmation_responded_at"),
        patient_confirmed_address=bool(row.get("patient_confirmed_address", 0)),
        patient_notes=row.get("patient_notes", ""),
        patient_rejected=bool(row.get("patient_rejected", 0)),
        patient_rejection_reason=row.get("patient_rejection_reason", ""),
        patient_callback_requested=bool(row.get("patient_callback_requested", 0)),
        fulfillment_method=row.get("fulfillment_method", FulfillmentMethod.NOT_SELECTED),
        shipping_fee=row.get("shipping_fee"),
        shipping_tracking_number=row.get("shipping_tracking_number"),
        shipping_carrier=row.get("shipping_carrier"),
        vendor_name=row.get("vendor_name"),
        vendor_order_id=row.get("vendor_order_id"),
        vendor_ordered_at=row.get("vendor_ordered_at"),
        estimated_delivery_date=row.get("estimated_delivery_date"),
        pickup_ready_date=row.get("pickup_ready_date"),
        fulfilled_at=row.get("fulfilled_at"),
        auto_deliver_after=row.get("auto_deliver_after"),
        assigned_to=row.get("assigned_to"),
        staff_notes=row.get("staff_notes", ""),
        hold_reason=row.get("hold_reason", ""),
        insurance_verified=ins_verified,
        insurance_notes=row.get("insurance_notes", ""),
        rejection_reason=row.get("rejection_reason", ""),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _save_order(order: DMEOrder) -> None:
    """Upsert a DME order to the database."""
    docs_json = json.dumps([asdict(d) for d in order.documents])
    hcpcs_json = json.dumps(order.hcpcs_codes)
    pricing_json = json.dumps(order.pricing_details)
    bundle_json = json.dumps(order.bundle_items)
    selected_json = json.dumps(order.selected_items)
    ins_verified = None if order.insurance_verified is None else int(order.insurance_verified)

    await db_execute(
        """INSERT INTO dme_orders (
               id, status, patient_first_name, patient_last_name, patient_dob,
               patient_phone, patient_email, patient_address, patient_city,
               patient_state, patient_zip, patient_id,
               insurance_payer, insurance_member_id, insurance_group,
               equipment_category, equipment_description, quantity,
               bundle_items, selected_items,
               diagnosis_code, diagnosis_description, referring_physician,
               referring_npi, clinical_notes,
               last_encounter_date, last_encounter_type, last_encounter_provider,
               last_encounter_provider_npi,
               origin, parent_order_id,
               auto_replace, auto_replace_frequency, next_replace_date,
               compliance_status, compliance_avg_hours, compliance_days_met,
               compliance_total_days, compliance_last_checked,
               documents, hcpcs_codes, expected_reimbursement, supply_months,
               pricing_details,
               confirmation_token, confirmation_token_expires, confirmation_sent_at,
               confirmation_sent_via, confirmation_responded_at,
               patient_confirmed_address, patient_notes,
               patient_rejected, patient_rejection_reason, patient_callback_requested,
               fulfillment_method, shipping_fee, shipping_tracking_number,
               shipping_carrier, vendor_name, vendor_order_id, vendor_ordered_at,
               estimated_delivery_date, pickup_ready_date, fulfilled_at,
               auto_deliver_after,
               assigned_to, staff_notes, hold_reason,
               insurance_verified, insurance_notes, rejection_reason,
               created_at, updated_at
           ) VALUES (
               ?,?,?,?,?, ?,?,?,?,?, ?,?, ?,?,?, ?,?,?, ?,?,
               ?,?,?,?,?, ?,?,?,?, ?,?, ?,?,?, ?,?,?,?,?, ?,?,?,?, ?,
               ?,?,?,?,?, ?,?, ?,?,?, ?,?,?,?,?,?,?, ?,?,?, ?,
               ?,?,?, ?,?,?, ?,?
           )
           ON CONFLICT(id) DO UPDATE SET
               status=excluded.status,
               patient_first_name=excluded.patient_first_name,
               patient_last_name=excluded.patient_last_name,
               patient_dob=excluded.patient_dob,
               patient_phone=excluded.patient_phone,
               patient_email=excluded.patient_email,
               patient_address=excluded.patient_address,
               patient_city=excluded.patient_city,
               patient_state=excluded.patient_state,
               patient_zip=excluded.patient_zip,
               patient_id=excluded.patient_id,
               insurance_payer=excluded.insurance_payer,
               insurance_member_id=excluded.insurance_member_id,
               insurance_group=excluded.insurance_group,
               equipment_category=excluded.equipment_category,
               equipment_description=excluded.equipment_description,
               quantity=excluded.quantity,
               bundle_items=excluded.bundle_items,
               selected_items=excluded.selected_items,
               diagnosis_code=excluded.diagnosis_code,
               diagnosis_description=excluded.diagnosis_description,
               referring_physician=excluded.referring_physician,
               referring_npi=excluded.referring_npi,
               clinical_notes=excluded.clinical_notes,
               last_encounter_date=excluded.last_encounter_date,
               last_encounter_type=excluded.last_encounter_type,
               last_encounter_provider=excluded.last_encounter_provider,
               last_encounter_provider_npi=excluded.last_encounter_provider_npi,
               origin=excluded.origin,
               parent_order_id=excluded.parent_order_id,
               auto_replace=excluded.auto_replace,
               auto_replace_frequency=excluded.auto_replace_frequency,
               next_replace_date=excluded.next_replace_date,
               compliance_status=excluded.compliance_status,
               compliance_avg_hours=excluded.compliance_avg_hours,
               compliance_days_met=excluded.compliance_days_met,
               compliance_total_days=excluded.compliance_total_days,
               compliance_last_checked=excluded.compliance_last_checked,
               documents=excluded.documents,
               hcpcs_codes=excluded.hcpcs_codes,
               expected_reimbursement=excluded.expected_reimbursement,
               supply_months=excluded.supply_months,
               pricing_details=excluded.pricing_details,
               confirmation_token=excluded.confirmation_token,
               confirmation_token_expires=excluded.confirmation_token_expires,
               confirmation_sent_at=excluded.confirmation_sent_at,
               confirmation_sent_via=excluded.confirmation_sent_via,
               confirmation_responded_at=excluded.confirmation_responded_at,
               patient_confirmed_address=excluded.patient_confirmed_address,
               patient_notes=excluded.patient_notes,
               patient_rejected=excluded.patient_rejected,
               patient_rejection_reason=excluded.patient_rejection_reason,
               patient_callback_requested=excluded.patient_callback_requested,
               fulfillment_method=excluded.fulfillment_method,
               shipping_fee=excluded.shipping_fee,
               shipping_tracking_number=excluded.shipping_tracking_number,
               shipping_carrier=excluded.shipping_carrier,
               vendor_name=excluded.vendor_name,
               vendor_order_id=excluded.vendor_order_id,
               vendor_ordered_at=excluded.vendor_ordered_at,
               estimated_delivery_date=excluded.estimated_delivery_date,
               pickup_ready_date=excluded.pickup_ready_date,
               fulfilled_at=excluded.fulfilled_at,
               auto_deliver_after=excluded.auto_deliver_after,
               assigned_to=excluded.assigned_to,
               staff_notes=excluded.staff_notes,
               hold_reason=excluded.hold_reason,
               insurance_verified=excluded.insurance_verified,
               insurance_notes=excluded.insurance_notes,
               rejection_reason=excluded.rejection_reason,
               updated_at=excluded.updated_at""",
        (order.id, order.status.value, order.patient_first_name, order.patient_last_name,
         order.patient_dob, order.patient_phone, order.patient_email,
         order.patient_address, order.patient_city, order.patient_state,
         order.patient_zip, order.patient_id,
         order.insurance_payer, order.insurance_member_id, order.insurance_group,
         order.equipment_category, order.equipment_description, order.quantity,
         bundle_json, selected_json,
         order.diagnosis_code, order.diagnosis_description, order.referring_physician,
         order.referring_npi, order.clinical_notes,
         order.last_encounter_date, order.last_encounter_type,
         order.last_encounter_provider, order.last_encounter_provider_npi,
         order.origin, order.parent_order_id,
         int(order.auto_replace), order.auto_replace_frequency, order.next_replace_date,
         order.compliance_status, order.compliance_avg_hours, order.compliance_days_met,
         order.compliance_total_days, order.compliance_last_checked,
         docs_json, hcpcs_json, order.expected_reimbursement, order.supply_months,
         pricing_json,
         order.confirmation_token, order.confirmation_token_expires,
         order.confirmation_sent_at, order.confirmation_sent_via,
         order.confirmation_responded_at,
         int(order.patient_confirmed_address), order.patient_notes,
         int(order.patient_rejected), order.patient_rejection_reason,
         int(order.patient_callback_requested),
         order.fulfillment_method, order.shipping_fee, order.shipping_tracking_number,
         order.shipping_carrier, order.vendor_name, order.vendor_order_id,
         order.vendor_ordered_at, order.estimated_delivery_date,
         order.pickup_ready_date, order.fulfilled_at,
         order.auto_deliver_after,
         order.assigned_to, order.staff_notes, order.hold_reason,
         ins_verified, order.insurance_notes, order.rejection_reason,
         order.created_at, order.updated_at),
    )


class DMEService:
    """Manages DME orders from intake through fulfillment.

    Workflow:
    1. Order created internally (auto-refill, Rx, staff-initiated)
    2. System auto-checks: insurance, compliance, allowable rates
    3. Staff reviews pre-checked card, approves
    4. System sends patient a tokenized confirmation link (SMS/email)
    5. Patient confirms address + chooses pickup/ship
    6. Staff orders from vendor
    7. Fulfillment tracked through delivery
    """

    CONFIRMATION_TOKEN_EXPIRY_HOURS = 48

    def __init__(self, fhir_client=None):
        self._fhir_client = fhir_client

    def set_fhir_client(self, fhir_client):
        self._fhir_client = fhir_client

    # ── Patient search (admin) ───────────────────────────────────

    async def search_patients(self, family: str = "", given: str = "", dob: str = "") -> List[dict]:
        """Search EMR for patients by name/DOB, returning demographics + insurance + devices."""
        if not self._fhir_client:
            logger.warning("Patient search attempted but FHIR client not connected")
            return []

        from server.fhir.resources import PatientResource, CoverageResource, DeviceResource
        patient_res = PatientResource(self._fhir_client)
        coverage_res = CoverageResource(self._fhir_client)
        device_res = DeviceResource(self._fhir_client)

        patients = await patient_res.search_by_name_dob(family, given, dob)
        results = []
        for p in patients[:20]:  # cap at 20 results
            result = self._patient_to_dict(p)
            # Fetch insurance
            if p.id:
                try:
                    coverages = await coverage_res.search_by_patient(p.id)
                    result["insurance"] = self._coverage_to_dict(coverages)
                except Exception:
                    result["insurance"] = {}
                # Fetch devices
                try:
                    devices = await device_res.search_by_patient(p.id)
                    result["devices"] = [self._device_to_dict(d) for d in devices]
                except Exception:
                    result["devices"] = []
                # Fetch local order history
                result["recent_orders"] = await self.get_patient_order_history(p.id)
            results.append(result)
        return results

    async def search_patients_by_mrn(self, mrn: str) -> List[dict]:
        """Search EMR for patients by MRN/identifier."""
        if not self._fhir_client:
            logger.warning("Patient search attempted but FHIR client not connected")
            return []

        from server.fhir.resources import PatientResource, CoverageResource, DeviceResource
        patient_res = PatientResource(self._fhir_client)
        coverage_res = CoverageResource(self._fhir_client)
        device_res = DeviceResource(self._fhir_client)

        patients = await patient_res.search_by_identifier(mrn)
        results = []
        for p in patients[:20]:
            result = self._patient_to_dict(p)
            if p.id:
                try:
                    coverages = await coverage_res.search_by_patient(p.id)
                    result["insurance"] = self._coverage_to_dict(coverages)
                except Exception:
                    result["insurance"] = {}
                try:
                    devices = await device_res.search_by_patient(p.id)
                    result["devices"] = [self._device_to_dict(d) for d in devices]
                except Exception:
                    result["devices"] = []
                result["recent_orders"] = await self.get_patient_order_history(p.id)
            results.append(result)
        return results

    async def get_patient_order_history(self, patient_id: str) -> List[dict]:
        """Get recent DME orders for a patient from local DB."""
        rows = await db_fetch_all(
            "SELECT * FROM dme_orders WHERE patient_id = ? ORDER BY created_at DESC LIMIT 20",
            (patient_id,),
        )
        orders = [_row_to_order(r) for r in rows]
        return [
            {
                "id": o.id,
                "status": o.status.value if hasattr(o.status, 'value') else o.status,
                "equipment_category": o.equipment_category,
                "equipment_description": o.equipment_description,
                "created_at": o.created_at,
                "fulfilled_at": o.fulfilled_at,
                "auto_replace": o.auto_replace,
                "auto_replace_frequency": o.auto_replace_frequency,
            }
            for o in orders
        ]

    @staticmethod
    def _patient_to_dict(patient) -> dict:
        """Convert FHIR Patient to a flat dict for frontend consumption."""
        name = patient.primary_name
        phone = ""
        email = ""
        for t in patient.telecom:
            if t.system == "phone" and not phone:
                phone = t.value or ""
            if t.system == "email" and not email:
                email = t.value or ""
        addr = patient.address[0] if patient.address else None
        return {
            "patient_id": patient.id or "",
            "first_name": name.given[0] if name and name.given else "",
            "last_name": name.family if name else "",
            "dob": patient.birthDate or "",
            "phone": phone,
            "email": email,
            "address": " ".join(addr.line) if addr else "",
            "city": addr.city or "" if addr else "",
            "state": addr.state or "" if addr else "",
            "zip": addr.postalCode or "" if addr else "",
            "gender": patient.gender or "",
            "insurance": {},
            "devices": [],
            "recent_orders": [],
        }

    @staticmethod
    def _coverage_to_dict(coverages: list) -> dict:
        """Extract insurance info from the first active FHIR Coverage."""
        for cov in coverages:
            if cov.status == "active":
                payer = cov.payor[0].display if cov.payor else ""
                member_id = ""
                group = ""
                # subscriberId may be a direct field or in class_
                raw = cov.model_dump(by_alias=True)
                member_id = raw.get("subscriberId", "")
                grouping = raw.get("grouping", {})
                if grouping:
                    group = grouping.get("group", "")
                return {
                    "payer": payer,
                    "member_id": member_id,
                    "group": group,
                }
        return {}

    @staticmethod
    def _device_to_dict(device) -> dict:
        """Convert FHIR Device to a flat dict."""
        device_type = ""
        if device.type and device.type.text:
            device_type = device.type.text
        elif device.type and device.type.coding:
            device_type = device.type.coding[0].display or ""
        notes = "; ".join(n.text for n in device.note if n.text)
        return {
            "id": device.id or "",
            "type": device_type,
            "manufacturer": device.manufacturer or "",
            "model": device.modelNumber or "",
            "serial_number": device.serialNumber or "",
            "status": device.status or "",
            "notes": notes,
        }

    # ── Order creation ──────────────────────────────────────────

    async def create_order(self, data: dict) -> DMEOrder:
        order = DMEOrder(
            patient_first_name=data["patient_first_name"],
            patient_last_name=data["patient_last_name"],
            patient_dob=data.get("patient_dob", ""),
            patient_phone=data.get("patient_phone", ""),
            patient_email=data.get("patient_email", ""),
            patient_address=data.get("patient_address", ""),
            patient_city=data.get("patient_city", ""),
            patient_state=data.get("patient_state", ""),
            patient_zip=data.get("patient_zip", ""),
            patient_id=data.get("patient_id", ""),
            insurance_payer=data.get("insurance_payer", ""),
            insurance_member_id=data.get("insurance_member_id", ""),
            insurance_group=data.get("insurance_group", ""),
            equipment_category=data.get("equipment_category", ""),
            equipment_description=data.get("equipment_description", ""),
            quantity=int(data.get("quantity", 1)),
            diagnosis_code=data.get("diagnosis_code", ""),
            diagnosis_description=data.get("diagnosis_description", ""),
            referring_physician=data.get("referring_physician", ""),
            referring_npi=data.get("referring_npi", ""),
            clinical_notes=data.get("clinical_notes", ""),
            auto_replace=bool(data.get("auto_replace", False)),
            auto_replace_frequency=data.get("auto_replace_frequency"),
            origin=data.get("origin", OrderOrigin.STAFF_INITIATED),
            parent_order_id=data.get("parent_order_id"),
            hcpcs_codes=data.get("hcpcs_codes", []),
            supply_months=data.get("supply_months", 6),
        )

        # Populate bundle items if the description or category matches a known bundle
        order.bundle_items = _resolve_bundle(order.equipment_description, order.equipment_category)
        if order.bundle_items:
            order.selected_items = list(order.bundle_items)

        if order.auto_replace and order.auto_replace_frequency:
            order.next_replace_date = self._compute_next_date(order.auto_replace_frequency)

        await _save_order(order)
        logger.info(f"DME order {order.id} created (origin={order.origin})")
        return order

    async def list_orders(self, status: Optional[DMEOrderStatus] = None) -> List[DMEOrder]:
        if status:
            rows = await db_fetch_all(
                "SELECT * FROM dme_orders WHERE status = ? ORDER BY created_at DESC",
                (status.value,),
            )
        else:
            rows = await db_fetch_all("SELECT * FROM dme_orders ORDER BY created_at DESC")
        return [_row_to_order(r) for r in rows]

    async def get_order(self, order_id: str) -> Optional[DMEOrder]:
        row = await db_fetch_one("SELECT * FROM dme_orders WHERE id = ?", (order_id,))
        return _row_to_order(row) if row else None

    # ── Eligibility checks (automated) ──────────────────────────

    async def verify_insurance(self, order_id: str) -> DMEOrder:
        """Attempt FHIR Coverage lookup + allowable rate pricing."""
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        order.status = DMEOrderStatus.VERIFYING
        order.updated_at = datetime.now().isoformat()

        if self._fhir_client and order.patient_id:
            try:
                from server.fhir.resources import CoverageResource
                cov_resource = CoverageResource(self._fhir_client)
                coverages = await cov_resource.search_by_patient(order.patient_id)
                active = [c for c in coverages if c.status == "active"]
                if active:
                    order.insurance_verified = True
                    payer = active[0].payor[0].display if active[0].payor else order.insurance_payer
                    order.insurance_notes = f"Active coverage found: {payer}"
                    order.status = DMEOrderStatus.VERIFIED
                else:
                    order.insurance_verified = False
                    order.insurance_notes = "No active coverage found in FHIR"
                    order.status = DMEOrderStatus.PENDING
            except Exception as e:
                logger.warning(f"FHIR coverage lookup failed: {e}")
                order.insurance_verified = None
                order.insurance_notes = "Automatic verification unavailable — manual review required"
                order.status = DMEOrderStatus.PENDING
        else:
            order.insurance_verified = None
            order.insurance_notes = "EMR not connected — manual verification required"
            order.status = DMEOrderStatus.PENDING

        # Look up allowable rates for pricing if payer and HCPCS codes are known
        if order.insurance_payer and order.hcpcs_codes:
            try:
                from server.services.allowable_rates import get_bundle_pricing
                pricing = await get_bundle_pricing(
                    payer=order.insurance_payer,
                    hcpcs_codes=order.hcpcs_codes,
                    supply_months=order.supply_months or 6,
                )
                order.expected_reimbursement = pricing["total"]
                order.pricing_details = pricing["items"]
                if pricing["complete"]:
                    order.insurance_notes += f" | Expected reimbursement: ${pricing['total']:.2f}"
                else:
                    missing = [i["hcpcs_code"] for i in pricing["items"] if not i["found"]]
                    order.insurance_notes += f" | Partial pricing (missing rates for: {', '.join(missing)})"
            except Exception as e:
                logger.warning(f"Allowable rate lookup failed for order {order_id}: {e}")

        await _save_order(order)
        return order

    # ── Staff actions ───────────────────────────────────────────

    async def approve_order(self, order_id: str, notes: str = "") -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        # Gate: check prior-auth status before allowing approval
        from server.services.prior_auth import PriorAuthService
        pa_svc = PriorAuthService(self._fhir_client)
        fulfillment = await pa_svc.can_fulfill(order_id)
        if not fulfillment["can_proceed"]:
            raise ValueError(f"Cannot approve: {fulfillment['reason']}")

        order.status = DMEOrderStatus.APPROVED
        if notes:
            order.staff_notes = (order.staff_notes + "\n" + notes).strip()
        order.updated_at = datetime.now().isoformat()
        await _save_order(order)
        return order

    async def reject_order(self, order_id: str, reason: str = "") -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        order.status = DMEOrderStatus.REJECTED
        order.rejection_reason = reason
        order.updated_at = datetime.now().isoformat()
        await _save_order(order)
        return order

    async def hold_order(self, order_id: str, reason: str = "") -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        order.status = DMEOrderStatus.ON_HOLD
        order.hold_reason = reason
        order.updated_at = datetime.now().isoformat()
        logger.info(f"DME order {order_id} placed on hold: {reason[:50]}")
        await _save_order(order)
        return order

    async def resume_order(self, order_id: str) -> DMEOrder:
        """Move a held order back to its logical next status."""
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        if order.insurance_verified:
            order.status = DMEOrderStatus.VERIFIED
        else:
            order.status = DMEOrderStatus.PENDING
        order.hold_reason = ""
        order.updated_at = datetime.now().isoformat()
        await _save_order(order)
        return order

    # ── Patient confirmation flow ───────────────────────────────

    async def generate_confirmation_token(self, order_id: str, send_via: str = "sms") -> DMEOrder:
        """Generate a short-lived token for patient confirmation link."""
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(hours=self.CONFIRMATION_TOKEN_EXPIRY_HOURS)

        order.confirmation_token = token
        order.confirmation_token_expires = expires.isoformat()
        order.confirmation_sent_at = datetime.now().isoformat()
        order.confirmation_sent_via = send_via
        order.status = DMEOrderStatus.PATIENT_CONTACTED
        order.updated_at = datetime.now().isoformat()

        await _save_order(order)
        logger.info(f"DME order {order_id} confirmation token generated, sent via {send_via}")
        return order

    async def validate_confirmation_token(self, token: str) -> Optional[DMEOrder]:
        """Look up an order by confirmation token. Returns None if invalid/expired."""
        row = await db_fetch_one(
            "SELECT * FROM dme_orders WHERE confirmation_token = ?", (token,)
        )
        if not row:
            return None
        order = _row_to_order(row)
        if order.confirmation_token_expires:
            expires = datetime.fromisoformat(order.confirmation_token_expires)
            if datetime.now() > expires:
                logger.info(f"Confirmation token expired for order {order.id}")
                return None
        return order

    async def patient_confirm(self, token: str, data: dict) -> Optional[DMEOrder]:
        """Patient confirms their details via the tokenized link."""
        order = await self.validate_confirmation_token(token)
        if not order:
            return None

        if data.get("skip"):
            order.status = DMEOrderStatus.CANCELLED
            order.staff_notes = (order.staff_notes + "\nPatient declined this supply cycle.").strip()
            order.updated_at = datetime.now().isoformat()
            logger.info(f"DME order {order.id} skipped by patient")
            await _save_order(order)
            return order

        if data.get("address"):
            order.patient_address = data["address"]
        if data.get("city"):
            order.patient_city = data["city"]
        if data.get("state"):
            order.patient_state = data["state"]
        if data.get("zip"):
            order.patient_zip = data["zip"]
        if data.get("phone"):
            order.patient_phone = data["phone"]

        method = data.get("fulfillment_method", FulfillmentMethod.NOT_SELECTED)
        if method in (FulfillmentMethod.PICKUP, FulfillmentMethod.SHIP, "pickup", "ship"):
            order.fulfillment_method = method
            if method in (FulfillmentMethod.SHIP, "ship"):
                order.shipping_fee = 15.00

        # Handle selected items for bundle orders
        selected = data.get("selected_items")
        if selected is not None and order.bundle_items:
            order.selected_items = [s for s in selected if s in order.bundle_items]

        if data.get("patient_notes"):
            order.patient_notes = data["patient_notes"]

        order.patient_confirmed_address = True
        order.confirmation_responded_at = datetime.now().isoformat()
        order.status = DMEOrderStatus.PATIENT_CONFIRMED
        order.updated_at = datetime.now().isoformat()

        logger.info(f"DME order {order.id} confirmed by patient (fulfillment={order.fulfillment_method})")
        await _save_order(order)
        return order

    def get_patient_safe_order(self, order: DMEOrder) -> dict:
        """Return order data safe to show to a patient (no internal notes, no staff fields)."""
        return {
            "id": order.id,
            "status": order.status.value,
            "status_label": order.patient_display_status,
            "patient_first_name": order.patient_first_name,
            "equipment_category": order.equipment_category,
            "equipment_description": order.equipment_description,
            "patient_address": order.patient_address,
            "patient_city": order.patient_city,
            "patient_state": order.patient_state,
            "patient_zip": order.patient_zip,
            "patient_phone": order.patient_phone,
            "fulfillment_method": order.fulfillment_method,
            "shipping_fee": order.shipping_fee,
            "shipping_tracking_number": order.shipping_tracking_number,
            "shipping_carrier": order.shipping_carrier,
            "estimated_delivery_date": order.estimated_delivery_date,
            "pickup_ready_date": order.pickup_ready_date,
            "bundle_items": order.bundle_items,
            "selected_items": order.selected_items,
            "auto_replace": order.auto_replace,
            "auto_replace_frequency": order.auto_replace_frequency,
            "next_replace_date": order.next_replace_date,
            "created_at": order.created_at,
            "patient_confirmed_address": order.patient_confirmed_address,
            "confirmation_responded_at": order.confirmation_responded_at,
        }

    # ── Fulfillment tracking ────────────────────────────────────

    async def mark_ordered(self, order_id: str, vendor_name: str = "",
                           vendor_order_id: str = "") -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        order.status = DMEOrderStatus.ORDERING
        order.vendor_name = vendor_name
        order.vendor_order_id = vendor_order_id
        order.vendor_ordered_at = datetime.now().isoformat()
        order.updated_at = datetime.now().isoformat()
        logger.info(f"DME order {order_id} sent to vendor {vendor_name}")
        await _save_order(order)
        return order

    async def mark_shipped(self, order_id: str, tracking_number: str = "",
                           carrier: str = "", estimated_delivery: str = "") -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        order.status = DMEOrderStatus.SHIPPED
        if tracking_number:
            order.shipping_tracking_number = tracking_number
        if carrier:
            order.shipping_carrier = carrier
        if estimated_delivery:
            order.estimated_delivery_date = estimated_delivery
        if order.fulfillment_method == FulfillmentMethod.PICKUP:
            order.pickup_ready_date = date.today().isoformat()
            order.auto_deliver_after = datetime.now().isoformat()  # immediate for pickup
        else:
            order.auto_deliver_after = (datetime.now() + timedelta(days=7)).isoformat()
        order.updated_at = datetime.now().isoformat()
        await _save_order(order)
        return order

    async def fulfill_order(self, order_id: str) -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        order.status = DMEOrderStatus.FULFILLED
        order.fulfilled_at = datetime.now().isoformat()
        order.updated_at = datetime.now().isoformat()
        if order.auto_replace and order.auto_replace_frequency:
            order.next_replace_date = self._compute_next_date(order.auto_replace_frequency)
            logger.info(f"DME order {order_id} fulfilled, next auto-replace: {order.next_replace_date}")
        await _save_order(order)
        return order

    # ── Queue queries (staff dashboard) ─────────────────────────

    async def get_auto_replace_due(self) -> List[DMEOrder]:
        today = date.today().isoformat()
        rows = await db_fetch_all(
            "SELECT * FROM dme_orders WHERE auto_replace = 1 AND status = ? AND next_replace_date IS NOT NULL AND next_replace_date <= ?",
            (DMEOrderStatus.FULFILLED.value, today),
        )
        return [_row_to_order(r) for r in rows]

    async def get_incoming_requests(self) -> List[DMEOrder]:
        rows = await db_fetch_all(
            "SELECT * FROM dme_orders WHERE status = ? ORDER BY created_at DESC",
            (DMEOrderStatus.PENDING.value,),
        )
        orders = [_row_to_order(r) for r in rows]
        return [o for o in orders if not self._is_auto_refill(o)]

    async def get_awaiting_patient(self) -> List[DMEOrder]:
        rows = await db_fetch_all(
            "SELECT * FROM dme_orders WHERE status = ? ORDER BY COALESCE(confirmation_sent_at, updated_at) ASC",
            (DMEOrderStatus.PATIENT_CONTACTED.value,),
        )
        return [_row_to_order(r) for r in rows]

    async def get_patient_confirmed(self) -> List[DMEOrder]:
        rows = await db_fetch_all(
            "SELECT * FROM dme_orders WHERE status = ? ORDER BY COALESCE(confirmation_responded_at, updated_at) ASC",
            (DMEOrderStatus.PATIENT_CONFIRMED.value,),
        )
        return [_row_to_order(r) for r in rows]

    async def get_in_progress(self) -> List[DMEOrder]:
        active = [s.value for s in (
            DMEOrderStatus.VERIFYING, DMEOrderStatus.VERIFIED,
            DMEOrderStatus.AWAITING_APPROVAL, DMEOrderStatus.APPROVED,
            DMEOrderStatus.ORDERING, DMEOrderStatus.SHIPPED,
        )]
        placeholders = ",".join("?" * len(active))
        rows = await db_fetch_all(
            f"SELECT * FROM dme_orders WHERE status IN ({placeholders}) ORDER BY updated_at DESC",
            tuple(active),
        )
        return [_row_to_order(r) for r in rows]

    async def get_on_hold(self) -> List[DMEOrder]:
        rows = await db_fetch_all(
            "SELECT * FROM dme_orders WHERE status = ? ORDER BY updated_at DESC",
            (DMEOrderStatus.ON_HOLD.value,),
        )
        return [_row_to_order(r) for r in rows]

    async def get_auto_refill_pending(self) -> List[DMEOrder]:
        today = date.today().isoformat()
        rows = await db_fetch_all(
            """SELECT * FROM dme_orders WHERE auto_replace = 1 AND (
                   (status = ? AND next_replace_date IS NOT NULL AND next_replace_date <= ?)
                   OR (status = ? AND next_replace_date IS NOT NULL)
               ) ORDER BY COALESCE(next_replace_date, created_at) ASC""",
            (DMEOrderStatus.FULFILLED.value, today, DMEOrderStatus.PENDING.value),
        )
        return [_row_to_order(r) for r in rows]

    async def process_due_refills(self) -> List[DMEOrder]:
        """Auto-process fulfilled orders whose refill date has arrived.

        For each due order:
        1. Creates a new child order cloned from the parent (patient/insurance/equipment info)
        2. Sets origin=AUTO_REFILL, links to parent via parent_order_id
        3. Generates a confirmation token and sets status to PATIENT_CONTACTED
        4. Advances the parent's next_replace_date to the next cycle

        Returns the list of newly created child orders (ready for patient confirmation).
        """
        due_orders = await self.get_auto_replace_due()
        if not due_orders:
            return []

        created = []
        for parent in due_orders:
            # Create new child order from the parent's patient/equipment info
            child = DMEOrder(
                patient_first_name=parent.patient_first_name,
                patient_last_name=parent.patient_last_name,
                patient_dob=parent.patient_dob,
                patient_phone=parent.patient_phone,
                patient_email=parent.patient_email,
                patient_address=parent.patient_address,
                patient_city=parent.patient_city,
                patient_state=parent.patient_state,
                patient_zip=parent.patient_zip,
                patient_id=parent.patient_id,
                insurance_payer=parent.insurance_payer,
                insurance_member_id=parent.insurance_member_id,
                insurance_group=parent.insurance_group,
                equipment_category=parent.equipment_category,
                equipment_description=parent.equipment_description,
                quantity=parent.quantity,
                bundle_items=list(parent.bundle_items),
                selected_items=list(parent.selected_items),
                diagnosis_code=parent.diagnosis_code,
                diagnosis_description=parent.diagnosis_description,
                referring_physician=parent.referring_physician,
                referring_npi=parent.referring_npi,
                last_encounter_date=parent.last_encounter_date,
                last_encounter_type=parent.last_encounter_type,
                last_encounter_provider=parent.last_encounter_provider,
                last_encounter_provider_npi=parent.last_encounter_provider_npi,
                origin=OrderOrigin.AUTO_REFILL,
                parent_order_id=parent.id,
                auto_replace=True,
                auto_replace_frequency=parent.auto_replace_frequency,
                hcpcs_codes=list(parent.hcpcs_codes),
                supply_months=parent.supply_months,
            )

            # Auto-generate confirmation token so patient gets notified immediately
            token = secrets.token_urlsafe(32)
            expires = datetime.now() + timedelta(hours=self.CONFIRMATION_TOKEN_EXPIRY_HOURS)
            child.confirmation_token = token
            child.confirmation_token_expires = expires.isoformat()
            child.confirmation_sent_at = datetime.now().isoformat()
            child.confirmation_sent_via = "sms"  # TODO: use patient's preferred contact method
            child.status = DMEOrderStatus.PATIENT_CONTACTED

            await _save_order(child)
            logger.info(
                f"Auto-refill: created order {child.id} from parent {parent.id} "
                f"(patient {parent.patient_id or parent.patient_last_name})"
            )

            # Advance the parent's next_replace_date so it doesn't re-trigger
            if parent.auto_replace_frequency:
                parent.next_replace_date = self._compute_next_date(parent.auto_replace_frequency)
            parent.updated_at = datetime.now().isoformat()
            await _save_order(parent)

            created.append(child)

        if created:
            logger.info(f"Auto-refill: processed {len(created)} due refills")
        return created

    async def get_encounter_expired(self) -> List[DMEOrder]:
        excluded = [DMEOrderStatus.FULFILLED.value, DMEOrderStatus.REJECTED.value,
                    DMEOrderStatus.CANCELLED.value]
        placeholders = ",".join("?" * len(excluded))
        rows = await db_fetch_all(
            f"SELECT * FROM dme_orders WHERE status NOT IN ({placeholders}) ORDER BY COALESCE(last_encounter_date, '0000-00-00') ASC",
            tuple(excluded),
        )
        orders = [_row_to_order(r) for r in rows]
        return [o for o in orders if not o.encounter_current]

    # ── Provider Encounter Tracking ───────────────────────────────

    async def update_encounter(self, order_id: str, data: dict) -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        if data.get("encounter_date"):
            order.last_encounter_date = data["encounter_date"]
        if data.get("encounter_type"):
            order.last_encounter_type = data["encounter_type"]
        if data.get("encounter_provider"):
            order.last_encounter_provider = data["encounter_provider"]
        if data.get("encounter_provider_npi"):
            order.last_encounter_provider_npi = data["encounter_provider_npi"]
        order.updated_at = datetime.now().isoformat()
        logger.info(
            f"DME order {order_id} encounter updated: "
            f"{order.last_encounter_type} on {order.last_encounter_date} "
            f"with {order.last_encounter_provider}"
        )
        await _save_order(order)
        return order

    # ── Documents & Compliance ──────────────────────────────────

    async def add_document(self, order_id: str, filename: str, document_type: str) -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        doc = DMEDocument(filename=filename, document_type=document_type)
        order.documents.append(doc)
        order.updated_at = datetime.now().isoformat()
        await _save_order(order)
        return order

    async def remove_document(self, order_id: str, doc_id: str) -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        order.documents = [d for d in order.documents if d.id != doc_id]
        order.updated_at = datetime.now().isoformat()
        await _save_order(order)
        return order

    async def update_compliance(self, order_id: str, data: dict) -> DMEOrder:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        order.compliance_status = data.get("status", ComplianceStatus.UNKNOWN)
        order.compliance_avg_hours = data.get("avg_hours")
        order.compliance_days_met = data.get("days_met")
        order.compliance_total_days = data.get("total_days")
        order.compliance_last_checked = datetime.now().isoformat()
        order.updated_at = datetime.now().isoformat()
        logger.info(f"DME order {order_id} compliance updated: {order.compliance_status}")
        await _save_order(order)
        return order

    # ── Dashboard ───────────────────────────────────────────────

    async def get_dashboard(self) -> dict:
        rows = await db_fetch_all("SELECT status, COUNT(*) as cnt FROM dme_orders GROUP BY status")
        counts = {r["status"]: r["cnt"] for r in rows}
        total = sum(counts.values())
        return {
            "total": total,
            "pending": counts.get("pending", 0),
            "verified": counts.get("verified", 0),
            "approved": counts.get("approved", 0),
            "patient_contacted": counts.get("patient_contacted", 0),
            "patient_confirmed": counts.get("patient_confirmed", 0),
            "ordering": counts.get("ordering", 0),
            "shipped": counts.get("shipped", 0),
            "fulfilled": counts.get("fulfilled", 0),
            "rejected": counts.get("rejected", 0),
            "on_hold": counts.get("on_hold", 0),
            "auto_replace_due": len(await self.get_auto_replace_due()),
            "incoming_requests": len(await self.get_incoming_requests()),
            "awaiting_patient": len(await self.get_awaiting_patient()),
            "ready_to_order": len(await self.get_patient_confirmed()),
            "auto_refill_pending": len(await self.get_auto_refill_pending()),
            "in_progress": len(await self.get_in_progress()),
            "encounter_expired": len(await self.get_encounter_expired()),
        }

    # ── Patient rejection ──────────────────────────────────────

    async def patient_reject_order(self, token: str, reason: str = "",
                                    callback_requested: bool = False) -> Optional[DMEOrder]:
        """Patient flags an issue with their order via the confirmation link."""
        order = await self.validate_confirmation_token(token)
        if not order:
            return None
        order.patient_rejected = True
        order.patient_rejection_reason = reason
        order.patient_callback_requested = callback_requested
        order.status = DMEOrderStatus.ON_HOLD
        order.hold_reason = f"Patient flagged issue: {reason}" if reason else "Patient flagged issue"
        order.confirmation_responded_at = datetime.now().isoformat()
        order.updated_at = datetime.now().isoformat()
        logger.info(f"DME order {order.id} rejected by patient (callback={callback_requested})")
        await _save_order(order)
        return order

    # ── Patient auto-refill toggle ──────────────────────────

    async def patient_toggle_refill(self, token: str, auto_replace: bool,
                                     frequency: str = "quarterly") -> Optional[DMEOrder]:
        """Patient opts in or out of auto-refill via their confirmation link."""
        order = await self.validate_confirmation_token(token)
        if not order:
            return None
        order.auto_replace = auto_replace
        if auto_replace:
            order.auto_replace_frequency = frequency
            order.next_replace_date = self._compute_next_date(frequency)
            logger.info(f"DME order {order.id} patient opted IN to auto-refill ({frequency})")
        else:
            order.auto_replace_frequency = None
            order.next_replace_date = None
            logger.info(f"DME order {order.id} patient opted OUT of auto-refill")
        order.updated_at = datetime.now().isoformat()
        await _save_order(order)
        return order

    # ── Auto-deliver ─────────────────────────────────────────

    async def process_auto_deliveries(self) -> List[DMEOrder]:
        """Fulfill orders whose auto-deliver timer has expired."""
        now = datetime.now().isoformat()
        rows = await db_fetch_all(
            "SELECT * FROM dme_orders WHERE status = ? AND auto_deliver_after IS NOT NULL AND auto_deliver_after <= ?",
            (DMEOrderStatus.SHIPPED.value, now),
        )
        fulfilled = []
        for row in rows:
            order = _row_to_order(row)
            order.status = DMEOrderStatus.FULFILLED
            order.fulfilled_at = datetime.now().isoformat()
            order.updated_at = datetime.now().isoformat()
            if order.auto_replace and order.auto_replace_frequency:
                order.next_replace_date = self._compute_next_date(order.auto_replace_frequency)
            await _save_order(order)
            fulfilled.append(order)
            logger.info(f"DME order {order.id} auto-fulfilled")
        return fulfilled

    # ── Expiring encounter queue ─────────────────────────────

    async def get_expiring_encounter_orders(self, days_threshold: int = 14) -> List[DMEOrder]:
        """Get active orders with encounters expiring within the threshold."""
        excluded = [DMEOrderStatus.FULFILLED.value, DMEOrderStatus.REJECTED.value,
                    DMEOrderStatus.CANCELLED.value]
        placeholders = ",".join("?" * len(excluded))
        rows = await db_fetch_all(
            f"SELECT * FROM dme_orders WHERE status NOT IN ({placeholders}) AND last_encounter_date IS NOT NULL ORDER BY last_encounter_date ASC",
            tuple(excluded),
        )
        orders = [_row_to_order(r) for r in rows]
        return [o for o in orders if o.encounter_expires_in_days is not None
                and 0 < o.encounter_expires_in_days <= days_threshold]

    # ── Receipt & delivery ticket ────────────────────────────

    async def generate_receipt(self, order_id: str) -> Optional[dict]:
        """Generate structured receipt data for a fulfilled order."""
        order = await self.get_order(order_id)
        if not order:
            return None
        items = order.selected_items if order.selected_items else [order.equipment_description]
        return {
            "order_id": order.id,
            "date": order.fulfilled_at or order.updated_at,
            "patient_name": order.patient_name,
            "patient_dob": order.patient_dob,
            "items": items,
            "equipment_category": order.equipment_category,
            "hcpcs_codes": order.hcpcs_codes,
            "insurance_payer": order.insurance_payer,
            "insurance_member_id": order.insurance_member_id,
            "vendor": order.vendor_name or "In-House",
            "fulfillment_method": order.fulfillment_method,
            "shipping_fee": order.shipping_fee,
            "diagnosis_code": order.diagnosis_code,
            "diagnosis_description": order.diagnosis_description,
            "referring_physician": order.referring_physician,
        }

    async def generate_delivery_ticket(self, order_id: str) -> Optional[dict]:
        """Generate delivery ticket data for shipping/pickup."""
        order = await self.get_order(order_id)
        if not order:
            return None
        items = order.selected_items if order.selected_items else [order.equipment_description]
        return {
            "order_id": order.id,
            "patient_name": order.patient_name,
            "items": items,
            "equipment_category": order.equipment_category,
            "fulfillment_method": order.fulfillment_method,
            "shipping_address": {
                "address": order.patient_address,
                "city": order.patient_city,
                "state": order.patient_state,
                "zip": order.patient_zip,
            } if order.fulfillment_method == FulfillmentMethod.SHIP else None,
            "tracking_number": order.shipping_tracking_number,
            "carrier": order.shipping_carrier,
            "shipped_at": order.vendor_ordered_at,
            "fulfilled_at": order.fulfilled_at,
            "vendor": order.vendor_name or "In-House",
        }

    # ── Demo data ────────────────────────────────────────────

    async def seed_demo_data(self):
        """Populate with realistic sleep-medicine DME orders across all workflow stages."""
        # Only seed if no orders exist yet
        existing = await db_fetch_one("SELECT COUNT(*) as cnt FROM dme_orders")
        if existing and existing["cnt"] > 0:
            return

        today = date.today()

        # ── Incoming requests (pending, new Rx) ─────────────────
        o_maria = await self.create_order({
            "patient_first_name": "Maria", "patient_last_name": "Garcia",
            "patient_dob": "1965-04-12", "patient_phone": "(210) 555-1234",
            "patient_email": "maria.garcia@email.com",
            "patient_address": "1420 Oak Valley", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78229",
            "insurance_payer": "Blue Cross Blue Shield", "insurance_member_id": "BCB1234567",
            "insurance_group": "GRP100",
            "equipment_category": "CPAP Machine",
            "equipment_description": "ResMed AirSense 11 Auto CPAP",
            "hcpcs_codes": ["E0601"],
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Thomas Nguyen", "referring_npi": "1234567890",
            "clinical_notes": "AHI 32, requires CPAP at 12 cmH2O",
            "origin": OrderOrigin.PRESCRIPTION,
        })
        o_maria.last_encounter_date = (today - timedelta(days=14)).isoformat()
        o_maria.last_encounter_type = EncounterType.INITIAL_CONSULTATION
        o_maria.last_encounter_provider = "Dr. Thomas Nguyen"
        o_maria.last_encounter_provider_npi = "1234567890"
        await _save_order(o_maria)

        o_robert = await self.create_order({
            "patient_first_name": "Robert", "patient_last_name": "Johnson",
            "patient_dob": "1952-11-08", "patient_phone": "(210) 555-5678",
            "patient_address": "305 Elm St", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78201",
            "insurance_payer": "Medicare", "insurance_member_id": "1EG4-TE5-MK72",
            "equipment_category": "BiPAP / ASV Machine",
            "equipment_description": "ResMed AirCurve 10 VAuto BiPAP",
            "hcpcs_codes": ["E0470"],
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Sarah Andry", "referring_npi": "1661906534",
            "origin": OrderOrigin.PRESCRIPTION,
        })
        o_robert.last_encounter_date = (today - timedelta(days=410)).isoformat()
        o_robert.last_encounter_type = EncounterType.OFFICE_VISIT
        o_robert.last_encounter_provider = "Dr. Sarah Andry"
        o_robert.last_encounter_provider_npi = "1661906534"
        await _save_order(o_robert)

        # ── Auto-refill due (fulfilled, past replace date) ──────
        o1 = await self.create_order({
            "patient_first_name": "Carmen", "patient_last_name": "Martinez",
            "patient_dob": "1970-03-15", "patient_phone": "(210) 555-3456",
            "patient_email": "cmartinez70@gmail.com",
            "patient_address": "2100 Fredericksburg Rd", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78201",
            "insurance_payer": "Cigna", "insurance_member_id": "CIG5551234",
            "insurance_group": "GRP300",
            "equipment_category": "Mask Cushion / Pillow Replacement",
            "equipment_description": "Full face mask cushion + disposable filters",
            "hcpcs_codes": ["A7031", "A7038", "A7039"],
            "supply_months": 3,
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Thomas Nguyen", "referring_npi": "1234567890",
            "auto_replace": True, "auto_replace_frequency": "quarterly",
            "origin": OrderOrigin.AUTO_REFILL,
        })
        o1.status = DMEOrderStatus.FULFILLED
        o1.next_replace_date = (today - timedelta(days=5)).isoformat()
        o1.compliance_status = ComplianceStatus.COMPLIANT
        o1.compliance_avg_hours = 6.3
        o1.compliance_days_met = 27
        o1.compliance_total_days = 30
        o1.compliance_last_checked = (today - timedelta(days=10)).isoformat()
        o1.last_encounter_date = (today - timedelta(days=90)).isoformat()
        o1.last_encounter_type = EncounterType.OFFICE_VISIT
        o1.last_encounter_provider = "Dr. Thomas Nguyen"
        o1.last_encounter_provider_npi = "1234567890"
        await _save_order(o1)

        o2 = await self.create_order({
            "patient_first_name": "Albert", "patient_last_name": "Ortiz",
            "patient_dob": "1958-09-20", "patient_phone": "(210) 555-7890",
            "patient_address": "4500 Medical Dr", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78229",
            "insurance_payer": "UnitedHealthcare", "insurance_member_id": "UHC7654321",
            "insurance_group": "GRP400",
            "equipment_category": "Heated Tubing",
            "equipment_description": "Heated tubing + humidifier chamber",
            "hcpcs_codes": ["A4604", "A7046"],
            "supply_months": 6,
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Sarah Andry", "referring_npi": "1661906534",
            "auto_replace": True, "auto_replace_frequency": "biannual",
            "origin": OrderOrigin.AUTO_REFILL,
        })
        o2.status = DMEOrderStatus.FULFILLED
        o2.next_replace_date = (today - timedelta(days=12)).isoformat()
        o2.compliance_status = ComplianceStatus.UNKNOWN
        await _save_order(o2)

        # ── Verified, waiting for staff review ──────────────────
        o3 = await self.create_order({
            "patient_first_name": "Linda", "patient_last_name": "Chen",
            "patient_dob": "1982-01-30", "patient_phone": "(210) 555-2345",
            "patient_email": "lchen82@yahoo.com",
            "patient_address": "7700 IH-10 West", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78230",
            "insurance_payer": "Humana", "insurance_member_id": "HUM3456789",
            "insurance_group": "GRP500",
            "equipment_category": "CPAP Mask — Full Face",
            "equipment_description": "ResMed AirFit F30i full face mask",
            "hcpcs_codes": ["A7030", "A7031", "A7035"],
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Thomas Nguyen", "referring_npi": "1234567890",
            "origin": OrderOrigin.STAFF_INITIATED,
        })
        o3.status = DMEOrderStatus.VERIFIED
        o3.insurance_verified = True
        o3.insurance_notes = "Active coverage found: Humana Choice PPO"
        o3.compliance_status = ComplianceStatus.COMPLIANT
        o3.compliance_avg_hours = 7.1
        o3.compliance_days_met = 29
        o3.compliance_total_days = 30
        o3.compliance_last_checked = (today - timedelta(days=3)).isoformat()
        o3.last_encounter_date = (today - timedelta(days=45)).isoformat()
        o3.last_encounter_type = EncounterType.TELEHEALTH
        o3.last_encounter_provider = "Dr. Thomas Nguyen"
        o3.last_encounter_provider_npi = "1234567890"
        await _save_order(o3)

        # ── Approved ─────
        o4 = await self.create_order({
            "patient_first_name": "David", "patient_last_name": "Hernandez",
            "patient_dob": "1990-07-14", "patient_phone": "(210) 555-6789",
            "patient_email": "dhernandez90@gmail.com",
            "patient_address": "1200 Loop 410", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78217",
            "insurance_payer": "Molina Healthcare", "insurance_member_id": "MOL8765432",
            "equipment_category": "CPAP Mask — Nasal Pillow",
            "equipment_description": "ResMed AirFit P30i nasal pillow mask + headgear",
            "hcpcs_codes": ["A7033", "A7032", "A7035"],
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Antonio Reyes", "referring_npi": "1122334455",
            "origin": OrderOrigin.PATIENT_REQUEST,
        })
        o4.status = DMEOrderStatus.APPROVED
        o4.insurance_verified = True
        o4.insurance_notes = "Active coverage found: Molina Marketplace"
        o4.compliance_status = ComplianceStatus.COMPLIANT
        o4.compliance_avg_hours = 5.8
        o4.compliance_days_met = 25
        o4.compliance_total_days = 30
        o4.last_encounter_date = (today - timedelta(days=200)).isoformat()
        o4.last_encounter_type = EncounterType.OFFICE_VISIT
        o4.last_encounter_provider = "Dr. Antonio Reyes"
        o4.last_encounter_provider_npi = "1122334455"
        await _save_order(o4)

        # ── Patient contacted ──
        o5 = await self.create_order({
            "patient_first_name": "Sandra", "patient_last_name": "Perez",
            "patient_dob": "1975-12-02", "patient_phone": "(210) 555-4321",
            "patient_email": "sperez75@outlook.com",
            "patient_address": "9200 Wurzbach Rd", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78240",
            "insurance_payer": "Humana", "insurance_member_id": "HUM2223334",
            "insurance_group": "GRP600",
            "equipment_category": "CPAP Mask — Nasal",
            "equipment_description": "Full resupply (nasal) — mask, cushion, headgear, tubing, chamber, filters",
            "hcpcs_codes": ["A7034", "A7032", "A7035", "A4604", "A7046", "A7038", "A7039"],
            "supply_months": 6,
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Sarah Andry", "referring_npi": "1661906534",
            "auto_replace": True, "auto_replace_frequency": "biannual",
            "origin": OrderOrigin.AUTO_REFILL,
        })
        o5.status = DMEOrderStatus.PATIENT_CONTACTED
        o5.insurance_verified = True
        o5.confirmation_token = "demo-token-sandra-perez"
        o5.confirmation_token_expires = (datetime.now() + timedelta(hours=36)).isoformat()
        o5.confirmation_sent_at = (datetime.now() - timedelta(hours=12)).isoformat()
        o5.confirmation_sent_via = "sms"
        o5.last_encounter_date = (today - timedelta(days=330)).isoformat()
        o5.last_encounter_type = EncounterType.OFFICE_VISIT
        o5.last_encounter_provider = "Dr. Sarah Andry"
        o5.last_encounter_provider_npi = "1661906534"
        await _save_order(o5)

        # ── Patient confirmed ────────
        o6 = await self.create_order({
            "patient_first_name": "James", "patient_last_name": "Wilson",
            "patient_dob": "1978-06-22", "patient_phone": "(210) 555-9012",
            "patient_email": "jwilson78@gmail.com",
            "patient_address": "800 Broadway", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78215",
            "insurance_payer": "Aetna", "insurance_member_id": "AET9876543",
            "insurance_group": "GRP200",
            "equipment_category": "Filters — Disposable",
            "equipment_description": "Cushion + filters quarterly resupply",
            "hcpcs_codes": ["A7031", "A7038", "A7039"],
            "supply_months": 3,
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Thomas Nguyen", "referring_npi": "1234567890",
            "auto_replace": True, "auto_replace_frequency": "quarterly",
            "origin": OrderOrigin.AUTO_REFILL,
        })
        o6.status = DMEOrderStatus.PATIENT_CONFIRMED
        o6.insurance_verified = True
        o6.fulfillment_method = FulfillmentMethod.SHIP
        o6.patient_confirmed_address = True
        o6.confirmation_responded_at = (datetime.now() - timedelta(hours=2)).isoformat()
        o6.last_encounter_date = (today - timedelta(days=120)).isoformat()
        o6.last_encounter_type = EncounterType.TELEHEALTH
        o6.last_encounter_provider = "Dr. Thomas Nguyen"
        o6.last_encounter_provider_npi = "1234567890"
        await _save_order(o6)

        # ── Shipped ────────────────────────────────
        o7 = await self.create_order({
            "patient_first_name": "Patricia", "patient_last_name": "Ramirez",
            "patient_dob": "1968-08-19", "patient_phone": "(210) 555-1111",
            "patient_address": "3300 Nacogdoches Rd", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78217",
            "insurance_payer": "Blue Cross Blue Shield", "insurance_member_id": "BCB9991234",
            "equipment_category": "Headgear",
            "equipment_description": "Headgear + heated tubing replacement",
            "hcpcs_codes": ["A7035", "A4604"],
            "supply_months": 6,
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Sarah Andry", "referring_npi": "1661906534",
            "origin": OrderOrigin.STAFF_INITIATED,
        })
        o7.status = DMEOrderStatus.SHIPPED
        o7.insurance_verified = True
        o7.fulfillment_method = FulfillmentMethod.SHIP
        o7.patient_confirmed_address = True
        o7.vendor_name = "ResMed Direct"
        o7.vendor_order_id = "RSM-2026-44821"
        o7.vendor_ordered_at = (datetime.now() - timedelta(days=3)).isoformat()
        o7.shipping_tracking_number = "1Z999AA10123456784"
        o7.shipping_carrier = "UPS"
        o7.estimated_delivery_date = (today + timedelta(days=2)).isoformat()
        o7.last_encounter_date = (today - timedelta(days=60)).isoformat()
        o7.last_encounter_type = EncounterType.OFFICE_VISIT
        o7.last_encounter_provider = "Dr. Sarah Andry"
        o7.last_encounter_provider_npi = "1661906534"
        await _save_order(o7)

        # ── On hold ───────────────────────
        o8 = await self.create_order({
            "patient_first_name": "Michael", "patient_last_name": "Thompson",
            "patient_dob": "1955-02-28", "patient_phone": "(210) 555-2222",
            "patient_address": "5600 Babcock Rd", "patient_city": "San Antonio",
            "patient_state": "TX", "patient_zip": "78240",
            "insurance_payer": "Medicare", "insurance_member_id": "1EG4-AB9-QR33",
            "equipment_category": "Water Chamber / Humidifier",
            "equipment_description": "Humidifier chamber replacement",
            "hcpcs_codes": ["A7046"],
            "diagnosis_code": "G47.33", "diagnosis_description": "Obstructive Sleep Apnea",
            "referring_physician": "Dr. Thomas Nguyen", "referring_npi": "1234567890",
            "origin": OrderOrigin.AUTO_REFILL,
            "auto_replace": True, "auto_replace_frequency": "biannual",
        })
        o8.status = DMEOrderStatus.ON_HOLD
        o8.hold_reason = "Patient phone disconnected — sent letter, awaiting response"
        o8.insurance_verified = True
        o8.last_encounter_date = (today - timedelta(days=380)).isoformat()
        o8.last_encounter_type = EncounterType.ANNUAL_WELLNESS
        o8.last_encounter_provider = "Dr. Thomas Nguyen"
        o8.last_encounter_provider_npi = "1234567890"
        await _save_order(o8)

        logger.info("DME demo data seeded to SQLite")

    @staticmethod
    def _is_auto_refill(order: DMEOrder) -> bool:
        """Check if an order is a reorder from auto-replace schedule."""
        return order.auto_replace and order.next_replace_date is not None

    @staticmethod
    def _compute_next_date(frequency: str) -> str:
        today = date.today()
        delta_map = {
            AutoReplaceFrequency.MONTHLY: timedelta(days=30),
            AutoReplaceFrequency.QUARTERLY: timedelta(days=91),
            AutoReplaceFrequency.BIANNUAL: timedelta(days=182),
            AutoReplaceFrequency.ANNUAL: timedelta(days=365),
        }
        delta = delta_map.get(frequency, timedelta(days=30))
        return (today + delta).isoformat()
