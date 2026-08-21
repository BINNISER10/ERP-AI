"""Extend res.config.settings with SaaS platform options."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    saas_base_domain = fields.Char(
        string="SaaS Base Domain",
        config_parameter="nexus_saas.base_domain",
        help="e.g. nexus-engine.app — new tenants get <code>.nexus-engine.app",
    )
    saas_self_service_signup = fields.Boolean(
        string="Self-Service Signup",
        config_parameter="nexus_saas.self_service_signup",
        help="Allow public signup without admin approval.",
    )
    saas_cloudflare_api_token = fields.Char(
        string="Cloudflare API Token",
        config_parameter="nexus_saas.cloudflare_api_token",
        password=True,
        help="Cloudflare API token with Zone:Read and DNS:Edit permissions.",
    )
    saas_cloudflare_zone_id = fields.Char(
        string="Cloudflare Zone ID",
        config_parameter="nexus_saas.cloudflare_zone_id",
        help="Optional. If empty, the zone is discovered from the base domain.",
    )
    saas_cloudflare_cname_target = fields.Char(
        string="Cloudflare CNAME Target",
        config_parameter="nexus_saas.cloudflare_cname_target",
        help="Target hostname for tenant subdomains/custom domains, e.g. app.nexus-engine.app",
    )
    saas_db_provisioner_api_key = fields.Char(
        string="DB Provisioner API Key",
        config_parameter="nexus_saas.db_provisioner_api_key",
        password=True,
        help="Shared secret the external saas-db-provisioner service sends "
        "in the 'X-Provisioner-Api-Key' header when polling for pending "
        "jobs and reporting results.",
    )
    saas_dedicated_db_default_modules = fields.Char(
        string="Dedicated DB Default Modules",
        config_parameter="nexus_saas.dedicated_db_default_modules",
        default="base,nexus_base_security,nexus_saas_tenant",
        help="Comma-separated module list installed on every newly "
        "provisioned dedicated tenant database.",
    )
