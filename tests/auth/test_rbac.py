"""Test role-based access control — admin, front_office, and dme route guards."""

import pytest


pytestmark = pytest.mark.asyncio


# ────────────────────── Admin-only routes ──────────────────────
# These should return 200 for admin, 403 for front_office and dme, 401 for unauthenticated.

ADMIN_ONLY_ROUTES = [
    ("GET",  "/api/rcm/dashboard"),
    ("GET",  "/api/settings/emr"),
    ("GET",  "/api/settings/llm"),
    ("GET",  "/api/admin/users"),
]


@pytest.mark.parametrize("method,path", ADMIN_ONLY_ROUTES)
async def test_admin_route_allows_admin(client, admin_cookies, method, path):
    resp = await client.request(method, path, cookies=admin_cookies)
    assert resp.status_code != 403, f"Admin should access {path}, got {resp.status_code}"
    assert resp.status_code != 401, f"Admin should be authenticated for {path}"


@pytest.mark.parametrize("method,path", ADMIN_ONLY_ROUTES)
async def test_admin_route_blocks_dme(client, dme_cookies, method, path):
    resp = await client.request(method, path, cookies=dme_cookies)
    assert resp.status_code == 403, f"DME should get 403 on {path}, got {resp.status_code}"


@pytest.mark.parametrize("method,path", ADMIN_ONLY_ROUTES)
async def test_admin_route_blocks_front_office(client, front_office_cookies, method, path):
    resp = await client.request(method, path, cookies=front_office_cookies)
    assert resp.status_code == 403, f"Front office should get 403 on {path}, got {resp.status_code}"


@pytest.mark.parametrize("method,path", ADMIN_ONLY_ROUTES)
async def test_admin_route_requires_auth(client, method, path):
    resp = await client.request(method, path)
    assert resp.status_code == 401, f"Unauthenticated should get 401 on {path}, got {resp.status_code}"


# ────────────────────── Front office routes ──────────────────────
# Faxes, referrals, referral auths, scheduling — accessible by admin + front_office.

FRONT_OFFICE_ROUTES = [
    ("GET",  "/api/referrals"),
    ("GET",  "/api/faxes/status"),
    ("GET",  "/api/referral-auths"),
    ("GET",  "/api/referral-auths/dashboard"),
]


@pytest.mark.parametrize("method,path", FRONT_OFFICE_ROUTES)
async def test_front_office_route_allows_admin(client, admin_cookies, method, path):
    resp = await client.request(method, path, cookies=admin_cookies)
    assert resp.status_code != 403, f"Admin should access {path}, got {resp.status_code}"
    assert resp.status_code != 401


@pytest.mark.parametrize("method,path", FRONT_OFFICE_ROUTES)
async def test_front_office_route_allows_front_office(client, front_office_cookies, method, path):
    resp = await client.request(method, path, cookies=front_office_cookies)
    assert resp.status_code != 403, f"Front office should access {path}, got {resp.status_code}"
    assert resp.status_code != 401


@pytest.mark.parametrize("method,path", FRONT_OFFICE_ROUTES)
async def test_front_office_route_blocks_dme(client, dme_cookies, method, path):
    resp = await client.request(method, path, cookies=dme_cookies)
    assert resp.status_code == 403, f"DME should get 403 on {path}, got {resp.status_code}"


@pytest.mark.parametrize("method,path", FRONT_OFFICE_ROUTES)
async def test_front_office_route_requires_auth(client, method, path):
    resp = await client.request(method, path)
    assert resp.status_code == 401


# ────────────────────── DME-accessible routes ──────────────────────
# These should return 200 for admin AND dme, 403 for front_office, 401 for unauthenticated.

DME_ALLOWED_ROUTES = [
    ("GET", "/api/dme/dashboard"),
    ("GET", "/api/dme/orders"),
    ("GET", "/api/allowable-rates"),
    ("GET", "/api/prescriptions/status"),
]


@pytest.mark.parametrize("method,path", DME_ALLOWED_ROUTES)
async def test_dme_route_allows_admin(client, admin_cookies, method, path):
    resp = await client.request(method, path, cookies=admin_cookies)
    assert resp.status_code != 403, f"Admin should access {path}, got {resp.status_code}"
    assert resp.status_code != 401


@pytest.mark.parametrize("method,path", DME_ALLOWED_ROUTES)
async def test_dme_route_allows_dme(client, dme_cookies, method, path):
    resp = await client.request(method, path, cookies=dme_cookies)
    assert resp.status_code != 403, f"DME should access {path}, got {resp.status_code}"
    assert resp.status_code != 401


@pytest.mark.parametrize("method,path", DME_ALLOWED_ROUTES)
async def test_dme_route_blocks_front_office(client, front_office_cookies, method, path):
    resp = await client.request(method, path, cookies=front_office_cookies)
    assert resp.status_code == 403, f"Front office should get 403 on {path}, got {resp.status_code}"


@pytest.mark.parametrize("method,path", DME_ALLOWED_ROUTES)
async def test_dme_route_requires_auth(client, method, path):
    resp = await client.request(method, path)
    assert resp.status_code == 401


# ────────────────────── Login returns correct role ──────────────────────

async def test_login_returns_admin_role(client, admin_user):
    resp = await client.post(
        "/api/admin/login",
        json={"username": admin_user["username"], "password": "AdminPass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert data["authenticated"] is True


async def test_login_returns_dme_role(client, dme_user):
    resp = await client.post(
        "/api/admin/login",
        json={"username": dme_user["username"], "password": "DmePass1234"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "dme"


async def test_login_returns_front_office_role(client, front_office_user):
    resp = await client.post(
        "/api/admin/login",
        json={"username": front_office_user["username"], "password": "FoPass12345"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "front_office"


# ────────────────────── Deactivated user rejected ──────────────────────

async def test_deactivated_user_rejected(client, dme_user, dme_cookies):
    from server.auth.users import update_user

    # Deactivate the user
    await update_user(dme_user["id"], is_active=False)

    # Existing token should now be rejected
    resp = await client.get("/api/dme/dashboard", cookies=dme_cookies)
    assert resp.status_code == 401
    assert "deactivated" in resp.json().get("detail", "").lower()


async def test_deactivated_user_cannot_login(client, dme_user):
    from server.auth.users import update_user

    await update_user(dme_user["id"], is_active=False)

    resp = await client.post(
        "/api/admin/login",
        json={"username": dme_user["username"], "password": "DmePass1234"},
    )
    assert resp.status_code == 403
    assert "deactivated" in resp.json().get("detail", "").lower()


# ────────────────────── /admin/me returns correct role ──────────────────────

async def test_me_returns_admin_role(client, admin_cookies):
    resp = await client.get("/api/admin/me", cookies=admin_cookies)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


async def test_me_returns_dme_role(client, dme_cookies):
    resp = await client.get("/api/admin/me", cookies=dme_cookies)
    assert resp.status_code == 200
    assert resp.json()["role"] == "dme"


async def test_me_returns_front_office_role(client, front_office_cookies):
    resp = await client.get("/api/admin/me", cookies=front_office_cookies)
    assert resp.status_code == 200
    assert resp.json()["role"] == "front_office"
