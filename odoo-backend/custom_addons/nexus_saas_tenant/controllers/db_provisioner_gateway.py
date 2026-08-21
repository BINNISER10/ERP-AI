"""HTTP contract between the control-plane and the external, privileged
``saas-db-provisioner`` service (see ``saas-db-provisioner/`` at the repo
root).

This Odoo process intentionally never creates/drops Postgres databases
itself — that requires OS/Postgres-admin privileges application code
should never hold. Instead:

  1. GET  /saas/db-provisioner/pending   — provisioner polls for jobs
  2. POST /saas/db-provisioner/callback  — provisioner reports the result

Both routes are authenticated via a static shared secret configured in
Settings > SaaS ("DB Provisioner API Key"), sent as the
``X-Provisioner-Api-Key`` header — no interactive Odoo session involved.
"""
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SaaSDbProvisionerGateway(http.Controller):
    _BASE_ROUTE = "/saas/db-provisioner"

    def _json_response(self, data, status=200):
        return request.make_json_response(data, status=status)

    def _authenticated(self):
        expected = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("nexus_saas.db_provisioner_api_key")
        )
        provided = request.httprequest.headers.get("X-Provisioner-Api-Key")
        return bool(expected) and provided == expected

    @http.route(
        f"{_BASE_ROUTE}/pending", type="http", auth="none", methods=["GET"], csrf=False, sitemap=False
    )
    def pending(self):
        if not self._authenticated():
            return self._json_response({"error": "Unauthorized"}, status=401)

        env = request.env(su=True)
        requests_ = env["nexus.saas.db.provision.request"].search(
            [("state", "=", "pending")], order="id asc", limit=20
        )
        # Mark as in_progress immediately so a slow/retried poll from the
        # same or another provisioner instance never double-processes a job.
        requests_.write({"state": "in_progress", "started_at": fields.Datetime.now()})

        jobs = []
        for req in requests_:
            jobs.append({
                "request_id": req.id,
                "request_type": req.request_type,
                "target_db_name": req.target_db_name,
                "modules": [m.strip() for m in (req.modules or "").split(",") if m.strip()],
                "admin_name": req.admin_name,
                "admin_email": req.admin_email,
                "admin_password": req.admin_password,
            })
        return self._json_response({"jobs": jobs})

    @http.route(
        f"{_BASE_ROUTE}/callback", type="json", auth="none", methods=["POST"], csrf=False, sitemap=False
    )
    def callback(self):
        if not self._authenticated():
            return {"error": "Unauthorized"}

        payload = request.jsonrequest or {}
        request_id = payload.get("request_id")
        success = bool(payload.get("success"))
        message = payload.get("message") or ""
        log = payload.get("log") or ""

        env = request.env(su=True)
        req = env["nexus.saas.db.provision.request"].browse(request_id)
        if not req.exists():
            return {"error": f"Unknown request_id {request_id}"}

        req.write({
            "state": "done" if success else "error",
            "error_message": False if success else message,
            "log": log,
            "completed_at": fields.Datetime.now(),
            "admin_password": False,  # one-time secret, consumed either way
        })

        if req.request_type == "create":
            req.tenant_id._on_dedicated_db_provisioned(req, success, message)
        elif req.request_type == "drop" and success:
            req.tenant_id.message_post(body="Dedicated database dropped successfully.")

        return {"ok": True}
