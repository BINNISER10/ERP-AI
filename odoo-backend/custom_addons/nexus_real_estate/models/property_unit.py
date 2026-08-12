from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PropertyUnit(models.Model):
    _name = "property.unit"
    _description = "Property Unit"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Unit Name", required=True, tracking=True)
    property_id = fields.Many2one(
        "property.asset",
        string="Property",
        tracking=True,
    )
    unit_code = fields.Char(string="Unit Code", required=True, copy=False)
    unit_type = fields.Selection(
        [
            ("residential", "Residential"),
            ("commercial", "Commercial"),
            ("industrial", "Industrial"),
            ("mixed", "Mixed Use"),
        ],
        string="Unit Type",
        required=True,
        default="commercial",
    )
    area = fields.Float(string="Area (sqm)", digits=(16, 2))
    floor = fields.Integer(string="Floor")
    bedrooms = fields.Integer(string="Bedrooms")
    bathrooms = fields.Integer(string="Bathrooms")
    rent_amount = fields.Monetary(
        string="Monthly Rent",
        currency_field="currency_id",
        tracking=True,
    )
    sale_price = fields.Monetary(
        string="Sale Price",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    state = fields.Selection(
        [
            ("vacant", "Vacant"),
            ("occupied", "Occupied"),
            ("maintenance", "Maintenance"),
        ],
        string="Status",
        default="vacant",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Tenant",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "uniq_unit_code_company",
            "UNIQUE(unit_code, company_id)",
            "Unit code must be unique per company.",
        ),
    ]

    @api.constrains("area", "rent_amount", "sale_price")
    def _check_positive_values(self):
        for unit in self:
            if unit.area < 0:
                raise ValidationError(_("Area cannot be negative."))
            if unit.rent_amount < 0:
                raise ValidationError(_("Rent amount cannot be negative."))
            if unit.sale_price < 0:
                raise ValidationError(_("Sale price cannot be negative."))


class PropertyAsset(models.Model):
    _name = "property.asset"
    _description = "Property Asset"

    name = fields.Char(string="Property Name", required=True)
    address = fields.Text(string="Address")
    owner_id = fields.Many2one("res.partner", string="Owner")
    unit_ids = fields.One2many("property.unit", "property_id", string="Units")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
