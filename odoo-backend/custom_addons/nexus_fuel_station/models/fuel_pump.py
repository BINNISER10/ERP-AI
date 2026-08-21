from odoo import models, fields, api


class FuelPump(models.Model):
    """The physical Lanfeng dispenser cabinet.

    A single pump can host 1-3 nozzles (see ``fuel.pump.nozzle``), each
    tied to its own tank/fuel product, since dispensers in the field
    commonly serve Diesel + Gasoline 91 (or similar combinations) from
    the same cabinet.
    """

    _name = "fuel.pump"
    _description = "Fuel Pump"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Pump Name", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    nozzle_ids = fields.One2many("fuel.pump.nozzle", "pump_id", string="Nozzles")
    nozzle_count = fields.Integer(
        string="Nozzle Count",
        compute="_compute_nozzle_count",
        store=True,
    )
    controller_id = fields.Many2one(
        "fuel.forecourt.device",
        string="Forecourt Controller",
        help="The RS-485 aggregator this pump reports through.",
    )
    active = fields.Boolean(default=True)

    @api.depends("nozzle_ids")
    def _compute_nozzle_count(self):
        for pump in self:
            pump.nozzle_count = len(pump.nozzle_ids)
