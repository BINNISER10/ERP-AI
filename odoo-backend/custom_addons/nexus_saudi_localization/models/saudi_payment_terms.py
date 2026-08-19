# -*- coding: utf-8 -*-
"""Nexus Saudi Payment Terms — شروط الدفع السعودية.

Standard Saudi payment terms with their day counts.  These are the
defaults recommended by most Saudi SMEs; the user can override per
customer.

    COD — Cash on delivery
    IMM — Immediate (0 days)
    NET_7 / NET_15 / NET_30 / NET_45 / NET_60 / NET_90
    END_OF_MONTH_30 / END_OF_MONTH_60
"""

from odoo import api, fields, models, _


class NexusSaudiPaymentTerm(models.Model):
    """Saudi-friendly payment term templates."""

    _name = "nexus.saudi.payment.term"
    _description = "Nexus Saudi Payment Terms"
    _order = "days asc"

    name = fields.Char(string="Term", required=True)
    code = fields.Char(string="Code", required=True)
    days = fields.Integer(string="Days", default=0)
    end_of_month = fields.Boolean(string="End-of-Month Anchor", default=False)
    description = fields.Char(string="Description")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "saudi_term_code_unique",
            "UNIQUE(code)",
            "Payment term code must be unique.",
        ),
    ]

    @api.model
    def _load_defaults(cls):
        """Seed the standard set on module install."""
        defaults = [
            ("COD", "الدفع عند الاستلام / Cash on Delivery", 0, False),
            ("IMM", "فوري / Immediate", 0, False),
            ("NET7", "صافي 7 أيام / Net 7", 7, False),
            ("NET15", "صافي 15 يوماً / Net 15", 15, False),
            ("NET30", "صافي 30 يوماً / Net 30", 30, False),
            ("NET45", "صافي 45 يوماً / Net 45", 45, False),
            ("NET60", "صافي 60 يوماً / Net 60", 60, False),
            ("NET90", "صافي 90 يوماً / Net 90", 90, False),
            ("EOM30", "نهاية الشهر + 30 / EOM + 30", 30, True),
            ("EOM60", "نهاية الشهر + 60 / EOM + 60", 60, True),
        ]
        for code, name, days, eom in defaults:
            existing = cls.search([("code", "=", code)], limit=1)
            if existing:
                continue
            cls.create({
                "code": code,
                "name": name,
                "days": days,
                "end_of_month": eom,
                "description": name,
            })
