import secrets

from odoo import models, fields, api, _


class FuelForecourtDevice(models.Model):
    """A registered Forecourt Controller (RS-485 aggregator).

    Per the Ocean Seven fuel-automation technical study, all 11 pumps /
    23 nozzles are wired via RS-485 into a single central Forecourt
    Controller, which then relays normalized readings to Odoo over a
    standard Ethernet/TCP-IP link using a JSON push (see
    ``controllers/forecourt_gateway.py``).

    Each device authenticates with a static API key (machine-to-machine,
    no interactive user session) scoped to one company.
    """

    _name = "fuel.forecourt.device"
    _description = "Fuel Forecourt Controller"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Device Name", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    protocol = fields.Selection(
        [("lanfeng_rs485", "Lanfeng RS-485")],
        string="Field Protocol",
        default="lanfeng_rs485",
        required=True,
    )
    api_key = fields.Char(
        string="API Key",
        required=True,
        copy=False,
        default=lambda self: self._generate_api_key(),
        groups="base.group_system",
        help="Shared secret sent by the controller in the "
        "'X-Forecourt-Api-Key' header of every push request.",
    )
    pump_ids = fields.One2many("fuel.pump", "controller_id", string="Pumps")
    last_seen = fields.Datetime(string="Last Contact", readonly=True, copy=False)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("api_key_uniq", "unique(api_key)", "API Key must be unique."),
    ]

    @api.model
    def _generate_api_key(self):
        return secrets.token_urlsafe(32)

    def action_rotate_api_key(self):
        for device in self:
            device.api_key = self._generate_api_key()

    @api.model
    def _authenticate(self, api_key):
        """Return the ``fuel.forecourt.device`` matching an incoming API key.

        Raises no exception; the caller decides how to respond. Runs as
        sudo since the caller has no user session at all.
        """
        if not api_key:
            return self.env["fuel.forecourt.device"]
        device = self.sudo().search([("api_key", "=", api_key), ("active", "=", True)], limit=1)
        if device:
            device.sudo().write({"last_seen": fields.Datetime.now()})
        return device
