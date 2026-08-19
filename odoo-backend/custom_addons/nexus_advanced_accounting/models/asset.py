"""Pillar 3 — Fixed Assets & Automated Depreciation.

When a Vendor Bill is validated for a product marked as a Fixed Asset,
an Asset record is queued in the Nexus Core.  The payload configures
calculation of depreciation so that the Core automatically creates the
monthly depreciation journal entries.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_fixed_asset = fields.Boolean(
        string="Fixed Asset",
        default=False,
        help="When set, vendor bills that include this product will "
        "auto-create a depreciable Asset in the Nexus Core.",
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_fixed_asset = fields.Boolean(
        string="Fixed Asset",
        related="product_tmpl_id.is_fixed_asset",
        store=True,
        readonly=False,
        help="Inherited from the product template.",
    )
