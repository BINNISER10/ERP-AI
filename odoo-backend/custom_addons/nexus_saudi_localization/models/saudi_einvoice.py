# -*- coding: utf-8 -*-
"""Nexus Saudi E-Invoice Generator — مولّد الفاتورة الإلكترونية.

Produces a UBL 2.1 compliant invoice XML that ZATCA accepts at
Phase 2. The XML structure follows the ZATCA "Invoice Data File"
specification:

    * ``cac:Invoice`` with ``cbc:ID`` and ``cbc:IssueDate``
    * ``cac:AccountingSupplierParty`` / ``cac:AccountingCustomerParty``
    * ``cac:TaxTotal`` with ``cac:TaxSubtotal`` for VAT
    * ``cac:LegalMonetaryTotal`` for amounts

The hash (Phase 1 & 2) is delegated to
``zatca.hasher.canonicalize_and_hash``, chained via the company's
stored ``zatca_last_invoice_hash`` (PIH — Previous Invoice Hash,
embedded as a ``cac:AdditionalDocumentReference`` per ZATCA spec).

When the company has completed CSID onboarding (Phase 2, private key
+ certificate present on ``nexus.saudi.company.settings``), the
invoice is additionally cryptographically stamped via
``zatca.signer``: an ECDSA-SHA256 ``ds:Signature`` is embedded in
``ext:UBLExtensions`` and QR tags 7-9 (signature, public key,
certificate signature) are appended. Tenants still on Phase 1 (or
without keys yet) silently fall back to the unsigned hash-only QR
(tags 1-6) — this keeps the generator usable before ZATCA onboarding
completes.
"""

import base64
import hashlib
import logging
import uuid
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
    invoice_uuid = fields.Char(string="Invoice UUID", readonly=True)
    invoice_hash = fields.Char(string="Invoice Hash (Base64)", readonly=True)
    qr_tlv = fields.Char(string="QR TLV Payload", readonly=True)
    is_cryptographically_signed = fields.Boolean(
        string="Cryptographically Stamped",
        readonly=True,
        help="True when the invoice carries a real ECDSA signature "
        "(Phase 2, CSID onboarding complete). False means only the "
        "hash-chain (PIH) is present — the tenant hasn't finished "
        "ZATCA onboarding yet.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("signed", "Signed")],
        default="draft",
    )

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────
    def action_generate(self):
        for rec in self:
            move = rec.invoice_id
            settings = self.env["nexus.saudi.company.settings"].get_for_company(
                move.company_id
            )
            invoice_uuid = str(uuid.uuid4())
            previous_hash = settings.zatca_last_invoice_hash or ""

            # 1) Build the base (unsigned) XML — this is what gets hashed
            # and, if signing, what gets ECDSA-signed.
            base_payload = self._build_xml(move, invoice_uuid, previous_hash)
            invoice_hash = self._hash_xml(base_payload)

            signing_chain = None
            has_keys = bool(settings.zatca_private_key and settings.zatca_certificate)
            if settings.zatca_phase == "phase_2" and has_keys:
                try:
                    signing_chain = self._sign_xml(base_payload, settings)
                except Exception:
                    _logger.exception(
                        "ZATCA signing failed for invoice %s; falling back to "
                        "unsigned hash-only QR.",
                        move.name,
                    )
                    signing_chain = None

            qr_tlv = self.env["nexus.saudi.zatca.qr"].compute_for_invoice(
                move.id,
                invoice_hash=invoice_hash,
                signing_chain=signing_chain,
            )

            final_payload = base_payload
            if signing_chain:
                final_payload = self._embed_signature(base_payload, signing_chain)

            rec.write({
                "xml_payload": final_payload,
                "invoice_uuid": invoice_uuid,
                "invoice_hash": invoice_hash,
                "qr_tlv": qr_tlv,
                "is_cryptographically_signed": bool(signing_chain),
                "state": "signed",
            })
            # Advance the hash chain (PIH) on the company for the next invoice.
            settings.write({"zatca_last_invoice_hash": invoice_hash})
            # Persist hash on the move for audit.
            move.write({"zatca_invoice_hash": invoice_hash})
        return True

    def _sign_xml(self, canonical_xml_str, settings):
        """Run the ECDSA signing chain via ``zatca.signer``.

        Raises if keys are malformed — caller decides whether to
        degrade gracefully.
        """
        # Re-canonicalize here (not just hash) since signing needs the
        # canonical *bytes*, not the digest.
        from lxml import etree

        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(canonical_xml_str.encode("utf-8"), parser=parser)
        canonical_bytes = etree.tostring(root, method="c14n", with_comments=False)

        private_key_pem = bytes(settings.zatca_private_key)
        certificate_pem = bytes(settings.zatca_certificate)
        return self.env["zatca.signer"].build_signing_chain(
            canonical_bytes, private_key_pem, certificate_pem
        )

    def _embed_signature(self, xml_str, signing_chain):
        """Insert the ECDSA signature + certificate into a
        ``ext:UBLExtensions`` block, per the ZATCA UBL signature profile.
        """
        from lxml import etree

        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(xml_str.encode("utf-8"), parser=parser)

        ext_ns = "urn:oasis:names:specification:ubl:dsig:2.1"
        ds_ns = "http://www.w3.org/2000/09/xmldsig#"

        extensions = etree.Element(f"{{{ext_ns}}}UBLExtensions")
        extension = etree.SubElement(extensions, f"{{{ext_ns}}}UBLExtension")
        content = etree.SubElement(extension, f"{{{ext_ns}}}ExtensionContent")
        signature = etree.SubElement(content, f"{{{ds_ns}}}Signature")
        signed_info = etree.SubElement(signature, f"{{{ds_ns}}}SignedInfo")
        etree.SubElement(
            signed_info, f"{{{ds_ns}}}SignatureMethod"
        ).set("Algorithm", "http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256")
        etree.SubElement(
            signature, f"{{{ds_ns}}}SignatureValue"
        ).text = signing_chain["signature"]
        key_info = etree.SubElement(signature, f"{{{ds_ns}}}KeyInfo")
        x509_data = etree.SubElement(key_info, f"{{{ds_ns}}}X509Data")
        etree.SubElement(
            x509_data, f"{{{ds_ns}}}X509Certificate"
        ).text = signing_chain["certificate_raw"]

        root.insert(0, extensions)
        return etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        ).decode("utf-8")

    # ─────────────────────────────────────────────────────────────────
    # Internal builders
    # ─────────────────────────────────────────────────────────────────
    def _build_xml(self, move, invoice_uuid=None, previous_hash=""):
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
            invoice, "{urn:oasis:names:specification:ubl:cbc:2.1}UUID"
        ).text = invoice_uuid or str(uuid.uuid4())
        etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cbc:2.1}IssueDate"
        ).text = str(move.invoice_date or "")
        # 388 = Tax Invoice (B2B). 383 for credit notes.
        type_code = "381" if move.move_type == "out_refund" else "388"
        etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cbc:2.1}InvoiceTypeCode"
        ).text = type_code
        etree.SubElement(
            invoice, "{urn:oasis:names:specification:ubl:cbc:2.1}DocumentCurrencyCode"
        ).text = move.currency_id.name

        # PIH — Previous Invoice Hash chain, required by ZATCA for every
        # invoice after the first.
        if previous_hash:
            pih_ref = etree.SubElement(
                invoice, "{urn:oasis:names:specification:ubl:cac:2.1}AdditionalDocumentReference"
            )
            etree.SubElement(
                pih_ref, "{urn:oasis:names:specification:ubl:cbc:2.1}ID"
            ).text = "PIH"
            attachment = etree.SubElement(
                pih_ref, "{urn:oasis:names:specification:ubl:cac:2.1}Attachment"
            )
            etree.SubElement(
                attachment,
                "{urn:oasis:names:specification:ubl:cbc:2.1}EmbeddedDocumentBinaryObject",
                mimeCode="text/plain",
            ).text = previous_hash

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
