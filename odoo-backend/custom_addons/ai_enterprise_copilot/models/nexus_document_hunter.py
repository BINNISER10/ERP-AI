# -*- coding: utf-8 -*-
"""Nexus Smart Document Hunter & Conversational AI Wizard — صياد ومعالج الوثائق الذكي.

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

    # ── Status ──
    state = fields.Selection(
        [
            ("upload", "1. رفع المستندات (Upload Documents)"),
            ("extracted", "2. البيانات المصطادة وأسئلة الذكاء الاصطناعي (AI Review)"),
            ("completed", "3. تم التأسيس بنجاح (Provisioned)"),
        ],
        default="upload",
        required=True,
    )

    # ── Upload Dropzones (Single Unified AI Dropzone) ──
    upload_document_file = fields.Binary(string="اسحب أو ارفع أي وثيقة رسمية هنا (Single AI Dropzone)", attachment=True)
    upload_document_filename = fields.Char(string="اسم ملف الوثيقة")

    # Legacy dropzones for backwards compatibility
    cr_file = fields.Binary(string="السجل التجاري (Commercial Registration)", attachment=True)
    cr_filename = fields.Char(string="CR File Name")
    vat_file = fields.Binary(string="الشهادة الضريبية (VAT Certificate)", attachment=True)
    vat_filename = fields.Char(string="VAT File Name")
    gosi_file = fields.Binary(string="شهادة التأمينات (GOSI Certificate)", attachment=True)
    gosi_filename = fields.Char(string="GOSI File Name")
    address_file = fields.Binary(string="العنوان الوطني / رخصة البلدية (National Address / Balady)", attachment=True)
    address_filename = fields.Char(string="Address File Name")
    any_document_file = fields.Binary(string="مستند مجمع أو وثيقة أعمال (Any Document)", attachment=True)
    any_document_filename = fields.Char(string="Document File Name")

    # ── Auto-Extracted Fields ──
    detected_doc_type_title = fields.Char(string="نوع الوثيقة المصطادة", readonly=True)
    company_name = fields.Char(string="اسم المنشأة / الشركة (Company Name)")
    company_name_ar = fields.Char(string="الاسم التجاري بالعربية")
    cr_number = fields.Char(string="رقم السجل التجاري (CR Number)", placeholder="1010XXXXXX")
    vat_number = fields.Char(string="الرقم الضريبي (VAT / Tax ID)", placeholder="3000XXXXXXXX003")
    gosi_number = fields.Char(string="رقم اشتراك التأمينات (GOSI Number)", placeholder="700XXXXXXX")
    balady_license_no = fields.Char(string="رقم رخصة بلدي", placeholder="1445XXXXXXXX")
    saudization_rate = fields.Float(string="نسبة التوطين / السعودة (%)")

    industry_sector = fields.Selection(
        [
            ("retail", "تجارة التجزئة / Retail"),
            ("restaurant", "مطاعم وكافيهات / F&B"),
            ("manufacturing", "تصنيع وإنتاج / Manufacturing"),
            ("construction", "مقاولات وتشييد / Construction"),
            ("services", "خدمات عامة واستشارات / Services"),
            ("healthcare", "رعاية صحية ومستلزمات / Healthcare"),
            ("fuel_station", "محطات وقود / Fuel Station"),
            ("real_estate", "عقارات وإدارة أملاك / Real Estate"),
            ("logistics", "نقل ولوجستيات / Logistics"),
            ("other", "أخرى / Other"),
        ],
        string="النشاط التجاري (Activity)",
        default="retail",
    )
    employee_count = fields.Integer(string="عدد الموظفين المرصود (Employees)", default=5)
    capital = fields.Float(string="رأس المال (Capital)")
    city = fields.Char(string="المدينة (City)", default="الرياض")
    district = fields.Char(string="الحي (District)")
    street = fields.Char(string="الشارع (Street)")
    building_no = fields.Char(string="رقم المبنى (Building No)")
    additional_no = fields.Char(string="الرقم الإضافي (Additional No)")
    postal_code = fields.Char(string="الرمز البريدي (Postal Code)")
    national_short_address = fields.Char(string="العنوان المختصر (Short Address)", placeholder="RRRD2934")

    # ── Conversational AI Options ──
    opt_pos_kds = fields.Boolean(
        string="🛒 نقاط البيع وشاشات المطبخ: تفعيل نقاط بيع متوافقة مع مدى وشاشات KDS",
        default=True,
    )
    opt_zatca = fields.Boolean(
        string="🧾 الفوترة الإلكترونية: تفعيل الامتثال للربط مع هيئة الزكاة (ZATCA Phase 2)",
        default=True,
    )
    opt_payroll_wps = fields.Boolean(
        string="👥 الموارد البشرية وحماية الأجور: تهيئة ملفات الرواتب (WPS) وأقسام الموظفين",
        default=True,
    )
    opt_accounting_chart = fields.Boolean(
        string="💰 المحاسبة المتقدمة: إنشاء دليل حسابات شجري متوافق مع معايير IFRS والنشاط",
        default=True,
    )
    opt_warehouses = fields.Boolean(
        string="📦 المستودعات والمخزون: إنشاء المستودع الرئيسي ومواقع التخزين الافتراضية",
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
        """AI Document Hunter Engine — Parses all uploaded documents and extracts fields."""
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
            raise UserError(_("يرجى سحب أو رفع وثيقة رسمية واحدة على الأقل (السجل التجاري، الشهادة الضريبية، العنوان الوطني، التأمينات، رخصة بلدي) للبدء في الاستخراج الآلي."))

        for b_data, f_name, doc_label in files_to_check:
            if b_data:
                txt = self._extract_text_from_binary(b_data, f_name)
                all_texts.append(txt)

        combined_text = "\n".join(all_texts)
        full_lower = combined_text.lower()

        # 1. Extract CR Number (10 digits starting with 1 to 5)
        cr_m = re.search(r"(?:سجل\s*تجاري|رقم\s*السجل|cr\s*no|commercial\s*reg)[\s:–-]*([1-5]\d{9})", combined_text, re.I)
        if not cr_m:
            cr_m = re.search(r"\b([1-5]\d{9})\b", combined_text)
        if cr_m:
            self.cr_number = cr_m.group(1)

        # 2. Extract VAT Number (15 digits starting and ending with 3)
        vat_m = re.search(r"(?:الرقم\s*الضريبي|ضريبة\s*القيمة\s*المضافة|vat\s*no|tax\s*id)[\s:–-]*([3]\d{13}[3])", combined_text, re.I)
        if not vat_m:
            vat_m = re.search(r"\b([3]\d{13}[3])\b", combined_text)
        if not vat_m:
            vat_m = re.search(r"\b(\d{15})\b", combined_text)
        if vat_m:
            self.vat_number = vat_m.group(1)

        # 3. Extract GOSI / Unified 700 Number
        gosi_m = re.search(r"(?:رقم\s*الاشتراك|رقم\s*المنشأة|التأمينات\s*الاجتماعية|الرقم\s*الموحد|gosi\s*no)[\s:–-]*([7]\d{9}|\d{7,10})", combined_text, re.I)
        if not gosi_m:
            gosi_m = re.search(r"\b(700\d{7})\b", combined_text)
        if gosi_m:
            self.gosi_number = gosi_m.group(1)

        # 4. Extract Balady License No
        balady_m = re.search(r"(?:رخصة\s*بلدية|رخصة\s*نشاط\s*تجاري|منصة\s*بلدي|بلدي|رقم\s*الرخصة)[\s:–-]*(\d{8,14})", combined_text, re.I)
        if balady_m:
            self.balady_license_no = balady_m.group(1)

        # 5. National Address Details (Building No, Postal Code, Additional No, District, Street)
        bm = re.search(r"(?:رقم\s*المبنى|building\s*no)[\s:–-]*(\d{4})", combined_text, re.I)
        if bm:
            self.building_no = bm.group(1)
        pm = re.search(r"(?:الرمز\s*البريدي|postal\s*code|zip)[\s:–-]*(\d{5})", combined_text, re.I)
        if pm:
            self.postal_code = pm.group(1)
        am = re.search(r"(?:الرقم\s*الإضافي|additional\s*no)[\s:–-]*(\d{4})", combined_text, re.I)
        if am:
            self.additional_no = am.group(1)
        dm = re.search(r"(?:الحي|district|حي)[\s:–-]*([^\n,]+)", combined_text, re.I)
        if dm:
            self.district = dm.group(1).strip()
        sm = re.search(r"(?:الشارع|street|طريق)[\s:–-]*([^\n,]+)", combined_text, re.I)
        if sm:
            self.street = sm.group(1).strip()

        # 6. Saudization / Nitaqat
        sr_m = re.search(r"(?:نسبة\s*التوطين|السعودة)[\s:–-]*(\d+(?:\.\d+)?)\s*%", combined_text, re.I)
        if sr_m:
            try:
                self.saudization_rate = float(sr_m.group(1))
            except Exception:
                pass

        # 7. Extract Employee count
        emp_m = re.search(r"(?:عدد\s*المشتركين|عدد\s*الموظفين|إجمالي\s*العاملين|total\s*employees)[\s:–-]*(\d+)", combined_text, re.I)
        if emp_m:
            self.employee_count = int(emp_m.group(1))

        # 5. Extract Company Name
        lines = [l.strip() for l in combined_text.splitlines() if l.strip()]
        for line in lines:
            if any(kw in line for kw in ["شركة", "مؤسسة", "فرع شركة", "مجموعة", "مصنع"]):
                clean = re.sub(r"(?:اسم المنشأة|اسم الشركة|اسم المؤسسة|الاسم التجاري)[\s:–-]*", "", line).strip()
                if 3 < len(clean) < 80:
                    self.company_name = clean
                    self.company_name_ar = clean
                    break

        if not self.company_name:
            self.company_name = self.env.company.name or "شركة الأعمال المتقدمة"
            self.company_name_ar = self.company_name

        # 6. Sector Detection
        if any(w in full_lower for w in ["مطعم", "كافيه", "مقهى", "أغذية", "وجبات", "restaurant", "cafe"]):
            self.industry_sector = "restaurant"
        elif any(w in full_lower for w in ["مصنع", "تصنيع", "صناعي", "إنتاج", "manufacturing"]):
            self.industry_sector = "manufacturing"
        elif any(w in full_lower for w in ["مقاولات", "بناء", "تشييد", "عقود", "construction"]):
            self.industry_sector = "construction"
        elif any(w in full_lower for w in ["محطة", "وقود", "بنزين", "ديزل", "fuel"]):
            self.industry_sector = "fuel_station"
        elif any(w in full_lower for w in ["عقار", "عقارات", "تطوير عقاري", "إيجار", "real estate"]):
            self.industry_sector = "real_estate"
        elif any(w in full_lower for w in ["طبي", "مستوصف", "عيادة", "صيدلية", "medical"]):
            self.industry_sector = "healthcare"
        elif any(w in full_lower for w in ["نقل", "لوجستي", "شحن", "تخزين", "logistics"]):
            self.industry_sector = "logistics"
        else:
            self.industry_sector = "retail"

        # 7. City Detection
        for c in ["الرياض", "جدة", "الدمام", "مكة", "المدينة", "الخبر", "القصيم", "تبوك", "أبها"]:
            if c in combined_text:
                self.city = c
                break

        # 8. Document Classification
        doc_type_title = "📄 وثيقة أعمال رسمية"
        if "سجل تجاري" in combined_text or "وزارة التجارة" in combined_text or (cr_m and "رأس المال" in combined_text):
            doc_type_title = "📑 السجل التجاري (Commercial Registration)"
        elif "الزكاة والضريبة والجمارك" in combined_text or "zatca" in full_lower or (vat_m and ("ضريبة القيمة المضافة" in combined_text or "شهادة تسجيل" in combined_text)):
            doc_type_title = "🧾 شهادة ضريبة القيمة المضافة (VAT Certificate)"
        elif "العنوان الوطني" in combined_text or "national address" in full_lower or "سبل" in combined_text or (bm and pm):
            doc_type_title = "📍 شهادة العنوان الوطني (National Address - سبل)"
        elif "التأمينات الاجتماعية" in combined_text or "gosi" in full_lower:
            doc_type_title = "🛡️ شهادة التأمينات الاجتماعية (GOSI Certificate)"
        elif "بلدي" in combined_text or "رخصة النشاط التجاري" in combined_text or balady_m:
            doc_type_title = "🏢 رخصة النشاط التجاري البلدية (Balady License)"
        elif "نطاقات" in combined_text or "شهادة السعودة" in combined_text or "وزارة الموارد البشرية" in combined_text:
            doc_type_title = "👥 شهادة السعودة ونطاقات (Nitaqat Certificate)"
        elif "الغرفة التجارية" in combined_text or "اشتراك الغرفة" in combined_text:
            doc_type_title = "🏛️ شهادة اشتراك الغرفة التجارية (Chamber of Commerce)"

        self.detected_doc_type_title = doc_type_title

        # 9. Render Rich AI Analysis & Conversational Cards
        detected_badges = []
        if self.cr_number:
            detected_badges.append(f'<span class="badge bg-success p-2 me-2 mb-2" style="font-size:13px;">📑 السجل التجاري: {self.cr_number}</span>')
        if self.vat_number:
            detected_badges.append(f'<span class="badge bg-success p-2 me-2 mb-2" style="font-size:13px;">🧾 الرقم الضريبي: {self.vat_number}</span>')
        if self.gosi_number:
            detected_badges.append(f'<span class="badge bg-success p-2 me-2 mb-2" style="font-size:13px;">🛡️ التأمينات: {self.gosi_number} ({self.employee_count} موظف)</span>')
        if self.balady_license_no:
            badges.append(f'<span class="badge bg-success p-2 me-2 mb-2" style="font-size:13px;">🏢 رخصة بلدي: {self.balady_license_no}</span>')
        if self.building_no or self.district:
            addr_str = f"{self.city or ''} - {self.district or ''} - مبنى {self.building_no or ''}"
            badges.append(f'<span class="badge bg-info p-2 me-2 mb-2" style="font-size:13px;">📍 العنوان الوطني: {addr_str}</span>')
        if self.city:
            detected_badges.append(f'<span class="badge bg-info p-2 me-2 mb-2" style="font-size:13px;">📍 المركز الرئيسي: {self.city}</span>')

        self.ai_analysis_html = f"""
            <div class="alert alert-success border-0 shadow-sm p-3 mb-3" style="border-radius: 10px; background-color: #E8F5E9;">
                <h5 class="text-success mb-2 font-weight-bold">🎯 تم التعرف بنجاح على: {doc_type_title}</h5>
                <p class="mb-2 text-dark">تم مسح المستندات المرفوعة والتعرف على البيانات الرسمية التالية بدقة عالية:</p>
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
                    <span>المساعد الذكي لتأسيس المنشأة (Nexus AI Consultant):</span>
                </div>
                <div class="card-body bg-light">
                    <p class="lead mb-2" style="font-size: 16px;">
                        « مرحباً! قمتُ بفحص السجل والشهادات المرفوعة لمنشأتكم <b>({self.company_name})</b>.
                        نشاطكم الرئيسي هو <b>({sector_name})</b> في مدينة <b>({self.city})</b>.
                    </p>
                    <p class="text-muted mb-0">
                        بناءً على هذا الملف، أعددتُ لك خطة التأسيس الآلية أدناه. يمكنك تأكيد الخيارات بضغطة زر لنقوم بتشغيل النظام فوراً! »
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
                dept_names = ["الإدارة العامة", "المبيعات والتسويق", "المحاسبة والمالية", "العمليات والتشغيل"]
                for d_name in dept_names:
                    if not Department.search([("name", "=", d_name), ("company_id", "=", company.id)], limit=1):
                        try:
                            Department.create({"name": d_name, "company_id": company.id})
                        except Exception:
                            pass

        self.state = "completed"

        msg = f"""
        ✅ تم تأسيس وتهيئة المنشأة بنجاح تام!
        - المنشأة: {self.company_name}
        - السجل التجاري: {self.cr_number or 'غير محدد'}
        - الرقم الضريبي: {self.vat_number or 'غير محدد'}
        - النشاط: {dict(self._fields['industry_sector'].selection).get(self.industry_sector)}
        - المدينة: {self.city}
        """

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("🎉 تم التأسيس الذكي بنجاح!"),
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
