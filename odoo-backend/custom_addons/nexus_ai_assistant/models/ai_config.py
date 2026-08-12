import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urljoin

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AiAssistantConfig(models.Model):
    _name = "nexus.ai.config"
    _description = "Nexus AI Assistant Configuration"

    name = fields.Char(default="AI Assistant Configuration")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    ai_service_url = fields.Char(
        string="AI Service URL",
        default="http://ai_services:8000",
        required=True,
        help="URL of the Nexus AI microservice (FastAPI).",
    )
    ai_provider = fields.Selection(
        [
            ("auto", "Auto (fallback)"),
            ("gemini", "Gemini"),
            ("openai", "OpenAI"),
            ("deepseek", "DeepSeek"),
            ("ollama", "Ollama"),
        ],
        default="auto",
        required=True,
    )
    request_timeout = fields.Integer(default=180)

    _sql_constraints = [
        ("company_uniq", "unique(company_id)", "Only one AI config is allowed per company."),
    ]

    @api.model
    def get_config(self):
        """Return the active AI configuration record for the current company."""
        config = self.search([("company_id", "=", self.env.company.id)], limit=1)
        if not config:
            config = self.create({
                "name": "AI Assistant Configuration",
                "company_id": self.env.company.id,
            })
        return config

    def _call_ai_service(self, endpoint, payload, method="POST"):
        """Call the Nexus AI microservice and return the parsed JSON response."""
        self.ensure_one()
        url = urljoin(self.ai_service_url.rstrip("/") + "/", endpoint)
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        _logger.info("Calling AI service at %s", url)
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            _logger.error("AI service HTTP %s: %s", exc.code, body)
            raise UserError(_("AI service error (%(code)s): %(body)s") % {"code": exc.code, "body": body}) from exc
        except urllib.error.URLError as exc:
            _logger.error("AI service unreachable: %s", exc.reason)
            raise UserError(_("AI service is unreachable. Is the Nexus AI container running?")) from exc
        except json.JSONDecodeError as exc:
            _logger.error("AI service returned invalid JSON: %s", exc)
            raise UserError(_("AI service returned invalid JSON.")) from exc
