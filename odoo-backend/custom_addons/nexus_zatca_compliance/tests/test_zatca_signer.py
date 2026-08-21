"""Tests for the ZATCA ECDSA digital signature chain (zatca.signer).

A throwaway self-signed EC certificate (secp256k1, matching ZATCA's
required curve) is generated in ``setUpClass`` so these tests run
without any real ZATCA-issued CSID material.
"""
import datetime

from odoo.tests.common import TransactionCase, tagged


def _generate_test_keypair():
    """Generate a self-signed secp256k1 cert + private key for testing."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    private_key = ec.generate_private_key(ec.SECP256K1())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Nexus Test ZATCA Cert"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    certificate_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
    return private_key_pem, certificate_pem


@tagged("post_install", "-at_install")
class TestZatcaSigner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_key_pem, cls.certificate_pem = _generate_test_keypair()
        cls.signer = cls.env["zatca.signer"]

    def test_sign_invoice_xml_returns_verifiable_signature(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        import base64

        payload = b"<Invoice><ID>INV-001</ID></Invoice>"
        signature_b64 = self.signer.sign_invoice_xml(payload, self.private_key_pem)
        self.assertTrue(signature_b64)

        cert = x509.load_pem_x509_certificate(self.certificate_pem)
        public_key = cert.public_key()
        # Should not raise: verifies the signature was produced by the
        # matching private key over this exact payload.
        public_key.verify(
            base64.b64decode(signature_b64), payload, ec.ECDSA(hashes.SHA256())
        )

    def test_sign_invoice_xml_tamper_detection(self):
        from cryptography import x509
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        import base64

        payload = b"<Invoice><ID>INV-001</ID></Invoice>"
        signature_b64 = self.signer.sign_invoice_xml(payload, self.private_key_pem)

        cert = x509.load_pem_x509_certificate(self.certificate_pem)
        public_key = cert.public_key()
        with self.assertRaises(InvalidSignature):
            public_key.verify(
                base64.b64decode(signature_b64),
                b"<Invoice><ID>TAMPERED</ID></Invoice>",
                ec.ECDSA(hashes.SHA256()),
            )

    def test_get_public_key_base64_matches_certificate(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        import base64

        result = self.signer.get_public_key_base64(self.certificate_pem)
        cert = x509.load_pem_x509_certificate(self.certificate_pem)
        expected = base64.b64encode(
            cert.public_key().public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint,
            )
        ).decode("ascii")
        self.assertEqual(result, expected)

    def test_get_certificate_signature_base64(self):
        result = self.signer.get_certificate_signature_base64(self.certificate_pem)
        self.assertTrue(result)

    def test_build_signing_chain_returns_all_fields(self):
        payload = b"<Invoice><ID>INV-002</ID></Invoice>"
        chain = self.signer.build_signing_chain(
            payload, self.private_key_pem, self.certificate_pem
        )
        self.assertIn("signature", chain)
        self.assertIn("public_key", chain)
        self.assertIn("certificate_signature", chain)
        self.assertIn("certificate_raw", chain)
        for value in chain.values():
            self.assertTrue(value)

    def test_missing_private_key_raises_user_error(self):
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.signer.sign_invoice_xml(b"data", None)

    def test_missing_certificate_raises_user_error(self):
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.signer.get_public_key_base64(None)
