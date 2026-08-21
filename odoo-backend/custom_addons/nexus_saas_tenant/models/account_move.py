"""Enforce per-tenant monthly invoice quota at posting time.

Enforcing on ``_post`` rather than ``create`` matches the metric being
measured (``fuel/_count_invoices_this_month`` counts *posted*
out_invoice moves for the current month) — an unbounded number of
drafts can exist, but posting is what consumes the quota.
"""
from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        if not self.env.context.get("skip_saas_quota_check"):
            pending_by_tenant = {}
            for move in self:
                if move.move_type != "out_invoice":
                    continue
                tenant = move.company_id.saas_tenant_id
                if tenant:
                    extra = pending_by_tenant.get(tenant.id, 0)
                    tenant.check_invoice_quota(extra=extra)
                    pending_by_tenant[tenant.id] = extra + 1
        return super()._post(soft=soft)
