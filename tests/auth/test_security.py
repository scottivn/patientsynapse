"""Test security hardening: rate limiting, SMART auth guards, CSP header, input validation."""

import pytest

pytestmark = pytest.mark.asyncio


# ────────────────────── Login rate limiting ──────────────────────


async def test_login_rate_limit_blocks_after_failures(client):
    """5 failed logins from the same IP should trigger 429."""
    for i in range(5):
        resp = await client.post(
            "/api/admin/login",
            json={"username": "nonexistent", "password": "wrong"},
        )
        assert resp.status_code == 401, f"Attempt {i+1} should be 401"

    # 6th attempt should be rate-limited
    resp = await client.post(
        "/api/admin/login",
        json={"username": "nonexistent", "password": "wrong"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


async def test_successful_login_resets_rate_limit(client, admin_user):
    """A successful login should clear the failure counter for that IP."""
    # 4 failures (below threshold)
    for _ in range(4):
        await client.post(
            "/api/admin/login",
            json={"username": "nobody", "password": "wrong"},
        )

    # Successful login should clear the counter
    resp = await client.post(
        "/api/admin/login",
        json={"username": admin_user["username"], "password": "AdminPass123"},
    )
    assert resp.status_code == 200

    # Should be able to fail again without hitting 429 immediately
    resp = await client.post(
        "/api/admin/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code == 401


# ────────────────────── SMART OAuth routes require admin ──────────────────────

SMART_ROUTES = [
    ("GET", "/api/auth/status"),
    ("GET", "/api/auth/login"),
    ("POST", "/api/auth/connect-service"),
]


@pytest.mark.parametrize("method,path", SMART_ROUTES)
async def test_smart_routes_require_auth(client, method, path):
    """SMART OAuth routes should return 401 for unauthenticated requests."""
    resp = await client.request(method, path)
    assert resp.status_code == 401, f"{method} {path} should require auth"


@pytest.mark.parametrize("method,path", SMART_ROUTES)
async def test_smart_routes_require_admin(client, dme_cookies, method, path):
    """SMART OAuth routes should return 403 for non-admin roles."""
    resp = await client.request(method, path, cookies=dme_cookies)
    assert resp.status_code == 403, f"DME should not access {path}"


@pytest.mark.parametrize("method,path", SMART_ROUTES)
async def test_smart_routes_allow_admin(client, admin_cookies, method, path):
    """SMART OAuth routes should be accessible to admin."""
    resp = await client.request(method, path, cookies=admin_cookies)
    assert resp.status_code != 401, f"Admin should be authenticated for {path}"
    assert resp.status_code != 403, f"Admin should access {path}"


# ────────────────────── CSP header ──────────────────────


async def test_csp_header_present(client, admin_cookies):
    """All responses should have a Content-Security-Policy header."""
    resp = await client.get("/api/admin/me", cookies=admin_cookies)
    assert "content-security-policy" in resp.headers
    csp = resp.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


async def test_security_headers_present(client, admin_cookies):
    """X-Content-Type-Options, X-Frame-Options, Referrer-Policy should be set."""
    resp = await client.get("/api/admin/me", cookies=admin_cookies)
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "strict-origin" in resp.headers.get("referrer-policy", "")


async def test_api_no_cache_headers(client, admin_cookies):
    """API responses should have Cache-Control: no-store."""
    resp = await client.get("/api/admin/me", cookies=admin_cookies)
    assert resp.headers.get("cache-control") == "no-store"


# ────────────────────── DME order input validation ──────────────────────


async def test_dme_order_rejects_missing_name(client):
    """DME order creation should reject missing patient_first_name."""
    resp = await client.post(
        "/api/dme/orders",
        json={"patient_last_name": "Doe"},
    )
    assert resp.status_code == 422  # Pydantic validation error


async def test_dme_order_rejects_empty_name(client):
    """DME order creation should reject empty patient names."""
    resp = await client.post(
        "/api/dme/orders",
        json={"patient_first_name": "", "patient_last_name": "Doe"},
    )
    assert resp.status_code == 422


async def test_dme_order_rejects_bad_quantity(client):
    """DME order creation should reject negative quantity."""
    resp = await client.post(
        "/api/dme/orders",
        json={
            "patient_first_name": "Jane",
            "patient_last_name": "Doe",
            "quantity": -1,
        },
    )
    assert resp.status_code == 422


async def test_dme_order_accepts_valid_input(client):
    """DME order creation should accept valid input."""
    resp = await client.post(
        "/api/dme/orders",
        json={
            "patient_first_name": "Jane",
            "patient_last_name": "Doe",
            "patient_dob": "1990-01-15",
            "equipment_category": "CPAP",
            "quantity": 1,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_first_name"] == "Jane"
    assert data["patient_last_name"] == "Doe"
