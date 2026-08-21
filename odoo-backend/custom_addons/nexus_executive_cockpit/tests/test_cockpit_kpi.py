"""Tests for the Executive Cockpit KPI builder.

Uses the standard demo chart of accounts (searched defensively, per
this repo's existing convention in nexus_advanced_accounting/tests)
rather than building a full CoA from scratch.
"""
from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCockpitKPI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.builder = cls.env["nexus.cockpit.kpi"]
        cls.partner = cls.env["res.partner"].create({"name": "Cockpit Test Customer"})

        cls.income_account = cls.env["account.account"].search([
            ("account_type", "in", ("income", "income_other")),
            ("company_id", "=", cls.company.id),
        ], limit=1) or cls.env["account.account"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.expense_account = cls.env["account.account"].search([
            ("account_type", "in", ("expense", "expense_direct_cost")),
            ("company_id", "=", cls.company.id),
        ], limit=1) or cls.income_account

    def _post_invoice(self, move_type, amount, invoice_date=None):
        move = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "invoice_date": invoice_date or fields.Date.today(),
            "invoice_line_ids": [(0, 0, {
                "name": "Test line",
                "quantity": 1,
                "price_unit": amount,
                "account_id": self.income_account.id,
            })],
        })
        move.action_post()
        return move

    def test_daily_sales_sums_todays_posted_invoices(self):
        self._post_invoice("out_invoice", 1000.0)
        self._post_invoice("out_invoice", 500.0)
        result = self.builder.daily_sales(self.company)
        self.assertGreaterEqual(result["value"], 1500.0)
        self.assertGreaterEqual(result["invoice_count"], 2)

    def test_daily_sales_excludes_other_days(self):
        yesterday = fields.Date.today() - fields.timedelta(days=1)
        self._post_invoice("out_invoice", 999.0, invoice_date=yesterday)
        result = self.builder.daily_sales(self.company)
        # Only today's invoices should count; the 999 from yesterday must
        # not silently inflate today's total.
        self.assertNotIn(999.0, [result["value"]])

    def test_liquidity_summary_returns_numeric_value(self):
        result = self.builder.liquidity_summary(self.company)
        self.assertIn("value", result)
        self.assertIsInstance(result["value"], float)

    def test_gross_margin_returns_percentage_and_breakdown(self):
        self._post_invoice("out_invoice", 2000.0)
        result = self.builder.gross_margin(self.company)
        self.assertIn("value", result)
        self.assertIn("revenue", result)
        self.assertIn("cogs", result)

    def test_branch_performance_returns_one_row_per_company(self):
        companies = self.env["res.company"].search([], limit=3)
        result = self.builder.branch_performance(companies)
        self.assertEqual(len(result), len(companies))
        for row in result:
            self.assertIn("daily_sales", row)
            self.assertIn("name", row)

    def test_cash_flow_forecast_returns_13_weekly_buckets(self):
        result = self.builder.cash_flow_forecast_90d(self.company)
        # 90 days / 7-day buckets ≈ 13 buckets.
        self.assertGreaterEqual(len(result["buckets"]), 12)
        self.assertLessEqual(len(result["buckets"]), 14)
        for bucket in result["buckets"]:
            self.assertIn("projected_balance", bucket)

    def test_anomaly_alerts_returns_list(self):
        result = self.builder.anomaly_alerts(self.company)
        self.assertIsInstance(result, list)

    def test_revenue_trend_returns_6_months(self):
        self._post_invoice("out_invoice", 3000.0)
        result = self.builder.revenue_trend_6m(self.company)
        self.assertEqual(len(result["months"]), 6)
        for m in result["months"]:
            self.assertIn("month", m)
            self.assertIn("revenue", m)
        # Current month should include the 3000 we just posted.
        self.assertGreaterEqual(result["months"][-1]["revenue"], 3000.0)

    def test_ar_aging_returns_bucket_dict(self):
        result = self.builder.ar_aging_summary(self.company)
        self.assertIn("buckets", result)
        for key in ("current", "1_30", "31_60", "61_90", "90_plus"):
            self.assertIn(key, result["buckets"])
        self.assertIn("total_overdue", result)

    def test_top_expenses_returns_sorted_list(self):
        result = self.builder.top_expenses(self.company)
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)
        # Items should be sorted descending by amount.
        amounts = [i["amount"] for i in result["items"]]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_customer_concentration_returns_risk_level(self):
        self._post_invoice("out_invoice", 5000.0)
        result = self.builder.customer_concentration(self.company)
        self.assertIn("items", result)
        self.assertIn("top5_share_pct", result)
        self.assertIn("risk_level", result)
        self.assertIn(result["risk_level"], ("low", "medium", "high"))
