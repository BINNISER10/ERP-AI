"""Account move extension for ERPNext sync tracking."""
from odoo import models, fields


class AccountMove(models.Model):
    """Adds flags used by the hybrid sync and copilot modules to protect
    synchronized accounting entries.
    """

    _inherit = "account.move"

    erpnext_synced = fields.Boolean(
        string="Synced to ERPNext",
        default=False,
        copy=False,
        index=True,
        help="True when this journal entry/invoice has been pushed to ERPNext.",
    )
    erpnext_docname = fields.Char(
        string="ERPNext Document Name",
        copy=False,
        help="Reference name of the corresponding ERPNext document.",
    )
