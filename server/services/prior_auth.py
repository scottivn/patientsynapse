"""Prior Authorization tracking for DME orders.

Determines whether a DME order requires payer prior-authorization,
tracks the request lifecycle (pending → submitted → approved/denied),
and gates the DME approval workflow.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Optional, List

from server.db import db_execute, db_fetch_one, db_fetch_all

logger = logging.getLogger(__name__)


class PriorAuthStatus(str, Enum):
    PENDING = "pending"            # Created, not yet submitted to payer
    SUBMITTED = "submitted"        # Sent to payer, awaiting decision
    APPROVED = "approved"          # Payer approved
    DENIED = "denied"              # Payer denied
    EXPIRED = "expired"            # Was approved but valid_until has passed
    NOT_REQUIRED = "not_required"  # System determined auth not needed


# ── Auth-required rules ──────────────────────────────────────────

# HCPCS codes that require prior-auth by insurance type.
# "all" means every DME HCPCS needs auth for that insurance type.
PRIOR_AUTH_RULES: dict[str, set | str] = {
    # Medicare: requires auth for CPAP machines after initial 90-day trial
    "medicare": {"E0601", "E0470"},
    # HMO: requires auth for ALL DME
    "hmo": "all",
    # POS: same as HMO
    "pos": "all",
    # EPO: machines only, not supplies
    "epo": {"E0601", "E0470"},
    # PPO: typically not required for standard CPAP supplies
    "ppo": set(),
}


@dataclass
class PriorAuthRequest:
    dme_order_id: str
    patient_id: str = ""
    patient_first_name: str = ""
    patient_last_name: str = ""
    payer_name: str = ""
    payer_member_id: str = ""
    insurance_type: str = ""
    auth_number: str = ""
    status: PriorAuthStatus = PriorAuthStatus.PENDING
    diagnosis_codes: list = field(default_factory=list)
    hcpcs_codes: list = field(default_factory=list)
    request_date: Optional[str] = None
    submitted_date: Optional[str] = None
    decision_date: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    denial_reason: str = ""
    submission_notes: str = ""
    staff_notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def days_until_expiry(self) -> Optional[int]:
        if not self.valid_until:
            return None
        try:
            end = date.fromisoformat(self.valid_until)
            return (end - date.today()).days
        except ValueError:
            return None

    @property
    def is_blocking(self) -> bool:
        """Returns True if this auth prevents order fulfillment."""
        return self.status in (
            PriorAuthStatus.PENDING,
            PriorAuthStatus.SUBMITTED,
            PriorAuthStatus.DENIED,
        )


def _row_to_auth(row: dict) -> PriorAuthRequest:
    return PriorAuthRequest(
        id=row["id"],
        dme_order_id=row["dme_order_id"],
        patient_id=row.get("patient_id", ""),
        patient_first_name=row.get("patient_first_name", ""),
        patient_last_name=row.get("patient_last_name", ""),
        payer_name=row.get("payer_name", ""),
        payer_member_id=row.get("payer_member_id", ""),
        insurance_type=row.get("insurance_type", ""),
        auth_number=row.get("auth_number", ""),
        status=PriorAuthStatus(row.get("status", "pending")),
        diagnosis_codes=json.loads(row.get("diagnosis_codes", "[]")),
        hcpcs_codes=json.loads(row.get("hcpcs_codes", "[]")),
        request_date=row.get("request_date"),
        submitted_date=row.get("submitted_date"),
        decision_date=row.get("decision_date"),
        valid_from=row.get("valid_from"),
        valid_until=row.get("valid_until"),
        denial_reason=row.get("denial_reason", ""),
        submission_notes=row.get("submission_notes", ""),
        staff_notes=row.get("staff_notes", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


async def _save_auth(auth: PriorAuthRequest) -> None:
    await db_execute(
        """INSERT INTO prior_auth_requests
               (id, dme_order_id, patient_id, patient_first_name, patient_last_name,
                payer_name, payer_member_id, insurance_type, auth_number, status,
                diagnosis_codes, hcpcs_codes, request_date, submitted_date,
                decision_date, valid_from, valid_until, denial_reason,
                submission_notes, staff_notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               auth_number=excluded.auth_number, status=excluded.status,
               submitted_date=excluded.submitted_date, decision_date=excluded.decision_date,
               valid_from=excluded.valid_from, valid_until=excluded.valid_until,
               denial_reason=excluded.denial_reason, submission_notes=excluded.submission_notes,
               staff_notes=excluded.staff_notes, updated_at=excluded.updated_at""",
        (auth.id, auth.dme_order_id, auth.patient_id,
         auth.patient_first_name, auth.patient_last_name,
         auth.payer_name, auth.payer_member_id, auth.insurance_type,
         auth.auth_number, auth.status.value,
         json.dumps(auth.diagnosis_codes), json.dumps(auth.hcpcs_codes),
         auth.request_date, auth.submitted_date, auth.decision_date,
         auth.valid_from, auth.valid_until, auth.denial_reason,
         auth.submission_notes, auth.staff_notes,
         auth.created_at, auth.updated_at),
    )


def _detect_insurance_type(payer_name: str) -> str:
    """Heuristic insurance type detection from payer name string."""
    name = (payer_name or "").lower()
    if "medicare" in name:
        return "medicare"
    if "hmo" in name:
        return "hmo"
    if "ppo" in name:
        return "ppo"
    if "pos" in name:
        return "pos"
    if "epo" in name:
        return "epo"
    # Common HMO payer patterns
    if any(kw in name for kw in ["kaiser", "health net hmo"]):
        return "hmo"
    return "unknown"


class PriorAuthService:
    """Manages prior authorization requests for DME orders."""

    def __init__(self, fhir_client=None):
        self._fhir_client = fhir_client

    def set_fhir_client(self, fhir_client):
        self._fhir_client = fhir_client

    # ── Auth requirement check ──────────────────────────────────

    async def check_auth_required(self, order_id: str) -> dict:
        """Determine if a DME order requires prior authorization.

        Uses insurance type + HCPCS codes to check against payer rules.
        Returns {"required": bool, "reason": str, "insurance_type": str}.
        """
        order = await db_fetch_one(
            "SELECT * FROM dme_orders WHERE id = ?", (order_id,)
        )
        if not order:
            raise ValueError(f"Order {order_id} not found")

        payer = order.get("insurance_payer", "")
        hcpcs_raw = order.get("hcpcs_codes", "[]")
        hcpcs_codes = json.loads(hcpcs_raw) if isinstance(hcpcs_raw, str) else hcpcs_raw

        # Try FHIR Coverage for insurance type detection first
        ins_type = "unknown"
        patient_id = order.get("patient_id", "")
        if self._fhir_client and patient_id:
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
                            for itype in ["hmo", "ppo", "pos", "epo"]:
                                if itype in code_lower or itype in display_lower:
                                    ins_type = itype
                                    break
                            if ins_type != "unknown":
                                break
                    if ins_type == "unknown" and cov.payor:
                        for payor_ref in cov.payor:
                            display = (payor_ref.display or "").lower()
                            detected = _detect_insurance_type(display)
                            if detected != "unknown":
                                ins_type = detected
                                break
                    if ins_type != "unknown":
                        break
            except Exception as e:
                logger.warning(f"FHIR insurance type detection failed: {e}")

        # Fallback to payer name heuristic
        if ins_type == "unknown":
            ins_type = _detect_insurance_type(payer)

        # Check rules
        rules = PRIOR_AUTH_RULES.get(ins_type)
        if rules is None:
            return {
                "required": False,
                "reason": f"No prior-auth rules for insurance type '{ins_type}'",
                "insurance_type": ins_type,
            }

        if rules == "all":
            return {
                "required": True,
                "reason": f"{ins_type.upper()} insurance requires prior authorization for all DME",
                "insurance_type": ins_type,
            }

        if isinstance(rules, set) and hcpcs_codes:
            matching = set(hcpcs_codes) & rules
            if matching:
                return {
                    "required": True,
                    "reason": f"{ins_type.upper()} insurance requires prior authorization for HCPCS: {', '.join(sorted(matching))}",
                    "insurance_type": ins_type,
                }

        return {
            "required": False,
            "reason": f"Prior authorization not required for this equipment under {ins_type.upper()}",
            "insurance_type": ins_type,
        }

    # ── CRUD ────────────────────────────────────────────────────

    async def create_auth_request(self, order_id: str) -> PriorAuthRequest:
        """Create a prior-auth request from a DME order."""
        order = await db_fetch_one(
            "SELECT * FROM dme_orders WHERE id = ?", (order_id,)
        )
        if not order:
            raise ValueError(f"Order {order_id} not found")

        # Check if one already exists and is active
        existing = await self.get_auth_for_order(order_id)
        if existing and existing.status in (PriorAuthStatus.PENDING, PriorAuthStatus.SUBMITTED):
            raise ValueError(
                f"Active prior-auth request already exists for order {order_id} "
                f"(status: {existing.status.value})"
            )

        hcpcs_raw = order.get("hcpcs_codes", "[]")
        hcpcs_codes = json.loads(hcpcs_raw) if isinstance(hcpcs_raw, str) else hcpcs_raw

        diag_code = order.get("diagnosis_code", "")
        diagnosis_codes = [diag_code] if diag_code else []

        ins_type = _detect_insurance_type(order.get("insurance_payer", ""))

        auth = PriorAuthRequest(
            dme_order_id=order_id,
            patient_id=order.get("patient_id", ""),
            patient_first_name=order.get("patient_first_name", ""),
            patient_last_name=order.get("patient_last_name", ""),
            payer_name=order.get("insurance_payer", ""),
            payer_member_id=order.get("insurance_member_id", ""),
            insurance_type=ins_type,
            diagnosis_codes=diagnosis_codes,
            hcpcs_codes=hcpcs_codes,
            request_date=date.today().isoformat(),
        )
        await _save_auth(auth)
        logger.info(f"Prior auth {auth.id} created for order {order_id}")
        return auth

    async def get_auth(self, auth_id: str) -> Optional[PriorAuthRequest]:
        row = await db_fetch_one(
            "SELECT * FROM prior_auth_requests WHERE id = ?", (auth_id,)
        )
        if not row:
            return None
        auth = _row_to_auth(row)
        # Auto-expire
        if auth.status == PriorAuthStatus.APPROVED:
            days = auth.days_until_expiry
            if days is not None and days < 0:
                auth.status = PriorAuthStatus.EXPIRED
                auth.updated_at = datetime.now().isoformat()
                await _save_auth(auth)
        return auth

    async def get_auth_for_order(self, order_id: str) -> Optional[PriorAuthRequest]:
        """Get the most recent prior-auth request for an order."""
        row = await db_fetch_one(
            "SELECT * FROM prior_auth_requests WHERE dme_order_id = ? ORDER BY created_at DESC LIMIT 1",
            (order_id,),
        )
        if not row:
            return None
        auth = _row_to_auth(row)
        # Auto-expire
        if auth.status == PriorAuthStatus.APPROVED:
            days = auth.days_until_expiry
            if days is not None and days < 0:
                auth.status = PriorAuthStatus.EXPIRED
                auth.updated_at = datetime.now().isoformat()
                await _save_auth(auth)
        return auth

    async def get_auths_for_orders(self, order_ids: list[str]) -> dict[str, dict]:
        """Batch-fetch prior-auth data for multiple orders. Returns {order_id: serialized_auth}."""
        if not order_ids:
            return {}
        placeholders = ",".join("?" for _ in order_ids)
        rows = await db_fetch_all(
            f"""SELECT * FROM prior_auth_requests
                WHERE dme_order_id IN ({placeholders})
                ORDER BY created_at DESC""",
            tuple(order_ids),
        )
        # Keep only the most recent per order
        result = {}
        for row in rows:
            oid = row["dme_order_id"]
            if oid not in result:
                auth = _row_to_auth(row)
                result[oid] = self._serialize(auth)
        return result

    # ── State transitions ───────────────────────────────────────

    async def submit_auth(self, auth_id: str, submission_notes: str = "") -> PriorAuthRequest:
        """Mark auth as submitted to payer."""
        auth = await self.get_auth(auth_id)
        if not auth:
            raise ValueError(f"Prior auth {auth_id} not found")
        if auth.status != PriorAuthStatus.PENDING:
            raise ValueError(
                f"Can only submit a pending auth (current: {auth.status.value})"
            )
        auth.status = PriorAuthStatus.SUBMITTED
        auth.submitted_date = date.today().isoformat()
        if submission_notes:
            auth.submission_notes = submission_notes
        auth.updated_at = datetime.now().isoformat()
        await _save_auth(auth)
        logger.info(f"Prior auth {auth_id} submitted to payer")
        return auth

    async def record_decision(
        self,
        auth_id: str,
        approved: bool,
        auth_number: str = "",
        valid_from: str = "",
        valid_until: str = "",
        denial_reason: str = "",
        staff_notes: str = "",
    ) -> PriorAuthRequest:
        """Record payer decision (approval or denial)."""
        auth = await self.get_auth(auth_id)
        if not auth:
            raise ValueError(f"Prior auth {auth_id} not found")
        if auth.status not in (PriorAuthStatus.PENDING, PriorAuthStatus.SUBMITTED):
            raise ValueError(
                f"Can only record decision on pending/submitted auth (current: {auth.status.value})"
            )

        auth.decision_date = date.today().isoformat()
        if approved:
            auth.status = PriorAuthStatus.APPROVED
            auth.auth_number = auth_number
            if valid_from:
                auth.valid_from = valid_from
            if valid_until:
                auth.valid_until = valid_until
        else:
            auth.status = PriorAuthStatus.DENIED
            auth.denial_reason = denial_reason

        if staff_notes:
            auth.staff_notes = (auth.staff_notes + "\n" + staff_notes).strip()
        auth.updated_at = datetime.now().isoformat()
        await _save_auth(auth)
        logger.info(f"Prior auth {auth_id}: {'approved' if approved else 'denied'}")
        return auth

    # ── Queries ─────────────────────────────────────────────────

    async def list_pending(self) -> List[PriorAuthRequest]:
        """All pending/submitted auths needing follow-up."""
        rows = await db_fetch_all(
            "SELECT * FROM prior_auth_requests WHERE status IN ('pending', 'submitted') ORDER BY created_at ASC"
        )
        return [_row_to_auth(r) for r in rows]

    async def get_expiring(self, days: int = 14) -> List[PriorAuthRequest]:
        """Approved auths expiring within N days."""
        rows = await db_fetch_all(
            "SELECT * FROM prior_auth_requests WHERE status = 'approved' AND valid_until IS NOT NULL"
        )
        result = []
        for row in rows:
            auth = _row_to_auth(row)
            d = auth.days_until_expiry
            if d is not None and 0 <= d <= days:
                result.append(auth)
        return sorted(result, key=lambda a: a.valid_until or "9999")

    async def can_fulfill(self, order_id: str) -> dict:
        """Check if a DME order can proceed past approval.

        Returns {"can_proceed": bool, "reason": str, "auth": dict|None}.
        If no auth request exists, the order can proceed (auth not required).
        """
        auth = await self.get_auth_for_order(order_id)
        if not auth:
            return {"can_proceed": True, "reason": "No prior authorization required", "auth": None}

        if auth.status == PriorAuthStatus.NOT_REQUIRED:
            return {"can_proceed": True, "reason": "Prior authorization not required", "auth": self._serialize(auth)}

        if auth.status == PriorAuthStatus.APPROVED:
            # Check expiry
            days = auth.days_until_expiry
            if days is not None and days < 0:
                auth.status = PriorAuthStatus.EXPIRED
                auth.updated_at = datetime.now().isoformat()
                await _save_auth(auth)
                return {
                    "can_proceed": False,
                    "reason": f"Prior authorization expired on {auth.valid_until}",
                    "auth": self._serialize(auth),
                }
            return {"can_proceed": True, "reason": "Prior authorization approved", "auth": self._serialize(auth)}

        if auth.status == PriorAuthStatus.EXPIRED:
            return {
                "can_proceed": False,
                "reason": f"Prior authorization expired on {auth.valid_until}",
                "auth": self._serialize(auth),
            }

        if auth.status == PriorAuthStatus.DENIED:
            return {
                "can_proceed": False,
                "reason": f"Prior authorization denied: {auth.denial_reason or 'no reason provided'}",
                "auth": self._serialize(auth),
            }

        # PENDING or SUBMITTED
        return {
            "can_proceed": False,
            "reason": f"Prior authorization {auth.status.value} — awaiting payer decision",
            "auth": self._serialize(auth),
        }

    async def get_dashboard(self) -> dict:
        """Summary counts for prior-auth requests."""
        rows = await db_fetch_all("SELECT status, COUNT(*) as cnt FROM prior_auth_requests GROUP BY status")
        counts = {r["status"]: r["cnt"] for r in rows}
        return {
            "total": sum(counts.values()),
            "pending": counts.get("pending", 0),
            "submitted": counts.get("submitted", 0),
            "approved": counts.get("approved", 0),
            "denied": counts.get("denied", 0),
            "expired": counts.get("expired", 0),
        }

    # ── Serialization ───────────────────────────────────────────

    @staticmethod
    def _serialize(auth: PriorAuthRequest) -> dict:
        d = asdict(auth)
        d["status"] = auth.status.value
        d["days_until_expiry"] = auth.days_until_expiry
        d["is_blocking"] = auth.is_blocking
        return d
