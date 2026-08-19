# -*- coding: utf-8 -*-
"""Nexus US Company Settings — إعدادات الشركة الأمريكية.

A singleton-style model that stores US-specific settings:
    * EIN, fiscal year, accounting basis (cash/accrual)
    * 1099 thresholds and tracking
    * Default multi-state nexus states
    * W-9 collection flag
    * ACH processor configuration
"""

from odoo import api, fields, models, _


class NexusUSCompanySettings(models.Model):
    """Per-company US localization settings."""

    _name = "nexus.us.company.settings"
    _description = "Nexus US Company Settings"
    _inherit = ["mail.thread"]
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        ondelete="cascade",
    )

    # ── Identity ──
    ein = fields.Char(
        string="EIN / Employer Identification Number",
        size=10,
        help="9-digit EIN (e.g. 12-3456789 → 123456789).",
    )
    legal_name = fields.Char(
        related="company_id.name",
        string="Legal Name",
    )
    state_of_incorporation = fields.Many2one(
        "res.country.state",
        string="State of Incorporation",
        domain=[("country_id.code", "=", "US")],
    )

    # ── Fiscal & Tax ──
    fiscal_year_end_month = fields.Selection(
        [
            ("1", "January"),
            ("2", "February"),
            ("3", "March"),
            ("4", "April"),
            ("5", "May"),
            ("6", "June"),
            ("7", "July"),
            ("8", "August"),
            ("9", "September"),
            ("10", "October"),
            ("11", "November"),
            ("12", "December"),
        ],
        string="Fiscal Year End Month",
        default="12",
    )
    fiscal_year_end_day = fields.Integer(
        string="Fiscal Year End Day",
        default=31,
    )
    accounting_basis = fields.Selection(
        [("accrual", "Accrual"), ("cash", "Cash")],
        string="Accounting Basis",
        default="accrual",
        help="Determines when revenue/expense are recognized.",
    )

    # ── 1099 ──
    track_1099 = fields.Boolean(
        string="Track 1099 Vendors",
        default=True,
    )
    require_w9 = fields.Boolean(
        string="Require W-9 from New Vendors",
        default=True,
    )
    form_1099_threshold = fields.Float(
        string="1099-NEC Threshold ($)",
        default=600.0,
        help="IRS threshold for requiring 1099-NEC filing.",
    )

    # ── Sales Tax Nexus ──
    nexus_state_ids = fields.Many2many(
        "res.country.state",
        string="Sales Tax Nexus States",
        domain=[("country_id.code", "=", "US")],
        help="States where the company has economic nexus and must collect sales tax.",
    )
    default_sales_tax_rate = fields.Float(
        string="Default Sales Tax Rate (%)",
        default=0.0,
    )
    use_economic_nexus = fields.Boolean(
        string="Track Economic Nexus Thresholds",
        default=True,
        help="Monitor transaction count / dollar threshold by state.",
    )
    economic_nexus_threshold_usd = fields.Float(
        string="Economic Nexus Threshold (USD)",
        default=100000.0,
        help="Many states trigger economic nexus at $100K sales.",
    )
    economic_nexus_txn_threshold = fields.Integer(
        string="Economic Nexus Transaction Count Threshold",
        default=200,
        help="Many states trigger economic nexus at 200+ transactions.",
    )

    # ── Payment Processing ──
    ach_processor = fields.Selection(
        [
            ("manual", "Manual / Wire Transfer"),
            ("stripe", "Stripe ACH"),
            ("plaid", "Plaid"),
            ("dwolla", "Dwolla"),
        ],
        string="ACH Processor",
        default="manual",
    )
    # Persistent bank/processor credentials. Restricted to System
    # Administrators only, regardless of the broader "Nexus Manager" ACL
    # granted on this model, since nothing else in the codebase currently
    # reads these fields as a non-admin user.
    ach_routing_number = fields.Char(
        string="Default ACH Routing Number",
        help="Bank routing number used as default for outbound ACH.",
        groups="base.group_system",
    )
    ach_account_number = fields.Char(
        string="Default ACH Account Number",
        groups="base.group_system",
    )
    ach_processor_api_key = fields.Char(
        string="ACH Processor API Key",
        groups="base.group_system",
    )

    notes = fields.Text(string="Notes")

    _sql_constraints = [
        (
            "us_company_unique",
            "UNIQUE(company_id)",
            "Only one US settings record is allowed per company.",
        ),
    ]

    # ─────────────────────────────────────────────────────────────────
    # Singleton accessor
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def get_for_company(self, company=None):
        company = company or self.env.company
        rec = self.search([("company_id", "=", company.id)], limit=1)
        if rec:
            return rec
        return self.create({"company_id": company.id})

    # ─────────────────────────────────────────────────────────────────
    # Cron hooks
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def _cron_check_economic_nexus(self):
        """Alert when a new state crosses economic nexus threshold."""
        for rec in self.search([("use_economic_nexus", "=", True)]):
            company = rec.company_id
            states = rec.nexus_state_ids
            for state in self.env["res.country.state"].search([
                ("country_id.code", "=", "US"),
                ("id", "not in", states.ids),
            ]):
                total_sales = self._state_sales_total(
                    company, state
                )
                if total_sales >= rec.economic_nexus_threshold_usd:
                    Incident = self.env.get("copilot.support.incident")
                    if not Incident:
                        continue
                    existing = Incident.search_count([
                        ("name", "like", "Economic nexus - %s" % state.name),
                        ("create_date", ">=", fields.Datetime.subtract(
                            fields.Datetime.now(), days=30
                        )),
                    ])
                    if existing:
                        continue
                    Incident.create({
                        "name": "Economic nexus - %s" % state.name,
                        "severity": "medium",
                        "description": (
                            "%s مبيعات في %s تجاوزت العتبة الاقتصادية "
                            "($%.2f). يُرجى التسجيل في الولاية للامتثال الضريبي."
                        ) % (total_sales, state.name, rec.economic_nexus_threshold_usd),
                    })

    @api.model
    def _state_sales_total(self, company, state, year_start=None):
        """Sum YTD sales in a given US state."""
        if not year_start:
            today = fields.Date.today()
            year_start = today.replace(month=1, day=1)
        moves = self.env["account.move"].search_read([
            ("company_id", "=", company.id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", year_start),
            ("partner_id.state_id", "=", state.id),
        ], ["amount_total"])
        return sum(m["amount_total"] for m in moves)

    @api.model
    def _cron_1099_reminder(self):
        """Open a low-severity incident on January 5th to remind
        about 1099 filings.
        """
        today = fields.Date.today()
        if today.month != 1 or today.day > 15:
            return
        Incident = self.env.get("copilot.support.incident")
        if not Incident:
            return
        existing = Incident.search_count([
            ("name", "like", "1099 filing reminder"),
            ("create_date", ">=", fields.Datetime.subtract(
                fields.Datetime.now(), days=14
            )),
        ])
        if existing:
            return
        Incident.create({
            "name": "1099 filing reminder",
            "severity": "low",
            "description": (
                "تذكير: موسم تقديم 1099-NEC و 1099-MISC. "
                "تاريخ الاستحقاق 31 يناير."
            ),
        })
