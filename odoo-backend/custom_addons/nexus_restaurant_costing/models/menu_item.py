from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json


class MenuItem(models.Model):
    _name = "menu.item"
    _description = "Menu Item"

    name = fields.Char(string="Display Name", required=True)
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain="[('sale_ok', '=', True)]",
    )
    recipe_bom_id = fields.Many2one("recipe.bom", string="Recipe BOM")
    pos_category_id = fields.Many2one("pos.category", string="POS Category")
    sale_price = fields.Float(
        string="Sale Price",
        digits=(16, 2),
        related="product_id.lst_price",
        store=True,
        readonly=True,
    )
    recipe_cost = fields.Float(
        string="Recipe Cost",
        digits=(16, 4),
        compute="_compute_recipe_cost",
        store=True,
    )
    profit_margin = fields.Float(
        string="Profit Margin (%)",
        digits=(5, 2),
        compute="_compute_profit_margin",
        store=True,
    )
    modifier_schema = fields.Text(
        string="Modifier Schema JSON",
        help="Defines available modifiers and their cost adjustments.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    @api.depends("recipe_bom_id", "recipe_bom_id.total_recipe_cost")
    def _compute_recipe_cost(self):
        for item in self:
            if item.recipe_bom_id:
                item.recipe_cost = item.recipe_bom_id.total_recipe_cost
            else:
                item.recipe_cost = item.product_id.standard_price

    @api.depends("sale_price", "recipe_cost")
    def _compute_profit_margin(self):
        for item in self:
            if item.sale_price:
                item.profit_margin = ((item.sale_price - item.recipe_cost) / item.sale_price) * 100.0
            else:
                item.profit_margin = 0.0

    @api.model
    def get_cost_for_order_line(self, product_id, modifiers=None, quantity=1.0):
        """Calculate exact COGS for an order line, honoring modifiers."""
        menu_item = self.search([("product_id", "=", product_id)], limit=1)
        if not menu_item or not menu_item.recipe_bom_id:
            product = self.env["product.product"].browse(product_id)
            return product.standard_price * quantity

        bom = menu_item.recipe_bom_id
        total = 0.0
        modifiers = modifiers or {}

        for ingredient in bom.line_ids:
            base_qty = ingredient.quantity
            unit_cost = ingredient.standard_cost
            product = ingredient.product_id

            # If ingredient excluded via modifier
            if product.name in modifiers.get("exclude", []):
                continue

            # If ingredient substituted via modifier, apply option cost
            selected = modifiers.get("substitute", {}).get(product.name)
            if selected and ingredient.is_modifiable and ingredient.modifier_options:
                try:
                    options = json.loads(ingredient.modifier_options)
                    adjustment = options.get(selected, 0.0)
                    unit_cost += adjustment
                    # When substituting, optional quantity may increase
                    base_qty += modifiers.get("extra_qty", {}).get(product.name, 0.0)
                except (ValueError, TypeError):
                    pass

            total += base_qty * unit_cost * quantity

        return total

    @api.model
    def get_dynamic_price(self, product_id, modifiers=None, base_price=None):
        """Recalculate sale price based on modifiers."""
        product = self.env["product.product"].browse(product_id)
        price = base_price if base_price is not None else product.lst_price
        modifiers = modifiers or {}

        # Surcharges
        surcharges = modifiers.get("surcharges", {})
        for _key, value in surcharges.items():
            price += float(value)

        # Discounts
        discounts = modifiers.get("discounts", {})
        for _key, value in discounts.items():
            price -= float(value)

        return max(price, 0.0)
