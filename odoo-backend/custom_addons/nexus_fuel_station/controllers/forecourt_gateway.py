"""HTTP ingestion endpoint for the Forecourt Controller.

Per the Ocean Seven fuel-automation technical study, all 11 pumps / 23
nozzles are wired via RS-485 into a single central Forecourt Controller,
which relays normalized readings to Odoo over a standard Ethernet/TCP-IP
link. This module implements that receiving side:

    POST /nexus_fuel/forecourt/readings
    Headers: X-Forecourt-Api-Key: <device api key>
    Body:
        {
            "readings": [
                {
                    "transaction_ref": "TXN-000123",   # required, unique
                    "nozzle_address": "P03-N02",         # required
                    "volume": 25.4,                       # liters, required
                    "amount": 101.6,                       # optional
                    "unit_price": 4.0,                     # optional
                    "meter_total": 184532.7,               # optional
                    "timestamp": "2026-08-21T03:12:00"     # optional, ISO-8601
                },
                ...
            ]
        }

Each reading is first persisted to ``fuel.reading.buffer`` (idempotent on
``transaction_ref`` per device) *before* any business logic executes, so
a connection drop / retry from the controller never loses or
double-counts a transaction. Processing then runs synchronously so the
controller gets an immediate per-item result, with a nightly/periodic
cron (`fuel.reading.buffer._cron_retry_errors`) sweeping up anything
that failed transiently (e.g. nozzle not yet configured).
"""
import json
import logging
from datetime import datetime

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class NexusForecourtGateway(http.Controller):
    _ROUTE = "/nexus_fuel/forecourt/readings"

    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json")],
            status=status,
        )

    def _parse_timestamp(self, value):
        if not value:
            return False
        try:
            return fields.Datetime.to_string(datetime.fromisoformat(value))
        except (ValueError, TypeError):
            return False

    @http.route(_ROUTE, type="http", auth="none", methods=["POST"], csrf=False, sitemap=False)
    def forecourt_readings(self, **kwargs):
        api_key = request.httprequest.headers.get("X-Forecourt-Api-Key")
        env = request.env(su=True)
        device = env["fuel.forecourt.device"]._authenticate(api_key)
        if not device:
            return self._json_response(
                {"error": {"code": 401, "message": "Invalid or missing API key"}},
                status=401,
            )

        try:
            body = json.loads(request.httprequest.get_data(as_text=True) or "{}")
        except (ValueError, TypeError) as exc:
            return self._json_response(
                {"error": {"code": 400, "message": f"Invalid JSON: {exc}"}}, status=400
            )

        readings = body.get("readings")
        if not isinstance(readings, list) or not readings:
            return self._json_response(
                {"error": {"code": 400, "message": "'readings' must be a non-empty list"}},
                status=400,
            )

        env = env.with_company(device.company_id)
        BufferModel = env["fuel.reading.buffer"]
        results = {"accepted": [], "duplicates": [], "errors": []}
        to_process = env["fuel.reading.buffer"]

        for index, reading in enumerate(readings):
            transaction_ref = reading.get("transaction_ref")
            nozzle_address = reading.get("nozzle_address")
            volume = reading.get("volume")

            if not transaction_ref or not nozzle_address or volume is None:
                results["errors"].append(
                    {
                        "index": index,
                        "message": "transaction_ref, nozzle_address and volume are required",
                    }
                )
                continue

            existing = BufferModel.search(
                [
                    ("device_id", "=", device.id),
                    ("transaction_ref", "=", transaction_ref),
                ],
                limit=1,
            )
            if existing:
                results["duplicates"].append(
                    {"index": index, "transaction_ref": transaction_ref, "buffer_id": existing.id}
                )
                continue

            try:
                with env.cr.savepoint():
                    buffer_row = BufferModel.create(
                        {
                            "device_id": device.id,
                            "transaction_ref": transaction_ref,
                            "nozzle_address": nozzle_address,
                            "volume": volume,
                            "amount": reading.get("amount") or 0.0,
                            "unit_price": reading.get("unit_price") or 0.0,
                            "meter_total": reading.get("meter_total") or 0.0,
                            "controller_timestamp": self._parse_timestamp(
                                reading.get("timestamp")
                            ),
                            "raw_payload": json.dumps(reading),
                        }
                    )
                    to_process |= buffer_row
                    results["accepted"].append(
                        {
                            "index": index,
                            "transaction_ref": transaction_ref,
                            "buffer_id": buffer_row.id,
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                _logger.error(
                    "Forecourt reading rejected (device=%s, ref=%s): %s",
                    device.name,
                    transaction_ref,
                    exc,
                    exc_info=True,
                )
                results["errors"].append({"index": index, "message": str(exc)})

        if to_process:
            to_process.process()
            for item in results["accepted"]:
                row = to_process.browse(item["buffer_id"])
                item["state"] = row.state
                if row.state == "error":
                    item["error"] = row.error_message

        return self._json_response({"result": results})
