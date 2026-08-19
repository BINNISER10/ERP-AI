# -*- coding: utf-8 -*-
"""Nexus Finance Report Renderer — local fallback report engine.

When the Nexus Core (ERPNext) backend is unavailable, this renderer
builds the same financial reports from Odoo's native ``account.*``
models. The numbers won't be quite as rich as ERPNext's, but the UI
stays consistent — the user never sees a difference.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class NexusFinanceReportRenderer(models.AbstractModel):
    """Pure-Python financial report renderer used as the bridge fallback."""

    _name = "nexus.finance.report.renderer"
    _description = "Nexus Finance Report Local Renderer"

    # ── Public entry point ──
    def render(self, wizard):
        """Dispatch to the right renderer based on ``wizard.report_type``."""
        method = "render_" + wizard.report_type
        if not hasattr(self, method):
            return self._render_not_implemented(wizard.report_type)
        return getattr(self, method)(wizard)

    # ═══════════════════════════════════════════════════════════════════
    # 1. Balance Sheet
    # ═══════════════════════════════════════════════════════════════════
    def render_balance_sheet(self, wiz):
        MoveLine = self.env["account.move.line"]
        company = wiz.company_id
        domain = [
            ("company_id", "=", company.id),
            ("date", "<=", wiz.date_to),
            ("parent_state", "=", "posted"),
        ]

        lines = MoveLine.read_group(
            domain,
            ["account_id", "debit", "credit", "balance"],
            ["account_id"],
        )

        grouped = {"asset": [], "liability": [], "equity": []}
        totals = {"asset": 0.0, "liability": 0.0, "equity": 0.0}

        for line in lines:
            acc = self.env["account.account"].browse(line["account_id"][0])
            if not acc.account_type:
                continue
            balance = line["balance"]
            if acc.account_type in ("asset_receivable", "asset_cash", "asset_current", "asset_non_current", "asset_prepayment", "asset_fixed"):
                grouped["asset"].append((acc.display_name, balance))
                totals["asset"] += balance
            elif acc.account_type in ("liability_payable", "liability_current", "liability_non_current"):
                grouped["liability"].append((acc.display_name, balance))
                totals["liability"] += balance
            elif acc.account_type in ("equity", "equity_unaffected"):
                grouped["equity"].append((acc.display_name, balance))
                totals["equity"] += balance

        return self._build_balance_sheet_html(grouped, totals, wiz)

    # ═══════════════════════════════════════════════════════════════════
    # 2. Profit & Loss
    # ═══════════════════════════════════════════════════════════════════
    def render_profit_loss(self, wiz):
        MoveLine = self.env["account.move.line"]
        domain = [
            ("company_id", "=", wiz.company_id.id),
            ("date", ">=", wiz.date_from),
            ("date", "<=", wiz.date_to),
            ("parent_state", "=", "posted"),
        ]
        lines = MoveLine.read_group(
            domain,
            ["account_id", "debit", "credit", "balance"],
            ["account_id"],
        )
        revenue = 0.0
        expense = 0.0
        revenue_rows = []
        expense_rows = []
        for line in lines:
            acc = self.env["account.account"].browse(line["account_id"][0])
            balance = line["balance"]
            if acc.account_type in ("income", "income_other"):
                revenue += -balance  # revenue has credit balance
                revenue_rows.append((acc.display_name, -balance))
            elif acc.account_type in ("expense", "expense_depreciation", "expense_direct_cost"):
                expense += balance  # expense has debit balance
                expense_rows.append((acc.display_name, balance))

        net = revenue - expense
        return self._build_profit_loss_html(
            revenue_rows, expense_rows, revenue, expense, net, wiz
        )

    # ═══════════════════════════════════════════════════════════════════
    # 3. Cash Flow
    # ═══════════════════════════════════════════════════════════════════
    def render_cash_flow(self, wiz):
        # Simplified cash-flow using account.move.line aggregation
        MoveLine = self.env["account.move.line"]
        cash_accounts = self.env["account.account"].search([
            ("account_type", "in", ["asset_cash", "asset_bank"]),
            ("company_id", "=", wiz.company_id.id),
        ])
        opening = MoveLine.read_group(
            [
                ("account_id", "in", cash_accounts.ids),
                ("date", "<", wiz.date_from),
                ("parent_state", "=", "posted"),
            ],
            ["balance"],
            [],
        )
        opening_balance = opening[0]["balance"] if opening else 0.0

        movements = MoveLine.read_group(
            [
                ("account_id", "in", cash_accounts.ids),
                ("date", ">=", wiz.date_from),
                ("date", "<=", wiz.date_to),
                ("parent_state", "=", "posted"),
            ],
            ["balance"],
            [],
        )
        net_movement = movements[0]["balance"] if movements else 0.0
        closing = opening_balance + net_movement

        return self._build_cash_flow_html(opening_balance, net_movement, closing, wiz)

    # ═══════════════════════════════════════════════════════════════════
    # 4. Trial Balance
    # ═══════════════════════════════════════════════════════════════════
    def render_trial_balance(self, wiz):
        MoveLine = self.env["account.move.line"]
        domain = [
            ("company_id", "=", wiz.company_id.id),
            ("date", "<=", wiz.date_to),
            ("parent_state", "=", "posted"),
        ]
        groups = MoveLine.read_group(
            domain, ["account_id", "debit", "credit"], ["account_id"]
        )
        rows = []
        total_debit = total_credit = 0.0
        for g in groups:
            acc = self.env["account.account"].browse(g["account_id"][0])
            rows.append((acc.code, acc.display_name, g["debit"], g["credit"]))
            total_debit += g["debit"]
            total_credit += g["credit"]
        return self._build_trial_balance_html(rows, total_debit, total_credit, wiz)

    # ═══════════════════════════════════════════════════════════════════
    # 5. General Ledger
    # ═══════════════════════════════════════════════════════════════════
    def render_general_ledger(self, wiz):
        domain = [
            ("company_id", "=", wiz.company_id.id),
            ("date", ">=", wiz.date_from),
            ("date", "<=", wiz.date_to),
            ("parent_state", "=", "posted"),
        ]
        if wiz.account_id:
            domain.append(("account_id", "=", wiz.account_id.id))
        if wiz.partner_id:
            domain.append(("partner_id", "=", wiz.partner_id.id))
        lines = self.env["account.move.line"].search(
            domain, order="date,id"
        )
        rows = []
        for line in lines:
            rows.append({
                "date": line.date,
                "move": line.move_id.name,
                "account": line.account_id.display_name,
                "partner": line.partner_id.display_name if line.partner_id else "",
                "label": line.name or line.move_id.ref or "",
                "debit": line.debit,
                "credit": line.credit,
            })
        return self._build_general_ledger_html(rows, wiz)

    # ═══════════════════════════════════════════════════════════════════
    # 6. Receivable Aging
    # ═══════════════════════════════════════════════════════════════════
    def render_aging_receivable(self, wiz):
        return self._render_aging(wiz, "asset_receivable", "Receivable")

    # ═══════════════════════════════════════════════════════════════════
    # 7. Payable Aging
    # ═══════════════════════════════════════════════════════════════════
    def render_aging_payable(self, wiz):
        return self._render_aging(wiz, "liability_payable", "Payable")

    def _render_aging(self, wiz, account_type, label):
        MoveLine = self.env["account.move.line"]
        as_of = wiz.date_to
        domain = [
            ("company_id", "=", wiz.company_id.id),
            ("date", "<=", as_of),
            ("parent_state", "=", "posted"),
            ("account_id.account_type", "=", account_type),
            ("reconciled", "=", False),
        ]
        lines = MoveLine.search(domain)
        buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
        partner_totals = {}
        for line in lines:
            days = (as_of - line.date).days
            amount = line.amount_residual
            if days <= 30:
                bucket = "0-30"
            elif days <= 60:
                bucket = "31-60"
            elif days <= 90:
                bucket = "61-90"
            else:
                bucket = "90+"
            buckets[bucket] += amount
            partner_totals.setdefault(
                line.partner_id.display_name if line.partner_id else "Unknown",
                {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0, "total": 0.0},
            )
            partner_totals[line.partner_id.display_name if line.partner_id else "Unknown"][bucket] += amount
            partner_totals[line.partner_id.display_name if line.partner_id else "Unknown"]["total"] += amount
        return self._build_aging_html(buckets, partner_totals, label, wiz)

    # ═══════════════════════════════════════════════════════════════════
    # 8. Budget Variance
    # ═══════════════════════════════════════════════════════════════════
    def render_budget_variance(self, wiz):
        # Use Odoo analytic budgets if present
        Budget = self.env.get("crossovered.budget")
        if not Budget:
            return self._render_not_implemented("budget_variance")
        budgets = Budget.search([
            ("date_from", "<=", wiz.date_to),
            ("date_to", ">=", wiz.date_from),
            ("company_id", "=", wiz.company_id.id),
        ])
        rows = []
        for budget in budgets:
            for line in budget.crossovered_budget_line:
                rows.append({
                    "budget": budget.name,
                    "analytic": line.analytic_account_id.display_name,
                    "planned": line.planned_amount,
                    "actual": line.achieved_amount,
                    "variance": line.planned_amount - line.achieved_amount,
                })
        return self._build_budget_variance_html(rows, wiz)

    # ═══════════════════════════════════════════════════════════════════
    # 9. Cost Center Report
    # ═══════════════════════════════════════════════════════════════════
    def render_cost_center(self, wiz):
        # Cost center report based on analytic distribution
        lines = self.env["account.analytic.line"].search([
            ("company_id", "=", wiz.company_id.id),
            ("date", ">=", wiz.date_from),
            ("date", "<=", wiz.date_to),
        ])
        totals = {}
        for line in lines:
            key = line.account_id.display_name
            totals.setdefault(key, 0.0)
            totals[key] += line.amount
        rows = sorted(totals.items(), key=lambda x: -x[1])
        return self._build_cost_center_html(rows, wiz)

    # ─────────────────────────────────────────────────────────────────
    # HTML builders — kept simple, table-based, print-friendly
    # ─────────────────────────────────────────────────────────────────
    def _build_balance_sheet_html(self, grouped, totals, wiz):
        sections = []
        for section_key, label in [
            ("asset", "الأصول / Assets"),
            ("liability", "الخصوم / Liabilities"),
            ("equity", "حقوق الملكية / Equity"),
        ]:
            rows_html = "".join(
                "<tr><td>%s</td><td class='text-end'>%s</td></tr>"
                % (self._x(name), self._money(bal))
                for name, bal in grouped[section_key]
                if abs(bal) > 0.001
            )
            sections.append(
                "<h5 class='mt-3'>%s</h5>"
                "<table class='table table-sm'>"
                "<thead><tr><th>الحساب</th><th class='text-end'>الرصيد</th></tr></thead>"
                "<tbody>%s</tbody>"
                "<tfoot><tr class='table-light'><th>إجمالي %s</th>"
                "<th class='text-end'>%s</th></tr></tfoot>"
                "</table>" % (label, rows_html, label, self._money(totals[section_key]))
            )
        header = self._render_report_header("الميزانية العمومية", wiz)
        footer = self._render_report_footer(wiz)
        return header + "".join(sections) + footer

    def _build_profit_loss_html(self, rev_rows, exp_rows, rev_total, exp_total, net, wiz):
        rev_html = "".join(
            "<tr><td>%s</td><td class='text-end'>%s</td></tr>"
            % (self._x(n), self._money(a))
            for n, a in rev_rows if abs(a) > 0.001
        )
        exp_html = "".join(
            "<tr><td>%s</td><td class='text-end'>%s</td></tr>"
            % (self._x(n), self._money(a))
            for n, a in exp_rows if abs(a) > 0.001
        )
        net_color = "text-success" if net >= 0 else "text-danger"
        html = (
            self._render_report_header("قائمة الدخل", wiz)
            + "<h5 class='mt-3'>الإيرادات / Revenue</h5>"
            "<table class='table table-sm'>"
            "<tbody>%s</tbody>"
            "<tfoot><tr class='table-light'><th>إجمالي الإيرادات</th>"
            "<th class='text-end'>%s</th></tr></tfoot></table>"
            "<h5 class='mt-3'>المصروفات / Expenses</h5>"
            "<table class='table table-sm'>"
            "<tbody>%s</tbody>"
            "<tfoot><tr class='table-light'><th>إجمالي المصروفات</th>"
            "<th class='text-end'>%s</th></tr></tfoot></table>"
            "<div class='alert alert-light text-center mt-3'>"
            "<strong>صافي الربح / Net %s:</strong> "
            "<span class='%s h4 mb-0'>%s</span></div>"
            + self._render_report_footer(wiz)
        ) % (rev_html, self._money(rev_total),
             exp_html, self._money(exp_total),
             "Profit" if net >= 0 else "Loss", net_color, self._money(net))
        return html

    def _build_cash_flow_html(self, opening, net, closing, wiz):
        html = (
            self._render_report_header("التدفقات النقدية", wiz)
            + "<table class='table'>"
            "<tr><th>الرصيد الافتتاحي / Opening Balance</th>"
            "<td class='text-end'>%s</td></tr>"
            "<tr><th>صافي الحركة / Net Movement</th>"
            "<td class='text-end'>%s</td></tr>"
            "<tr class='table-primary'><th>الرصيد الختامي / Closing Balance</th>"
            "<th class='text-end'>%s</th></tr>"
            "</table>" + self._render_report_footer(wiz)
        ) % (self._money(opening), self._money(net), self._money(closing))
        return html

    def _build_trial_balance_html(self, rows, total_debit, total_credit, wiz):
        body = "".join(
            "<tr><td>%s</td><td>%s</td>"
            "<td class='text-end'>%s</td><td class='text-end'>%s</td></tr>"
            % (self._x(code), self._x(name), self._money(d), self._money(c))
            for code, name, d, c in rows
        )
        diff = total_debit - total_credit
        diff_alert = ""
        if abs(diff) > 0.01:
            diff_alert = (
                "<div class='alert alert-warning mt-2'>"
                "<i class='fa fa-exclamation-triangle'></i> "
                "فرق غير متوازن: %s</div>" % self._money(diff)
            )
        html = (
            self._render_report_header("ميزان المراجعة", wiz)
            + "<table class='table table-sm'>"
            "<thead><tr><th>الكود</th><th>الحساب</th>"
            "<th class='text-end'>مدين</th><th class='text-end'>دائن</th></tr></thead>"
            "<tbody>%s</tbody>"
            "<tfoot><tr class='table-light'>"
            "<th colspan='2'>الإجمالي</th>"
            "<th class='text-end'>%s</th><th class='text-end'>%s</th></tr>"
            "</tfoot></table>%s" + self._render_report_footer(wiz)
        ) % (body, self._money(total_debit), self._money(total_credit), diff_alert)
        return html

    def _build_general_ledger_html(self, rows, wiz):
        body = "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            "<td>%s</td>"
            "<td class='text-end'>%s</td>"
            "<td class='text-end'>%s</td></tr>"
            % (r["date"], self._x(r["move"]), self._x(r["account"]),
               self._x(r["partner"]), self._x(r["label"]),
               self._money(r["debit"]), self._money(r["credit"]))
            for r in rows
        )
        html = (
            self._render_report_header("دفتر الأستاذ العام", wiz)
            + "<table class='table table-sm'>"
            "<thead><tr><th>التاريخ</th><th>القيد</th><th>الحساب</th>"
            "<th>الجهة</th><th>البيان</th>"
            "<th class='text-end'>مدين</th>"
            "<th class='text-end'>دائن</th></tr></thead>"
            "<tbody>%s</tbody></table>" + self._render_report_footer(wiz)
        ) % body
        return html

    def _build_aging_html(self, buckets, partner_totals, label, wiz):
        bucket_rows = "".join(
            "<tr><th>%s</th><td class='text-end'>%s</td></tr>"
            % (b, self._money(v)) for b, v in buckets.items()
        )
        total = sum(buckets.values())
        partner_rows = "".join(
            "<tr><td>%s</td>"
            "<td class='text-end'>%s</td><td class='text-end'>%s</td>"
            "<td class='text-end'>%s</td><td class='text-end'>%s</td>"
            "<td class='text-end fw-bold'>%s</td></tr>"
            % (self._x(name),
               self._money(d["0-30"]), self._money(d["31-60"]),
               self._money(d["61-90"]), self._money(d["90+"]),
               self._money(d["total"]))
            for name, d in sorted(partner_totals.items(), key=lambda x: -x[1]["total"])
        )
        html = (
            self._render_report_header("أعمار الذمم %s" % label, wiz)
            + "<h6 class='mt-2'>ملخص حسب الفترة / Period Summary</h6>"
            "<table class='table table-sm'>"
            "<tbody>%s</tbody>"
            "<tfoot><tr class='table-primary'>"
            "<th>الإجمالي الكلي</th>"
            "<th class='text-end'>%s</th></tr></tfoot></table>"
            "<h6 class='mt-3'>حسب العميل/المورد / By Partner</h6>"
            "<table class='table table-sm'>"
            "<thead><tr><th>الجهة</th>"
            "<th class='text-end'>0-30</th><th class='text-end'>31-60</th>"
            "<th class='text-end'>61-90</th><th class='text-end'>90+</th>"
            "<th class='text-end'>الإجمالي</th></tr></thead>"
            "<tbody>%s</tbody></table>"
            + self._render_report_footer(wiz)
        ) % (bucket_rows, self._money(total), partner_rows)
        return html

    def _build_budget_variance_html(self, rows, wiz):
        body = "".join(
            "<tr><td>%s</td><td>%s</td>"
            "<td class='text-end'>%s</td>"
            "<td class='text-end'>%s</td>"
            "<td class='text-end %s'>%s</td></tr>"
            % (self._x(r["budget"]), self._x(r["analytic"]),
               self._money(r["planned"]),
               self._money(r["actual"]),
               "text-danger" if r["variance"] < 0 else "text-success",
               self._money(r["variance"]))
            for r in rows
        )
        html = (
            self._render_report_header("انحراف الميزانية", wiz)
            + "<table class='table table-sm'>"
            "<thead><tr><th>الميزانية</th><th>المركز التحليلي</th>"
            "<th class='text-end'>المخطط</th>"
            "<th class='text-end'>الفعلي</th>"
            "<th class='text-end'>الانحراف</th></tr></thead>"
            "<tbody>%s</tbody></table>" + self._render_report_footer(wiz)
        ) % body
        return html

    def _build_cost_center_html(self, rows, wiz):
        body = "".join(
            "<tr><td>%s</td><td class='text-end'>%s</td></tr>"
            % (self._x(name), self._money(amount))
            for name, amount in rows
        )
        total = sum(a for _, a in rows)
        html = (
            self._render_report_header("تقرير مراكز التكلفة", wiz)
            + "<table class='table table-sm'>"
            "<thead><tr><th>المركز التحليلي</th>"
            "<th class='text-end'>المبلغ</th></tr></thead>"
            "<tbody>%s</tbody>"
            "<tfoot><tr class='table-primary'>"
            "<th>الإجمالي</th>"
            "<th class='text-end'>%s</th></tr></tfoot></table>"
            + self._render_report_footer(wiz)
        ) % (body, self._money(total))
        return html

    def _render_not_implemented(self, report_type):
        return (
            "<div class='alert alert-warning'>"
            "<i class='fa fa-exclamation-circle'></i> "
            "هذا التقرير (%s) غير مفعّل في الوضع المحلي. "
            "يرجى تفعيل Nexus Core للحصول على النسخة الكاملة."
            "</div>" % report_type
        )

    # ── Helpers ──
    def _render_report_header(self, title, wiz):
        company = wiz.company_id.name
        period = "%s → %s" % (wiz.date_from, wiz.date_to)
        return (
            "<div class='nexus-report-header mb-3'>"
            "<h3 class='mb-1'>%s</h3>"
            "<div class='text-muted'>%s</div>"
            "<div class='text-muted small'>الفترة: %s</div>"
            "<hr/></div>"
        ) % (self._x(title), self._x(company), self._x(period))

    def _render_report_footer(self, wiz):
        return (
            "<div class='nexus-report-footer mt-4 text-muted small text-end'>"
            "تم التوليد بواسطة Nexus Engine — "
            "التاريخ: %s</div>"
        ) % fields.Datetime.now()

    def _money(self, value):
        try:
            return "%.2f" % float(value or 0.0)
        except (TypeError, ValueError):
            return "0.00"

    def _x(self, text):
        """HTML-escape helper."""
        if text is None:
            return ""
        import html
        return html.escape(str(text))
