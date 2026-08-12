from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UsTaxRate(models.Model):
    _name = "us.tax.rate"
    _description = "US Sales Tax Rate"

    name = fields.Char(string="Rate Name", required=True)
    state_code = fields.Char(string="State Code", required=True, size=2)
    county = fields.Char(string="County")
    city = fields.Char(string="City")
    zip_start = fields.Char(string="ZIP Start")
    zip_end = fields.Char(string="ZIP End")
    rate = fields.Float(
        string="Tax Rate",
        digits=(7, 5),
        required=True,
        help="Decimal tax rate, e.g. 0.0875 for 8.75%.",
    )
    tax_type = fields.Selection(
        [
            ("state", "State"),
            ("county", "County"),
            ("city", "City"),
            ("special", "Special District"),
        ],
        string="Tax Type",
        required=True,
        default="state",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("check_rate_positive", "CHECK(rate >= 0)", "Tax rate must not be negative."),
    ]

    @api.constrains("state_code")
    def _check_state_code(self):
        for rate in self:
            if len(rate.state_code) != 2:
                raise ValidationError(_("State code must be two letters."))

    def name_get(self):
        result = []
        for rec in self:
            parts = [rec.state_code]
            if rec.county:
                parts.append(rec.county)
            if rec.city:
                parts.append(rec.city)
            name = " - ".join(parts) + f" ({rec.rate * 100:.3f}%)"
            result.append((rec.id, name))
        return result
