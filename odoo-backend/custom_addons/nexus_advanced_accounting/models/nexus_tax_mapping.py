"""Pillar 4 — ZATCA / VAT Compliance Matrix.

Links Nexus Command Center taxes (account.tax) to the exact
Item Tax Template in the Nexus Core.  Every invoice line payload
then includes the correct ``item_tax_template`` key so that the Core's
Tax Engine and VAT Returns are ZATCA Phase 2 ready.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NexusTaxMapping(models.Model):
    _name = "nexus.tax.mapping"
    _description = "Nexus Core Tax Template Mapping"
    _rec_name = "display_name"
    _order = "company_id, odoo_tax_id"

    odoo_tax_id = fields.Many2one(
        "account.tax",
        string="Command Center Tax",
        required=True,
        ondelete="restrict",
        domain="[('type_tax_use', 'in', ('sale', 'purchase', 'none', 'adjustment'))]",
        index=True,
    )
    nexus_tax_template = fields.Char(
        string="Nexus Core Item Tax Template",
        required=True,
        help="Exact name of the Item Tax Template in the Nexus Core.",
    )
    nexus_tax_code = fields.Char(
        string="Nexus Core Tax Code",
        help="e.g. VAT-15, GST-5, SR-5.",
    )
    nexus_tax_rate = fields.Float(
        string="Tax Rate (%)",
        digits=(5, 2),
    )
    active = fields.Boolean(
        default=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("odoo_tax_id.name", "nexus_tax_template")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.odoo_tax_id.name or '?'} → {rec.nexus_tax_template}"
                if rec.nexus_tax_template
                else rec.odoo_tax_id.name or "?"
            )

    _sql_constraints = [
        (
            "tax_company_uniq",
            "unique(odoo_tax_id, company_id)",
            "Nexus Core: each Command Center tax can only be mapped once per company.",
        ),
    ]

    def action_sync_tax_template(self):
        """Queue creation of the Item Tax Template in the Nexus Core."""
        self.ensure_one()
        tx_id = f"NX-TAX-{self.odoo_tax_id.id}-{self.company_id.id}"
        self.env["nexus.sync.queue"].enqueue(
            operation="tax_template.create",
            payload={},
            endpoint="/api/resource/Item Tax Template",
            company=self.company_id,
            model_name="account.tax",
            res_id=self.odoo_tax_id.id,
            transaction_id=tx_id,
            priority=25,
        )
        _logger.info(
            "Nexus Core: queued Item Tax Template '%s' → '%s' [%s]",
            self.odoo_tax_id.name,
            self.nexus_tax_template,
            tx_id[:12],
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Nexus Core"),
                "message": _(
                    "Tax template '%s' queued for creation in the Nexus Core."
                )
                % self.nexus_tax_template,
                "type": "success",
            },
        }

    @api.model
    def _get_map_for_company(self, company):
        """Return a dict mapping odoo_tax_id → nexus.tax.mapping record for a company."""
        company_id = company.id if hasattr(company, "id") else int(company)
        mappings = self.sudo().search(
            [("company_id", "=", company_id), ("active", "=", True)]
        )
        return {m.odoo_tax_id.id: m for m in mappings}
