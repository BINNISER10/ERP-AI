"""Persona-aware insights generated from ERPNext KPIs and the Copilot brain."""
import logging
import requests
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class CopilotInsight(models.Model):
    """A warm, persona-specific insight that surfaces on the CEO dashboard."""

    _name = "copilot.insight"
    _description = "AI Enterprise Copilot Insight"
    _order = "create_date desc"

    name = fields.Char(string="Title", required=True, translate=True)
    persona = fields.Selection(
        [
            ("ceo", "CEO"),
            ("cfo", "CFO"),
            ("coo", "COO"),
            ("it_admin", "IT Admin"),
        ],
        default="ceo",
        required=True,
        help="The audience/persona that should see this insight.",
    )
    insight_text = fields.Text(
        string="Insight",
        required=True,
        translate=True,
    )
    warm_message = fields.Text(
        string="Warm Message",
        translate=True,
        help="Friendly guidance for the end user.",
    )
    source = fields.Char(
        string="Source",
        help="e.g. erpnext_kpi, cron_error, manual.",
    )
    active = fields.Boolean(default=True)

    @api.model
    def _create_insight(self, persona, title, insight, warm, source):
        """Create an insight record while suppressing duplicate errors."""
        try:
            return self.create({
                "persona": persona,
                "name": title,
                "insight_text": insight,
                "warm_message": warm,
                "source": source,
            })
        except Exception:
            _logger.exception("Could not create Copilot insight.")
            return self.browse()

    @api.model
    def fetch_erpnext_kpis(self):
        """Cron-called method that fetches Cash Flow and MRP data from ERPNext
        and stores warm CEO insights.
        """
        config = self.env["copilot.config"].sudo().get_active_config()
        if not config or not config.hybrid_config_id or not config.erpnext_url:
            self._create_insight(
                "ceo",
                _("ERPNext is not configured yet"),
                _("I cannot fetch your KPIs because the ERPNext URL is missing."),
                _("Please open Copilot Settings and link a Hybrid Sync configuration."),
                "cron_error",
            )
            return

        hc = config.hybrid_config_id
        erpnext_url = hc.erpnext_url.rstrip("/")
        headers = {}
        if hc.erpnext_api_key and hc.erpnext_api_secret:
            headers["Authorization"] = f"token {hc.erpnext_api_key}:{hc.erpnext_api_secret}"

        try:
            # Cash flow snapshot.
            cash_resp = requests.get(
                f"{erpnext_url}/api/method/erpnext.accounts.utils.get_cash_flow",
                headers=headers,
                timeout=15,
            )
            cash_text = "Cash flow data not available."
            if cash_resp.ok:
                try:
                    cash_payload = cash_resp.json()
                    cash_text = str(cash_payload.get("message", cash_text))
                except ValueError:
                    cash_text = cash_resp.text[:250]

            # MRP status snapshot.
            mrp_resp = requests.get(
                f"{erpnext_url}/api/method/erpnext.manufacturing.doctype.work_order.work_order.get_work_orders",
                headers=headers,
                timeout=15,
            )
            mrp_text = "MRP data not available."
            if mrp_resp.ok:
                try:
                    mrp_payload = mrp_resp.json()
                    mrp_text = str(mrp_payload.get("message", mrp_text))
                except ValueError:
                    mrp_text = mrp_resp.text[:250]

            self._create_insight(
                "ceo",
                _("Financial & Manufacturing Snapshot"),
                f"Cash Flow: {cash_text}. MRP: {mrp_text}.",
                _(
                    "Your financial and manufacturing data is flowing. "
                    "I will keep watching for trends and alert you when something needs attention."
                ),
                "erpnext_kpi",
            )
        except Exception as exc:
            _logger.exception("Failed to fetch ERPNext KPIs.")
            self._create_insight(
                "ceo",
                _("ERPNext KPI fetch failed"),
                f"I could not reach ERPNext to read the latest KPIs: {exc}.",
                _(
                    "ERPNext is temporarily unavailable. I will retry soon; "
                    "your Odoo invoices are still safe here."
                ),
                "cron_error",
            )
            self.env["copilot.support.incident"].sudo().create({
                "name": _("ERPNext KPI Fetch Failed"),
                "source": "erpnext",
                "severity": "medium",
                "description": str(exc),
            })
