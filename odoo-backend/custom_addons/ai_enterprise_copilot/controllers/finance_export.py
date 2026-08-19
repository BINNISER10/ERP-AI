# -*- coding: utf-8 -*-
"""Nexus Finance Export Controllers — وحدات تحكم التصدير.

Provides HTTP endpoints for:
    * ``/nexus/finance/export_xlsx`` — streams an XLSX file for a
      ``nexus.finance.report`` wizard.
    * ``/nexus/finance/chart_data`` — returns chart-ready JSON for
      the dashboard widgets.

Both endpoints require the user to be authenticated.
"""

import json
import logging

from odoo import http
from odoo.http import content_disposition, request

_logger = logging.getLogger(__name__)


class NexusFinanceExportController(http.Controller):
    """HTTP controllers for finance report exports."""

    # ═══════════════════════════════════════════════════════════════════
    # XLSX Export
    # ═══════════════════════════════════════════════════════════════════
    @http.route(
        "/nexus/finance/export_xlsx",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def export_xlsx(self, wizard_id=None, **kwargs):
        if not wizard_id:
            return request.not_found()
        try:
            wizard = request.env["nexus.finance.report"].browse(int(wizard_id))
        except (ValueError, TypeError):
            return request.not_found()
        if not wizard.exists():
            return request.not_found()
        # IDOR guard: a wizard is a private, per-user report request. Only
        # its creator (or a Nexus manager) may download its export.
        if (
            wizard.create_uid.id != request.env.uid
            and not request.env.user.has_group("nexus_base_security.group_nexus_manager")
        ):
            return request.not_found()

        exporter = request.env["nexus.finance.excel.export"]
        try:
            filename, content, mime = exporter.generate(wizard)
        except Exception as exc:
            _logger.exception("XLSX export failed for wizard %s", wizard_id)
            return request.make_response(
                ("Excel export failed: %s" % exc).encode("utf-8"),
                headers=[("Content-Type", "text/plain; charset=utf-8")],
            )

        return request.make_response(
            content,
            headers=[
                ("Content-Type", mime),
                ("Content-Length", str(len(content))),
                ("Content-Disposition", content_disposition(filename)),
                ("Cache-Control", "no-store"),
            ],
        )

    # ═══════════════════════════════════════════════════════════════════
    # Chart Data (JSON)
    # �══════════════════════════════════════════════════════════════════
    @http.route(
        "/nexus/finance/chart_data",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def chart_data(self, chart_type, **kwargs):
        """Return JSON for dashboard charts.

        Supported chart types:
            * ``revenue_expense`` — last 6 months revenue vs expense
            * ``aging_receivable`` — receivable bucket totals
            * ``aging_payable`` — payable bucket totals
            * ``cash_flow`` — last 30 days cash position
            * ``top_customers`` — top 10 customers by YTD revenue
            * ``kpi_summary`` — period totals + deltas
        """
        try:
            payload = self._build_chart(chart_type)
        except Exception as exc:
            _logger.exception("Chart data build failed")
            return request.make_response(
                json.dumps({"error": str(exc)}),
                headers=[("Content-Type", "application/json")],
            )

        body = json.dumps(payload, default=str)
        return request.make_response(
            body,
            headers=[
                ("Content-Type", "application/json"),
                ("Cache-Control", "no-store"),
            ],
        )

    def _build_chart(self, chart_type):
        env = request.env
        company = env.company
        builder = env["nexus.finance.dashboard.chart"]

        if chart_type == "revenue_expense":
            return builder.revenue_vs_expense(company)
        if chart_type == "aging_receivable":
            return builder.aging_buckets(company, "asset_receivable")
        if chart_type == "aging_payable":
            return builder.aging_buckets(company, "liability_payable")
        if chart_type == "cash_flow":
            return builder.cash_position(company)
        if chart_type == "top_customers":
            return builder.top_customers(company)
        if chart_type == "kpi_summary":
            return builder.kpi_summary(company)

        return {"error": "unknown chart_type: %s" % chart_type}
