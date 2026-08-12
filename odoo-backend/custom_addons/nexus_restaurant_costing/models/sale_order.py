from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cogs_total = fields.Float(
        string="Total COGS",
        digits=(16, 4),
        compute="_compute_cogs",
        store=True,
    )
    profit_margin = fields.Float(
        string="Order Profit Margin (%)",
        digits=(5, 2),
        compute="_compute_profit_margin",
        store=True,
    )
    recipe_consumed = fields.Boolean(string="Recipe Inventory Consumed", default=False)

    @api.depends("order_line.cogs")
    def _compute_cogs(self):
        for order in self:
            order.cogs_total = sum(line.cogs for line in order.order_line)

    @api.depends("amount_untaxed", "cogs_total")
    def _compute_profit_margin(self):
        for order in self:
            if order.amount_untaxed:
                order.profit_margin = ((order.amount_untaxed - order.cogs_total) / order.amount_untaxed) * 100.0
            else:
                order.profit_margin = 0.0

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if not order.recipe_consumed:
                boms = self.env["recipe.bom"].search([("company_id", "=", order.company_id.id)])
                if boms:
                    boms[0].consume_for_sale_order(order)
                order.recipe_consumed = True
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cogs = fields.Float(
        string="COGS",
        digits=(16, 4),
        compute="_compute_line_cogs",
        store=True,
    )
    modifiers = fields.Text(string="Modifiers JSON")

    @api.depends("product_id", "product_uom_qty", "modifiers")
    def _compute_line_cogs(self):
        for line in self:
            mods = {}
            if line.modifiers:
                try:
                    import json

                    mods = json.loads(line.modifiers)
                except (ValueError, TypeError):
                    mods = {}
            line.cogs = self.env["menu.item"].get_cost_for_order_line(
                line.product_id.id,
                modifiers=mods,
                quantity=line.product_uom_qty,
            )
