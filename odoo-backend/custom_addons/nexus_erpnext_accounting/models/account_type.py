"""ERPNext-style Account Type — an enumerable set of account classes.

Mirrors the ERPNext ``Account Type`` doctype: accounts are classified into
types such as Bank, Cash, Receivable, Payable, Fixed Asset, Tax, Stock,
Income, Expense, etc.  Each account references one type; each type has a
``root_type`` (Asset / Liability / Equity / Income / Expense) that drives
report placement in the Balance Sheet and Profit & Loss statement.
"""

from odoo import api, fields, models, _


class NexusAccountType(models.Model):
    _name = "nexus.account.type"
    _description = "Nexus Financial Account Type"
    _order = "name"

    name = fields.Char(string="Account Type", required=True, translate=True)
    root_type = fields.Selection(
        [
            ("asset", "Asset"),
            ("liability", "Liability"),
            ("equity", "Equity"),
            ("income", "Income"),
            ("expense", "Expense"),
        ],
        string="Root Type",
        required=True,
        help="Determines which financial statement this type belongs to.",
    )
    report_type = fields.Selection(
        [
            ("balance_sheet", "Balance Sheet"),
            ("profit_and_loss", "Profit and Loss"),
        ],
        string="Report Type",
        compute="_compute_report_type",
        store=True,
    )
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "An account type with this name already exists."),
    ]

    @api.depends("root_type")
    def _compute_report_type(self):
        for record in self:
            record.report_type = (
                "balance_sheet"
                if record.root_type in ("asset", "liability", "equity")
                else "profit_and_loss"
            )
