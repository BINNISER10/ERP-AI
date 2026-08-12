"""Nexus JSON-RPC gateway for the Flutter POS.

Implements a lightweight HTTP JSON-RPC surface:

- authenticate
- get_catalog
- post_offline_orders
"""
import json
import logging
import uuid
from datetime import datetime

from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import UserError, AccessDenied

_logger = logging.getLogger(__name__)


class NexusPosGateway(http.Controller):
    _BASE_ROUTE = "/nexus_pos/jsonrpc"

    def _json_response(self, result=None, error=None, id=None):
        payload = {"jsonrpc": "2.0", "id": id}
        if error:
            payload["error"] = error
        if result is not None:
            payload["result"] = result
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json")],
        )

    def _parse_request(self, body):
        try:
            data = json.loads(body) if isinstance(body, (str, bytes)) else body
        except (ValueError, TypeError) as exc:
            return None, {"code": -32700, "message": "Parse error", "data": str(exc)}
        if not isinstance(data, dict):
            return None, {"code": -32600, "message": "Invalid Request"}
        return data, None

    @http.route(f"{_BASE_ROUTE}", type="http", auth="none", methods=["POST"], csrf=False, sitemap=False)
    def pos_jsonrpc(self, **kwargs):
        body = request.httprequest.get_data(as_text=True)
        data, error = self._parse_request(body)
        if error:
            return self._json_response(error=error, id=None)

        method = data.get("method")
        params = data.get("params", {})
        req_id = data.get("id")

        if method == "authenticate":
            return self._authenticate(params, req_id)
        if method == "get_catalog":
            return self._get_catalog(params, req_id)
        if method == "post_offline_orders":
            return self._post_offline_orders(params, req_id)

        return self._json_response(
            error={"code": -32601, "message": f"Method not found: {method}"},
            id=req_id,
        )

    def _authenticate(self, params, req_id):
        login = params.get("login")
        password = params.get("password")
        if not login or not password:
            return self._json_response(
                error={"code": 400, "message": "Missing login or password"},
                id=req_id,
            )

        try:
            uid = request.session.authenticate(request.db, login, password)
        except AccessDenied as exc:
            _logger.warning("POS auth failed for %s: %s", login, exc)
            return self._json_response(
                error={"code": 401, "message": "Authentication failed"},
                id=req_id,
            )

        user = request.env["res.users"].sudo().browse(uid)
        company = user.company_id
        return self._json_response(
            result={
                "uid": uid,
                "name": user.name,
                "login": user.login,
                "company_id": company.id,
                "company_name": company.name,
                "currency_id": company.currency_id.id,
                "currency_name": company.currency_id.name,
                "session_id": request.session.sid,
            },
            id=req_id,
        )

    def _get_catalog(self, params, req_id):
        if not request.uid:
            return self._json_response(
                error={"code": 401, "message": "Not authenticated"},
                id=req_id,
            )

        env = request.env(user=request.uid)
        company_id = params.get("company_id") or env.company.id

        products = env["product.product"].with_company(company_id).search(
            [("sale_ok", "=", True), ("active", "=", True)]
        )
        categories = env["pos.category"].with_company(company_id).search([])
        taxes = env["account.tax"].with_company(company_id).search([])

        product_data = []
        for product in products:
            product_data.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "default_code": product.default_code or "",
                    "barcode": product.barcode or "",
                    "list_price": product.list_price,
                    "standard_price": product.standard_price,
                    "uom_id": product.uom_id.id,
                    "uom_name": product.uom_id.name,
                    "categ_id": product.categ_id.id,
                    "taxes_id": [t.id for t in product.taxes_id],
                    "qty_available": product.qty_available,
                    "image_128": product.image_128.decode("utf-8") if product.image_128 else None,
                }
            )

        category_data = [
            {
                "id": c.id,
                "name": c.name,
                "parent_id": c.parent_id.id,
            }
            for c in categories
        ]

        tax_data = [
            {
                "id": t.id,
                "name": t.name,
                "amount": t.amount,
                "amount_type": t.amount_type,
            }
            for t in taxes
        ]

        return self._json_response(
            result={
                "products": product_data,
                "categories": category_data,
                "taxes": tax_data,
                "company_id": company_id,
            },
            id=req_id,
        )

    def _post_offline_orders(self, params, req_id):
        if not request.uid:
            return self._json_response(
                error={"code": 401, "message": "Not authenticated"},
                id=req_id,
            )

        env = request.env(user=request.uid)
        orders = params.get("orders", [])
        if not isinstance(orders, list) or not orders:
            return self._json_response(
                error={"code": 400, "message": "orders must be a non-empty list"},
                id=req_id,
            )

        result = {"created": [], "errors": [], "failed_indices": []}

        for index, order in enumerate(orders):
            try:
                with env.cr.savepoint():
                    created = env["nexus.pos.order"].sudo().create_pos_order(order)
                    result["created"].append(
                        {
                            "index": index,
                            "odoo_order_id": created.get("order_id"),
                            "name": created.get("name"),
                            "client_order_ref": order.get("client_order_ref"),
                        }
                    )
            except Exception as exc:
                _logger.error("POS offline order post failed: %s", exc, exc_info=True)
                result["errors"].append({"index": index, "message": str(exc)})
                result["failed_indices"].append(index)

        return self._json_response(result=result, id=req_id)
