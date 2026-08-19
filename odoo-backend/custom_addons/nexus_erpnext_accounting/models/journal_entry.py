"""ERPNext-style Journal Entry + Journal Entry Account.

A Journal Entry is a balanced set of debit/credit lines.  Posting a
journal entry writes immutable GL Entries (double-entry), validates that
debits == credits, resolves party accounts, and records the against side.

Workflow (mirrors ERPNext): Draft -> Submitted -> Cancelled.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

VOUCHER_TYPES = [
    ("journal_entry", "Journal Entry"),
    ("bank_entry", "Bank Entry"),
    ("cash_entry", "Cash Entry"),
    ("credit_note", "Credit Note"),
    ("debit_note", "Debit Note"),
    ("contra_entry", "Contra Entry"),
    ("payment_entry", "Payment Entry"),
    ("opening_entry", "Opening Entry"),
    ("closing_entry", "Closing Entry"),
    ("purchase_invoice", "Purchase Invoice"),
    ("sales_invoice", "Sales Invoice"),
    ("salary_entry", "Salary Entry"),
    ("payroll_entry", "Payroll Entry"),
    ("expense_claim", "Expense Claim"),
    ("asset_capitalization", "Asset Capitalization"),
    ("asset_depreciation", "Asset Depreciation"),
    ("exchange_rate_revaluation", "Exchange Rate Revaluation"),
    ("excise_entry", "Excise Entry"),
    ("deferred_revenue", "Deferred Revenue"),
    ("deferred_expense", "Deferred Expense"),
]


class NexusJournalEntry(models.Model):
    _name = "nexus.journal.entry"
    _description = "Nexus Financial Journal Entry"
    _order = "posting_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Journal Entry No",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
    )
    posting_date = fields.Date(
        string="Posting Date",
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    accounting_date = fields.Date(string="Accounting Date")
    voucher_type = fields.Selection(
        VOUCHER_TYPES,
        string="Voucher Type",
        default="journal_entry",
        required=True,
    )
    reference = fields.Char(string="Reference")
    user_remark = fields.Text(string="User Remark")
    title = fields.Char(string="Title", compute="_compute_title")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    is_opening = fields.Boolean(string="Is Opening Entry", default=False)
    multi_currency = fields.Boolean(
        string="Multi Currency",
        compute="_compute_multi_currency",
        store=True,
    )
    total_debit = fields.Monetary(
        string="Total Debit",
        compute="_compute_totals",
        currency_field="company_currency_id",
        store=True,
    )
    total_credit = fields.Monetary(
        string="Total Credit",
        compute="_compute_totals",
        currency_field="company_currency_id",
        store=True,
    )
    difference = fields.Monetary(
        string="Difference",
        compute="_compute_totals",
        currency_field="company_currency_id",
        store=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        "nexus.journal.entry.line",
        "journal_entry_id",
        string="Journal Entry Accounts",
        copy=True,
    )
    reversal_of_id = fields.Many2one(
        "nexus.journal.entry",
        string="Reversal Of",
        readonly=True,
        copy=False,
    )
    fiscal_year_id = fields.Many2one(
        "nexus.fiscal.year",
        string="Fiscal Year",
        compute="_compute_fiscal_year",
        store=True,
    )
    gl_entry_count = fields.Integer(
        string="GL Entries",
        compute="_compute_gl_entry_count",
    )
    gl_entry_ids = fields.One2many(
        "nexus.gl.entry",
        "journal_entry_id",
        string="GL Entries",
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------

    @api.depends("reference", "voucher_type", "posting_date", "user_remark")
    def _compute_title(self):
        for record in self:
            record.title = " ".join(
                filter(
                    None,
                    [
                        record.reference,
                        dict(record._fields["voucher_type"].selection).get(
                            record.voucher_type, ""
                        ),
                        record.user_remark,
                    ],
                )
            ) or _("Journal Entry")

    @api.depends("line_ids.debit", "line_ids.credit", "line_ids.debit_in_account_currency")
    def _compute_totals(self):
        for record in self:
            record.total_debit = sum(record.line_ids.mapped("debit"))
            record.total_credit = sum(record.line_ids.mapped("credit"))
            record.difference = record.total_debit - record.total_credit

    @api.depends("line_ids.account_id.currency_id")
    def _compute_multi_currency(self):
        for record in self:
            record.multi_currency = any(
                line.account_id.currency_id and line.account_id.currency_id != record.company_id.currency_id
                for line in record.line_ids
            )

    @api.depends("posting_date", "company_id")
    def _compute_fiscal_year(self):
        for record in self:
            fiscal = self.env["nexus.fiscal.year"].get_fiscal_year(
                record.company_id.id, record.posting_date
            )
            record.fiscal_year_id = fiscal.id if fiscal else False

    @api.depends("gl_entry_ids")
    def _compute_gl_entry_count(self):
        for record in self:
            record.gl_entry_count = len(record.gl_entry_ids)

    # ------------------------------------------------------------------
    # Name / numbering
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                company_id = vals.get("company_id") or self.env.company.id
                seq = self.env["ir.sequence"].with_company(company_id).next_by_code(
                    "nexus.journal.entry", sequence_date=vals.get("posting_date")
                )
                vals["name"] = seq or _("New")
        return super(NexusJournalEntry, self).create(vals_list)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_for_posting(self):
        for entry in self:
            if not entry.line_ids:
                raise UserError(_("Journal Entry %s has no lines.") % entry.name)
            if abs(entry.difference) > 0.0001:
                raise UserError(
                    _(
                        "Journal Entry %(name)s is not balanced. "
                        "Debit total: %(dr).2f / Credit total: %(cr).2f "
                        "Difference: %(diff).2f"
                    )
                    % {
                        "name": entry.name,
                        "dr": entry.total_debit,
                        "cr": entry.total_credit,
                        "diff": entry.difference,
                    }
                )
            for line in entry.line_ids:
                if line.account_id.is_group:
                    raise UserError(
                        _(
                            "Line account '%(account)s' is a group account and "
                            "cannot be posted to directly."
                        )
                        % {"account": line.account_id.name}
                    )
                if line.account_id.disabled:
                    raise UserError(
                        _("Account '%s' is disabled and cannot be used in a journal entry.")
                        % line.account_id.name
                    )
                if line.debit and line.credit:
                    raise UserError(
                        _("Line '%s' cannot have both debit and credit values.")
                        % line.name
                    )

    def _ensure_fiscal_year(self):
        for entry in self:
            fiscal = self.env["nexus.fiscal.year"].get_fiscal_year(
                entry.company_id.id, entry.posting_date
            )
            if not fiscal:
                raise UserError(
                    _(
                        "There is no open fiscal year covering %(date)s for company '%(company)s'. "
                        "Create or open a fiscal year before posting."
                    )
                    % {"date": entry.posting_date, "company": entry.company_id.name}
                )

    # ------------------------------------------------------------------
    # Posting engine — creates GL entries (the audit trail)
    # ------------------------------------------------------------------

    def action_submit(self):
        """Validate and post the journal entry, generating GL Entries."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft journal entries can be submitted."))
        self._validate_for_posting()
        self._ensure_fiscal_year()
        self._create_gl_entries()
        self.write({"state": "submitted"})
        self.message_post(body=_("Journal Entry %s submitted and posted to the GL.") % self.name)
        return True

    def _create_gl_entries(self):
        """Create one GL Entry per journal line, resolving the against side."""
        gl_model = self.env["nexus.gl.entry"]
        for entry in self:
            fiscal = self.env["nexus.fiscal.year"].get_fiscal_year(
                entry.company_id.id, entry.posting_date
            )
            other_lines = entry.line_ids
            for line in entry.line_ids:
                against_names = [
                    ol.account_id.full_name
                    for ol in other_lines
                    if ol.id != line.id and ol.account_id
                ]
                against = ", ".join(dict.fromkeys(against_names)) if against_names else ""
                gl_model.create(
                    {
                        "posting_date": entry.posting_date,
                        "transaction_date": entry.accounting_date or entry.posting_date,
                        "voucher_type": entry.voucher_type,
                        "voucher_no": entry.name,
                        "account_id": line.account_id.id,
                        "party_type": line.party_type,
                        "party_id": line.party_id.id,
                        "cost_center_id": line.cost_center_id.id,
                        "against_account": against,
                        "debit": line.debit,
                        "credit": line.credit,
                        "account_currency_id": (
                            line.account_id.currency_id.id
                            or entry.company_currency_id.id
                        ),
                        "debit_in_account_currency": line.debit_in_account_currency
                        or line.debit,
                        "credit_in_account_currency": line.credit_in_account_currency
                        or line.credit,
                        "exchange_rate": line.exchange_rate,
                        "fiscal_year_id": fiscal.id if fiscal else False,
                        "company_id": entry.company_id.id,
                        "is_opening": entry.is_opening,
                        "remarks": line.remark or entry.user_remark,
                        "journal_entry_id": entry.id,
                    }
                )

    def action_cancel(self):
        """Cancel a submitted journal entry by removing its GL entries."""
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted journal entries can be cancelled."))
        self.line_ids.gl_entry_ids.unlink()
        self.write({"state": "cancelled"})
        self.message_post(body=_("Journal Entry %s cancelled.") % self.name)
        return True

    def action_set_draft(self):
        self.ensure_one()
        if self.state != "cancelled":
            raise UserError(_("Only cancelled journal entries can be reset to draft."))
        self.write({"state": "draft"})
        return True

    def action_view_gl_entries(self):
        self.ensure_one()
        gls = self.gl_entry_ids
        return {
            "type": "ir.actions.act_window",
            "name": _("GL Entries"),
            "res_model": "nexus.gl.entry",
            "view_mode": "list,form",
            "domain": [("id", "in", gls.ids)],
        }

    def action_reverse(self):
        """Create a reversal journal entry mirroring this one."""
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted entries can be reversed."))
        reverse = self.copy(
            default={
                "name": False,
                "state": "draft",
                "posting_date": fields.Date.context_today(self),
                "reversal_of_id": self.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": line.account_id.id,
                            "party_type": line.party_type,
                            "party_id": line.party_id.id,
                            "cost_center_id": line.cost_center_id.id,
                            "debit": line.credit,
                            "credit": line.debit,
                            "remark": _("Reversal of %s") % self.name,
                        },
                    )
                    for line in self.line_ids
                ],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Reversal Journal Entry"),
            "res_model": "nexus.journal.entry",
            "view_mode": "form",
            "res_id": reverse.id,
        }


class NexusJournalEntryLine(models.Model):
    _name = "nexus.journal.entry.line"
    _description = "Nexus Financial Journal Entry Line"
    _order = "id"

    journal_entry_id = fields.Many2one(
        "nexus.journal.entry",
        string="Journal Entry",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(compute="_compute_line_name", store=True)
    account_id = fields.Many2one(
        "nexus.account",
        string="Account",
        required=True,
        ondelete="restrict",
        domain="[('is_group', '=', False), ('disabled', '=', False)]",
    )
    account_name = fields.Char(related="account_id.name", string="Account Name")
    party_type = fields.Selection(
        [
            ("customer", "Customer"),
            ("supplier", "Supplier"),
            ("employee", "Employee"),
        ],
        string="Party Type",
    )
    party_id = fields.Many2one("res.partner", string="Party", ondelete="restrict")
    cost_center_id = fields.Many2one(
        "nexus.cost.center",
        string="Cost Center",
        ondelete="restrict",
    )
    project_id = fields.Many2one("project.project", string="Project", ondelete="restrict")
    debit = fields.Monetary(string="Debit", currency_field="company_currency_id")
    credit = fields.Monetary(string="Credit", currency_field="company_currency_id")
    company_id = fields.Many2one(
        "res.company",
        related="journal_entry_id.company_id",
        store=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    account_currency_id = fields.Many2one(
        "res.currency",
        related="account_id.currency_id",
        readonly=True,
    )
    debit_in_account_currency = fields.Monetary(
        string="Debit (Account Currency)",
        currency_field="account_currency_id",
    )
    credit_in_account_currency = fields.Monetary(
        string="Credit (Account Currency)",
        currency_field="account_currency_id",
    )
    exchange_rate = fields.Float(string="Exchange Rate", default=1.0)
    reference = fields.Char(string="Reference")
    remark = fields.Text(string="Remark")
    is_advance = fields.Boolean(string="Is Advance", default=False)
    is_opening = fields.Boolean(string="Is Opening", default=False)

    @api.depends("account_id", "party_id")
    def _compute_line_name(self):
        for line in self:
            parts = []
            if line.party_id:
                parts.append(line.party_id.name)
            if line.account_id:
                parts.append(line.account_id.name)
            line.name = " / ".join(parts) or _("Line")
