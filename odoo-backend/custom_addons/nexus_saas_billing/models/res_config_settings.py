"""Extend res.config.settings with Stripe billing options."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    saas_stripe_publishable_key = fields.Char(
        string="Stripe Publishable Key",
        config_parameter="nexus_saas_billing.stripe_publishable_key",
    )
    saas_stripe_secret_key = fields.Char(
        string="Stripe Secret Key",
        config_parameter="nexus_saas_billing.stripe_secret_key",
    )
    saas_stripe_webhook_secret = fields.Char(
        string="Stripe Webhook Secret",
        config_parameter="nexus_saas_billing.stripe_webhook_secret",
        help="Used to verify Stripe webhook signatures.",
    )
