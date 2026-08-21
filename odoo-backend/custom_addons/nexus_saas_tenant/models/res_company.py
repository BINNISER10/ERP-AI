"""Extend res.company with tenant linkage."""
from odoo import api, fields, models


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

    @api.model_create_multi
    def create(self, vals_list):
        skip_quota = self.env.context.get("skip_saas_quota_check")
        pending_by_tenant = {}
        for vals in vals_list:
            tenant_id = vals.get("saas_tenant_id")
            if tenant_id and not skip_quota:
                tenant = self.env["nexus.saas.tenant"].browse(tenant_id)
                extra = pending_by_tenant.get(tenant.id, 0)
                tenant.check_company_quota(extra=extra)
                pending_by_tenant[tenant.id] = extra + 1
        return super().create(vals_list)
