"""Executive Cockpit KPI builders — محرك مؤشرات لوحة القيادة.

Pure-data builders, mirroring the pattern established by
``nexus.finance.dashboard.chart`` in ``ai_enterprise_copilot``: each
method returns JSON-serializable data consumed by the dashboard's
JS/Chart.js frontend. Kept as an ``AbstractModel`` so it can be reused
from any controller without persisting state.

All calculations are rule-based and fully auditable (no black-box ML):
    * liquidity        — sum of cash/bank account balances
    * daily_sales       — today's posted customer invoices (+ POS if installed)
    * gross_margin      — (revenue - COGS) / revenue for the current month
    * branch_performance— per-company sales snapshot (multi-branch groups)
    * cash_flow_forecast_90d — weekly net cash buckets from AR/AP due dates
    * anomaly_alerts    — this week's expense vs trailing 4-week average
"""
from datetime import timedelta

from odoo import _, api, fields, models


class NexusCockpitKPI(models.AbstractModel):
    _name = "nexus.cockpit.kpi"
    _description = "Executive Cockpit KPI Builder"

    # ─────────────────────────────────────────────────────────────────
    # Liquidity
    # ─────────────────────────────────────────────────────────────────
    def liquidity_summary(self, company):
        lines = self.env["account.move.line"].search([
            ("company_id", "=", company.id),
            ("account_id.account_type", "in", ("asset_cash",)),
            ("parent_state", "=", "posted"),
        ])
        balance = sum(lines.mapped("balance"))
        return {
            "label": _("معدل السيولة / Liquidity"),
            "value": round(balance, 2),
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Daily sales
    # ─────────────────────────────────────────────────────────────────
    def daily_sales(self, company):
        today = fields.Date.today()
        moves = self.env["account.move"].search([
            ("company_id", "=", company.id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_date", "=", today),
        ])
        total = sum(
            m.amount_total if m.move_type == "out_invoice" else -m.amount_total
            for m in moves
        )
        pos_total = 0.0
        pos_order = self.env.get("pos.order")
        if pos_order is not None:
            orders = pos_order.sudo().search([
                ("company_id", "=", company.id),
                ("state", "in", ("paid", "done", "invoiced")),
                ("date_order", ">=", fields.Datetime.to_string(
                    fields.Datetime.now().replace(hour=0, minute=0, second=0)
                )),
            ])
            pos_total = sum(orders.mapped("amount_total"))
        return {
            "label": _("المبيعات اليومية / Daily Sales"),
            "value": round(total + pos_total, 2),
            "invoice_count": len(moves),
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Gross margin
    # ─────────────────────────────────────────────────────────────────
    def gross_margin(self, company):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        revenue_lines = self.env["account.move.line"].search([
            ("company_id", "=", company.id),
            ("account_id.account_type", "in", ("income", "income_other")),
            ("parent_state", "=", "posted"),
            ("date", ">=", month_start),
            ("date", "<=", today),
        ])
        cogs_lines = self.env["account.move.line"].search([
            ("company_id", "=", company.id),
            ("account_id.account_type", "in", ("expense_direct_cost", "expense")),
            ("parent_state", "=", "posted"),
            ("date", ">=", month_start),
            ("date", "<=", today),
        ])
        revenue = -sum(revenue_lines.mapped("balance"))  # income is credit-balance (negative)
        cogs = sum(cogs_lines.mapped("balance"))
        margin_pct = round((revenue - cogs) / revenue * 100, 2) if revenue else 0.0
        return {
            "label": _("هامش الربح الإجمالي / Gross Margin"),
            "value": margin_pct,
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Per-branch / per-company performance
    # ─────────────────────────────────────────────────────────────────
    def branch_performance(self, companies):
        result = []
        for company in companies:
            sales = self.daily_sales(company)
            result.append({
                "company_id": company.id,
                "name": company.display_name,
                "daily_sales": sales["value"],
                "invoice_count": sales["invoice_count"],
                "currency": company.currency_id.name,
            })
        return result

    # ─────────────────────────────────────────────────────────────────
    # 90-day cash flow forecast (weekly buckets)
    # ─────────────────────────────────────────────────────────────────
    def cash_flow_forecast_90d(self, company):
        today = fields.Date.today()
        horizon_end = today + timedelta(days=90)

        receivables = self.env["account.move.line"].search([
            ("company_id", "=", company.id),
            ("move_id.move_type", "=", "out_invoice"),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("date_maturity", ">=", today),
            ("date_maturity", "<=", horizon_end),
        ])
        payables = self.env["account.move.line"].search([
            ("company_id", "=", company.id),
            ("move_id.move_type", "=", "in_invoice"),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("date_maturity", ">=", today),
            ("date_maturity", "<=", horizon_end),
        ])

        buckets = []
        cursor = today
        running_balance = self.liquidity_summary(company)["value"]
        while cursor <= horizon_end:
            bucket_end = min(cursor + timedelta(days=6), horizon_end)
            in_amount = sum(
                l.amount_residual for l in receivables
                if l.date_maturity and cursor <= l.date_maturity <= bucket_end
            )
            out_amount = sum(
                l.amount_residual for l in payables
                if l.date_maturity and cursor <= l.date_maturity <= bucket_end
            )
            net = in_amount - out_amount
            running_balance += net
            buckets.append({
                "week_start": fields.Date.to_string(cursor),
                "inflow": round(in_amount, 2),
                "outflow": round(out_amount, 2),
                "net": round(net, 2),
                "projected_balance": round(running_balance, 2),
            })
            cursor = bucket_end + timedelta(days=1)

        return {
            "label": _("توقع التدفق النقدي / 90-Day Cash Flow Forecast"),
            "buckets": buckets,
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Anomaly / waste alerts
    # ─────────────────────────────────────────────────────────────────
    def anomaly_alerts(self, company, deviation_threshold_pct=20.0):
        """Flag expense accounts whose current-week total deviates from
        the trailing 4-week average by more than ``deviation_threshold_pct``.

        Generic on purpose: this naturally surfaces fuel/raw-material
        waste, unusual utility spikes, etc. without hard-coding any
        one industry's account structure.
        """
        today = fields.Date.today()
        week_start = today - timedelta(days=today.weekday())
        alerts = []

        expense_accounts = self.env["account.account"].search([
            ("company_id", "=", company.id),
            ("account_type", "in", ("expense", "expense_direct_cost")),
        ])
        for account in expense_accounts:
            current_lines = self.env["account.move.line"].search([
                ("company_id", "=", company.id),
                ("account_id", "=", account.id),
                ("parent_state", "=", "posted"),
                ("date", ">=", week_start),
                ("date", "<=", today),
            ])
            current_total = sum(current_lines.mapped("balance"))
            if not current_total:
                continue

            trailing_start = week_start - timedelta(weeks=4)
            trailing_end = week_start - timedelta(days=1)
            trailing_lines = self.env["account.move.line"].search([
                ("company_id", "=", company.id),
                ("account_id", "=", account.id),
                ("parent_state", "=", "posted"),
                ("date", ">=", trailing_start),
                ("date", "<=", trailing_end),
            ])
            trailing_total = sum(trailing_lines.mapped("balance"))
            trailing_avg = trailing_total / 4.0 if trailing_total else 0.0
            if not trailing_avg:
                continue

            deviation_pct = round((current_total - trailing_avg) / trailing_avg * 100, 1)
            if abs(deviation_pct) >= deviation_threshold_pct:
                alerts.append({
                    "account": account.display_name,
                    "current_week_total": round(current_total, 2),
                    "trailing_avg": round(trailing_avg, 2),
                    "deviation_pct": deviation_pct,
                    "severity": "high" if abs(deviation_pct) >= 40 else "medium",
                    "message": _(
                        "⚠️ %(account)s: %(dev)s%% %(direction)s trailing average"
                    ) % {
                        "account": account.display_name,
                        "dev": abs(deviation_pct),
                        "direction": _("above") if deviation_pct > 0 else _("below"),
                    },
                })
        return sorted(alerts, key=lambda a: abs(a["deviation_pct"]), reverse=True)

    # ─────────────────────────────────────────────────────────────────
    # Revenue trend (last 6 months)
    # ─────────────────────────────────────────────────────────────────
    def revenue_trend_6m(self, company):
        import calendar
        today = fields.Date.today()
        months = []
        for i in range(5, -1, -1):
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_start = fields.Date.to_date(f"{year}-{month:02d}-01")
            last_day = calendar.monthrange(year, month)[1]
            month_end = fields.Date.to_date(f"{year}-{month:02d}-{last_day:02d}")
            if i == 0:
                month_end = today
            lines = self.env["account.move.line"].search([
                ("company_id", "=", company.id),
                ("account_id.account_type", "in", ("income", "income_other")),
                ("parent_state", "=", "posted"),
                ("date", ">=", month_start),
                ("date", "<=", month_end),
            ])
            revenue = -sum(lines.mapped("balance"))
            months.append({
                "month": fields.Date.to_string(month_start),
                "revenue": round(revenue, 2),
            })
        return {
            "label": _("اتجاه الإيرادات / Revenue Trend (6M)"),
            "months": months,
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # AR aging summary
    # ─────────────────────────────────────────────────────────────────
    def ar_aging_summary(self, company):
        today = fields.Date.today()
        receivables = self.env["account.move.line"].search([
            ("company_id", "=", company.id),
            ("move_id.move_type", "=", "out_invoice"),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("date_maturity", "<", today),
        ])
        buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}
        for line in receivables:
            if not line.date_maturity:
                continue
            overdue = (today - line.date_maturity).days
            residual = line.amount_residual or 0.0
            if overdue <= 0:
                buckets["current"] += residual
            elif overdue <= 30:
                buckets["1_30"] += residual
            elif overdue <= 60:
                buckets["31_60"] += residual
            elif overdue <= 90:
                buckets["61_90"] += residual
            else:
                buckets["90_plus"] += residual
        return {
            "label": _("تأخر الذمم المدينة / AR Aging"),
            "buckets": {k: round(v, 2) for k, v in buckets.items()},
            "total_overdue": round(sum(buckets[k] for k in ("1_30", "31_60", "61_90", "90_plus")), 2),
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Top 5 expense accounts (current month)
    # ─────────────────────────────────────────────────────────────────
    def top_expenses(self, company, limit=5):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        expense_lines = self.env["account.move.line"].search([
            ("company_id", "=", company.id),
            ("account_id.account_type", "in", ("expense", "expense_direct_cost")),
            ("parent_state", "=", "posted"),
            ("date", ">=", month_start),
            ("date", "<=", today),
        ])
        account_totals = {}
        for line in expense_lines:
            acct = line.account_id.display_name
            account_totals[acct] = account_totals.get(acct, 0.0) + line.balance
        sorted_items = sorted(account_totals.items(), key=lambda x: x[1], reverse=True)[:limit]
        return {
            "label": _("أعلى المصروفات / Top Expenses (MTD)"),
            "items": [{"account": name, "amount": round(amt, 2)} for name, amt in sorted_items],
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Customer concentration risk (top 5 by revenue this quarter)
    # ─────────────────────────────────────────────────────────────────
    def customer_concentration(self, company, limit=5):
        today = fields.Date.today()
        quarter_start = today - timedelta(days=90)
        moves = self.env["account.move"].search([
            ("company_id", "=", company.id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", quarter_start),
            ("invoice_date", "<=", today),
        ])
        partner_totals = {}
        for move in moves:
            partner = move.partner_id.display_name
            partner_totals[partner] = partner_totals.get(partner, 0.0) + move.amount_untaxed
        total_revenue = sum(partner_totals.values())
        sorted_items = sorted(partner_totals.items(), key=lambda x: x[1], reverse=True)[:limit]
        items = []
        for name, amt in sorted_items:
            pct = round(amt / total_revenue * 100, 1) if total_revenue else 0.0
            items.append({"customer": name, "revenue": round(amt, 2), "share_pct": pct})
        top_share = sum(i["share_pct"] for i in items)
        return {
            "label": _("تركز العملاء / Customer Concentration"),
            "items": items,
            "top5_share_pct": round(top_share, 1),
            "risk_level": "high" if top_share >= 70 else ("medium" if top_share >= 50 else "low"),
            "currency": company.currency_id.name,
        }
