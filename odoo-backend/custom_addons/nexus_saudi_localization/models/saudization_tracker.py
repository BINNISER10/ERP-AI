# -*- coding: utf-8 -*-
"""Nexus Saudization Tracker — متتبع نظام نطاقات.

Computes real-time Saudization percentage from ``hr.employee`` and
exposes a target-vs-actual dashboard widget. The model is read-only —
it pulls from employees rather than storing denormalised data.

Nitaqat bands (Ministry of Human Resources & Social Development) are
activity-specific; this module uses the published thresholds for
"Retail / Wholesale / Restaurants" entities as a reasonable default.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class NexusSaudizationTracker(models.AbstractModel):
    """Pure-computation helper for Saudization KPIs."""

    _name = "nexus.saudi.saudization.tracker"
    _description = "Nexus Saudization Tracker"

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────
    def compute_for_company(self, company):
        """Return a dict of Saudization KPIs for a company."""
        employees = self.env["hr.employee"].search([
            ("company_id", "=", company.id),
            ("active", "=", True),
        ])
        total = len(employees)
        saudi = employees.filtered("is_saudi_nationality")
        non_saudi = employees - saudi
        saudi_count = len(saudi)
        non_saudi_count = len(non_saudi)
        pct = (saudi_count / total * 100.0) if total else 0.0

        # Salary cost weight (Nitaqat also considers this)
        saudi_salary = sum(e.contract_id.wage for e in saudi if e.contract_id)
        total_salary = sum(
            e.contract_id.wage for e in employees if e.contract_id
        )
        saudi_salary_pct = (
            saudi_salary / total_salary * 100.0 if total_salary else 0.0
        )

        return {
            "company_id": company.id,
            "total_employees": total,
            "saudi_employees": saudi_count,
            "non_saudi_employees": non_saudi_count,
            "saudization_pct": round(pct, 2),
            "saudi_salary_pct": round(saudi_salary_pct, 2),
            "band": self._band_for(pct),
            "employees": [
                {
                    "id": e.id,
                    "name": e.name,
                    "is_saudi": e.is_saudi_nationality,
                    "department": e.department_id.display_name if e.department_id else "",
                    "job": e.job_id.name if e.job_id else "",
                }
                for e in employees
            ],
        }

    # ─────────────────────────────────────────────────────────────────
    # Nitaqat band logic
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def _band_for(self, pct):
        """Map Saudization % to the published Nitaqat bands.

        Approximate thresholds (used by MOL's online calculator for
        most activities). Real thresholds depend on activity / size.
        """
        if pct >= 50:
            return {"code": "platinum", "label": _("بلاتيني / Platinum")}
        if pct >= 30:
            return {"code": "green_high", "label": _("أخضر مرتفع / Green High")}
        if pct >= 20:
            return {"code": "green_mid", "label": _("أخضر متوسط / Green Mid")}
        if pct >= 10:
            return {"code": "green_low", "label": _("أخضر منخفض / Green Low")}
        if pct >= 5:
            return {"code": "yellow", "label": _("أصفر / Yellow")}
        return {"code": "red", "label": _("أحمر / Red")}
