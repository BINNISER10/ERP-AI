"""SaaS pricing plans and feature/quotas definitions."""
from odoo import api, fields, models, _


class SaaSPlan(models.Model):
    _name = "nexus.saas.plan"
    _description = "SaaS Pricing Plan"
    _order = "sequence, id"

    name = fields.Char(string="Plan Name", required=True, translate=True)
    code = fields.Char(
        string="Plan Code",
        required=True,
        copy=False,
        help="Unique technical code used in Stripe and API calls.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(
        string="Default Plan",
        help="New signups are assigned to this plan unless another is chosen.",
    )

    # Pricing
    price_monthly = fields.Monetary(
        string="Monthly Price",
        currency_field="currency_id",
        default=0.0,
    )
    price_yearly = fields.Monetary(
        string="Yearly Price",
        currency_field="currency_id",
        default=0.0,
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    trial_days = fields.Integer(string="Trial Days", default=14)

    # Quotas (soft / hard)
    max_users = fields.Integer(string="Max Users", default=5, help="0 = unlimited")
    max_companies = fields.Integer(string="Max Companies", default=1, help="0 = unlimited")
    max_products = fields.Integer(string="Max Products", default=1000, help="0 = unlimited")
    max_invoices_monthly = fields.Integer(string="Max Invoices / Month", default=500, help="0 = unlimited")
    storage_gb = fields.Integer(string="Storage GB", default=10, help="0 = unlimited")
    max_api_calls_daily = fields.Integer(string="Max API Calls / Day", default=1000, help="0 = unlimited")

    # Feature flags
    has_ai_copilot = fields.Boolean(string="AI Copilot", default=False)
    has_advanced_accounting = fields.Boolean(string="Advanced Accounting", default=False)
    has_multi_location = fields.Boolean(string="Multi Location", default=False)
    has_priority_support = fields.Boolean(string="Priority Support", default=False)
    has_white_label = fields.Boolean(string="White-Label", default=False)

    stripe_price_id_monthly = fields.Char(string="Stripe Monthly Price ID")
    stripe_price_id_yearly = fields.Char(string="Stripe Yearly Price ID")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Plan code must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Ensure only one default plan
        for rec in records:
            if rec.is_default:
                self.search([("id", "!=", rec.id), ("is_default", "=", True)]).write(
                    {"is_default": False}
                )
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get("is_default"):
            self.search([("id", "not in", self.ids), ("is_default", "=", True)]).write(
                {"is_default": False}
            )
        return res
