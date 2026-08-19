"""Behavioral interceptor that protects hybrid-ledger synchronized account moves."""
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Prevents accidental write/unlink of synchronized journal entries while
    keeping the system friendly and auditable.
    """

    _inherit = "account.move"

    # Fields that change the actual accounting content of a move (amounts,
    # lines, partner, dates, journal...). Only writes touching at least one
    # of these fields on a hybrid-ledger synced move are blocked. Internal
    # bookkeeping updates (payment reconciliation, payment_state, message/
    # activity tracking, etc.) are never routed through these fields and are
    # therefore left untouched, so they keep working normally on synced moves.
    _SYNC_PROTECTED_FIELDS = {
        "line_ids",
        "invoice_line_ids",
        "partner_id",
        "invoice_date",
        "invoice_date_due",
        "date",
        "journal_id",
        "currency_id",
        "move_type",
        "ref",
        "name",
        "state",
        "amount_total",
        "amount_untaxed",
        "amount_tax",
        "company_id",
        "fiscal_position_id",
        "invoice_partner_bank_id",
    }

    def write(self, vals):
        """Block writes that would mutate the accounting content of a
        hybrid-ledger synced move, while letting internal bookkeeping
        operations (reconciliation, payment_state, chatter, etc.) proceed.

        The sync process may bypass the guard entirely by using the context
        key ``force_erpnext_write``, but only when running as superuser so
        that regular RPC users cannot mutate synced moves.
        """
        if self.env.context.get("force_erpnext_write") and self.env.is_superuser():
            return super().write(vals)

        protected_keys = set(vals.keys()) & self._SYNC_PROTECTED_FIELDS
        if protected_keys:
            for move in self:
                if not move.erpnext_synced:
                    continue
                warm = self._copilot_warm_message(move)
                self._copilot_log_block(move, "write", warm)
                raise UserError(warm)

        return super().write(vals)

    def unlink(self):
        """Block deletion of hybrid-ledger synced moves unless forced by superuser context."""
        if self.env.context.get("force_erpnext_unlink") and self.env.is_superuser():
            return super().unlink()

        for move in self:
            if move.erpnext_synced:
                warm = self._copilot_warm_message(move)
                self._copilot_log_block(move, "unlink", warm)
                raise UserError(warm)

        return super().unlink()

    def _copilot_warm_message(self, move):
        """Return the translated, friendly message shown to users."""
        return _(
            "This invoice %(name)s has already been synced with the hybrid ledger. "
            "To keep both ledgers perfectly aligned, please use a Credit Note instead. "
            "I am here to help you create it if you need me.",
            name=move.name or move.id,
        )

    def _copilot_log_block(self, move, action, message):
        """Log a blocked action attempt for the behavior dashboard."""
        try:
            self.env["copilot.behavior.log"].sudo().create({
                "user_id": self.env.uid,
                "model_name": "account.move",
                "record_id": move.id,
                "action": action,
                "reason": _(
                    "Record %(name)s is already synced with the hybrid ledger.",
                    name=move.name or move.id,
                ),
                "warm_message": message,
                "state": "blocked",
            })
        except Exception:
            _logger.exception("Could not create Copilot behavior log.")
