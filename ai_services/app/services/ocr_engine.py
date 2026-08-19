"""OCR engine for automated vendor bill / invoice parsing."""
import asyncio
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

# Security caps: prevent decompression bomb attacks and giant files
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
Image.MAX_IMAGE_PIXELS = 50_000_000  # Max 50 megapixels


class OcrEngine:
    def _extract_text_sync(self, content: bytes, content_type: str, lang: str = "eng") -> str:
        """Extract text from image or PDF bytes synchronously."""
        if content_type == "application/pdf" or content[:4] == b"%PDF":
            return self._extract_pdf_text(content)

        image = Image.open(BytesIO(content))
        with image:
            image.verify()
        # Reopen for reading after verification
        image = Image.open(BytesIO(content))
        with image:
            try:
                text = pytesseract.image_to_string(image, lang=lang)
            except Exception:
                text = pytesseract.image_to_string(image)
        return text

    async def parse_invoice(self, file: UploadFile, meta: Any | None = None) -> dict[str, Any]:
        """Extract text from an image/PDF invoice and parse structured fields non-blockingly."""
        content = await self._read_bounded(file)
        text = await asyncio.to_thread(self._extract_text_sync, content, file.content_type or "", "eng")

        parsed = self._parse_text(text)
        parsed["raw_text"] = text
        return parsed

    async def _read_bounded(self, file: UploadFile) -> bytes:
        """Read the upload in chunks, rejecting anything larger than the limit."""
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise ValueError("File is too large (max 10 MB).")
            chunks.append(chunk)
        return b"".join(chunks)

    def _extract_pdf_text(self, content: bytes) -> str:
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp.flush()
                tmp_path = tmp.name
            # Cap to first 10 pages to prevent denial of service
            images = convert_from_path(tmp_path, dpi=200, last_page=10)
            parts = [pytesseract.image_to_string(img) for img in images]
            return "\n".join(parts)
        finally:
            import os

            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

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

    async def parse_business_document(self, file: UploadFile) -> dict[str, Any]:
        """Extract and categorize Saudi/Enterprise business documents (CR, VAT, GOSI, Address) non-blockingly."""
        content = await self._read_bounded(file)
        text = await asyncio.to_thread(self._extract_text_sync, content, file.content_type or "", "ara+eng")

        parsed = self._parse_business_document_text(text)
        parsed["raw_text"] = text
        return parsed

    def _parse_business_document_text(self, text: str) -> dict[str, Any]:
        """Pattern match and heuristic parse for CR, VAT, GOSI, and National Address."""
        full = text.lower()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # 1. Commercial Registration (CR)
        cr_patterns = [
            r"(?:سجل\s*تجاري|رقم\s*السجل|cr\s*no|commercial\s*reg|registration\s*no)[\s:–-]*([1-7]\d{9})",
            r"(?:رقم\s*الترخيص|رقم\s*القيد)[\s:–-]*([1-7]\d{9})",
            r"\b([1-7]\d{9})\b",
        ]
        cr_number = None
        for p in cr_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                cr_number = m.group(1)
                break

        # 2. VAT / Tax Number (15 digits, typically starts with 3 and ends with 3 in KSA)
        vat_patterns = [
            r"(?:الرقم\s*الضريبي|ضريبة\s*القيمة\s*المضافة|vat\s*no|tax\s*id|trn|vat\s*number)[\s:–-]*([3]\d{13}[3])",
            r"\b([3]\d{13}[3])\b",
            r"\b(\d{15})\b",
        ]
        vat_number = None
        for p in vat_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                vat_number = m.group(1)
                break

        # 3. GOSI / Social Insurance Number
        gosi_patterns = [
            r"(?:رقم\s*الاشتراك|رقم\s*المنشأة|التأمينات\s*الاجتماعية|gosi\s*no|establishment\s*no)[\s:–-]*(\d{7,10})",
            r"(?:المشتركين|المنشأة)[\s:–-]*(\d{8,10})",
        ]
        gosi_number = None
        for p in gosi_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                gosi_number = m.group(1)
                break

        # 4. Employee count from GOSI certificate
        emp_match = re.search(r"(?:عدد\s*المشتركين|عدد\s*الموظفين|إجمالي\s*العاملين|total\s*employees|workers)[\s:–-]*(\d+)", text, re.IGNORECASE)
        employee_count = int(emp_match.group(1)) if emp_match else None

        # 5. Company Name Extraction
        company_name_ar = None
        for line in lines:
            if any(kw in line for kw in ["شركة", "مؤسسة", "فرع شركة", "مجموعة", "مصنع", "مكتب", "متجر"]):
                # Clean line
                clean_name = re.sub(r"(?:اسم المنشأة|اسم الشركة|اسم المؤسسة|الاسم التجاري)[\s:–-]*", "", line).strip()
                if len(clean_name) > 3:
                    company_name_ar = clean_name
                    break

        # 6. Industry Sector Detection
        industry = "retail"
        if any(w in full for w in ["مطعم", "كافيه", "مقهى", "أغذية", "وجبات", "restaurant", "cafe", "food"]):
            industry = "restaurant"
        elif any(w in full for w in ["مصنع", "تصنيع", "صناعي", "إنتاج", "manufacturing", "factory"]):
            industry = "manufacturing"
        elif any(w in full for w in ["مقاولات", "بناء", "تشييد", "عقود", "construction", "contracting"]):
            industry = "construction"
        elif any(w in full for w in ["محطة", "وقود", "بنزين", "ديزل", "fuel", "gas station"]):
            industry = "fuel_station"
        elif any(w in full for w in ["عقار", "عقارات", "تطوير عقاري", "إيجار", "real estate"]):
            industry = "real_estate"
        elif any(w in full for w in ["طبي", "مستوصف", "عيادة", "صيدلية", "medical", "clinic", "health"]):
            industry = "healthcare"
        elif any(w in full for w in ["نقل", "لوجستي", "شحن", "تخزين", "transport", "logistics"]):
            industry = "logistics"

        # 7. Document Type Identification & Comprehensive Saudi Classification
        doc_type = "unknown"
        doc_title_ar = "وثيقة أعمال عامة"

        # Check National Address fields
        building_no = None
        postal_code = None
        additional_no = None
        district = None
        street = None

        bm = re.search(r"(?:رقم\s*المبنى|building\s*no|bldg\s*no)[\s:–-]*(\d{4})", text, re.I)
        if bm:
            building_no = bm.group(1)
        pm = re.search(r"(?:الرمز\s*البريدي|postal\s*code|zip)[\s:–-]*(\d{5})", text, re.I)
        if pm:
            postal_code = pm.group(1)
        am = re.search(r"(?:الرقم\s*الإضافي|additional\s*no)[\s:–-]*(\d{4})", text, re.I)
        if am:
            additional_no = am.group(1)
        dm = re.search(r"(?:الحي|district|حي)[\s:–-]*([^\n,]+)", text, re.I)
        if dm:
            district = dm.group(1).strip()
        sm = re.search(r"(?:الشارع|street|طريق)[\s:–-]*([^\n,]+)", text, re.I)
        if sm:
            street = sm.group(1).strip()

        # Check Balady Municipality License
        balady_m = re.search(r"(?:رخصة\s*بلدية|رخصة\s*نشاط\s*تجاري|منصة\s*بلدي|بلدي|رقم\s*الرخصة)[\s:–-]*(\d{8,14})", text, re.I)
        balady_license_no = balady_m.group(1) if balady_m else None

        # Check Saudization / Nitaqat
        saudization_rate = None
        sr_m = re.search(r"(?:نسبة\s*التوطين|السعودة)[\s:–-]*(\d+(?:\.\d+)?)\s*%", text, re.I)
        if sr_m:
            try:
                saudization_rate = float(sr_m.group(1))
            except Exception:
                pass

        if "سجل تجاري" in text or "وزارة التجارة" in text or "commercial registration" in full or (cr_number and "رأس المال" in text):
            doc_type = "cr"
            doc_title_ar = "📑 السجل التجاري (Commercial Registration)"
        elif "الزكاة والضريبة والجمارك" in text or "zatca" in full or (vat_number and ("ضريبة القيمة المضافة" in text or "شهادة تسجيل" in text)):
            doc_type = "vat"
            doc_title_ar = "🧾 شهادة ضريبة القيمة المضافة (VAT Certificate)"
        elif "العنوان الوطني" in text or "national address" in full or "سبل" in text or (building_no and postal_code):
            doc_type = "national_address"
            doc_title_ar = "📍 شهادة العنوان الوطني (National Address - سبل)"
        elif "التأمينات الاجتماعية" in text or "gosi" in full or "المؤسسة العامة للتأمينات" in text:
            doc_type = "gosi"
            doc_title_ar = "🛡️ شهادة التأمينات الاجتماعية (GOSI Certificate)"
        elif "بلدي" in text or "رخصة النشاط التجاري" in text or balady_license_no:
            doc_type = "balady"
            doc_title_ar = "🏢 رخصة النشاط التجاري البلدية (Balady License)"
        elif "نطاقات" in text or "شهادة السعودة" in text or "وزارة الموارد البشرية" in text:
            doc_type = "nitaqat"
            doc_title_ar = "👥 شهادة السعودة ونطاقات (Nitaqat Certificate)"
        elif "الغرفة التجارية" in text or "اشتراك الغرفة" in text:
            doc_type = "chamber"
            doc_title_ar = "🏛️ شهادة اشتراك الغرفة التجارية (Chamber of Commerce)"

        # 8. City and National Address Details
        city = None
        for c in ["الرياض", "جدة", "الدمام", "مكة", "المدينة", "الخبر", "القصيم", "تبوك", "أبها", "Riyadh", "Jeddah", "Dammam"]:
            if c.lower() in full:
                city = c
                break

        # 9. Dynamic AI Suggestions & Questions
        ai_questions = []
        suggested_modules = ["account_accountant", "stock"]

        if industry == "restaurant":
            suggested_modules += ["point_of_sale", "nexus_restaurant_costing"]
            ai_questions.append({
                "id": "q_pos_kds",
                "question_ar": "🎯 رصدنا أن نشاطك في المطاعم والمقاهي. هل ترغب في تفعيل نقاط البيع (POS) مع شاشات المطبخ الذكية (KDS) وحساب تكلفة الوجبات؟",
                "default": True,
            })
        elif industry == "fuel_station":
            suggested_modules += ["point_of_sale", "nexus_fuel_station"]
            ai_questions.append({
                "id": "q_fuel",
                "question_ar": "⛽ رصدنا نشاط محطات الوقود. هل ترغب بتفعيل إدارة الخزانات والمضخات ومطابقة الورديات؟",
                "default": True,
            })
        elif industry == "construction":
            suggested_modules += ["project", "nexus_contracting"]
            ai_questions.append({
                "id": "q_contracting",
                "question_ar": "🏗️ رصدنا نشاط المقاولات. هل ترغب بتفعيل إدارة عقود المشاريع والمستخلصات ونسبة الإنجاز (POC)؟",
                "default": True,
            })
        elif industry == "retail":
            suggested_modules += ["point_of_sale"]
            ai_questions.append({
                "id": "q_pos",
                "question_ar": "🛒 هل ترغب في تفعيل نقاط البيع السريعة الداعمة لمدى (Mada POS) وطباعة الفواتير الفورية؟",
                "default": True,
            })

        if vat_number or doc_type == "vat":
            suggested_modules.append("nexus_zatca_compliance")
            ai_questions.append({
                "id": "q_zatca",
                "question_ar": "🧾 رصدنا الرقم الضريبي. هل ترغب في تفعيل التكامل مع منصة فاتورة وهيئة الزكاة والضريبة (ZATCA Phase 2)؟",
                "default": True,
            })

        if employee_count and employee_count > 3:
            suggested_modules.append("hr")
            ai_questions.append({
                "id": "q_hr",
                "question_ar": f"👥 رصدنا عدد ({employee_count}) موظفاً في المنشأة. هل ترغب بتهيئة مسيرات الرواتب لحماية الأجور وهيكل الأقسام آلياً؟",
                "default": True,
            })

        score = sum(1 for v in [cr_number, vat_number, gosi_number, company_name_ar] if v is not None)
        confidence = min(score / 3.0 * 100, 100.0) if score > 0 else 50.0

        return {
            "document_type": doc_type,
            "document_title_ar": doc_title_ar,
            "cr_number": cr_number,
            "vat_number": vat_number,
            "gosi_number": gosi_number,
            "company_name_ar": company_name_ar,
            "company_name_en": None,
            "industry_sector": industry,
            "employee_count": employee_count,
            "saudization_rate": saudization_rate,
            "city": city,
            "district": district,
            "street": street,
            "building_no": building_no,
            "postal_code": postal_code,
            "confidence": round(confidence, 2),
            "ai_questions": ai_questions,
            "suggested_modules": list(set(suggested_modules)),
        }

    async def parse_employee_document(self, file: UploadFile) -> dict[str, Any]:
        """Extract and parse Saudi Iqama, National ID, or Passport data non-blockingly."""
        content = await self._read_bounded(file)
        text = await asyncio.to_thread(self._extract_text_sync, content, file.content_type or "", "ara+eng")
        return self._parse_employee_text(text)

    def _parse_employee_text(self, text: str) -> dict[str, Any]:
        """Extract name, ID/Iqama number, passport number, job, nationality from OCR text."""
        # Normalize Arabic Eastern digits (٠-٩)
        trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
        norm_text = text.translate(trans)
        full_lower = norm_text.lower()
        lines = [l.strip() for l in norm_text.splitlines() if l.strip()]

        doc_type = "iqama"
        doc_title_ar = "بطاقة الإقامة / الهوية الوطنية"
        iqama_number = None
        passport_number = None
        employee_name = None
        job_title = None
        nationality = None
        birth_date = None
        gender = "male"

        # 1. Iqama / National ID Number (10 digits starting with 1 or 2)
        iq_m = re.search(r"(?:رقم\s*الإقامة|رقم\s*الهوية|iqama\s*no|id\s*no)[\s:–-]*([12]\d{9})", norm_text, re.I)
        if not iq_m:
            iq_m = re.search(r"\b([12]\d{9})\b", norm_text)
        if iq_m:
            iqama_number = iq_m.group(1)

        # 2. Passport Number & MRZ Detection
        mrz_m = re.search(r"P<([A-Z]{3})([A-Z<]+)<<([A-Z<]+)", norm_text)
        pass_m = re.search(r"(?:passport\s*no|رقم\s*الجواز)[\s:–-]*([A-Za-z0-9]{7,10})", norm_text, re.I)
        if mrz_m:
            doc_type = "passport"
            doc_title_ar = "جواز السفر (Passport)"
            raw_surname = mrz_m.group(2).replace("<", " ").strip()
            raw_given = mrz_m.group(3).replace("<", " ").strip()
            employee_name = f"{raw_given} {raw_surname}".strip()
        elif pass_m:
            doc_type = "passport"
            doc_title_ar = "جواز السفر (Passport)"
            passport_number = pass_m.group(1).upper()

        # 3. Job / Profession (المهنة)
        job_m = re.search(r"(?:المهنة|المسمى\s*الوظيفي|الوظيفة|occupation|job\s*title)[\s:–-]*([^\n,]+)", norm_text, re.I)
        if job_m:
            job_title = job_m.group(1).strip()

        # 4. Nationality (الجنسية)
        nat_m = re.search(r"(?:الجنسية|nationality)[\s:–-]*([^\n,]+)", norm_text, re.I)
        if nat_m:
            nationality = nat_m.group(1).strip()

        # 5. Full Name fallback
        if not employee_name:
            name_m = re.search(r"(?:الاسم|اسم\s*المقيم|اسم\s*المواطن|name|full\s*name)[\s:–-]*([^\n]+)", norm_text, re.I)
            if name_m:
                employee_name = name_m.group(1).strip()
            else:
                for line in lines:
                    if len(line.split()) >= 3 and not any(kw in line for kw in ["المملكة", "وزارة", "الإقامة", "الجوازات"]):
                        employee_name = line
                        break

        # 6. Birth Date
        dob_m = re.search(r"(?:تاريخ\s*الميلاد|date\s*of\s*birth|dob)[\s:–-]*(\d{2,4}[/-]\d{1,2}[/-]\d{1,4})", norm_text, re.I)
        if dob_m:
            birth_date = dob_m.group(1)

        score = sum(1 for v in [iqama_number, passport_number, employee_name, job_title] if v is not None)
        confidence = min(score / 3.0 * 100, 100.0) if score > 0 else 50.0

        return {
            "document_type": doc_type,
            "document_title_ar": doc_title_ar,
            "iqama_number": iqama_number,
            "passport_number": passport_number,
            "employee_name": employee_name,
            "job_title": job_title,
            "nationality": nationality,
            "birth_date": birth_date,
            "gender": gender,
            "confidence": round(confidence, 2),
            "raw_text": norm_text,
        }



