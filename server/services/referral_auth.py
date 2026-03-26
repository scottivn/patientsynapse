"""HMO Referral Authorization tracking service.

Tracks PCP referral authorizations for HMO patients — referral numbers,
expiration dates, visit counts, and renewal requests. Distinct from
fax-based referral documents (server/services/referral.py).
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Optional, List, Dict

from server.db import db_execute, db_fetch_one, db_fetch_all

logger = logging.getLogger(__name__)


class ReferralAuthStatus(str, Enum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"
    PENDING_RENEWAL = "pending_renewal"
    CANCELLED = "cancelled"


class InsuranceType(str, Enum):
    HMO = "hmo"
    PPO = "ppo"
    POS = "pos"
    EPO = "epo"
    UNKNOWN = "unknown"


# Insurance types that require a referral on file
REFERRAL_REQUIRED_TYPES = {InsuranceType.HMO, InsuranceType.POS, InsuranceType.EPO}


@dataclass
class ReferralAuth:
    # Patient
    patient_id: str
    patient_first_name: str
    patient_last_name: str

    # Insurance
    insurance_name: str = ""
    insurance_type: str = InsuranceType.UNKNOWN
    insurance_member_id: str = ""
    insurance_npi: str = ""
    copay: str = ""

    # Referral auth details
    referral_number: str = ""
    referring_pcp_name: str = ""
    referring_pcp_npi: str = ""
    referring_pcp_phone: str = ""
    referring_pcp_fax: str = ""

    # Date/visit tracking
    start_date: str = ""
    end_date: str = ""
    visits_allowed: int = 0
    visits_used: int = 0

    # Internal
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    status: ReferralAuthStatus = ReferralAuthStatus.ACTIVE
    notes: str = ""
    renewal_requested_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: date.today().isoformat())
    updated_at: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def patient_name(self) -> str:
        return f"{self.patient_first_name} {self.patient_last_name}"

    @property
    def visits_remaining(self) -> int:
        return max(0, self.visits_allowed - self.visits_used)

    @property
    def days_until_expiry(self) -> Optional[int]:
        if not self.end_date:
            return None
        try:
            end = date.fromisoformat(self.end_date)
            return (end - date.today()).days
        except ValueError:
            return None


def _row_to_auth(row: dict) -> ReferralAuth:
    """Convert a DB row dict to a ReferralAuth."""
    return ReferralAuth(
        id=row["id"],
        patient_id=row["patient_id"],
        patient_first_name=row["patient_first_name"],
        patient_last_name=row["patient_last_name"],
        insurance_name=row.get("insurance_name", ""),
        insurance_type=row.get("insurance_type", InsuranceType.UNKNOWN),
        insurance_member_id=row.get("insurance_member_id", ""),
        insurance_npi=row.get("insurance_npi", ""),
        copay=row.get("copay", ""),
        referral_number=row.get("referral_number", ""),
        referring_pcp_name=row.get("referring_pcp_name", ""),
        referring_pcp_npi=row.get("referring_pcp_npi", ""),
        referring_pcp_phone=row.get("referring_pcp_phone", ""),
        referring_pcp_fax=row.get("referring_pcp_fax", ""),
        start_date=row.get("start_date", ""),
        end_date=row.get("end_date", ""),
        visits_allowed=row.get("visits_allowed", 0),
        visits_used=row.get("visits_used", 0),
        status=ReferralAuthStatus(row.get("status", "active")),
        notes=row.get("notes", ""),
        renewal_requested_at=row.get("renewal_requested_at"),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


async def _save_auth(auth: ReferralAuth) -> None:
    """Upsert a referral authorization to the database."""
    await db_execute(
        """INSERT INTO referral_auths (id, patient_id, patient_first_name, patient_last_name,
               insurance_name, insurance_type, insurance_member_id, insurance_npi, copay,
               referral_number, referring_pcp_name, referring_pcp_npi, referring_pcp_phone,
               referring_pcp_fax, start_date, end_date, visits_allowed, visits_used,
               status, notes, renewal_requested_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               insurance_name=excluded.insurance_name, insurance_type=excluded.insurance_type,
               insurance_member_id=excluded.insurance_member_id, insurance_npi=excluded.insurance_npi,
               copay=excluded.copay, referral_number=excluded.referral_number,
               referring_pcp_name=excluded.referring_pcp_name, referring_pcp_npi=excluded.referring_pcp_npi,
               referring_pcp_phone=excluded.referring_pcp_phone, referring_pcp_fax=excluded.referring_pcp_fax,
               start_date=excluded.start_date, end_date=excluded.end_date,
               visits_allowed=excluded.visits_allowed, visits_used=excluded.visits_used,
               status=excluded.status, notes=excluded.notes,
               renewal_requested_at=excluded.renewal_requested_at, updated_at=excluded.updated_at""",
        (auth.id, auth.patient_id, auth.patient_first_name, auth.patient_last_name,
         auth.insurance_name, auth.insurance_type, auth.insurance_member_id, auth.insurance_npi,
         auth.copay, auth.referral_number, auth.referring_pcp_name, auth.referring_pcp_npi,
         auth.referring_pcp_phone, auth.referring_pcp_fax, auth.start_date, auth.end_date,
         auth.visits_allowed, auth.visits_used, auth.status.value, auth.notes,
         auth.renewal_requested_at, auth.created_at, auth.updated_at),
    )


class ReferralAuthService:
    """Manages HMO referral authorizations: tracking, alerts, and renewals."""

    def __init__(self, fhir_client=None):
        self._fhir_client = fhir_client

    def set_fhir_client(self, fhir_client):
        self._fhir_client = fhir_client

    # ---- CRUD ----

    async def create_auth(self, data: dict) -> ReferralAuth:
        auth = ReferralAuth(
            patient_id=data["patient_id"],
            patient_first_name=data["patient_first_name"],
            patient_last_name=data["patient_last_name"],
            insurance_name=data.get("insurance_name", ""),
            insurance_type=data.get("insurance_type", InsuranceType.UNKNOWN),
            insurance_member_id=data.get("insurance_member_id", ""),
            insurance_npi=data.get("insurance_npi", ""),
            copay=data.get("copay", ""),
            referral_number=data.get("referral_number", ""),
            referring_pcp_name=data.get("referring_pcp_name", ""),
            referring_pcp_npi=data.get("referring_pcp_npi", ""),
            referring_pcp_phone=data.get("referring_pcp_phone", ""),
            referring_pcp_fax=data.get("referring_pcp_fax", ""),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            visits_allowed=int(data.get("visits_allowed", 0)),
            visits_used=int(data.get("visits_used", 0)),
            notes=data.get("notes", ""),
        )
        auth.status = self._compute_status(auth)
        await _save_auth(auth)
        logger.info(f"Referral auth {auth.id} created (type={auth.insurance_type})")
        return auth

    async def list_auths(
        self, status: Optional[ReferralAuthStatus] = None, patient_id: Optional[str] = None
    ) -> List[ReferralAuth]:
        if status and patient_id:
            rows = await db_fetch_all(
                "SELECT * FROM referral_auths WHERE status = ? AND patient_id = ? ORDER BY created_at DESC",
                (status.value, patient_id),
            )
        elif status:
            rows = await db_fetch_all(
                "SELECT * FROM referral_auths WHERE status = ? ORDER BY created_at DESC",
                (status.value,),
            )
        elif patient_id:
            rows = await db_fetch_all(
                "SELECT * FROM referral_auths WHERE patient_id = ? ORDER BY created_at DESC",
                (patient_id,),
            )
        else:
            rows = await db_fetch_all(
                "SELECT * FROM referral_auths ORDER BY created_at DESC"
            )
        auths = [_row_to_auth(r) for r in rows]
        # Refresh statuses for time-based transitions
        for auth in auths:
            new_status = self._compute_status(auth)
            if new_status != auth.status:
                auth.status = new_status
                await _save_auth(auth)
        return auths

    async def get_auth(self, auth_id: str) -> Optional[ReferralAuth]:
        row = await db_fetch_one("SELECT * FROM referral_auths WHERE id = ?", (auth_id,))
        if not row:
            return None
        auth = _row_to_auth(row)
        new_status = self._compute_status(auth)
        if new_status != auth.status:
            auth.status = new_status
            await _save_auth(auth)
        return auth

    async def update_auth(self, auth_id: str, data: dict) -> ReferralAuth:
        auth = await self.get_auth(auth_id)
        if not auth:
            raise ValueError(f"Referral auth {auth_id} not found")

        updatable = [
            "referral_number", "start_date", "end_date", "visits_allowed", "visits_used",
            "copay", "referring_pcp_name", "referring_pcp_npi", "referring_pcp_phone",
            "referring_pcp_fax", "notes", "insurance_name", "insurance_type",
            "insurance_member_id", "insurance_npi",
        ]
        for field_name in updatable:
            if field_name in data and data[field_name] is not None:
                value = data[field_name]
                if field_name in ("visits_allowed", "visits_used"):
                    value = int(value)
                setattr(auth, field_name, value)

        auth.updated_at = date.today().isoformat()
        auth.status = self._compute_status(auth)
        await _save_auth(auth)
        return auth

    # ---- Visit tracking ----

    async def record_visit(self, auth_id: str) -> ReferralAuth:
        auth = await self.get_auth(auth_id)
        if not auth:
            raise ValueError(f"Referral auth {auth_id} not found")
        auth.visits_used += 1
        auth.updated_at = date.today().isoformat()
        auth.status = self._compute_status(auth)
        await _save_auth(auth)
        logger.info(f"Referral auth {auth.id}: visit recorded ({auth.visits_used}/{auth.visits_allowed})")
        return auth

    # ---- Patient lookups ----

    async def get_patient_auths(self, patient_id: str) -> List[ReferralAuth]:
        rows = await db_fetch_all(
            "SELECT * FROM referral_auths WHERE patient_id = ? ORDER BY end_date DESC",
            (patient_id,),
        )
        auths = [_row_to_auth(r) for r in rows]
        for auth in auths:
            auth.status = self._compute_status(auth)
        return auths

    async def get_active_auth(self, patient_id: str) -> Optional[ReferralAuth]:
        """Return the best active auth for a patient (ACTIVE or EXPIRING_SOON)."""
        auths = await self.get_patient_auths(patient_id)
        for auth in auths:
            if auth.status in (ReferralAuthStatus.ACTIVE, ReferralAuthStatus.EXPIRING_SOON):
                return auth
        return None

    async def check_scheduling_eligibility(self, patient_id: str) -> dict:
        """Check if a patient can be scheduled based on referral auth status."""
        patient_auths = await self.get_patient_auths(patient_id)
        insurance_type = InsuranceType.UNKNOWN
        if patient_auths:
            insurance_type = patient_auths[0].insurance_type

        requires_referral = insurance_type in REFERRAL_REQUIRED_TYPES

        if not requires_referral:
            return {
                "eligible": True,
                "requires_referral": False,
                "insurance_type": insurance_type,
                "active_auth": None,
                "warnings": [],
                "block": False,
            }

        active = await self.get_active_auth(patient_id)
        warnings = []
        block = False

        if not active:
            block = True
            warnings.append(
                "No active referral authorization on file. "
                "HMO patients must have a valid referral before being seen."
            )
        else:
            days = active.days_until_expiry
            if days is not None and days < 14:
                warnings.append(f"Referral expires in {days} day(s) on {active.end_date}.")
            if active.visits_allowed > 0 and active.visits_remaining < 2:
                warnings.append(
                    f"Only {active.visits_remaining} visit(s) remaining "
                    f"({active.visits_used}/{active.visits_allowed} used)."
                )

        return {
            "eligible": not block,
            "requires_referral": True,
            "insurance_type": insurance_type,
            "active_auth": self._serialize(active) if active else None,
            "warnings": warnings,
            "block": block,
        }

    # ---- Insurance type detection ----

    async def detect_insurance_type(self, patient_id: str) -> str:
        """Try to detect HMO/PPO from FHIR Coverage resources."""
        if not self._fhir_client:
            return InsuranceType.UNKNOWN

        try:
            from server.fhir.resources import CoverageResource
            cov_resource = CoverageResource(self._fhir_client)
            coverages = await cov_resource.search_by_patient(patient_id)
            for cov in coverages:
                if cov.status != "active":
                    continue
                if cov.type and cov.type.coding:
                    for coding in cov.type.coding:
                        code_lower = (coding.code or "").lower()
                        display_lower = (coding.display or "").lower()
                        for ins_type in InsuranceType:
                            if ins_type.value in code_lower or ins_type.value in display_lower:
                                return ins_type
                if cov.payor:
                    for payor_ref in cov.payor:
                        display = (payor_ref.display or "").lower()
                        if "hmo" in display:
                            return InsuranceType.HMO
                        if "ppo" in display:
                            return InsuranceType.PPO
                        if "pos" in display:
                            return InsuranceType.POS
                        if "epo" in display:
                            return InsuranceType.EPO
        except Exception as e:
            logger.warning(f"FHIR insurance type detection failed: {e}")

        return InsuranceType.UNKNOWN

    # ---- Renewal ----

    async def request_renewal(self, auth_id: str) -> ReferralAuth:
        auth = await self.get_auth(auth_id)
        if not auth:
            raise ValueError(f"Referral auth {auth_id} not found")
        auth.status = ReferralAuthStatus.PENDING_RENEWAL
        auth.renewal_requested_at = date.today().isoformat()
        auth.updated_at = date.today().isoformat()
        await _save_auth(auth)
        logger.info(f"Referral auth {auth.id}: renewal requested")
        return auth

    async def get_renewal_content(self, auth_id: str) -> dict:
        """Generate fax content for PCP renewal request."""
        auth = await self.get_auth(auth_id)
        if not auth:
            raise ValueError(f"Referral auth {auth_id} not found")
        return {
            "to_name": auth.referring_pcp_name,
            "to_fax": auth.referring_pcp_fax,
            "to_phone": auth.referring_pcp_phone,
            "to_npi": auth.referring_pcp_npi,
            "patient_name": auth.patient_name,
            "patient_id": auth.patient_id,
            "insurance_name": auth.insurance_name,
            "insurance_member_id": auth.insurance_member_id,
            "current_referral_number": auth.referral_number,
            "current_expiry": auth.end_date,
            "visits_used": auth.visits_used,
            "visits_allowed": auth.visits_allowed,
            "message": (
                f"Dear {auth.referring_pcp_name or 'Provider'},\n\n"
                f"We are requesting a referral renewal for patient {auth.patient_name} "
                f"(ID: {auth.patient_id}).\n\n"
                f"Current referral #{auth.referral_number} "
                f"{'expires on ' + auth.end_date if auth.end_date else 'has no expiration date set'}. "
                f"Visits used: {auth.visits_used}/{auth.visits_allowed}.\n\n"
                f"Insurance: {auth.insurance_name} (Member ID: {auth.insurance_member_id})\n\n"
                f"Please issue a new referral authorization and fax it to our office.\n\n"
                f"Thank you."
            ),
        }

    # ---- Alerts & dashboard ----

    async def get_expiring_soon(self, days: int = 14) -> List[ReferralAuth]:
        """Return auths expiring within N days or with fewer than 2 visits remaining."""
        rows = await db_fetch_all(
            "SELECT * FROM referral_auths WHERE status != ?",
            (ReferralAuthStatus.CANCELLED.value,),
        )
        result = []
        for row in rows:
            auth = _row_to_auth(row)
            auth.status = self._compute_status(auth)
            expiring_date = False
            expiring_visits = False
            d = auth.days_until_expiry
            if d is not None and 0 <= d <= days:
                expiring_date = True
            if auth.visits_allowed > 0 and auth.visits_remaining < 2:
                expiring_visits = True
            if expiring_date or expiring_visits:
                result.append(auth)
        return sorted(result, key=lambda a: a.end_date or "9999")

    async def get_dashboard(self) -> dict:
        rows = await db_fetch_all("SELECT * FROM referral_auths")
        auths = [_row_to_auth(r) for r in rows]
        for auth in auths:
            auth.status = self._compute_status(auth)
        return {
            "total": len(auths),
            "active": sum(1 for a in auths if a.status == ReferralAuthStatus.ACTIVE),
            "expiring_soon": sum(1 for a in auths if a.status == ReferralAuthStatus.EXPIRING_SOON),
            "expired": sum(1 for a in auths if a.status == ReferralAuthStatus.EXPIRED),
            "exhausted": sum(1 for a in auths if a.status == ReferralAuthStatus.EXHAUSTED),
            "pending_renewal": sum(1 for a in auths if a.status == ReferralAuthStatus.PENDING_RENEWAL),
        }

    async def cancel_auth(self, auth_id: str) -> ReferralAuth:
        auth = await self.get_auth(auth_id)
        if not auth:
            raise ValueError(f"Referral auth {auth_id} not found")
        auth.status = ReferralAuthStatus.CANCELLED
        auth.updated_at = date.today().isoformat()
        await _save_auth(auth)
        return auth

    # ---- Internal ----

    def _compute_status(self, auth: ReferralAuth) -> ReferralAuthStatus:
        if auth.status == ReferralAuthStatus.CANCELLED:
            return ReferralAuthStatus.CANCELLED
        if auth.status == ReferralAuthStatus.PENDING_RENEWAL:
            return ReferralAuthStatus.PENDING_RENEWAL

        # Check exhausted
        if auth.visits_allowed > 0 and auth.visits_used >= auth.visits_allowed:
            return ReferralAuthStatus.EXHAUSTED

        # Check expired
        if auth.end_date:
            try:
                end = date.fromisoformat(auth.end_date)
                if end < date.today():
                    return ReferralAuthStatus.EXPIRED
            except ValueError:
                pass

        # Check expiring soon: <14 days or <2 visits
        expiring = False
        days = auth.days_until_expiry
        if days is not None and days < 14:
            expiring = True
        if auth.visits_allowed > 0 and auth.visits_remaining < 2:
            expiring = True
        if expiring:
            return ReferralAuthStatus.EXPIRING_SOON

        return ReferralAuthStatus.ACTIVE

    @staticmethod
    def _serialize(auth: ReferralAuth) -> dict:
        d = asdict(auth)
        d["status"] = auth.status.value
        d["visits_remaining"] = auth.visits_remaining
        d["days_until_expiry"] = auth.days_until_expiry
        return d
