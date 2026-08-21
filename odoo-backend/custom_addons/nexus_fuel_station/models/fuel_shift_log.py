from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class FuelShiftLog(models.Model):
    _name = "fuel.shift.log"
    _description = "Fuel Shift Reconciliation Log"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, name desc"

    name = fields.Char(
        string="Shift Reference",
        required=True,
        default=lambda self: _("New"),
        copy=False,
        readonly=True,
    )
    date = fields.Datetime(
        string="Shift Date",
        required=True,
        default=fields.Datetime.now,
    )
    nozzle_id = fields.Many2one(
        "fuel.pump.nozzle",
        string="Nozzle",
        required=True,
        ondelete="restrict",
    )
    pump_id = fields.Many2one(
        "fuel.pump",
        string="Fuel Pump",
        related="nozzle_id.pump_id",
        store=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Attendant",
        default=lambda self: self.env.user,
    )
    source = fields.Selection(
        [("manual", "Manual Entry"), ("forecourt", "Forecourt Controller")],
        string="Source",
        default="manual",
        required=True,
        tracking=True,
    )
    reading_buffer_id = fields.Many2one(
        "fuel.reading.buffer",
        string="Source Reading",
        readonly=True,
        copy=False,
    )
    opening_meter = fields.Float(
        string="Opening Meter",
        digits=(16, 3),
        required=True,
    )
    closing_meter = fields.Float(
        string="Closing Meter",
        digits=(16, 3),
        required=True,
    )
    volume_sold = fields.Float(
        string="Volume Sold (Liters)",
        digits=(16, 3),
        compute="_compute_volume_sold",
        store=True,
    )
    product_id = fields.Many2one(
        "product.product",
        related="nozzle_id.product_id",
        string="Fuel Product",
        store=True,
        readonly=True,
    )
    stock_move_id = fields.Many2one(
        "stock.move",
        string="Stock Move",
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="nozzle_id.company_id",
        store=True,
        readonly=True,
    )

    @api.depends("opening_meter", "closing_meter")
    def _compute_volume_sold(self):
        for log in self:
            log.volume_sold = log.closing_meter - log.opening_meter

    @api.constrains("opening_meter", "closing_meter")
    def _check_meter_consistency(self):
        for log in self:
            if log.closing_meter < log.opening_meter:
                raise ValidationError(
                    _("Closing meter must be greater than or equal to opening meter.")
                )
            if log.volume_sold > log.nozzle_id.tank_id.current_volume:
                raise ValidationError(
                    _(
                        "Volume sold (%(sold)s L) exceeds available tank volume "
                        "(%(available)s L)."
                    )
                    % {
                        "sold": log.volume_sold,
                        "available": log.nozzle_id.tank_id.current_volume,
                    }
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("fuel.shift.log") or _("New")
        return super(FuelShiftLog, self).create(vals_list)

    def action_confirm(self):
        self.ensure_one()
        if self.state == "confirmed":
            raise UserError(_("Shift log is already confirmed."))
        if not self.product_id or not self.nozzle_id.tank_id.location_id:
            raise UserError(_("Missing fuel product or tank location."))

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if not picking_type:
            raise UserError(_("No outgoing operation type configured for this company."))

        src_location = self.nozzle_id.tank_id.location_id
        customer_location = self.env.ref("stock.stock_location_customers")

        move = self.env["stock.move"].create(
            {
                "name": _("Fuel Sale: %s") % self.product_id.display_name,
                "product_id": self.product_id.id,
                "product_uom_qty": self.volume_sold,
                "product_uom": self.product_id.uom_id.id,
                "location_id": src_location.id,
                "location_dest_id": customer_location.id,
                "picking_type_id": picking_type.id,
                "state": "draft",
            }
        )
        move._action_confirm()
        move._action_assign()
        move._action_done()

        self.write({"stock_move_id": move.id, "state": "confirmed"})

        # Update tank volume
        tank = self.nozzle_id.tank_id
        tank.write({"current_volume": tank.current_volume - self.volume_sold})

        # Update nozzle ending meter
        self.nozzle_id.write({"meter_end": self.closing_meter})

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.stock_move_id and self.stock_move_id.state == "done":
            raise UserError(_("Cannot reset a confirmed shift with a done stock move."))
        self.write({"state": "draft"})
