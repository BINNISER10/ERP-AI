"""ERPNext-style GL Entry doctype.

The heart of the ERPNext accounting engine: a flat, immutable ledger of
debit/credit movements.  Journal entries do not store balances; posting a
journal entry *creates* GL entries.  Every GL entry carries the voucher
reference, fiscal year, party, cost center, and the "against" account so
the audit trail (and General Ledger report) can be rebuilt at any time.

GL Entries are the source of truth for the Trial Balance, Profit & Loss
and Balance Sheet reports.
"""

from odoo import api, fields, models, _


class NexusGlEntry(models.Model):
    _name = "nexus.gl.entry"
    _description = "Nexus Financial GL Entry"
    _order = "posting_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="GL Entry No",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
    )
    posting_date = fields.Date(string="Posting Date", required=True, index=True)
    transaction_date = fields.Date(string="Transaction Date")
    voucher_type = fields.Char(string="Voucher Type", index=True)
    voucher_no = fields.Char(string="Voucher No", index=True)
    voucher_detail_no = fields.Char(string="Voucher Detail No")
    account_id = fields.Many2one(
        "nexus.account",
        string="Account",
        required=True,
        index=True,
        ondelete="restrict",
    )
    party_type = fields.Selection(
        [
            ("customer", "Customer"),
            ("supplier", "Supplier"),
            ("employee", "Employee"),
        ],
        string="Party Type",
    )
    party_id = fields.Many2one(
        "res.partner",
        string="Party",
        ondelete="restrict",
    )
    cost_center_id = fields.Many2one(
        "nexus.cost.center",
        string="Cost Center",
        ondelete="restrict",
    )
    against_account = fields.Char(
        string="Against Account",
        help="Human-readable list of the other side(s) of the entry.",
    )
    against_voucher_type = fields.Char(string="Against Voucher Type")
    against_voucher_no = fields.Char(string="Against Voucher No")
    debit = fields.Monetary(string="Debit", currency_field="company_currency_id")
    credit = fields.Monetary(string="Credit", currency_field="company_currency_id")
    account_currency_id = fields.Many2one(
        "res.currency",
        string="Account Currency",
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
    fiscal_year_id = fields.Many2one(
        "nexus.fiscal.year",
        string="Fiscal Year",
        index=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    is_opening = fields.Boolean(
        string="Is Opening",
        default=False,
        help="True when this GL Entry was created by the opening-entry wizard.",
    )
    is_advance = fields.Boolean(string="Is Advance", default=False)
    is_cancelled = fields.Boolean(string="Is Cancelled", default=False)
    remarks = fields.Text(string="Remarks")
    journal_entry_id = fields.Many2one(
        "nexus.journal.entry",
        string="Journal Entry",
        index=True,
        ondelete="cascade",
    )
    is_reverse = fields.Boolean(string="Is Reversal", default=False)

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "GL entry numbers must be unique.",
        ),
    ]

    @api.model
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == _("New") or not record.name:
                record.name = record._next_gl_number()
        return records

    @api.model
    def _next_gl_number(self):
        """Sequence-like GL numbering (e.g. GL-00001) without a separate ir.sequence."""
        last = self.search([], order="id desc", limit=1)
        if last:
            try:
                next_num = int(last.name.split("-")[1]) + 1
            except (IndexError, ValueError):
                next_num = 1
        else:
            next_num = 1
        return "GL-%05d" % next_num
