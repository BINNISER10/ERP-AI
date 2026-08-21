"""AI Scoping & Checkout Engine — محرك الفحص الذكي وإغلاق البيع الذاتي.

Captures the business-profiling answers from the public website wizard,
computes a rule-based module/resource-tier recommendation and a dynamic
price quote, then (on checkout) provisions the tenant + subscription and
hands off to ``nexus_saas_billing``'s existing Stripe checkout flow.

Rule-based, not ML — deliberately. The pricing/sizing logic here is a
transparent, auditable formula (see ``_compute_quote``) rather than an
opaque model, which is what a paying customer and a finance team both
need to trust an automated quote.
"""
import logging
import math

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaaSScopingRequest(models.Model):
    _name = "nexus.saas.scoping.request"
    _description = "SaaS Scoping & Quote Request"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        string="Reference",
        default=lambda self: _("New"),
        copy=False,
        readonly=True,
    )
    company_name = fields.Char(string="Company Name", required=True)
    contact_email = fields.Char(string="Contact Email", required=True)
    contact_phone = fields.Char(string="Contact Phone")

    sector_id = fields.Many2one("nexus.saas.sector", string="Sector", required=True)

    # ── Operational sizing inputs (the wizard's questions) ──
    branches_count = fields.Integer(string="Branches", default=1)
    pos_count = fields.Integer(string="POS Terminals / Cashiers", default=0)
    warehouse_main_count = fields.Integer(string="Main Warehouses", default=1)
    warehouse_sub_count = fields.Integer(string="Sub Warehouses", default=0)
    employees_count = fields.Integer(string="Total Employees", default=1)
    has_manufacturing = fields.Boolean(string="Manufacturing / BOM Operations")
    has_iot_integration = fields.Boolean(
        string="Field Device Integration",
        help="Fuel pumps, kitchen display systems, IoT sensors, etc.",
    )
    has_ecommerce = fields.Boolean(string="Needs Online Store")

    billing_interval = fields.Selection(
        [("month", "Monthly"), ("year", "Yearly")],
        default="month",
        required=True,
    )

    # ── Computed recommendation / quote ──
    recommended_modules = fields.Char(
        string="Recommended Modules", readonly=True, compute="_compute_quote", store=True
    )
    resource_tier = fields.Selection(
        [
            ("small", "Small"),
            ("medium", "Medium"),
            ("large", "Large"),
            ("enterprise", "Enterprise"),
        ],
        readonly=True, compute="_compute_quote", store=True,
    )
    price_monthly = fields.Float(readonly=True, compute="_compute_quote", store=True)
    price_yearly = fields.Float(readonly=True, compute="_compute_quote", store=True)
    price_breakdown = fields.Text(readonly=True, compute="_compute_quote", store=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("quoted", "Quoted"),
            ("checkout", "Checkout Started"),
            ("provisioned", "Provisioned"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    tenant_id = fields.Many2one("nexus.saas.tenant", string="Tenant", readonly=True, copy=False)
    subscription_id = fields.Many2one(
        "nexus.saas.subscription", string="Subscription", readonly=True, copy=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "nexus.saas.scoping.request"
                ) or _("New")
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────
    # Pricing / sizing engine
    # ─────────────────────────────────────────────────────────────────
    # Resource-tier "load score" thresholds. Score is a weighted sum of
    # operational size signals; crossing a threshold bumps the tier up
    # from the sector's baseline (never down — a fuel station's baseline
    # is already "medium", for instance).
    _TIER_ORDER = ["small", "medium", "large", "enterprise"]
    _TIER_THRESHOLDS = [(0, "small"), (15, "medium"), (40, "large"), (80, "enterprise")]

    @api.depends(
        "sector_id",
        "branches_count",
        "pos_count",
        "warehouse_main_count",
        "warehouse_sub_count",
        "employees_count",
        "has_manufacturing",
        "has_iot_integration",
        "has_ecommerce",
        "billing_interval",
    )
    def _compute_quote(self):
        for rec in self:
            if not rec.sector_id:
                rec.recommended_modules = False
                rec.resource_tier = "small"
                rec.price_monthly = 0.0
                rec.price_yearly = 0.0
                rec.price_breakdown = False
                continue

            sector = rec.sector_id
            modules = set(self.env["nexus.saas.sector"].get_module_list(sector))
            if rec.has_manufacturing:
                modules.add("mrp")
            if rec.has_ecommerce:
                modules.add("website_sale")
            rec.recommended_modules = ",".join(sorted(modules))

            rec.resource_tier = rec._compute_resource_tier(sector)
            monthly, breakdown = rec._compute_price_monthly(sector)
            rec.price_monthly = monthly
            # Yearly = 10x monthly (2 months free) — standard SaaS discount.
            rec.price_yearly = round(monthly * 10, 2)
            rec.price_breakdown = "\n".join(breakdown)

    def _load_score(self):
        self.ensure_one()
        return (
            self.branches_count * 3
            + self.pos_count * 2
            + (self.warehouse_main_count + self.warehouse_sub_count) * 2
            + math.ceil(self.employees_count / 10.0) * 2
            + (10 if self.has_manufacturing else 0)
            + (5 if self.has_iot_integration else 0)
            + (5 if self.has_ecommerce else 0)
        )

    def _compute_resource_tier(self, sector):
        self.ensure_one()
        score = self._load_score()
        computed_tier = "small"
        for threshold, tier in self._TIER_THRESHOLDS:
            if score >= threshold:
                computed_tier = tier
        # Never downgrade below the sector's own baseline tier.
        baseline_idx = self._TIER_ORDER.index(sector.base_resource_tier)
        computed_idx = self._TIER_ORDER.index(computed_tier)
        return self._TIER_ORDER[max(baseline_idx, computed_idx)]

    def _compute_price_monthly(self, sector):
        self.ensure_one()
        breakdown = []
        total = sector.base_price_monthly
        breakdown.append(_("Base (%s): %.2f") % (sector.name, sector.base_price_monthly))

        if self.branches_count > 1 and sector.price_per_branch:
            extra_branches = self.branches_count - 1
            amount = extra_branches * sector.price_per_branch
            total += amount
            breakdown.append(_("Extra branches (%d x %.2f): %.2f") % (
                extra_branches, sector.price_per_branch, amount
            ))

        if self.pos_count and sector.price_per_pos:
            amount = self.pos_count * sector.price_per_pos
            total += amount
            breakdown.append(_("POS terminals (%d x %.2f): %.2f") % (
                self.pos_count, sector.price_per_pos, amount
            ))

        total_warehouses = self.warehouse_main_count + self.warehouse_sub_count
        if total_warehouses > 1 and sector.price_per_warehouse:
            extra_warehouses = total_warehouses - 1
            amount = extra_warehouses * sector.price_per_warehouse
            total += amount
            breakdown.append(_("Extra warehouses (%d x %.2f): %.2f") % (
                extra_warehouses, sector.price_per_warehouse, amount
            ))

        if self.employees_count and sector.price_per_employee_block:
            blocks = math.ceil(self.employees_count / 10.0)
            amount = blocks * sector.price_per_employee_block
            total += amount
            breakdown.append(_("Employee blocks (%d x 10, %.2f each): %.2f") % (
                blocks, sector.price_per_employee_block, amount
            ))

        if self.has_manufacturing and sector.manufacturing_surcharge:
            total += sector.manufacturing_surcharge
            breakdown.append(_("Manufacturing surcharge: %.2f") % sector.manufacturing_surcharge)

        if self.has_iot_integration and sector.iot_surcharge:
            total += sector.iot_surcharge
            breakdown.append(_("IoT integration surcharge: %.2f") % sector.iot_surcharge)

        if self.has_ecommerce and sector.ecommerce_surcharge:
            total += sector.ecommerce_surcharge
            breakdown.append(_("E-commerce surcharge: %.2f") % sector.ecommerce_surcharge)

        breakdown.append(_("Total monthly: %.2f") % total)
        return round(total, 2), breakdown

    # ─────────────────────────────────────────────────────────────────
    # Zero-touch checkout: quote -> tenant + subscription -> Stripe
    # ─────────────────────────────────────────────────────────────────
    def action_start_checkout(self, tenant_code, admin_email, admin_password=None):
        """Provision the tenant (trialing) + subscription and return a
        Stripe checkout URL. Tenant activation happens automatically
        when ``nexus_saas_billing``'s webhook receives payment
        confirmation — no human involvement required.
        """
        self.ensure_one()
        if self.state not in ("draft", "quoted"):
            raise UserError(_("This scoping request has already started checkout."))
        if not self.price_monthly:
            raise UserError(_("Cannot checkout a request with no computed quote."))

        Plan = self.env["nexus.saas.plan"]
        plan = Plan.search([("is_default", "=", True)], limit=1)
        if not plan:
            raise UserError(_("No default SaaS plan configured; cannot start checkout."))

        Tenant = self.env["nexus.saas.tenant"]
        tenant = Tenant.provision_tenant(
            name=self.company_name,
            code=tenant_code,
            email=admin_email or self.contact_email,
            plan_id=plan.id,
            create_user=True,
        )
        if admin_password:
            tenant.owner_user_id.sudo().write({"password": admin_password})

        subscription = self.env["nexus.saas.subscription"].create({
            "tenant_id": tenant.id,
            "plan_id": plan.id,
            "billing_interval": self.billing_interval,
            "state": "trialing",
            "trial_end": tenant.trial_end_date,
        })

        self.write({
            "tenant_id": tenant.id,
            "subscription_id": subscription.id,
            "state": "checkout",
        })

        action = subscription.action_create_stripe_checkout()
        return {
            "checkout_url": action.get("url"),
            "tenant_code": tenant.code,
            "scoping_request": self.name,
        }

    def action_mark_provisioned(self):
        """Called once the linked subscription/tenant is confirmed active
        (e.g. from the Stripe webhook flow) to close the loop on this
        scoping request for reporting purposes.
        """
        for rec in self:
            if rec.tenant_id and rec.tenant_id.state == "active":
                rec.state = "provisioned"
