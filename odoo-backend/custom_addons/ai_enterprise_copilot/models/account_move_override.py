"""Behavioral interceptor that protects ERPNext-synchronized account moves."""
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Prevents accidental write/unlink of synchronized journal entries while
    keeping the system friendly and auditable.
    """

    _inherit = "account.move"

    def write(self, vals):
        """Block writes that would mutate an ERPNext-synced move.

        The sync process may bypass the guard by using the context key
        ``force_erpnext_write``.
        """
        if self.env.context.get("force_erpnext_write"):
            return super().write(vals)

        allowed_internal = {"erpnext_synced", "erpnext_docname"}
        for move in self:
            if not move.erpnext_synced:
                continue
            # If this is just an internal sync flag update, allow it.
            if vals.get("erpnext_synced") and set(vals.keys()).issubset(allowed_internal):
                continue

            warm = self._copilot_warm_message(move)
            self._copilot_log_block(move, "write", warm)
            raise UserError(warm)

        return super().write(vals)

    def unlink(self):
        """Block deletion of ERPNext-synced moves unless forced by context."""
        if self.env.context.get("force_erpnext_unlink"):
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
            "This invoice %(name)s has already been synced with ERPNext. "
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
                    "Record %(name)s is already synced with ERPNext.",
                    name=move.name or move.id,
                ),
                "warm_message": message,
                "state": "blocked",
            })
        except Exception:
            _logger.exception("Could not create Copilot behavior log.")
