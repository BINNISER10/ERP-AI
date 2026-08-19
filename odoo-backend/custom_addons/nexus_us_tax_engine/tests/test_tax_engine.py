"""Tests for the US multi-jurisdiction sales tax engine."""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged("post_install", "-at_install")
class TestUsTaxEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["us.tax.rate"].search([]).unlink()
        cls.rate_state = cls.env["us.tax.rate"].create({
            "name": "CA State",
            "state_code": "CA",
            "rate": 0.06,
            "tax_type": "state",
        })
        cls.rate_county = cls.env["us.tax.rate"].create({
            "name": "CA Los Angeles",
            "state_code": "CA",
            "county": "Los Angeles",
            "rate": 0.01,
            "tax_type": "county",
        })
        cls.rate_city = cls.env["us.tax.rate"].create({
            "name": "CA LA City",
            "state_code": "CA",
            "county": "Los Angeles",
            "city": "Los Angeles",
            "rate": 0.015,
            "tax_type": "city",
        })
        cls.rate_zip = cls.env["us.tax.rate"].create({
            "name": "CA Zip 90001",
            "state_code": "CA",
            "zip_start": "90001",
            "zip_end": "90005",
            "rate": 0.005,
            "tax_type": "special",
        })

    def test_negative_amount_raises(self):
        with self.assertRaises(UserError):
            self.env["us.tax.engine"].calculate_tax(-100, "CA")

    def test_missing_state_returns_zero_tax(self):
        result = self.env["us.tax.engine"].calculate_tax(100, None)
        self.assertEqual(result["total_tax"], 0.0)
        self.assertEqual(result["taxable_amount"], 100)
        self.assertFalse(result["tax_lines"])

    def test_state_only_rate(self):
        result = self.env["us.tax.engine"].calculate_tax(100, "CA")
        self.assertEqual(result["total_tax"], 6.0)
        self.assertEqual(len(result["tax_lines"]), 1)
        self.assertEqual(result["tax_lines"][0]["rate"], 0.06)

    def test_jurisdiction_breakdown(self):
        result = self.env["us.tax.engine"].calculate_tax(
            200, "CA", county="Los Angeles", city="Los Angeles", zip_code="90002"
        )
        self.assertEqual(result["total_tax"], 16.0)  # 6% + 1% + 1.5% + 0.5% on 200
        self.assertEqual(len(result["tax_lines"]), 4)

    def test_zip_outside_range_is_excluded(self):
        result = self.env["us.tax.engine"].calculate_tax(
            100, "CA", zip_code="99999"
        )
        self.assertEqual(result["total_tax"], 6.0)  # state only
