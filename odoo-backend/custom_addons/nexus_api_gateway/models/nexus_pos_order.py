"""Nexus POS order model used by the Flutter POS gateway.

This model accepts a JSON payload from the offline-first Flutter app
and turns it into a confirmed sale order with an optional stock
picking.
"""
import json
import uuid
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class NexusPosOrder(models.Model):
    _name = "nexus.pos.order"
    _description = "Nexus POS Order"
    _order = "id desc"

    name = fields.Char(string="POS Order Ref", required=True, default=lambda self: _("New"), copy=False, readonly=True)
    client_order_ref = fields.Char(string="Client Reference", index=True)
    order_date = fields.Datetime(string="Order Date", required=True, default=fields.Datetime.now)
    partner_id = fields.Many2one("res.partner", string="Customer", default=lambda self: self.env.ref("base.public_partner").id)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True, readonly=True)
    user_id = fields.Many2one("res.users", string="Cashier", default=lambda self: self.env.user)
    state = fields.Selection(
        [("draft", "Draft"), ("posted", "Posted"), ("cancelled", "Cancelled")],
        string="Status",
        default="draft",
    )
    amount_total = fields.Monetary(string="Total", currency_field="currency_id")
    amount_tax = fields.Monetary(string="Tax", currency_field="currency_id")
    note = fields.Text(string="Notes")
    raw_payload = fields.Text(string="Raw Payload")
    sale_order_id = fields.Many2one("sale.order", string="Sale Order", readonly=True, copy=False)
    line_ids = fields.One2many("nexus.pos.order.line", "order_id", string="Lines")

    _sql_constraints = [
        (
            "client_order_ref_company_uniq",
            "unique(client_order_ref, company_id)",
            "Duplicate client order reference is not allowed per company.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("nexus.pos.order") or _("New")
        return super(NexusPosOrder, self).create(vals_list)

    @api.model
    def create_pos_order(self, payload):
        """Create a Nexus POS order and its underlying sale order from a JSON payload (Idempotent)."""
        if not isinstance(payload, dict):
            raise ValidationError("Order payload must be a dictionary.")

        # 1. Company Security Scoping
        requested_company_id = payload.get("company_id")
        user = self.env.user
        if requested_company_id:
            if requested_company_id not in user.company_ids.ids:
                raise AccessError(_("You are not authorized to create orders for this company."))
            company = self.env["res.company"].browse(requested_company_id)
        else:
            company = user.company_id

        # 2. Idempotency Check (H-1)
        client_ref = payload.get("client_order_ref")
        if client_ref:
            existing = self.search([
                ("client_order_ref", "=", client_ref),
                ("company_id", "=", company.id),
            ], limit=1)
            if existing:
                _logger.info("POS Idempotency: returning existing order %s for ref %s", existing.name, client_ref)
                return {
                    "order_id": existing.id,
                    "name": existing.name,
                    "sale_order_id": existing.sale_order_id.id if existing.sale_order_id else False,
                    "idempotent": True,
                }

        partner = self._resolve_partner(payload)
        lines = payload.get("lines", [])
        if not lines:
            raise ValidationError("Order payload must contain at least one line.")

        order_vals = {
            "client_order_ref": client_ref or str(uuid.uuid4()),
            "order_date": payload.get("order_date") or fields.Datetime.now(),
            "partner_id": partner.id,
            "company_id": company.id,
            "user_id": user.id,
            "note": payload.get("note", ""),
            "raw_payload": json.dumps(payload),
        }

        order = self.create(order_vals)
        line_records = self.env["nexus.pos.order.line"]

        amount_untaxed = 0.0
        amount_tax = 0.0
        sale_lines = []

        for line in lines:
            product_id = line.get("product_id")
            qty = line.get("quantity") or 1.0
            price = line.get("price_unit") or 0.0
            discount = line.get("discount") or 0.0
            tax_ids = line.get("tax_ids", [])
            modifiers = line.get("modifiers", {})

            product = self.env["product.product"].with_company(company).browse(product_id)
            if not product.exists():
                raise UserError(f"Product {product_id} not found.")

            price_unit = (price or product.lst_price) * (1 - discount / 100.0)
            subtotal = price_unit * qty

            taxes = self.env["account.tax"].with_company(company).browse(tax_ids)
            tax_values = taxes.compute_all(
                price_unit,
                currency=order.currency_id,
                quantity=qty,
                product=product,
                partner=partner,
            )
            line_tax = sum(t.get("amount", 0.0) for t in tax_values.get("taxes", []))
            line_total = tax_values.get("total_included", subtotal)

            amount_untaxed += tax_values.get("total_excluded", subtotal)
            amount_tax += line_tax

            line_records.create(
                {
                    "order_id": order.id,
                    "product_id": product.id,
                    "name": product.name,
                    "quantity": qty,
                    "price_unit": price_unit,
                    "discount": discount,
                    "tax_ids": [(6, 0, tax_ids)],
                    "subtotal": subtotal,
                    "price_total": line_total,
                    "modifiers": json.dumps(modifiers) if modifiers else False,
                }
            )

            sale_lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": price or product.lst_price,
                        "discount": discount,
                        "tax_id": [(6, 0, tax_ids)],
                    },
                )
            )

        order.write(
            {
                "amount_total": amount_untaxed + amount_tax,
                "amount_tax": amount_tax,
            }
        )

        # Create underlying sale order for stock/MRP consumption and accounting
        sale_order = self.env["sale.order"].with_company(company).create(
            {
                "partner_id": partner.id,
                "client_order_ref": order.client_order_ref,
                "company_id": company.id,
                "user_id": order.user_id.id,
                "note": order.note,
                "order_line": sale_lines,
            }
        )
        sale_order.action_confirm()

        order.write({"sale_order_id": sale_order.id, "state": "posted"})

        return {"order_id": order.id, "name": order.name, "sale_order_id": sale_order.id}

        # Recipe costing consumption is triggered inside action_confirm() via the
        # nexus_restaurant_costing sale.order override. Do NOT call
        # consume_for_sale_order() again here (would double-consume stock).

        return {"order_id": order.id, "name": order.name, "sale_order_id": sale_order.id}

    def _resolve_partner(self, payload):
        partner_id = payload.get("partner_id")
        if partner_id:
            partner = self.env["res.partner"].browse(partner_id)
            if partner.exists():
                return partner
        return self.env.ref("base.public_partner")


class NexusPosOrderLine(models.Model):
    _name = "nexus.pos.order.line"
    _description = "Nexus POS Order Line"

    order_id = fields.Many2one("nexus.pos.order", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True)
    name = fields.Char(string="Description")
    quantity = fields.Float(string="Quantity", default=1.0)
    price_unit = fields.Float(string="Unit Price", digits=(16, 4))
    discount = fields.Float(string="Discount %", default=0.0)
    tax_ids = fields.Many2many("account.tax", string="Taxes")
    subtotal = fields.Float(string="Subtotal", digits=(16, 4))
    price_total = fields.Float(string="Total", digits=(16, 4))
    modifiers = fields.Text(string="Modifiers JSON")
