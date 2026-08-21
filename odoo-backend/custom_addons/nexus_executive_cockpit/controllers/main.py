"""HTTP endpoints for the Executive Cockpit dashboard widgets + layout."""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CockpitController(http.Controller):

    @http.route("/nexus/cockpit", type="http", auth="user", methods=["GET"], csrf=False)
    def cockpit_page(self, **kwargs):
        return request.render("nexus_executive_cockpit.cockpit_dashboard_template", {})

    @http.route("/nexus/cockpit/data", type="http", auth="user", methods=["GET"], csrf=False)
    def cockpit_data(self, widget, company_id=None, **kwargs):
        """Return JSON for one cockpit widget.

        Supported widgets: liquidity, daily_sales, gross_margin,
        branch_performance, cash_flow_forecast, anomaly_alerts.
        """
        env = request.env
        company = env["res.company"].browse(int(company_id)) if company_id else env.company
        builder = env["nexus.cockpit.kpi"]

        try:
            payload = self._build_widget(builder, widget, company, env)
        except Exception as exc:
            _logger.exception("Cockpit widget build failed: %s", widget)
            payload = {"error": str(exc)}

        return request.make_response(
            json.dumps(payload, default=str),
            headers=[("Content-Type", "application/json"), ("Cache-Control", "no-store")],
        )

    def _build_widget(self, builder, widget, company, env):
        if widget == "liquidity":
            return builder.liquidity_summary(company)
        if widget == "daily_sales":
            return builder.daily_sales(company)
        if widget == "gross_margin":
            return builder.gross_margin(company)
        if widget == "branch_performance":
            companies = env["res.company"].search([])
            return {"branches": builder.branch_performance(companies)}
        if widget == "cash_flow_forecast":
            return builder.cash_flow_forecast_90d(company)
        if widget == "anomaly_alerts":
            return {"alerts": builder.anomaly_alerts(company)}
        if widget == "revenue_trend":
            return builder.revenue_trend_6m(company)
        if widget == "ar_aging":
            return builder.ar_aging_summary(company)
        if widget == "top_expenses":
            return builder.top_expenses(company)
        if widget == "customer_concentration":
            return builder.customer_concentration(company)
        return {"error": "Unknown widget: %s" % widget}

    # ── Customizable layout ─────────────────────────────────────────
    @http.route("/nexus/cockpit/layout", type="http", auth="user", methods=["GET"], csrf=False)
    def get_layout(self, **kwargs):
        layout = request.env["nexus.cockpit.layout"].get_for_user()
        return request.make_response(
            json.dumps(layout.get_layout()),
            headers=[("Content-Type", "application/json")],
        )

    @http.route("/nexus/cockpit/layout", type="json", auth="user", methods=["POST"], csrf=False)
    def save_layout(self, **kwargs):
        payload = request.jsonrequest or {}
        layout = request.env["nexus.cockpit.layout"].get_for_user()
        return layout.set_layout(
            order=payload.get("order"),
            hidden=payload.get("hidden"),
        )
