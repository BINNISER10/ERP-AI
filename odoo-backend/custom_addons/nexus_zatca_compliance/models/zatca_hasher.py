"""ZATCA e-invoicing XML hash utilities.

This module produces a SHA-256 digest over a C14N 1.1 canonicalized
XML payload, as required for ZATCA compliant QR generation and signed
invoice XML.
"""
import base64
import hashlib
from lxml import etree

from odoo import models, fields, api
from odoo.exceptions import UserError


class ZatcaHasher(models.TransientModel):
    _name = "zatca.hasher"
    _description = "ZATCA XML Hasher"

    xml_payload = fields.Text(string="XML Payload", required=True)
    digest = fields.Char(string="SHA-256 Digest (Base64)", readonly=True)

    @api.model
    def canonicalize_and_hash(self, xml_payload):
        """Canonicalize an XML string using C14N 1.1 and return base64 SHA-256."""
        if not xml_payload:
            raise UserError("XML payload is empty.")
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            root = etree.fromstring(xml_payload.encode("utf-8"), parser=parser)
        except etree.XMLSyntaxError as exc:
            raise UserError(f"Invalid XML payload: {exc}") from exc

        # C14N 1.1 canonicalization (exclusive) with comments omitted.
        canonical_bytes = etree.tostring(
            root,
            method="c14n",
            exclusive=True,
            with_comments=False,
        )

        digest = hashlib.sha256(canonical_bytes).digest()
        return base64.b64encode(digest).decode("ascii")

    def action_hash(self):
        for rec in self:
            rec.digest = rec.canonicalize_and_hash(rec.xml_payload)
        return True
