"""Invoice sync bridge + cost center enrichment.

When an invoice is posted in the Nexus Command Center, it is queued
for creation in the Nexus Core.  Every invoice line includes the
correct cost center and item tax template for deep P&L and ZATCA
compliance.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

MOVE_TYPES_TO_SYNC = (
    "out_invoice",
    "out_refund",
    "in_invoice",
    "in_refund",
)


class AccountMove(models.Model):
    _inherit = "account.move"

    nexus_cost_center = fields.Char(
        string="Nexus Core Cost Center",
        copy=False,
        help="Cost center tag sent to the Nexus Core on every invoice line.",
    )

    def _post(self, soft=True):
        """Override posting to enqueue Nexus Core invoice sync when applicable."""
        moves = super()._post(soft=soft)
        for move in moves:
            # Vendor bills: check for fixed-asset lines
            if move.move_type == "in_invoice":
                move._check_and_enqueue_assets()
            # Invoice sync — skip if already synced
            if move.move_type in MOVE_TYPES_TO_SYNC and not move.erpnext_synced:
                move._enqueue_invoice_sync()
        return moves

    def _enqueue_invoice_sync(self):
        """Queue this invoice for creation in the Nexus Core."""
        self.ensure_one()

        # Resolve cost center before queueing
        if not self.nexus_cost_center:
            self._compute_nexus_cost_center_value()

        doctype_map = {
            "out_invoice": "/api/resource/Sales Invoice",
            "out_refund": "/api/resource/Sales Invoice",
            "in_invoice": "/api/resource/Purchase Invoice",
            "in_refund": "/api/resource/Purchase Invoice",
        }
        endpoint = doctype_map.get(self.move_type, "/api/resource/Sales Invoice")
        tx_id = f"NX-INV-{self.id}"

        self.env["nexus.sync.queue"].enqueue(
            operation="invoice.create",
            payload={},
            endpoint=endpoint,
            company=self.company_id,
            model_name="account.move",
            res_id=self.id,
            transaction_id=tx_id,
            priority=15,
        )
        _logger.info(
            "Nexus Core: queued invoice '%s' (%s) [%s]",
            self.name,
            self.move_type,
            tx_id[:12],
        )

    def _compute_nexus_cost_center_value(self):
        """Fallback cost center resolution when none is explicitly set."""
        for move in self:
            # Try from the related document first
            cost_center = (
                move.nexus_cost_center
                or (move.company_id.name if move.company_id else "")
            )
            # If it's a vendor bill, try warehouse/purchase order dimensions
            if move.move_type == "in_invoice" and move.purchase_id:
                po = move.purchase_id
                # Try picking type / warehouse name
                if po.picking_type_id and po.picking_type_id.warehouse_id:
                    wh = po.picking_type_id.warehouse_id
                    cost_center = f"Branch - {wh.name}"
            move.nexus_cost_center = cost_center

    # ── Asset detection: after posting a vendor bill, check for fixed asset lines ──
    def _check_and_enqueue_assets(self):
        """Scan this vendor bill for fixed-asset products and queue Nexus Core Asset creation."""
        self.ensure_one()
        if self.move_type != "in_invoice":
            return

        # Ensure a cost center is assigned so the asset payload is complete
        if not self.nexus_cost_center:
            self._compute_nexus_cost_center_value()

        for line in self.invoice_line_ids:
            product = line.product_id.product_tmpl_id or line.product_id
            if product and product.is_fixed_asset:
                self._enqueue_asset_for_line(line)

    def _enqueue_asset_for_line(self, line):
        """Queue a single asset creation in the Nexus Core."""
        line.ensure_one()
        tx_id = f"NX-ASSET-{line.id}"
        self.env["nexus.sync.queue"].enqueue(
            operation="asset.create",
            payload={},
            endpoint="/api/resource/Asset",
            company=self.company_id,
            model_name="account.move.line",
            res_id=line.id,
            transaction_id=tx_id,
            priority=18,
        )
        _logger.info(
            "Nexus Core: queued asset '%s' from vendor bill '%s' [%s]",
            line.name,
            self.name,
            tx_id[:12],
        )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    nexus_cost_center = fields.Char(
        string="Nexus Core Cost Center",
        copy=False,
        related="move_id.nexus_cost_center",
        store=True,
        readonly=False,
    )
    nexus_asset_synced = fields.Boolean(
        string="Nexus Core Asset Synced",
        default=False,
        copy=False,
    )
    nexus_asset_docname = fields.Char(
        string="Nexus Core Asset Doc Name",
        copy=False,
    )
