# -*- coding: utf-8 -*-
"""Post-install setup for the Nexus Saudi chart-of-accounts extension.

Odoo 17+ removed the ``account.account.template`` / ``account.tax.template``
models in favor of a Python/dict-based chart template loader, and Odoo 18
further changed ``account.account`` to a company-shared model
(``company_ids`` many2many instead of ``company_id``). Rather than hooking
into the low-level chart template loader (which only runs once, when a
company's Chart of Accounts is first installed, and is tightly coupled to
``l10n_sa``/``l10n_us``), this module creates its extra accounts and VAT/tax
records directly as real ``account.account`` / ``account.tax`` records for
every existing company, via this post-install hook.
"""

import logging

from odoo import Command, SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# (code, name, account_type, reconcile)
_ACCOUNTS = [
    ("1000", "الأصول / Assets", "asset_non_current", False),
    ("2000", "الخصوم / Liabilities", "liability_non_current", False),
    ("3000", "حقوق الملكية / Equity", "equity", False),
    ("4000", "الإيرادات / Revenue", "income", False),
    ("5000", "المصروفات / Expenses", "expense", False),
    ("1100", "النقدية / Cash on Hand", "asset_cash", False),
    ("1110", "البنوك / Banks", "asset_bank", True),
    ("1200", "ذمم العملاء / Accounts Receivable", "asset_receivable", True),
    ("1300", "المخزون / Inventory", "asset_current", False),
    ("1400", "المصروفات المقدمة / Prepayments", "asset_current", False),
    ("1500", "ضريبة مدخلات / VAT Input", "asset_current", False),
    ("1600", "الأصول الثابتة / Fixed Assets", "asset_fixed", False),
    ("1650", "مجمع الإهلاك / Accumulated Depreciation", "asset_fixed", False),
    ("2100", "ذمم الموردين / Accounts Payable", "liability_payable", True),
    ("2200", "ضريبة مخرجات / VAT Output", "liability_current", False),
    ("2300", "مصروفات مستحقة / Accrued Expenses", "liability_current", False),
    ("2400", "التأمينات الاجتماعية المستحقة / GOSI Payable", "liability_current", False),
    ("2500", "قروض طويلة الأجل / Long-term Loans", "liability_non_current", False),
    ("3100", "رأس المال / Share Capital", "equity", False),
    ("3200", "أرباح محتجزة / Retained Earnings", "equity", False),
    ("3300", "أرباح السنة الحالية / Current Year Earnings", "equity_unaffected", False),
    ("4100", "مبيعات / Sales", "income", False),
    ("4200", "إيرادات خدمات / Service Revenue", "income", False),
    ("4900", "إيرادات أخرى / Other Income", "income_other", False),
    ("5100", "تكلفة المبيعات / Cost of Goods Sold", "expense_direct_cost", False),
    ("5200", "رواتب وأجور / Salaries & Wages", "expense", False),
    ("5300", "إيجار / Rent", "expense", False),
    ("5400", "كهرباء وماء / Utilities", "expense", False),
    ("5500", "مصاريف الإهلاك / Depreciation Expense", "expense_depreciation", False),
    ("5900", "مصاريف إدارية وعمومية / Admin Expenses", "expense", False),
]

# (code, name, amount, type_tax_use, vat_account_code, zatca_category)
# vat_account_code is None for zero-rated/exempt taxes (no tax amount to book).
# zatca_category matches l10n_sa's ZATCA tax category codes (S/Z/E) when that
# field is available (i.e. l10n_sa is installed on the company).
_TAXES = [
    ("VAT-S-15", "ضريبة القيمة المضافة 15% / VAT 15% (Sales)", 15.0, "sale", "2200", "S"),
    ("VAT-P-15", "ضريبة القيمة المضافة 15% / VAT 15% (Purchases)", 15.0, "purchase", "1500", "S"),
    ("VAT-Z", "ضريبة صفر / Zero-Rated", 0.0, "sale", None, "Z"),
    ("VAT-E", "معفى / Exempt", 0.0, "sale", None, "E"),
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


def _get_or_create_tax(env, company, code, name, amount, type_tax_use, vat_account, zatca_category):
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
    if zatca_category and "l10n_sa_tax_category" in Tax._fields:
        vals["l10n_sa_tax_category"] = zatca_category
    if vat_account:
        repartition = [
            Command.create({"repartition_type": "base", "factor_percent": 100.0}),
            Command.create({
                "repartition_type": "tax",
                "factor_percent": 100.0,
                "account_id": vat_account.id,
            }),
        ]
        vals["invoice_repartition_line_ids"] = repartition
        vals["refund_repartition_line_ids"] = repartition
    return Tax.create(vals)


def post_init_hook(cr, registry=None):
    """Create the Saudi accounts/taxes for every existing company.

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
                    "Nexus Saudi: failed to create account %s for company %s",
                    code, company.display_name,
                )

        for code, name, amount, type_tax_use, vat_code, zatca_category in _TAXES:
            vat_account = accounts_by_code.get(vat_code) if vat_code else None
            try:
                _get_or_create_tax(
                    env, company, code, name, amount, type_tax_use,
                    vat_account, zatca_category,
                )
            except Exception:
                _logger.exception(
                    "Nexus Saudi: failed to create tax %s for company %s",
                    code, company.display_name,
                )
