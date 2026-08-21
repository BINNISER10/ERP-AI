"""Business sector catalog — القطاعات ومصفوفة التوصيات الآلية.

Each sector defines the "sizing matrix" row shown to the customer:
which modules get auto-enabled, the baseline resource tier, and the
per-unit pricing add-ons used by ``nexus.saas.scoping.request`` to
compute the dynamic quote.
"""
from odoo import api, fields, models


class SaaSSector(models.Model):
    _name = "nexus.saas.sector"
    _description = "SaaS Business Sector"
    _order = "sequence, id"

    name = fields.Char(string="Sector", required=True, translate=True)
    code = fields.Char(string="Code", required=True, copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)

    # ── Auto-enabled modules for this sector ──
    module_technical_names = fields.Char(
        string="Auto-Enabled Modules",
        help="Comma-separated Odoo module technical names enabled "
        "automatically when a tenant picks this sector "
        "(e.g. 'point_of_sale,stock,nexus_fuel_station').",
    )

    # ── Resource sizing baseline (before per-unit add-ons) ──
    base_resource_tier = fields.Selection(
        [
            ("small", "Small — 2 vCPU / 4GB RAM / 20GB SSD"),
            ("medium", "Medium — 4 vCPU / 8GB RAM / 50GB SSD"),
            ("large", "Large — 8 vCPU / 16GB RAM / 100GB NVMe"),
            ("enterprise", "Enterprise — Custom / Dedicated Cluster"),
        ],
        default="small",
        required=True,
    )

    # ── Pricing baseline + per-unit add-ons (monthly, in plan currency) ──
    base_price_monthly = fields.Float(
        string="Base Monthly Price",
        default=0.0,
        help="Flat baseline fee for this sector before any per-unit add-ons.",
    )
    price_per_branch = fields.Float(string="Price / Branch", default=0.0)
    price_per_pos = fields.Float(string="Price / POS Terminal", default=0.0)
    price_per_warehouse = fields.Float(string="Price / Warehouse", default=0.0)
    price_per_employee_block = fields.Float(
        string="Price / 10 Employees",
        default=0.0,
        help="Charged per block of 10 employees (HR/payroll load).",
    )
    manufacturing_surcharge = fields.Float(
        string="Manufacturing Surcharge",
        default=0.0,
        help="Flat monthly surcharge when the tenant answers 'yes' to "
        "manufacturing/BOM operations.",
    )
    iot_surcharge = fields.Float(
        string="IoT Integration Surcharge",
        default=0.0,
        help="Flat monthly surcharge for field-device integration "
        "(fuel pumps, kitchen display systems, etc.).",
    )
    ecommerce_surcharge = fields.Float(
        string="E-Commerce Surcharge",
        default=0.0,
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Sector code must be unique."),
    ]

    @api.model
    def get_module_list(self, sector):
        """Return the list of module technical names for a sector record."""
        if not sector or not sector.module_technical_names:
            return []
        return [m.strip() for m in sector.module_technical_names.split(",") if m.strip()]
