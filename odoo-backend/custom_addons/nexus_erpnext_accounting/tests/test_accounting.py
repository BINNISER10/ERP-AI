"""Core double-entry tests for the ERPNext-style accounting model.

Covers: account/cost-center/fiscal-year setup, a balanced journal entry
posting to GL entries, unbalanced-entry rejection, cancellation removing
GL entries, party account resolution, and budget variance computation.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestNexusErpnextAccounting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Company = cls.env["res.company"]
        cls.AccountType = cls.env["nexus.account.type"]
        cls.Account = cls.env["nexus.account"]
        cls.CostCenter = cls.env["nexus.cost.center"]
        cls.FiscalYear = cls.env["nexus.fiscal.year"]
        cls.PartyAccount = cls.env["nexus.party.account"]
        cls.JournalEntry = cls.env["nexus.journal.entry"]
        cls.GlEntry = cls.env["nexus.gl.entry"]
        cls.Budget = cls.env["nexus.budget"]
        cls.Partner = cls.env["res.partner"]

        cls.company = cls.Company.create({"name": "ERPNext Test Co"})
        cls.cash_type = cls.AccountType.search([("name", "=", "Cash")], limit=1)
        cls.receivable_type = cls.AccountType.search([("name", "=", "Receivable")], limit=1)
        cls.income_type = cls.AccountType.search([("name", "=", "Income")], limit=1)
        cls.expense_type = cls.AccountType.search([("name", "=", "Expense")], limit=1)

        cls.cash_account = cls.Account.create(
            {
                "name": "Cash",
                "account_type": cls.cash_type.id,
                "company_id": cls.company.id,
            }
        )
        cls.receivable_account = cls.Account.create(
            {
                "name": "Debtors",
                "account_type": cls.receivable_type.id,
                "company_id": cls.company.id,
            }
        )
        cls.income_account = cls.Account.create(
            {
                "name": "Sales",
                "account_type": cls.income_type.id,
                "company_id": cls.company.id,
            }
        )
        cls.expense_account = cls.Account.create(
            {
                "name": "Office Expenses",
                "account_type": cls.expense_type.id,
                "company_id": cls.company.id,
            }
        )
        cls.cost_center = cls.CostCenter.create(
            {"cost_center_name": "Head Office", "company_id": cls.company.id}
        )

        cls.fiscal = cls.FiscalYear.create(
            {
                "company_id": cls.company.id,
                "year_start_date": "2026-01-01",
                "year_end_date": "2026-12-31",
            }
        )

        cls.partner = cls.Partner.create({"name": "ERPNext Customer", "is_company": True})
        cls.PartyAccount.create(
            {
                "party_type": "customer",
                "party_id": cls.partner.id,
                "account_type": "receivable",
                "account_id": cls.receivable_account.id,
                "company_id": cls.company.id,
            }
        )

    def _je(self, lines, **kwargs):
        vals = {
            "posting_date": "2026-06-15",
            "company_id": self.company.id,
            "line_ids": [(0, 0, line) for line in lines],
        }
        vals.update(kwargs)
        return self.JournalEntry.create(vals)

    def test_balanced_posting_creates_gl_entries(self):
        je = self._je(
            [
                {"account_id": self.cash_account.id, "debit": 1000.0},
                {"account_id": self.income_account.id, "credit": 1000.0},
            ]
        )
        self.assertAlmostEqual(je.difference, 0.0, places=4)
        je.action_submit()
        self.assertEqual(je.state, "submitted")
        gls = je.gl_entry_ids
        self.assertEqual(len(gls), 2)
        self.assertEqual(
            sum(gls.mapped("debit")) - sum(gls.mapped("credit")), 0.0
        )
        self.assertEqual(gls[0].fiscal_year_id, self.fiscal)
        # Against account should reference the other side
        for gl in gls:
            self.assertTrue(gl.against_account)

    def test_unbalanced_entry_rejected(self):
        je = self._je(
            [
                {"account_id": self.cash_account.id, "debit": 1000.0},
                {"account_id": self.income_account.id, "credit": 999.0},
            ]
        )
        with self.assertRaises(UserError):
            je.action_submit()
        self.assertEqual(je.state, "draft")

    def test_cancel_removes_gl_entries(self):
        je = self._je(
            [
                {"account_id": self.cash_account.id, "debit": 500.0},
                {"account_id": self.income_account.id, "credit": 500.0},
            ]
        )
        je.action_submit()
        gl_ids = je.gl_entry_ids.ids
        self.assertTrue(gl_ids)
        je.action_cancel()
        self.assertEqual(je.state, "cancelled")
        self.assertFalse(self.GlEntry.browse(gl_ids).exists())

    def test_party_account_resolution(self):
        account = self.PartyAccount.resolve_account(
            self.partner.id, "customer", self.company.id
        )
        self.assertEqual(account, self.receivable_account)

    def test_budget_variance(self):
        budget = self.Budget.create(
            {
                "name": "Office Budget",
                "budget_against": "cost_center",
                "cost_center_id": self.cost_center.id,
                "fiscal_year_id": self.fiscal.id,
                "company_id": self.company.id,
                "account_ids": [
                    (0, 0, {"account_id": self.expense_account.id, "budget_amount": 5000.0})
                ],
            }
        )
        self.assertAlmostEqual(budget.total_budget, 5000.0)
        self.assertEqual(budget.state, "draft")
        budget.action_activate()
        self.assertEqual(budget.state, "active")

        # Post an expense of 1200 against the cost center
        je = self._je(
            [
                {
                    "account_id": self.expense_account.id,
                    "debit": 1200.0,
                    "cost_center_id": self.cost_center.id,
                },
                {"account_id": self.cash_account.id, "credit": 1200.0},
            ]
        )
        je.action_submit()
        self.assertAlmostEqual(budget.total_actual, 1200.0)
        self.assertAlmostEqual(budget.total_variance, 3800.0)

    def test_reversal_creates_mirror(self):
        je = self._je(
            [
                {"account_id": self.cash_account.id, "debit": 250.0},
                {"account_id": self.income_account.id, "credit": 250.0},
            ]
        )
        je.action_submit()
        action = je.action_reverse()
        reverse = self.JournalEntry.browse(action["res_id"])
        self.assertEqual(reverse.reversal_of_id, je)
        self.assertEqual(reverse.state, "draft")
        self.assertEqual(sum(reverse.line_ids.mapped("debit")), 250.0)
        self.assertEqual(sum(reverse.line_ids.mapped("credit")), 250.0)
