# -*- coding: utf-8 -*-
"""Post-install setup for the Nexus US chart-of-accounts extension.

Odoo 17+ removed the ``account.account.template`` / ``account.tax.template``
models in favor of a Python/dict-based chart template loader, and Odoo 18
further changed ``account.account`` to a company-shared model
(``company_ids`` many2many instead of ``company_id``). Rather than hooking
into the low-level chart template loader (which only runs once, when a
company's Chart of Accounts is first installed, and is tightly coupled to
``l10n_us``), this module creates its extra accounts and tax records
directly as real ``account.account`` / ``account.tax`` records for every
existing company, via this post-install hook.
"""

import logging

from odoo import Command, SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# (code, name, account_type, reconcile)
_ACCOUNTS = [
    ("1000", "Assets / الأصول", "asset_non_current", False),
    ("2000", "Liabilities / الخصوم", "liability_non_current", False),
    ("3000", "Equity / حقوق الملكية", "equity", False),
    ("4000", "Revenue / الإيرادات", "income", False),
    ("5000", "Expenses / المصروفات", "expense", False),
    ("1100", "Cash / النقدية", "asset_cash", False),
    ("1110", "Checking Account / حساب جاري", "asset_bank", True),
    ("1120", "Savings / حساب توفير", "asset_bank", True),
    ("1200", "Accounts Receivable / ذمم العملاء", "asset_receivable", True),
    ("1300", "Inventory / المخزون", "asset_current", False),
    ("1400", "Prepaid Expenses / مصروفات مقدمة", "asset_current", False),
    ("1500", "Fixed Assets / أصول ثابتة", "asset_fixed", False),
    ("1550", "Accumulated Depreciation / مجمع الإهلاك", "asset_fixed", False),
    ("2100", "Accounts Payable / ذمم الموردين", "liability_payable", True),
    ("2200", "Sales Tax Payable / ضريبة المبيعات المستحقة", "liability_current", False),
    ("2300", "Payroll Liabilities / التزامات الرواتب", "liability_current", False),
    ("2400", "1099 Payable / مستحقات 1099", "liability_current", False),
    ("2500", "Long-term Loans / قروض طويلة الأجل", "liability_non_current", False),
    ("3100", "Owner's Equity / رأس المال", "equity", False),
    ("3200", "Retained Earnings / أرباح محتجزة", "equity", False),
    ("3300", "Owner's Draws / مسحوبات المالك", "equity", False),
    ("4100", "Sales / المبيعات", "income", False),
    ("4200", "Service Revenue / إيرادات الخدمات", "income", False),
    ("4900", "Other Income / إيرادات أخرى", "income_other", False),
    ("5100", "Cost of Goods Sold / تكلفة المبيعات", "expense_direct_cost", False),
    ("5200", "Payroll / الرواتب", "expense", False),
    ("5300", "Rent Expense / إيجار", "expense", False),
    ("5400", "Utilities / خدمات", "expense", False),
    ("5500", "Depreciation Expense / مصاريف الإهلاك", "expense_depreciation", False),
    ("5900", "General & Administrative / مصاريف إدارية", "expense", False),
    ("6000", "Interest Expense / مصاريف الفوائد", "expense", False),
]

# (code, name, amount, type_tax_use, tax_account_code)
# tax_account_code is None for the generic sales tax placeholder / withholding
# taxes that don't need an explicit repartition override.
_TAXES = [
    ("US-ST", "Sales Tax / ضريبة المبيعات", 0.0, "sale", "2200"),
    ("US-FW", "Federal Tax Withholding", 15.0, "purchase", None),
    ("US-SW", "State Tax Withholding", 5.0, "purchase", None),
]


def _get_or_create_account(env, company, code, name, account_type, reconcile):
    Account = env["account.account"].with_company(company)
    existing = Account.search([("code", "=", code)], limit=1)
    if existing:
        return existing
    return Account.create({
        "code": code,
        "name": name,
        "account_type": account_type,
        "reconcile": reconcile,
        "company_ids": [Command.set([company.id])],
    })


def _get_or_create_tax(env, company, code, name, amount, type_tax_use, tax_account):
    Tax = env["account.tax"]
    existing = Tax.search([
        ("company_id", "=", company.id),
        ("description", "=", code),
    ], limit=1)
    if existing:
        return existing

    vals = {
        "name": name,
        "description": code,
        "amount": amount,
        "amount_type": "percent",
        "type_tax_use": type_tax_use,
        "company_id": company.id,
    }
    if tax_account:
        repartition = [
            Command.create({"repartition_type": "base", "factor_percent": 100.0}),
            Command.create({
                "repartition_type": "tax",
                "factor_percent": 100.0,
                "account_id": tax_account.id,
            }),
        ]
        vals["invoice_repartition_line_ids"] = repartition
        vals["refund_repartition_line_ids"] = repartition
    return Tax.create(vals)


def post_init_hook(cr, registry=None):
    """Create the US accounts/taxes for every existing company.

    Signature kept compatible with both the legacy ``(cr, registry)`` and
    the Odoo 17+ ``(env)`` post_init_hook calling conventions.
    """
    env = cr if hasattr(cr, "cr") else api.Environment(cr, SUPERUSER_ID, {})

    for company in env["res.company"].search([]):
        accounts_by_code = {}
        for code, name, account_type, reconcile in _ACCOUNTS:
            try:
                accounts_by_code[code] = _get_or_create_account(
                    env, company, code, name, account_type, reconcile
                )
            except Exception:
                _logger.exception(
                    "Nexus US: failed to create account %s for company %s",
                    code, company.display_name,
                )

        for code, name, amount, type_tax_use, tax_code in _TAXES:
            tax_account = accounts_by_code.get(tax_code) if tax_code else None
            try:
                _get_or_create_tax(env, company, code, name, amount, type_tax_use, tax_account)
            except Exception:
                _logger.exception(
                    "Nexus US: failed to create tax %s for company %s",
                    code, company.display_name,
                )
