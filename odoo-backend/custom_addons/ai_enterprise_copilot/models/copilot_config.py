"""Central configuration for the AI Enterprise Copilot."""
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class CopilotConfig(models.Model):
    """Holds LLM keys, external monitoring webhooks and a link to the
    hybrid ERPNext/n8n configuration.
    """

    _name = "copilot.config"
    _description = "AI Enterprise Copilot Settings"
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
        help="Company that this Copilot configuration belongs to.",
    )
    active = fields.Boolean(default=True, help="Enable or disable this Copilot.")

    # Link to the hybrid sync configuration; all ERPNext/n8n URLs live there.
    hybrid_config_id = fields.Many2one(
        "hybrid.config",
        string="Hybrid Sync Configuration",
        help="Select the ERPNext/n8n connection to use.",
    )

    # Related fields exposed for a single settings screen.
    erpnext_url = fields.Char(
        related="hybrid_config_id.erpnext_url",
        readonly=False,
        string="ERPNext Base URL",
    )
    erpnext_api_key = fields.Char(
        related="hybrid_config_id.erpnext_api_key",
        readonly=False,
        string="ERPNext API Key",
        password=True,
    )
    erpnext_api_secret = fields.Char(
        related="hybrid_config_id.erpnext_api_secret",
        readonly=False,
        string="ERPNext API Secret",
        password=True,
    )
    n8n_url = fields.Char(
        related="hybrid_config_id.n8n_url",
        readonly=False,
        string="n8n Base URL",
    )
    n8n_webhook_key = fields.Char(
        related="hybrid_config_id.n8n_webhook_key",
        readonly=False,
        string="n8n Webhook Key",
        password=True,
    )

    # Nexus Core (Command Center) sync endpoint.
    nexus_core_url = fields.Char(
        string="Nexus Core Base URL",
        help="Base URL of the Nexus Core API that receives setup configuration.",
    )
    nexus_core_api_key = fields.Char(
        string="Nexus Core API Key",
        help="Bearer token or API key for Nexus Core authentication.",
        password=True,
    )

    # LLM / AI settings.
    llm_provider = fields.Selection(
        [
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("ollama", "Ollama"),
            ("gemini", "Google Gemini"),
        ],
        string="LLM Provider",
        default="gemini",
        help="Preferred Large Language Model provider.",
    )
    llm_api_key = fields.Char(
        string="LLM API Key",
        help="API key for the selected LLM provider.",
        password=True,
    )
    llm_model = fields.Char(
        string="LLM Model",
        default="gemini-1.5-flash",
        help="Model name, e.g. qwen2.5:1.5b or gpt-4o.",
    )
    llm_timeout = fields.Integer(
        string="LLM Timeout (seconds)",
        default=120,
        help="Request timeout when calling the LLM service.",
    )
    nexus_ai_api_key = fields.Char(
        string="Nexus AI Service Shared Key",
        help="Shared secret sent as the X-API-Key header when Odoo calls the "
        "nexus_ai microservice (ai_services). Must match AI_SERVICES_API_KEY "
        "configured on that container, otherwise every AI-assisted feature "
        "(BOM advisor, chart-of-accounts mapping, developer consult, ...) "
        "will be rejected with 401 Unauthorized.",
        password=True,
    )

    # DevOps monitoring.
    dev_team_webhook = fields.Char(
        string="Dev Team Webhook URL",
        help="Endpoint that receives silent technical incident payloads.",
    )
    dev_team_webhook_timeout = fields.Integer(
        string="Webhook Timeout (seconds)",
        default=10,
    )

    _sql_constraints = [
        (
            "company_uniq",
            "unique(company_id)",
            "Only one Copilot configuration is allowed per company.",
        ),
    ]

    @api.model
    def get_active_config(self, company=None):
        """Return the active Copilot configuration for the given company.

        :param company: Optional res.company record or integer ID.
        :return: A single ``copilot.config`` record or an empty recordset.
        """
        domain = [("active", "=", True)]
        if company:
            company_id = company.id if hasattr(company, "id") else int(company)
            domain.append(("company_id", "=", company_id))
        return self.search(domain, limit=1)
