"""The core tenant model: one tenant owns companies, users and subscriptions."""
import logging
import re

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


class SaaSTenant(models.Model):
    _name = "nexus.saas.tenant"
    _description = "SaaS Tenant"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Tenant Name", required=True, tracking=True)
    code = fields.Char(
        string="Subdomain / Code",
        required=True,
        copy=False,
        index=True,
        help="Unique subdomain-safe identifier. Used for routing and URLs.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    # Contact / ownership
    owner_partner_id = fields.Many2one(
        "res.partner",
        string="Owner Contact",
        help="Billing/primary contact for the tenant.",
    )
    owner_user_id = fields.Many2one(
        "res.users",
        string="Owner User",
        help="The first admin user created for this tenant.",
    )
    email = fields.Char(
        string="Admin Email",
        required=True,
        help="Email used for login and billing notifications.",
    )

    # Routing
    custom_domain = fields.Char(
        string="Custom Domain",
        help="e.g. erp.customer.com. Leave empty to use subdomain.nexus-engine.app.",
    )
    subdomain = fields.Char(
        string="Subdomain",
        compute="_compute_subdomain",
        store=True,
        readonly=True,
    )

    # Companies and users belonging to this tenant
    company_ids = fields.One2many(
        "res.company",
        "saas_tenant_id",
        string="Companies",
    )
    primary_company_id = fields.Many2one(
        "res.company",
        string="Primary Company",
        domain="[('saas_tenant_id', '=', id)]",
    )
    user_ids = fields.One2many(
        "res.users",
        "saas_tenant_id",
        string="Users",
    )

    # Plan / billing
    plan_id = fields.Many2one(
        "nexus.saas.plan",
        string="Plan",
        required=True,
        default=lambda self: self.env["nexus.saas.plan"]._get_default_plan().id,
    )
    max_users = fields.Integer(
        string="Max Users",
        related="plan_id.max_users",
        readonly=False,
        help="Override plan limit per tenant. 0 = unlimited.",
    )
    max_companies = fields.Integer(
        string="Max Companies",
        related="plan_id.max_companies",
        readonly=False,
        help="Override plan limit per tenant. 0 = unlimited.",
    )
    max_products = fields.Integer(
        string="Max Products",
        related="plan_id.max_products",
        readonly=False,
    )
    max_invoices_monthly = fields.Integer(
        string="Max Invoices / Month",
        related="plan_id.max_invoices_monthly",
        readonly=False,
    )
    storage_gb = fields.Integer(
        string="Storage GB",
        related="plan_id.storage_gb",
        readonly=False,
    )
    trial_end_date = fields.Date(
        string="Trial End Date",
        help="After this date the tenant must be on a paid subscription.",
    )
    is_trial = fields.Boolean(
        string="In Trial",
        compute="_compute_is_trial",
        search="_search_is_trial",
    )

    # Stripe linkage (filled by nexus_saas_billing)
    stripe_customer_id = fields.Char(string="Stripe Customer ID")

    # Notes
    notes = fields.Text()

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Tenant code must be unique."),
    ]

    @api.model
    def _get_default_plan(self):
        return self.env["nexus.saas.plan"].search([("is_default", "=", True)], limit=1)

    @api.constrains("code")
    def _check_code(self):
        for tenant in self:
            if not tenant.code:
                raise ValidationError(_("Tenant code is required."))
            if not _SUBDOMAIN_RE.match(tenant.code):
                raise ValidationError(
                    _(
                        "Tenant code must be a valid subdomain: lowercase letters, numbers, "
                        "and hyphens only; cannot start or end with a hyphen."
                    )
                )

    @api.constrains("custom_domain")
    def _check_custom_domain(self):
        for tenant in self:
            if tenant.custom_domain:
                # Very simple validation; real validation should use DNS records.
                if not re.match(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", tenant.custom_domain, re.I):
                    raise ValidationError(_("Custom domain format is invalid."))

    @api.depends("code")
    def _compute_subdomain(self):
        for tenant in self:
            tenant.subdomain = tenant.code

    @api.depends("trial_end_date", "state")
    def _compute_is_trial(self):
        today = fields.Date.today()
        for tenant in self:
            tenant.is_trial = bool(
                tenant.trial_end_date and tenant.trial_end_date >= today
                and tenant.state == "active"
            )

    @api.model
    def _search_is_trial(self, operator, value):
        today = fields.Date.today()
        if operator in ("=", "!="):
            is_trial = value if operator == "=" else not value
            if is_trial:
                return [
                    ("trial_end_date", ">=", today),
                    ("state", "=", "active"),
                ]
            return [
                "|",
                ("trial_end_date", "<", today),
                ("state", "!=", "active"),
            ]
        return []

    # ── Lifecycle helpers ───────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.state == "active":
                rec._provision_dns()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ("code", "custom_domain", "state")):
            for rec in self:
                if rec.state == "active":
                    rec._provision_dns()
                elif rec.state == "cancelled":
                    rec._deprovision_dns()
        return res

    def _provision_dns(self):
        """Create/update Cloudflare DNS records for this tenant."""
        self.ensure_one()
        dns = self.env["nexus.saas.cloudflare.dns"].sudo()
        try:
            dns.provision_tenant_subdomain(self.code)
            if self.custom_domain:
                dns.provision_tenant_custom_domain(self.custom_domain)
        except Exception:
            _logger.exception(
                "Failed to provision DNS for tenant %s. The tenant record was saved.",
                self.code,
            )

    def _deprovision_dns(self):
        """Remove Cloudflare DNS records when a tenant is cancelled."""
        self.ensure_one()
        dns = self.env["nexus.saas.cloudflare.dns"].sudo()
        try:
            base = self.env["ir.config_parameter"].sudo().get_param("nexus_saas.base_domain", "")
            if base:
                dns.delete_record(f"{self.code}.{base}")
            if self.custom_domain:
                dns.delete_record(self.custom_domain)
        except Exception:
            _logger.exception(
                "Failed to deprovision DNS for tenant %s.",
                self.code,
            )

    def action_activate(self):
        self.ensure_one()
        if not self.primary_company_id:
            raise UserError(_("Please create or select a primary company first."))
        self.write({"state": "active"})

    def action_suspend(self):
        self.write({"state": "suspended"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    # ── Quota helpers ─────────────────────────────────────────────────

    def _count_users(self):
        self.ensure_one()
        return self.env["res.users"].search_count([
            ("saas_tenant_id", "=", self.id),
            ("share", "=", False),
        ])

    def _count_companies(self):
        self.ensure_one()
        return len(self.company_ids)

    def _count_products(self):
        self.ensure_one()
        return self.env["product.template"].search_count([
            ("company_id", "in", self.company_ids.ids),
        ])

    def _count_invoices_this_month(self):
        self.ensure_one()
        today = fields.Date.today()
        start_of_month = today.replace(day=1)
        return self.env["account.move"].search_count([
            ("company_id", "in", self.company_ids.ids),
            ("move_type", "=", "out_invoice"),
            ("invoice_date", ">=", start_of_month),
            ("state", "=", "posted"),
        ])

    def _check_quota(self, metric, current, limit):
        if limit and current >= limit:
            raise UserError(
                _(
                    "Tenant '%(tenant)s' has reached the %(metric)s limit (%(limit)s). "
                    "Please upgrade your plan."
                )
                % {"tenant": self.name, "metric": metric, "limit": limit}
            )

    def check_user_quota(self):
        self._check_quota(
            _("users"), self._count_users(), self.max_users
        )

    def check_company_quota(self):
        self._check_quota(
            _("companies"), self._count_companies(), self.max_companies
        )

    def check_product_quota(self):
        self._check_quota(
            _("products"), self._count_products(), self.max_products
        )

    def check_invoice_quota(self):
        self._check_quota(
            _("monthly invoices"),
            self._count_invoices_this_month(),
            self.max_invoices_monthly,
        )

    # ── Provisioning ──────────────────────────────────────────────────

    @api.model
    def provision_tenant(self, name, code, email, plan_id=None, create_user=True):
        """Create a new tenant with a primary company and an admin user.

        This is the core self-service signup path.
        """
        if self.search([("code", "=", code)], limit=1):
            raise UserError(_("Tenant code '%s' is already taken.") % code)

        plan = self.env["nexus.saas.plan"].browse(plan_id) if plan_id else self._get_default_plan()
        if not plan:
            raise UserError(_("No default SaaS plan is configured."))

        # Run as superuser so provisioning always succeeds regardless of caller.
        env = self.sudo().env

        # Create primary company
        company_vals = {
            "name": name,
            "email": email,
            "saas_tenant_id": False,  # filled after tenant creation
        }
        company = env["res.company"].create(company_vals)

        tenant_vals = {
            "name": name,
            "code": code,
            "email": email,
            "plan_id": plan.id,
            "primary_company_id": company.id,
            "trial_end_date": fields.Date.add(fields.Date.today(), days=plan.trial_days),
            "state": "active",
        }
        tenant = env["nexus.saas.tenant"].create(tenant_vals)

        # Link the company back to the tenant
        company.write({"saas_tenant_id": tenant.id})

        # Create owner user
        if create_user:
            user_vals = {
                "name": name,
                "login": email,
                "email": email,
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "saas_tenant_id": tenant.id,
                "groups_id": [
                    (6, 0, [
                        env.ref("base.group_user").id,
                        env.ref("base.group_partner_manager").id,
                    ])
                ],
            }
            user = env["res.users"].create(user_vals)
            tenant.write({"owner_user_id": user.id})

        return tenant
