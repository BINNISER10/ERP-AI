"""Tenant subscriptions and lifecycle (billing integration lives in nexus_saas_billing)."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaaSSubscription(models.Model):
    _name = "nexus.saas.subscription"
    _description = "SaaS Subscription"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    tenant_id = fields.Many2one(
        "nexus.saas.tenant",
        string="Tenant",
        required=True,
        index=True,
        ondelete="cascade",
    )
    plan_id = fields.Many2one(
        "nexus.saas.plan",
        string="Plan",
        required=True,
    )

    state = fields.Selection(
        [
            ("trialing", "Trialing"),
            ("active", "Active"),
            ("past_due", "Past Due"),
            ("cancelled", "Cancelled"),
        ],
        default="trialing",
        required=True,
        tracking=True,
    )
    billing_interval = fields.Selection(
        [("month", "Monthly"), ("year", "Yearly")],
        default="month",
        required=True,
    )

    trial_end = fields.Date(string="Trial End")
    current_period_start = fields.Date()
    current_period_end = fields.Date()
    cancelled_at = fields.Datetime()

    # Stripe linkage (populated by nexus_saas_billing)
    stripe_customer_id = fields.Char()
    stripe_subscription_id = fields.Char()
    stripe_price_id = fields.Char()

    is_paid = fields.Boolean(
        string="Paid This Period",
        compute="_compute_is_paid",
        store=True,
        help="Set by billing webhooks or manual admin confirmation.",
    )

    @api.depends("state", "trial_end", "current_period_end")
    def _compute_is_paid(self):
        today = fields.Date.today()
        for sub in self:
            if sub.state == "cancelled":
                sub.is_paid = False
                continue
            if sub.state == "trialing" and sub.trial_end and sub.trial_end >= today:
                sub.is_paid = True
                continue
            if sub.state == "active" and sub.current_period_end and sub.current_period_end >= today:
                sub.is_paid = True
                continue
            sub.is_paid = False

    @api.model
    def _cron_check_subscriptions(self):
        """Suspend tenants with unpaid/cancelled subscriptions past grace period."""
        today = fields.Date.today()
        overdue = self.search([
            ("state", "in", ["past_due", "cancelled"]),
            ("current_period_end", "<", today),
        ])
        for sub in overdue:
            if sub.tenant_id.state != "cancelled":
                sub.tenant_id.action_suspend()
                sub.message_post(body=_("Subscription overdue — tenant suspended."))

    @api.model
    def _cron_trial_expiry(self):
        """Convert trials to active or past_due when trial ends."""
        today = fields.Date.today()
        trials = self.search([
            ("state", "=", "trialing"),
            ("trial_end", "<=", today),
        ])
        for sub in trials:
            if sub.stripe_subscription_id:
                sub.write({"state": "active"})
            else:
                sub.write({"state": "past_due"})
                sub.tenant_id.action_suspend()

    def action_cancel(self):
        for sub in self:
            sub.write({"state": "cancelled", "cancelled_at": fields.Datetime.now()})
            sub.tenant_id.action_cancel()
