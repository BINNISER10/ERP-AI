"""ERPNext-style Party Account doctype.

In ERPNext a Customer / Supplier can hold multiple accounts depending on
company.  This mapping mirrors the ``Party Account`` doctype: for a given
party_type (Customer/Supplier), party (res.partner) and company, it stores
the receivable/payable account to use.
"""

from odoo import api, fields, models, _


class NexusPartyAccount(models.Model):
    _name = "nexus.party.account"
    _description = "Nexus Financial Party Account"
    _rec_name = "display_name"

    party_type = fields.Selection(
        [
            ("customer", "Customer"),
            ("supplier", "Supplier"),
            ("employee", "Employee"),
        ],
        string="Party Type",
        required=True,
    )
    party_id = fields.Many2one(
        "res.partner",
        string="Party",
        required=True,
        ondelete="cascade",
        context={"default_is_company": True},
    )
    account_type = fields.Selection(
        [
            ("receivable", "Receivable"),
            ("payable", "Payable"),
        ],
        string="Account Type",
        required=True,
        help="Receivable for customers, Payable for suppliers.",
    )
    account_id = fields.Many2one(
        "nexus.account",
        string="Account",
        required=True,
        domain="[('is_group', '=', False), ('account_type.root_type', 'in', ('asset', 'liability'))]",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    display_name = fields.Char(compute="_compute_display_name")

    _sql_constraints = [
        (
            "party_type_company_uniq",
            "unique(party_type, party_id, account_type, company_id)",
            "This party/company already has an account of that type.",
        ),
    ]

    @api.depends("party_type", "party_id", "account_type", "company_id")
    def _compute_display_name(self):
        for record in self:
            record.display_name = "%s — %s (%s)" % (
                record.party_id.name,
                record.account_id.name,
                dict(record._fields["account_type"].selection).get(record.account_type, ""),
            )

    @api.model
    def resolve_account(self, party_id, party_type, company_id):
        """Return the receivable/payable account for a party, or None."""
        account_type = "receivable" if party_type in ("customer",) else "payable"
        record = self.search(
            [
                ("party_id", "=", party_id),
                ("party_type", "=", party_type),
                ("account_type", "=", account_type),
                ("company_id", "=", company_id),
            ],
            limit=1,
        )
        if record:
            return record.account_id
        # Fallback: try any company / shared mapping
        record = self.search(
            [
                ("party_id", "=", party_id),
                ("party_type", "=", party_type),
                ("account_type", "=", account_type),
            ],
            limit=1,
        )
        return record.account_id if record else False
