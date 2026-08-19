"""Tests for the ZATCA XML canonicalization hasher."""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
    <ID>INV-001</ID>
    <IssueDate>2024-01-15</IssueDate>
</Invoice>
"""


@tagged("post_install", "-at_install")
class TestZatcaHasher(TransactionCase):

    def test_canonicalize_and_hash_returns_digest(self):
        hasher = self.env["zatca.hasher"].create({
            "xml_payload": SAMPLE_XML,
        })
        digest = hasher.canonicalize_and_hash(SAMPLE_XML)
        self.assertTrue(digest)
        self.assertIsInstance(digest, str)
        # Should be a base64-encoded SHA-256 digest (44 chars with padding).
        self.assertEqual(len(digest), 44)
        self.assertEqual(digest[-1:], "=")

    def test_hash_is_deterministic(self):
        hasher = self.env["zatca.hasher"]
        digest1 = hasher.canonicalize_and_hash(SAMPLE_XML)
        digest2 = hasher.canonicalize_and_hash(SAMPLE_XML)
        self.assertEqual(digest1, digest2)

    def test_empty_payload_raises(self):
        with self.assertRaises(UserError):
            self.env["zatca.hasher"].canonicalize_and_hash("")

    def test_invalid_xml_raises(self):
        with self.assertRaises(UserError):
            self.env["zatca.hasher"].canonicalize_and_hash("<not-xml")
