"""Public API for the AI Scoping & Checkout wizard (consumed by the
Next.js marketing site — see nexus_saas_website/README.md).
"""
import logging

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class ScopingController(http.Controller):
    _BASE_ROUTE = "/saas/scoping"

    def _json_response(self, data, status=200):
        return request.make_json_response(data, status=status)

    @http.route(f"{_BASE_ROUTE}/sectors", type="http", auth="none", methods=["GET"], csrf=False, sitemap=False)
    def list_sectors(self):
        """Public: list sectors + their questions/labels for the wizard UI."""
        sectors = request.env["nexus.saas.sector"].sudo().search([("active", "=", True)])
        return self._json_response({
            "sectors": [
                {"code": s.code, "name": s.name, "description": s.description or ""}
                for s in sectors
            ]
        })

    @http.route(f"{_BASE_ROUTE}/quote", type="json", auth="none", methods=["POST"], csrf=False, sitemap=False)
    def compute_quote(self):
        """Compute a dynamic quote from the wizard's answers, without
        persisting a tenant/subscription yet.

        Expects JSON body:
            {
                "company_name": "Acme LLC",
                "contact_email": "...",
                "sector_code": "fuel_station",
                "branches_count": 2,
                "pos_count": 6,
                "warehouse_main_count": 1,
                "warehouse_sub_count": 2,
                "employees_count": 25,
                "has_manufacturing": false,
                "has_iot_integration": true,
                "has_ecommerce": false,
                "billing_interval": "month"
            }
        """
        payload = request.jsonrequest or {}
        sector = request.env["nexus.saas.sector"].sudo().search(
            [("code", "=", payload.get("sector_code"))], limit=1
        )
        if not sector:
            return self._json_response({"error": "Unknown sector_code."}, status=400)

        vals = self._extract_scoping_vals(payload, sector.id)
        try:
            scoping = request.env["nexus.saas.scoping.request"].sudo().create(vals)
        except (UserError, ValidationError) as exc:
            return self._json_response({"error": str(exc)}, status=400)

        scoping.state = "quoted"
        return self._json_response(self._quote_response(scoping))

    @http.route(f"{_BASE_ROUTE}/checkout", type="json", auth="none", methods=["POST"], csrf=False, sitemap=False)
    def checkout(self):
        """Start checkout for a previously computed quote.

        Expects JSON body:
            {
                "scoping_reference": "SCOPE-0001",
                "tenant_code": "acme",
                "admin_email": "...",
                "admin_password": "..."
            }
        """
        payload = request.jsonrequest or {}
        reference = payload.get("scoping_reference")
        tenant_code = (payload.get("tenant_code") or "").strip().lower()
        admin_email = payload.get("admin_email")
        admin_password = payload.get("admin_password")

        if not reference or not tenant_code:
            return self._json_response(
                {"error": "scoping_reference and tenant_code are required."}, status=400
            )

        scoping = request.env["nexus.saas.scoping.request"].sudo().search(
            [("name", "=", reference)], limit=1
        )
        if not scoping:
            return self._json_response({"error": "Scoping request not found."}, status=404)

        try:
            result = scoping.action_start_checkout(
                tenant_code=tenant_code,
                admin_email=admin_email,
                admin_password=admin_password,
            )
        except (UserError, ValidationError) as exc:
            return self._json_response({"error": str(exc)}, status=400)
        except Exception:
            _logger.exception("Scoping checkout failed for %s", reference)
            return self._json_response({"error": "Internal error starting checkout."}, status=500)

        return self._json_response(result)

    # ── Helpers ──────────────────────────────────────────────────────
    def _extract_scoping_vals(self, payload, sector_id):
        return {
            "company_name": (payload.get("company_name") or "").strip(),
            "contact_email": (payload.get("contact_email") or "").strip().lower(),
            "contact_phone": payload.get("contact_phone"),
            "sector_id": sector_id,
            "branches_count": int(payload.get("branches_count") or 1),
            "pos_count": int(payload.get("pos_count") or 0),
            "warehouse_main_count": int(payload.get("warehouse_main_count") or 1),
            "warehouse_sub_count": int(payload.get("warehouse_sub_count") or 0),
            "employees_count": int(payload.get("employees_count") or 1),
            "has_manufacturing": bool(payload.get("has_manufacturing")),
            "has_iot_integration": bool(payload.get("has_iot_integration")),
            "has_ecommerce": bool(payload.get("has_ecommerce")),
            "billing_interval": payload.get("billing_interval") or "month",
        }

    def _quote_response(self, scoping):
        return {
            "scoping_reference": scoping.name,
            "sector": scoping.sector_id.name,
            "resource_tier": scoping.resource_tier,
            "recommended_modules": (scoping.recommended_modules or "").split(","),
            "price_monthly": scoping.price_monthly,
            "price_yearly": scoping.price_yearly,
            "price_breakdown": (scoping.price_breakdown or "").split("\n"),
            "currency": request.env.company.currency_id.name,
        }
