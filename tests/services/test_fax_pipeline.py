"""Fax pipeline tests — OCR, file serving, error tracking, retry."""

import os
import pytest
import pytest_asyncio
import io
import tempfile

from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture()
async def client_with_fax_service():
    """Client with fax ingestion service initialized pointing at a temp dir."""
    from tests.conftest import _ensure_db
    await _ensure_db()
    from server.api.routes import _login_limiter, set_fax_ingestion_service
    from server.services.fax_ingestion import FaxIngestionService
    from server.services.referral import ReferralService

    _login_limiter._attempts.clear()

    # Create temp inbox dir
    inbox = tempfile.mkdtemp(prefix="fax_test_inbox_")

    # Init fax service — ReferralService gets LLM internally
    referral_svc = ReferralService(fhir_client=None)
    fax_svc = FaxIngestionService(inbox_dir=inbox, referral_service=referral_svc)
    set_fax_ingestion_service(fax_svc)

    from server.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, inbox

    # Cleanup: reset fax service
    set_fax_ingestion_service(None)


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
    username = f"faxadmin_{uuid.uuid4().hex[:8]}"
    user = await create_user(username, "AdminPass123", "admin")
    token = create_access_token(user["id"], user["username"], user["role"])
    return {"access_token": token}


# ---- OCR with PyMuPDF ----

@pytest.mark.asyncio
async def test_ocr_pdf_with_pymupdf():
    """_ocr_pdf renders pages via PyMuPDF and runs tesseract."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello from test PDF", fontsize=24)
    pdf_bytes = doc.tobytes()
    doc.close()

    from server.services.ocr import _ocr_pdf
    text = await _ocr_pdf(pdf_bytes)
    assert "Hello" in text or "hello" in text.lower()


@pytest.mark.asyncio
async def test_extract_text_from_pdf_embedded():
    """extract_text_from_pdf finds embedded text without OCR fallback."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Embedded text content here", fontsize=16)
    pdf_bytes = doc.tobytes()
    doc.close()

    from server.services.ocr import extract_text_from_pdf
    text = await extract_text_from_pdf(pdf_bytes)
    assert "Embedded" in text or len(text) > 10


@pytest.mark.asyncio
async def test_extract_text_from_image():
    """extract_text_from_image processes a simple PNG."""
    from PIL import Image, ImageDraw

    img = Image.new("L", (200, 50), 255)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Test OCR", fill=0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    from server.services.ocr import extract_text_from_image
    text = await extract_text_from_image(buf.getvalue())
    assert isinstance(text, str)


# ---- Fax Status Error Count ----

@pytest.mark.asyncio
async def test_fax_status_includes_error_count(client_with_fax_service, admin_cookies):
    """Fax status response includes errors field."""
    client, _ = client_with_fax_service
    resp = await client.get("/api/faxes/status", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "errors" in data
    assert isinstance(data["errors"], int)
    assert "processed" in data
    assert "pending" in data


# ---- Retry Failed Endpoint ----

@pytest.mark.asyncio
async def test_retry_failed_returns_results(client_with_fax_service, admin_cookies):
    """Retry-failed endpoint returns retried count and status."""
    client, _ = client_with_fax_service
    resp = await client.post("/api/faxes/retry-failed", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert "retried" in data
    assert "status" in data


# ---- File Serving — Path Traversal Protection ----

@pytest.mark.asyncio
async def test_fax_file_rejects_path_traversal():
    """_resolve_fax_path blocks filenames with traversal characters."""
    import tempfile
    from pathlib import Path
    from server.api.routes import _resolve_fax_path

    inbox = Path(tempfile.mkdtemp(prefix="fax_traversal_test_"))

    for bad_name in ["../etc/passwd", "foo/../bar", "test\x00.pdf", "sub/file.pdf"]:
        with pytest.raises(Exception) as exc_info:
            _resolve_fax_path(inbox, bad_name)
        assert "400" in str(exc_info.value.status_code) or "Invalid" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_fax_file_returns_404_for_missing(client_with_fax_service, admin_cookies):
    """File endpoint returns 404 for non-existent files."""
    client, _ = client_with_fax_service
    resp = await client.get("/api/faxes/file/nonexistent-file.pdf", cookies=admin_cookies)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fax_file_requires_auth(client):
    """File endpoint rejects unauthenticated requests."""
    resp = await client.get("/api/faxes/file/test.pdf")
    assert resp.status_code in (401, 503)


# ---- File Info Endpoint ----

@pytest.mark.asyncio
async def test_fax_file_info_returns_404_for_missing(client_with_fax_service, admin_cookies):
    """File info returns 404 for non-existent files."""
    client, _ = client_with_fax_service
    resp = await client.get("/api/faxes/file/nonexistent.pdf/info", cookies=admin_cookies)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fax_file_info_for_existing_pdf(client_with_fax_service, admin_cookies):
    """File info returns page count for a real PDF."""
    import fitz
    client, inbox = client_with_fax_service

    # Create a 2-page test PDF
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(os.path.join(inbox, "test-doc.pdf"))
    doc.close()

    resp = await client.get("/api/faxes/file/test-doc.pdf/info", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pages"] == 2
    assert data["content_type"] == "application/pdf"
    assert data["size_bytes"] > 0


# ---- Page Rendering Endpoint ----

@pytest.mark.asyncio
async def test_fax_page_returns_404_for_missing(client_with_fax_service, admin_cookies):
    """Page render returns 404 for non-existent files."""
    client, _ = client_with_fax_service
    resp = await client.get("/api/faxes/file/nonexistent.pdf/page/0", cookies=admin_cookies)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fax_page_renders_pdf_page(client_with_fax_service, admin_cookies):
    """Page render returns PNG for a valid PDF page."""
    import fitz
    client, inbox = client_with_fax_service

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Render me", fontsize=24)
    doc.save(os.path.join(inbox, "render-test.pdf"))
    doc.close()

    resp = await client.get("/api/faxes/file/render-test.pdf/page/0", cookies=admin_cookies)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 100  # Non-trivial PNG


@pytest.mark.asyncio
async def test_fax_page_out_of_range(client_with_fax_service, admin_cookies):
    """Page render returns 404 for page beyond document length."""
    import fitz
    client, inbox = client_with_fax_service

    doc = fitz.open()
    doc.new_page()
    doc.save(os.path.join(inbox, "one-page.pdf"))
    doc.close()

    resp = await client.get("/api/faxes/file/one-page.pdf/page/5", cookies=admin_cookies)
    assert resp.status_code == 404


# ---- File Serving Endpoint ----

@pytest.mark.asyncio
async def test_serve_fax_file_returns_pdf(client_with_fax_service, admin_cookies):
    """Serve endpoint returns the actual PDF file with correct headers."""
    import fitz
    client, inbox = client_with_fax_service

    doc = fitz.open()
    doc.new_page()
    doc.save(os.path.join(inbox, "serve-test.pdf"))
    doc.close()

    resp = await client.get("/api/faxes/file/serve-test.pdf", cookies=admin_cookies)
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]
    assert resp.headers.get("cache-control") == "no-store"
