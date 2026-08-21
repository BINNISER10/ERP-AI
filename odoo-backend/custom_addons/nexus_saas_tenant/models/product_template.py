"""Enforce per-tenant product quota on creation."""
from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        skip_quota = self.env.context.get("skip_saas_quota_check")
        pending_by_tenant = {}
        for vals in vals_list:
            company_id = vals.get("company_id")
            if not company_id or skip_quota:
                continue
            company = self.env["res.company"].browse(company_id)
            tenant = company.saas_tenant_id
            if tenant:
                extra = pending_by_tenant.get(tenant.id, 0)
                tenant.check_product_quota(extra=extra)
                pending_by_tenant[tenant.id] = extra + 1
        return super().create(vals_list)
