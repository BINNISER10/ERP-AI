"""ERPNext-style Fiscal Year doctype.

Defines a company's accounting year window.  Journal entries can only be
posted inside an open fiscal year, and every GL Entry records the fiscal
year it belongs to.
"""

from odoo import api, fields, models, _


class NexusFiscalYear(models.Model):
    _name = "nexus.fiscal.year"
    _description = "Nexus Financial Fiscal Year"
    _rec_name = "year_name"

    year_name = fields.Char(
        string="Fiscal Year",
        compute="_compute_year_name",
        store=True,
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    year_start_date = fields.Date(string="Year Start Date", required=True)
    year_end_date = fields.Date(string="Year End Date", required=True)
    year_closed = fields.Boolean(
        string="Year Closed",
        default=False,
        help="When closed, new entries cannot be posted in this fiscal year.",
    )
    closing_journal_entry_id = fields.Many2one(
        "nexus.journal.entry",
        string="Closing Journal Entry",
        readonly=True,
        copy=False,
    )
    opening_journal_entry_id = fields.Many2one(
        "nexus.journal.entry",
        string="Opening Journal Entry",
        readonly=True,
        copy=False,
    )
    auto_created = fields.Boolean(
        string="Auto Created",
        default=False,
        copy=False,
    )

    _sql_constraints = [
        ("year_uniq", "unique(year_name, company_id)", "This fiscal year already exists."),
    ]

    @api.depends("year_start_date", "year_end_date")
    def _compute_year_name(self):
        for record in self:
            if record.year_start_date and record.year_end_date:
                record.year_name = "FY %s - %s" % (
                    record.year_start_date.year,
                    record.year_end_date.year,
                )
            else:
                record.year_name = "Unnamed Fiscal Year"

    @api.constrains("year_start_date", "year_end_date")
    def _check_dates(self):
        for record in self:
            if (
                record.year_start_date
                and record.year_end_date
                and record.year_end_date < record.year_start_date
            ):
                raise models.ValidationError(
                    _("The fiscal year end date must be after the start date.")
                )

    @api.model
    def get_fiscal_year(self, company_id, date_value=None):
        """Return the open fiscal year for a company/date, or an empty recordset."""
        date_value = date_value or fields.Date.context_today(self)
        fiscal = self.search(
            [
                ("company_id", "=", company_id),
                ("year_start_date", "<=", date_value),
                ("year_end_date", ">=", date_value),
                ("year_closed", "=", False),
            ],
            limit=1,
        )
        return fiscal

    def action_create_opening_entry(self):
        """Open a blank opening Journal Entry dated at the fiscal year start."""
        self.ensure_one()
        if self.year_closed:
            raise models.ValidationError(
                _("This fiscal year is closed; you cannot create an opening entry.")
            )
        opening = self.env["nexus.journal.entry"].create(
            {
                "posting_date": self.year_start_date,
                "voucher_type": "opening_entry",
                "reference": "Opening %s" % self.year_name,
                "is_opening": True,
                "company_id": self.company_id.id,
                "user_remark": _(
                    "Opening balances for fiscal year %s. "
                    "Enter the closing balances of the previous year here."
                )
                % self.year_name,
            }
        )
        self.opening_journal_entry_id = opening.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Opening Journal Entry"),
            "res_model": "nexus.journal.entry",
            "view_mode": "form",
            "res_id": opening.id,
        }
