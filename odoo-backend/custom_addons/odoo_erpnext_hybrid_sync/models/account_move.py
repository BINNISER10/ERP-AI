"""Account move extension for hybrid-ledger sync tracking."""
from odoo import models, fields


class AccountMove(models.Model):
    """Adds flags used by the hybrid sync and copilot modules to protect
    synchronized accounting entries.
    """

    _inherit = "account.move"

    erpnext_synced = fields.Boolean(
        string="Synced to Hybrid Ledger",
        default=False,
        copy=False,
        index=True,
        help="True when this journal entry/invoice has been pushed to the hybrid ledger.",
    )
    erpnext_docname = fields.Char(
        string="Hybrid Ledger Document Name",
        copy=False,
        help="Reference name of the corresponding hybrid ledger document.",
    )
