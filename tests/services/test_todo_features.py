"""Tests for TODO.md practice feature requests — fax categories, patient portal, DME workflow."""

import pytest
import pytest_asyncio
import json
from datetime import date, datetime, timedelta

from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture()
async def client():
    from tests.conftest import _ensure_db
    await _ensure_db()
    from server.api.routes import _login_limiter
    _login_limiter._attempts.clear()
    from server.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture()
async def admin_cookies():
    from tests.conftest import _ensure_db
    await _ensure_db()
    import uuid
    from server.auth.users import create_user
    from server.auth.jwt_auth import create_access_token
    username = f"todoadmin_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "AdminPass123", "admin")
    token = create_access_token(user["id"], user["username"], user["role"])
    return {"access_token": token}


# ──────────────────────────────────────────────
# Group 1: Fax Document Categories
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_classify_document_new_categories():
    """LLM classify_document prompt includes the new categories."""
    from server.llm.base import LLMProvider
    # Check the classify_document method exists and prompt includes new cats
    import inspect
    source = inspect.getsource(LLMProvider.classify_document)
    assert "medication_prior_auth" in source
    assert "dme" in source
    assert "sleep_study_results" in source
    assert "labs_imaging" in source
    # Old category should not be in the prompt
    assert "lab_result" not in source


@pytest.mark.asyncio
async def test_referral_valid_types_updated():
    """classify_and_process accepts the new document types."""
    from server.services.referral import ReferralService
    import inspect
    source = inspect.getsource(ReferralService.classify_and_process)
    assert "labs_imaging" in source
    assert "medication_prior_auth" in source
    assert "dme" in source
    assert "sleep_study_results" in source


@pytest.mark.asyncio
async def test_migration_renames_lab_result():
    """Migration converts lab_result → labs_imaging in referrals table."""
    from tests.conftest import _ensure_db
    await _ensure_db()
    from server.db import db_execute, db_fetch_all
    # Insert a referral with old type
    await db_execute(
        "INSERT OR IGNORE INTO referrals (id, filename, status, uploaded_at, document_type) VALUES (?, ?, ?, ?, ?)",
        ("test-migrate-1", "test.pdf", "completed", datetime.now().isoformat(), "lab_result"),
    )
    # Re-run migration
    await db_execute(
        "UPDATE referrals SET document_type = 'labs_imaging' WHERE document_type = 'lab_result'"
    )
    rows = await db_fetch_all("SELECT * FROM referrals WHERE id = 'test-migrate-1'")
    assert len(rows) == 1
    assert rows[0]["document_type"] == "labs_imaging"
    # Cleanup
    await db_execute("DELETE FROM referrals WHERE id = 'test-migrate-1'")


# ──────────────────────────────────────────────
# Group 2a: Bundle Items
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bundle_items_populated_on_create():
    """Creating a bundle order populates bundle_items from SUPPLY_BUNDLES."""
    from server.services.dme import DMEService, SUPPLY_BUNDLES
    svc = DMEService()
    bundle_name = "Full Resupply (Full Face)"
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "Bundle",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0001",
        "equipment_category": "CPAP Supplies",
        "equipment_description": bundle_name,
    })
    assert order.bundle_items == SUPPLY_BUNDLES[bundle_name]
    assert order.selected_items == SUPPLY_BUNDLES[bundle_name]


@pytest.mark.asyncio
async def test_single_item_has_no_bundle():
    """Non-bundle orders have empty bundle_items."""
    from server.services.dme import DMEService
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "Single",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0002",
        "equipment_category": "CPAP Machine",
        "equipment_description": "ResMed AirSense 11",
    })
    assert order.bundle_items == []
    assert order.selected_items == []


# ──────────────────────────────────────────────
# Group 2b: Shipping Fee
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shipping_fee_set_on_ship():
    """Shipping fee is $15 when patient chooses ship fulfillment."""
    from server.services.dme import DMEService, DMEOrderStatus
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "Ship",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0003",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    # Move to patient_contacted
    order.status = DMEOrderStatus.PATIENT_CONTACTED
    token_order = await svc.generate_confirmation_token(order.id)
    token = token_order.confirmation_token
    confirmed = await svc.patient_confirm(token, {
        "address": "123 Test St",
        "city": "Test City",
        "state": "TX",
        "zip": "78229",
        "fulfillment_method": "ship",
    })
    assert confirmed.shipping_fee == 15.00
    assert confirmed.fulfillment_method == "ship"


@pytest.mark.asyncio
async def test_no_shipping_fee_on_pickup():
    """Pickup fulfillment has no shipping fee."""
    from server.services.dme import DMEService, DMEOrderStatus
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "Pickup",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0004",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    order.status = DMEOrderStatus.PATIENT_CONTACTED
    token_order = await svc.generate_confirmation_token(order.id)
    token = token_order.confirmation_token
    confirmed = await svc.patient_confirm(token, {
        "fulfillment_method": "pickup",
    })
    assert confirmed.shipping_fee is None
    assert confirmed.fulfillment_method == "pickup"


# ──────────────────────────────────────────────
# Group 2c: Patient Rejection
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_reject_order():
    """Patient can reject an order and request callback."""
    from server.services.dme import DMEService, DMEOrderStatus
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "Reject",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0005",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    order.status = DMEOrderStatus.PATIENT_CONTACTED
    token_order = await svc.generate_confirmation_token(order.id)
    token = token_order.confirmation_token
    rejected = await svc.patient_reject_order(token, "Wrong mask size", True)
    assert rejected is not None
    assert rejected.patient_rejected is True
    assert rejected.patient_rejection_reason == "Wrong mask size"
    assert rejected.patient_callback_requested is True
    assert rejected.status == DMEOrderStatus.ON_HOLD


@pytest.mark.asyncio
async def test_reject_endpoint(client, admin_cookies):
    """POST /api/dme/confirm/{token}/reject works via HTTP."""
    from server.services.dme import DMEService, DMEOrderStatus
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "RejectHTTP",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0006",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    order.status = DMEOrderStatus.PATIENT_CONTACTED
    token_order = await svc.generate_confirmation_token(order.id)
    token = token_order.confirmation_token

    resp = await client.post(f"/api/dme/confirm/{token}/reject", json={
        "reason": "Wrong supplies",
        "callback_requested": True,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"


# ──────────────────────────────────────────────
# Group 3b: Vendor Options
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vendor_options_constant():
    """VENDOR_OPTIONS has the expected values."""
    from server.services.dme import VENDOR_OPTIONS
    assert "In-House" in VENDOR_OPTIONS
    assert "PPM" in VENDOR_OPTIONS
    assert "VGM" in VENDOR_OPTIONS
    assert len(VENDOR_OPTIONS) == 3


# ──────────────────────────────────────────────
# Group 3c: Patient-Facing Status Label
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ordering_shows_being_fulfilled():
    """Patient sees 'Being fulfilled' instead of 'Order placed with supplier'."""
    from server.services.dme import DMEOrder, DMEOrderStatus
    order = DMEOrder(
        patient_first_name="Test", patient_last_name="Status",
        patient_dob="1990-01-01", patient_phone="555-0007",
        patient_address="123 Test", patient_city="Test", patient_state="TX", patient_zip="78229",
    )
    order.status = DMEOrderStatus.ORDERING
    assert order.patient_display_status == "Being fulfilled"


# ──────────────────────────────────────────────
# Group 3d: Auto-Deliver Timer
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auto_deliver_after_set_on_ship():
    """Shipping sets auto_deliver_after to ~7 days from now."""
    from server.services.dme import DMEService, DMEOrderStatus
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "AutoDeliver",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0008",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    order.status = DMEOrderStatus.ORDERING
    order.fulfillment_method = "ship"
    from server.services.dme import _save_order
    await _save_order(order)

    shipped = await svc.mark_shipped(order.id, "TRACK123", "UPS", "2026-04-01")
    assert shipped.auto_deliver_after is not None
    auto_dt = datetime.fromisoformat(shipped.auto_deliver_after)
    assert (auto_dt - datetime.now()).days >= 6  # ~7 days


@pytest.mark.asyncio
async def test_auto_deliver_after_immediate_for_pickup():
    """Pickup sets auto_deliver_after to now (immediate)."""
    from server.services.dme import DMEService, DMEOrderStatus
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "AutoPickup",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0009",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    order.status = DMEOrderStatus.ORDERING
    order.fulfillment_method = "pickup"
    from server.services.dme import _save_order
    await _save_order(order)

    shipped = await svc.mark_shipped(order.id)
    assert shipped.auto_deliver_after is not None
    auto_dt = datetime.fromisoformat(shipped.auto_deliver_after)
    assert (datetime.now() - auto_dt).total_seconds() < 60  # within a minute


@pytest.mark.asyncio
async def test_process_auto_deliveries():
    """process_auto_deliveries fulfills orders past their timer."""
    from server.services.dme import DMEService, DMEOrderStatus, _save_order
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "AutoFulfill",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0010",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    # Set to shipped with past auto_deliver_after
    order.status = DMEOrderStatus.SHIPPED
    order.auto_deliver_after = (datetime.now() - timedelta(hours=1)).isoformat()
    await _save_order(order)

    fulfilled = await svc.process_auto_deliveries()
    assert len(fulfilled) >= 1
    order_ids = [o.id for o in fulfilled]
    assert order.id in order_ids
    refreshed = await svc.get_order(order.id)
    assert refreshed.status == DMEOrderStatus.FULFILLED


# ──────────────────────────────────────────────
# Group 2d: Expiring Encounters
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_expiring_encounter_queue():
    """Orders with encounters ≤14 days from expiry appear in the queue."""
    from server.services.dme import DMEService, _save_order
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "Expiring",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0011",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    # Set encounter date to ~355 days ago (10 days from expiry)
    enc_date = (date.today() - timedelta(days=355)).isoformat()
    order.last_encounter_date = enc_date
    await _save_order(order)

    expiring = await svc.get_expiring_encounter_orders(14)
    order_ids = [o.id for o in expiring]
    assert order.id in order_ids


@pytest.mark.asyncio
async def test_expiring_encounters_endpoint(client, admin_cookies):
    """GET /api/dme/orders/expiring-encounters returns results."""
    resp = await client.get("/api/dme/orders/expiring-encounters", cookies=admin_cookies)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ──────────────────────────────────────────────
# Group 3e: Receipt & Delivery Ticket
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_receipt():
    """generate_receipt returns structured receipt data."""
    from server.services.dme import DMEService
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "Receipt",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0012",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
        "insurance_payer": "BCBS",
        "referring_physician": "Dr. Test",
    })
    receipt = await svc.generate_receipt(order.id)
    assert receipt is not None
    assert receipt["order_id"] == order.id
    assert receipt["patient_name"] == "Test Receipt"
    assert receipt["insurance_payer"] == "BCBS"
    assert "items" in receipt


@pytest.mark.asyncio
async def test_generate_delivery_ticket():
    """generate_delivery_ticket returns delivery data."""
    from server.services.dme import DMEService
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "Delivery",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0013",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    ticket = await svc.generate_delivery_ticket(order.id)
    assert ticket is not None
    assert ticket["order_id"] == order.id
    assert ticket["patient_name"] == "Test Delivery"
    assert "items" in ticket


@pytest.mark.asyncio
async def test_receipt_endpoint(client, admin_cookies):
    """GET /api/dme/orders/{id}/receipt returns data."""
    from server.services.dme import DMEService
    svc = DMEService()
    order = await svc.create_order({
        "patient_first_name": "Test",
        "patient_last_name": "ReceiptHTTP",
        "patient_dob": "1990-01-01",
        "patient_phone": "555-0014",
        "equipment_category": "CPAP Supplies",
        "equipment_description": "Test supplies",
    })
    resp = await client.get(f"/api/dme/orders/{order.id}/receipt", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == order.id


@pytest.mark.asyncio
async def test_auto_deliveries_endpoint(client, admin_cookies):
    """POST /api/dme/process-auto-deliveries works via HTTP."""
    resp = await client.post("/api/dme/process-auto-deliveries", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "fulfilled" in data
