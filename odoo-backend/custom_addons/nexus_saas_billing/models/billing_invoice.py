"""Internal billing invoices generated for SaaS subscriptions.

These are *not* sent to Stripe; they are the tenant's record of what they owe
or have paid, optionally synced from Stripe invoices.
"""
from odoo import api, fields, models, _


class SaaSBillingInvoice(models.Model):
    _name = "nexus.saas.billing.invoice"
    _description = "SaaS Billing Invoice"
    _order = "invoice_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    tenant_id = fields.Many2one(
        "nexus.saas.tenant",
        required=True,
        index=True,
        ondelete="cascade",
    )
    subscription_id = fields.Many2one(
        "nexus.saas.subscription",
        string="Subscription",
    )

    name = fields.Char(
        string="Invoice Number",
        required=True,
        default=lambda self: _("New"),
    )
    invoice_date = fields.Date(
        required=True,
        default=fields.Date.today,
    )
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    amount_total = fields.Monetary(
        currency_field="currency_id",
        required=True,
    )
    amount_paid = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
    )
    amount_due = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_amount_due",
        store=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("paid", "Paid"),
            ("overdue", "Overdue"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )

    stripe_invoice_id = fields.Char(string="Stripe Invoice ID")
    stripe_invoice_url = fields.Char(string="Stripe Invoice URL")

    @api.depends("amount_total", "amount_paid")
    def _compute_amount_due(self):
        for inv in self:
            inv.amount_due = inv.amount_total - inv.amount_paid

    def action_post(self):
        self.write({"state": "posted"})

    def action_mark_paid(self):
        self.write({"state": "paid", "amount_paid": self.amount_total})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    @api.model
    def generate_for_period(self, subscription, period_end):
        """Generate a draft billing invoice for the subscription period."""
        plan = subscription.plan_id
        amount = plan.price_yearly if subscription.billing_interval == "year" else plan.price_monthly
        period_start = fields.Date.subtract(period_end, months=12 if subscription.billing_interval == "year" else 1, day=1)
        existing = self.search([
            ("subscription_id", "=", subscription.id),
            ("period_end", "=", period_end),
        ], limit=1)
        if existing:
            return existing
        return self.create({
            "tenant_id": subscription.tenant_id.id,
            "subscription_id": subscription.id,
            "invoice_date": fields.Date.today(),
            "period_start": period_start,
            "period_end": period_end,
            "amount_total": amount,
            "currency_id": plan.currency_id.id,
        })
