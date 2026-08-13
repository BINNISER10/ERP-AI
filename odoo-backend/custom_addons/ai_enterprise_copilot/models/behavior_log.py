"""Behavioral interceptor log for the AI Copilot."""
from odoo import models, fields, _


class CopilotBehaviorLog(models.Model):
    """Keeps a human-readable audit of actions that the Copilot allowed or
    blocked, especially changes to ERPNext-synchronized records.
    """

    _name = "copilot.behavior.log"
    _description = "Copilot Behavioral Interceptor Log"
    _order = "create_date desc"

    name = fields.Char(
        string="Reference",
        default=lambda self: _("Behavior Log"),
    )
    user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )
    model_name = fields.Char(required=True)
    record_id = fields.Integer()
    action = fields.Char(
        string="Attempted Action",
        required=True,
        help="e.g. write, unlink, cancel.",
    )
    reason = fields.Text()
    warm_message = fields.Text(
        help="Friendly message that was shown to the user.",
    )
    state = fields.Selection(
        [
            ("blocked", "Blocked"),
            ("allowed", "Allowed"),
        ],
        default="blocked",
    )
