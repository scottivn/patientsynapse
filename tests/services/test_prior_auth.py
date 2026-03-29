"""Tests for DME Prior Authorization tracking."""

import pytest
import pytest_asyncio

VALID_ORDER = {
    "patient_first_name": "Alice",
    "patient_last_name": "Johnson",
    "patient_dob": "1970-05-20",
    "patient_phone": "555-999-0001",
    "equipment_category": "CPAP Machine",
    "equipment_description": "CPAP unit E0601",
    "hcpcs_codes": ["E0601"],
    "insurance_payer": "Aetna HMO",
    "diagnosis_code": "G47.33",
    "diagnosis_description": "Obstructive sleep apnea",
}

PPO_ORDER = {
    **VALID_ORDER,
    "insurance_payer": "United PPO",
    "equipment_category": "Filters — Disposable",
    "equipment_description": "Disposable filters",
    "hcpcs_codes": ["A7038"],
}


async def _create_order(client, cookies, data=None):
    resp = await client.post("/api/dme/orders", json=data or VALID_ORDER)
    assert resp.status_code == 200
    return resp.json()["id"]


# ── Auth-required check ────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_auth_required_hmo(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    resp = await client.post(
        f"/api/dme/orders/{order_id}/prior-auth/check",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["required"] is True
    assert data["insurance_type"] == "hmo"


@pytest.mark.asyncio
async def test_check_auth_not_required_ppo_supplies(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies, PPO_ORDER)
    resp = await client.post(
        f"/api/dme/orders/{order_id}/prior-auth/check",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["required"] is False
    assert data["insurance_type"] == "ppo"


@pytest.mark.asyncio
async def test_check_auth_required_medicare_cpap(client, admin_cookies):
    order = {**VALID_ORDER, "insurance_payer": "Medicare"}
    order_id = await _create_order(client, admin_cookies, order)
    resp = await client.post(
        f"/api/dme/orders/{order_id}/prior-auth/check",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["required"] is True
    assert data["insurance_type"] == "medicare"


# ── Create auth request ────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_auth_request(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    resp = await client.post(
        f"/api/dme/orders/{order_id}/prior-auth",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    auth = resp.json()
    assert auth["status"] == "pending"
    assert auth["dme_order_id"] == order_id
    assert auth["patient_first_name"] == "Alice"
    assert auth["payer_name"] == "Aetna HMO"
    assert auth["insurance_type"] == "hmo"
    assert "E0601" in auth["hcpcs_codes"]
    assert "G47.33" in auth["diagnosis_codes"]
    assert auth["is_blocking"] is True


@pytest.mark.asyncio
async def test_get_auth_for_order(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    # Create auth
    await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    # Get it
    resp = await client.get(
        f"/api/dme/orders/{order_id}/prior-auth",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["dme_order_id"] == order_id


@pytest.mark.asyncio
async def test_no_duplicate_active_auth(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    # First one works
    resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    assert resp.status_code == 200
    # Second should fail
    resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


# ── Submit ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_auth(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    create_resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    auth_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/dme/prior-auth/{auth_id}",
        json={"action": "submit", "submission_notes": "Faxed to Aetna"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    auth = resp.json()
    assert auth["status"] == "submitted"
    assert auth["submitted_date"] is not None
    assert auth["submission_notes"] == "Faxed to Aetna"


@pytest.mark.asyncio
async def test_cannot_submit_already_submitted(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    create_resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    auth_id = create_resp.json()["id"]

    # First submit
    await client.put(f"/api/dme/prior-auth/{auth_id}", json={"action": "submit"}, cookies=admin_cookies)
    # Second submit should fail
    resp = await client.put(f"/api/dme/prior-auth/{auth_id}", json={"action": "submit"}, cookies=admin_cookies)
    assert resp.status_code == 400
    assert "pending" in resp.json()["detail"].lower()


# ── Record decision ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_approval(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    create_resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    auth_id = create_resp.json()["id"]

    # Submit then approve
    await client.put(f"/api/dme/prior-auth/{auth_id}", json={"action": "submit"}, cookies=admin_cookies)
    resp = await client.put(
        f"/api/dme/prior-auth/{auth_id}",
        json={"action": "approve", "auth_number": "PA-12345", "valid_until": "2027-06-01"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    auth = resp.json()
    assert auth["status"] == "approved"
    assert auth["auth_number"] == "PA-12345"
    assert auth["valid_until"] == "2027-06-01"
    assert auth["is_blocking"] is False


@pytest.mark.asyncio
async def test_record_denial(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    create_resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    auth_id = create_resp.json()["id"]

    await client.put(f"/api/dme/prior-auth/{auth_id}", json={"action": "submit"}, cookies=admin_cookies)
    resp = await client.put(
        f"/api/dme/prior-auth/{auth_id}",
        json={"action": "deny", "denial_reason": "Not medically necessary"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    auth = resp.json()
    assert auth["status"] == "denied"
    assert auth["denial_reason"] == "Not medically necessary"
    assert auth["is_blocking"] is True


# ── can_fulfill ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_can_fulfill_no_auth_returns_true(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    resp = await client.get(
        f"/api/dme/orders/{order_id}/prior-auth/can-fulfill",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["can_proceed"] is True


@pytest.mark.asyncio
async def test_can_fulfill_pending_auth_returns_false(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    resp = await client.get(
        f"/api/dme/orders/{order_id}/prior-auth/can-fulfill",
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_proceed"] is False
    assert "pending" in data["reason"].lower()


@pytest.mark.asyncio
async def test_can_fulfill_approved_returns_true(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    create_resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    auth_id = create_resp.json()["id"]

    await client.put(f"/api/dme/prior-auth/{auth_id}", json={"action": "submit"}, cookies=admin_cookies)
    await client.put(
        f"/api/dme/prior-auth/{auth_id}",
        json={"action": "approve", "auth_number": "PA-99", "valid_until": "2027-12-31"},
        cookies=admin_cookies,
    )

    resp = await client.get(f"/api/dme/orders/{order_id}/prior-auth/can-fulfill", cookies=admin_cookies)
    assert resp.status_code == 200
    assert resp.json()["can_proceed"] is True


# ── Approve order blocked by prior-auth ────────────────────────


@pytest.mark.asyncio
async def test_approve_order_blocked_when_auth_pending(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    # Create a pending auth
    await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    # Try to approve — should fail
    resp = await client.post(
        f"/api/dme/orders/{order_id}/approve",
        json={"notes": ""},
        cookies=admin_cookies,
    )
    assert resp.status_code == 409
    assert "cannot approve" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_approve_order_allowed_when_auth_approved(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    create_resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    auth_id = create_resp.json()["id"]

    await client.put(f"/api/dme/prior-auth/{auth_id}", json={"action": "submit"}, cookies=admin_cookies)
    await client.put(
        f"/api/dme/prior-auth/{auth_id}",
        json={"action": "approve", "auth_number": "PA-OK"},
        cookies=admin_cookies,
    )

    resp = await client.post(
        f"/api/dme/orders/{order_id}/approve",
        json={"notes": "All clear"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


# ── List/query endpoints ───────────────────────────────────────


@pytest.mark.asyncio
async def test_list_pending(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)

    resp = await client.get("/api/dme/prior-auth/pending", cookies=admin_cookies)
    assert resp.status_code == 200
    auths = resp.json()
    assert any(a["dme_order_id"] == order_id for a in auths)


@pytest.mark.asyncio
async def test_dashboard(client, admin_cookies):
    resp = await client.get("/api/dme/prior-auth/dashboard", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "pending" in data
    assert "approved" in data
    assert "denied" in data


# ── Prior-auth attached to order serialization ─────────────────


@pytest.mark.asyncio
async def test_order_includes_prior_auth(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)

    resp = await client.get(f"/api/dme/orders/{order_id}", cookies=admin_cookies)
    assert resp.status_code == 200
    order = resp.json()
    assert order["prior_auth"] is not None
    assert order["prior_auth"]["status"] == "pending"


@pytest.mark.asyncio
async def test_order_list_includes_prior_auth(client, admin_cookies):
    order_id = await _create_order(client, admin_cookies)
    await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)

    resp = await client.get("/api/dme/orders", cookies=admin_cookies)
    assert resp.status_code == 200
    orders = resp.json()
    matching = [o for o in orders if o["id"] == order_id]
    assert len(matching) == 1
    assert matching[0]["prior_auth"] is not None


# ── Auth endpoints require authentication ──────────────────────


@pytest.mark.asyncio
async def test_prior_auth_endpoints_require_auth(client):
    """All prior-auth endpoints should return 401 without cookies."""
    endpoints = [
        ("GET", "/api/dme/prior-auth/pending"),
        ("GET", "/api/dme/prior-auth/expiring"),
        ("GET", "/api/dme/prior-auth/dashboard"),
        ("POST", "/api/dme/orders/test-id/prior-auth/check"),
        ("GET", "/api/dme/orders/test-id/prior-auth"),
        ("POST", "/api/dme/orders/test-id/prior-auth"),
        ("PUT", "/api/dme/prior-auth/test-id"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} should require auth"


# ── Full flow integration test ─────────────────────────────────


@pytest.mark.asyncio
async def test_full_prior_auth_flow(client, admin_cookies):
    """End-to-end: create order → check required → create auth → submit → approve → approve order."""
    # Create order with HMO insurance
    order_id = await _create_order(client, admin_cookies)

    # Check if auth required
    check = await client.post(f"/api/dme/orders/{order_id}/prior-auth/check", cookies=admin_cookies)
    assert check.json()["required"] is True

    # Create auth request
    create_resp = await client.post(f"/api/dme/orders/{order_id}/prior-auth", cookies=admin_cookies)
    auth_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending"

    # Cannot approve order yet
    approve_resp = await client.post(
        f"/api/dme/orders/{order_id}/approve", json={"notes": ""}, cookies=admin_cookies
    )
    assert approve_resp.status_code == 409

    # Submit to payer
    submit_resp = await client.put(
        f"/api/dme/prior-auth/{auth_id}",
        json={"action": "submit", "submission_notes": "Faxed to Aetna 555-0100"},
        cookies=admin_cookies,
    )
    assert submit_resp.json()["status"] == "submitted"

    # Record approval
    approve_auth = await client.put(
        f"/api/dme/prior-auth/{auth_id}",
        json={"action": "approve", "auth_number": "PA-2026-789", "valid_until": "2027-03-28"},
        cookies=admin_cookies,
    )
    assert approve_auth.json()["status"] == "approved"

    # Now approve order succeeds
    order_resp = await client.post(
        f"/api/dme/orders/{order_id}/approve", json={"notes": "Auth approved"}, cookies=admin_cookies
    )
    assert order_resp.status_code == 200
    assert order_resp.json()["status"] == "approved"

    # Verify order includes prior-auth data
    order_detail = await client.get(f"/api/dme/orders/{order_id}", cookies=admin_cookies)
    pa = order_detail.json()["prior_auth"]
    assert pa["status"] == "approved"
    assert pa["auth_number"] == "PA-2026-789"
