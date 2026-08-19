"""Hybrid ERP Sync configuration model."""
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class HybridConfig(models.Model):
    """Stores hybrid ledger and n8n connection settings shared across hybrid modules."""

    _name = "hybrid.config"
    _description = "Hybrid ERP Sync Configuration"
    _rec_name = "name"
    _order = "id desc"

    name = fields.Char(
        related="company_id.name",
        store=True,
        readonly=True,
        string="Configuration Name",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Company that this hybrid configuration belongs to.",
    )
    active = fields.Boolean(default=True, help="Enable or disable this configuration.")

    erpnext_url = fields.Char(
        string="Hybrid Ledger Base URL",
        help="Base URL of the hybrid ledger instance.",
    )
    erpnext_api_key = fields.Char(
        string="Hybrid Ledger API Key",
        help="Hybrid ledger API key for token-based authentication.",
        password=True,
    )
    erpnext_api_secret = fields.Char(
        string="Hybrid Ledger API Secret",
        help="Hybrid ledger API secret for token-based authentication.",
        password=True,
    )

    n8n_url = fields.Char(
        string="n8n Base URL",
        help="Base URL of the n8n automation server.",
    )
    n8n_webhook_key = fields.Char(
        string="n8n Webhook Key / Token",
        help="Optional bearer token used by n8n webhooks.",
        password=True,
    )

    _sql_constraints = [
        (
            "company_uniq",
            "unique(company_id)",
            "Only one hybrid configuration is allowed per company.",
        ),
    ]

    @api.model
    def get_active_config(self, company=None):
        """Return the active hybrid configuration for the given company.

        :param company: Optional res.company record or integer ID.
        :return: A single ``hybrid.config`` record or an empty recordset.
        """
        domain = [("active", "=", True)]
        if company:
            company_id = company.id if hasattr(company, "id") else int(company)
            domain.append(("company_id", "=", company_id))
        return self.search(domain, limit=1)
