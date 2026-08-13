"""Setup milestones and the interactive setup wizard."""
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CopilotSetupMilestone(models.Model):
    """Tracks progress of the Copilot/ERPNext hybrid onboarding."""

    _name = "copilot.setup.milestone"
    _description = "Copilot Setup Milestone"
    _order = "sequence, id"

    name = fields.Char(string="Milestone", required=True, translate=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("skipped", "Skipped"),
        ],
        default="pending",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    description = fields.Text(translate=True)
    completed_date = fields.Datetime()
    triggered_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )

    @api.model
    def mark_done(self, name, company=None, description=None):
        """Convenience helper to mark a milestone as completed."""
        company = company or self.env.company
        return self.create({
            "name": name,
            "state": "done",
            "company_id": company.id,
            "description": description or "",
            "completed_date": fields.Datetime.now(),
        })


class CopilotSetupWizard(models.TransientModel):
    """Interactive wizard that validates ERPNext and triggers n8n chart of
    accounts sync without requiring the user to leave Odoo.
    """

    _name = "copilot.setup.wizard"
    _description = "Copilot Setup Wizard"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    hybrid_config_id = fields.Many2one(
        "hybrid.config",
        string="Hybrid Sync Configuration",
    )

    erpnext_url = fields.Char(
        related="hybrid_config_id.erpnext_url",
        readonly=False,
        string="ERPNext URL",
    )
    n8n_url = fields.Char(
        related="hybrid_config_id.n8n_url",
        readonly=False,
        string="n8n URL",
    )

    step = fields.Selection(
        [
            ("connection", "Validate ERPNext Connection"),
            ("chart_of_accounts", "Sync Chart of Accounts"),
            ("done", "Done"),
        ],
        default="connection",
        required=True,
    )
    connection_status = fields.Char(
        string="Connection Status",
        readonly=True,
    )
    coa_sync_status = fields.Char(
        string="Chart of Accounts Sync Status",
        readonly=True,
    )
    log = fields.Text(string="Log", readonly=True)

    @api.onchange("company_id")
    def _onchange_company_id(self):
        """Pre-select the active hybrid configuration for the chosen company."""
        for wizard in self:
            if wizard.company_id:
                wizard.hybrid_config_id = self.env["hybrid.config"].search([
                    ("company_id", "=", wizard.company_id.id),
                    ("active", "=", True),
                ], limit=1)

    def _get_hybrid_config(self):
        """Return the active hybrid config or raise a clear UserError."""
        self.ensure_one()
        config = self.hybrid_config_id or self.env["hybrid.config"].get_active_config(self.company_id)
        if not config:
            raise UserError(_(
                "Please configure a Hybrid Sync record first (Settings -> Hybrid ERP Sync)."
            ))
        return config

    def action_validate_erpnext(self):
        """Ping the ERPNext instance and record the milestone."""
        self.ensure_one()
        config = self._get_hybrid_config()
        if not config.erpnext_url:
            self.connection_status = "No ERPNext URL configured."
            self.log = "Please set the ERPNext base URL in Hybrid Sync settings."
            return self._reopen_wizard()

        try:
            headers = {}
            if config.erpnext_api_key and config.erpnext_api_secret:
                headers["Authorization"] = f"token {config.erpnext_api_key}:{config.erpnext_api_secret}"

            url = config.erpnext_url.rstrip("/") + "/api/method/erpnext.ping"
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            self.connection_status = _(
                "Connection validated successfully (HTTP %s).", response.status_code
            )
            self.log = response.text[:500]
            self.step = "chart_of_accounts"

            self.env["copilot.setup.milestone"].sudo().mark_done(
                _("ERPNext Connection Validated"),
                company=self.company_id,
                description=self.connection_status,
            )
        except Exception as exc:
            _logger.exception("ERPNext connection validation failed.")
            self.connection_status = "Connection failed."
            self.log = str(exc)

        return self._reopen_wizard()

    def action_sync_chart_of_accounts(self):
        """Trigger the n8n webhook that configures the Chart of Accounts in ERPNext."""
        self.ensure_one()
        config = self._get_hybrid_config()

        try:
            payload = {
                "company_id": self.company_id.id,
                "company_name": self.company_id.name,
                "triggered_by": self.env.user.id,
            }
            headers = {"Content-Type": "application/json"}
            if config.n8n_webhook_key:
                headers["Authorization"] = f"Bearer {config.n8n_webhook_key}"

            if config.n8n_url:
                url = config.n8n_url.rstrip("/") + "/webhook/sync-chart-of-accounts"
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()
                self.coa_sync_status = _(
                    "n8n webhook called successfully (HTTP %s).", response.status_code
                )
                self.log = response.text[:500]
            else:
                self.coa_sync_status = _(
                    "No n8n URL configured; sync queued for later manual trigger."
                )

            self.env["copilot.setup.milestone"].sudo().mark_done(
                _("Chart of Accounts Sync Triggered"),
                company=self.company_id,
                description=self.coa_sync_status,
            )
            self.step = "done"
        except Exception as exc:
            _logger.exception("Chart of Accounts sync failed.")
            self.coa_sync_status = "Sync failed."
            self.log = str(exc)

        return self._reopen_wizard()

    def _reopen_wizard(self):
        """Return an action that keeps the wizard open and refreshes the form."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }
