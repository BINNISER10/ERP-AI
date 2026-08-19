# -*- coding: utf-8 -*-
"""Nexus Saudi E-Invoice Generator — مولّد الفاتورة الإلكترونية.

Produces a UBL 2.1 compliant invoice XML that ZATCA accepts at
Phase 2. The XML structure follows the ZATCA "Invoice Data File"
specification:

    * ``cac:Invoice`` with ``cbc:ID`` and ``cbc:IssueDate``
    * ``cac:AccountingSupplierParty`` / ``cac:AccountingCustomerParty``
    * ``cac:TaxTotal`` with ``cac:TaxSubtotal`` for VAT
    * ``cac:LegalMonetaryTotal`` for amounts

The signing chain (hash + CSID) is delegated to
``zatca.hasher.canonicalize_and_hash`` and the ``res.company``'s
stored ``nexus.last_invoice_hash``.
"""

import base64
import hashlib
import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NexusSaudiEInvoice(models.TransientModel):
    """Build a ZATCA-UBL invoice payload + signing chain."""

    _name = "nexus.saudi.einvoice"
    _description = "Nexus Saudi E-Invoice Generator"

    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        domain=[
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
        ],
    )

    xml_payload = fields.Text(string="Invoice XML (UBL 2.1)", readonly=True)
    invoice_hash = fields.Char(string="Invoice Hash (Base64)", readonly=True)
    qr_tlv = fields.Char(string="QR TLV Payload", readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("signed", "Signed")],
        default="draft",
    )

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────
    def action_generate(self):
        for rec in self:
            payload = self._build_xml(rec.invoice_id)
            invoice_hash = self._hash_xml(payload)
            qr_tlv = self.env["nexus.saudi.zatca.qr"].compute_for_invoice(
                rec.invoice_id.id
            )
            rec.write({
                "xml_payload": payload,
                "invoice_hash": invoice_hash,
                "qr_tlv": qr_tlv,
                "state": "signed",
            })
            # Update chain on the company
            settings = self.env["nexus.saudi.company.settings"].get_for_company(
                rec.invoice_id.company_id
            )
            settings.write({
                "zatca_last_invoice_hash": invoice_hash,
            })
            # Persist hash on the move for audit
            rec.invoice_id.write({
                "zatca_invoice_hash": invoice_hash,
            })
        return True

    # ─────────────────────────────────────────────────────────────────
    # Internal builders
    # ─────────────────────────────────────────────────────────────────
    def _build_xml(self, move):
        """Compose the UBL 2.1 invoice XML body."""
        from lxml import etree

        nsmap = {
            "cac": "urn:oasis:names:specification:ubl:cac:2.1",
            "cbc": "urn:oasis:names:specification:ubl:cbc:2.1",
            "ext": "urn:oasis:names:specification:ubl:dsig:2.1",
        }
        invoice = etree.Element(
            "{urn:oasis:names:specification:ubl:cac:2.1}Invoice",
            nsmap=nsmap,
        )
        # Header
        etree.SubElement(invoice, "{urn:oasis:names:specification:ubl:cbc:2.1}ID").text = (
            move.name or ""
        )
        etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cbc:2.1}IssueDate"
        ).text = str(move.invoice_date or "")
        etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cbc:2.1}DocumentCurrencyCode"
        ).text = move.currency_id.name

        # Supplier party
        supplier = etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cac:2.1}AccountingSupplierParty"
        )
        party_s = etree.SubElement(
            supplier, "{urn:oasis:names:specification:ubl:cac:2.1}Party"
        )
        etree.SubElement(
            party_s, "{urn:oasis:names:specification:ubl:cac:2.1}PartyIdentification"
        ).append(self._id_node(move.company_id.vat or ""))
        etree.SubElement(
            party_s, "{urn:oasis:names:specification:ubl:cac:2.1}PartyName"
        ).append(self._name_node(move.company_id.display_name or ""))

        # Customer party
        customer = etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cac:2.1}AccountingCustomerParty"
        )
        party_c = etree.SubElement(
            customer, "{urn:oasis:names:specification:ubl:cac:2.1}Party"
        )
        etree.SubElement(
            party_c, "{urn:oasis:names:specification:ubl:cac:2.1}PartyIdentification"
        ).append(self._id_node(move.partner_id.vat or ""))
        etree.SubElement(
            party_c, "{urn:oasis:names:specification:ubl:cac:2.1}PartyName"
        ).append(self._name_node(move.partner_id.display_name or ""))

        # Tax total
        tax_total = etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cac:2.1}TaxTotal"
        )
        etree.SubElement(
            tax_total, "{urn:oasis:names:specification:ubl:cbc:2.1}TaxAmount"
        ).text = "%0.2f" % (move.amount_tax or 0.0)
        for tax in move.line_ids.mapped("tax_line_id"):
            ts = etree.SubElement(
                tax_total,
                "{urn:oasis:names:specification:ubl:cac:2.1}TaxSubtotal",
            )
            etree.SubElement(
                ts, "{urn:oasis:names:specification:ubl:cbc:2.1}TaxableAmount"
            ).text = "%0.2f" % (move.amount_untaxed or 0.0)
            etree.SubElement(
                ts, "{urn:oasis:names:specification:ubl:cbc:2.1}TaxAmount"
            ).text = "%0.2f" % (move.amount_tax or 0.0)
            cat = etree.SubElement(
                ts, "{urn:oasis:names:specification:ubl:cac:2.1}TaxCategory"
            )
            etree.SubElement(
                cat, "{urn:oasis:names:specification:ubl:cbc:2.1}ID"
            ).text = (tax.l10n_sa_tax_category.code if hasattr(tax, "l10n_sa_tax_category") else "S")
            etree.SubElement(
                cat, "{urn:oasis:names:specification:ubl:cbc:2.1}Percent"
            ).text = "%0.2f" % (tax.amount or 0.0)

        # Legal monetary total
        lmt = etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cac:2.1}LegalMonetaryTotal"
        )
        etree.SubElement(
            lmt, "{urn:oasis:names:specification:ubl:cbc:2.1}LineExtensionAmount"
        ).text = "%0.2f" % (move.amount_untaxed or 0.0)
        etree.SubElement(
            lmt, "{urn:oasis:names:specification:ubl:cbc:2.1}TaxExclusiveAmount"
        ).text = "%0.2f" % (move.amount_untaxed or 0.0)
        etree.SubElement(
            lmt, "{urn:oasis:names:specification:ubl:cbc:2.1}TaxInclusiveAmount"
        ).text = "%0.2f" % (move.amount_total or 0.0)
        etree.SubElement(
            lmt, "{urn:oasis:names:specification:ubl:cbc:2.1}PayableAmount"
        ).text = "%0.2f" % (move.amount_residual or 0.0)

        # Lines
        for line in move.invoice_line_ids:
            il = etree.SubElement(
                invoice, "{urn:oasis:names:specification:ubl:cac:2.1}InvoiceLine"
            )
            etree.SubElement(
                il, "{urn:oasis:names:specification:ubl:cbc:2.1}ID"
            ).text = str(line.sequence or "")
            etree.SubElement(
                il, "{urn:oasis:names:specification:ubl:cbc:2.1}InvoicedQuantity"
            ).text = "%0.2f" % (line.quantity or 0.0)
            etree.SubElement(
                il, "{urn:oasis:names:specification:ubl:cbc:2.1}LineExtensionAmount"
            ).text = "%0.2f" % (line.price_subtotal or 0.0)
            item = etree.SubElement(
                il, "{urn:oasis:names:specification:ubl:cac:2.1}Item"
            )
            etree.SubElement(
                item, "{urn:oasis:names:specification:ubl:cbc:2.1}Description"
            ).text = line.name or ""

        return etree.tostring(
            invoice, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        ).decode("utf-8")

    def _hash_xml(self, xml_str):
        """Canonicalize + SHA-256 + base64."""
        try:
            return self.env["zatca.hasher"].canonicalize_and_hash(xml_str)
        except Exception:
            return base64.b64encode(
                hashlib.sha256(xml_str.encode("utf-8")).digest()
            ).decode("ascii")

    def _id_node(self, value):
        from lxml import etree
        node = etree.Element(
            "{urn:oasis:names:specification:ubl:cac:2.1}ID",
        )
        node.text = value
        return node

    def _name_node(self, value):
        from lxml import etree
        node = etree.Element(
            "{urn:oasis:names:specification:ubl:cac:2.1}Name",
        )
        node.text = value
        return node
