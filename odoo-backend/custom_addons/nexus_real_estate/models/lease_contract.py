from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class LeaseContract(models.Model):
    _name = "lease.contract"
    _description = "Lease Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_date desc, name desc"

    name = fields.Char(
        string="Contract Reference",
        required=True,
        default=lambda self: _("New"),
        copy=False,
        readonly=True,
    )
    property_id = fields.Many2one(
        "property.asset",
        string="Property",
        required=True,
    )
    unit_id = fields.Many2one(
        "property.unit",
        string="Unit",
        required=True,
        domain="[('property_id', '=', property_id), ('state', '!=', 'occupied')]",
        tracking=True,
    )
    tenant_id = fields.Many2one(
        "res.partner",
        string="Tenant",
        required=True,
        tracking=True,
    )
    start_date = fields.Date(
        string="Start Date",
        required=True,
        tracking=True,
    )
    end_date = fields.Date(
        string="End Date",
        required=True,
        tracking=True,
    )
    rent_amount = fields.Monetary(
        string="Monthly Rent",
        currency_field="currency_id",
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )
    payment_frequency = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semi_annual", "Semi-Annual"),
            ("annual", "Annual"),
        ],
        string="Payment Frequency",
        default="monthly",
        required=True,
    )
    security_deposit = fields.Monetary(
        string="Security Deposit",
        currency_field="currency_id",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("terminated", "Terminated"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    invoice_count = fields.Integer(
        string="Invoice Count",
        compute="_compute_invoice_count",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for contract in self:
            contract.invoice_count = len(contract.invoice_ids)

    invoice_ids = fields.One2many("account.move", "lease_contract_id", string="Invoices")

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for contract in self:
            if contract.end_date <= contract.start_date:
                raise ValidationError(_("End date must be after start date."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("lease.contract") or _("New")
                )
        return super(LeaseContract, self).create(vals_list)

    def action_activate(self):
        self.ensure_one()
        if self.state != "draft":
            raise ValidationError(_("Only draft contracts can be activated."))
        self.unit_id.write({"state": "occupied", "partner_id": self.tenant_id.id})
        self.write({"state": "active"})

    def action_terminate(self):
        self.ensure_one()
        if self.state not in ("draft", "active"):
            raise ValidationError(_("Only active or draft contracts can be terminated."))
        self.unit_id.write({"state": "vacant", "partner_id": False})
        self.write({"state": "terminated"})

    def action_create_invoice(self):
        self.ensure_one()
        journal = self.env["account.journal"].search([("type", "=", "sale")], limit=1)
        if not journal:
            raise ValidationError(_("No sales journal found."))
        income_account = (
            self.tenant_id.property_account_income_id
            or journal.default_account_id
        )
        if not income_account:
            raise ValidationError(_(
                "Set an income account on the tenant or on the sales journal "
                "before creating an invoice."
            ))
        move = self.env["account.move"].create(
            {
                "partner_id": self.tenant_id.id,
                "move_type": "out_invoice",
                "invoice_date": fields.Date.context_today(self),
                "journal_id": journal.id,
                "ref": self.name,
                "lease_contract_id": self.id,
                "company_id": self.company_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": _("Rent for %s") % self.name,
                            "quantity": 1.0,
                            "price_unit": self.rent_amount,
                            "account_id": income_account.id,
                        },
                    )
                ],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.onchange("unit_id")
    def _onchange_unit_id(self):
        if self.unit_id:
            self.rent_amount = self.unit_id.rent_amount


class AccountMove(models.Model):
    _inherit = "account.move"

    lease_contract_id = fields.Many2one("lease.contract", string="Lease Contract", index=True)
