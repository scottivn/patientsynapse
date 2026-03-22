"""Referral authorization CRUD, status computation, visit tracking, and renewal tests."""

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
async def fo_cookies():
    """Front-office user cookies for referral auth routes."""
    from tests.conftest import _ensure_db
    await _ensure_db()
    import uuid
    from server.auth.users import create_user
    from server.auth.jwt_auth import create_access_token
    username = f"fouser_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "FoPass123456", "front_office")
    token = create_access_token(user["id"], user["username"], user["role"])
    return {"access_token": token}


VALID_AUTH = {
    "patient_id": "pat-001",
    "patient_first_name": "Jane",
    "patient_last_name": "Doe",
    "insurance_name": "Aetna",
    "insurance_type": "hmo",
    "insurance_member_id": "AET123456",
    "referral_number": "REF-2026-001",
    "referring_pcp_name": "Dr. Adams",
    "referring_pcp_npi": "1234567890",
    "referring_pcp_phone": "555-111-2222",
    "referring_pcp_fax": "555-111-3333",
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "visits_allowed": 12,
    "notes": "Annual referral",
}


# ---- CRUD ----

@pytest.mark.asyncio
async def test_create_referral_auth(client, fo_cookies):
    """Create a referral auth and verify fields."""
    resp = await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_first_name"] == "Jane"
    assert data["patient_last_name"] == "Doe"
    assert data["insurance_type"] == "hmo"
    assert data["referral_number"] == "REF-2026-001"
    assert data["visits_allowed"] == 12
    assert data["visits_used"] == 0
    assert data["status"] == "active"
    assert data["id"]


@pytest.mark.asyncio
async def test_list_referral_auths(client, fo_cookies):
    """Created auth appears in the list."""
    create_resp = await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)
    auth_id = create_resp.json()["id"]

    resp = await client.get("/api/referral-auths", cookies=fo_cookies)
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert auth_id in ids


@pytest.mark.asyncio
async def test_get_referral_auth_by_id(client, fo_cookies):
    """Retrieve a specific auth by ID."""
    create_resp = await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)
    auth_id = create_resp.json()["id"]

    resp = await client.get(f"/api/referral-auths/{auth_id}", cookies=fo_cookies)
    assert resp.status_code == 200
    assert resp.json()["id"] == auth_id


@pytest.mark.asyncio
async def test_get_nonexistent_auth_returns_404(client, fo_cookies):
    resp = await client.get("/api/referral-auths/ZZZZZZ", cookies=fo_cookies)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_referral_auth(client, fo_cookies):
    """Update fields on an existing auth."""
    create_resp = await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)
    auth_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/referral-auths/{auth_id}",
        json={"visits_allowed": 24, "notes": "Extended"},
        cookies=fo_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["visits_allowed"] == 24
    assert resp.json()["notes"] == "Extended"


# ---- Visit Tracking ----

@pytest.mark.asyncio
async def test_record_visit(client, fo_cookies):
    """Recording a visit increments visits_used and decrements visits_remaining."""
    create_resp = await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)
    auth_id = create_resp.json()["id"]

    resp = await client.post(f"/api/referral-auths/{auth_id}/record-visit", cookies=fo_cookies)
    assert resp.status_code == 200
    assert resp.json()["visits_used"] == 1
    assert resp.json()["visits_remaining"] == 11


@pytest.mark.asyncio
async def test_visits_exhausted_status(client, fo_cookies):
    """Auth with all visits used gets exhausted status."""
    auth_data = {**VALID_AUTH, "visits_allowed": 2, "end_date": "2027-12-31"}
    create_resp = await client.post("/api/referral-auths", json=auth_data, cookies=fo_cookies)
    auth_id = create_resp.json()["id"]

    # Use both visits
    await client.post(f"/api/referral-auths/{auth_id}/record-visit", cookies=fo_cookies)
    resp = await client.post(f"/api/referral-auths/{auth_id}/record-visit", cookies=fo_cookies)
    assert resp.json()["status"] == "exhausted"
    assert resp.json()["visits_remaining"] == 0


# ---- Status Computation ----

@pytest.mark.asyncio
async def test_expired_auth_status(client, fo_cookies):
    """Auth with past end_date gets expired status."""
    auth_data = {**VALID_AUTH, "end_date": "2020-01-01"}
    resp = await client.post("/api/referral-auths", json=auth_data, cookies=fo_cookies)
    assert resp.json()["status"] == "expired"


@pytest.mark.asyncio
async def test_expiring_soon_status(client, fo_cookies):
    """Auth expiring within 14 days gets expiring_soon status."""
    from datetime import date, timedelta
    soon = (date.today() + timedelta(days=7)).isoformat()
    auth_data = {**VALID_AUTH, "end_date": soon}
    resp = await client.post("/api/referral-auths", json=auth_data, cookies=fo_cookies)
    assert resp.json()["status"] == "expiring_soon"


# ---- Renewal ----

@pytest.mark.asyncio
async def test_request_renewal(client, fo_cookies):
    """Requesting renewal changes status to pending_renewal."""
    create_resp = await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)
    auth_id = create_resp.json()["id"]

    resp = await client.post(f"/api/referral-auths/{auth_id}/request-renewal", cookies=fo_cookies)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_renewal"
    assert resp.json()["renewal_requested_at"]


@pytest.mark.asyncio
async def test_get_renewal_content(client, fo_cookies):
    """Renewal content includes PCP info and patient details."""
    create_resp = await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)
    auth_id = create_resp.json()["id"]

    resp = await client.get(f"/api/referral-auths/{auth_id}/renewal-content", cookies=fo_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["to_name"] == "Dr. Adams"
    assert data["to_fax"] == "555-111-3333"
    assert "Jane Doe" in data["message"]
    assert "REF-2026-001" in data["message"]


# ---- Cancel ----

@pytest.mark.asyncio
async def test_cancel_auth(client, fo_cookies):
    """Cancelling an auth sets status to cancelled."""
    create_resp = await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)
    auth_id = create_resp.json()["id"]

    resp = await client.post(f"/api/referral-auths/{auth_id}/cancel", cookies=fo_cookies)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


# ---- Dashboard ----

@pytest.mark.asyncio
async def test_referral_auth_dashboard(client, fo_cookies):
    """Dashboard returns status counts."""
    resp = await client.get("/api/referral-auths/dashboard", cookies=fo_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "active" in data
    assert "expired" in data


# ---- Expiring Soon ----

@pytest.mark.asyncio
async def test_expiring_soon_endpoint(client, fo_cookies):
    """Expiring endpoint returns auths within N days."""
    from datetime import date, timedelta
    soon = (date.today() + timedelta(days=5)).isoformat()
    auth_data = {**VALID_AUTH, "end_date": soon}
    await client.post("/api/referral-auths", json=auth_data, cookies=fo_cookies)

    resp = await client.get("/api/referral-auths/expiring?days=14", cookies=fo_cookies)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


# ---- Filter by Status ----

@pytest.mark.asyncio
async def test_list_auths_with_status_filter(client, fo_cookies):
    """Filtering by status returns only matching auths."""
    await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)

    resp = await client.get("/api/referral-auths?status=active", cookies=fo_cookies)
    assert resp.status_code == 200
    for auth in resp.json():
        assert auth["status"] == "active"


# ---- Scheduling Eligibility ----

@pytest.mark.asyncio
async def test_scheduling_eligibility_with_active_auth(client, fo_cookies):
    """HMO patient with active referral is eligible for scheduling."""
    await client.post("/api/referral-auths", json=VALID_AUTH, cookies=fo_cookies)

    resp = await client.get(f"/api/scheduling/referral-check/{VALID_AUTH['patient_id']}", cookies=fo_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is True
    assert data["requires_referral"] is True
    assert data["block"] is False


@pytest.mark.asyncio
async def test_scheduling_eligibility_no_auth(client, fo_cookies):
    """Patient with no auth data returns eligible (unknown insurance type)."""
    resp = await client.get("/api/scheduling/referral-check/no-auths-patient", cookies=fo_cookies)
    assert resp.status_code == 200
    # Unknown insurance type = no referral required
    assert resp.json()["requires_referral"] is False
