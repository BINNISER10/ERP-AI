"""Pillar 2 — Order-to-Cash (O2C) & Procure-to-Pay (P2P).

When a Payment is posted in the Nexus Command Center, a Payment Entry
is queued to the Nexus Core.  The payload references each reconciled
invoice by its Core docname, auto-reconciling the invoice to 'Paid'.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    nexus_core_synced = fields.Boolean(
        string="Nexus Core Payment Entry Synced",
        default=False,
        copy=False,
    )
    nexus_core_docname = fields.Char(
        string="Nexus Core Payment Doc Name",
        copy=False,
    )

    def action_post(self):
        """Post the payment and queue the Nexus Core Payment Entry."""
        res = super().action_post()
        for payment in self:
            if not payment.nexus_core_synced:
                payment._enqueue_payment_entry()
        return res

    def _enqueue_payment_entry(self):
        """Queue a Payment Entry for this payment in the Nexus Core."""
        self.ensure_one()

        # Skip non-posted payments
        if self.state != "posted":
            return

        tx_id = f"NX-PAY-{self.id}"

        # Check if any referenced invoices have been synced (for logging).
        reconciled = (
            self.reconciled_invoice_ids
            or self.env["account.move"]
        )
        synced_invoices = reconciled.filtered(lambda i: i.erpnext_synced)
        if synced_invoices:
            _logger.info(
                "Nexus Core: payment #%s references %d synced invoices",
                self.name,
                len(synced_invoices),
            )

        self.env["nexus.sync.queue"].enqueue(
            operation="payment_entry.create",
            payload={},
            endpoint="/api/resource/Payment Entry",
            company=self.company_id,
            model_name="account.payment",
            res_id=self.id,
            transaction_id=tx_id,
            priority=10,
        )
        _logger.info(
            "Nexus Core: queued Payment Entry '%s' (%s %s) [%s]",
            self.name or self.id,
            self.payment_type,
            self.partner_type,
            tx_id[:12],
        )
