from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectCostSheet(models.Model):
    _name = "project.cost.sheet"
    _description = "Project Cost Sheet (Percentage of Completion)"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Cost Sheet Name", required=True)
    contract_id = fields.Many2one(
        "project.contract",
        string="Contract",
        required=True,
        ondelete="cascade",
    )
    project_id = fields.Many2one(
        "project.project",
        related="contract_id.project_id",
        string="Project",
        store=True,
        readonly=True,
    )
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    percentage = fields.Float(
        string="Completion %",
        digits=(5, 2),
        required=True,
        help="Percentage of project completion for this period.",
    )
    cost = fields.Monetary(
        string="Cost Incurred",
        currency_field="currency_id",
        required=True,
    )
    revenue = fields.Monetary(
        string="Revenue Recognized",
        currency_field="currency_id",
        compute="_compute_revenue",
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="contract_id.currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )
    description = fields.Text(string="Description")
    company_id = fields.Many2one(
        "res.company",
        related="contract_id.company_id",
        string="Company",
        store=True,
        readonly=True,
    )

    @api.constrains("percentage", "cost")
    def _check_positive_values(self):
        for sheet in self:
            if sheet.percentage < 0 or sheet.percentage > 100:
                raise ValidationError(_("Completion percentage must be between 0 and 100."))
            if sheet.cost < 0:
                raise ValidationError(_("Cost cannot be negative."))

    @api.depends("percentage", "cost", "contract_id.contract_value")
    def _compute_revenue(self):
        for sheet in self:
            if sheet.contract_id:
                sheet.revenue = sheet.contract_id.contract_value * (sheet.percentage / 100.0)
            else:
                sheet.revenue = 0.0
