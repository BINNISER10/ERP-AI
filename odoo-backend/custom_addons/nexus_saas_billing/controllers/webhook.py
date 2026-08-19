"""Stripe webhook handlers for SaaS billing events."""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class StripeWebhookController(http.Controller):
    _ROUTE = "/saas/billing/stripe/webhook"

    @http.route(_ROUTE, type="json", auth="none", methods=["POST"], csrf=False, sitemap=False)
    def webhook(self):
        """Receive Stripe webhooks and update subscriptions/invoices."""
        stripe = self._get_stripe()
        payload = request.httprequest.data
        sig_header = request.httprequest.headers.get("Stripe-Signature", "")
        secret = request.env["ir.config_parameter"].sudo().get_param(
            "nexus_saas_billing.stripe_webhook_secret", ""
        )

        if not secret:
            _logger.error("Stripe webhook secret is not configured; rejecting event.")
            return {"status": "rejected", "reason": "webhook secret not configured"}

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        except ValueError:
            _logger.warning("Stripe webhook: invalid payload.")
            return {"status": "rejected", "reason": "invalid payload"}
        except stripe.error.SignatureVerificationError:
            _logger.warning("Stripe webhook: invalid signature.")
            return {"status": "rejected", "reason": "invalid signature"}

        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        _logger.info("Stripe webhook received: %s", event_type)

        subscription_env = request.env["nexus.saas.subscription"].sudo()
        invoice_env = request.env["nexus.saas.billing.invoice"].sudo()

        if event_type == "checkout.session.completed":
            sub_id = data.get("subscription")
            metadata = data.get("metadata", {})
            local_sub_id = metadata.get("nexus_subscription_id")
            if local_sub_id and sub_id:
                local = subscription_env.browse(int(local_sub_id))
                if local.exists():
                    local.write({
                        "stripe_subscription_id": sub_id,
                        "state": "active",
                        "last_stripe_event": event_type,
                        "last_stripe_event_at": request.env.cr.now(),
                    })

        elif event_type in ("invoice.paid", "invoice.payment_succeeded"):
            sub_id = data.get("subscription")
            local = subscription_env.search([("stripe_subscription_id", "=", sub_id)], limit=1)
            if local.exists():
                local.write({
                    "state": "active",
                    "last_stripe_event": event_type,
                    "last_stripe_event_at": request.env.cr.now(),
                })
                local.tenant_id.action_activate()
                # Optionally create a paid billing invoice record
                invoice_env.create({
                    "tenant_id": local.tenant_id.id,
                    "subscription_id": local.id,
                    "invoice_date": request.env.cr.now(),
                    "period_start": local.current_period_start,
                    "period_end": local.current_period_end,
                    "amount_total": (data.get("amount_due", 0) or 0) / 100.0,
                    "amount_paid": (data.get("amount_paid", 0) or 0) / 100.0,
                    "state": "paid",
                    "currency_id": request.env["res.currency"].search([
                        ("name", "=", (data.get("currency") or "USD").upper())
                    ], limit=1).id or request.env.company.currency_id.id,
                    "stripe_invoice_id": data.get("id"),
                    "stripe_invoice_url": data.get("hosted_invoice_url"),
                })

        elif event_type in ("invoice.payment_failed", "customer.subscription.past_due"):
            sub_id = data.get("id") or data.get("subscription")
            local = subscription_env.search([("stripe_subscription_id", "=", sub_id)], limit=1)
            if local.exists():
                local.write({
                    "state": "past_due",
                    "last_stripe_event": event_type,
                    "last_stripe_event_at": request.env.cr.now(),
                })
                local.tenant_id.action_suspend()

        elif event_type == "customer.subscription.deleted":
            sub_id = data.get("id")
            local = subscription_env.search([("stripe_subscription_id", "=", sub_id)], limit=1)
            if local.exists():
                local.action_cancel()

        return {"status": "ok"}

    def _get_stripe(self):
        try:
            import stripe
        except ImportError as exc:
            _logger.error("Stripe library is not installed: %s", exc)
            raise
        return stripe
