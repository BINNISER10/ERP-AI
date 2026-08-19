"""ERPNext-style Budget + Budget Account doctypes.

A budget is set for a fiscal year, against a cost center or a project.
Each budget account carries a monthly/annual budget amount.  The engine
compares posted GL entries (debit minus credit on expense accounts)
against the budget and reports the variance.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class NexusBudget(models.Model):
    _name = "nexus.budget"
    _description = "Nexus Financial Budget"
    _order = "id desc"

    name = fields.Char(string="Budget Name", required=True)
    budget_against = fields.Selection(
        [
            ("cost_center", "Cost Center"),
            ("project", "Project"),
        ],
        string="Budget Against",
        required=True,
        default="cost_center",
        help="What this budget is allocated against (like ERPNext).",
    )
    cost_center_id = fields.Many2one(
        "nexus.cost.center",
        string="Cost Center",
        ondelete="restrict",
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        ondelete="restrict",
    )
    fiscal_year_id = fields.Many2one(
        "nexus.fiscal.year",
        string="Fiscal Year",
        required=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    action_if_budget_exceeded = fields.Selection(
        [
            ("stop", "Stop"),
            ("warn", "Warn"),
            ("ignore", "Ignore"),
        ],
        string="Action if Annual Budget Exceeded",
        default="warn",
        help="Like ERPNext's action_if_annual_budget_exceeded.",
    )
    action_if_accumulated_exceeded = fields.Selection(
        [
            ("stop", "Stop"),
            ("warn", "Warn"),
            ("ignore", "Ignore"),
        ],
        string="Action if Accumulated Monthly Budget Exceeded",
        default="ignore",
    )
    account_ids = fields.One2many(
        "nexus.budget.account",
        "budget_id",
        string="Budget Accounts",
    )
    total_budget = fields.Monetary(
        string="Total Budget",
        compute="_compute_totals",
        currency_field="company_currency_id",
        store=True,
    )
    total_actual = fields.Monetary(
        string="Actual",
        compute="_compute_actuals",
        currency_field="company_currency_id",
    )
    total_variance = fields.Monetary(
        string="Variance",
        compute="_compute_actuals",
        currency_field="company_currency_id",
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("cancelled", "Cancelled")],
        string="Status",
        default="draft",
    )

    @api.constrains("budget_against", "cost_center_id", "project_id")
    def _check_budget_against(self):
        for record in self:
            if record.budget_against == "cost_center" and not record.cost_center_id:
                raise models.ValidationError(_("Select a cost center for this budget."))
            if record.budget_against == "project" and not record.project_id:
                raise models.ValidationError(_("Select a project for this budget."))

    @api.depends("account_ids.budget_amount")
    def _compute_totals(self):
        for record in self:
            record.total_budget = sum(record.account_ids.mapped("budget_amount"))

    @api.depends(
        "account_ids.budget_amount",
        "fiscal_year_id",
        "cost_center_id",
        "project_id",
    )
    def _compute_actuals(self):
        gl_model = self.env["nexus.gl.entry"]
        for record in self:
            if not record.fiscal_year_id:
                record.total_actual = 0.0
                record.total_variance = 0.0
                continue
            total = 0.0
            for ba in record.account_ids:
                domain = [
                    ("account_id", "=", ba.account_id.id),
                    ("is_cancelled", "=", False),
                    ("fiscal_year_id", "=", record.fiscal_year_id.id),
                ]
                if record.budget_against == "cost_center" and record.cost_center_id:
                    domain.append(("cost_center_id", "=", record.cost_center_id.id))
                elif record.budget_against == "project" and record.project_id:
                    domain.append(("project_id", "=", record.project_id.id))
                gls = gl_model.search(domain)
                total += sum(gls.mapped("debit")) - sum(gls.mapped("credit"))
            record.total_actual = total
            record.total_variance = record.total_budget - total

    def action_activate(self):
        for record in self:
            record.write({"state": "active"})
        return True

    def action_cancel(self):
        for record in self:
            record.write({"state": "cancelled"})
        return True

    def action_set_draft(self):
        for record in self:
            record.write({"state": "draft"})
        return True


class NexusBudgetAccount(models.Model):
    _name = "nexus.budget.account"
    _description = "Nexus Financial Budget Account"

    budget_id = fields.Many2one(
        "nexus.budget",
        string="Budget",
        required=True,
        ondelete="cascade",
        index=True,
    )
    account_id = fields.Many2one(
        "nexus.account",
        string="Account",
        required=True,
        ondelete="restrict",
    )
    budget_amount = fields.Monetary(
        string="Budget Amount",
        currency_field="company_currency_id",
        required=True,
        default=0.0,
    )
    company_id = fields.Many2one(
        "res.company",
        related="budget_id.company_id",
        store=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
