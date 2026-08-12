import json
import logging
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AiMonitorWizard(models.TransientModel):
    _name = "nexus.ai.monitor.wizard"
    _description = "AI Monitor Wizard"

    monitor_type = fields.Selection(
        [
            ("inventory_sales", "Inventory + Sales"),
            ("cash_register", "Cash Register"),
            ("bank_reconciliation", "Bank Reconciliation"),
            ("reports", "Report Suggestions"),
        ],
        default="inventory_sales",
        required=True,
    )
    date_from = fields.Date(default=lambda self: fields.Date.today())
    date_to = fields.Date(default=lambda self: fields.Date.today())
    language = fields.Char(default="ar", required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    role = fields.Char(default="manager", help="User role for report suggestions")
    industry = fields.Char(default="general", help="Industry for report suggestions")

    state = fields.Selection(
        [("input", "Input"), ("result", "Result")],
        default="input",
    )
    result_json = fields.Text(readonly=True)
    summary = fields.Text(readonly=True)

    @api.onchange("monitor_type")
    def _onchange_monitor_type(self):
        if self.monitor_type == "reports":
            self.date_from = False
            self.date_to = False

    def _fetch_inventory_sales(self):
        inventory = []
        sales = []
        sq = self.env.get("stock.quant")
        if sq:
            quants = sq.search([
                ("company_id", "=", self.company_id.id),
                ("quantity", "!=", 0),
            ], limit=50)
            inventory = [
                {
                    "product": q.product_id.display_name or q.product_id.name,
                    "location": q.location_id.display_name,
                    "quantity": q.quantity,
                    "reserved": q.reserved_quantity,
                }
                for q in quants
            ]
        so = self.env.get("sale.order")
        if so:
            orders = so.search([
                ("company_id", "=", self.company_id.id),
                ("date_order", ">=", datetime.combine(self.date_from, time.min)),
                ("date_order", "<=", datetime.combine(self.date_to, time.max)),
            ], limit=50)
            sales = [
                {
                    "name": o.name,
                    "amount": o.amount_total,
                    "state": o.state,
                    "partner": o.partner_id.name,
                }
                for o in orders
            ]
        return {"inventory": inventory, "sales": sales, "language": self.language}

    def _fetch_cash_register(self):
        sessions = []
        ps = self.env.get("pos.session")
        if ps:
            records = ps.search([
                ("company_id", "=", self.company_id.id),
                ("start_at", ">=", datetime.combine(self.date_from, time.min)),
                ("start_at", "<=", datetime.combine(self.date_to, time.max)),
            ], limit=50)
            sessions = [
                {
                    "name": s.name,
                    "state": s.state,
                    "cashier": s.user_id.name,
                    "balance_start": s.cash_register_balance_start,
                    "balance_end": s.cash_register_balance_end_real,
                }
                for s in records
            ]
        return {"sessions": sessions, "language": self.language}

    def _fetch_bank_reconciliation(self):
        bank_lines = []
        transactions = []
        bsl = self.env.get("account.bank.statement.line")
        if bsl:
            records = bsl.search([
                ("company_id", "=", self.company_id.id),
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
            ], limit=50)
            bank_lines = [
                {
                    "name": r.payment_ref,
                    "date": str(r.date),
                    "amount": r.amount,
                    "journal": r.journal_id.name,
                }
                for r in records
            ]
        aml = self.env.get("account.move.line")
        if aml:
            records = aml.search([
                ("company_id", "=", self.company_id.id),
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
                ("account_id.account_type", "=", "asset_cash"),
            ], limit=50)
            transactions = [
                {
                    "name": r.name,
                    "date": str(r.date),
                    "amount": r.balance,
                    "move": r.move_id.name,
                }
                for r in records
            ]
        return {
            "bank_lines": bank_lines,
            "transactions": transactions,
            "language": self.language,
        }

    def _fetch_report_suggestions(self):
        return {
            "role": self.role,
            "industry": self.industry,
            "size": "small",
            "language": self.language,
        }

    def _endpoint_and_payload(self):
        dispatch = {
            "inventory_sales": ("api/v1/ai/monitor/inventory-sales", self._fetch_inventory_sales),
            "cash_register": ("api/v1/ai/monitor/cash-register", self._fetch_cash_register),
            "bank_reconciliation": ("api/v1/ai/monitor/bank-reconciliation", self._fetch_bank_reconciliation),
            "reports": ("api/v1/ai/reports/suggest", self._fetch_report_suggestions),
        }
        endpoint, fetcher = dispatch.get(self.monitor_type, ("", lambda: {}))
        return endpoint, fetcher()

    def action_run(self):
        self.ensure_one()
        config = self.env["nexus.ai.config"].get_config()
        endpoint, payload = self._endpoint_and_payload()
        if not endpoint:
            raise UserError(_("Unsupported monitor type."))
        result = config._call_ai_service(endpoint, payload)
        self.result_json = json.dumps(result, ensure_ascii=False)
        self.summary = result.get("summary_ar") or result.get("summary") or ""
        self.state = "result"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
