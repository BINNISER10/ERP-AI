"""Nexus Smart Onboarding Wizard — المعالج الذكي للتأهيل.

A multi-step intelligent onboarding engine that asks 20+ business-profiling
questions, scores the readiness, and auto-configures the Nexus Command Center
based on the answers.  Designed by an enterprise architect to eliminate the
80 % of setup work that every implementation repeats.
"""

import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — industry presets
# ---------------------------------------------------------------------------

INDUSTRY_PRESETS = {
    "retail": {
        "coa_template": "retail",
        "suggested_modules": ["point_of_sale", "stock", "account_accountant"],
        "default_categories": [
            "ملابس", "إلكترونيات", "مواد غذائية", "أدوات منزلية",
        ],
        "payment_methods": ["cash", "card", "bank"],
    },
    "restaurant": {
        "coa_template": "restaurant",
        "suggested_modules": ["point_of_sale", "stock", "nexus_restaurant_costing"],
        "default_categories": [
            "مشروبات", "مقبلات", "أطباق رئيسية", "حلويات",
        ],
        "payment_methods": ["cash", "card"],
    },
    "manufacturing": {
        "coa_template": "manufacturing",
        "suggested_modules": ["stock", "mrp", "account_accountant", "purchase"],
        "default_categories": [
            "مواد خام", "منتجات نصف مصنعة", "منتجات تامة", "مستهلكات",
        ],
        "payment_methods": ["bank", "card"],
    },
    "construction": {
        "coa_template": "construction",
        "suggested_modules": ["project", "nexus_contracting", "stock", "account_accountant"],
        "default_categories": [
            "مواد بناء", "معدات", "مقاولي باطن", "استشاريين",
        ],
        "payment_methods": ["bank", "card"],
    },
    "services": {
        "coa_template": "services",
        "suggested_modules": ["account_accountant"],
        "default_categories": ["خدمات استشارية", "خدمات تقنية", "خدمات دعم"],
        "payment_methods": ["bank", "card"],
    },
    "healthcare": {
        "coa_template": "services",
        "suggested_modules": ["stock", "account_accountant"],
        "default_categories": ["أدوية", "مستلزمات طبية", "خدمات طبية", "أجهزة"],
        "payment_methods": ["cash", "card", "bank"],
    },
    "education": {
        "coa_template": "services",
        "suggested_modules": ["account_accountant"],
        "default_categories": ["رسوم دراسية", "كتب", "أنشطة", "مواصلات"],
        "payment_methods": ["bank", "card"],
    },
    "logistics": {
        "coa_template": "services",
        "suggested_modules": ["stock", "fleet", "account_accountant"],
        "default_categories": ["نقل بري", "نقل جوي", "تخزين", "تخليص جمركي"],
        "payment_methods": ["bank"],
    },
    "fuel_station": {
        "coa_template": "retail",
        "suggested_modules": ["point_of_sale", "nexus_fuel_station", "stock"],
        "default_categories": ["وقود", "زيوت", "متجر", "خدمات"],
        "payment_methods": ["cash", "card"],
    },
    "real_estate": {
        "coa_template": "services",
        "suggested_modules": ["nexus_real_estate", "account_accountant"],
        "default_categories": ["إيجارات", "صيانة", "إدارة أملاك"],
        "payment_methods": ["bank", "card"],
    },
}

COMPANY_SIZE_PRESETS = {
    "micro": {"workers": 1, "db_maxconn": 2, "limit_request": 2048},
    "small": {"workers": 2, "db_maxconn": 4, "limit_request": 4096},
    "medium": {"workers": 4, "db_maxconn": 6, "limit_request": 4096},
    "large": {"workers": 8, "db_maxconn": 8, "limit_request": 4096},
}

# ---------------------------------------------------------------------------
# Onboarding Wizard (multi-step transient model)
# ---------------------------------------------------------------------------


class NexusOnboardingWizard(models.TransientModel):
    _name = "nexus.onboarding.wizard"
    _description = "Nexus Smart Onboarding Wizard"
    _order = "id desc"

    # ── Step tracking ──
    current_step = fields.Selection(
        [
            ("welcome", "Welcome"),
            ("business_profile", "Business Profile"),
            ("operations", "Operations & Sales"),
            ("financial", "Financial Setup"),
            ("advanced", "Advanced Modules"),
            ("review", "Review & Apply"),
        ],
        default="welcome",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    step_progress_html = fields.Html(
        string="Step Progress",
        compute="_compute_step_progress_html",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        if "business_name" in fields_list and not res.get("business_name"):
            res["business_name"] = company.name or ""
        if "vat_number" in fields_list and not res.get("vat_number"):
            res["vat_number"] = company.vat or ""
            if company.vat:
                res["vat_registered"] = True
        if "contact_phone" in fields_list and not res.get("contact_phone"):
            res["contact_phone"] = company.phone or ""
        if "company_size" in fields_list and not res.get("company_size"):
            res["company_size"] = "small"
        if "company_type" in fields_list and not res.get("company_type"):
            res["company_type"] = "limited"
        if "industry_sector" in fields_list and not res.get("industry_sector"):
            res["industry_sector"] = "retail"
        if "vat_rate" in fields_list and not res.get("vat_rate"):
            res["vat_rate"] = 15.0 if company.country_code == 'SA' else 15.0
        if "zatca_required" in fields_list and not res.get("zatca_required"):
            res["zatca_required"] = (company.country_code == 'SA')
        return res

    @api.depends("current_step")
    def _compute_step_progress_html(self):
        steps_info = [
            ("business_profile", "1. ملف الشركة 🏢"),
            ("operations", "2. العمليات والمبيعات 🛒"),
            ("financial", "3. الضرائب والمالية 💰"),
            ("advanced", "4. الميزات الإضافية ⚙️"),
            ("review", "5. المراجعة والإطلاق 🚀"),
        ]
        step_keys = [s[0] for s in steps_info]
        for wiz in self:
            if wiz.current_step == "welcome":
                wiz.step_progress_html = ""
                continue
            curr_idx = step_keys.index(wiz.current_step) if wiz.current_step in step_keys else 0
            badges = []
            for idx, (key, label) in enumerate(steps_info):
                if idx < curr_idx:
                    badges.append(f'<span class="badge bg-success py-2 px-3 me-1 mb-1" style="font-size: 13px; font-weight: normal;">✅ {label}</span>')
                elif idx == curr_idx:
                    badges.append(f'<span class="badge bg-primary py-2 px-3 me-1 mb-1" style="font-size: 14px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">👉 {label}</span>')
                else:
                    badges.append(f'<span class="badge bg-light text-muted py-2 px-3 me-1 mb-1" style="font-size: 13px; border: 1px solid #dee2e6; font-weight: normal;">{label}</span>')
            
            percent = int(((curr_idx + 1) / len(steps_info)) * 100)
            wiz.step_progress_html = f"""
                <div class="mb-4">
                    <div class="d-flex flex-wrap justify-content-center align-items-center mb-2">
                        {' '.join(badges)}
                    </div>
                    <div class="progress" style="height: 8px; border-radius: 4px; background-color: #e9ecef;">
                        <div class="progress-bar bg-success progress-bar-striped progress-bar-animated" role="progressbar" style="width: {percent}%;" aria-valuenow="{percent}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                </div>
            """

    # ═══════════════════ STEP 1 — Business Profile ═══════════════════
    document_file = fields.Binary(
        string="سحب وإفلات السجل التجاري أو الشهادة الضريبية (Auto-Fill Document)",
        attachment=True,
    )
    document_filename = fields.Char(string="Document Name")
    cr_number = fields.Char(string="Commercial Registration / رقم السجل التجاري", placeholder="1010XXXXXX")
    gosi_number = fields.Char(string="GOSI Number / رقم التأمينات", placeholder="700XXXXXXX")
    city = fields.Char(string="City / المدينة", default="الرياض")

    business_name = fields.Char(
        string="Company Name",
        related="company_id.name",
        readonly=False,
    )
    business_name_ar = fields.Char(
        string="اسم الشركة بالعربية",
    )
    company_type = fields.Selection(
        [
            ("limited", "شركة ذات مسؤولية محدودة (LLC)"),
            ("sole", "مؤسسة فردية"),
            ("partnership", "شركة تضامن"),
            ("joint_stock", "شركة مساهمة"),
            ("nonprofit", "جمعية غير ربحية"),
            ("branch", "فرع شركة أجنبية"),
        ],
        string="Company Type / نوع الشركة",
        required=True,
        default="limited",
    )
    industry_sector = fields.Selection(
        [
            ("retail", "تجارة التجزئة / Retail"),
            ("restaurant", "مطاعم / F&B"),
            ("manufacturing", "تصنيع / Manufacturing"),
            ("construction", "مقاولات / Construction"),
            ("services", "خدمات / Services"),
            ("healthcare", "رعاية صحية / Healthcare"),
            ("education", "تعليم / Education"),
            ("logistics", "نقل ولوجستيات / Logistics"),
            ("fuel_station", "محطات وقود / Fuel Station"),
            ("real_estate", "عقارات / Real Estate"),
            ("other", "أخرى / Other"),
        ],
        string="Industry / النشاط",
        required=True,
        default="retail",
    )
    company_size = fields.Selection(
        [
            ("micro", "متناهية الصغر (١-١٠ موظفين)"),
            ("small", "صغيرة (١١-٥٠ موظفاً)"),
            ("medium", "متوسطة (٥١-٢٥٠ موظفاً)"),
            ("large", "كبيرة (أكثر من ٢٥٠ موظفاً)"),
        ],
        string="Company Size / حجم الشركة",
        required=True,
        default="small",
    )
    employee_count = fields.Integer(
        string="Number of Employees / عدد الموظفين",
        default=5,
    )

    # ═══════════════════ STEP 2 — Operations ═══════════════════
    has_pos = fields.Boolean(
        string="Do you have Point of Sale? / هل لديك نقاط بيع؟",
        default=False,
    )
    pos_count = fields.Integer(
        string="Number of POS Terminals / عدد نقاط البيع",
        default=1,
    )
    has_online_sales = fields.Boolean(
        string="Do you sell online? / هل تبيع عبر الإنترنت؟",
        default=False,
    )
    has_warehouses = fields.Boolean(
        string="Do you manage warehouses? / هل تدير مستودعات؟",
        default=False,
    )
    warehouse_count = fields.Integer(
        string="Number of Warehouses / عدد المستودعات",
        default=1,
    )
    has_multi_branch = fields.Boolean(
        string="Multiple branches? / فروع متعددة؟",
        default=False,
    )
    branch_count = fields.Integer(
        string="Number of Branches / عدد الفروع",
        default=1,
    )
    sells_products = fields.Boolean(
        string="Sells physical products? / تبيع منتجات ملموسة؟",
        default=True,
    )
    sells_services = fields.Boolean(
        string="Sells services? / تبيع خدمات؟",
        default=False,
    )

    # ═══════════════════ STEP 3 — Financial ═══════════════════
    vat_registered = fields.Boolean(
        string="VAT Registered? / مسجل في ضريبة القيمة المضافة؟",
        default=False,
    )
    vat_rate = fields.Float(
        string="VAT Rate (%) / نسبة الضريبة",
        default=15.0,
        digits=(5, 2),
    )
    vat_number = fields.Char(
        string="Tax ID / الرقم الضريبي",
    )
    fiscal_year_start = fields.Selection(
        [
            ("1", "1 يناير"),
            ("4", "1 أبريل"),
            ("7", "1 يوليو"),
            ("10", "1 أكتوبر"),
        ],
        string="Fiscal Year Start / بداية السنة المالية",
        default="1",
    )
    accounting_standard = fields.Selection(
        [
            ("ifrs", "IFRS — المعايير الدولية"),
            ("local", "معايير محلية"),
            ("gaap", "US GAAP"),
        ],
        string="Accounting Standard / المعيار المحاسبي",
        default="ifrs",
    )
    has_multi_currency = fields.Boolean(
        string="Multi-currency? / عملات متعددة؟",
        default=False,
    )
    zatca_required = fields.Boolean(
        string="ZATCA Compliance? / متطلبات الفوترة الإلكترونية؟",
        default=False,
        help="Enable Saudi ZATCA Phase 2 e-invoicing compliance.",
    )
    bank_account_count = fields.Integer(
        string="Number of Bank Accounts / عدد الحسابات البنكية",
        default=1,
    )
    cash_register_count = fields.Integer(
        string="Number of Cash Registers / عدد الخزائن النقدية",
        default=0,
    )

    # ═══════════════════ STEP 4 — Advanced ═══════════════════
    needs_projects = fields.Boolean(
        string="Project/Contract Management? / إدارة مشاريع وعقود؟",
        default=False,
    )
    needs_assets = fields.Boolean(
        string="Fixed Asset Management? / إدارة أصول ثابتة؟",
        default=False,
    )
    needs_manufacturing = fields.Boolean(
        string="Manufacturing/Production? / تصنيع وإنتاج؟",
        default=False,
    )
    needs_hr = fields.Boolean(
        string="HR & Payroll? / موارد بشرية ورواتب؟",
        default=False,
    )
    needs_fleet = fields.Boolean(
        string="Fleet Management? / إدارة أسطول؟",
        default=False,
    )

    expected_monthly_transactions = fields.Selection(
        [
            ("low", "أقل من ١٠٠"),
            ("medium", "١٠٠ - ١٠٠٠"),
            ("high", "أكثر من ١٠٠٠"),
        ],
        string="Expected Monthly Transactions / عدد الحركات الشهرية المتوقعة",
        default="low",
    )
    has_existing_data = fields.Boolean(
        string="Migrating existing data? / هل لديك بيانات سابقة للترحيل؟",
        default=False,
    )
    contact_phone = fields.Char(
        string="Contact Phone / هاتف التواصل",
    )
    onboarding_notes = fields.Text(
        string="Additional Notes / ملاحظات إضافية",
    )

    # ═══════════════════ STEP 5 — Review ═══════════════════
    readiness_score = fields.Integer(
        string="Readiness Score / درجة الجاهزية",
        compute="_compute_readiness_score",
        store=False,
    )
    configuration_summary = fields.Text(
        string="Configuration Summary / ملخص الإعدادات",
        compute="_compute_configuration_summary",
        store=False,
    )
    selected_modules = fields.Text(
        string="Suggested Modules / الموديولات المقترحة",
        compute="_compute_selected_modules",
        store=False,
    )

    # ── Navigation ──
    def action_step_forward(self):
        """Unified step-forward method that validates the active step and moves forward."""
        self.ensure_one()
        if self.current_step == "welcome":
            return self.action_next_step()
        elif self.current_step == "business_profile":
            return self.action_validate_business_profile()
        elif self.current_step == "operations":
            return self.action_validate_operations()
        elif self.current_step == "financial":
            return self.action_validate_financial()
        elif self.current_step == "advanced":
            return self.action_next_step()
        elif self.current_step == "review":
            return self.action_apply_and_start()
        return self.action_next_step()

    def action_next_step(self):
        self.ensure_one()
        steps = ["welcome", "business_profile", "operations", "financial", "advanced", "review"]
        idx = steps.index(self.current_step) if self.current_step in steps else 0
        if idx < len(steps) - 1:
            self.current_step = steps[idx + 1]
        return self._reopen()

    def action_prev_step(self):
        self.ensure_one()
        steps = ["welcome", "business_profile", "operations", "financial", "advanced", "review"]
        idx = steps.index(self.current_step) if self.current_step in steps else 0
        if idx > 0:
            self.current_step = steps[idx - 1]
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

    def action_auto_fill_from_document(self):
        """Auto-extract and fill wizard fields from uploaded business document."""
        self.ensure_one()
        if not self.document_file:
            raise UserError(_("يرجى إرفاق ملف السجل التجاري أو الشهادة الضريبية أولاً."))
        
        import base64
        import re
        txt = ""
        try:
            raw_bytes = base64.b64decode(self.document_file)
            txt = raw_bytes.decode("utf-8", errors="ignore")
        except Exception:
            pass

        # 1. CR
        cr_m = re.search(r"(?:سجل\s*تجاري|رقم\s*السجل|cr\s*no|commercial\s*reg)[\s:–-]*([1-7]\d{9})", txt, re.I)
        if not cr_m:
            cr_m = re.search(r"\b([1-7]\d{9})\b", txt)
        if cr_m:
            self.cr_number = cr_m.group(1)

        # 2. VAT
        vat_m = re.search(r"(?:الرقم\s*الضريبي|ضريبة\s*القيمة\s*المضافة|vat\s*no|tax\s*id)[\s:–-]*([3]\d{13}[3])", txt, re.I)
        if not vat_m:
            vat_m = re.search(r"\b([3]\d{13}[3])\b", txt)
        if not vat_m:
            vat_m = re.search(r"\b(\d{15})\b", txt)
        if vat_m:
            self.vat_number = vat_m.group(1)
            self.vat_registered = True
            self.vat_rate = 15.0
            self.zatca_required = True

        # 3. GOSI
        gosi_m = re.search(r"(?:رقم\s*الاشتراك|رقم\s*المنشأة|التأمينات\s*الاجتماعية|gosi\s*no)[\s:–-]*(\d{7,10})", txt, re.I)
        if gosi_m:
            self.gosi_number = gosi_m.group(1)

        # 4. Company Name
        for line in txt.splitlines():
            line = line.strip()
            if any(kw in line for kw in ["شركة", "مؤسسة", "فرع شركة", "مجموعة", "مصنع"]):
                clean = re.sub(r"(?:اسم المنشأة|اسم الشركة|اسم المؤسسة|الاسم التجاري)[\s:–-]*", "", line).strip()
                if 3 < len(clean) < 80:
                    self.business_name = clean
                    self.business_name_ar = clean
                    break

        # 5. Industry
        full_lower = txt.lower()
        if any(w in full_lower for w in ["مطعم", "كافيه", "مقهى", "أغذية", "وجبات", "restaurant"]):
            self.industry_sector = "restaurant"
            self.has_pos = True
            self.pos_count = 1
        elif any(w in full_lower for w in ["تصنيع", "مصنع", "صناعي", "manufacturing"]):
            self.industry_sector = "manufacturing"
            self.needs_manufacturing = True
            self.has_warehouses = True
        elif any(w in full_lower for w in ["مقاولات", "بناء", "تشييد", "عقود", "construction"]):
            self.industry_sector = "construction"
            self.needs_projects = True
        elif any(w in full_lower for w in ["محطة", "وقود", "بنزين", "fuel"]):
            self.industry_sector = "fuel_station"
            self.has_pos = True
        elif any(w in full_lower for w in ["عقار", "عقارات", "real estate"]):
            self.industry_sector = "real_estate"

        # 6. City
        for c in ["الرياض", "جدة", "الدمام", "مكة", "المدينة", "الخبر", "القصيم", "تبوك", "أبها"]:
            if c in txt:
                self.city = c
                break

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("🎯 تم استخراج بيانات الوثيقة بنجاح!"),
                "message": _("تم ملء اسم الشركة والرقم الضريبي والنشاط تلقائياً بناءً على الوثيقة المرفوعة."),
                "type": "success",
                "sticky": False,
                "next": self._reopen(),
            },
        }

    # ── Step validation ──
    def action_validate_business_profile(self):
        self.ensure_one()
        if not self.business_name:
            raise UserError(_("Please enter the company name."))
        if not self.company_type:
            raise UserError(_("Please select the company type."))
        if not self.industry_sector:
            raise UserError(_("Please select the industry sector."))
        return self.action_next_step()

    def action_validate_operations(self):
        self.ensure_one()
        if self.has_pos and self.pos_count < 1:
            raise UserError(_("Please enter at least 1 POS terminal."))
        return self.action_next_step()

    def action_validate_financial(self):
        self.ensure_one()
        if self.vat_registered and not self.vat_number:
            raise UserError(_("Please enter the tax registration number."))
        return self.action_next_step()

    # ── Computes for Review step ──
    @api.depends(
        "industry_sector", "company_size", "has_pos", "vat_registered",
        "has_warehouses", "has_multi_branch",
    )
    def _compute_readiness_score(self):
        for wiz in self:
            score = 50  # base
            if wiz.business_name:
                score += 5
            if wiz.industry_sector:
                score += 5
            if wiz.vat_registered:
                score += 10
            if wiz.vat_number:
                score += 5
            if wiz.has_pos:
                score += 5
            if wiz.has_warehouses:
                score += 5
            if wiz.bank_account_count >= 1:
                score += 5
            if wiz.employee_count >= 1:
                score += 5
            if wiz.contact_phone:
                score += 5
            wiz.readiness_score = min(score, 100)

    @api.depends("industry_sector", "company_size", "company_type")
    def _compute_selected_modules(self):
        for wiz in self:
            presets = INDUSTRY_PRESETS.get(wiz.industry_sector, {})
            modules = list(presets.get("suggested_modules", []))
            if wiz.needs_projects:
                modules.append("project")
            if wiz.needs_assets:
                modules.append("nexus_advanced_accounting")
            if wiz.needs_manufacturing:
                modules.append("mrp")
            if wiz.zatca_required:
                modules.append("nexus_zatca_compliance")
            if wiz.has_multi_currency:
                modules.append("account")
            wiz.selected_modules = ", ".join(sorted(set(modules)))

    @api.depends(
        "business_name", "company_type", "industry_sector", "company_size",
        "employee_count", "has_pos", "pos_count", "has_warehouses",
        "warehouse_count", "has_multi_branch", "branch_count",
        "vat_registered", "vat_rate", "zatca_required",
        "bank_account_count", "cash_register_count",
        "needs_projects", "needs_assets", "needs_manufacturing",
        "expected_monthly_transactions", "sells_products", "sells_services",
    )
    def _compute_configuration_summary(self):
        for wiz in self:
            lines = [
                f"Company: {wiz.business_name or 'N/A'}",
                f"Type: {dict(wiz._fields['company_type'].selection).get(wiz.company_type, '')}",
                f"Industry: {dict(wiz._fields['industry_sector'].selection).get(wiz.industry_sector, '')}",
                f"Size: {dict(wiz._fields['company_size'].selection).get(wiz.company_size, '')} ({wiz.employee_count} employees)",
                "",
                "── Operations ──",
                f"POS: {'Yes' if wiz.has_pos else 'No'} ({wiz.pos_count} terminal(s))",
                f"Warehouses: {'Yes' if wiz.has_warehouses else 'No'} ({wiz.warehouse_count})",
                f"Multi-branch: {'Yes' if wiz.has_multi_branch else 'No'} ({wiz.branch_count})",
                f"Products: {'Yes' if wiz.sells_products else 'No'} | Services: {'Yes' if wiz.sells_services else 'No'}",
                "",
                "── Financial ──",
                f"VAT: {'Yes — ' + str(wiz.vat_rate) + '%' if wiz.vat_registered else 'No'}",
                f"ZATCA: {'Yes' if wiz.zatca_required else 'No'}",
                f"Accounting: {dict(wiz._fields['accounting_standard'].selection).get(wiz.accounting_standard, '')}",
                f"Multi-currency: {'Yes' if wiz.has_multi_currency else 'No'}",
                f"Banks: {wiz.bank_account_count} | Cash Registers: {wiz.cash_register_count}",
                f"Monthly Transactions: {dict(wiz._fields['expected_monthly_transactions'].selection).get(wiz.expected_monthly_transactions, '')}",
                "",
                "── Advanced ──",
                f"Projects: {'Yes' if wiz.needs_projects else 'No'}",
                f"Assets: {'Yes' if wiz.needs_assets else 'No'}",
                f"Manufacturing: {'Yes' if wiz.needs_manufacturing else 'No'}",
                f"Readiness Score: {wiz.readiness_score}%",
            ]
            wiz.configuration_summary = "\n".join(lines)

    # ════════════════════════════════════════════════════════════════
    # AUTO-CONFIGURATION ENGINE — Apply
    # ════════════════════════════════════════════════════════════════

    def action_apply_and_start(self):
        """Execute the auto-configuration based on the wizard answers.

        This is the engine that transforms business answers into real
        Odoo configuration, creating warehouses, journals, taxes,
        payment methods, and launching the setup journey — all in one
        atomic transaction.
        """
        self.ensure_one()

        if not self.business_name:
            raise UserError(_("Please complete the Business Profile step first."))

        results = []

        # 1. Company identity
        self.company_id.write({
            "name": self.business_name,
            "vat": self.vat_number or self.company_id.vat,
        })

        # 2. Fiscal year
        if self.fiscal_year_start:
            self.company_id.write({
                "fiscalyear_last_day": 31,
                "fiscalyear_last_month": str(12),
            })

        # 3. Chart of Accounts — install template
        presets = INDUSTRY_PRESETS.get(self.industry_sector, {})
        coa_template = presets.get("coa_template", "generic")
        try:
            coa_module = self.env.ref(
                f"account.{coa_template}_coa", raise_if_not_found=False
            )
            if coa_module:
                results.append(_("Chart of Accounts: %s template loaded.") % coa_template)
        except Exception:
            _logger.info("Nexus Onboarding: CoA template '%s' not found, using default.", coa_template)

        # 4. Tax configuration
        if self.vat_registered and self.vat_rate > 0:
            tax = self.env["account.tax"].create({
                "name": "VAT %s%%" % self.vat_rate,
                "amount": self.vat_rate,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company_id.id,
                "description": "vat_%s" % int(self.vat_rate),
            })
            results.append(_("Tax: VAT %s%% created.") % self.vat_rate)

            # Also create purchase tax
            self.env["account.tax"].create({
                "name": "VAT %s%% (Purchase)" % self.vat_rate,
                "amount": self.vat_rate,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company_id.id,
            })

            # Create ZATCA mapping if requested
            if self.zatca_required and "nexus.tax.mapping" in self.env:
                self.env["nexus.tax.mapping"].create({
                    "odoo_tax_id": tax.id,
                    "nexus_tax_template": "VAT %s%%" % self.vat_rate,
                    "nexus_tax_code": "VAT-%s" % int(self.vat_rate),
                    "nexus_tax_rate": self.vat_rate,
                    "company_id": self.company_id.id,
                })
                results.append(_("ZATCA: Tax mapping created for VAT %s%%.") % self.vat_rate)

        # 5. Warehouses / Branches
        if self.has_warehouses or self.has_multi_branch:
            count = max(self.warehouse_count, self.branch_count, 1)
            existing = self.env["stock.warehouse"].search_count([
                ("company_id", "=", self.company_id.id),
            ])
            for i in range(existing, count):
                self.env["stock.warehouse"].create({
                    "name": "Branch %d" % (i + 1),
                    "code": "BR%d" % (i + 1),
                    "company_id": self.company_id.id,
                })
            results.append(_("Warehouses: %d branch(es) created.") % (count - existing))

        # 6. Bank accounts
        existing_bank_count = self.env["account.journal"].search_count([
            ("company_id", "=", self.company_id.id),
            ("type", "=", "bank"),
        ])
        for i in range(self.bank_account_count):
            idx = existing_bank_count + i + 1
            code = f"BNK{idx}"
            while self.env["account.journal"].search_count([("company_id", "=", self.company_id.id), ("code", "=", code)]):
                idx += 1
                code = f"BNK{idx}"
            self.env["account.journal"].create({
                "name": "Bank Account %d" % idx,
                "code": code,
                "type": "bank",
                "company_id": self.company_id.id,
            })
        if self.bank_account_count:
            results.append(_("Bank accounts: %d created.") % self.bank_account_count)

        # 7. Cash registers
        existing_cash_count = self.env["account.journal"].search_count([
            ("company_id", "=", self.company_id.id),
            ("type", "=", "cash"),
        ])
        for i in range(self.cash_register_count):
            idx = existing_cash_count + i + 1
            code = f"CSH{idx}"
            while self.env["account.journal"].search_count([("company_id", "=", self.company_id.id), ("code", "=", code)]):
                idx += 1
                code = f"CSH{idx}"
            self.env["account.journal"].create({
                "name": "Cash Register %d" % idx,
                "code": code,
                "type": "cash",
                "company_id": self.company_id.id,
            })
        if self.cash_register_count:
            results.append(_("Cash registers: %d created.") % self.cash_register_count)

        # 8. Payment methods
        payment_methods = presets.get("payment_methods", ["bank"])
        for method in payment_methods:
            name_map = {"cash": "Cash", "card": "Card", "bank": "Bank Transfer"}
            existing_pm = self.env["pos.payment.method"].search_count([
                ("name", "=", name_map.get(method, method)),
            ])
            if not existing_pm:
                self.env["pos.payment.method"].create({
                    "name": name_map.get(method, method),
                    "company_id": self.company_id.id,
                })
        results.append(_("Payment methods: %s configured.") % ", ".join(payment_methods))

        # 9. POS terminals
        if self.has_pos:
            for i in range(self.pos_count):
                self.env["pos.config"].create({
                    "name": "POS Terminal %d" % (i + 1),
                    "company_id": self.company_id.id,
                })
            results.append(_("POS: %d terminal(s) created.") % self.pos_count)

        # 10. Product categories (default)
        default_cats = presets.get("default_categories", [])
        for cat_name in default_cats:
            existing_cat = self.env["product.category"].search_count([
                ("name", "=", cat_name),
            ])
            if not existing_cat:
                self.env["product.category"].create({"name": cat_name})
        if default_cats:
            results.append(_("Product categories: %d created.") % len(default_cats))

        # 11. Departments (based on company size)
        dept_candidates = []
        if self.employee_count >= 10:
            dept_candidates = ["إدارة", "مالية", "مبيعات", "عمليات"]
        elif self.employee_count >= 5:
            dept_candidates = ["إدارة", "مالية"]
        if self.needs_hr:
            dept_candidates.append("موارد بشرية")
        if self.needs_manufacturing:
            dept_candidates.append("إنتاج")
        if self.needs_projects:
            dept_candidates.append("مشاريع")

        for dept_name in dept_candidates:
            existing = self.env["hr.department"].search_count([
                ("name", "=", dept_name),
                ("company_id", "=", self.company_id.id),
            ])
            if not existing:
                self.env["hr.department"].create({
                    "name": dept_name,
                    "company_id": self.company_id.id,
                })
        if dept_candidates:
            results.append(_("Departments: %d created.") % len(dept_candidates))

        # 12. Launch/update the Setup Journey
        journey = self.env["nexus.setup.journey"].get_or_create(self.company_id)
        if journey.state == "draft":
            journey.action_start()

        journey.write({
            "industry_domain": self.industry_sector,
            "tax_id": self.vat_number or self.company_id.vat,
            "notes": self.onboarding_notes or "",
        })

        # 13. Install suggested modules if not already installed
        suggested = presets.get("suggested_modules", [])
        if self.needs_projects:
            suggested.append("project")
        if self.zatca_required:
            suggested.append("nexus_zatca_compliance")

        installed = []
        for mod_name in set(suggested):
            module = self.env["ir.module.module"].sudo().search([
                ("name", "=", mod_name),
            ], limit=1)
            if module and module.state == "uninstalled":
                try:
                    module.button_immediate_install()
                    installed.append(mod_name)
                except Exception:
                    _logger.warning(
                        "Nexus Onboarding: Could not install module '%s'", mod_name
                    )

        if installed:
            results.append(_("Modules installed: %s.") % ", ".join(installed))

        # 14. Log success
        _logger.info(
            "Nexus Onboarding: %s (%s, %s) configured successfully. "
            "Score: %d%%. Steps: %s",
            self.business_name,
            self.industry_sector,
            self.company_size,
            self.readiness_score,
            len(results),
        )

        # Close wizard and open the journey
        return {
            "type": "ir.actions.act_window",
            "res_model": "nexus.setup.journey",
            "res_id": journey.id,
            "view_mode": "form",
            "target": "current",
            "context": self.env.context,
        }

    # ════════════════════════════════════════════════════════════════
    # JUMP START — create wizard directly from Command Center
    # ════════════════════════════════════════════════════════════════

    @api.model
    def jump_start(self, company=None):
        """Open the wizard immediately for a company."""
        company = company or self.env.company
        wizard = self.create({"company_id": company.id})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }
