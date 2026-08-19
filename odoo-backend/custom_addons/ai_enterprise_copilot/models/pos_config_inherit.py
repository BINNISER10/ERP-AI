"""POS warm-reminder enforcement for the Nexus setup journey."""
from odoo import models, _
from odoo.exceptions import RedirectWarning


class PosConfig(models.Model):
    """Hook POS opening to the Nexus setup journey readiness check."""

    _inherit = "pos.config"

    def open_ui(self):
        """Show a warm AI-friendly reminder if setup prerequisites are missing."""
        for config in self:
            company = config.company_id or self.env.company
            journey = self.env["nexus.setup.journey"].get_or_create(company)
            msg = journey._get_warm_message("pos_session")
            if msg:
                raise RedirectWarning(
                    msg,
                    {
                        "type": "ir.actions.act_window",
                        "res_model": "nexus.setup.journey",
                        "res_id": journey.id,
                        "views": [[False, "form"]],
                        "target": "current",
                    },
                    _("Open Setup Journey"),
                )
        return super().open_ui()
