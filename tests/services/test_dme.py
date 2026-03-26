"""DME order lifecycle tests — create, workflow transitions, confirmation tokens, dashboard."""

import pytest
import pytest_asyncio

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
    username = f"dmeadmin_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "AdminPass123", "admin")
    token = create_access_token(user["id"], user["username"], user["role"])
    return {"access_token": token}


@pytest_asyncio.fixture()
async def dme_cookies():
    from tests.conftest import _ensure_db
    await _ensure_db()
    import uuid
    from server.auth.users import create_user
    from server.auth.jwt_auth import create_access_token
    username = f"dmeuser_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "DmePass12345", "dme")
    token = create_access_token(user["id"], user["username"], user["role"])
    return {"access_token": token}


VALID_ORDER = {
    "patient_first_name": "John",
    "patient_last_name": "Smith",
    "patient_dob": "1985-03-15",
    "patient_phone": "555-123-4567",
    "equipment_category": "CPAP Supplies",
    "equipment_description": "CPAP mask and tubing replacement",
    "quantity": 1,
}


# ---- Order Creation ----

@pytest.mark.asyncio
async def test_create_dme_order(client, admin_cookies):
    """Public endpoint creates a DME order and returns it with pending status."""
    resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["patient_first_name"] == "John"
    assert data["patient_last_name"] == "Smith"
    assert data["equipment_category"] == "CPAP Supplies"
    assert data["id"]  # UUID assigned


@pytest.mark.asyncio
async def test_create_order_persists_in_list(client, dme_cookies):
    """Created order appears in the orders list."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    list_resp = await client.get("/api/dme/orders", cookies=dme_cookies)
    assert list_resp.status_code == 200
    ids = [o["id"] for o in list_resp.json()]
    assert order_id in ids


@pytest.mark.asyncio
async def test_get_order_by_id(client, dme_cookies):
    """Can retrieve a specific order by ID."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    resp = await client.get(f"/api/dme/orders/{order_id}", cookies=dme_cookies)
    assert resp.status_code == 200
    assert resp.json()["id"] == order_id


@pytest.mark.asyncio
async def test_get_nonexistent_order_returns_404(client, dme_cookies):
    resp = await client.get("/api/dme/orders/nonexistent-id", cookies=dme_cookies)
    assert resp.status_code == 404


# ---- Approval / Rejection ----

@pytest.mark.asyncio
async def test_approve_order(client, dme_cookies):
    """Approving an order transitions it to approved status."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/dme/orders/{order_id}/approve",
        json={"notes": "Looks good"},
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_order(client, dme_cookies):
    """Rejecting an order transitions it to rejected status with reason."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/dme/orders/{order_id}/reject",
        json={"reason": "Insurance not eligible"},
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["rejection_reason"] == "Insurance not eligible"


@pytest.mark.asyncio
async def test_approve_nonexistent_order_returns_404(client, dme_cookies):
    resp = await client.post(
        "/api/dme/orders/fake-id/approve", json={}, cookies=dme_cookies
    )
    assert resp.status_code == 404


# ---- Hold / Resume ----

@pytest.mark.asyncio
async def test_hold_and_resume_order(client, dme_cookies):
    """Place an order on hold and resume it."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    hold_resp = await client.post(
        f"/api/dme/orders/{order_id}/hold",
        json={"reason": "Patient unreachable"},
        cookies=dme_cookies,
    )
    assert hold_resp.status_code == 200
    assert hold_resp.json()["status"] == "on_hold"

    resume_resp = await client.post(
        f"/api/dme/orders/{order_id}/resume", cookies=dme_cookies
    )
    assert resume_resp.status_code == 200
    # Resume restores to the status before hold (stored in hold_previous_status)
    assert resume_resp.json()["status"] != "on_hold"


# ---- Fulfillment Flow ----

@pytest.mark.asyncio
async def test_full_fulfillment_flow(client, dme_cookies):
    """Walk an order through approve → mark-ordered → mark-shipped → fulfill."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    # Approve
    await client.post(f"/api/dme/orders/{order_id}/approve", json={}, cookies=dme_cookies)

    # Mark ordered
    resp = await client.post(
        f"/api/dme/orders/{order_id}/mark-ordered",
        json={"vendor_name": "ResMed Direct", "vendor_order_id": "RM-12345"},
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ordering"
    assert resp.json()["vendor_name"] == "ResMed Direct"

    # Mark shipped
    resp = await client.post(
        f"/api/dme/orders/{order_id}/mark-shipped",
        json={"tracking_number": "1Z999AA10", "carrier": "UPS"},
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "shipped"

    # Fulfill
    resp = await client.post(f"/api/dme/orders/{order_id}/fulfill", cookies=dme_cookies)
    assert resp.status_code == 200
    assert resp.json()["status"] == "fulfilled"


# ---- Patient Confirmation Token ----

@pytest.mark.asyncio
async def test_confirmation_token_flow(client, dme_cookies):
    """Generate a token, validate it publicly, and submit patient confirmation."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    # Approve first (required for sending confirmation)
    await client.post(f"/api/dme/orders/{order_id}/approve", json={}, cookies=dme_cookies)

    # Generate confirmation token
    resp = await client.post(
        f"/api/dme/orders/{order_id}/send-confirmation",
        json={"send_via": "sms"},
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    token = resp.json()["order"]["confirmation_token"]
    assert token  # Token was generated
    assert resp.json()["order"]["status"] == "patient_contacted"

    # Validate token (PUBLIC endpoint — no cookies)
    validate_resp = await client.get(f"/api/dme/confirm/{token}")
    assert validate_resp.status_code == 200
    assert validate_resp.json()["patient_first_name"] == "John"

    # Submit patient confirmation (PUBLIC endpoint)
    confirm_resp = await client.post(
        f"/api/dme/confirm/{token}",
        json={"fulfillment_method": "ship", "address": "123 Main St", "city": "Tampa", "state": "FL", "zip": "33601"},
    )
    assert confirm_resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_token_returns_404(client):
    resp = await client.get("/api/dme/confirm/invalid-token-xyz")
    assert resp.status_code == 404


# ---- Insurance Verification ----

@pytest.mark.asyncio
async def test_verify_insurance(client, dme_cookies):
    """Insurance verification transitions order to verifying/verified."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/dme/orders/{order_id}/verify-insurance", cookies=dme_cookies
    )
    assert resp.status_code == 200
    # Without FHIR connection, falls back to manual verification
    assert "insurance_notes" in resp.json()
    assert resp.json()["insurance_notes"]  # Non-empty notes explaining status


# ---- Encounter Tracking ----

@pytest.mark.asyncio
async def test_update_encounter(client, dme_cookies):
    """Record a patient encounter on an order."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/dme/orders/{order_id}/encounter",
        json={
            "encounter_date": "2026-03-15",
            "encounter_type": "office_visit",
            "encounter_provider": "Dr. Chen",
        },
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["last_encounter_date"] == "2026-03-15"
    assert resp.json()["encounter_current"] is True


# ---- Compliance ----

@pytest.mark.asyncio
async def test_update_compliance(client, dme_cookies):
    """Update compliance data on an order."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/dme/orders/{order_id}/compliance",
        json={"status": "compliant", "avg_hours": 6.5, "days_met": 25, "total_days": 30},
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["compliance_status"] == "compliant"
    assert resp.json()["compliance_avg_hours"] == 6.5


# ---- Documents ----

@pytest.mark.asyncio
async def test_add_and_remove_document(client, dme_cookies):
    """Attach a document to an order, then remove it."""
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]

    # Add document
    add_resp = await client.post(
        f"/api/dme/orders/{order_id}/documents",
        json={"filename": "rx_scan.pdf", "document_type": "rx"},
        cookies=dme_cookies,
    )
    assert add_resp.status_code == 200
    docs = add_resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "rx_scan.pdf"
    doc_id = docs[0]["id"]

    # Remove document
    rm_resp = await client.delete(
        f"/api/dme/orders/{order_id}/documents/{doc_id}", cookies=dme_cookies
    )
    assert rm_resp.status_code == 200
    assert len(rm_resp.json()["documents"]) == 0


# ---- Dashboard ----

@pytest.mark.asyncio
async def test_dme_dashboard(client, dme_cookies):
    """Dashboard returns status counts."""
    resp = await client.get("/api/dme/dashboard", cookies=dme_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "pending" in data or "approved" in data  # Status breakdown keys


# ---- Queue Endpoints ----

@pytest.mark.asyncio
async def test_queue_endpoints_return_lists(client, dme_cookies):
    """All queue filter endpoints return 200 with list results."""
    endpoints = [
        "/api/dme/orders/auto-replace-due",
        "/api/dme/orders/incoming",
        "/api/dme/orders/auto-refill-pending",
        "/api/dme/orders/in-progress",
        "/api/dme/orders/awaiting-patient",
        "/api/dme/orders/patient-confirmed",
        "/api/dme/orders/on-hold",
        "/api/dme/orders/encounter-expired",
    ]
    for ep in endpoints:
        resp = await client.get(ep, cookies=dme_cookies)
        assert resp.status_code == 200, f"Failed: {ep}"
        assert isinstance(resp.json(), list), f"Not a list: {ep}"


# ---- Static Reference Endpoints ----

@pytest.mark.asyncio
async def test_encounter_types_endpoint(client):
    """Public encounter types endpoint returns available types."""
    resp = await client.get("/api/dme/encounter-types")
    assert resp.status_code == 200
    assert "types" in resp.json()


@pytest.mark.asyncio
async def test_equipment_categories_endpoint(client):
    """Public equipment categories endpoint returns categories and bundles."""
    resp = await client.get("/api/dme/equipment-categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "bundles" in data
    assert "hcpcs_map" in data


# ---- Status Filter ----

@pytest.mark.asyncio
async def test_list_orders_with_status_filter(client, dme_cookies):
    """Filtering orders by status works."""
    # Create and approve an order
    create_resp = await client.post("/api/dme/orders", json=VALID_ORDER)
    order_id = create_resp.json()["id"]
    await client.post(f"/api/dme/orders/{order_id}/approve", json={}, cookies=dme_cookies)

    # Filter by approved
    resp = await client.get("/api/dme/orders?status=approved", cookies=dme_cookies)
    assert resp.status_code == 200
    for order in resp.json():
        assert order["status"] == "approved"
