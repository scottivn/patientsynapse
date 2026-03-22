"""System status, settings, allowable rates, scheduling, and RCM endpoint tests."""

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
    username = f"sysadmin_{uuid.uuid4().hex[:8]}"
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
    username = f"sysdme_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "DmePass12345", "dme")
    token = create_access_token(user["id"], user["username"], user["role"])
    return {"access_token": token}


@pytest_asyncio.fixture()
async def fo_cookies():
    from tests.conftest import _ensure_db
    await _ensure_db()
    import uuid
    from server.auth.users import create_user
    from server.auth.jwt_auth import create_access_token
    username = f"sysfo_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "FoPass123456", "front_office")
    token = create_access_token(user["id"], user["username"], user["role"])
    return {"access_token": token}


# ---- System Status ----

@pytest.mark.asyncio
async def test_system_status(client):
    """Public status endpoint returns running state."""
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert "emr_provider" in data
    assert "llm_provider" in data
    assert "app_env" in data


# ---- Settings ----

@pytest.mark.asyncio
async def test_get_emr_config(client, admin_cookies):
    """Get EMR config returns provider info."""
    resp = await client.get("/api/settings/emr", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "emr_provider" in data
    assert "fhir_base_url" in data


@pytest.mark.asyncio
async def test_get_llm_config(client, admin_cookies):
    """Get LLM config returns current provider."""
    resp = await client.get("/api/settings/llm", cookies=admin_cookies)
    assert resp.status_code == 200
    assert "llm_provider" in resp.json()


@pytest.mark.asyncio
async def test_settings_routes_require_admin(client, dme_cookies):
    """Settings routes reject non-admin users."""
    for path in ["/api/settings/emr", "/api/settings/llm"]:
        resp = await client.get(path, cookies=dme_cookies)
        assert resp.status_code == 403, f"Expected 403 for DME user on {path}"


# ---- Admin Logout ----

@pytest.mark.asyncio
async def test_admin_logout(client, admin_cookies):
    """Logout clears cookies and returns success."""
    resp = await client.post("/api/admin/logout", cookies=admin_cookies)
    assert resp.status_code == 200
    assert resp.json()["logged_out"] is True


# ---- Scheduling (Stub) ----

@pytest.mark.asyncio
async def test_search_providers(client, fo_cookies):
    """Provider search returns stub data in dev mode."""
    resp = await client.get("/api/scheduling/providers", cookies=fo_cookies)
    assert resp.status_code == 200
    assert "providers" in resp.json()
    assert len(resp.json()["providers"]) > 0


@pytest.mark.asyncio
async def test_search_providers_by_specialty(client, fo_cookies):
    """Provider search filters by specialty."""
    resp = await client.get("/api/scheduling/providers?specialty=pulmonology", cookies=fo_cookies)
    assert resp.status_code == 200
    for p in resp.json()["providers"]:
        assert "pulmonology" in p["specialty"].lower()


@pytest.mark.asyncio
async def test_verify_insurance(client, fo_cookies):
    """Insurance verification returns stub coverage data."""
    resp = await client.get("/api/scheduling/insurance/pat-001", cookies=fo_cookies)
    assert resp.status_code == 200
    assert "coverages" in resp.json()


# ---- RCM (Stub) ----

@pytest.mark.asyncio
async def test_rcm_dashboard(client, admin_cookies):
    """RCM dashboard returns summary stats."""
    resp = await client.get("/api/rcm/dashboard", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "referrals_processed" in data
    assert "payer_mix" in data
    assert "top_diagnoses" in data


@pytest.mark.asyncio
async def test_rcm_patient_billing(client, admin_cookies):
    """Patient billing endpoint returns stub data."""
    resp = await client.get("/api/rcm/patient/pat-001", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "encounters" in data
    assert "conditions" in data
    assert "insurance" in data


# ---- Allowable Rates ----

@pytest.mark.asyncio
async def test_create_and_list_rate(client, dme_cookies):
    """Create a rate and find it in the list."""
    rate = {
        "payer": "TestPayer",
        "hcpcs_code": "E0601",
        "description": "CPAP device",
        "supply_months": 6,
        "allowed_amount": 450.00,
        "effective_year": 2026,
    }
    create_resp = await client.post("/api/allowable-rates", json=rate, cookies=dme_cookies)
    assert create_resp.status_code == 200
    assert create_resp.json()["payer"] == "TestPayer"

    list_resp = await client.get("/api/allowable-rates?payer=TestPayer", cookies=dme_cookies)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_lookup_rate(client, dme_cookies):
    """Look up a specific rate by payer + HCPCS code."""
    rate = {
        "payer": "LookupTest",
        "hcpcs_code": "A7030",
        "description": "Full face mask",
        "supply_months": 3,
        "allowed_amount": 125.50,
        "effective_year": 2026,
    }
    await client.post("/api/allowable-rates", json=rate, cookies=dme_cookies)

    resp = await client.get(
        "/api/allowable-rates/lookup?payer=LookupTest&hcpcs_code=A7030&supply_months=3",
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["allowed_amount"] == 125.50


@pytest.mark.asyncio
async def test_lookup_nonexistent_rate_returns_404(client, dme_cookies):
    resp = await client.get(
        "/api/allowable-rates/lookup?payer=NoPayer&hcpcs_code=Z9999&supply_months=6",
        cookies=dme_cookies,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bundle_pricing(client, dme_cookies):
    """Bundle pricing calculates total for multiple codes."""
    # Create two rates for the same payer
    for code, amount in [("E0601", 450.0), ("A7030", 125.0)]:
        await client.post("/api/allowable-rates", json={
            "payer": "BundleTest",
            "hcpcs_code": code,
            "supply_months": 6,
            "allowed_amount": amount,
            "effective_year": 2026,
        }, cookies=dme_cookies)

    resp = await client.post(
        "/api/allowable-rates/bundle-pricing",
        json={"payer": "BundleTest", "hcpcs_codes": ["E0601", "A7030"], "supply_months": 6},
        cookies=dme_cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert data["total"] >= 575.0  # 450 + 125


@pytest.mark.asyncio
async def test_delete_rate(client, dme_cookies):
    """Delete a rate by ID."""
    rate = {
        "payer": "DeleteTest",
        "hcpcs_code": "E0601",
        "supply_months": 6,
        "allowed_amount": 100.0,
        "effective_year": 2026,
    }
    create_resp = await client.post("/api/allowable-rates", json=rate, cookies=dme_cookies)
    rate_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/allowable-rates/{rate_id}", cookies=dme_cookies)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_list_payers(client, dme_cookies):
    """List payers returns payer names with counts."""
    resp = await client.get("/api/allowable-rates/payers", cookies=dme_cookies)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---- Fax Status / Prescription Status ----

@pytest.mark.asyncio
async def test_fax_status_requires_auth(client):
    """Fax status endpoint rejects unauthenticated requests."""
    resp = await client.get("/api/faxes/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_prescription_status_without_monitor(client, dme_cookies):
    """Prescription status returns graceful response when monitor not initialized."""
    resp = await client.get("/api/prescriptions/status", cookies=dme_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_detected" in data


@pytest.mark.asyncio
async def test_prescriptions_list_without_monitor(client, dme_cookies):
    """Prescriptions list returns empty when monitor not initialized."""
    resp = await client.get("/api/prescriptions", cookies=dme_cookies)
    assert resp.status_code == 200


# ---- DME Patient Verify (Public) ----

@pytest.mark.asyncio
async def test_dme_patient_verify_stub(client):
    """Patient verification returns verified in stub/dev mode."""
    resp = await client.post(
        "/api/dme/patient-verify",
        json={"patient_id": "pat-001", "dob": "1985-03-15"},
    )
    assert resp.status_code == 200
    assert resp.json()["verified"] is True
