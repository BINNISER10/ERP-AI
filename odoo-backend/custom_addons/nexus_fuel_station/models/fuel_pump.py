from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FuelPump(models.Model):
    _name = "fuel.pump"
    _description = "Fuel Pump"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Pump Name", required=True, tracking=True)
    tank_id = fields.Many2one(
        "fuel.tank",
        string="Fuel Tank",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    product_id = fields.Many2one(
        related="tank_id.product_id",
        string="Fuel Product",
        store=True,
        readonly=True,
    )
    meter_start = fields.Float(
        string="Starting Meter",
        digits=(16, 3),
        default=0.0,
        tracking=True,
    )
    meter_end = fields.Float(
        string="Ending Meter",
        digits=(16, 3),
        default=0.0,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="tank_id.company_id",
        string="Company",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)
    nozzle_count = fields.Integer(string="Nozzle Count", default=1)

    @api.constrains("meter_start", "meter_end")
    def _check_meter_reading(self):
        for pump in self:
            if pump.meter_end < pump.meter_start:
                raise ValidationError(
                    _(
                        "Ending meter on pump '%(pump)s' must be greater than or equal to "
                        "the starting meter."
                    )
                    % {"pump": pump.name}
                )


class FuelPumpNozzle(models.Model):
    _name = "fuel.pump.nozzle"
    _description = "Fuel Pump Nozzle"

    pump_id = fields.Many2one("fuel.pump", string="Pump", required=True, ondelete="cascade")
    name = fields.Char(string="Nozzle Name", required=True)
    product_id = fields.Many2one(
        "product.product",
        string="Fuel Product",
        related="pump_id.product_id",
        store=True,
        readonly=True,
    )
    last_meter_reading = fields.Float(
        string="Last Meter Reading",
        digits=(16, 3),
        default=0.0,
    )
