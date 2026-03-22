"""Test user management CRUD endpoints (admin only)."""

import pytest


pytestmark = pytest.mark.asyncio


# ────────────────────── List users ──────────────────────

async def test_list_users(client, admin_cookies, admin_user):
    resp = await client.get("/api/admin/users", cookies=admin_cookies)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert any(u["username"] == admin_user["username"] for u in users)


async def test_list_users_blocked_for_dme(client, dme_cookies):
    resp = await client.get("/api/admin/users", cookies=dme_cookies)
    assert resp.status_code == 403


# ────────────────────── Create user ──────────────────────

async def test_create_user(client, admin_cookies):
    import uuid
    username = f"newuser_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/admin/users",
        json={"username": username, "password": "SecurePass1", "role": "dme"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == username
    assert data["role"] == "dme"
    assert "password_hash" not in data


async def test_create_user_short_password(client, admin_cookies):
    resp = await client.post(
        "/api/admin/users",
        json={"username": "shortpw", "password": "abc", "role": "dme"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 400
    assert "8 characters" in resp.json()["detail"]


async def test_create_user_invalid_role(client, admin_cookies):
    resp = await client.post(
        "/api/admin/users",
        json={"username": "badrole", "password": "SecurePass1", "role": "superadmin"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 400
    assert "Invalid role" in resp.json()["detail"]


async def test_create_duplicate_username(client, admin_cookies, admin_user):
    resp = await client.post(
        "/api/admin/users",
        json={"username": admin_user["username"], "password": "SecurePass1", "role": "dme"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


async def test_create_user_blocked_for_dme(client, dme_cookies):
    resp = await client.post(
        "/api/admin/users",
        json={"username": "shouldfail", "password": "SecurePass1", "role": "dme"},
        cookies=dme_cookies,
    )
    assert resp.status_code == 403


# ────────────────────── Update user ──────────────────────

async def test_update_user_role(client, admin_cookies, dme_user):
    resp = await client.put(
        f"/api/admin/users/{dme_user['id']}",
        json={"role": "admin"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


async def test_deactivate_user(client, admin_cookies, dme_user):
    resp = await client.put(
        f"/api/admin/users/{dme_user['id']}",
        json={"is_active": False},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] == 0


async def test_reactivate_user(client, admin_cookies, dme_user):
    from server.auth.users import update_user
    await update_user(dme_user["id"], is_active=False)

    resp = await client.put(
        f"/api/admin/users/{dme_user['id']}",
        json={"is_active": True},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] == 1


async def test_cannot_self_deactivate(client, admin_cookies, admin_user):
    resp = await client.put(
        f"/api/admin/users/{admin_user['id']}",
        json={"is_active": False},
        cookies=admin_cookies,
    )
    assert resp.status_code == 400
    assert "own account" in resp.json()["detail"].lower()


async def test_update_nonexistent_user(client, admin_cookies):
    resp = await client.put(
        "/api/admin/users/99999",
        json={"role": "dme"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 404


async def test_update_empty_body(client, admin_cookies, dme_user):
    resp = await client.put(
        f"/api/admin/users/{dme_user['id']}",
        json={},
        cookies=admin_cookies,
    )
    assert resp.status_code == 400
    assert "Nothing to update" in resp.json()["detail"]


async def test_update_user_blocked_for_dme(client, dme_cookies, dme_user):
    resp = await client.put(
        f"/api/admin/users/{dme_user['id']}",
        json={"role": "admin"},
        cookies=dme_cookies,
    )
    assert resp.status_code == 403


# ────────────────────── Reset password ──────────────────────

async def test_reset_password(client, admin_cookies, dme_user):
    resp = await client.post(
        f"/api/admin/users/{dme_user['id']}/reset-password",
        json={"password": "NewSecure99"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["reset"] is True

    # Verify new password works
    login_resp = await client.post(
        "/api/admin/login",
        json={"username": dme_user["username"], "password": "NewSecure99"},
    )
    assert login_resp.status_code == 200


async def test_reset_password_short(client, admin_cookies, dme_user):
    resp = await client.post(
        f"/api/admin/users/{dme_user['id']}/reset-password",
        json={"password": "short"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 400


async def test_reset_password_nonexistent_user(client, admin_cookies):
    resp = await client.post(
        "/api/admin/users/99999/reset-password",
        json={"password": "SecurePass1"},
        cookies=admin_cookies,
    )
    assert resp.status_code == 404


async def test_reset_password_blocked_for_dme(client, dme_cookies, dme_user):
    resp = await client.post(
        f"/api/admin/users/{dme_user['id']}/reset-password",
        json={"password": "SecurePass1"},
        cookies=dme_cookies,
    )
    assert resp.status_code == 403


# ────────────────────── Get roles ──────────────────────

async def test_get_roles(client, admin_cookies):
    resp = await client.get("/api/admin/roles", cookies=admin_cookies)
    assert resp.status_code == 200
    roles = resp.json()
    keys = [r["key"] for r in roles]
    assert "admin" in keys
    assert "dme" in keys


async def test_get_roles_accessible_by_dme(client, dme_cookies):
    """Roles endpoint is read-only info, accessible to any authenticated user."""
    resp = await client.get("/api/admin/roles", cookies=dme_cookies)
    assert resp.status_code == 200
