from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FuelPumpNozzle(models.Model):
    """A single physical meter/nozzle on a Lanfeng dispenser.

    Real-world layout (Ocean Seven fuel station technical study, Aug 2026):
    11 pumps host 23 nozzles in total (14 x Gasoline 91, 6 x Diesel,
    3 x Gasoline 95). A single pump routinely serves more than one fuel
    product, so the tank/product/meter association must live on the
    nozzle, not on the pump itself.
    """

    _name = "fuel.pump.nozzle"
    _description = "Fuel Pump Nozzle (Meter)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "pump_id, nozzle_number"

    name = fields.Char(
        string="Nozzle Reference",
        compute="_compute_name",
        store=True,
    )
    pump_id = fields.Many2one(
        "fuel.pump",
        string="Fuel Pump",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    nozzle_number = fields.Integer(
        string="Nozzle #",
        required=True,
        help="Physical nozzle number on the pump (1, 2 or 3).",
    )
    tank_id = fields.Many2one(
        "fuel.tank",
        string="Fuel Tank",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product",
        related="tank_id.product_id",
        string="Fuel Product",
        store=True,
        readonly=True,
    )
    meter_start = fields.Float(string="Starting Meter", digits=(16, 3), default=0.0, tracking=True)
    meter_end = fields.Float(string="Ending Meter", digits=(16, 3), default=0.0, tracking=True)
    controller_address = fields.Char(
        string="Controller Address",
        help=(
            "Identifier reported by the Forecourt Controller for this "
            "nozzle (e.g. 'P03-N02' — Lanfeng RS-485 pump/nozzle pair). "
            "Used to match incoming readings automatically."
        ),
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="pump_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "pump_nozzle_number_uniq",
            "unique(pump_id, nozzle_number)",
            "Nozzle number must be unique per pump.",
        ),
        (
            "controller_address_uniq",
            "unique(controller_address)",
            "Controller address must be unique across all nozzles.",
        ),
    ]

    @api.depends("pump_id.name", "nozzle_number")
    def _compute_name(self):
        for nozzle in self:
            nozzle.name = _("%(pump)s / N%(num)s") % {
                "pump": nozzle.pump_id.name or "?",
                "num": nozzle.nozzle_number,
            }

    @api.constrains("meter_start", "meter_end")
    def _check_meter_reading(self):
        for nozzle in self:
            if nozzle.meter_end < nozzle.meter_start:
                raise ValidationError(
                    _(
                        "Ending meter on nozzle '%(nozzle)s' must be greater than or "
                        "equal to the starting meter."
                    )
                    % {"nozzle": nozzle.name}
                )
