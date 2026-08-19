"""Tests for the Nexus Advanced Accounting bridge."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNexusTaxMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "VAT 15%",
                "amount": 15.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.env.company.id,
            }
        )
        cls.mapping = cls.env["nexus.tax.mapping"].create(
            {
                "odoo_tax_id": cls.tax.id,
                "nexus_tax_template": "VAT 15%",
                "nexus_tax_code": "VAT-15",
                "nexus_tax_rate": 15.0,
                "company_id": cls.env.company.id,
            }
        )

    def test_mapping_creation(self):
        self.assertEqual(self.mapping.odoo_tax_id, self.tax)
        self.assertEqual(self.mapping.nexus_tax_template, "VAT 15%")
        self.assertEqual(self.mapping.nexus_tax_rate, 15.0)

    def test_mapping_unique_per_company(self):
        from odoo.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.env["nexus.tax.mapping"].create(
                {
                    "odoo_tax_id": self.tax.id,
                    "nexus_tax_template": "VAT 15% v2",
                    "company_id": self.env.company.id,
                }
            )

    def test_get_map_for_company(self):
        mapping = self.env["nexus.tax.mapping"]._get_map_for_company(self.env.company)
        self.assertIn(self.tax.id, mapping)
        self.assertEqual(mapping[self.tax.id].nexus_tax_template, "VAT 15%")

    def test_display_name(self):
        self.assertIn("VAT 15%", self.mapping.display_name)

    def test_inactive_mapping_excluded(self):
        self.mapping.active = False
        mapping = self.env["nexus.tax.mapping"]._get_map_for_company(self.env.company)
        self.assertNotIn(self.tax.id, mapping)


@tagged("post_install", "-at_install")
class TestNexusCostCenterMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search([], limit=1)
        if not cls.warehouse:
            cls.warehouse = cls.env["stock.warehouse"].create(
                {
                    "name": "Test Branch",
                    "code": "TBR",
                    "company_id": cls.env.company.id,
                }
            )

    def test_warehouse_has_sync_field(self):
        self.assertIn(
            "nexus_cost_center_synced", self.env["stock.warehouse"]._fields
        )

    def test_cost_center_mapping_model_exists(self):
        self.assertTrue(self.env["nexus.cost.center.mapping"]._name)

    def test_mark_synced(self):
        wh = self.warehouse
        wh.nexus_cost_center_synced = False
        self.env["nexus.cost.center.mapping"]._mark_synced(
            "stock.warehouse", wh.id, "CC-TBR-001"
        )
        mapping = self.env["nexus.cost.center.mapping"].search(
            [("model_name", "=", "stock.warehouse"), ("res_id", "=", wh.id)], limit=1
        )
        self.assertTrue(mapping)
        self.assertTrue(mapping.synced)
        self.assertEqual(mapping.nexus_cost_center_id, "CC-TBR-001")


@tagged("post_install", "-at_install")
class TestProductFixedAsset(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {
                "name": "Laptop",
                "type": "consu",
                "company_id": cls.env.company.id,
            }
        )

    def test_product_is_fixed_asset_field(self):
        self.assertIn("is_fixed_asset", self.env["product.template"]._fields)
        self.assertIn("is_fixed_asset", self.env["product.product"]._fields)

    def test_is_fixed_asset_inherits_from_template(self):
        self.product.product_tmpl_id.is_fixed_asset = True
        self.assertTrue(self.product.is_fixed_asset)


@tagged("post_install", "-at_install")
class TestAccountMoveCostCenter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})

    def test_invoice_has_cost_center_field(self):
        self.assertIn("nexus_cost_center", self.env["account.move"]._fields)

    def test_invoice_line_has_cost_center_field(self):
        self.assertIn("nexus_cost_center", self.env["account.move.line"]._fields)

    def test_invoice_line_has_asset_fields(self):
        self.assertIn("nexus_asset_synced", self.env["account.move.line"]._fields)
        self.assertIn("nexus_asset_docname", self.env["account.move.line"]._fields)


@tagged("post_install", "-at_install")
class TestAccountPaymentNexusFields(TransactionCase):

    def test_payment_has_nexus_fields(self):
        self.assertIn("nexus_core_synced", self.env["account.payment"]._fields)
        self.assertIn("nexus_core_docname", self.env["account.payment"]._fields)
