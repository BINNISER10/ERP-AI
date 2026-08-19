"""Stripe integration for Nexus SaaS subscriptions."""
import logging
from datetime import datetime as dt

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _get_stripe_api():
    try:
        import stripe
    except ImportError as exc:
        raise UserError(_("Stripe Python library is not installed. Run: pip install stripe")) from exc
    return stripe


class SaaSSubscription(models.Model):
    _inherit = "nexus.saas.subscription"

    stripe_checkout_url = fields.Char(string="Stripe Checkout URL", readonly=True)
    last_stripe_event = fields.Char(string="Last Stripe Event Type", readonly=True)
    last_stripe_event_at = fields.Datetime(string="Last Stripe Event At", readonly=True)

    def _get_stripe_secret(self):
        self.ensure_one()
        key = self.env["ir.config_parameter"].sudo().get_param("nexus_saas_billing.stripe_secret_key", "")
        if not key:
            raise UserError(_("Stripe secret key is not configured."))
        return key

    def action_create_stripe_checkout(self):
        """Create a Stripe Checkout session for this subscription and redirect the user."""
        self.ensure_one()
        stripe = _get_stripe_api()
        stripe.api_key = self._get_stripe_secret()

        tenant = self.tenant_id
        plan = self.plan_id

        price_id = (
            plan.stripe_price_id_yearly
            if self.billing_interval == "year" and plan.stripe_price_id_yearly
            else plan.stripe_price_id_monthly
        )
        if not price_id:
            raise UserError(_("Plan '%s' does not have a Stripe price ID for interval '%s'.") % (plan.name, self.billing_interval))

        # Create or reuse Stripe customer
        if not tenant.stripe_customer_id:
            customer = stripe.Customer.create(
                email=tenant.email,
                name=tenant.name,
                metadata={"tenant_code": tenant.code, "tenant_id": str(tenant.id)},
            )
            tenant.sudo().write({"stripe_customer_id": customer.id})

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        success_url = f"{base_url}/saas/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/saas/subscription/cancel"

        session = stripe.checkout.Session.create(
            customer=tenant.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={"metadata": {"nexus_subscription_id": str(self.id)}},
            metadata={"nexus_subscription_id": str(self.id), "tenant_code": tenant.code},
        )
        self.write({"stripe_checkout_url": session.url})
        return {
            "type": "ir.actions.act_url",
            "url": session.url,
            "target": "new",
        }

    @api.model
    def sync_from_stripe(self, subscription_id):
        """Pull the latest status from Stripe for a subscription."""
        stripe = _get_stripe_api()
        stripe.api_key = self.env["ir.config_parameter"].sudo().get_param("nexus_saas_billing.stripe_secret_key", "")
        if not stripe.api_key:
            _logger.error("Stripe secret key missing; cannot sync subscription %s", subscription_id)
            return False
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
        except Exception:
            _logger.exception("Failed to retrieve Stripe subscription %s", subscription_id)
            return False

        local = self.search([("stripe_subscription_id", "=", subscription_id)], limit=1)
        if not local:
            _logger.warning("No local subscription for Stripe ID %s", subscription_id)
            return False

        status = sub.get("status", "")
        state_map = {
            "trialing": "trialing",
            "active": "active",
            "past_due": "past_due",
            "canceled": "cancelled",
            "unpaid": "past_due",
            "incomplete": "trialing",
            "incomplete_expired": "cancelled",
        }
        def _ts_to_date(ts):
            return fields.Date.to_date(dt.utcfromtimestamp(ts)) if ts else False

        vals = {
            "state": state_map.get(status, local.state),
            "current_period_start": _ts_to_date(sub.get("current_period_start")),
            "current_period_end": _ts_to_date(sub.get("current_period_end")),
        }
        local.write(vals)
        if vals["state"] in ("past_due", "cancelled"):
            local.tenant_id.action_suspend()
        return True

    @api.model
    def _cron_sync_stripe_subscriptions(self):
        """Sync all active subscriptions with Stripe once per day."""
        records = self.search([("stripe_subscription_id", "!=", False)])
        for rec in records:
            rec.sync_from_stripe(rec.stripe_subscription_id)
