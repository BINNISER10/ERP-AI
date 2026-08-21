"""ZATCA Phase 2 cryptographic stamp — digital signature utilities.

Completes the signing chain that ``zatca.hasher`` starts: given the
canonicalized invoice XML and the tenant's ECDSA (secp256k1) private
key + X.509 certificate (both issued by ZATCA's Fatoora portal during
CSID onboarding and stored on ``nexus.saudi.company.settings``), this
model produces:

    * the ECDSA-SHA256 signature over the canonicalized invoice
      (embedded as ``ds:SignatureValue`` in the UBL ``ext:UBLExtensions``
      block, and as QR Tag 7)
    * the raw EC public key bytes (QR Tag 8)
    * the certificate's own signature, i.e. ZATCA CA's signature over
      the tenant's public key (QR Tag 9) — extracted directly from the
      X.509 certificate object, since that field *is* the CA signature
      per ZATCA's certificate profile.

This module intentionally does NOT implement CSID/PCSID onboarding
(the OTP exchange with ZATCA's Fatoora API to obtain the private
key/certificate in the first place) — that is a one-time manual/API
step captured by the ``zatca_otp_code`` field on
``nexus.saudi.company.settings`` and is out of scope here. This model
only consumes an already-issued key/certificate pair.
"""
import base64
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZatcaSigner(models.AbstractModel):
    _name = "zatca.signer"
    _description = "ZATCA Cryptographic Stamp Signer"

    # ── Key / certificate loading ───────────────────────────────────
    @api.model
    def _load_private_key(self, private_key_pem):
        from cryptography.hazmat.primitives import serialization

        if not private_key_pem:
            raise UserError(_("No ZATCA private key is configured for this company."))
        try:
            return serialization.load_pem_private_key(private_key_pem, password=None)
        except ValueError as exc:
            raise UserError(_("Invalid ZATCA private key: %s") % exc) from exc

    @api.model
    def _load_certificate(self, certificate_pem):
        from cryptography import x509

        if not certificate_pem:
            raise UserError(_("No ZATCA certificate is configured for this company."))
        try:
            return x509.load_pem_x509_certificate(certificate_pem)
        except ValueError as exc:
            raise UserError(_("Invalid ZATCA certificate: %s") % exc) from exc

    # ── Public API ───────────────────────────────────────────────────
    @api.model
    def sign_invoice_xml(self, canonical_xml_bytes, private_key_pem):
        """ECDSA-SHA256 sign the canonicalized invoice XML.

        Returns the DER-encoded signature, base64-encoded.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        private_key = self._load_private_key(private_key_pem)
        signature = private_key.sign(canonical_xml_bytes, ec.ECDSA(hashes.SHA256()))
        return base64.b64encode(signature).decode("ascii")

    @api.model
    def get_public_key_base64(self, certificate_pem):
        """Return the raw EC public key point (uncompressed X9.62 form),
        base64-encoded, as required for QR Tag 8.
        """
        from cryptography.hazmat.primitives import serialization

        cert = self._load_certificate(certificate_pem)
        public_bytes = cert.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        return base64.b64encode(public_bytes).decode("ascii")

    @api.model
    def get_certificate_signature_base64(self, certificate_pem):
        """Return ZATCA CA's signature over the certificate (QR Tag 9)."""
        cert = self._load_certificate(certificate_pem)
        return base64.b64encode(cert.signature).decode("ascii")

    @api.model
    def get_certificate_raw_base64(self, certificate_pem):
        """Return the full DER certificate, base64-encoded, for
        embedding as ``ds:X509Certificate`` in the UBL signature block.
        """
        from cryptography.hazmat.primitives import serialization

        cert = self._load_certificate(certificate_pem)
        der_bytes = cert.public_bytes(encoding=serialization.Encoding.DER)
        return base64.b64encode(der_bytes).decode("ascii")

    @api.model
    def build_signing_chain(self, canonical_xml_bytes, private_key_pem, certificate_pem):
        """Convenience: compute everything needed for QR tags 7-9 and
        the UBL signature block in one call.
        """
        return {
            "signature": self.sign_invoice_xml(canonical_xml_bytes, private_key_pem),
            "public_key": self.get_public_key_base64(certificate_pem),
            "certificate_signature": self.get_certificate_signature_base64(certificate_pem),
            "certificate_raw": self.get_certificate_raw_base64(certificate_pem),
        }
