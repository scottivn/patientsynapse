"""OCR utility for extracting text from fax PDFs and images."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from a PDF file. Falls back to OCR if no embedded text."""
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        text = "\n".join(text_parts).strip()
        if len(text) > 50:
            logger.info(f"Extracted {len(text)} chars from PDF (embedded text)")
            return text

        # Fallback: OCR
        logger.info("No embedded text, attempting OCR...")
        return await _ocr_pdf(pdf_bytes)
    except ImportError:
        logger.warning("pypdf not installed, attempting OCR only")
        return await _ocr_pdf(pdf_bytes)


async def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from an image using OCR. Handles multi-page TIFFs."""
    try:
        import pytesseract
        from PIL import Image, ImageSequence
        import io

        img = Image.open(io.BytesIO(image_bytes))
        text_parts = []
        for i, frame in enumerate(ImageSequence.Iterator(img)):
            # Convert to RGB/L for consistent Tesseract handling
            frame_copy = frame.convert("L")
            page_text = pytesseract.image_to_string(frame_copy)
            if page_text.strip():
                text_parts.append(page_text)
            logger.info(f"OCR image page {i + 1}: {len(page_text)} chars")

        text = "\n".join(text_parts).strip()
        logger.info(f"OCR extracted {len(text)} chars from image ({i + 1} page(s))")
        return text
    except ImportError:
        logger.error("pytesseract or Pillow not installed")
        return ""


async def _ocr_pdf(pdf_bytes: bytes) -> str:
    """OCR a PDF by converting pages to images first."""
    try:
        import pdf2image
        import pytesseract

        images = pdf2image.convert_from_bytes(pdf_bytes)
        text_parts = []
        for i, img in enumerate(images):
            page_text = pytesseract.image_to_string(img)
            text_parts.append(page_text)
            logger.info(f"OCR page {i+1}: {len(page_text)} chars")
        return "\n".join(text_parts).strip()
    except ImportError:
        logger.error("pdf2image or pytesseract not installed for OCR")
        return ""
