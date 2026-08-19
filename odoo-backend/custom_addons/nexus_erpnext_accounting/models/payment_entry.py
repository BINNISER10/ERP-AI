"""ERPNext-style Payment Entry doctype.

Records money received from customers or paid to suppliers, and allocates
it against outstanding invoices (references).  On submission it creates
the balanced Journal Entry and the corresponding GL entries.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NexusPaymentEntry(models.Model):
    _name = "nexus.payment.entry"
    _description = "Nexus Financial Payment Entry"
    _order = "posting_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Payment No",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
    )
    payment_type = fields.Selection(
        [
            ("receive", "Receive"),
            ("pay", "Pay"),
            ("internal", "Internal Transfer"),
        ],
        string="Payment Type",
        required=True,
        default="receive",
    )
    party_type = fields.Selection(
        [
            ("customer", "Customer"),
            ("supplier", "Supplier"),
            ("employee", "Employee"),
        ],
        string="Party Type",
        required=True,
        default="customer",
    )
    party_id = fields.Many2one(
        "res.partner",
        string="Party",
        required=True,
        ondelete="restrict",
    )
    posting_date = fields.Date(
        string="Posting Date",
        required=True,
        default=fields.Date.context_today,
    )
    mode_of_payment = fields.Char(string="Mode of Payment")
    reference_no = fields.Char(string="Reference No")
    reference_date = fields.Date(string="Reference Date")
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
    paid_from_account_id = fields.Many2one(
        "nexus.account",
        string="Paid From Account",
        ondelete="restrict",
    )
    paid_to_account_id = fields.Many2one(
        "nexus.account",
        string="Paid To Account",
        ondelete="restrict",
    )
    paid_amount = fields.Monetary(
        string="Paid Amount",
        currency_field="company_currency_id",
        default=0.0,
    )
    received_amount = fields.Monetary(
        string="Received Amount",
        currency_field="company_currency_id",
        default=0.0,
    )
    difference_amount = fields.Monetary(
        string="Difference Amount",
        currency_field="company_currency_id",
        compute="_compute_difference_amount",
    )
    total_allocated_amount = fields.Monetary(
        string="Total Allocated Amount",
        currency_field="company_currency_id",
        compute="_compute_allocated_totals",
    )
    unallocated_amount = fields.Monetary(
        string="Unallocated Amount",
        currency_field="company_currency_id",
        compute="_compute_allocated_totals",
    )
    reference_ids = fields.One2many(
        "nexus.payment.reference",
        "payment_entry_id",
        string="References",
    )
    journal_entry_id = fields.Many2one(
        "nexus.journal.entry",
        string="Journal Entry",
        readonly=True,
        copy=False,
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

    _sql_constraints = [
        (
            "party_amount_positive",
            "check(paid_amount >= 0 and received_amount >= 0)",
            "Payment amounts must be positive.",
        ),
    ]

    @api.onchange("party_id", "party_type", "company_id")
    def _onchange_party_resolve_accounts(self):
        """Auto-resolve receivable/payable accounts from the party mapping."""
        for record in self:
            if not record.party_id:
                continue
            if record.payment_type == "receive":
                record.paid_from_account_id = (
                    self.env["nexus.party.account"]
                    .resolve_account(record.party_id.id, "customer", record.company_id.id)
                    or record.paid_from_account_id
                )
            elif record.payment_type == "pay":
                record.paid_to_account_id = (
                    self.env["nexus.party.account"]
                    .resolve_account(record.party_id.id, "supplier", record.company_id.id)
                    or record.paid_to_account_id
                )

    @api.onchange("party_id")
    def _onchange_party_fetch_outstanding(self):
        """Suggest the outstanding invoices for allocation."""
        for record in self:
            if record.party_id and record.party_type in ("customer", "supplier"):
                record._refresh_reference_ids()

    @api.depends("paid_amount", "received_amount")
    def _compute_difference_amount(self):
        for record in self:
            record.difference_amount = record.paid_amount - record.received_amount

    @api.depends("reference_ids.allocated_amount")
    def _compute_allocated_totals(self):
        for record in self:
            record.total_allocated_amount = sum(record.reference_ids.mapped("allocated_amount"))
            record.unallocated_amount = record.received_amount - record.total_allocated_amount

    # ------------------------------------------------------------------
    # Outstanding invoice fetch
    # ------------------------------------------------------------------

    def _refresh_reference_ids(self):
        """Fetch outstanding invoices for this party and pre-fill allocations."""
        self.ensure_one()
        if not self.party_id:
            return
        move_type = "out_invoice" if self.party_type == "customer" else "in_invoice"
        invoices = self.env["account.move"].search(
            [
                ("move_type", "=", move_type),
                ("partner_id", "=", self.party_id.id),
                ("state", "=", "posted"),
                ("payment_state", "in", ("not_paid", "partial")),
            ],
            order="invoice_date",
        )
        vals_list = []
        existing = {
            ref.nexus_document_name: ref
            for ref in self.reference_ids
            if ref.nexus_document_name
        }
        for invoice in invoices:
            if invoice.name in existing:
                continue
            vals_list.append(
                (0, 0, {
                    "nexus_document_type": "account.move",
                    "nexus_document_name": invoice.name,
                    "nexus_document_id": invoice.id,
                    "total_amount": invoice.amount_total,
                    "outstanding_amount": invoice.amount_residual,
                    "allocated_amount": 0.0,
                })
            )
        if vals_list:
            self.reference_ids = vals_list

    # ------------------------------------------------------------------
    # Submit / cancel
    # ------------------------------------------------------------------

    def action_submit(self):
        for record in self:
            record._validate_payment()
            record._create_journal_entry()
            record.write({"state": "submitted"})
        return True

    def _validate_payment(self):
        self.ensure_one()
        if self.paid_amount <= 0 and self.received_amount <= 0:
            raise UserError(_("Payment amount must be greater than zero."))
        if self.payment_type == "internal":
            if not self.paid_from_account_id or not self.paid_to_account_id:
                raise UserError(_("Select both the 'Paid From' and 'Paid To' accounts."))
        if abs(self.unallocated_amount) > 0.005:
            raise UserError(
                _(
                    "Payment is not fully allocated. Unallocated amount: %(amount).2f. "
                    "Allocate the full amount to references, or leave it as advance."
                )
                % {"amount": self.unallocated_amount}
            )

    def _create_journal_entry(self):
        """Build the balanced journal entry that moves the cash and clears the debts."""
        self.ensure_one()
        if self.journal_entry_id:
            return self.journal_entry_id

        lines = []
        # The cash side
        if self.payment_type == "receive":
            cash_account = self.paid_to_account_id
            receivable_account = self.paid_from_account_id
            if not cash_account:
                raise UserError(_("Select the 'Paid To' (cash/bank) account."))
            if not receivable_account:
                raise UserError(_("Select the 'Paid From' (receivable) account."))
            lines.append(
                {
                    "account_id": cash_account.id,
                    "debit": self.received_amount,
                    "remark": _("Payment received from %s") % self.party_id.name,
                }
            )
        elif self.payment_type == "pay":
            cash_account = self.paid_from_account_id
            payable_account = self.paid_to_account_id
            if not cash_account:
                raise UserError(_("Select the 'Paid From' (cash/bank) account."))
            if not payable_account:
                raise UserError(_("Select the 'Paid To' (payable) account."))
            lines.append(
                {
                    "account_id": cash_account.id,
                    "credit": self.paid_amount,
                    "remark": _("Payment made to %s") % self.party_id.name,
                }
            )
        else:  # internal transfer
            lines.append(
                {
                    "account_id": self.paid_from_account_id.id,
                    "credit": self.paid_amount,
                    "remark": _("Internal transfer from %s") % self.paid_from_account_id.name,
                }
            )
            lines.append(
                {
                    "account_id": self.paid_to_account_id.id,
                    "debit": self.paid_amount,
                    "remark": _("Internal transfer to %s") % self.paid_to_account_id.name,
                }
            )

        # The party side — allocate against each reference
        party_account = self._get_party_ledger_account()
        for reference in self.reference_ids:
            if not reference.allocated_amount:
                continue
            if self.payment_type == "receive":
                lines.append(
                    {
                        "account_id": party_account.id,
                        "party_type": self.party_type,
                        "party_id": self.party_id.id,
                        "credit": reference.allocated_amount,
                        "remark": _(
                            "Payment allocated to %(doc)s (%(name)s)",
                            doc=reference.nexus_document_name,
                            name=reference.nexus_document_type,
                        ),
                    }
                )
            elif self.payment_type == "pay":
                lines.append(
                    {
                        "account_id": party_account.id,
                        "party_type": self.party_type,
                        "party_id": self.party_id.id,
                        "debit": reference.allocated_amount,
                        "remark": _(
                            "Payment allocated to %(doc)s (%(name)s)",
                            doc=reference.nexus_document_name,
                            name=reference.nexus_document_type,
                        ),
                    }
                )

        # Unallocated part = advance on the party ledger
        advance = self.received_amount if self.payment_type == "receive" else self.paid_amount
        allocated = self.total_allocated_amount
        if abs(advance - allocated) > 0.005 and party_account:
            remaining = advance - allocated
            if self.payment_type == "receive":
                lines.append(
                    {
                        "account_id": party_account.id,
                        "party_type": self.party_type,
                        "party_id": self.party_id.id,
                        "credit": remaining,
                        "remark": _("Advance payment from %s") % self.party_id.name,
                    }
                )
            elif self.payment_type == "pay":
                lines.append(
                    {
                        "account_id": party_account.id,
                        "party_type": self.party_type,
                        "party_id": self.party_id.id,
                        "debit": remaining,
                        "remark": _("Advance payment to %s") % self.party_id.name,
                    }
                )

        entry = self.env["nexus.journal.entry"].create(
            {
                "posting_date": self.posting_date,
                "voucher_type": "payment_entry",
                "reference": self.name,
                "user_remark": _("Payment: %s") % self.reference_no or self.name,
                "company_id": self.company_id.id,
                "line_ids": [(0, 0, line) for line in lines],
            }
        )
        entry.action_submit()
        self.journal_entry_id = entry.id
        return entry

    def _get_party_ledger_account(self):
        self.ensure_one()
        party_kind = "customer" if self.party_type == "customer" else (
            "supplier" if self.party_type == "supplier" else "employee"
        )
        account = self.env["nexus.party.account"].resolve_account(
            self.party_id.id, party_kind, self.company_id.id
        )
        if not account:
            raise UserError(
                _(
                    "No receivable/payable account is configured for %(party)s. "
                    "Create a Party Account mapping first."
                )
                % {"party": self.party_id.name}
            )
        return account

    def action_cancel(self):
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only submitted payments can be cancelled."))
            if record.journal_entry_id:
                record.journal_entry_id.action_cancel()
                record.journal_entry_id = False
            record.write({"state": "cancelled"})
        return True

    def action_view_journal_entry(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Journal Entry"),
            "res_model": "nexus.journal.entry",
            "view_mode": "form",
            "res_id": self.journal_entry_id.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == _("New") or not record.name:
                record.name = record._next_payment_number()
        return records

    @api.model
    def _next_payment_number(self):
        last = self.search([], order="id desc", limit=1)
        if last:
            try:
                next_num = int(last.name.split("-")[1]) + 1
            except (IndexError, ValueError):
                next_num = 1
        else:
            next_num = 1
        return "PAY-%05d" % next_num


class NexusPaymentReference(models.Model):
    _name = "nexus.payment.reference"
    _description = "Nexus Financial Payment Reference"

    payment_entry_id = fields.Many2one(
        "nexus.payment.entry",
        string="Payment Entry",
        required=True,
        ondelete="cascade",
        index=True,
    )
    nexus_document_type = fields.Char(string="Reference Type")
    nexus_document_name = fields.Char(string="Reference Name")
    nexus_document_id = fields.Integer(string="Document ID")
    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field="company_currency_id",
    )
    outstanding_amount = fields.Monetary(
        string="Outstanding Amount",
        currency_field="company_currency_id",
    )
    allocated_amount = fields.Monetary(
        string="Allocated Amount",
        currency_field="company_currency_id",
    )
    company_id = fields.Many2one(
        "res.company",
        related="payment_entry_id.company_id",
        store=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
