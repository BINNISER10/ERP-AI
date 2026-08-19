"""Extend res.company with tenant linkage."""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    saas_tenant_id = fields.Many2one(
        "nexus.saas.tenant",
        string="SaaS Tenant",
        index=True,
        help="The tenant that owns this company.",
    )
    is_saas_tenant_root = fields.Boolean(
        string="Tenant Root Company",
        help="Marked automatically when a tenant is provisioned.",
    )
