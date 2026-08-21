# -*- coding: utf-8 -*-
"""Nexus Finance Reports Wizard — معالج التقارير المالية الموحدة.

A unified wizard that generates all financial reports. Under the hood,
each report type fetches its data from the Nexus Core (ERPNext) API
and renders the result in Odoo's UI with Nexus branding. End users
never see "ERPNext" — they see "Nexus Engine".

Supports:
    - Balance Sheet (الميزانية العمومية)
    - Profit & Loss (قائمة الدخل)
    - Cash Flow (التدفقات النقدية)
    - Trial Balance (ميزان المراجعة)
    - General Ledger (دفتر الأستاذ)
    - Receivable Aging (أعمار الذمم المدينة)
    - Payable Aging (أعمار الذمم الدائنة)
    - Budget Variance (انحراف الميزانية)
    - Cost Center Report (تقرير مراكز التكلفة)
"""

import json
import logging
from datetime import date, timedelta

import markupsafe
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


REPORT_TYPES = [
    ("balance_sheet", "الميزانية العمومية / Balance Sheet"),
    ("profit_loss", "قائمة الدخل / Profit & Loss"),
    ("cash_flow", "التدفقات النقدية / Cash Flow"),
    ("trial_balance", "ميزان المراجعة / Trial Balance"),
    ("general_ledger", "دفتر الأستاذ العام / General Ledger"),
    ("aging_receivable", "أعمار الذمم المدينة / Receivable Aging"),
    ("aging_payable", "أعمار الذمم الدائنة / Payable Aging"),
    ("budget_variance", "انحراف الميزانية / Budget Variance"),
    ("cost_center", "تقرير مراكز التكلفة / Cost Center Report"),
]

# ERPNext doctype mapping for each report type
_ERPNEXT_REPORT_MAP = {
    "balance_sheet": "Balance Sheet",
    "profit_loss": "Profit and Loss Statement",
    "cash_flow": "Cash Flow Statement",
    "trial_balance": "Trial Balance",
    "general_ledger": "General Ledger",
    "aging_receivable": "Accounts Receivable Summary",
    "aging_payable": "Accounts Payable Summary",
    "budget_variance": "Budget Variance Report",
    "cost_center": "Cost Center Report",
}


class NexusFinanceReport(models.TransientModel):
    """Nexus unified financial report wizard.

    The wizard collects the report parameters from the user (date range,
    company, cost center, etc.) and delegates execution to the
    ``nexus.erpnext.bridge`` service, which talks to the Nexus Core
    (ERPNext) backend and returns the rendered report data.
    """

    _name = "nexus.finance.report"
    _description = "Nexus Financial Report Wizard"

    # ── Report parameters ──
    report_type = fields.Selection(
        selection=REPORT_TYPES,
        string="نوع التقرير / Report Type",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="المنشأة / Company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string="من تاريخ / From Date",
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string="إلى تاريخ / To Date",
        required=True,
        default=fields.Date.today,
    )
    fiscal_year_id = fields.Many2one(
        "account.fiscal.year",
        string="السنة المالية / Fiscal Year",
    )
    cost_center_id = fields.Many2one(
        "account.analytic.account",
        string="مركز التكلفة / Cost Center",
    )
    account_id = fields.Many2one(
        "account.account",
        string="الحساب / Account",
        help="Filter to a single account (only for General Ledger).",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="العميل / المورد / Partner",
        help="Filter to a single partner (only for Aging / GL).",
    )

    # ── Output ──
    state = fields.Selection(
        [
            ("draft", "إعداد / Draft"),
            ("generated", "تم الإنشاء / Generated"),
            ("error", "خطأ / Error"),
        ],
        default="draft",
        required=True,
    )
    report_html = fields.Html(
        string="نتيجة التقرير / Report Output",
        readonly=True,
        sanitize=True,
        sanitize_tags=True,
        sanitize_attributes=True,
    )
    error_message = fields.Text(
        string="رسالة الخطأ / Error Message",
        readonly=True,
    )
    generation_time_ms = fields.Integer(
        string="زمن التنفيذ (ms) / Generation Time",
        readonly=True,
    )

    # ── Validation ──
    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise ValidationError(
                    _("تاريخ البداية يجب أن يكون قبل تاريخ النهاية.")
                )

    # ── Actions ──
    def action_generate_report(self):
        """Generate the selected report by calling the Nexus Core bridge.

        Returns a client action that re-opens this wizard in
        ``generated`` or ``error`` state with the HTML payload embedded.
        """
        self.ensure_one()
        start = fields.Datetime.now()

        # Try cache first
        cache = self.env["nexus.finance.report.cache"]
        cached = cache.get(self)
        if cached:
            self.report_html = cached
            self.state = "generated"
            self.error_message = False
            delta = fields.Datetime.now() - start
            self.generation_time_ms = int(delta.total_seconds() * 1000)
            self._set_cache_hit_indicator()
            return self._reopen_with_result()

        try:
            html_payload = self._delegate_to_bridge()
            self.report_html = html_payload
            self.state = "generated"
            self.error_message = False
            cache.set(self, html_payload)
        except Exception as exc:
            _logger.exception("Nexus finance report failed")
            self.state = "error"
            self.error_message = str(exc)
            self.report_html = self._render_error_card(str(exc))
        finally:
            delta = fields.Datetime.now() - start
            self.generation_time_ms = int(delta.total_seconds() * 1000)

        return self._reopen_with_result()

    def _set_cache_hit_indicator(self):
        """Mark the report as served from cache (no extra field needed)."""
        # We embed the indicator in the HTML so the user sees it.
        if self.report_html and "data-cache-hit" not in self.report_html:
            indicator = (
                '<div class="alert alert-info py-1 px-2 small mb-2" '
                'data-cache-hit="true">'
                '<i class="fa fa-bolt"></i> '
                'تم العرض من الذاكرة المؤقتة — مولّد فوراً.'
                '</div>'
            )
            self.report_html = indicator + self.report_html

    def action_reset(self):
        """Reset the wizard back to draft state."""
        self.ensure_one()
        self.write({
            "state": "draft",
            "report_html": False,
            "error_message": False,
            "generation_time_ms": 0,
        })
        return self._reopen_with_result()

    def action_export_pdf(self):
        """Export the current report as PDF via the standard Odoo report engine."""
        self.ensure_one()
        if self.state != "generated":
            raise UserError(_("يجب توليد التقرير أولاً قبل التصدير."))
        return self.env.ref(
            "ai_enterprise_copilot.action_report_nexus_finance"
        ).report_action(self)

    def action_export_excel(self):
        """Export the current report as XLSX (basic flat export)."""
        self.ensure_one()
        if self.state != "generated":
            raise UserError(_("يجب توليد التقرير أولاً قبل التصدير."))
        return {
            "type": "ir.actions.act_url",
            "url": "/nexus/finance/export_xlsx?wizard_id=%d" % self.id,
            "target": "self",
        }

    # ── Internals ──
    def _delegate_to_bridge(self):
        """Call the Nexus ERPNext bridge and return rendered HTML.

        Falls back to a local rendering pipeline if the bridge is
        unreachable or unconfigured (so the wizard stays functional in
        single-node deployments).
        """
        bridge = self.env["nexus.erpnext.bridge"]
        if bridge.is_configured():
            try:
                return bridge.run_finance_report(self)
            except Exception as exc:
                _logger.warning(
                    "Nexus bridge failed (%s); falling back to local render.",
                    exc,
                )
        return self._render_local_fallback()

    def _render_local_fallback(self):
        """Render the report from Odoo's native ``account.*`` models.

        This is the safety net used when no ERPNext backend is
        available. Reports computed locally will be slightly less rich
        than the ERPNext versions, but they cover the 80% case.
        """
        renderer = self.env["nexus.finance.report.renderer"]
        return renderer.render(self)

    def _render_error_card(self, message):
        # Escape the message: it may echo back untrusted content (e.g. an
        # external API error body), and report_html is a sanitize=False
        # field rendered raw both in the form view and the PDF template.
        safe_message = markupsafe.escape(message or "")
        return (
            "<div class='alert alert-danger' role='alert'>"
            "<h4><i class='fa fa-exclamation-triangle'></i> "
            "تعذر توليد التقرير</h4>"
            "<p>%s</p>"
            "<p class='text-muted small'>"
            "يرجى التحقق من اتصال Nexus Core ومراجعة سجلات النظام."
            "</p></div>"
        ) % safe_message

    def _reopen_with_result(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }
