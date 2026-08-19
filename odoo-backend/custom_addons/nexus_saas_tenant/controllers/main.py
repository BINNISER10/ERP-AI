"""Public HTTP endpoints for SaaS tenant provisioning and health."""
import logging

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SaaSController(http.Controller):
    _BASE_ROUTE = "/saas"

    def _json_response(self, data, status=200):
        return request.make_json_response(data, status=status)

    @http.route(f"{_BASE_ROUTE}/health", type="http", auth="none", methods=["GET"], csrf=False, sitemap=False)
    def health(self):
        """Public health check used by load balancers and monitoring."""
        return self._json_response({"status": "ok", "service": "nexus-saas"})

    @http.route(f"{_BASE_ROUTE}/plans", type="http", auth="none", methods=["GET"], csrf=False, sitemap=False)
    def list_plans(self):
        """Public endpoint returning available SaaS plans."""
        plans = request.env["nexus.saas.plan"].sudo().search([("active", "=", True)])
        result = []
        for plan in plans:
            result.append({
                "code": plan.code,
                "name": plan.name,
                "price_monthly": plan.price_monthly,
                "price_yearly": plan.price_yearly,
                "trial_days": plan.trial_days,
                "quotas": {
                    "max_users": plan.max_users,
                    "max_companies": plan.max_companies,
                    "max_products": plan.max_products,
                    "max_invoices_monthly": plan.max_invoices_monthly,
                    "storage_gb": plan.storage_gb,
                    "max_api_calls_daily": plan.max_api_calls_daily,
                },
                "features": {
                    "ai_copilot": plan.has_ai_copilot,
                    "advanced_accounting": plan.has_advanced_accounting,
                    "multi_location": plan.has_multi_location,
                    "priority_support": plan.has_priority_support,
                    "white_label": plan.has_white_label,
                },
            })
        return self._json_response({"plans": result})

    @http.route(f"{_BASE_ROUTE}/signup", type="json", auth="none", methods=["POST"], csrf=False, sitemap=False)
    def signup(self):
        """Self-service signup endpoint.

        Expects JSON body:
            {
                "name": "Acme LLC",
                "code": "acme",
                "email": "admin@acme.com",
                "password": "...",
                "plan_code": "basic"   # optional
            }
        """
        # Check global setting
        signup_enabled = request.env["ir.config_parameter"].sudo().get_param(
            "nexus_saas.self_service_signup", "false"
        ).lower() in ("true", "1", "yes")
        if not signup_enabled:
            return self._json_response({"error": "Self-service signup is disabled."}, status=403)

        payload = request.jsonrequest or {}
        name = (payload.get("name") or "").strip()
        code = (payload.get("code") or "").strip().lower()
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
        plan_code = (payload.get("plan_code") or "").strip() or False

        errors = []
        if not name:
            errors.append("name is required")
        if not code:
            errors.append("code is required")
        if not email or "@" not in email:
            errors.append("valid email is required")
        if not password or len(password) < 8:
            errors.append("password must be at least 8 characters")
        if errors:
            return self._json_response({"error": "Validation failed", "details": errors}, status=400)

        plan_id = False
        if plan_code:
            plan = request.env["nexus.saas.plan"].sudo().search([("code", "=", plan_code)], limit=1)
            if not plan:
                return self._json_response({"error": "Unknown plan code."}, status=400)
            plan_id = plan.id

        try:
            tenant = request.env["nexus.saas.tenant"].sudo().provision_tenant(
                name=name, code=code, email=email, plan_id=plan_id, create_user=True
            )
            user = tenant.owner_user_id
            # Set password for the created user
            user.sudo().write({"password": password})

            # Create a subscription record
            request.env["nexus.saas.subscription"].sudo().create({
                "tenant_id": tenant.id,
                "plan_id": tenant.plan_id.id,
                "state": "trialing",
                "trial_end": tenant.trial_end_date,
            })

            base_domain = request.env["ir.config_parameter"].sudo().get_param(
                "nexus_saas.base_domain", "nexus-engine.app"
            )
            return self._json_response({
                "tenant": {
                    "id": tenant.id,
                    "name": tenant.name,
                    "code": tenant.code,
                    "subdomain": f"{tenant.code}.{base_domain}",
                    "trial_end": fields.Date.to_string(tenant.trial_end_date),
                },
                "message": "Tenant created. Please check your email for login instructions.",
            }, status=201)
        except (UserError, ValidationError) as exc:
            _logger.warning("SaaS signup failed: %s", exc)
            return self._json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            _logger.exception("SaaS signup unexpected error.")
            return self._json_response({"error": "Internal error."}, status=500)

    @http.route(f"{_BASE_ROUTE}/tenant/<string:code>/status", type="http", auth="none", methods=["GET"], csrf=False, sitemap=False)
    def tenant_status(self, code):
        """Public status endpoint for a tenant (used by signup landing pages)."""
        tenant = request.env["nexus.saas.tenant"].sudo().search([("code", "=", code)], limit=1)
        if not tenant:
            return self._json_response({"error": "Tenant not found"}, status=404)
        return self._json_response({
            "code": tenant.code,
            "name": tenant.name,
            "state": tenant.state,
            "is_trial": tenant.is_trial,
            "trial_end": fields.Date.to_string(tenant.trial_end_date) if tenant.trial_end_date else None,
        })
