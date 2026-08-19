# Nexus SaaS Tenant — multi-tenant foundation for Nexus ERP.
import logging
import os

from odoo import api, SUPERUSER_ID

from . import controllers, models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Seed SaaS settings from environment variables if present."""
    mapping = {
        "nexus_saas.base_domain": os.environ.get("SAAS_BASE_DOMAIN", ""),
        "nexus_saas.self_service_signup": os.environ.get("SAAS_SELF_SERVICE_SIGNUP", "false").lower() in ("true", "1", "yes"),
        "nexus_saas.cloudflare_api_token": os.environ.get("CLOUDFLARE_API_TOKEN", ""),
        "nexus_saas.cloudflare_zone_id": os.environ.get("CLOUDFLARE_ZONE_ID", ""),
        "nexus_saas.cloudflare_cname_target": os.environ.get("CLOUDFLARE_CNAME_TARGET", ""),
        "nexus_saas_billing.stripe_secret_key": os.environ.get("STRIPE_SECRET_KEY", ""),
        "nexus_saas_billing.stripe_publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY", ""),
        "nexus_saas_billing.stripe_webhook_secret": os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
    }
    icp = env["ir.config_parameter"].sudo()
    for key, value in mapping.items():
        if value:
            icp.set_param(key, value)
            _logger.info("Set config parameter %s from environment.", key)


def _post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    post_init_hook(env)
