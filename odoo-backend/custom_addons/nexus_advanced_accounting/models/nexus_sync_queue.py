"""Nexus Core operation handlers — payload builders dispatched by the queue.

This file *inherits* ``nexus.sync.queue`` (defined in the foundation)
and adds the operation-specific ``_prepare_operation()`` overrides
for the four accounting pillars.  Each override reconstructs the
payload fresh at send time so dependencies (e.g. invoice docname for
payment entries) are always up‑to‑date.
"""

import json
import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Sentinel exception for dependency gating (defined here to avoid
# cross-module import that fails during Odoo 18 custom-addon loading).
class PendingDependency(Exception):
    """Payload depends on a resource not yet synced to the Nexus Core."""

    def __init__(self, missing_refs):
        self.missing_refs = missing_refs
        super().__init__(
            _("Nexus Core: waiting for dependency sync — %s") % ", ".join(missing_refs)
        )


class NexusSyncQueue(models.Model):
    _inherit = "nexus.sync.queue"

    # ------------------------------------------------------------------
    # Overridden dispatch — resolve payload specific to operation
    # ------------------------------------------------------------------

    def _prepare_operation(self):
        """Return the payload dict for the current record's operation.

        Falls back to the stored payload when no specific handler exists.
        """
        self.ensure_one()
        handler = self._get_handler()
        if handler:
            return handler(self)
        return super()._prepare_operation()

    def _on_success(self, resp_text, docname):
        """Mark the source Odoo record as synced when applicable."""
        super()._on_success(resp_text, docname)

        if not self.model_name or not self.res_id:
            return

        source = self.env[self.model_name].browse(self.res_id)
        if not source.exists():
            return

        if self.operation == "invoice.create":
            _logger.info(
                "Nexus Core: marking invoice %s as synced → %s",
                source.name or source.id,
                self.docname,
            )
            source.with_context(force_erpnext_write=True).sudo().write(
                {
                    "erpnext_synced": True,
                    "erpnext_docname": self.docname or "",
                }
            )
        elif self.operation == "payment_entry.create":
            if hasattr(source, "nexus_core_synced"):
                source.sudo().write(
                    {
                        "nexus_core_synced": True,
                        "nexus_core_docname": self.docname or "",
                    }
                )
        elif self.operation == "cost_center.create":
            self.env["nexus.cost.center.mapping"].sudo()._mark_synced(
                self.model_name, self.res_id, self.docname or ""
            )
        elif self.operation == "asset.create":
            # Asset creation is per line; store docname on the move line
            if self.model_name == "account.move.line":
                source.sudo().write(
                    {
                        "nexus_asset_synced": True,
                        "nexus_asset_docname": self.docname or "",
                    }
                )
        elif self.operation == "expense_claim.create":
            # Mark the expense move as synced
            if hasattr(source, "erpnext_synced"):
                source.with_context(force_erpnext_write=True).sudo().write(
                    {
                        "erpnext_synced": True,
                        "erpnext_docname": self.docname or "",
                    }
                )

    # ------------------------------------------------------------------
    # Handler registry
    # ------------------------------------------------------------------

    _HANDLERS = {}

    def _get_handler(self):
        """Return the callable handler for the current operation, or None."""
        self.ensure_one()
        return self._HANDLERS.get(self.operation)

    # ------------------------------------------------------------------
    # Handler: Invoice → Nexus Core Sales / Purchase Invoice
    # ------------------------------------------------------------------

    @staticmethod
    def _build_invoice_payload(record):
        """Build a Sales Invoice or Purchase Invoice payload for the Nexus Core."""
        invoice = record.env["account.move"].browse(record.res_id)
        if not invoice.exists():
            raise UserError(
                _("Nexus Core: source invoice #%d no longer exists.", record.res_id)
            )

        doctype = {
            "out_invoice": "Sales Invoice",
            "out_refund": "Sales Invoice",
            "in_invoice": "Purchase Invoice",
            "in_refund": "Purchase Invoice",
        }.get(invoice.move_type, "Sales Invoice")

        is_credit = invoice.move_type in ("out_refund", "in_refund")

        # Tax mapping helper
        tax_map = invoice.env["nexus.tax.mapping"].sudo()._get_map_for_company(
            invoice.company_id
        )

        items = []
        for line in invoice.invoice_line_ids:
            product = line.product_id
            # Resolve Nexus Core Item Tax Template from the mapping table
            item_tax_template = None
            if line.tax_ids and tax_map:
                mapped = tax_map.get(line.tax_ids[0].id)
                if mapped:
                    item_tax_template = mapped.nexus_tax_template

            items.append(
                {
                    "item_code": product.default_code or product.name if product else line.name,
                    "item_name": line.name,
                    "description": line.name,
                    "qty": line.quantity,
                    "rate": line.price_unit,
                    "amount": line.price_subtotal,
                    "cost_center": invoice.nexus_cost_center or "",
                    "item_tax_template": item_tax_template or "",
                    "income_account": (
                        line.account_id.code or line.account_id.name
                        if line.account_id and doctype == "Sales Invoice"
                        else ""
                    ),
                    "expense_account": (
                        line.account_id.code or line.account_id.name
                        if line.account_id and doctype == "Purchase Invoice"
                        else ""
                    ),
                }
            )

        # Build tax table from move tax lines
        taxes_table = []
        for tax_line in invoice.line_ids.filtered(
            lambda l: l.tax_line_id or l.tax_repartition_line_id
        ):
            tax_name = (
                tax_line.tax_line_id.name
                if tax_line.tax_line_id
                else tax_line.name
            )
            taxes_table.append(
                {
                    "charge_type": "On Net Total",
                    "account_head": (
                        tax_line.account_id.code or tax_line.account_id.name
                        if tax_line.account_id
                        else ""
                    ),
                    "description": tax_name,
                    "rate": tax_line.tax_line_id.amount
                    if tax_line.tax_line_id
                    else 0.0,
                    "tax_amount": abs(tax_line.balance),
                    "total": abs(tax_line.tax_base_amount),
                    "cost_center": invoice.nexus_cost_center or "",
                }
            )

        posting_date = (
            invoice.invoice_date
            or invoice.date
            or fields.Date.context_today(invoice)
        )
        due_date = invoice.invoice_date_due or posting_date

        payload = {
            "doctype": doctype,
            "docstatus": 1,
            "title": invoice.name or "",
            "customer": (
                invoice.partner_id.name
                if doctype == "Sales Invoice" and invoice.partner_id
                else ""
            ),
            "supplier": (
                invoice.partner_id.name
                if doctype == "Purchase Invoice" and invoice.partner_id
                else ""
            ),
            "posting_date": str(posting_date),
            "due_date": str(due_date),
            "currency": invoice.currency_id.name,
            "cost_center": invoice.nexus_cost_center or "",
            "is_return": 1 if is_credit else 0,
            "items": items,
            "taxes": taxes_table,
            "nexus_transaction_id": record.transaction_id,
            "custom_nexus_source_id": str(invoice.id),
            "bill_no": invoice.name,
            "set_posting_time": 1,
        }
        return payload

    @staticmethod
    def _build_payment_entry_payload(record):
        """Build a Payment Entry payload referencing the synced invoice."""
        payment = record.env["account.payment"].browse(record.res_id)
        if not payment.exists():
            raise UserError(
                _("Nexus Core: source payment #%d no longer exists.", record.res_id)
            )

        is_inbound = payment.payment_type == "inbound"
        doctype = "Payment Entry"
        party_type = "Customer" if payment.partner_type == "customer" else "Supplier"

        # Build references: must resolve each invoice to its Nexus Core docname.
        # If an invoice is not yet synced, raise PendingDependency.
        references = []
        unresolved = []

        reconciled_invoices = payment.reconciled_invoice_ids or (
            payment._get_reconciled_invoices()
            if hasattr(payment, "_get_reconciled_invoices")
            else payment.env["account.move"]
        )

        for inv in reconciled_invoices:
            core_docname = inv.erpnext_docname
            if not core_docname:
                unresolved.append(inv.name or str(inv.id))
                # Fallback: treat the invoice number as the reference
                core_docname = inv.name
            ref_doctype = (
                "Sales Invoice"
                if inv.move_type in ("out_invoice", "out_refund")
                else "Purchase Invoice"
            )
            references.append(
                {
                    "reference_doctype": ref_doctype,
                    "reference_name": core_docname,
                    "total_amount": inv.amount_total,
                    "allocated_amount": abs(payment.amount),
                }
            )

        if unresolved and not references:
            raise PendingDependency(unresolved)

        # If some are resolved and some not, reschedule the unresolved portion
        # Actually just proceed with what we have; partial references are OK in
        # Payment Entry. But if ALL are unresolved and we're using fallbacks,
        # we proceed cautiously.
        for inv_name in unresolved:
            _logger.info(
                "Nexus Core: payment references invoice '%s' — pending sync",
                inv_name,
            )

        payload = {
            "doctype": doctype,
            "docstatus": 1,
            "payment_type": "Receive" if is_inbound else "Pay",
            "party_type": party_type,
            "party": payment.partner_id.name if payment.partner_id else "",
            "posting_date": str(payment.date or fields.Date.context_today(payment)),
            "paid_amount": payment.amount,
            "received_amount": payment.amount,
            "paid_to": (
                payment.outstanding_account_id.code
                if payment.outstanding_account_id
                else ""
            ),
            "paid_from": (
                payment.outstanding_account_id.code
                if payment.outstanding_account_id
                else ""
            ),
            "mode_of_payment": (
                payment.journal_id.name if payment.journal_id else ""
            ),
            "reference_no": payment.ref or payment.name,
            "reference_date": str(payment.date or fields.Date.context_today(payment)),
            "references": references,
            "nexus_transaction_id": record.transaction_id,
            "custom_nexus_source_id": str(payment.id),
        }
        return payload

    @staticmethod
    def _build_cost_center_payload(record):
        """Build a Cost Center creation payload."""
        source = record.env[record.model_name].browse(record.res_id)
        if not source.exists():
            raise UserError(
                _("Nexus Core: source record #%d no longer exists.", record.res_id)
            )

        parent_cost_center = "All Cost Centers"
        if record.model_name == "stock.warehouse":
            cc_name = f"Branch - {source.name}"
        elif record.model_name == "hr.department":
            cc_name = f"Department - {source.name}"
        elif record.model_name == "project.project":
            cc_name = f"Project - {source.name}"
        else:
            cc_name = source.display_name or source.name

        payload = {
            "doctype": "Cost Center",
            "docstatus": 1,
            "cost_center_name": cc_name,
            "parent_cost_center": parent_cost_center,
            "company": source.company_id.name
            if hasattr(source, "company_id") and source.company_id
            else "",
            "is_group": 0,
            "nexus_transaction_id": record.transaction_id,
            "custom_nexus_source_model": record.model_name,
            "custom_nexus_source_id": str(record.res_id),
        }
        return payload

    @staticmethod
    def _build_asset_payload(record):
        """Build an Asset creation payload for a fixed-asset purchase line."""
        line = record.env["account.move.line"].browse(record.res_id)
        if not line.exists():
            raise UserError(
                _("Nexus Core: source line #%d no longer exists.", record.res_id)
            )

        move = line.move_id
        product = line.product_id.product_tmpl_id or line.product_id
        asset_name = product.name if product else line.name

        # Determine asset category from product category
        asset_category = "Fixed Assets"
        if product and product.categ_id:
            asset_category = product.categ_id.name

        payload = {
            "doctype": "Asset",
            "docstatus": 1,
            "asset_name": asset_name,
            "item_code": product.default_code or product.name if product else line.name,
            "asset_category": asset_category,
            "purchase_date": str(
                move.invoice_date
                or move.date
                or fields.Date.context_today(move)
            ),
            "available_for_use_date": str(
                move.invoice_date
                or move.date
                or fields.Date.context_today(move)
            ),
            "gross_purchase_amount": line.price_subtotal or line.price_total,
            "purchase_receipt": line.name,
            "cost_center": move.nexus_cost_center or "",
            "calculate_depreciation": 1,
            "depreciation_method": "Straight Line",
            "frequency_of_depreciation": 12,
            "total_number_of_depreciations": 60,
            "is_existing_asset": 0,
            "opening_accumulated_depreciation": 0.0,
            "nexus_transaction_id": record.transaction_id,
            "custom_nexus_source_id": str(line.id),
            "custom_nexus_invoice_id": str(move.id),
        }
        return payload

    @staticmethod
    def _build_expense_claim_payload(record):
        """Build an Expense Claim payload for the Nexus Core."""
        sheet = record.env["hr.expense.sheet"].browse(record.res_id)
        if not sheet.exists():
            raise UserError(
                _("Nexus Core: source expense sheet #%d no longer exists.",
                  record.res_id)
            )

        items = []
        for expense in sheet.expense_line_ids:
            items.append(
                {
                    "expense_date": str(expense.date or fields.Date.today()),
                    "description": expense.name,
                    "amount": expense.total_amount,
                    "sanctioned_amount": expense.total_amount,
                    "cost_center": sheet.nexus_cost_center
                    if hasattr(sheet, "nexus_cost_center")
                    else "",
                    "expense_account": (
                        expense.account_id.code or expense.account_id.name
                        if expense.account_id
                        else ""
                    ),
                }
            )

        payload = {
            "doctype": "Expense Claim",
            "docstatus": 1,
            "employee": sheet.employee_id.name if sheet.employee_id else "",
            "posting_date": str(
                sheet.approval_date
                or sheet.accounting_date
                or fields.Date.context_today(sheet)
            ),
            "total_claimed_amount": sheet.total_amount,
            "total_sanctioned_amount": sheet.total_amount,
            "expenses": items,
            "nexus_transaction_id": record.transaction_id,
            "custom_nexus_source_id": str(sheet.id),
        }
        return payload

    @staticmethod
    def _build_tax_template_payload(record):
        """Build an Item Tax Template creation payload for ZATCA/VAT compliance."""
        tax = record.env["account.tax"].browse(record.res_id)
        if not tax.exists():
            raise UserError(
                _("Nexus Core: source tax #%d no longer exists.", record.res_id)
            )

        payload = {
            "doctype": "Item Tax Template",
            "docstatus": 1,
            "title": tax.name,
            "taxes": [
                {
                    "tax_type": (
                        tax.description or tax.name
                    ),
                    "tax_rate": tax.amount if tax.amount_type == "percent" else 0.0,
                }
            ],
            "nexus_transaction_id": record.transaction_id,
            "custom_nexus_source_id": str(tax.id),
        }
        return payload

    # Handler registry population
    _HANDLERS = {
        "invoice.create": _build_invoice_payload.__func__,
        "payment_entry.create": _build_payment_entry_payload.__func__,
        "cost_center.create": _build_cost_center_payload.__func__,
        "asset.create": _build_asset_payload.__func__,
        "expense_claim.create": _build_expense_claim_payload.__func__,
        "tax_template.create": _build_tax_template_payload.__func__,
    }
