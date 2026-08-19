# -*- coding: utf-8 -*-
"""Nexus ↔ ERPNext Bridge — الجسر المالي بين Odoo و ERPNext.

Every financial write in Odoo is mirrored to the Nexus Core
(ERPNext) backend through this bridge. Reports fetch from ERPNext
so the customer sees a single, unified accounting experience.

Configuration is stored in ``nexus.hybrid.config`` (created in the
``odoo_erpnext_hybrid_sync`` module) and respects SSRF-safe
endpoint validation.
"""

import json
import logging
import re
from urllib.parse import urlparse

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# Endpoints on the Nexus Core (ERPNext) side
_ERPNEXT_RESOURCES = {
    "account.account": "/api/resource/Account",
    "account.journal": "/api/resource/Journal",
    "account.tax": "/api/resource/Item Tax Template",
    "account.move": "/api/resource/Sales Invoice",
    "account.payment": "/api/resource/Payment Entry",
    "res.partner": "/api/resource/Customer",
    "product.product": "/api/resource/Item",
    "stock.warehouse": "/api/resource/Warehouse",
    "hr.department": "/api/resource/Cost Center",
}


# IPs / hosts that must never be contacted (SSRF protection)
_BLOCKED_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
}


class NexusERPNextBridge(models.AbstractModel):
    """Thin wrapper around the ERPNext REST API.

    Used by:
        * ``nexus.finance.report`` — to fetch report data
        * ``account.move`` override (in nexus_advanced_accounting) — to push invoices
        * ``account.payment`` override — to push payments
    """

    _name = "nexus.erpnext.bridge"
    _description = "Nexus ↔ ERPNext Bridge"

    # ─────────────────────────────────────────────────────────────────
    # Configuration
    # ─────────────────────────────────────────────────────────────────
    def _get_config(self):
        """Return the active ``nexus.hybrid.config`` record."""
        Config = self.env.get("nexus.hybrid.config")
        if not Config:
            return self.env["ir.config_parameter"].sudo()
        cfg = Config.search([], limit=1, order="id desc")
        return cfg or Config

    def is_configured(self):
        """Whether the bridge has a usable endpoint + auth."""
        cfg = self._get_config()
        if hasattr(cfg, "erpnext_url"):
            url = cfg.erpnext_url
            key = cfg.api_key
            secret = cfg.api_secret
            return bool(url and key and secret)
        # Fallback: check ir.config_parameter
        ICP = self.env["ir.config_parameter"].sudo()
        url = ICP.get_param("nexus_core.url", "")
        key = ICP.get_param("nexus_core.api_key", "")
        secret = ICP.get_param("nexus_core.api_secret", "")
        return bool(url and key and secret)

    def _base_url(self):
        cfg = self._get_config()
        if hasattr(cfg, "erpnext_url"):
            return cfg.erpnext_url.rstrip("/")
        return self.env["ir.config_parameter"].sudo().get_param(
            "nexus_core.url", ""
        ).rstrip("/")

    def _auth_headers(self):
        cfg = self._get_config()
        if hasattr(cfg, "api_key"):
            return {"Authorization": "token %s:%s" % (cfg.api_key, cfg.api_secret)}
        ICP = self.env["ir.config_parameter"].sudo()
        return {
            "Authorization": "token %s:%s" % (
                ICP.get_param("nexus_core.api_key", ""),
                ICP.get_param("nexus_core.api_secret", ""),
            )
        }

    # ─────────────────────────────────────────────────────────────────
    # SSRF guard
    # ─────────────────────────────────────────────────────────────────
    def _is_safe_endpoint(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        if not host or host in _BLOCKED_HOSTS:
            return False
        # Block private IP ranges if reached by IP literal
        if host.startswith(("10.", "192.168.", "172.16.")):
            return False
        return True

    # ─────────────────────────────────────────────────────────────────
    # Generic HTTP wrapper
    # ─────────────────────────────────────────────────────────────────
    def _request(self, method, path, *, params=None, json_body=None, timeout=15):
        url = self._base_url() + path
        if not self._is_safe_endpoint(url):
            raise UserError(_("رابط غير آمن: %s") % url)
        try:
            resp = requests.request(
                method,
                url,
                headers={**self._auth_headers(), "Content-Type": "application/json"},
                params=params,
                json=json_body,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            _logger.error("Nexus bridge call failed: %s", exc)
            raise UserError(_("فشل الاتصال بـ Nexus Core: %s") % exc)

    # ─────────────────────────────────────────────────────────────────
    # Push operations (Odoo → ERPNext)
    # ─────────────────────────────────────────────────────────────────
    def push_account_move(self, move_id):
        """Push a posted ``account.move`` to ERPNext as a Sales/Purchase Invoice."""
        move = self.env["account.move"].browse(move_id)
        if not move.exists() or move.state != "posted":
            return False
        resource = (
            _ERPNEXT_RESOURCES["account.move"]
            if move.move_type in ("out_invoice", "out_refund")
            else "/api/resource/Purchase Invoice"
        )
        payload = self._serialize_move(move)
        try:
            data = self._request("POST", resource, json_body=payload)
            erpnext_name = (data.get("data") or {}).get("name")
            if erpnext_name and hasattr(move, "nexus_erpnext_id"):
                move.write({"nexus_erpnext_id": erpnext_name})
            return True
        except Exception:
            # Enqueue for retry instead of failing the user transaction
            self.env["nexus.sync.queue"].enqueue(
                operation="account.move.push",
                payload=payload,
                endpoint=resource,
                company=move.company_id,
                model_name="account.move",
                res_id=move.id,
            )
            return False

    def _serialize_move(self, move):
        """Convert an Odoo account.move to an ERPNext invoice payload."""
        line_items = []
        for line in move.invoice_line_ids:
            line_items.append({
                "item_code": line.product_id.default_code or line.product_id.name,
                "qty": line.quantity,
                "rate": line.price_unit,
                "amount": line.price_subtotal,
                "income_account": self._get_erpnext_account(line.account_id),
                "cost_center": self._get_erpnext_cost_center(line.analytic_account_id),
            })
        return {
            "doctype": "Sales Invoice" if move.move_type.startswith("out_") else "Purchase Invoice",
            "customer" if move.move_type.startswith("out_") else "supplier":
                self._get_erpnext_partner(move.partner_id),
            "company": self.env.company.name,
            "posting_date": str(move.invoice_date),
            "due_date": str(move.invoice_date_due or move.invoice_date),
            "currency": move.currency_id.name,
            "items": line_items,
            "taxes": [
                {"charge_type": "On Net Total", "rate": t.amount, "description": t.name}
                for t in move.line_ids.mapped("tax_line_id")
            ],
        }

    def _get_erpnext_account(self, account):
        return getattr(account, "nexus_erpnext_id", False) or account.code

    def _get_erpnext_cost_center(self, analytic):
        if not analytic:
            return None
        return getattr(analytic, "nexus_erpnext_id", False) or analytic.name

    def _get_erpnext_partner(self, partner):
        return getattr(partner, "nexus_erpnext_id", False) or partner.name

    # ─────────────────────────────────────────────────────────────────
    # Report fetch (ERPNext → Odoo UI)
    # ─────────────────────────────────────────────────────────────────
    def run_finance_report(self, wizard):
        """Fetch a report payload from ERPNext and return Odoo HTML."""
        from . import nexus_finance_report  # noqa: F401  for doctype map

        doctype = nexus_finance_report._ERPNEXT_REPORT_MAP.get(wizard.report_type)
        if not doctype:
            raise UserError(_("نوع تقرير غير مدعوم: %s") % wizard.report_type)

        params = {
            "company": wizard.company_id.name,
            "from_date": str(wizard.date_from),
            "to_date": str(wizard.date_to),
        }
        if wizard.cost_center_id:
            params["cost_center"] = wizard.cost_center_id.name

        try:
            result = self._request(
                "GET",
                "/api/method/frappe.desk.query_report.run",
                params={"report_name": doctype, "filters": json.dumps(params)},
                timeout=30,
            )
            return self._render_erpnext_payload(wizard, result.get("result"))
        except UserError:
            raise
        except Exception as exc:
            raise UserError(_("فشل توليد التقرير من Nexus Core: %s") % exc)

    def _render_erpnext_payload(self, wizard, result):
        """Render ERPNext report payload as HTML.

        ERPNext returns ``result`` shaped as::

            {"columns": [...], "result": [...rows...]}
        """
        if not result:
            return (
                "<div class='alert alert-info'>لا توجد بيانات للفترة المحددة.</div>"
            )
        columns = result.get("columns") or []
        rows = result.get("result") or []

        renderer = self.env["nexus.finance.report.renderer"]
        head = "".join(
            "<th class='text-end'>%s</th>" % renderer._x(c.get("label", ""))
            for c in columns
        )
        body_rows = []
        for row in rows:
            cells = "".join(
                "<td class='text-end'>%s</td>" % renderer._x(v)
                for v in row
            )
            body_rows.append("<tr>%s</tr>" % cells)
        body = "".join(body_rows)
        return (
            self.env["nexus.finance.report.renderer"]._render_report_header(
                dict(wizard._fields["report_type"].selection).get(
                    wizard.report_type, wizard.report_type
                ),
                wizard,
            )
            + "<table class='table table-sm table-striped'>"
            "<thead><tr>%s</tr></thead>"
            "<tbody>%s</tbody></table>"
            % (head, body)
            + self.env["nexus.finance.report.renderer"]._render_report_footer(wizard)
        )

    # ─────────────────────────────────────────────────────────────────
    # Lightweight helpers used elsewhere
    # ─────────────────────────────────────────────────────────────────
    def ping(self):
        """Return ``True`` if the Nexus Core is reachable and authenticated."""
        try:
            self._request("GET", "/api/method/frappe.auth.get_logged_user", timeout=5)
            return True
        except Exception:
            return False

    @api.model
    def _heartbeat(self):
        """Cron entry point: record Nexus Core availability and latency."""
        ICP = self.env["ir.config_parameter"].sudo()
        start = fields.Datetime.now()
        ok = False
        latency_ms = None
        try:
            self._request("GET", "/api/method/frappe.auth.get_logged_user", timeout=5)
            ok = True
        except Exception:
            ok = False
        latency_ms = int((fields.Datetime.now() - start).total_seconds() * 1000)

        ICP.set_param("nexus_core.last_heartbeat", fields.Datetime.now())
        ICP.set_param("nexus_core.last_heartbeat_ok", ok)
        ICP.set_param("nexus_core.last_heartbeat_latency_ms", latency_ms)

        # Create a low-severity incident if heartbeats fail for 3 consecutive runs
        if not ok:
            Incident = self.env.get("copilot.support.incident")
            if Incident:
                recent = Incident.search_count([
                    ("name", "like", "ERPNext heartbeat"),
                    ("create_date", ">=", fields.Datetime.subtract(fields.Datetime.now(), hours=1)),
                ])
                if recent >= 2:
                    Incident.create({
                        "name": "ERPNext heartbeat - 3rd failure",
                        "severity": "high",
                        "description": "Nexus Core لم يستجيب لـ 3 اختبارات heartbeat متتالية.",
                    })
        return ok
