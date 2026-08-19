# -*- coding: utf-8 -*-
"""Nexus ERPNext Bridge Listeners — المستمعات التلقائية للجسر.

Hooks Odoo's ``account.*`` and related models so that every relevant
write is mirrored to the Nexus Core (ERPNext).  Failures do not break
the user transaction — they fall back to ``nexus.sync.queue`` for
asynchronous retry.

Models listened to:
    * ``account.move``            (on post)
    * ``account.payment``         (on post)
    * ``account.asset``           (on create / write)
    * ``res.partner``             (on write when financial fields change)
    * ``product.product``         (on write when accounting-relevant fields change)
    * ``stock.warehouse``         (on create)
    * ``account.tax``             (on write)
    * ``account.analytic.account``(on write)
    * ``account.account``         (on write)
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


# Fields that, when changed on res.partner, justify a sync
_PARTNER_FINANCIAL_FIELDS = (
    "vat",
    "property_account_receivable_id",
    "property_account_payable_id",
    "property_payment_term_id",
    "property_supplier_payment_term_id",
    "credit_limit",
    "company_id",
)

# Fields on product that justify a sync
_PRODUCT_FINANCIAL_FIELDS = (
    "default_code",
    "name",
    "categ_id",
    "uom_id",
    "list_price",
    "standard_price",
    "taxes_id",
    "supplier_taxes_id",
    "sale_ok",
    "purchase_ok",
    "type",
)


class NexusERPNextBridgeListeners(models.AbstractModel):
    """Auto-trigger pushes when accounting-relevant records change."""

    _name = "nexus.erpnext.bridge.listeners"
    _description = "Nexus ERPNext Bridge Listeners"

    # ═══════════════════════════════════════════════════════════════════
    # account.move (Invoice / Bill) — listen on post
    # ═══════════════════════════════════════════════════════════════════
    @api.model
    def _on_account_move_posted(self, move_id):
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_account_move(move_id)

    @api.model
    def _on_account_move_updated(self, move_id):
        """Triggered when a posted move is re-opened or reversed."""
        ext = self.env["nexus.erpnext.bridge.extensions"]
        move = self.env["account.move"].browse(move_id)
        if move.exists() and move.state == "posted":
            return ext.push_account_move(move_id)
        return False

    # ═══════════════════════════════════════════════════════════════════
    # account.payment — listen on post
    # ═══════════════════════════════════════════════════════════════════
    @api.model
    def _on_account_payment_posted(self, payment_id):
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_payment(payment_id)

    # ═══════════════════════════════════════════════════════════════════
    # account.asset — listen on create / write
    # ═══════════════════════════════════════════════════════════════════
    @api.model
    def _on_account_asset_saved(self, asset_id):
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_asset(asset_id)

    # ═══════════════════════════════════════════════════════════════════
    # res.partner — listen on financial-field changes
    # �══════════════════════════════════════════════════════════════════
    @api.model
    def _on_partner_financial_changed(self, partner_id, changed_fields=None):
        if changed_fields is not None and not (
            set(changed_fields) & set(_PARTNER_FINANCIAL_FIELDS)
        ):
            return False
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_partner(partner_id)

    # ═══════════════════════════════════════════════════════════════════
    # product.product — listen on accounting-relevant changes
    # ═══════════════════════════════════════════════════════════════════
    @api.model
    def _on_product_financial_changed(self, product_id, changed_fields=None):
        if changed_fields is not None and not (
            set(changed_fields) & set(_PRODUCT_FINANCIAL_FIELDS)
        ):
            return False
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_product(product_id)

    # ═══════════════════════════════════════════════════════════════════
    # stock.warehouse — listen on create
    # ═══════════════════════════════════════════════════════════════════
    @api.model
    def _on_warehouse_created(self, warehouse_id):
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_warehouse(warehouse_id)

    # ═══════════════════════════════════════════════════════════════════
    # account.tax — listen on write
    # ═══════════════════════════════════════════════════════════════════
    @api.model
    def _on_tax_changed(self, tax_id):
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_tax(tax_id)

    # ═══════════════════════════════════════════════════════════════════
    # account.analytic.account (Cost Center) — listen on write
    # ═══════════════════════════════════════════════════════════════════
    @api.model
    def _on_analytic_changed(self, analytic_id):
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_cost_center(analytic_id)

    # �══════════════════════════════════════════════════════════════════
    # account.account — listen on write
    # ═══════════════════════════════════════════════════════════════════
    @api.model
    def _on_account_changed(self, account_id):
        ext = self.env["nexus.erpnext.bridge.extensions"]
        return ext.push_account(account_id)

    # ═══════════════════════════════════════════════════════════════════
    # Trigger from UI buttons
    # ═══════════════════════════════════════════════════════════════════
    def action_resync_all(self):
        """Manual trigger: re-push everything currently out of sync."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("nexus.last_resync_at", fields.Datetime.now())
        ext = self.env["nexus.erpnext.bridge.extensions"]

        # 1. Re-push recent posted moves
        moves = self.env["account.move"].search(
            [("state", "=", "posted"), ("write_date", ">=", fields.Datetime.subtract(fields.Datetime.now(), days=7))],
            limit=500,
        )
        for move in moves:
            ext.push_account_move(move.id)

        # 2. Re-push recent payments
        payments = self.env["account.payment"].search(
            [("state", "=", "posted"), ("write_date", ">=", fields.Datetime.subtract(fields.Datetime.now(), days=7))],
            limit=500,
        )
        for payment in payments:
            ext.push_payment(payment.id)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("تمت إعادة المزامنة"),
                "message": _(
                    "تمت إعادة مزامنة %d فاتورة و %d دفعة مع Nexus Core."
                ) % (len(moves), len(payments)),
                "type": "success",
                "sticky": False,
            },
        }
