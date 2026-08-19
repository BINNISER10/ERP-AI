# -*- coding: utf-8 -*-
"""Nexus ERPNext Bridge Extensions — توسيع الجسر لكافة الكيانات.

Extends the base ``nexus.erpnext.bridge`` with concrete push
operations for:
    * Customer / Supplier (``res.partner``)
    * Product / Item (``product.product``)
    * Payment Entry (``account.payment``)
    * Fixed Asset (``account.asset``)
    * Warehouse (``stock.warehouse``)
    * Tax Template (``account.tax``)
    * Cost Center (``account.analytic.account``)

Each push follows the same idempotency pattern via
``nexus.sync.queue`` — synchronous failure → enqueue for retry.
"""

import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NexusERPNextBridgeExtensions(models.AbstractModel):
    """Additional bridge methods for non-move entities."""

    _name = "nexus.erpnext.bridge.extensions"
    _description = "Nexus ↔ ERPNext Bridge Extensions"

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────
    def _base_bridge(self):
        return self.env["nexus.erpnext.bridge"]

    def _enqueue(self, operation, payload, resource, record=None):
        """Enqueue a failed push for retry."""
        company = (
            record.company_id
            if record is not None and hasattr(record, "company_id") and record.company_id
            else self.env.company
        )
        return self.env["nexus.sync.queue"].enqueue(
            operation=operation,
            payload=payload,
            endpoint=resource,
            company=company,
            model_name=record._name if record is not None else None,
            res_id=record.id if record is not None else None,
        )

    def _safe_push(self, operation, payload, resource, *, record, success_message=None):
        """Try a synchronous push; fall back to the queue on failure."""
        bridge = self._base_bridge()
        if not bridge.is_configured():
            return self._enqueue(operation, payload, resource, record=record)
        try:
            result = bridge._request("POST", resource, json_body=payload)
            erpnext_name = (result.get("data") or {}).get("name")
            if erpnext_name and hasattr(record, "nexus_erpnext_id"):
                record.write({"nexus_erpnext_id": erpnext_name})
            if success_message:
                _logger.info(success_message, erpnext_name)
            return True
        except UserError:
            self._enqueue(operation, payload, resource, record=record)
            return False
        except Exception as exc:
            _logger.warning("Bridge push failed (%s): %s", operation, exc)
            self._enqueue(operation, payload, resource, record=record)
            return False

    # ═══════════════════════════════════════════════════════════════════
    # Invoice / Bill (delegates to the base bridge)
    # ═══════════════════════════════════════════════════════════════════
    def push_account_move(self, move_id):
        """Push a posted account.move via the base bridge implementation."""
        return self._base_bridge().push_account_move(move_id)

    # ─────────────────────────────────────────────────────────────────
    # Customer / Supplier
    # ═══════════════════════════════════════════════════════════════════
    def push_partner(self, partner_id):
        """Push a res.partner to ERPNext as Customer or Supplier."""
        partner = self.env["res.partner"].browse(partner_id)
        if not partner.exists():
            return False

        if partner.supplier_rank and not partner.customer_rank:
            resource = "/api/resource/Supplier"
        elif partner.customer_rank and not partner.supplier_rank:
            resource = "/api/resource/Customer"
        else:
            resource = (
                "/api/resource/Customer"
                if partner.customer_rank >= partner.supplier_rank
                else "/api/resource/Supplier"
            )

        payload = {
            "doctype": "Customer" if "Customer" in resource else "Supplier",
            "customer_name" if "Customer" in resource else "supplier_name":
                partner.name,
            "company": self.env.company.name,
            "tax_id": partner.vat or "",
            "default_currency": (
                partner.property_product_pricelist.currency_id.name
                if partner.property_product_pricelist
                else self.env.company.currency_id.name
            ),
            "email_id": partner.email or "",
            "mobile_no": partner.mobile or "",
            "phone": partner.phone or "",
            "address_line1": partner.street or "",
            "city": partner.city or "",
            "country": partner.country_id.name if partner.country_id else "",
            "pincode": partner.zip or "",
            "is_internal_supplier": False,
        }

        return self._safe_push(
            operation="res.partner.push",
            payload=payload,
            resource=resource,
            record=partner,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Product / Item
    # ═══════════════════════════════════════════════════════════════════
    def push_product(self, product_id):
        """Push a product.product to ERPNext as Item."""
        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            return False

        is_fixed_asset = getattr(product, "is_fixed_asset", False)
        item_group = self._get_or_create_item_group(product.categ_id)

        payload = {
            "doctype": "Item",
            "item_code": product.default_code or product.name,
            "item_name": product.name,
            "item_group": item_group,
            "stock_uom": product.uom_id.name if product.uom_id else "Nos",
            "is_stock_item": product.type == "product",
            "is_fixed_asset": is_fixed_asset,
            "is_sales_item": product.sale_ok,
            "is_purchase_item": product.purchase_ok,
            "standard_rate": product.standard_price,
            "valuation_rate": product.standard_price,
            "description": product.description_sale or "",
            "company": self.env.company.name,
        }

        return self._safe_push(
            operation="product.product.push",
            payload=payload,
            resource="/api/resource/Item",
            record=product,
        )

    def _get_or_create_item_group(self, category):
        """Map product.category to an ERPNext Item Group name (cached)."""
        if not category:
            return "All Item Groups"
        # The simplest mapping: name passthrough. ERPNext will create
        # the group if it doesn't exist when sync runs.
        return category.name.replace("/", "-")[:140]

    # ═══════════════════════════════════════════════════════════════════
    # Payment Entry
    # ═══════════════════════════════════════════════════════════════════
    def push_payment(self, payment_id):
        """Push account.payment to ERPNext as Payment Entry."""
        payment = self.env["account.payment"].browse(payment_id)
        if not payment.exists() or payment.state != "posted":
            return False

        is_outbound = payment.payment_type == "outbound"
        is_internal = payment.payment_type == "transfer"

        payload = {
            "doctype": "Payment Entry",
            "company": self.env.company.name,
            "posting_date": str(payment.date),
            "payment_type": (
                "Pay" if is_outbound
                else "Receive" if payment.payment_type == "inbound"
                else "Internal Transfer"
            ),
            "party_type": (
                "Supplier" if is_outbound
                else "Customer" if payment.payment_type == "inbound"
                else ""
            ),
            "party": (
                payment.partner_id.name
                if payment.payment_type in ("inbound", "outbound")
                else ""
            ),
            "paid_from": (
                payment.journal_id.display_name
                if payment.payment_type == "inbound"
                else payment.journal_id.display_name
            ),
            "paid_to": (
                payment.journal_id.display_name
                if payment.payment_type == "outbound"
                else payment.journal_id.display_name
            ),
            "paid_amount": payment.amount,
            "received_amount": payment.amount,
            "source_exchange_rate": 1.0,
            "target_exchange_rate": 1.0,
            "reference_no": payment.name,
            "reference_date": str(payment.date),
            "mode_of_payment": payment.payment_method_line_id.name
            if payment.payment_method_line_id
            else "",
        }

        # Add allocations against outstanding invoices
        allocations = []
        for line in payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in (
                "asset_receivable",
                "liability_payable",
            )
        ):
            allocations.append({
                "reference_doctype": "Sales Invoice" if line.account_id.account_type == "asset_receivable"
                else "Purchase Invoice",
                "reference_name": line.move_id.name,
                "allocated_amount": abs(line.amount_residual),
            })
        if allocations:
            payload["references"] = allocations

        return self._safe_push(
            operation="account.payment.push",
            payload=payload,
            resource="/api/resource/Payment Entry",
            record=payment,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Fixed Asset
    # ═══════════════════════════════════════════════════════════════════
    def push_asset(self, asset_id):
        """Push account.asset to ERPNext as Asset."""
        asset = self.env["account.asset"].browse(asset_id)
        if not asset.exists():
            return False

        payload = {
            "doctype": "Asset",
            "company": self.env.company.name,
            "asset_name": asset.name,
            "item_code": (
                asset.original_move_line_id.product_id.default_code
                if asset.original_move_line_id
                else ""
            ),
            "asset_category": (
                asset.asset_category_id.name
                if hasattr(asset, "asset_category_id") and asset.asset_category_id
                else "Default"
            ),
            "purchase_date": str(asset.acquisition_date),
            "gross_purchase_amount": asset.original_value,
            "available_for_use_date": str(asset.acquisition_date),
            "total_depreciations": asset.already_depreciated_amount,
            "current_value": asset.book_value,
            "depreciation_method": (
                "Straight Line" if asset.method == "linear"
                else "Written Down Value"
            ),
            "total_number_of_depreciations": asset.method_number,
            "frequency_of_depreciation": (
                "Monthly" if asset.method_period == "1"
                else "Quarterly" if asset.method_period == "3"
                else "Yearly"
            ),
        }

        return self._safe_push(
            operation="account.asset.push",
            payload=payload,
            resource="/api/resource/Asset",
            record=asset,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Warehouse
    # ═══════════════════════════════════════════════════════════════════
    def push_warehouse(self, warehouse_id):
        """Push stock.warehouse to ERPNext as Warehouse."""
        warehouse = self.env["stock.warehouse"].browse(warehouse_id)
        if not warehouse.exists():
            return False

        payload = {
            "doctype": "Warehouse",
            "warehouse_name": warehouse.name,
            "company": warehouse.company_id.name,
            "warehouse_type": (
                "Finished Goods" if warehouse.wh_type == "finished"
                else "Raw Material" if warehouse.wh_type == "raw"
                else "Stores"
            ),
            "is_group": False,
            "parent_warehouse": (
                warehouse.view_location_id.display_name
                if warehouse.view_location_id
                else "All Warehouses"
            ),
            "address_line1": warehouse.partner_id.street if warehouse.partner_id else "",
            "city": warehouse.partner_id.city if warehouse.partner_id else "",
        }

        return self._safe_push(
            operation="stock.warehouse.push",
            payload=payload,
            resource="/api/resource/Warehouse",
            record=warehouse,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Cost Center
    # ═══════════════════════════════════════════════════════════════════
    def push_cost_center(self, analytic_account_id):
        """Push account.analytic.account to ERPNext as Cost Center."""
        aa = self.env["account.analytic.account"].browse(analytic_account_id)
        if not aa.exists():
            return False

        payload = {
            "doctype": "Cost Center",
            "cost_center_name": aa.name,
            "company": (
                aa.company_id.name
                if aa.company_id
                else self.env.company.name
            ),
            "is_group": aa.parent_id is False and aa.child_ids,
            "parent_cost_center": aa.parent_id.name if aa.parent_id else "",
        }

        return self._safe_push(
            operation="account.analytic.account.push",
            payload=payload,
            resource="/api/resource/Cost Center",
            record=aa,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Tax Item Template
    # ═══════════════════════════════════════════════════════════════════
    def push_tax(self, tax_id):
        """Push account.tax to ERPNext as Item Tax Template."""
        tax = self.env["account.tax"].browse(tax_id)
        if not tax.exists():
            return False

        payload = {
            "doctype": "Item Tax Template",
            "title": tax.name,
            "company": self.env.company.name,
            "taxes": [
                {
                    "tax_type": self._map_tax_type(tax),
                    "rate": tax.amount,
                }
            ],
        }

        return self._safe_push(
            operation="account.tax.push",
            payload=payload,
            resource="/api/resource/Item Tax Template",
            record=tax,
        )

    def _map_tax_type(self, tax):
        """Best-effort Odoo tax → ERPNext Account mapping."""
        if tax.country_code == "SA":
            return "VAT - " + self.env.company.name
        if tax.country_code == "US":
            return "Sales Tax - " + self.env.company.name
        return "Standard Tax - " + self.env.company.name

    # ═══════════════════════════════════════════════════════════════════
    # Chart of Accounts (one-shot setup)
    # �══════════════════════════════════════════════════════════════════
    def push_account(self, account_id):
        """Push account.account to ERPNext as Account."""
        account = self.env["account.account"].browse(account_id)
        if not account.exists():
            return False

        payload = {
            "doctype": "Account",
            "company": self.env.company.name,
            "account_name": account.name,
            "account_number": account.code,
            "account_type": self._map_account_type(account.account_type),
            "account_currency": (
                account.currency_id.name
                if account.currency_id
                else self.env.company.currency_id.name
            ),
            "is_group": bool(getattr(account, "is_group", False)),
            "root_type": self._map_root_type(account.account_type),
            "parent_account": account.parent_id.code if account.parent_id else "",
        }

        return self._safe_push(
            operation="account.account.push",
            payload=payload,
            resource="/api/resource/Account",
            record=account,
        )

    def _map_account_type(self, odoo_type):
        """Best-effort Odoo account.account_type → ERPNext account_type."""
        return {
            "asset_receivable": "Receivable",
            "asset_cash": "Cash",
            "asset_current": "Current Asset",
            "asset_non_current": "Fixed Asset",
            "asset_prepayment": "Current Asset",
            "asset_fixed": "Fixed Asset",
            "liability_payable": "Payable",
            "liability_current": "Current Liability",
            "liability_non_current": "Non-Current Liability",
            "equity": "Equity",
            "equity_unaffected": "Equity",
            "income": "Income Account",
            "income_other": "Income Account",
            "expense": "Expense Account",
            "expense_depreciation": "Depreciation",
            "expense_direct_cost": "Cost of Goods Sold",
        }.get(odoo_type, "Current Asset")

    def _map_root_type(self, odoo_type):
        return {
            "asset_receivable": "Asset",
            "asset_cash": "Asset",
            "asset_current": "Asset",
            "asset_non_current": "Asset",
            "asset_prepayment": "Asset",
            "asset_fixed": "Asset",
            "liability_payable": "Liability",
            "liability_current": "Liability",
            "liability_non_current": "Liability",
            "equity": "Equity",
            "equity_unaffected": "Equity",
            "income": "Income",
            "income_other": "Income",
            "expense": "Expense",
            "expense_depreciation": "Expense",
            "expense_direct_cost": "Expense",
        }.get(odoo_type, "Asset")
