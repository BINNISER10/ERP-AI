"""OCR engine for automated vendor bill / invoice parsing."""
import logging
import re
import tempfile
from datetime import datetime
from io import BytesIO
from typing import Any

import pytesseract
from fastapi import UploadFile
from PIL import Image
from pdf2image import convert_from_path

from app.config import settings

logger = logging.getLogger(__name__)


class OcrEngine:
    async def parse_invoice(self, file: UploadFile, meta: Any | None = None) -> dict[str, Any]:
        """Extract text from an image/PDF invoice and parse structured fields."""
        content = await file.read()

        if file.content_type == "application/pdf":
            text = self._extract_pdf_text(content)
        else:
            image = Image.open(BytesIO(content))
            # Ensure the image is closed after OCR.
            with image:
                image = image.copy()
            text = pytesseract.image_to_string(image)

        parsed = self._parse_text(text)
        parsed["raw_text"] = text
        return parsed

    def _extract_pdf_text(self, content: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            images = convert_from_path(tmp.name, dpi=200)
            parts = [pytesseract.image_to_string(img) for img in images]
        return "\n".join(parts)

    def _parse_text(self, text: str) -> dict[str, Any]:
        lines = text.splitlines()
        full = text.lower()

        vendor = self._extract_vendor(lines)
        invoice_number = self._extract_invoice_number(text)
        invoice_date = self._extract_date(text, r"(?:invoice date|date)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})")
        due_date = self._extract_date(text, r"(?:due date|payment due)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})")
        total = self._extract_amount(text, r"(?:total|amount due|balance due)\s*[:\-]?\s*\$?([0-9,]+\.?\d{0,2})")
        tax = self._extract_amount(text, r"(?:tax|vat|gst)\s*[:\-]?\s*\$?([0-9,]+\.?\d{0,2})")

        items = self._extract_line_items(lines)

        # Confidence is a rough heuristic based on key field presence.
        score = sum(
            1
            for v in [vendor, invoice_number, invoice_date, total]
            if v is not None
        )
        confidence = min(score / 4.0 * 100, 100.0)

        return {
            "vendor": vendor,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "total_amount": total,
            "tax_amount": tax,
            "currency": "USD" if "usd" in full or "$" in text else None,
            "confidence": round(confidence, 2),
            "lines": items,
        }

    def _extract_vendor(self, lines: list[str]) -> str | None:
        # First non-empty line is often the vendor name.
        for line in lines:
            clean = line.strip()
            if clean and not clean.lower().startswith(("invoice", "date", "total", "bill to")):
                return clean
        return None

    def _extract_invoice_number(self, text: str) -> str | None:
        patterns = [
            r"invoice\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Za-z0-9\-]+)",
            r"inv\s*(?:#|no\.?|number)?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_date(self, text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_amount(self, text: str, pattern: str) -> float | None:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                return None
        return None

    def _extract_line_items(self, lines: list[str]) -> list[dict[str, Any]]:
        items = []
        for line in lines:
            # Look for lines with quantity x price or total.
            match = re.search(r"(.+?)\s+(\d+)\s*[xX@]\s*\$?([0-9,.]+)", line)
            if match:
                desc = match.group(1).strip()
                qty = float(match.group(2))
                price = float(match.group(3).replace(",", ""))
                items.append({
                    "description": desc,
                    "quantity": qty,
                    "unit_price": price,
                    "total": round(qty * price, 2),
                })
        return items


