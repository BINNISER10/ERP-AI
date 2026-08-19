"""ERPNext-style Chart of Accounts (Account doctype).

A self-contained, parent-child tree of accounts with:
  - account_number + name  (like ERPNext's ``account_number`` / ``account_name``)
  - account_type + root_type (Asset/Liability/Equity/Income/Expense)
  - is_group and parent_id for hierarchy
  - currency override per account
  - freeze/disabled flags
"""

from odoo import api, fields, models, _


class NexusAccount(models.Model):
    _name = "nexus.account"
    _description = "Nexus Financial Account"
    _rec_name = "full_name"
    _order = "code"

    name = fields.Char(string="Account Name", required=True, translate=True)
    account_number = fields.Char(string="Account Number")
    code = fields.Char(
        string="Code",
        compute="_compute_code",
        store=True,
        help="Sortable code used for ordering the chart.",
    )
    full_name = fields.Char(
        string="Full Name",
        compute="_compute_full_name",
        store=True,
    )
    parent_id = fields.Many2one(
        "nexus.account",
        string="Parent Account",
        index=True,
        ondelete="cascade",
    )
    child_ids = fields.One2many("nexus.account", "parent_id")
    is_group = fields.Boolean(
        string="Is Group",
        default=False,
        help="Group accounts aggregate their children and cannot be posted to directly.",
    )
    account_type = fields.Many2one(
        "nexus.account.type",
        string="Account Type",
        required=True,
        help="e.g. Bank, Cash, Receivable, Payable, Fixed Asset, Expense...",
    )
    root_type = fields.Selection(
        [
            ("asset", "Asset"),
            ("liability", "Liability"),
            ("equity", "Equity"),
            ("income", "Income"),
            ("expense", "Expense"),
        ],
        string="Root Type",
        related="account_type.root_type",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        help="Leave empty to use the company currency.",
    )
    is_debit_or_credit = fields.Selection(
        [
            ("debit", "Debit"),
            ("credit", "Credit"),
        ],
        string="Normal Balance",
        default="debit",
        help="Normal balance side of the account.  Mirrors ERPNext's "
        "balance_must_be field.",
    )
    tax_rate = fields.Float(string="Tax Rate (%)", group_operator="avg")
    credit_limit = fields.Float(string="Credit Limit", group_operator="sum")
    disabled = fields.Boolean(
        string="Disabled",
        default=False,
        help="Disabled accounts cannot be selected in new journal entries.",
    )
    freeze_account = fields.Boolean(
        string="Freeze Account",
        default=False,
        help="When frozen, the account cannot be edited in posted entries.",
    )
    is_opening = fields.Boolean(
        string="Is Opening",
        default=False,
        help="Create opening balances here on fiscal-year opening.",
    )
    balance = fields.Monetary(
        string="Current Balance",
        compute="_compute_balance",
        currency_field="currency_id",
        store=False,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    _sql_constraints = [
        (
            "name_parent_uniq",
            "unique(name, parent_id, company_id)",
            "An account with this name already exists under the same parent.",
        ),
    ]

    @api.constrains("is_group", "child_ids")
    def _check_group_leaf(self):
        for record in self:
            if not record.is_group and record.child_ids:
                raise models.ValidationError(
                    _("Account '%s' has children, so it must be marked as a Group.") % record.name
                )

    @api.depends("account_number", "name")
    def _compute_code(self):
        for record in self:
            record.code = (
                (record.account_number or record.name)
                if record.account_number
                else record.name
            )

    @api.depends("parent_id", "name", "account_number")
    def _compute_full_name(self):
        for record in self:
            parts = []
            parent = record.parent_id
            while parent:
                parts.append(parent.name)
                parent = parent.parent_id
            parts.append(record.name)
            record.full_name = " / ".join(parts)

    @api.depends("currency_id")
    def _compute_balance(self):
        for record in self:
            record.balance = 0.0

    def action_open_ledger(self):
        """Open the General Ledger filtered on this account."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Ledger: %s") % self.full_name,
            "res_model": "nexus.gl.entry",
            "view_mode": "list,form",
            "domain": [("account_id", "=", self.id)],
            "context": {"search_default_not_cancelled": 1},
        }
