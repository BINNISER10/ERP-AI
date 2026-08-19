"""Extend res.users with tenant linkage and quota hooks."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = "res.users"

    saas_tenant_id = fields.Many2one(
        "nexus.saas.tenant",
        string="SaaS Tenant",
        index=True,
        help="Primary tenant this user belongs to.",
    )
    saas_tenant_ids = fields.Many2many(
        "nexus.saas.tenant",
        "res_users_saas_tenant_rel",
        "user_id",
        "tenant_id",
        string="Allowed Tenants",
        help="For SaaS administrators who can manage multiple tenants.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            tenant_id = vals.get("saas_tenant_id")
            company_id = vals.get("company_id")
            if tenant_id and not company_id:
                tenant = self.env["nexus.saas.tenant"].browse(tenant_id)
                if tenant.primary_company_id:
                    vals["company_id"] = tenant.primary_company_id.id
                    vals.setdefault("company_ids", [(6, 0, [tenant.primary_company_id.id])])
            elif company_id and not tenant_id:
                company = self.env["res.company"].browse(company_id)
                if company.saas_tenant_id:
                    vals["saas_tenant_id"] = company.saas_tenant_id.id
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        # Enforce tenant company membership
        for user in self:
            if user.saas_tenant_id and user.company_id:
                tenant = user.saas_tenant_id
                if user.company_id.saas_tenant_id and user.company_id.saas_tenant_id != tenant:
                    raise UserError(
                        _(
                            "User %(user)s is assigned to tenant %(tenant)s but "
                            "their default company belongs to a different tenant."
                        )
                        % {"user": user.name, "tenant": tenant.name}
                    )
        return res

    @api.constrains("saas_tenant_id", "company_ids")
    def _check_tenant_companies(self):
        for user in self:
            if not user.saas_tenant_id:
                continue
            tenant = user.saas_tenant_id
            for company in user.company_ids:
                if company.saas_tenant_id and company.saas_tenant_id != tenant:
                    raise UserError(
                        _(
                            "User %(user)s cannot be a member of company %(company)s "
                            "because it belongs to tenant %(other_tenant)s."
                        )
                        % {
                            "user": user.name,
                            "company": company.name,
                            "other_tenant": company.saas_tenant_id.name,
                        }
                    )
