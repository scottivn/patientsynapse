"""Shared fixtures for PatientSynapse tests."""

import os
import tempfile

# Point config at an isolated test database BEFORE any app imports
_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db.name}"
os.environ["APP_ENV"] = "development"
os.environ["APP_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["USE_STUB_FHIR"] = "true"
os.environ["ADMIN_DEFAULT_PASSWORD"] = ""  # skip auto-seed

import pytest
import pytest_asyncio
import asyncio
import uuid

from httpx import AsyncClient, ASGITransport
from server.auth.jwt_auth import create_access_token
from server.auth.users import init_db, create_user

# Clear the lru_cache so Settings re-reads our env vars
from server.config import get_settings
get_settings.cache_clear()


# Run init_db at module import time (before any tests run)
_db_initialized = False


async def _ensure_db():
    global _db_initialized
    if not _db_initialized:
        await init_db()
        # Init business-entity tables (referrals, dme_orders, referral_auths, prescriptions, fax_processed)
        from server.db import init_all_tables
        await init_all_tables()
        # Also init allowable rates table
        from server.services.allowable_rates import init_rates_table
        await init_rates_table()
        _db_initialized = True


@pytest_asyncio.fixture()
async def admin_user():
    await _ensure_db()
    username = f"testadmin_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "AdminPass123", "admin")
    return user


@pytest_asyncio.fixture()
async def dme_user():
    await _ensure_db()
    username = f"testdme_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "DmePass1234", "dme")
    return user


@pytest_asyncio.fixture()
async def front_office_user():
    await _ensure_db()
    username = f"testfo_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "FoPass12345", "front_office")
    return user


def _make_cookie(user_id: int, username: str, role: str) -> str:
    return create_access_token(user_id, username, role)


@pytest.fixture()
def admin_cookies(admin_user):
    token = _make_cookie(admin_user["id"], admin_user["username"], admin_user["role"])
    return {"access_token": token}


@pytest.fixture()
def dme_cookies(dme_user):
    token = _make_cookie(dme_user["id"], dme_user["username"], dme_user["role"])
    return {"access_token": token}


@pytest.fixture()
def front_office_cookies(front_office_user):
    token = _make_cookie(front_office_user["id"], front_office_user["username"], front_office_user["role"])
    return {"access_token": token}


@pytest_asyncio.fixture()
async def demo_user():
    await _ensure_db()
    username = f"testdemo_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "DemoPass123", "demo")
    return user


@pytest.fixture()
def demo_cookies(demo_user):
    token = _make_cookie(demo_user["id"], demo_user["username"], demo_user["role"])
    return {"access_token": token}


@pytest_asyncio.fixture()
async def client():
    await _ensure_db()
    # Reset login rate limiter between tests to prevent cross-test interference
    from server.api.routes import _login_limiter
    _login_limiter._attempts.clear()
    from server.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
