from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectContract(models.Model):
    _name = "project.contract"
    _description = "Construction Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Contract Reference", required=True, default=lambda self: _("New"), readonly=True, copy=False)
    partner_id = fields.Many2one("res.partner", string="Customer", required=True, tracking=True)
    project_id = fields.Many2one("project.project", string="Project", tracking=True)
    contract_value = fields.Monetary(string="Contract Value", currency_field="currency_id", required=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("invoiced", "Invoiced"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    completion_percentage = fields.Float(
        string="Completion %",
        digits=(5, 2),
        compute="_compute_completion",
        store=True,
    )
    cost_sheet_ids = fields.One2many("project.cost.sheet", "contract_id", string="Cost Sheets")
    total_cost = fields.Monetary(
        string="Total Cost",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    total_revenue = fields.Monetary(
        string="Recognized Revenue",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for contract in self:
            if contract.end_date <= contract.start_date:
                raise ValidationError(_("End date must be after the start date."))

    @api.depends("cost_sheet_ids.percentage", "cost_sheet_ids.cost", "cost_sheet_ids.revenue")
    def _compute_completion(self):
        for contract in self:
            sheets = contract.cost_sheet_ids
            total_completion = sum(s.percentage for s in sheets) / len(sheets) if sheets else 0.0
            contract.completion_percentage = min(total_completion, 100.0)

    @api.depends("cost_sheet_ids.cost", "cost_sheet_ids.revenue")
    def _compute_totals(self):
        for contract in self:
            contract.total_cost = sum(s.cost for s in contract.cost_sheet_ids)
            contract.total_revenue = sum(s.revenue for s in contract.cost_sheet_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("project.contract") or _("New")
        return super(ProjectContract, self).create(vals_list)

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_complete(self):
        self.write({"state": "completed"})

    def action_create_progress_invoice(self):
        self.ensure_one()
        if not self.cost_sheet_ids:
            raise ValidationError(_("No cost sheets defined for this contract."))
        if self.completion_percentage <= 0:
            raise ValidationError(_("Completion percentage must be greater than 0 to invoice."))

        invoice_amount = self.contract_value * (self.completion_percentage / 100.0)
        move = self.env["account.move"].create(
            {
                "partner_id": self.partner_id.id,
                "move_type": "out_invoice",
                "invoice_date": fields.Date.context_today(self),
                "company_id": self.company_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": _("Progress Invoice: %s") % self.name,
                            "quantity": 1.0,
                            "price_unit": invoice_amount,
                        },
                    )
                ],
            }
        )
        self.write({"state": "invoiced"})
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "target": "current",
        }
