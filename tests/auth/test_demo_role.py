"""Tests for the demo role — read-only access for portfolio/recruiter demos."""

import pytest


# ── Read access: demo can view all non-admin routes ──────────────


@pytest.mark.asyncio
async def test_demo_can_read_dme_orders(client, demo_cookies):
    resp = await client.get("/api/dme/orders/incoming", cookies=demo_cookies)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_demo_can_read_dme_dashboard(client, demo_cookies):
    resp = await client.get("/api/dme/dashboard", cookies=demo_cookies)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_demo_can_read_allowable_rates(client, demo_cookies):
    resp = await client.get("/api/allowable-rates", cookies=demo_cookies)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_demo_can_read_referrals(client, demo_cookies):
    resp = await client.get("/api/referrals", cookies=demo_cookies)
    # 200 or 503 (service not initialized in tests) — but not 401/403
    assert resp.status_code not in (401, 403)


@pytest.mark.asyncio
async def test_demo_can_read_fax_status(client, demo_cookies):
    resp = await client.get("/api/faxes/status", cookies=demo_cookies)
    assert resp.status_code not in (401, 403)


# ── Write access: demo is blocked on all mutations ───────────────


@pytest.mark.asyncio
async def test_demo_blocked_post_dme_order(client, demo_cookies):
    resp = await client.post("/api/dme/admin/orders", cookies=demo_cookies, json={
        "patient_first_name": "Test", "patient_last_name": "User",
    })
    assert resp.status_code == 403
    assert "read-only" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_demo_blocked_approve_order(client, demo_cookies):
    resp = await client.post("/api/dme/orders/FAKE123/approve", cookies=demo_cookies)
    assert resp.status_code == 403
    assert "read-only" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_demo_blocked_delete_rate(client, demo_cookies):
    resp = await client.delete("/api/allowable-rates/1", cookies=demo_cookies)
    assert resp.status_code == 403
    assert "read-only" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_demo_blocked_put_settings(client, demo_cookies):
    resp = await client.post("/api/settings/emr", cookies=demo_cookies, json={
        "emr_provider": "stub",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_demo_blocked_create_user(client, demo_cookies):
    resp = await client.post("/api/admin/users", cookies=demo_cookies, json={
        "username": "hacker", "password": "secret", "role": "admin",
    })
    assert resp.status_code == 403


# ── Admin-only routes: demo cannot access ────────────────────────


@pytest.mark.asyncio
async def test_demo_cannot_access_settings(client, demo_cookies):
    resp = await client.get("/api/settings/emr", cookies=demo_cookies)
    assert resp.status_code == 403
    assert "admin" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_demo_cannot_access_user_management(client, demo_cookies):
    resp = await client.get("/api/admin/users", cookies=demo_cookies)
    assert resp.status_code == 403


# ── Auth endpoints still work for demo ───────────────────────────


@pytest.mark.asyncio
async def test_demo_can_login(client, demo_user):
    resp = await client.post("/api/admin/login", json={
        "username": demo_user["username"], "password": "DemoPass123",
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "demo"


@pytest.mark.asyncio
async def test_demo_me_returns_demo_role(client, demo_cookies):
    resp = await client.get("/api/admin/me", cookies=demo_cookies)
    assert resp.status_code == 200
    assert resp.json()["role"] == "demo"


# ── Admin still works normally ───────────────────────────────────


@pytest.mark.asyncio
async def test_admin_not_blocked_by_demo_middleware(client, admin_cookies):
    """Verify the demo middleware doesn't interfere with admin writes."""
    resp = await client.post("/api/dme/admin/orders", cookies=admin_cookies, json={
        "patient_first_name": "Admin",
        "patient_last_name": "Test",
        "patient_dob": "1990-01-01",
    })
    # Should get through to the route handler (may fail on missing fields, but not 403)
    assert resp.status_code != 403
