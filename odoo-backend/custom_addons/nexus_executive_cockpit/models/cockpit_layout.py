"""Per-user customizable Executive Cockpit widget layout."""
import json

from odoo import api, fields, models

DEFAULT_WIDGET_ORDER = [
    "liquidity",
    "daily_sales",
    "gross_margin",
    "revenue_trend",
    "cash_flow_forecast",
    "ar_aging",
    "branch_performance",
    "top_expenses",
    "customer_concentration",
    "anomaly_alerts",
]


class NexusCockpitLayout(models.Model):
    _name = "nexus.cockpit.layout"
    _description = "Executive Cockpit Layout (per user)"
    _rec_name = "user_id"

    user_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, index=True
    )
    widget_order_json = fields.Text(
        string="Widget Order (JSON)",
        default=lambda self: json.dumps(DEFAULT_WIDGET_ORDER),
    )
    hidden_widgets_json = fields.Text(
        string="Hidden Widgets (JSON)",
        default="[]",
    )

    _sql_constraints = [
        ("user_uniq", "unique(user_id)", "Each user has exactly one cockpit layout."),
    ]

    @api.model
    def get_for_user(self, user=None):
        user = user or self.env.user
        rec = self.search([("user_id", "=", user.id)], limit=1)
        if rec:
            return rec
        return self.create({"user_id": user.id})

    def get_layout(self):
        self.ensure_one()
        try:
            order = json.loads(self.widget_order_json or "[]")
        except ValueError:
            order = list(DEFAULT_WIDGET_ORDER)
        try:
            hidden = json.loads(self.hidden_widgets_json or "[]")
        except ValueError:
            hidden = []
        return {"order": order, "hidden": hidden}

    def set_layout(self, order=None, hidden=None):
        self.ensure_one()
        vals = {}
        if order is not None:
            vals["widget_order_json"] = json.dumps(order)
        if hidden is not None:
            vals["hidden_widgets_json"] = json.dumps(hidden)
        if vals:
            self.write(vals)
        return self.get_layout()
