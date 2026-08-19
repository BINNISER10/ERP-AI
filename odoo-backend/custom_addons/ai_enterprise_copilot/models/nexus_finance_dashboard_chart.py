# -*- coding: utf-8 -*-
"""Nexus Finance Dashboard Charts — مولّد بيانات الرسوم البيانية.

Pure-data builders consumed by the chart controllers. Each method
returns a dict with two keys:

    * ``labels`` — list of category labels (str)
    * ``values`` — list of numeric values (float)

Charts are rendered client-side (Chart.js) using this JSON.
"""

from datetime import date, timedelta

from odoo import api, fields, models, _


class NexusFinanceDashboardChart(models.AbstractModel):
    """JSON builders for dashboard charts."""

    _name = "nexus.finance.dashboard.chart"
    _description = "Nexus Finance Dashboard Chart Builder"

    # ─────────────────────────────────────────────────────────────────
    # Revenue vs Expense — last 6 months
    # ─────────────────────────────────────────────────────────────────
    def revenue_vs_expense(self, company):
        today = fields.Date.today()
        first_of_month = today.replace(day=1)
        months = []
        cursor = first_of_month
        for _ in range(6):
            months.insert(0, cursor)
            # previous month
            if cursor.month == 1:
                cursor = cursor.replace(year=cursor.year - 1, month=12)
            else:
                cursor = cursor.replace(month=cursor.month - 1)

        labels = [m.strftime("%Y-%m") for m in months]
        revenue = []
        expense = []
        for m in months:
            domain_start = m
            domain_end = self._last_day_of_month(m)
            rev, exp = self._period_totals(company, domain_start, domain_end)
            revenue.append(round(rev, 2))
            expense.append(round(exp, 2))
        return {
            "chart_type": "bar",
            "title": _("الإيرادات مقابل المصروفات / Revenue vs Expense"),
            "labels": labels,
            "datasets": [
                {"label": _("Revenue"), "data": revenue, "color": "#0B3D2E"},
                {"label": _("Expense"), "data": expense, "color": "#D32F2F"},
            ],
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Aging buckets
    # ─────────────────────────────────────────────────────────────────
    def aging_buckets(self, company, account_type):
        MoveLine = self.env["account.move.line"]
        as_of = fields.Date.today()
        lines = MoveLine.search([
            ("company_id", "=", company.id),
            ("date", "<=", as_of),
            ("parent_state", "=", "posted"),
            ("account_id.account_type", "=", account_type),
            ("reconciled", "=", False),
        ])
        buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
        for line in lines:
            days = (as_of - line.date).days
            amount = line.amount_residual
            if days <= 30:
                buckets["0-30"] += amount
            elif days <= 60:
                buckets["31-60"] += amount
            elif days <= 90:
                buckets["61-90"] += amount
            else:
                buckets["90+"] += amount
        label = (
            _("أعمار الذمم المدينة / Receivable Aging")
            if "receivable" in account_type
            else _("أعمار الذمم الدائنة / Payable Aging")
        )
        return {
            "chart_type": "doughnut",
            "title": label,
            "labels": list(buckets.keys()),
            "datasets": [
                {
                    "label": label,
                    "data": [round(v, 2) for v in buckets.values()],
                    "colors": ["#4CAF50", "#FFC107", "#FF9800", "#D32F2F"],
                }
            ],
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Cash position — last 30 days
    # ─────────────────────────────────────────────────────────────────
    def cash_position(self, company):
        MoveLine = self.env["account.move.line"]
        cash_accounts = self.env["account.account"].search([
            ("account_type", "in", ["asset_cash", "asset_bank"]),
            ("company_id", "=", company.id),
        ])
        today = fields.Date.today()
        days = []
        cursor = today
        for _ in range(30):
            days.insert(0, cursor)
            cursor = cursor - timedelta(days=1)
        values = []
        for d in days:
            line_sum = MoveLine.read_group([
                ("account_id", "in", cash_accounts.ids),
                ("date", "<=", d),
                ("parent_state", "=", "posted"),
            ], ["balance"], [])
            values.append(round(line_sum[0]["balance"] if line_sum else 0.0, 2))
        return {
            "chart_type": "line",
            "title": _("الوضع النقدي / Cash Position (30 days)"),
            "labels": [d.isoformat() for d in days],
            "datasets": [
                {"label": _("Cash"), "data": values, "color": "#0B3D2E"}
            ],
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Top 10 customers by YTD revenue
    # ─────────────────────────────────────────────────────────────────
    def top_customers(self, company):
        today = fields.Date.today()
        ytd_start = today.replace(month=1, day=1)
        Invoice = self.env["account.move"].search_read([
            ("company_id", "=", company.id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", ytd_start),
            ("invoice_date", "<=", today),
        ], ["partner_id", "amount_total"])
        totals = {}
        for inv in Invoice:
            partner_id = inv["partner_id"][0] if inv["partner_id"] else None
            if not partner_id:
                continue
            totals[partner_id] = totals.get(partner_id, 0.0) + inv["amount_total"]
        sorted_totals = sorted(totals.items(), key=lambda x: -x[1])[:10]
        partner_ids = [pid for pid, _ in sorted_totals]
        partner_map = {
            p.id: p.display_name
            for p in self.env["res.partner"].browse(partner_ids)
        }
        labels = [partner_map.get(pid, "?") for pid, _ in sorted_totals]
        values = [round(v, 2) for _, v in sorted_totals]
        return {
            "chart_type": "horizontalBar",
            "title": _("أهم 10 عملاء / Top 10 Customers (YTD)"),
            "labels": labels,
            "datasets": [
                {"label": _("Revenue"), "data": values, "color": "#0B3D2E"}
            ],
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # KPI summary — current period vs previous
    # ─────────────────────────────────────────────────────────────────
    def kpi_summary(self, company):
        today = fields.Date.today()
        first = today.replace(day=1)
        previous_start = (first - timedelta(days=1)).replace(day=1)
        previous_end = first - timedelta(days=1)

        cur_rev, cur_exp = self._period_totals(company, first, today)
        prv_rev, prv_exp = self._period_totals(company, previous_start, previous_end)

        return {
            "chart_type": "kpi",
            "title": _("مؤشرات الأداء / KPI Summary"),
            "kpis": [
                {
                    "label": _("Revenue (current month)"),
                    "value": round(cur_rev, 2),
                    "previous": round(prv_rev, 2),
                    "delta_pct": self._delta_pct(cur_rev, prv_rev),
                    "color": "#4CAF50",
                },
                {
                    "label": _("Expense (current month)"),
                    "value": round(cur_exp, 2),
                    "previous": round(prv_exp, 2),
                    "delta_pct": self._delta_pct(cur_exp, prv_exp),
                    "color": "#D32F2F",
                },
                {
                    "label": _("Net (current month)"),
                    "value": round(cur_rev - cur_exp, 2),
                    "previous": round(prv_rev - prv_exp, 2),
                    "delta_pct": self._delta_pct(
                        cur_rev - cur_exp, prv_rev - prv_exp
                    ),
                    "color": "#0B3D2E",
                },
            ],
            "currency": company.currency_id.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────
    def _period_totals(self, company, date_from, date_to):
        MoveLine = self.env["account.move.line"]
        groups = MoveLine.read_group([
            ("company_id", "=", company.id),
            ("parent_state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ], ["account_id", "balance"], ["account_id"])
        revenue = expense = 0.0
        for g in groups:
            acc = self.env["account.account"].browse(g["account_id"][0])
            bal = g["balance"]
            if acc.account_type in ("income", "income_other"):
                revenue += -bal
            elif acc.account_type in (
                "expense",
                "expense_depreciation",
                "expense_direct_cost",
            ):
                expense += bal
        return revenue, expense

    def _delta_pct(self, current, previous):
        if previous == 0:
            return 100.0 if current > 0 else -100.0 if current < 0 else 0.0
        return round(((current - previous) / abs(previous)) * 100.0, 1)

    def _last_day_of_month(self, d):
        if d.month == 12:
            return d.replace(day=31)
        return d.replace(month=d.month + 1, day=1) - timedelta(days=1)
