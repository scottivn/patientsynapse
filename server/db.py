"""Centralized database schema and helpers for PatientSynapse.

All business-entity tables are defined here. Auth tables (admin_users,
phi_audit_log) remain in server/auth/users.py for backward compatibility.
"""

import json
import logging
from typing import Optional

import aiosqlite

from server.config import get_settings

logger = logging.getLogger(__name__)


def _get_db_path() -> str:
    settings = get_settings()
    return settings.database_url.replace("sqlite:///", "")


async def init_all_tables():
    """Create all business-entity tables. Call once at startup after init_db()."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        # ── Referrals ──────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                uploaded_at TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT 'referral',
                extracted_data TEXT,
                patient_id TEXT,
                service_request_id TEXT,
                error TEXT,
                reviewed_by TEXT,
                completed_at TEXT,
                raw_text TEXT
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status)"
        )

        # ── DME Orders ─────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dme_orders (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                patient_first_name TEXT NOT NULL,
                patient_last_name TEXT NOT NULL,
                patient_dob TEXT NOT NULL DEFAULT '',
                patient_phone TEXT NOT NULL DEFAULT '',
                patient_email TEXT NOT NULL DEFAULT '',
                patient_address TEXT NOT NULL DEFAULT '',
                patient_city TEXT NOT NULL DEFAULT '',
                patient_state TEXT NOT NULL DEFAULT '',
                patient_zip TEXT NOT NULL DEFAULT '',
                patient_id TEXT NOT NULL DEFAULT '',
                insurance_payer TEXT NOT NULL DEFAULT '',
                insurance_member_id TEXT NOT NULL DEFAULT '',
                insurance_group TEXT NOT NULL DEFAULT '',
                equipment_category TEXT NOT NULL DEFAULT '',
                equipment_description TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 1,
                diagnosis_code TEXT NOT NULL DEFAULT '',
                diagnosis_description TEXT NOT NULL DEFAULT '',
                referring_physician TEXT NOT NULL DEFAULT '',
                referring_npi TEXT NOT NULL DEFAULT '',
                clinical_notes TEXT NOT NULL DEFAULT '',
                last_encounter_date TEXT,
                last_encounter_type TEXT,
                last_encounter_provider TEXT,
                last_encounter_provider_npi TEXT,
                origin TEXT NOT NULL DEFAULT 'staff_initiated',
                parent_order_id TEXT,
                auto_replace INTEGER NOT NULL DEFAULT 0,
                auto_replace_frequency TEXT,
                next_replace_date TEXT,
                compliance_status TEXT NOT NULL DEFAULT 'unknown',
                compliance_avg_hours REAL,
                compliance_days_met INTEGER,
                compliance_total_days INTEGER,
                compliance_last_checked TEXT,
                documents TEXT NOT NULL DEFAULT '[]',
                hcpcs_codes TEXT NOT NULL DEFAULT '[]',
                expected_reimbursement REAL,
                supply_months INTEGER NOT NULL DEFAULT 6,
                pricing_details TEXT NOT NULL DEFAULT '[]',
                confirmation_token TEXT,
                confirmation_token_expires TEXT,
                confirmation_sent_at TEXT,
                confirmation_sent_via TEXT,
                confirmation_responded_at TEXT,
                patient_confirmed_address INTEGER NOT NULL DEFAULT 0,
                patient_notes TEXT NOT NULL DEFAULT '',
                fulfillment_method TEXT NOT NULL DEFAULT 'not_selected',
                shipping_fee REAL,
                shipping_tracking_number TEXT,
                shipping_carrier TEXT,
                vendor_name TEXT,
                vendor_order_id TEXT,
                vendor_ordered_at TEXT,
                estimated_delivery_date TEXT,
                pickup_ready_date TEXT,
                fulfilled_at TEXT,
                assigned_to TEXT,
                staff_notes TEXT NOT NULL DEFAULT '',
                hold_reason TEXT NOT NULL DEFAULT '',
                insurance_verified INTEGER,
                insurance_notes TEXT NOT NULL DEFAULT '',
                rejection_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_dme_status ON dme_orders(status)"
        )
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_dme_token ON dme_orders(confirmation_token) WHERE confirmation_token IS NOT NULL"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_dme_auto_replace ON dme_orders(auto_replace, status, next_replace_date)"
        )

        # ── Referral Authorizations ────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referral_auths (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                patient_first_name TEXT NOT NULL,
                patient_last_name TEXT NOT NULL,
                insurance_name TEXT NOT NULL DEFAULT '',
                insurance_type TEXT NOT NULL DEFAULT 'unknown',
                insurance_member_id TEXT NOT NULL DEFAULT '',
                insurance_npi TEXT NOT NULL DEFAULT '',
                copay TEXT NOT NULL DEFAULT '',
                referral_number TEXT NOT NULL DEFAULT '',
                referring_pcp_name TEXT NOT NULL DEFAULT '',
                referring_pcp_npi TEXT NOT NULL DEFAULT '',
                referring_pcp_phone TEXT NOT NULL DEFAULT '',
                referring_pcp_fax TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                visits_allowed INTEGER NOT NULL DEFAULT 0,
                visits_used INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT NOT NULL DEFAULT '',
                renewal_requested_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_status ON referral_auths(status)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_patient ON referral_auths(patient_id)"
        )

        # ── Prescriptions ──────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prescriptions (
                id TEXT PRIMARY KEY,
                patient_ref TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                author_npi TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'detected',
                raw_text TEXT NOT NULL DEFAULT '',
                extracted_data TEXT,
                dme_order_id TEXT,
                error TEXT,
                detected_at TEXT NOT NULL,
                processed_at TEXT
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_rx_status ON prescriptions(status)"
        )

        # ── Fax processing tracker ─────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fax_processed (
                filename TEXT PRIMARY KEY,
                referral_id TEXT NOT NULL,
                processed_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        await db.commit()
    logger.info("Business entity tables initialized")


# ── Generic helpers ─────────────────────────────────────────────

async def db_execute(sql: str, params: tuple = ()) -> aiosqlite.Cursor:
    """Execute a write query (INSERT/UPDATE/DELETE) and commit."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(sql, params)
        await db.commit()
        return cursor


async def db_fetch_one(sql: str, params: tuple = ()) -> Optional[dict]:
    """Fetch a single row as a dict."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def db_fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    """Fetch all rows as dicts."""
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
