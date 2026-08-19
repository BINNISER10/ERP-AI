"""Tests for recipe BOM costing and consumption."""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install")
class TestRecipeBom(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_tmpl = cls.env["product.template"].create({
            "name": "Signature Burger",
            "type": "product",
            "sale_ok": True,
        })
        cls.product = cls.product_tmpl.product_variant_id

        cls.ingredient_tmpl = cls.env["product.template"].create({
            "name": "Bun",
            "type": "product",
            "standard_price": 0.5,
        })
        cls.ingredient = cls.ingredient_tmpl.product_variant_id

        cls.recipe = cls.env["recipe.bom"].create({
            "name": "Signature Burger Recipe",
            "product_id": cls.product.id,
            "line_ids": [
                (0, 0, {
                    "product_id": cls.ingredient.id,
                    "quantity": 2.0,
                }),
            ],
        })

    def test_total_recipe_cost_computed(self):
        self.assertEqual(self.recipe.total_recipe_cost, 1.0)

    def test_get_cost_for_quantity(self):
        self.assertEqual(self.recipe.get_cost_for_quantity(3.0), 3.0)

    def test_negative_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["recipe.bom.line"].create({
                "bom_id": self.recipe.id,
                "product_id": self.ingredient.id,
                "quantity": -1.0,
            })

    def test_standard_cost_syncs_with_product_price(self):
        line = self.recipe.line_ids
        self.assertEqual(line.standard_cost, 0.5)
        self.ingredient.product_tmpl_id.standard_price = 0.75
        self.assertEqual(line.standard_cost, 0.75)
