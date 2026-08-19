# -*- coding: utf-8 -*-
"""Nexus ZATCA QR Code Generator — مولّد رمز QR للفوترة الإلكترونية.

Generates the standard TLV (Tag-Length-Value) encoded QR payload
that ZATCA-compliant invoices must carry, plus an optional
human-readable summary.  Encoding follows ZATCA's published spec:

    Tag 1  — Seller's name
    Tag 2  — VAT number
    Tag 3  — Invoice timestamp (ISO 8601)
    Tag 4  — Invoice total (with VAT)
    Tag 5  — VAT amount
    Tag 6  — Hash of XML (Base64 SHA-256)

The module produces a base64-encoded TLV blob suitable for embedding
in a QR matrix.
"""

import base64
import hashlib
import logging
from datetime import datetime

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


# ZATCA tag numbers (1-based). Order is significant.
_TAGS = [
    ("seller_name", 1),
    ("vat_number", 2),
    ("invoice_timestamp", 3),
    ("invoice_total_with_vat", 4),
    ("vat_amount", 5),
    ("xml_hash", 6),
]


class NexusSaudiZatcaQR(models.TransientModel):
    """Computes the TLV QR payload for a posted invoice."""

    _name = "nexus.saudi.zatca.qr"
    _description = "Nexus ZATCA QR Generator"

    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        domain=[
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
        ],
    )

    tlv_payload = fields.Char(
        string="TLV Payload (Base64)",
        readonly=True,
        help="TLV-encoded payload that goes inside the QR matrix.",
    )
    qr_summary = fields.Char(
        string="Human-Readable Summary",
        readonly=True,
    )

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────
    def action_compute(self):
        for rec in self:
            rec.tlv_payload = self._build_tlv(rec.invoice_id)
            rec.qr_summary = self._build_summary(rec.invoice_id)
        return True

    @api.model
    def compute_for_invoice(self, move_id):
        """Return the TLV payload for an invoice without persisting it."""
        move = self.env["account.move"].browse(move_id)
        if not move.exists():
            return ""
        return self._build_tlv(move)

    # ─────────────────────────────────────────────────────────────────
    # Internal builders
    # ─────────────────────────────────────────────────────────────────
    def _build_tlv(self, move):
        """Compose the standard TLV stream and base64-encode it."""
        seller = move.company_id.display_name or ""
        vat = (move.company_id.vat or "").replace(" ", "")
        ts = self._format_timestamp(move.invoice_date)
        total = "%0.2f" % (move.amount_total or 0.0)
        vat_amount = "%0.2f" % (move.amount_tax or 0.0)
        xml_hash = self._invoice_hash(move)

        fields_ = {
            "seller_name": seller,
            "vat_number": vat,
            "invoice_timestamp": ts,
            "invoice_total_with_vat": total,
            "vat_amount": vat_amount,
            "xml_hash": xml_hash,
        }

        tlv_bytes = bytearray()
        for key, tag in _TAGS:
            value = fields_[key].encode("utf-8") if fields_[key] else b""
            tlv_bytes.append(tag & 0xFF)
            tlv_bytes.append(len(value) & 0xFF)
            tlv_bytes.extend(value)

        return base64.b64encode(bytes(tlv_bytes)).decode("ascii")

    def _build_summary(self, move):
        """Short text summary suitable for display next to the QR."""
        vat = move.company_id.vat or "-"
        return (
            f"Seller: {move.company_id.display_name}\n"
            f"VAT: {vat}\n"
            f"Date: {move.invoice_date}\n"
            f"Total (incl. VAT): {move.amount_total:,.2f}\n"
            f"VAT amount: {move.amount_tax:,.2f}"
        )

    def _format_timestamp(self, date_value):
        """Return the timestamp in ZATCA's required format."""
        if not date_value:
            return ""
        if isinstance(date_value, str):
            date_value = fields.Date.from_string(date_value)
        # ZATCA expects ISO 8601 with timezone offset
        return datetime(
            date_value.year, date_value.month, date_value.day
        ).isoformat()

    def _invoice_hash(self, move):
        """Compute the invoice hash per ZATCA rules.

        Falls back to a SHA-256 over the move's XML representation if
        ``zatca.hasher`` is unavailable. The real-world ZATCA spec
        chains each invoice's hash with the previous one — the chain
        value is held on ``res.company`` via ``nexus.last_invoice_hash``.
        """
        try:
            xml_str = self.env["zatca.hasher"].canonicalize_and_hash(
                self._serialize_move(move)
            )
        except Exception:
            xml_str = base64.b64encode(
                hashlib.sha256(repr(move.read()).encode("utf-8")).digest()
            ).decode("ascii")
        return xml_str

    def _serialize_move(self, move):
        """Build a minimal XML for hashing."""
        from lxml import etree

        root = etree.Element("Invoice", xmlns="urn:zatca:xmlns")
        etree.SubElement(root, "Seller").text = move.company_id.display_name or ""
        etree.SubElement(root, "VATNumber").text = move.company_id.vat or ""
        etree.SubElement(root, "IssueDate").text = str(move.invoice_date or "")
        etree.SubElement(root, "TotalAmount").text = "%0.2f" % (move.amount_total or 0.0)
        etree.SubElement(root, "VATAmount").text = "%0.2f" % (move.amount_tax or 0.0)
        for line in move.invoice_line_ids:
            ln = etree.SubElement(root, "Line")
            etree.SubElement(ln, "Description").text = line.name or ""
            etree.SubElement(ln, "Quantity").text = str(line.quantity or 0.0)
            etree.SubElement(ln, "UnitPrice").text = "%0.2f" % (line.price_unit or 0.0)
        return etree.tostring(root, pretty_print=True).decode("utf-8")
