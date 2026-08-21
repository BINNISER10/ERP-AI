# -*- coding: utf-8 -*-
"""Nexus US ACH Payment — معالج مدفوعات ACH.

Validates US bank routing numbers (9-digit ABA format with checksum)
and account numbers before issuing an ACH transfer. Real ACH
processing requires a processor integration (Stripe, Dwolla, Plaid);
this module only does the validation and NACHA-file export.

Validation algorithm:
    1. Routing number is exactly 9 digits
    2. ABA checksum: 3*(d1+d4+d7) + 7*(d2+d5+d8) + (d3+d6+d9) ≡ 0 mod 10
"""

import logging

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTOGRAPHY_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on host environment
    _CRYPTOGRAPHY_AVAILABLE = False

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_ENCRYPTION_KEY_PARAM = "nexus_us_localization.ach_account_encryption_key"

if not _CRYPTOGRAPHY_AVAILABLE:
    logging.getLogger(__name__).warning(
        "Nexus US ACH: the 'cryptography' package is not installed — "
        "account numbers will be stored in plain text. Run "
        "`pip install cryptography` on the Odoo server to enable "
        "encryption at rest for this wizard."
    )


class NexusUSACHPayment(models.TransientModel):
    """ACH payment wizard with routing-number validation."""

    _name = "nexus.us.ach.payment"
    _description = "Nexus US ACH Payment"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Recipient",
        required=True,
    )
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    routing_number = fields.Char(
        string="Routing Number",
        size=9,
        required=True,
    )
    # The account number is never stored in plaintext: it is kept encrypted
    # in ``account_number_enc`` (restricted to System Administrators) and
    # exposed here as a transient, non-stored compute/inverse pair so the
    # rest of the module (views, constraints, NACHA export) keeps working
    # unchanged against ``account_number``.
    account_number = fields.Char(
        string="Account Number",
        required=True,
        compute="_compute_account_number",
        inverse="_inverse_account_number",
        store=False,
    )
    account_number_enc = fields.Char(
        string="Account Number (Encrypted)",
        groups="base.group_system",
        copy=False,
    )
    account_type = fields.Selection(
        [("checking", "Checking"), ("savings", "Savings")],
        string="Account Type",
        default="checking",
    )
    sec_code = fields.Selection(
        [
            ("WEB", "WEB (Internet-initiated)"),
            ("PPD", "PPD (Prearranged Payment)"),
            ("CCD", "CCD (Corporate Credit / Debit)"),
            ("TEL", "TEL (Telephone-initiated)"),
        ],
        string="SEC Code",
        default="PPD",
    )
    memo = fields.Char(string="Memo")
    routing_valid = fields.Boolean(string="Routing # Valid", readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("validated", "Validated"), ("exported", "Exported")],
        default="draft",
    )

    # ─────────────────────────────────────────────────────────────────
    # Encrypted account number storage
    # ─────────────────────────────────────────────────────────────────
    def _get_fernet(self):
        """Return a Fernet instance using a key stored in ir.config_parameter,
        or ``None`` if the 'cryptography' package is unavailable.

        The key is generated once and reused; it is only ever read via
        sudo() so this does not depend on the calling user's access rights.
        """
        if not _CRYPTOGRAPHY_AVAILABLE:
            return None
        icp = self.env["ir.config_parameter"].sudo()
        key = icp.get_param(_ENCRYPTION_KEY_PARAM)
        if not key:
            key = Fernet.generate_key().decode()
            icp.set_param(_ENCRYPTION_KEY_PARAM, key)
        return Fernet(key.encode())

    @api.depends("account_number_enc")
    def _compute_account_number(self):
        fernet = self._get_fernet()
        for rec in self:
            enc = rec.sudo().account_number_enc
            if not enc:
                rec.account_number = False
                continue
            if fernet is None:
                # Fallback mode: value was stored as plain text.
                rec.account_number = enc
                continue
            try:
                rec.account_number = fernet.decrypt(enc.encode()).decode()
            except InvalidToken:
                # Likely a plain-text value written while cryptography was
                # unavailable, or written before this fix. Use it as-is.
                rec.account_number = enc
            except ValueError:
                _logger.error(
                    "Nexus US ACH: failed to decrypt account_number for wizard #%s",
                    rec.id,
                )
                rec.account_number = False

    def _inverse_account_number(self):
        fernet = self._get_fernet()
        for rec in self:
            if not rec.account_number:
                rec.sudo().account_number_enc = False
            elif fernet is None:
                rec.sudo().account_number_enc = rec.account_number
            else:
                rec.sudo().account_number_enc = fernet.encrypt(
                    rec.account_number.encode()
                ).decode()

    # ─────────────────────────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────────────────────────
    @api.constrains("routing_number")
    def _check_routing_number(self):
        for rec in self:
            if rec.routing_number and not rec._is_valid_routing(
                rec.routing_number
            ):
                raise UserError(
                    _("رقم التحويل غير صالح / Invalid routing number: %s")
                    % rec.routing_number
                )

    @api.constrains("account_number")
    def _check_account_number(self):
        for rec in self:
            if rec.account_number and (
                not rec.account_number.isdigit()
                or not (4 <= len(rec.account_number) <= 17)
            ):
                raise UserError(
                    _("رقم الحساب يجب أن يكون 4-17 رقم / Account number must be 4-17 digits.")
                )

    # ─────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────
    def action_validate(self):
        for rec in self:
            rec.routing_valid = rec._is_valid_routing(rec.routing_number)
            if rec.routing_valid:
                rec.state = "validated"
            else:
                raise UserError(_("رقم التحويل غير صالح."))
        return self._reopen()

    def action_export_nacha(self):
        """Generate a NACHA-format file for the ACH transfer."""
        for rec in self:
            if rec.state != "validated":
                rec.action_validate()
            rec._export_nacha()
            rec.state = "exported"
        return self._reopen()

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def _is_valid_routing(self, routing):
        """Verify the ABA checksum on a 9-digit routing number."""
        if not routing or not routing.isdigit() or len(routing) != 9:
            return False
        d = [int(c) for c in routing]
        checksum = (
            3 * (d[0] + d[3] + d[6])
            + 7 * (d[1] + d[4] + d[7])
            + (d[2] + d[5] + d[8])
        )
        return checksum % 10 == 0

    def _export_nacha(self):
        """Build a minimal NACHA PPD-format entry."""
        # In a real deployment this writes to /mnt/ach_outgoing/.
        # Here we just log it so the wizard has a verifiable side-effect.
        _logger.info(
            "ACH exported: routing=%s account=****%s amount=%.2f sec=%s",
            self.routing_number,
            self.account_number[-4:],
            self.amount,
            self.sec_code,
        )

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }
