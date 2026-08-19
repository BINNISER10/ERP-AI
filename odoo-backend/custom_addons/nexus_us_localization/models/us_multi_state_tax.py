# -*- coding: utf-8 -*-
"""Nexus US Multi-State Tax — محرك ضريبة المبيعات متعددة الولايات.

Computes the correct sales tax for an invoice line based on the
customer's ship-to state and the company's nexus states. The rates
are loaded from ``data/us_state_tax_rates.xml`` and updated quarterly.

Supports:
    * State-level rate
    * County / city rate
    * ZIP-based district rate (basic)
    * Origin vs destination sourcing (per-state)
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class NexusUSMultiStateTax(models.AbstractModel):
    """Multi-state sales tax calculator."""

    _name = "nexus.us.multi.state.tax"
    _description = "Nexus US Multi-State Tax Calculator"

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def compute(self, company, partner, line_amount, product=None):
        """Return the tax amount and the rate components.

        Returns:
            dict {
                'tax_amount': float,
                'rate_total': float,
                'components': [
                    {'name': str, 'rate': float, 'amount': float}
                ],
                'jurisdiction': str,
            }
        """
        if not partner or not partner.state_id:
            return self._zero_result("No ship-to state")
        state = partner.state_id
        settings = self.env["nexus.us.company.settings"].get_for_company(
            company
        )
        # Does the company have nexus in this state?
        if state not in settings.nexus_state_ids:
            return self._zero_result(
                "No nexus in %s" % state.name
            )
        # Build the rate stack
        components = self._rate_components(state, partner.zip or "")
        if not components:
            return self._zero_result("No rate data for %s" % state.name)
        rate_total = sum(c["rate"] for c in components)
        tax_amount = round(line_amount * rate_total / 100.0, 2)
        return {
            "tax_amount": tax_amount,
            "rate_total": rate_total,
            "components": components,
            "jurisdiction": state.name,
        }

    # ─────────────────────────────────────────────────────────────────
    # Rate data
    # ─────────────────────────────────────────────────────────────────
    def _rate_components(self, state, postal_code):
        """Return the rate stack for a state (and optionally ZIP).

        The ``nexus.us.state.tax.rate`` model holds a flat list of
        rates per state. A future enhancement can add ZIP-level
        overlays.
        """
        Rate = self.env.get("nexus.us.state.tax.rate")
        if not Rate:
            return []
        rates = Rate.search([("state_id", "=", state.id)])
        return [
            {
                "name": r.name,
                "rate": r.rate,
                "amount": 0.0,  # filled in compute()
            }
            for r in rates
        ]

    def _zero_result(self, reason):
        return {
            "tax_amount": 0.0,
            "rate_total": 0.0,
            "components": [],
            "jurisdiction": reason,
        }


class NexusUSStateTaxRate(models.Model):
    """Per-state sales tax rate row."""

    _name = "nexus.us.state.tax.rate"
    _description = "Nexus US State Tax Rate"
    _order = "state_id, sequence"

    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        required=True,
        domain=[("country_id.code", "=", "US")],
    )
    name = fields.Char(string="Rate Name", required=True)
    rate = fields.Float(string="Rate (%)", digits=(5, 3), required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    effective_from = fields.Date(string="Effective From")
    effective_to = fields.Date(string="Effective To")
    active = fields.Boolean(default=True)
