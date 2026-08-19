# -*- coding: utf-8 -*-
"""Nexus Saudi Company Settings — إعدادات الشركة السعودية.

A singleton-style model that stores ZATCA, MOL, MISA and other
Saudi-specific settings for a single company.  Created automatically
when ``nexus_saudi_localization`` is installed; one record per
company is enforced via ``(company_id)`` unique constraint.
"""

from odoo import api, fields, models, _


class NexusSaudiCompanySettings(models.Model):
    """Per-company Saudi localization settings."""

    _name = "nexus.saudi.company.settings"
    _description = "Nexus Saudi Company Settings"
    _inherit = ["mail.thread"]
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        ondelete="cascade",
    )
    country_code = fields.Char(
        related="company_id.country_code",
        string="Country Code",
    )

    # ── ZATCA / E-Invoicing ──
    zatca_enabled = fields.Boolean(string="Activate ZATCA", default=False)
    zatca_phase = fields.Selection(
        [
            ("phase_1", "Phase 1 — Generation"),
            ("phase_2", "Phase 2 — Integration"),
        ],
        string="ZATCA Phase",
        default="phase_1",
    )
    # These are ZATCA cryptographic credentials (OTP / CSID / signing key /
    # certificate). Restricted to System Administrators only — the broader
    # "Nexus Manager" group (granted read/write on this model via ACL) must
    # not be able to read or export them. Nothing in the current signing
    # code path reads these fields as a non-sudo manager, so this is safe.
    zatca_otp_code = fields.Char(
        string="ZATCA OTP",
        help="One-time password issued by ZATCA's Fatoora portal.",
        groups="base.group_system",
    )
    zatca_csid = fields.Char(
        string="Compliance CSID",
        help="Cryptographic Stamp Identifier issued by ZATCA.",
        groups="base.group_system",
    )
    zatca_production_csid = fields.Char(
        string="Production CSID",
        help="Production-grade CSID, replacing the compliance one.",
        groups="base.group_system",
    )
    zatca_private_key = fields.Binary(
        string="ZATCA Private Key",
        attachment=True,
        help="ECDSA private key used to sign invoice XML.",
        groups="base.group_system",
    )
    zatca_private_key_filename = fields.Char(
        string="ZATCA Private Key Filename",
        groups="base.group_system",
    )
    zatca_certificate = fields.Binary(
        string="ZATCA Certificate",
        attachment=True,
        groups="base.group_system",
    )
    zatca_certificate_filename = fields.Char(
        string="ZATCA Certificate Filename",
        groups="base.group_system",
    )
    zatca_invoice_counter = fields.Integer(
        string="Invoice Counter",
        default=0,
        help="Monotonic counter expected by ZATCA's QR scheme.",
    )
    zatca_last_invoice_hash = fields.Char(
        string="Last Invoice Hash (Base64)",
        help="Hash of the previous invoice — required by ZATCA's signing chain.",
    )

    # ── VAT ──
    vat_registered = fields.Boolean(string="VAT Registered", default=True)
    vat_rate = fields.Float(string="Default VAT Rate (%)", default=15.0)
    vat_number = fields.Char(
        related="company_id.vat",
        string="VAT Number (15 digits)",
    )
    vat_period_start_day = fields.Integer(
        string="VAT Period Start Day",
        default=1,
        help="Day of month the VAT period starts (1-28).",
    )
    vat_period_length_months = fields.Selection(
        [
            ("1", "Monthly"),
            ("3", "Quarterly"),
        ],
        string="VAT Period Length",
        default="3",
    )

    # ── Saudization / Nitaqat ──
    saudization_required = fields.Boolean(
        string="Nitaqat Tracking Required",
        default=False,
        help="Enable Saudization tracking (mandatory for most Saudi entities).",
    )
    target_saudization_pct = fields.Float(
        string="Target Saudization %",
        default=30.0,
        help="The Saudization target set by MOL for the entity's activity.",
    )
    current_saudization_pct = fields.Float(
        string="Current Saudization %",
        compute="_compute_saudization_pct",
        store=False,
    )
    band = fields.Selection(
        [
            ("platinum", "Platinum"),
            ("green_high", "Green (High)"),
            ("green_mid", "Green (Mid)"),
            ("green_low", "Green (Low)"),
            ("yellow", "Yellow"),
            ("red", "Red"),
        ],
        string="Nitaqat Band",
        compute="_compute_saudization_pct",
        store=False,
    )

    # ── WPS (Wage Protection System) ──
    wps_required = fields.Boolean(
        string="WPS Compliance Required",
        default=False,
        help="Enable Wage Protection System file generation.",
    )
    wps_bank_id = fields.Many2one(
        "res.bank",
        string="Primary WPS Bank",
    )
    wps_mol_username = fields.Char(string="MOL Username")
    wps_mol_establishment_id = fields.Char(
        string="MOL Establishment ID",
        help="رقم المنشأة في وزارة العمل (700xxxxxxx).",
    )

    # ── Address / Localization ──
    cr_number = fields.Char(
        string="Commercial Registration / رقم السجل التجاري",
        size=10,
        help="10-digit Commercial Registration number.",
    )
    national_address_code = fields.Char(
        string="National Short Address",
        help="4-letter + 4-digit short address code (e.g. RRRD2934).",
    )
    additional_id_number = fields.Char(
        string="Additional ID",
        help="700-series ID for governmental entities.",
    )

    notes = fields.Text(string="Notes")

    _sql_constraints = [
        (
            "saudi_company_unique",
            "UNIQUE(company_id)",
            "Only one Saudi settings record is allowed per company.",
        ),
    ]

    # ─────────────────────────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────────────────────────
    @api.depends("saudization_required", "target_saudization_pct")
    def _compute_saudization_pct(self):
        for rec in self:
            if not rec.company_id:
                rec.current_saudization_pct = 0.0
                rec.band = False
                continue
            employees = self.env["hr.employee"].search([
                ("company_id", "=", rec.company_id.id),
                ("active", "=", True),
            ])
            total = len(employees)
            saudi = sum(1 for e in employees if e.is_saudi_nationality)
            pct = (saudi / total * 100.0) if total else 0.0
            rec.current_saudization_pct = round(pct, 2)
            rec.band = self._band_for(pct, rec.target_saudization_pct)

    @api.model
    def _band_for(self, current_pct, target_pct):
        """Return the Nitaqat band label based on current vs target.

        The real Nitaqat bands depend on the activity and entity size;
        this is a reasonable approximation that mirrors the published
        thresholds.
        """
        if target_pct <= 0:
            return False
        ratio = current_pct / target_pct
        if ratio >= 1.0:
            return "platinum"
        if ratio >= 0.85:
            return "green_high"
        if ratio >= 0.7:
            return "green_mid"
        if ratio >= 0.5:
            return "green_low"
        if ratio >= 0.3:
            return "yellow"
        return "red"

    # ─────────────────────────────────────────────────────────────────
    # Singleton accessor
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def get_for_company(self, company=None):
        company = company or self.env.company
        rec = self.search([("company_id", "=", company.id)], limit=1)
        if rec:
            return rec
        # Auto-create with safe defaults
        return self.create({"company_id": company.id})

    # ─────────────────────────────────────────────────────────────────
    # Cron hooks
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def _cron_refresh_saudization(self):
        """Refresh the computed Saudization for all settings records."""
        for rec in self.search([]):
            rec._compute_saudization_pct()

    @api.model
    def _cron_vat_reminder(self):
        """Open a low-severity incident 7 days before VAT period end.

        The user is expected to have completed and submitted their VAT
        return by then. The reminder is a soft nudge, not a blocker.
        """
        today = fields.Date.today()
        for rec in self.search([("vat_registered", "=", True)]):
            next_due = self._next_vat_due(rec, today)
            days_left = (next_due - today).days
            if 0 <= days_left <= 7:
                Incident = self.env.get("copilot.support.incident")
                if not Incident:
                    continue
                # Avoid duplicate reminders in the same week
                existing = Incident.search_count([
                    ("name", "like", "VAT return due"),
                    ("create_date", ">=", fields.Datetime.subtract(
                        fields.Datetime.now(), days=5
                    )),
                ])
                if existing:
                    continue
                Incident.create({
                    "name": "VAT return due for %s" % rec.company_id.display_name,
                    "severity": "low",
                    "description": (
                        "إقرار ضريبة القيمة المضافة يستحق بعد %s يوم. "
                        "تاريخ الاستحقاق: %s"
                    ) % (days_left, next_due),
                })

    @api.model
    def _next_vat_due(self, rec, today):
        """Return the next VAT period-end date for the given settings."""
        start_day = rec.vat_period_start_day or 1
        if rec.vat_period_length_months == "1":
            # Monthly: period ends at the end of the next month
            if today.month == 12:
                return today.replace(year=today.year + 1, month=1, day=28)
            return today.replace(month=today.month + 1, day=28)
        # Quarterly: every 3 months
        quarter_end_month = ((today.month - 1) // 3 + 1) * 3
        if quarter_end_month > 12:
            return today.replace(year=today.year + 1, month=3, day=31)
        return today.replace(month=quarter_end_month, day=31)
