# -*- coding: utf-8 -*-
"""Nexus Finance Report Cache — تخزين نتائج التقارير المؤقت.

Caches the rendered HTML for heavy reports so that re-opening the
same wizard with the same parameters within ``cache_ttl_seconds``
returns instantly. The cache is keyed by ``(report_type, company_id,
date_from, date_to, cost_center_id, account_id, partner_id)``.

Cache storage: ``ir.config_parameter`` (key namespace
``nexus.report.cache.<key>``). The default TTL is 60 seconds, which
covers the typical "user refreshes the wizard" case without keeping
stale data long.
"""

import hashlib
import json
import logging
import time

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


CACHE_NAMESPACE = "nexus.report.cache"
DEFAULT_TTL_SECONDS = 60


class NexusFinanceReportCache(models.AbstractModel):
    """Tiny key-value cache for finance report HTML payloads."""

    _name = "nexus.finance.report.cache"
    _description = "Nexus Finance Report Cache"

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────
    def get(self, wizard):
        """Return cached HTML payload, or ``False`` on miss / expiry."""
        key = self._make_key(wizard)
        full_key = "%s.%s" % (CACHE_NAMESPACE, key)
        ICP = self.env["ir.config_parameter"].sudo()
        record = ICP.search([("key", "=", full_key)], limit=1)
        if not record:
            return False
        try:
            payload = json.loads(record.value)
        except (ValueError, TypeError):
            return False
        if not isinstance(payload, dict):
            return False
        # Expiry check
        expires_at = payload.get("expires_at", 0)
        if expires_at and expires_at < time.time():
            record.unlink()
            return False
        return payload.get("html")

    def set(self, wizard, html, ttl_seconds=None):
        """Store the rendered HTML for ``ttl_seconds`` (default 60)."""
        ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_TTL_SECONDS
        key = self._make_key(wizard)
        full_key = "%s.%s" % (CACHE_NAMESPACE, key)
        payload = {
            "html": html,
            "expires_at": time.time() + ttl,
            "wizard_id": wizard.id,
            "report_type": wizard.report_type,
            "cached_at": fields.Datetime.now(),
        }
        ICP = self.env["ir.config_parameter"].sudo()
        existing = ICP.search([("key", "=", full_key)], limit=1)
        if existing:
            existing.write({"value": json.dumps(payload)})
        else:
            ICP.create({"key": full_key, "value": json.dumps(payload)})

    def invalidate_all(self):
        """Clear the entire Nexus report cache."""
        ICP = self.env["ir.config_parameter"].sudo()
        records = ICP.search([("key", "like", CACHE_NAMESPACE + ".%")])
        if records:
            records.unlink()
        return len(records)

    def stats(self):
        """Return a dict describing the current cache size."""
        ICP = self.env["ir.config_parameter"].sudo()
        records = ICP.search([("key", "like", CACHE_NAMESPACE + ".%")])
        return {
            "total": len(records),
            "expired": sum(
                1
                for r in records
                if self._is_expired(r.value)
            ),
        }

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────
    def _make_key(self, wizard):
        """Stable hash from all parameters that influence the report."""
        components = [
            wizard.report_type or "",
            str(wizard.company_id.id or 0),
            str(wizard.date_from or ""),
            str(wizard.date_to or ""),
            str(wizard.cost_center_id.id or 0),
            str(wizard.account_id.id or 0),
            str(wizard.partner_id.id or 0),
            str(wizard.fiscal_year_id.id or 0),
        ]
        joined = "|".join(components)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]

    def _is_expired(self, raw):
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            return True
        return payload.get("expires_at", 0) < time.time()
