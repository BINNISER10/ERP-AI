"""Tests for the rule-based scoping/pricing engine.

The pricing formula is intentionally transparent (no ML) — these tests
pin down the exact arithmetic so future changes to the formula are
deliberate, not accidental.
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScopingRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fuel_sector = cls.env.ref("nexus_saas_scoping.sector_fuel_station")
        cls.retail_sector = cls.env.ref("nexus_saas_scoping.sector_retail")
        cls.Scoping = cls.env["nexus.saas.scoping.request"]

    def test_fuel_station_quote_arithmetic(self):
        scoping = self.Scoping.create({
            "company_name": "Acme Fuel",
            "contact_email": "owner@acme-fuel.com",
            "sector_id": self.fuel_sector.id,
            "branches_count": 2,
            "pos_count": 6,
            "warehouse_main_count": 1,
            "warehouse_sub_count": 2,
            "employees_count": 25,
            "has_manufacturing": False,
            "has_iot_integration": True,
            "has_ecommerce": False,
        })
        # 1500 base + 1*800 (extra branch) + 6*150 (pos) + 2*100 (extra
        # warehouses) + 3*50 (employee blocks, ceil(25/10)=3) + 400 (iot)
        self.assertEqual(scoping.price_monthly, 3950.0)
        self.assertEqual(scoping.price_yearly, 39500.0)
        # Sector baseline ("large") wins over the computed "medium" tier.
        self.assertEqual(scoping.resource_tier, "large")

    def test_retail_tier_escalates_past_sector_baseline(self):
        scoping = self.Scoping.create({
            "company_name": "Mega Mart",
            "contact_email": "owner@megamart.com",
            "sector_id": self.retail_sector.id,
            "branches_count": 10,
            "pos_count": 20,
            "warehouse_main_count": 5,
            "warehouse_sub_count": 5,
            "employees_count": 200,
        })
        self.assertEqual(scoping.price_monthly, 8670.0)
        # Retail's baseline is "medium" but this load score (130) crosses
        # the "enterprise" threshold (80).
        self.assertEqual(scoping.resource_tier, "enterprise")

    def test_resource_tier_never_downgrades_below_sector_baseline(self):
        # A tiny fuel station (score way below any threshold) must still
        # get at least the sector's "large" baseline tier.
        scoping = self.Scoping.create({
            "company_name": "Tiny Fuel Stop",
            "contact_email": "owner@tinyfuel.com",
            "sector_id": self.fuel_sector.id,
            "branches_count": 1,
            "pos_count": 1,
            "warehouse_main_count": 1,
            "warehouse_sub_count": 0,
            "employees_count": 2,
        })
        self.assertEqual(scoping.resource_tier, "large")

    def test_recommended_modules_include_sector_defaults_and_extras(self):
        scoping = self.Scoping.create({
            "company_name": "Acme Fuel",
            "contact_email": "owner@acme-fuel.com",
            "sector_id": self.fuel_sector.id,
            "has_manufacturing": True,
            "has_ecommerce": True,
        })
        modules = set(scoping.recommended_modules.split(","))
        self.assertIn("nexus_fuel_station", modules)
        self.assertIn("mrp", modules)
        self.assertIn("website_sale", modules)

    def test_checkout_requires_default_plan(self):
        self.env["nexus.saas.plan"].search([("is_default", "=", True)]).write(
            {"is_default": False}
        )
        scoping = self.Scoping.create({
            "company_name": "Acme Fuel",
            "contact_email": "owner@acme-fuel.com",
            "sector_id": self.fuel_sector.id,
        })
        with self.assertRaises(UserError):
            scoping.action_start_checkout(tenant_code="acmefuel", admin_email="a@a.com")

    def test_checkout_twice_raises(self):
        scoping = self.Scoping.create({
            "company_name": "Acme Fuel",
            "contact_email": "owner@acme-fuel.com",
            "sector_id": self.fuel_sector.id,
        })
        scoping.state = "checkout"
        with self.assertRaises(UserError):
            scoping.action_start_checkout(tenant_code="acmefuel", admin_email="a@a.com")
