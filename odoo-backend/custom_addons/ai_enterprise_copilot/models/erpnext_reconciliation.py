# -*- coding: utf-8 -*-
"""Nexus ERPNext Reconciliation Engine — محرك المطابقة والمحاسبة.

Runs nightly (via cron) to compare key totals between Odoo and the
Nexus Core (ERPNext).  If a drift is detected, the record is
re-pushed automatically.  The engine is read-only on the ERPNext
side — it only calls ``frappe.client.get_value`` for totals.

Detection points:
    * Account balances (per account, debit/credit)
    * Open Receivables (per partner)
    * Open Payables (per partner)
    * Period revenue / expense
"""

import json
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class NexusReconciliation(models.Model):
    """Drift-detection record.

    A new record is created each time the cron runs. The
    ``action_reconcile`` method performs the actual comparison and
    re-pushes mismatched records.
    """

    _name = "nexus.erpnext.reconciliation"
    _description = "Nexus ↔ ERPNext Reconciliation Run"
    _order = "run_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(string="Run #", required=True, default="/", readonly=True)
    run_date = fields.Datetime(
        string="Run Date",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("running", "قيد التشغيل"),
            ("ok", "مطابق تماماً"),
            ("drift_found", "انحراف مكتشف"),
            ("error", "خطأ في الاتصال"),
        ],
        required=True,
        default="running",
        readonly=True,
    )
    drift_count = fields.Integer(string="عدد الانحرافات", readonly=True, default=0)
    notes = fields.Text(string="ملاحظات", readonly=True)
    duration_ms = fields.Integer(string="مدة التشغيل (ms)", readonly=True)

    drift_line_ids = fields.One2many(
        "nexus.erpnext.reconciliation.line",
        "reconciliation_id",
        string="تفاصيل الانحراف",
    )

    @api.model
    def _cron_reconcile(self):
        """Entry point for the cron job."""
        rec = self.create({})
        rec.action_reconcile()
        return rec

    def action_reconcile(self):
        self.ensure_one()
        start = fields.Datetime.now()
        bridge = self.env["nexus.erpnext.bridge"]
        if not bridge.is_configured():
            self.write({
                "state": "error",
                "notes": "Nexus Core غير مُهيأ — لا يمكن إجراء المطابقة.",
            })
            return

        try:
            drifts = self._run_checks()
            self.write({
                "drift_count": len(drifts),
                "state": "ok" if not drifts else "drift_found",
                "notes": "\n".join(d["summary"] for d in drifts) or "مطابق تماماً.",
                "duration_ms": int(
                    (fields.Datetime.now() - start).total_seconds() * 1000
                ),
            })
            # Self-healing: re-push drifted records and mark resolved on
            # success. Drifts that fail to resolve or keep repeating across
            # runs are escalated to a support incident instead of retrying
            # forever silently.
            for d in drifts:
                line = d.get("line")
                if not d.get("resync_record_id"):
                    continue
                try:
                    resynced = d["resync_method"](d["resync_record_id"])
                except Exception:
                    _logger.exception(
                        "Nexus reconciliation: resync failed for %s",
                        d["summary"],
                    )
                    resynced = False
                if resynced and line:
                    line.write({
                        "resolved": True,
                        "resolved_at": fields.Datetime.now(),
                    })
                elif not resynced:
                    self._escalate_if_persistent(d)
        except Exception as exc:
            _logger.exception("Reconciliation failed")
            self.write({
                "state": "error",
                "notes": str(exc),
                "duration_ms": int(
                    (fields.Datetime.now() - start).total_seconds() * 1000
                ),
            })

    def _run_checks(self):
        """Compare Odoo totals against ERPNext and return drift records."""
        drifts = []

        # ── 1. Period totals (revenue / expense) ──
        odoo_period = self._odoo_period_totals()
        erp_period = self._erpnext_period_totals()
        for key in ("revenue", "expense"):
            o = odoo_period.get(key, 0.0)
            e = erp_period.get(key, 0.0)
            if abs(o - e) > 0.5:  # tolerance
                drifts.append({
                    "drift_key": "period.%s" % key,
                    "summary": _(
                        "انحراف في %s: Odoo=%.2f مقابل ERPNext=%.2f"
                    ) % (key, o, e),
                    "resync_record_id": None,
                    "resync_method": None,
                })

        # ── 2. Open Receivables per partner ──
        rec_diffs = self._compare_partner_balances("asset_receivable")
        for d in rec_diffs:
            drifts.append({
                "drift_key": "receivable.%s" % d["partner_id"],
                "summary": _(
                    "انحراف في رصيد العميل %s: Odoo=%.2f مقابل ERPNext=%.2f"
                ) % (d["partner"], d["odoo"], d["erpnext"]),
                "resync_record_id": d["partner_id"],
                "resync_method": self.env[
                    "nexus.erpnext.bridge.extensions"
                ].push_partner,
            })

        # ── 3. Open Payables per partner ──
        pay_diffs = self._compare_partner_balances("liability_payable")
        for d in pay_diffs:
            drifts.append({
                "drift_key": "payable.%s" % d["partner_id"],
                "summary": _(
                    "انحراف في رصيد المورد %s: Odoo=%.2f مقابل ERPNext=%.2f"
                ) % (d["partner"], d["odoo"], d["erpnext"]),
                "resync_record_id": d["partner_id"],
                "resync_method": self.env[
                    "nexus.erpnext.bridge.extensions"
                ].push_partner,
            })

        # Persist drift lines and keep a handle to each for later resolution
        for d in drifts:
            self.write({
                "drift_line_ids": [(0, 0, {
                    "summary": d["summary"],
                    "drift_key": d.get("drift_key"),
                    "resolved": False,
                })],
            })
            d["line"] = self.drift_line_ids.sorted("id")[-1]

        return drifts

    def _escalate_if_persistent(self, drift, threshold=3):
        """Open a support incident if the same drift_key repeated ``threshold``
        times in a row across the last reconciliation runs, instead of
        silently re-attempting the resync forever.
        """
        Incident = self.env.get("copilot.support.incident")
        if not Incident:
            return
        drift_key = drift.get("drift_key")
        if not drift_key:
            return

        recent_runs = self.search(
            [("id", "!=", self.id)], order="run_date desc", limit=threshold - 1
        )
        repeats = 1  # current run counts as one occurrence
        for run in recent_runs:
            if any(
                line.drift_key == drift_key and not line.resolved
                for line in run.drift_line_ids
            ):
                repeats += 1

        if repeats < threshold:
            return

        existing = Incident.search_count([
            ("name", "like", "Nexus Reconciliation"),
            ("description", "like", drift_key),
            ("create_date", ">=", fields.Datetime.subtract(
                fields.Datetime.now(), days=1
            )),
        ])
        if existing:
            return

        Incident.create({
            "name": _("Nexus Reconciliation: drift persisted %d runs") % repeats,
            "severity": "medium",
            "description": "%s\n[drift_key=%s]" % (drift["summary"], drift_key),
        })

    # ─────────────────────────────────────────────────────────────────
    # Local aggregations (Odoo side)
    # ─────────────────────────────────────────────────────────────────
    def _odoo_period_totals(self):
        today = fields.Date.today()
        first_of_month = today.replace(day=1)
        domain = [
            ("parent_state", "=", "posted"),
            ("date", ">=", first_of_month),
            ("date", "<=", today),
        ]
        lines = self.env["account.move.line"].read_group(
            domain, ["account_id", "balance"], ["account_id"]
        )
        revenue = expense = 0.0
        for g in lines:
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
        return {"revenue": revenue, "expense": expense}

    def _compare_partner_balances(self, account_type):
        """Compare per-partner residual balances between Odoo and ERPNext."""
        MoveLine = self.env["account.move.line"]
        domain = [
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("account_id.account_type", "=", account_type),
        ]
        odoo_lines = MoveLine.read_group(
            domain, ["partner_id", "amount_residual"], ["partner_id"]
        )
        odoo_totals = {
            g["partner_id"][0]: g["amount_residual"]
            for g in odoo_lines
            if g["partner_id"]
        }
        erp_totals = self._erpnext_partner_totals(account_type)

        diffs = []
        all_partner_ids = set(odoo_totals) | set(erp_totals)
        for pid in all_partner_ids:
            o = odoo_totals.get(pid, 0.0)
            e = erp_totals.get(pid, 0.0)
            if abs(o - e) > 0.5:
                partner = self.env["res.partner"].browse(pid)
                diffs.append({
                    "partner_id": pid,
                    "partner": partner.display_name if partner.exists() else "?",
                    "odoo": o,
                    "erpnext": e,
                })
        return diffs

    # ─────────────────────────────────────────────────────────────────
    # ERPNext aggregations
    # ─────────────────────────────────────────────────────────────────
    def _erpnext_period_totals(self):
        """Sum Income/Expense GL Entry movements for the current month.

        Uses the standard ``GL Entry`` and ``Account`` REST resources that
        exist in any ERPNext installation — no custom Frappe app required.
        """
        bridge = self.env["nexus.erpnext.bridge"]
        company = self.env.company.name
        today = fields.Date.today()
        first_of_month = today.replace(day=1)
        try:
            accounts_resp = bridge._request(
                "GET",
                "/api/resource/Account",
                params={
                    "fields": json.dumps(["name", "root_type"]),
                    "filters": json.dumps([
                        ["company", "=", company],
                        ["root_type", "in", ["Income", "Expense"]],
                    ]),
                    "limit_page_length": 0,
                },
                timeout=20,
            )
            root_type_by_account = {
                row["name"]: row.get("root_type")
                for row in accounts_resp.get("data", [])
            }

            gl_resp = bridge._request(
                "GET",
                "/api/resource/GL Entry",
                params={
                    "fields": json.dumps(["account", "debit", "credit"]),
                    "filters": json.dumps([
                        ["company", "=", company],
                        ["posting_date", ">=", str(first_of_month)],
                        ["posting_date", "<=", str(today)],
                        ["is_cancelled", "=", 0],
                    ]),
                    "limit_page_length": 0,
                },
                timeout=30,
            )
            revenue = expense = 0.0
            for row in gl_resp.get("data", []):
                root_type = root_type_by_account.get(row.get("account"))
                debit = float(row.get("debit") or 0.0)
                credit = float(row.get("credit") or 0.0)
                if root_type == "Income":
                    revenue += credit - debit
                elif root_type == "Expense":
                    expense += debit - credit
            return {"revenue": revenue, "expense": expense}
        except Exception as exc:
            _logger.warning(
                "Nexus reconciliation: failed to fetch ERPNext period totals: %s",
                exc,
            )
            return {"revenue": 0.0, "expense": 0.0}

    def _erpnext_partner_totals(self, account_type):
        """Sum outstanding invoice amounts per partner from ERPNext.

        Matches partners by display name against ``customer``/``supplier``
        since there is no shared numeric ID between Odoo and ERPNext for
        partners; this is a best-effort heuristic.
        """
        bridge = self.env["nexus.erpnext.bridge"]
        is_receivable = "receivable" in account_type
        resource = "/api/resource/Sales Invoice" if is_receivable else "/api/resource/Purchase Invoice"
        party_field = "customer" if is_receivable else "supplier"
        try:
            data = bridge._request(
                "GET",
                resource,
                params={
                    "fields": json.dumps([party_field, "outstanding_amount"]),
                    "filters": json.dumps([
                        ["company", "=", self.env.company.name],
                        ["docstatus", "=", 1],
                        ["outstanding_amount", "!=", 0],
                    ]),
                    "limit_page_length": 0,
                },
                timeout=20,
            )
            totals = {}
            name_cache = {}
            for row in data.get("data", []):
                partner_name = row.get(party_field)
                if not partner_name:
                    continue
                if partner_name not in name_cache:
                    partner = self.env["res.partner"].search(
                        [("name", "=", partner_name)], limit=1
                    )
                    name_cache[partner_name] = partner.id if partner else None
                partner_id = name_cache[partner_name]
                if partner_id:
                    totals[partner_id] = totals.get(partner_id, 0.0) + float(
                        row.get("outstanding_amount") or 0.0
                    )
            return totals
        except Exception as exc:
            _logger.warning(
                "Nexus reconciliation: failed to fetch ERPNext %s totals: %s",
                party_field, exc,
            )
            return {}


class NexusReconciliationLine(models.Model):
    """Individual drift finding."""

    _name = "nexus.erpnext.reconciliation.line"
    _description = "Nexus Reconciliation Drift Line"

    reconciliation_id = fields.Many2one(
        "nexus.erpnext.reconciliation",
        string="Run",
        required=True,
        ondelete="cascade",
    )
    summary = fields.Char(string="Summary", required=True)
    drift_key = fields.Char(
        string="Drift Key",
        index=True,
        help="Stable identifier (e.g. 'receivable.42') used to detect the "
        "same drift repeating across reconciliation runs, independent of "
        "the exact amounts shown in the summary text.",
    )
    resolved = fields.Boolean(string="Resolved", default=False)
    resolved_at = fields.Datetime(string="Resolved At")
