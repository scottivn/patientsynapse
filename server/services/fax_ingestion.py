"""Fax ingestion service — simulates calling eCW and receiving incoming faxes.

Monitors the IncomingFaxes/ directory for new PDF files, OCRs them,
and feeds them through the referral processing pipeline.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from server.db import db_execute, db_fetch_one, db_fetch_all
from server.services.ocr import extract_text_from_pdf, extract_text_from_image
from server.services.referral import ReferralService, ReferralRecord

logger = logging.getLogger(__name__)


class FaxIngestionService:
    """Watches a local directory for incoming fax PDFs and processes them."""

    def __init__(self, inbox_dir: str, referral_service: ReferralService):
        self.inbox_dir = Path(inbox_dir)
        self.referral_service = referral_service
        self._polling: bool = False
        self._poll_task: Optional[asyncio.Task] = None

    async def _get_processed_count(self) -> int:
        row = await db_fetch_one("SELECT COUNT(*) as cnt FROM fax_processed")
        return row["cnt"] if row else 0

    async def _is_processed(self, filename: str) -> bool:
        row = await db_fetch_one(
            "SELECT filename FROM fax_processed WHERE filename = ?", (filename,)
        )
        return row is not None

    async def _mark_processed(self, filename: str, result_id: str) -> None:
        await db_execute(
            "INSERT OR IGNORE INTO fax_processed (filename, result_id) VALUES (?, ?)",
            (filename, result_id),
        )

    async def _get_pending_files(self) -> list[str]:
        """Files in inbox that haven't been processed yet."""
        if not self.inbox_dir.exists():
            return []
        all_files = [
            f.name for f in self.inbox_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif")
        ]
        pending = []
        for f in all_files:
            if not await self._is_processed(f):
                pending.append(f)
        return pending

    async def poll_once(self) -> list[ReferralRecord]:
        """Scan inbox directory and process any new fax files."""
        if not self.inbox_dir.exists():
            logger.warning(f"Inbox directory not found: {self.inbox_dir}")
            return []

        new_files = await self._get_pending_files()
        if not new_files:
            logger.info("No new faxes in inbox")
            return []

        logger.info(f"Found {len(new_files)} new fax(es) in {self.inbox_dir}")
        results: list[ReferralRecord] = []

        for filename in sorted(new_files):
            file_path = self.inbox_dir / filename
            try:
                record = await self._process_file(file_path)
                await self._mark_processed(filename, record.id)
                results.append(record)
                logger.info(f"Processed fax {filename} -> referral {record.id} ({record.status.value})")
            except Exception as e:
                logger.error(f"Failed to process fax {filename}: {e}")
                await self._mark_processed(filename, f"error:{e}")

        return results

    async def _process_file(self, file_path: Path) -> ReferralRecord:
        """Read a fax file, OCR it, classify, and route through appropriate pipeline."""
        content = file_path.read_bytes()
        ext = file_path.suffix.lower()

        if ext == ".pdf":
            text = await extract_text_from_pdf(content)
        elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
            text = await extract_text_from_image(content)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        if not text.strip():
            raise ValueError(f"Could not extract text from {file_path.name}")

        return await self.referral_service.classify_and_process(text, file_path.name)

    def start_polling(self, interval_seconds: int = 300):
        """Start background polling loop."""
        if self._polling:
            logger.info("Polling already active")
            return
        self._polling = True
        self._poll_task = asyncio.create_task(self._poll_loop(interval_seconds))
        logger.info(f"Fax polling started (every {interval_seconds}s) on {self.inbox_dir}")

    def stop_polling(self):
        """Stop background polling loop."""
        self._polling = False
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        logger.info("Fax polling stopped")

    async def _poll_loop(self, interval: int):
        """Background loop that checks inbox on interval."""
        while self._polling:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error(f"Fax poll error: {e}")
            await asyncio.sleep(interval)

    async def get_status(self) -> dict:
        """Return current ingestion status."""
        processed_count = await self._get_processed_count()
        pending_files = await self._get_pending_files()
        rows = await db_fetch_all("SELECT filename, result_id FROM fax_processed")
        processed_files = {r["filename"]: r["result_id"] for r in rows}
        return {
            "inbox_dir": str(self.inbox_dir),
            "inbox_exists": self.inbox_dir.exists(),
            "total_files": len(list(self.inbox_dir.iterdir())) if self.inbox_dir.exists() else 0,
            "processed": processed_count,
            "pending": len(pending_files),
            "polling_active": self._polling,
            "processed_files": processed_files,
        }
