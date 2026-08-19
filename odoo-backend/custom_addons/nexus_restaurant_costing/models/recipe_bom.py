from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class RecipeBom(models.Model):
    _name = "recipe.bom"
    _description = "Recipe Bill of Materials"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Recipe Name", required=True, tracking=True)
    product_id = fields.Many2one(
        "product.product",
        string="Menu Product",
        required=True,
        domain="[('type', '=', 'product'), ('sale_ok', '=', True)]",
        tracking=True,
    )
    version = fields.Integer(string="Version", default=1)
    line_ids = fields.One2many("recipe.bom.line", "bom_id", string="Ingredients")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    total_recipe_cost = fields.Float(
        string="Total Recipe Cost",
        digits=(16, 4),
        compute="_compute_total_recipe_cost",
        store=True,
    )

    @api.depends("line_ids.ingredient_cost")
    def _compute_total_recipe_cost(self):
        for bom in self:
            bom.total_recipe_cost = sum(line.ingredient_cost for line in bom.line_ids)

    def get_cost_for_quantity(self, qty=1.0):
        return self.total_recipe_cost * qty

    def consume_for_sale_order(self, sale_order):
        """Create a manufacturing/stock move for the ingredients of all order lines."""
        stock_move_obj = self.env["stock.move"]
        production_location = self.env.ref("stock.location_production", raise_if_not_found=False)
        if not production_location:
            raise UserError(_("No production location found for inventory consumption."))

        # Group product_id -> consumed qty
        consumption = {}
        for line in sale_order.order_line:
            product = line.product_id
            if not product:
                continue
            bom = self._match_bom(product.id, sale_order.company_id.id)
            if not bom:
                continue
            base_qty = line.product_uom_qty
            for ingredient in bom.line_ids:
                consumed = ingredient.quantity * base_qty
                if ingredient.product_id.id in consumption:
                    consumption[ingredient.product_id.id] += consumed
                else:
                    consumption[ingredient.product_id.id] = consumed

        if not consumption:
            return False

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("company_id", "=", sale_order.company_id.id),
            ],
            limit=1,
        )
        if not picking_type:
            raise UserError(_("No outgoing picking type found."))

        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", sale_order.company_id.id)], limit=1
        )
        default_stock = self.env.ref("stock.stock_location_stock")
        fallback_src = warehouse.lot_stock_id or default_stock

        for product_id, qty in consumption.items():
            product = self.env["product.product"].browse(product_id)
            src_location = product.property_stock_production or fallback_src
            # A move from the production location into the production location
            # is a no-op; fall back to the warehouse stock location instead.
            if src_location == production_location:
                src_location = fallback_src
            move = stock_move_obj.create(
                {
                    "name": _("Recipe consumption for %s") % sale_order.name,
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "product_uom": product.uom_id.id,
                    "location_id": src_location.id,
                    "location_dest_id": production_location.id,
                    "picking_type_id": picking_type.id,
                    "state": "draft",
                    "origin": sale_order.name,
                }
            )
            move._action_confirm()
            move._action_assign()
            move._action_done()
        return True

    def _match_bom(self, product_id, company_id):
        """Pick the most recent active BOM for a product and company."""
        return self.search(
            [
                ("product_id", "=", product_id),
                ("company_id", "=", company_id),
                ("active", "=", True),
            ],
            order="version desc",
            limit=1,
        )


class RecipeBomLine(models.Model):
    _name = "recipe.bom.line"
    _description = "Recipe BOM Line"

    bom_id = fields.Many2one("recipe.bom", required=True, ondelete="cascade")
    product_id = fields.Many2one(
        "product.product",
        string="Ingredient",
        required=True,
        domain="[('type', '=', 'product')]",
    )
    quantity = fields.Float(
        string="Quantity",
        digits=(16, 4),
        required=True,
        default=1.0,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        related="product_id.uom_id",
        store=True,
        readonly=True,
    )
    standard_cost = fields.Float(
        string="Unit Cost",
        digits=(16, 4),
        compute="_compute_standard_cost",
        store=True,
    )
    ingredient_cost = fields.Float(
        string="Ingredient Cost",
        digits=(16, 4),
        compute="_compute_ingredient_cost",
        store=True,
    )
    is_modifiable = fields.Boolean(
        string="Allow Modifiers",
        default=False,
        help="Whether this ingredient can be replaced or excluded by modifiers.",
    )
    modifier_options = fields.Text(
        string="Modifier Options JSON",
        help="Example: {'milk': [{'almond': 0.5, 'oat': 0.4}]}.",
    )

    @api.depends("product_id", "product_id.standard_price")
    def _compute_standard_cost(self):
        for line in self:
            line.standard_cost = line.product_id.standard_price

    @api.depends("quantity", "standard_cost")
    def _compute_ingredient_cost(self):
        for line in self:
            line.ingredient_cost = line.quantity * line.standard_cost

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Ingredient quantity must be positive."))
