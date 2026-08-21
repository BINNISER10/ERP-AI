# -*- coding: utf-8 -*-
"""Nexus Smart Document Hunter & Conversational AI Wizard â€” ØµÙŠØ§Ø¯ ÙˆÙ…Ø¹Ø§Ù„Ø¬ Ø§Ù„ÙˆØ«Ø§Ø¦Ù‚ Ø§Ù„Ø°ÙƒÙŠ.

Automatically extracts data from Saudi Commercial Registration (CR), VAT Certificate,
GOSI Certificate, and National Address, then uses conversational AI to ask contextual
questions and auto-provision the entire ERP instance in one click.
"""

import base64
import json
import logging
import re
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NexusDocumentHunterWizard(models.TransientModel):
    _name = "nexus.document.hunter.wizard"
    _description = "Nexus Smart Document Hunter & AI Onboarding Wizard"

    # â”€â”€ Status â”€â”€
    state = fields.Selection(
        [
            ("upload", "1. Ø±ÙØ¹ Ø§Ù„Ù…Ø³ØªÙ†Ø¯Ø§Øª (Upload Documents)"),
            ("extracted", "2. Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…ØµØ·Ø§Ø¯Ø© ÙˆØ£Ø³Ø¦Ù„Ø© Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ (AI Review)"),
            ("completed", "3. ØªÙ… Ø§Ù„ØªØ£Ø³ÙŠØ³ Ø¨Ù†Ø¬Ø§Ø­ (Provisioned)"),
        ],
        default="upload",
        required=True,
    )

    # â”€â”€ Upload Dropzones (Single Unified AI Dropzone) â”€â”€
    upload_document_file = fields.Binary(string="Ø§Ø³Ø­Ø¨ Ø£Ùˆ Ø§Ø±ÙØ¹ Ø£ÙŠ ÙˆØ«ÙŠÙ‚Ø© Ø±Ø³Ù…ÙŠØ© Ù‡Ù†Ø§ (Single AI Dropzone)", attachment=True)
    upload_document_filename = fields.Char(string="Ø§Ø³Ù… Ù…Ù„Ù Ø§Ù„ÙˆØ«ÙŠÙ‚Ø©")

    # Legacy dropzones for backwards compatibility
    cr_file = fields.Binary(string="Ø§Ù„Ø³Ø¬Ù„ Ø§Ù„ØªØ¬Ø§Ø±ÙŠ (Commercial Registration)", attachment=True)
    cr_filename = fields.Char(string="CR File Name")
    vat_file = fields.Binary(string="Ø§Ù„Ø´Ù‡Ø§Ø¯Ø© Ø§Ù„Ø¶Ø±ÙŠØ¨ÙŠØ© (VAT Certificate)", attachment=True)
    vat_filename = fields.Char(string="VAT File Name")
    gosi_file = fields.Binary(string="Ø´Ù‡Ø§Ø¯Ø© Ø§Ù„ØªØ£Ù…ÙŠÙ†Ø§Øª (GOSI Certificate)", attachment=True)
    gosi_filename = fields.Char(string="GOSI File Name")
    address_file = fields.Binary(string="Ø§Ù„Ø¹Ù†ÙˆØ§Ù† Ø§Ù„ÙˆØ·Ù†ÙŠ / Ø±Ø®ØµØ© Ø§Ù„Ø¨Ù„Ø¯ÙŠØ© (National Address / Balady)", attachment=True)
    address_filename = fields.Char(string="Address File Name")
    any_document_file = fields.Binary(string="Ù…Ø³ØªÙ†Ø¯ Ù…Ø¬Ù…Ø¹ Ø£Ùˆ ÙˆØ«ÙŠÙ‚Ø© Ø£Ø¹Ù…Ø§Ù„ (Any Document)", attachment=True)
    any_document_filename = fields.Char(string="Document File Name")

    # â”€â”€ Auto-Extracted Fields â”€â”€
    detected_doc_type_title = fields.Char(string="Ù†ÙˆØ¹ Ø§Ù„ÙˆØ«ÙŠÙ‚Ø© Ø§Ù„Ù…ØµØ·Ø§Ø¯Ø©", readonly=True)
    company_name = fields.Char(string="Ø§Ø³Ù… Ø§Ù„Ù…Ù†Ø´Ø£Ø© / Ø§Ù„Ø´Ø±ÙƒØ© (Company Name)")
    company_name_ar = fields.Char(string="Ø§Ù„Ø§Ø³Ù… Ø§Ù„ØªØ¬Ø§Ø±ÙŠ Ø¨Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©")
    cr_number = fields.Char(string="Ø±Ù‚Ù… Ø§Ù„Ø³Ø¬Ù„ Ø§Ù„ØªØ¬Ø§Ø±ÙŠ (CR Number)", placeholder="1010XXXXXX")
    vat_number = fields.Char(string="Ø§Ù„Ø±Ù‚Ù… Ø§Ù„Ø¶Ø±ÙŠØ¨ÙŠ (VAT / Tax ID)", placeholder="3000XXXXXXXX003")
    gosi_number = fields.Char(string="Ø±Ù‚Ù… Ø§Ø´ØªØ±Ø§Ùƒ Ø§Ù„ØªØ£Ù…ÙŠÙ†Ø§Øª (GOSI Number)", placeholder="700XXXXXXX")
    balady_license_no = fields.Char(string="Ø±Ù‚Ù… Ø±Ø®ØµØ© Ø¨Ù„Ø¯ÙŠ", placeholder="1445XXXXXXXX")
    saudization_rate = fields.Float(string="Ù†Ø³Ø¨Ø© Ø§Ù„ØªÙˆØ·ÙŠÙ† / Ø§Ù„Ø³Ø¹ÙˆØ¯Ø© (%)")

    industry_sector = fields.Selection(
        [
            ("retail", "ØªØ¬Ø§Ø±Ø© Ø§Ù„ØªØ¬Ø²Ø¦Ø© / Retail"),
            ("restaurant", "Ù…Ø·Ø§Ø¹Ù… ÙˆÙƒØ§ÙÙŠÙ‡Ø§Øª / F&B"),
            ("manufacturing", "ØªØµÙ†ÙŠØ¹ ÙˆØ¥Ù†ØªØ§Ø¬ / Manufacturing"),
            ("construction", "Ù…Ù‚Ø§ÙˆÙ„Ø§Øª ÙˆØªØ´ÙŠÙŠØ¯ / Construction"),
            ("services", "Ø®Ø¯Ù…Ø§Øª Ø¹Ø§Ù…Ø© ÙˆØ§Ø³ØªØ´Ø§Ø±Ø§Øª / Services"),
            ("healthcare", "Ø±Ø¹Ø§ÙŠØ© ØµØ­ÙŠØ© ÙˆÙ…Ø³ØªÙ„Ø²Ù…Ø§Øª / Healthcare"),
            ("fuel_station", "Ù…Ø­Ø·Ø§Øª ÙˆÙ‚ÙˆØ¯ / Fuel Station"),
            ("real_estate", "Ø¹Ù‚Ø§Ø±Ø§Øª ÙˆØ¥Ø¯Ø§Ø±Ø© Ø£Ù…Ù„Ø§Ùƒ / Real Estate"),
            ("logistics", "Ù†Ù‚Ù„ ÙˆÙ„ÙˆØ¬Ø³ØªÙŠØ§Øª / Logistics"),
            ("other", "Ø£Ø®Ø±Ù‰ / Other"),
        ],
        string="Ø§Ù„Ù†Ø´Ø§Ø· Ø§Ù„ØªØ¬Ø§Ø±ÙŠ (Activity)",
        default="retail",
    )
    employee_count = fields.Integer(string="Ø¹Ø¯Ø¯ Ø§Ù„Ù…ÙˆØ¸ÙÙŠÙ† Ø§Ù„Ù…Ø±ØµÙˆØ¯ (Employees)", default=5)
    capital = fields.Float(string="Ø±Ø£Ø³ Ø§Ù„Ù…Ø§Ù„ (Capital)")
    city = fields.Char(string="Ø§Ù„Ù…Ø¯ÙŠÙ†Ø© (City)", default="Ø§Ù„Ø±ÙŠØ§Ø¶")
    district = fields.Char(string="Ø§Ù„Ø­ÙŠ (District)")
    street = fields.Char(string="Ø§Ù„Ø´Ø§Ø±Ø¹ (Street)")
    building_no = fields.Char(string="Ø±Ù‚Ù… Ø§Ù„Ù…Ø¨Ù†Ù‰ (Building No)")
    additional_no = fields.Char(string="Ø§Ù„Ø±Ù‚Ù… Ø§Ù„Ø¥Ø¶Ø§ÙÙŠ (Additional No)")
    postal_code = fields.Char(string="Ø§Ù„Ø±Ù…Ø² Ø§Ù„Ø¨Ø±ÙŠØ¯ÙŠ (Postal Code)")
    national_short_address = fields.Char(string="Ø§Ù„Ø¹Ù†ÙˆØ§Ù† Ø§Ù„Ù…Ø®ØªØµØ± (Short Address)", placeholder="RRRD2934")

    # â”€â”€ Conversational AI Options â”€â”€
    opt_pos_kds = fields.Boolean(
        string="ðŸ›’ Ù†Ù‚Ø§Ø· Ø§Ù„Ø¨ÙŠØ¹ ÙˆØ´Ø§Ø´Ø§Øª Ø§Ù„Ù…Ø·Ø¨Ø®: ØªÙØ¹ÙŠÙ„ Ù†Ù‚Ø§Ø· Ø¨ÙŠØ¹ Ù…ØªÙˆØ§ÙÙ‚Ø© Ù…Ø¹ Ù…Ø¯Ù‰ ÙˆØ´Ø§Ø´Ø§Øª KDS",
        default=True,
    )
    opt_zatca = fields.Boolean(
        string="ðŸ§¾ Ø§Ù„ÙÙˆØªØ±Ø© Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠØ©: ØªÙØ¹ÙŠÙ„ Ø§Ù„Ø§Ù…ØªØ«Ø§Ù„ Ù„Ù„Ø±Ø¨Ø· Ù…Ø¹ Ù‡ÙŠØ¦Ø© Ø§Ù„Ø²ÙƒØ§Ø© (ZATCA Phase 2)",
        default=True,
    )
    opt_payroll_wps = fields.Boolean(
        string="ðŸ‘¥ Ø§Ù„Ù…ÙˆØ§Ø±Ø¯ Ø§Ù„Ø¨Ø´Ø±ÙŠØ© ÙˆØ­Ù…Ø§ÙŠØ© Ø§Ù„Ø£Ø¬ÙˆØ±: ØªÙ‡ÙŠØ¦Ø© Ù…Ù„ÙØ§Øª Ø§Ù„Ø±ÙˆØ§ØªØ¨ (WPS) ÙˆØ£Ù‚Ø³Ø§Ù… Ø§Ù„Ù…ÙˆØ¸ÙÙŠÙ†",
        default=True,
    )
    opt_accounting_chart = fields.Boolean(
        string="ðŸ’° Ø§Ù„Ù…Ø­Ø§Ø³Ø¨Ø© Ø§Ù„Ù…ØªÙ‚Ø¯Ù…Ø©: Ø¥Ù†Ø´Ø§Ø¡ Ø¯Ù„ÙŠÙ„ Ø­Ø³Ø§Ø¨Ø§Øª Ø´Ø¬Ø±ÙŠ Ù…ØªÙˆØ§ÙÙ‚ Ù…Ø¹ Ù…Ø¹Ø§ÙŠÙŠØ± IFRS ÙˆØ§Ù„Ù†Ø´Ø§Ø·",
        default=True,
    )
    opt_warehouses = fields.Boolean(
        string="ðŸ“¦ Ø§Ù„Ù…Ø³ØªÙˆØ¯Ø¹Ø§Øª ÙˆØ§Ù„Ù…Ø®Ø²ÙˆÙ†: Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ù…Ø³ØªÙˆØ¯Ø¹ Ø§Ù„Ø±Ø¦ÙŠØ³ÙŠ ÙˆÙ…ÙˆØ§Ù‚Ø¹ Ø§Ù„ØªØ®Ø²ÙŠÙ† Ø§Ù„Ø§ÙØªØ±Ø§Ø¶ÙŠØ©",
        default=True,
    )

    ai_analysis_html = fields.Html(string="AI Analysis Display", readonly=True)
    ai_conversation_html = fields.Html(string="AI Conversation", readonly=True)

    def _extract_text_from_binary(self, binary_data, filename=""):
        """Extract plain text and search patterns from binary (PDF/Image/Text)."""
        if not binary_data:
            return ""
        try:
            raw_bytes = base64.b64decode(binary_data)
        except Exception:
            return ""

        # 1. Try sending to AI Microservices if available
        try:
            url = "http://nexus_ai:8000/api/v1/ocr/document-hunter"
            files = {"file": (filename or "document.pdf", raw_bytes, "application/octet-stream")}
            resp = requests.post(url, files=files, timeout=4)
            if resp.ok:
                data = resp.json()
                return data.get("raw_text", "")
        except Exception:
            pass

        # 2. Fallback: Search strings and UTF-8 decodable blocks
        text_parts = []
        try:
            # Decode ascii/utf-8 strings
            text_parts.append(raw_bytes.decode("utf-8", errors="ignore"))
        except Exception:
            pass
        return " ".join(text_parts)

    def action_hunt_and_extract(self):
        """AI Document Hunter Engine â€” Parses all uploaded documents and extracts fields."""
        self.ensure_one()

        all_texts = []
        files_to_check = [
            (self.upload_document_file, self.upload_document_filename, "unified"),
            (self.cr_file, self.cr_filename, "cr"),
            (self.vat_file, self.vat_filename, "vat"),
            (self.gosi_file, self.gosi_filename, "gosi"),
            (self.address_file, self.address_filename, "address"),
            (self.any_document_file, self.any_document_filename, "any"),
        ]

        uploaded_count = sum(1 for f in files_to_check if f[0])
        if uploaded_count == 0:
            raise UserError(_("ÙŠØ±Ø¬Ù‰ Ø³Ø­Ø¨ Ø£Ùˆ Ø±ÙØ¹ ÙˆØ«ÙŠÙ‚Ø© Ø±Ø³Ù…ÙŠØ© ÙˆØ§Ø­Ø¯Ø© Ø¹Ù„Ù‰ Ø§Ù„Ø£Ù‚Ù„ (Ø§Ù„Ø³Ø¬Ù„ Ø§Ù„ØªØ¬Ø§Ø±ÙŠØŒ Ø§Ù„Ø´Ù‡Ø§Ø¯Ø© Ø§Ù„Ø¶Ø±ÙŠØ¨ÙŠØ©ØŒ Ø§Ù„Ø¹Ù†ÙˆØ§Ù† Ø§Ù„ÙˆØ·Ù†ÙŠØŒ Ø§Ù„ØªØ£Ù…ÙŠÙ†Ø§ØªØŒ Ø±Ø®ØµØ© Ø¨Ù„Ø¯ÙŠ) Ù„Ù„Ø¨Ø¯Ø¡ ÙÙŠ Ø§Ù„Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ù„Ø¢Ù„ÙŠ."))

        for b_data, f_name, doc_label in files_to_check:
            if b_data:
                txt = self._extract_text_from_binary(b_data, f_name)
                all_texts.append(txt)

        combined_text = "\n".join(all_texts)
        full_lower = combined_text.lower()

        # 1. Extract CR Number (10 digits starting with 1 to 5)
        cr_m = re.search(r"(?:Ø³Ø¬Ù„\s*ØªØ¬Ø§Ø±ÙŠ|Ø±Ù‚Ù…\s*Ø§Ù„Ø³Ø¬Ù„|cr\s*no|commercial\s*reg)[\s:â€“-]*([1-5]\d{9})", combined_text, re.I)
        if not cr_m:
            cr_m = re.search(r"\b([1-5]\d{9})\b", combined_text)
        if cr_m:
            self.cr_number = cr_m.group(1)

        # 2. Extract VAT Number (15 digits starting and ending with 3)
        vat_m = re.search(r"(?:Ø§Ù„Ø±Ù‚Ù…\s*Ø§Ù„Ø¶Ø±ÙŠØ¨ÙŠ|Ø¶Ø±ÙŠØ¨Ø©\s*Ø§Ù„Ù‚ÙŠÙ…Ø©\s*Ø§Ù„Ù…Ø¶Ø§ÙØ©|vat\s*no|tax\s*id)[\s:â€“-]*([3]\d{13}[3])", combined_text, re.I)
        if not vat_m:
            vat_m = re.search(r"\b([3]\d{13}[3])\b", combined_text)
        if not vat_m:
            vat_m = re.search(r"\b(\d{15})\b", combined_text)
        if vat_m:
            self.vat_number = vat_m.group(1)

        # 3. Extract GOSI / Unified 700 Number
        gosi_m = re.search(r"(?:Ø±Ù‚Ù…\s*Ø§Ù„Ø§Ø´ØªØ±Ø§Ùƒ|Ø±Ù‚Ù…\s*Ø§Ù„Ù…Ù†Ø´Ø£Ø©|Ø§Ù„ØªØ£Ù…ÙŠÙ†Ø§Øª\s*Ø§Ù„Ø§Ø¬ØªÙ…Ø§Ø¹ÙŠØ©|Ø§Ù„Ø±Ù‚Ù…\s*Ø§Ù„Ù…ÙˆØ­Ø¯|gosi\s*no)[\s:â€“-]*([7]\d{9}|\d{7,10})", combined_text, re.I)
        if not gosi_m:
            gosi_m = re.search(r"\b(700\d{7})\b", combined_text)
        if gosi_m:
            self.gosi_number = gosi_m.group(1)

        # 4. Extract Balady License No
        balady_m = re.search(r"(?:Ø±Ø®ØµØ©\s*Ø¨Ù„Ø¯ÙŠØ©|Ø±Ø®ØµØ©\s*Ù†Ø´Ø§Ø·\s*ØªØ¬Ø§Ø±ÙŠ|Ù…Ù†ØµØ©\s*Ø¨Ù„Ø¯ÙŠ|Ø¨Ù„Ø¯ÙŠ|Ø±Ù‚Ù…\s*Ø§Ù„Ø±Ø®ØµØ©)[\s:â€“-]*(\d{8,14})", combined_text, re.I)
        if balady_m:
            self.balady_license_no = balady_m.group(1)

        # 5. National Address Details (Building No, Postal Code, Additional No, District, Street)
        bm = re.search(r"(?:Ø±Ù‚Ù…\s*Ø§Ù„Ù…Ø¨Ù†Ù‰|building\s*no)[\s:â€“-]*(\d{4})", combined_text, re.I)
        if bm:
            self.building_no = bm.group(1)
        pm = re.search(r"(?:Ø§Ù„Ø±Ù…Ø²\s*Ø§Ù„Ø¨Ø±ÙŠØ¯ÙŠ|postal\s*code|zip)[\s:â€“-]*(\d{5})", combined_text, re.I)
        if pm:
            self.postal_code = pm.group(1)
        am = re.search(r"(?:Ø§Ù„Ø±Ù‚Ù…\s*Ø§Ù„Ø¥Ø¶Ø§ÙÙŠ|additional\s*no)[\s:â€“-]*(\d{4})", combined_text, re.I)
        if am:
            self.additional_no = am.group(1)
        dm = re.search(r"(?:Ø§Ù„Ø­ÙŠ|district|Ø­ÙŠ)[\s:â€“-]*([^\n,]+)", combined_text, re.I)
        if dm:
            self.district = dm.group(1).strip()
        sm = re.search(r"(?:Ø§Ù„Ø´Ø§Ø±Ø¹|street|Ø·Ø±ÙŠÙ‚)[\s:â€“-]*([^\n,]+)", combined_text, re.I)
        if sm:
            self.street = sm.group(1).strip()

        # 6. Saudization / Nitaqat
        sr_m = re.search(r"(?:Ù†Ø³Ø¨Ø©\s*Ø§Ù„ØªÙˆØ·ÙŠÙ†|Ø§Ù„Ø³Ø¹ÙˆØ¯Ø©)[\s:â€“-]*(\d+(?:\.\d+)?)\s*%", combined_text, re.I)
        if sr_m:
            try:
                self.saudization_rate = float(sr_m.group(1))
            except Exception:
                pass

        # 7. Extract Employee count
        emp_m = re.search(r"(?:Ø¹Ø¯Ø¯\s*Ø§Ù„Ù…Ø´ØªØ±ÙƒÙŠÙ†|Ø¹Ø¯Ø¯\s*Ø§Ù„Ù…ÙˆØ¸ÙÙŠÙ†|Ø¥Ø¬Ù…Ø§Ù„ÙŠ\s*Ø§Ù„Ø¹Ø§Ù…Ù„ÙŠÙ†|total\s*employees)[\s:â€“-]*(\d+)", combined_text, re.I)
        if emp_m:
            self.employee_count = int(emp_m.group(1))

        # 5. Extract Company Name
        lines = [l.strip() for l in combined_text.splitlines() if l.strip()]
        for line in lines:
            if any(kw in line for kw in ["Ø´Ø±ÙƒØ©", "Ù…Ø¤Ø³Ø³Ø©", "ÙØ±Ø¹ Ø´Ø±ÙƒØ©", "Ù…Ø¬Ù…ÙˆØ¹Ø©", "Ù…ØµÙ†Ø¹"]):
                clean = re.sub(r"(?:Ø§Ø³Ù… Ø§Ù„Ù…Ù†Ø´Ø£Ø©|Ø§Ø³Ù… Ø§Ù„Ø´Ø±ÙƒØ©|Ø§Ø³Ù… Ø§Ù„Ù…Ø¤Ø³Ø³Ø©|Ø§Ù„Ø§Ø³Ù… Ø§Ù„ØªØ¬Ø§Ø±ÙŠ)[\s:â€“-]*", "", line).strip()
                if 3 < len(clean) < 80:
                    self.company_name = clean
                    self.company_name_ar = clean
                    break

        if not self.company_name:
            self.company_name = self.env.company.name or "Ø´Ø±ÙƒØ© Ø§Ù„Ø£Ø¹Ù…Ø§Ù„ Ø§Ù„Ù…ØªÙ‚Ø¯Ù…Ø©"
            self.company_name_ar = self.company_name

        # 6. Sector Detection
        if any(w in full_lower for w in ["Ù…Ø·Ø¹Ù…", "ÙƒØ§ÙÙŠÙ‡", "Ù…Ù‚Ù‡Ù‰", "Ø£ØºØ°ÙŠØ©", "ÙˆØ¬Ø¨Ø§Øª", "restaurant", "cafe"]):
            self.industry_sector = "restaurant"
        elif any(w in full_lower for w in ["Ù…ØµÙ†Ø¹", "ØªØµÙ†ÙŠØ¹", "ØµÙ†Ø§Ø¹ÙŠ", "Ø¥Ù†ØªØ§Ø¬", "manufacturing"]):
            self.industry_sector = "manufacturing"
        elif any(w in full_lower for w in ["Ù…Ù‚Ø§ÙˆÙ„Ø§Øª", "Ø¨Ù†Ø§Ø¡", "ØªØ´ÙŠÙŠØ¯", "Ø¹Ù‚ÙˆØ¯", "construction"]):
            self.industry_sector = "construction"
        elif any(w in full_lower for w in ["Ù…Ø­Ø·Ø©", "ÙˆÙ‚ÙˆØ¯", "Ø¨Ù†Ø²ÙŠÙ†", "Ø¯ÙŠØ²Ù„", "fuel"]):
            self.industry_sector = "fuel_station"
        elif any(w in full_lower for w in ["Ø¹Ù‚Ø§Ø±", "Ø¹Ù‚Ø§Ø±Ø§Øª", "ØªØ·ÙˆÙŠØ± Ø¹Ù‚Ø§Ø±ÙŠ", "Ø¥ÙŠØ¬Ø§Ø±", "real estate"]):
            self.industry_sector = "real_estate"
        elif any(w in full_lower for w in ["Ø·Ø¨ÙŠ", "Ù…Ø³ØªÙˆØµÙ", "Ø¹ÙŠØ§Ø¯Ø©", "ØµÙŠØ¯Ù„ÙŠØ©", "medical"]):
            self.industry_sector = "healthcare"
        elif any(w in full_lower for w in ["Ù†Ù‚Ù„", "Ù„ÙˆØ¬Ø³ØªÙŠ", "Ø´Ø­Ù†", "ØªØ®Ø²ÙŠÙ†", "logistics"]):
            self.industry_sector = "logistics"
        else:
            self.industry_sector = "retail"

        # 7. City Detection
        for c in ["Ø§Ù„Ø±ÙŠØ§Ø¶", "Ø¬Ø¯Ø©", "Ø§Ù„Ø¯Ù…Ø§Ù…", "Ù…ÙƒØ©", "Ø§Ù„Ù…Ø¯ÙŠÙ†Ø©", "Ø§Ù„Ø®Ø¨Ø±", "Ø§Ù„Ù‚ØµÙŠÙ…", "ØªØ¨ÙˆÙƒ", "Ø£Ø¨Ù‡Ø§"]:
            if c in combined_text:
                self.city = c
                break

        # 8. Document Classification
        doc_type_title = "ðŸ“„ ÙˆØ«ÙŠÙ‚Ø© Ø£Ø¹Ù…Ø§Ù„ Ø±Ø³Ù…ÙŠØ©"
        if "Ø³Ø¬Ù„ ØªØ¬Ø§Ø±ÙŠ" in combined_text or "ÙˆØ²Ø§Ø±Ø© Ø§Ù„ØªØ¬Ø§Ø±Ø©" in combined_text or (cr_m and "Ø±Ø£Ø³ Ø§Ù„Ù…Ø§Ù„" in combined_text):
            doc_type_title = "ðŸ“‘ Ø§Ù„Ø³Ø¬Ù„ Ø§Ù„ØªØ¬Ø§Ø±ÙŠ (Commercial Registration)"
        elif "Ø§Ù„Ø²ÙƒØ§Ø© ÙˆØ§Ù„Ø¶Ø±ÙŠØ¨Ø© ÙˆØ§Ù„Ø¬Ù…Ø§Ø±Ùƒ" in combined_text or "zatca" in full_lower or (vat_m and ("Ø¶Ø±ÙŠØ¨Ø© Ø§Ù„Ù‚ÙŠÙ…Ø© Ø§Ù„Ù…Ø¶Ø§ÙØ©" in combined_text or "Ø´Ù‡Ø§Ø¯Ø© ØªØ³Ø¬ÙŠÙ„" in combined_text)):
            doc_type_title = "ðŸ§¾ Ø´Ù‡Ø§Ø¯Ø© Ø¶Ø±ÙŠØ¨Ø© Ø§Ù„Ù‚ÙŠÙ…Ø© Ø§Ù„Ù…Ø¶Ø§ÙØ© (VAT Certificate)"
        elif "Ø§Ù„Ø¹Ù†ÙˆØ§Ù† Ø§Ù„ÙˆØ·Ù†ÙŠ" in combined_text or "national address" in full_lower or "Ø³Ø¨Ù„" in combined_text or (bm and pm):
            doc_type_title = "ðŸ“ Ø´Ù‡Ø§Ø¯Ø© Ø§Ù„Ø¹Ù†ÙˆØ§Ù† Ø§Ù„ÙˆØ·Ù†ÙŠ (National Address - Ø³Ø¨Ù„)"
        elif "Ø§Ù„ØªØ£Ù…ÙŠÙ†Ø§Øª Ø§Ù„Ø§Ø¬ØªÙ…Ø§Ø¹ÙŠØ©" in combined_text or "gosi" in full_lower:
            doc_type_title = "ðŸ›¡ï¸ Ø´Ù‡Ø§Ø¯Ø© Ø§Ù„ØªØ£Ù…ÙŠÙ†Ø§Øª Ø§Ù„Ø§Ø¬ØªÙ…Ø§Ø¹ÙŠØ© (GOSI Certificate)"
        elif "Ø¨Ù„Ø¯ÙŠ" in combined_text or "Ø±Ø®ØµØ© Ø§Ù„Ù†Ø´Ø§Ø· Ø§Ù„ØªØ¬Ø§Ø±ÙŠ" in combined_text or balady_m:
            doc_type_title = "ðŸ¢ Ø±Ø®ØµØ© Ø§Ù„Ù†Ø´Ø§Ø· Ø§Ù„ØªØ¬Ø§Ø±ÙŠ Ø§Ù„Ø¨Ù„Ø¯ÙŠØ© (Balady License)"
        elif "Ù†Ø·Ø§Ù‚Ø§Øª" in combined_text or "Ø´Ù‡Ø§Ø¯Ø© Ø§Ù„Ø³Ø¹ÙˆØ¯Ø©" in combined_text or "ÙˆØ²Ø§Ø±Ø© Ø§Ù„Ù…ÙˆØ§Ø±Ø¯ Ø§Ù„Ø¨Ø´Ø±ÙŠØ©" in combined_text:
            doc_type_title = "ðŸ‘¥ Ø´Ù‡Ø§Ø¯Ø© Ø§Ù„Ø³Ø¹ÙˆØ¯Ø© ÙˆÙ†Ø·Ø§Ù‚Ø§Øª (Nitaqat Certificate)"
        elif "Ø§Ù„ØºØ±ÙØ© Ø§Ù„ØªØ¬Ø§Ø±ÙŠØ©" in combined_text or "Ø§Ø´ØªØ±Ø§Ùƒ Ø§Ù„ØºØ±ÙØ©" in combined_text:
            doc_type_title = "ðŸ›ï¸ Ø´Ù‡Ø§Ø¯Ø© Ø§Ø´ØªØ±Ø§Ùƒ Ø§Ù„ØºØ±ÙØ© Ø§Ù„ØªØ¬Ø§Ø±ÙŠØ© (Chamber of Commerce)"

        self.detected_doc_type_title = doc_type_title

        # 9. Render Rich AI Analysis & Conversational Cards
        detected_badges = []
        if self.cr_number:
            detected_badges.append(f'<span class="badge bg-success p-2 me-2 mb-2" style="font-size:13px;">ðŸ“‘ Ø§Ù„Ø³Ø¬Ù„ Ø§Ù„ØªØ¬Ø§Ø±ÙŠ: {self.cr_number}</span>')
        if self.vat_number:
            detected_badges.append(f'<span class="badge bg-success p-2 me-2 mb-2" style="font-size:13px;">ðŸ§¾ Ø§Ù„Ø±Ù‚Ù… Ø§Ù„Ø¶Ø±ÙŠØ¨ÙŠ: {self.vat_number}</span>')
        if self.gosi_number:
            detected_badges.append(f'<span class="badge bg-success p-2 me-2 mb-2" style="font-size:13px;">ðŸ›¡ï¸ Ø§Ù„ØªØ£Ù…ÙŠÙ†Ø§Øª: {self.gosi_number} ({self.employee_count} Ù…ÙˆØ¸Ù)</span>')
        if self.balady_license_no:
            badges.append(f'<span class="badge bg-success p-2 me-2 mb-2" style="font-size:13px;">ðŸ¢ Ø±Ø®ØµØ© Ø¨Ù„Ø¯ÙŠ: {self.balady_license_no}</span>')
        if self.building_no or self.district:
            addr_str = f"{self.city or ''} - {self.district or ''} - Ù…Ø¨Ù†Ù‰ {self.building_no or ''}"
            badges.append(f'<span class="badge bg-info p-2 me-2 mb-2" style="font-size:13px;">ðŸ“ Ø§Ù„Ø¹Ù†ÙˆØ§Ù† Ø§Ù„ÙˆØ·Ù†ÙŠ: {addr_str}</span>')
        if self.city:
            detected_badges.append(f'<span class="badge bg-info p-2 me-2 mb-2" style="font-size:13px;">ðŸ“ Ø§Ù„Ù…Ø±ÙƒØ² Ø§Ù„Ø±Ø¦ÙŠØ³ÙŠ: {self.city}</span>')

        self.ai_analysis_html = f"""
            <div class="alert alert-success border-0 shadow-sm p-3 mb-3" style="border-radius: 10px; background-color: #E8F5E9;">
                <h5 class="text-success mb-2 font-weight-bold">ðŸŽ¯ ØªÙ… Ø§Ù„ØªØ¹Ø±Ù Ø¨Ù†Ø¬Ø§Ø­ Ø¹Ù„Ù‰: {doc_type_title}</h5>
                <p class="mb-2 text-dark">ØªÙ… Ù…Ø³Ø­ Ø§Ù„Ù…Ø³ØªÙ†Ø¯Ø§Øª Ø§Ù„Ù…Ø±ÙÙˆØ¹Ø© ÙˆØ§Ù„ØªØ¹Ø±Ù Ø¹Ù„Ù‰ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø±Ø³Ù…ÙŠØ© Ø§Ù„ØªØ§Ù„ÙŠØ© Ø¨Ø¯Ù‚Ø© Ø¹Ø§Ù„ÙŠØ©:</p>
                <div class="d-flex flex-wrap mt-2">
                    {' '.join(detected_badges)}
                </div>
            </div>
        """

        # Conversational questions generated by AI
        sector_labels = dict(self._fields["industry_sector"].selection)
        sector_name = sector_labels.get(self.industry_sector, self.industry_sector)

        ai_dialogue = f"""
            <div class="card border-primary mb-3 shadow-sm" style="border-radius: 10px; border-width: 2px;">
                <div class="card-header bg-primary text-white font-weight-bold d-flex align-items-center">
                    <span class="fa fa-robot fa-lg me-2"></span>
                    <span>Ø§Ù„Ù…Ø³Ø§Ø¹Ø¯ Ø§Ù„Ø°ÙƒÙŠ Ù„ØªØ£Ø³ÙŠØ³ Ø§Ù„Ù…Ù†Ø´Ø£Ø© (Nexus AI Consultant):</span>
                </div>
                <div class="card-body bg-light">
                    <p class="lead mb-2" style="font-size: 16px;">
                        Â« Ù…Ø±Ø­Ø¨Ø§Ù‹! Ù‚Ù…ØªÙ Ø¨ÙØ­Øµ Ø§Ù„Ø³Ø¬Ù„ ÙˆØ§Ù„Ø´Ù‡Ø§Ø¯Ø§Øª Ø§Ù„Ù…Ø±ÙÙˆØ¹Ø© Ù„Ù…Ù†Ø´Ø£ØªÙƒÙ… <b>({self.company_name})</b>.
                        Ù†Ø´Ø§Ø·ÙƒÙ… Ø§Ù„Ø±Ø¦ÙŠØ³ÙŠ Ù‡Ùˆ <b>({sector_name})</b> ÙÙŠ Ù…Ø¯ÙŠÙ†Ø© <b>({self.city})</b>.
                    </p>
                    <p class="text-muted mb-0">
                        Ø¨Ù†Ø§Ø¡Ù‹ Ø¹Ù„Ù‰ Ù‡Ø°Ø§ Ø§Ù„Ù…Ù„ÙØŒ Ø£Ø¹Ø¯Ø¯ØªÙ Ù„Ùƒ Ø®Ø·Ø© Ø§Ù„ØªØ£Ø³ÙŠØ³ Ø§Ù„Ø¢Ù„ÙŠØ© Ø£Ø¯Ù†Ø§Ù‡. ÙŠÙ…ÙƒÙ†Ùƒ ØªØ£ÙƒÙŠØ¯ Ø§Ù„Ø®ÙŠØ§Ø±Ø§Øª Ø¨Ø¶ØºØ·Ø© Ø²Ø± Ù„Ù†Ù‚ÙˆÙ… Ø¨ØªØ´ØºÙŠÙ„ Ø§Ù„Ù†Ø¸Ø§Ù… ÙÙˆØ±Ø§Ù‹! Â»
                    </p>
                </div>
            </div>
        """
        self.ai_conversation_html = ai_dialogue
        self.state = "extracted"

        return self._reopen()

    def action_apply_and_provision(self):
        """Execute one-click automated ERP setup based on extracted document data."""
        self.ensure_one()

        company = self.env.company
        vals = {}
        if self.company_name:
            vals["name"] = self.company_name
        if self.vat_number:
            vals["vat"] = self.vat_number
        if self.city:
            vals["city"] = self.city
        if self.street:
            vals["street"] = self.street
        if self.building_no:
            vals["street2"] = f"Building {self.building_no}"
        if self.postal_code:
            vals["zip"] = self.postal_code

        company.write(vals)

        # 1. Set System Parameters for ZATCA & Commercial Registration
        Param = self.env["ir.config_parameter"].sudo()
        if self.cr_number:
            Param.set_param("nexus.cr_number", self.cr_number)
        if self.gosi_number:
            Param.set_param("nexus.gosi_number", self.gosi_number)
        if self.vat_number:
            Param.set_param("nexus.vat_number", self.vat_number)
        Param.set_param("nexus.industry_sector", self.industry_sector)

        # 2. Auto-Provision Setup Journey
        journey = self.env["nexus.setup.journey"].search([("company_id", "=", company.id)], limit=1)
        if journey:
            journey.write({
                "industry_domain": self.industry_sector,
                "company_name": self.company_name,
            })
            try:
                journey.action_start()
                journey.action_complete_identity()
            except Exception as e:
                _logger.warning("Error completing setup journey stage: %s", e)

        # 3. Create Default POS if requested
        if self.opt_pos_kds:
            PosConfig = self.env.get("pos.config")
            if PosConfig:
                existing_pos = PosConfig.search([("company_id", "=", company.id)], limit=1)
                if not existing_pos:
                    try:
                        PosConfig.create({
                            "name": f"Main POS - {self.company_name}",
                            "company_id": company.id,
                        })
                    except Exception as e:
                        _logger.info("Could not auto-create POS config: %s", e)

        # 4. Create Employee Departments if requested
        if self.opt_payroll_wps:
            Department = self.env.get("hr.department")
            if Department:
                dept_names = ["Ø§Ù„Ø¥Ø¯Ø§Ø±Ø© Ø§Ù„Ø¹Ø§Ù…Ø©", "Ø§Ù„Ù…Ø¨ÙŠØ¹Ø§Øª ÙˆØ§Ù„ØªØ³ÙˆÙŠÙ‚", "Ø§Ù„Ù…Ø­Ø§Ø³Ø¨Ø© ÙˆØ§Ù„Ù…Ø§Ù„ÙŠØ©", "Ø§Ù„Ø¹Ù…Ù„ÙŠØ§Øª ÙˆØ§Ù„ØªØ´ØºÙŠÙ„"]
                for d_name in dept_names:
                    if not Department.search([("name", "=", d_name), ("company_id", "=", company.id)], limit=1):
                        try:
                            Department.create({"name": d_name, "company_id": company.id})
                        except Exception:
                            pass

        self.state = "completed"

        msg = f"""
        âœ… ØªÙ… ØªØ£Ø³ÙŠØ³ ÙˆØªÙ‡ÙŠØ¦Ø© Ø§Ù„Ù…Ù†Ø´Ø£Ø© Ø¨Ù†Ø¬Ø§Ø­ ØªØ§Ù…!
        - Ø§Ù„Ù…Ù†Ø´Ø£Ø©: {self.company_name}
        - Ø§Ù„Ø³Ø¬Ù„ Ø§Ù„ØªØ¬Ø§Ø±ÙŠ: {self.cr_number or 'ØºÙŠØ± Ù…Ø­Ø¯Ø¯'}
        - Ø§Ù„Ø±Ù‚Ù… Ø§Ù„Ø¶Ø±ÙŠØ¨ÙŠ: {self.vat_number or 'ØºÙŠØ± Ù…Ø­Ø¯Ø¯'}
        - Ø§Ù„Ù†Ø´Ø§Ø·: {dict(self._fields['industry_sector'].selection).get(self.industry_sector)}
        - Ø§Ù„Ù…Ø¯ÙŠÙ†Ø©: {self.city}
        """

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ðŸŽ‰ ØªÙ… Ø§Ù„ØªØ£Ø³ÙŠØ³ Ø§Ù„Ø°ÙƒÙŠ Ø¨Ù†Ø¬Ø§Ø­!"),
                "message": msg,
                "type": "success",
                "sticky": True,
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "nexus.setup.journey",
                    "view_mode": "kanban,form",
                    "target": "main",
                },
            },
        }

    def action_back_to_upload(self):
        self.ensure_one()
        self.state = "upload"
        return self._reopen()

    def action_clear_inputs(self):
        """Clear all inputs in Document Hunter wizard."""
        self.ensure_one()
        self.upload_document_file = False
        self.upload_document_filename = False
        self.cr_file = False
        self.cr_filename = False
        self.vat_file = False
        self.vat_filename = False
        self.gosi_file = False
        self.gosi_filename = False
        self.address_file = False
        self.address_filename = False
        self.any_document_file = False
        self.any_document_filename = False
        self.ai_analysis_html = False
        self.state = "upload"
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }
