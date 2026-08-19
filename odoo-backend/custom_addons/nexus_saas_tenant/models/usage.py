"""Usage metrics per tenant for quota enforcement and billing."""
from odoo import api, fields, models, _


class SaaSUsageMetric(models.Model):
    _name = "nexus.saas.usage.metric"
    _description = "SaaS Usage Metric"
    _order = "name"

    name = fields.Char(string="Metric Name", required=True, translate=True)
    technical_name = fields.Char(
        string="Technical Name",
        required=True,
        help="Used in code and API payloads, e.g. users, products, storage_mb.",
    )
    unit = fields.Char(string="Unit", help="e.g. count, GB, MB, calls")
    description = fields.Text()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("technical_name_uniq", "unique(technical_name)", "Metric technical name must be unique."),
    ]


class SaaSUsageRecord(models.Model):
    _name = "nexus.saas.usage.record"
    _description = "SaaS Usage Record"
    _order = "period_date desc, tenant_id"

    tenant_id = fields.Many2one(
        "nexus.saas.tenant",
        required=True,
        index=True,
        ondelete="cascade",
    )
    metric_id = fields.Many2one(
        "nexus.saas.usage.metric",
        required=True,
        index=True,
    )
    period_date = fields.Date(
        required=True,
        index=True,
        help="The day/month this record belongs to.",
    )
    value = fields.Float(string="Usage Value", required=True)
    notes = fields.Char()

    _sql_constraints = [
        (
            "tenant_metric_period_uniq",
            "unique(tenant_id, metric_id, period_date)",
            "Only one usage record per tenant/metric/period.",
        ),
    ]

    @api.model
    def record(self, tenant, technical_name, value, period_date=None, notes=""):
        """Upsert a usage record for the given tenant and metric."""
        metric = self.env["nexus.saas.usage.metric"].search(
            [("technical_name", "=", technical_name)], limit=1
        )
        if not metric:
            metric = self.env["nexus.saas.usage.metric"].create({
                "name": technical_name,
                "technical_name": technical_name,
            })
        period = period_date or fields.Date.today()
        existing = self.search([
            ("tenant_id", "=", tenant.id),
            ("metric_id", "=", metric.id),
            ("period_date", "=", period),
        ], limit=1)
        if existing:
            existing.write({"value": value, "notes": notes})
            return existing
        return self.create({
            "tenant_id": tenant.id,
            "metric_id": metric.id,
            "period_date": period,
            "value": value,
            "notes": notes,
        })

    @api.model
    def _cron_aggregate_daily(self):
        """Compute yesterday's usage for active tenants."""
        today = fields.Date.today()
        yesterday = fields.Date.subtract(today, days=1)
        tenants = self.env["nexus.saas.tenant"].search([("state", "=", "active")])

        for tenant in tenants:
            user_count = self.env["res.users"].search_count([
                ("saas_tenant_id", "=", tenant.id),
                ("share", "=", False),
            ])
            product_count = self.env["product.template"].search_count([
                ("company_id", "in", tenant.company_ids.ids),
            ])
            self.record(tenant, "users", user_count, yesterday)
            self.record(tenant, "products", product_count, yesterday)
