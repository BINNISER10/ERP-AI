from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FuelTank(models.Model):
    _name = "fuel.tank"
    _description = "Fuel Tank"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Tank Name", required=True, tracking=True)
    product_id = fields.Many2one(
        "product.product",
        string="Fuel Product",
        required=True,
        domain="[('type', '=', 'product')]",
        tracking=True,
    )
    capacity = fields.Float(
        string="Capacity (Liters)",
        required=True,
        digits=(16, 3),
        help="Maximum physical capacity in liters.",
    )
    current_volume = fields.Float(
        string="Current Volume (Liters)",
        digits=(16, 3),
        default=0.0,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Tank Location",
        required=True,
        domain="[('usage', '=', 'internal')]",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "check_capacity_positive",
            "CHECK(capacity > 0)",
            "Tank capacity must be greater than zero.",
        ),
    ]

    @api.constrains("current_volume", "capacity")
    def _check_volume_constraints(self):
        for tank in self:
            if tank.current_volume < 0:
                raise ValidationError(
                    _("Current volume in tank '%s' cannot be negative.") % tank.name
                )
            if tank.current_volume > tank.capacity:
                raise ValidationError(
                    _(
                        "Current volume in tank '%(tank)s' (%(volume)s L) cannot exceed "
                        "capacity (%(capacity)s L)."
                    )
                    % {"tank": tank.name, "volume": tank.current_volume, "capacity": tank.capacity}
                )
