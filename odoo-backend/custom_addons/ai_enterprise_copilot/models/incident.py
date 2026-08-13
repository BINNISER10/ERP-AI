"""Autonomous proactive tech support: incidents, heartbeat monitor and notifications."""
import logging
import requests
import traceback
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)



class CopilotSupportIncident(models.Model):
    """Records health check failures and routes warm user + silent dev notifications."""

    _name = "copilot.support.incident"
    _description = "Copilot Support Incident"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(
        string="Incident",
        required=True,
        default=lambda self: _(
            "INC-%(timestamp)s",
            timestamp=fields.Datetime.now().strftime("%Y%m%d-%H%M%S"),
        ),
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        required=True,
    )
    description = fields.Text(required=True)
    traceback = fields.Text()
    source = fields.Selection(
        [
            ("erpnext", "ERPNext"),
            ("n8n", "n8n"),
            ("general", "General"),
        ],
        default="general",
        required=True,
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("investigating", "Investigating"),
            ("resolved", "Resolved"),
        ],
        default="new",
        required=True,
    )
    notify_users = fields.Boolean(
        default=True,
        help="When true, a warm notification is broadcast to active users.",
    )

    @api.model
    def create_incident(self, source, description, severity="medium", traceback_text="", notify=True):
        """Create an incident and trigger warm + silent notifications.

        :param source: erpnext, n8n or general.
        :param description: Human-readable incident description.
        :param severity: low, medium, high or critical.
        :param traceback_text: Optional technical traceback.
        :param notify: Whether to broadcast the warm notification.
        :return: The created incident record.
        """
        try:
            incident = self.create({
                "source": source,
                "description": description,
                "severity": severity,
                "traceback": traceback_text,
                "notify_users": notify,
            })
        except Exception:
            _logger.exception("Could not create support incident.")
            return self.browse()

        try:
            if notify:
                incident._notify_warm()
        except Exception:
            _logger.exception("Could not broadcast warm notification.")

        try:
            incident._send_dev_webhook()
        except Exception:
            _logger.exception("Could not send incident to Dev Team webhook.")

        return incident

    def _notify_warm(self):
        """Broadcast a sticky, friendly notification to every active user."""
        self.ensure_one()
        try:
            payload = {
                "type": "warning",
                "title": _("AI Copilot Notice"),
                "message": _(
                    "Our financial core is doing a quick update. Keep selling, I am queuing your invoices safely!"
                ),
                "sticky": True,
            }
            bus = self.env["bus.bus"].sudo()
            partners = self.env["res.users"].search([("active", "=", True)]).mapped("partner_id")
            for partner in partners:
                bus._sendone(partner, "simple_notification", payload)
        except Exception:
            _logger.exception("Warm notification broadcast failed.")

    def _send_dev_webhook(self):
        """Send a silent JSON payload to the Dev Team webhook."""
        self.ensure_one()
        try:
            config = self.env["copilot.config"].sudo().get_active_config()
            if not config or not config.dev_team_webhook:
                return

            payload = {
                "incident_id": self.id,
                "name": self.name,
                "source": self.source,
                "severity": self.severity,
                "description": self.description,
                "traceback": self.traceback,
                "created_at": fields.Datetime.to_string(self.create_date),
            }
            response = requests.post(
                config.dev_team_webhook,
                json=payload,
                timeout=config.dev_team_webhook_timeout or 10,
            )
            response.raise_for_status()
        except Exception:
            _logger.exception("Dev Team webhook dispatch failed.")

    @api.model
    def check_hybrid_health(self):
        """Heartbeat monitor: ping ERPNext and n8n, and raise incidents on failure."""
        config = self.env["copilot.config"].sudo().get_active_config()
        if not config or not config.hybrid_config_id:
            self.create_incident(
                "general",
                _(
                    "Copilot is not configured. Cannot check hybrid health "
                    "because no Hybrid Sync configuration is linked."
                ),
                severity="medium",
            )
            return

        hc = config.hybrid_config_id
        erpnext_url = hc.erpnext_url
        n8n_url = hc.n8n_url
        headers = {}
        if hc.erpnext_api_key and hc.erpnext_api_secret:
            headers["Authorization"] = f"token {hc.erpnext_api_key}:{hc.erpnext_api_secret}"

        failures = []

        if erpnext_url:
            try:
                response = requests.get(
                    f"{erpnext_url.rstrip('/')}/api/method/erpnext.ping",
                    headers=headers,
                    timeout=15,
                )
                response.raise_for_status()
            except Exception as exc:
                _logger.exception("ERPNext health check failed.")
                failures.append(("erpnext", f"ERPNext unreachable: {exc}"))

        if n8n_url:
            try:
                n8n_headers = {}
                if hc.n8n_webhook_key:
                    n8n_headers["Authorization"] = f"Bearer {hc.n8n_webhook_key}"
                response = requests.get(
                    f"{n8n_url.rstrip('/')}/healthz",
                    headers=n8n_headers,
                    timeout=10,
                )
                response.raise_for_status()
            except Exception as exc:
                _logger.exception("n8n health check failed.")
                failures.append(("n8n", f"n8n unreachable: {exc}"))

        if failures:
            for source, desc in failures:
                self.create_incident(
                    source,
                    desc,
                    severity="high",
                    traceback_text=traceback.format_exc(),
                )
        else:
            _logger.info("Hybrid health check passed for Copilot.")
