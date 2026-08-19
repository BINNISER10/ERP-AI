# -*- coding: utf-8 -*-
"""Nexus Core Sync Queue — asynchronous outbound API bridge.

Every call to the Nexus Core backend is queued here first; nothing goes
out synchronously during a user transaction.  A cron worker drains the
queue with retry/backoff, and each record carries a unique
``transaction_id`` so the Nexus Core can deduplicate idempotently.
"""

import json
import logging
import random
import re
import uuid
from datetime import timedelta
from urllib.parse import urlparse

import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PendingDependency(Exception):
    """Payload depends on a resource not yet synced to the Nexus Core.

    The queue processor catches this and reschedules instead of failing.
    """

    def __init__(self, missing_refs):
        self.missing_refs = missing_refs
        super().__init__(
            _("Nexus Core: waiting for dependency sync — %s") % ", ".join(missing_refs)
        )


class NexusSyncQueue(models.Model):
    _name = "nexus.sync.queue"
    _description = "Nexus Core Sync Queue"
    _order = "priority asc, id asc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Description",
        required=True,
        tracking=True,
    )
    transaction_id = fields.Char(
        string="Transaction ID",
        required=True,
        readonly=True,
        index=True,
        copy=False,
        help="Unique idempotency token passed to the Nexus Core to avoid duplicate writes.",
    )
    operation = fields.Char(
        string="Operation",
        required=True,
        index=True,
        help="Internal operation verb, e.g. 'invoice.create', 'payment.sync'.",
    )
    http_method = fields.Selection(
        [
            ("POST", "POST"),
            ("PUT", "PUT"),
            ("GET", "GET"),
            ("DELETE", "DELETE"),
        ],
        string="HTTP Method",
        default="POST",
        required=True,
    )
    endpoint = fields.Char(
        string="Nexus Core Endpoint",
        required=True,
        help="REST/RPC endpoint relative to the Nexus Core base URL, e.g. '/api/resource/Sales Invoice'.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    priority = fields.Integer(
        string="Priority",
        default=50,
        index=True,
        help="Lower numbers are processed first. Use 10 for masters, 50 for transactions.",
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="State",
        default="pending",
        required=True,
        index=True,
        tracking=True,
    )
    payload = fields.Text(
        string="Outbound Payload (JSON)",
        help="The serialized JSON sent to the Nexus Core endpoint.",
    )
    response = fields.Text(
        string="Nexus Core Response",
        readonly=True,
        help="Raw response body received from the Nexus Core.",
    )
    docname = fields.Char(
        string="Nexus Core Docname",
        readonly=True,
        index=True,
        help="Primary key / name assigned to the created document in the Nexus Core.",
    )
    retry_count = fields.Integer(
        string="Retry Count",
        default=0,
        readonly=True,
    )
    max_retries = fields.Integer(
        string="Max Retries",
        default=5,
        required=True,
    )
    reschedule_count = fields.Integer(
        string="Reschedule Count",
        default=0,
        readonly=True,
    )
    next_attempt = fields.Datetime(
        string="Next Attempt",
        default=fields.Datetime.now,
        index=True,
        help="Timestamp after which the cron worker may pick up this record.",
    )
    last_attempt = fields.Datetime(
        string="Last Attempt",
        readonly=True,
    )
    done_date = fields.Datetime(
        string="Completed At",
        readonly=True,
    )
    last_error = fields.Text(
        string="Last Error Message",
        readonly=True,
    )
    model_name = fields.Char(
        string="Source Model",
        help="Technical model name of the Odoo source record (e.g. 'account.move').",
    )
    res_id = fields.Integer(
        string="Source Record ID",
        help="Database ID of the Odoo source record.",
    )

    _sql_constraints = [
        (
            "transaction_id_uniq",
            "unique(transaction_id)",
            "Nexus Core: the transaction_id must be globally unique to guarantee idempotency.",
        ),
    ]

    # ------------------------------------------------------------------
    # Factory: enqueue helper
    # ------------------------------------------------------------------

    @api.model
    def enqueue(
        self,
        operation,
        payload,
        endpoint,
        company,
        model_name=None,
        res_id=None,
        transaction_id=None,
        priority=50,
        http_method="POST",
    ):
        """Place an outbound sync operation on the queue."""
        if not transaction_id:
            transaction_id = f"NX-{uuid.uuid4().hex}"

        existing = self.search([("transaction_id", "=", transaction_id)], limit=1)
        if existing:
            _logger.info(
                "Nexus Core: duplicate enqueue ignored for tx %s (state=%s)",
                transaction_id,
                existing.state,
            )
            return existing

        payload_str = (
            json.dumps(payload, indent=2, default=str)
            if isinstance(payload, (dict, list))
            else (payload or "{}")
        )

        record = self.create(
            {
                "name": f"{operation} [{model_name} #{res_id}]" if model_name else operation,
                "transaction_id": transaction_id,
                "operation": operation,
                "http_method": http_method,
                "endpoint": endpoint,
                "company_id": company.id if hasattr(company, "id") else company,
                "priority": priority,
                "payload": payload_str,
                "model_name": model_name,
                "res_id": res_id,
                "state": "pending",
                "next_attempt": fields.Datetime.now(),
            }
        )
        _logger.info(
            "Nexus Core: queued operation '%s' [%s] → %s",
            operation,
            transaction_id[:12],
            endpoint,
        )
        return record

    # ------------------------------------------------------------------
    # Queue processing (called by cron)
    # ------------------------------------------------------------------

    @api.model
    def process_queue(self, batch_size=20):
        """Process pending queue records with auto-reclamation of stale processing records."""
        # 1. Stale processing reaper: reclaim records stuck for > 10 minutes
        stale_threshold = fields.Datetime.now() - timedelta(minutes=10)
        stale_records = self.search([
            ("state", "=", "processing"),
            ("last_attempt", "<=", stale_threshold),
        ])
        if stale_records:
            _logger.warning("Nexus Core: reclaiming %d stale processing records", len(stale_records))
            stale_records.write({
                "state": "pending",
                "last_error": "Reclaimed from stuck processing worker.",
                "next_attempt": fields.Datetime.now(),
            })
            self.env.cr.commit()

        # 2. Find due pending records
        due = self.search(
            [
                ("state", "=", "pending"),
                ("next_attempt", "<=", fields.Datetime.now()),
            ],
            limit=batch_size,
            order="priority asc, id asc",
        )
        if not due:
            return

        to_process = due
        chunk = 5
        for i in range(0, len(to_process), chunk):
            group = to_process[i : i + chunk]
            for record in group:
                try:
                    with self.env.cr.savepoint():
                        self._process_single(record)
                except Exception:
                    _logger.exception(
                        "Nexus Core: unhandled processing error on queue #%s",
                        record.id,
                    )
                    record._mark_failed("Unhandled processing exception — see server logs.")
            self.env.cr.commit()

        _logger.info("Nexus Core: processed batch of %d queue records", len(to_process))

    def _process_single(self, record):
        """Attempt to dispatch one queue record to the Nexus Core."""
        self.ensure_one()

        if record.retry_count >= record.max_retries:
            record._mark_failed("Max retries exceeded.")
            return

        record.state = "processing"
        record.last_attempt = fields.Datetime.now()

        config = self.env["hybrid.config"].sudo().get_active_config(record.company_id)
        if not config or not config.erpnext_url:
            record._mark_failed("Nexus Core: no active hybrid configuration found.")
            return

        # Build fresh payload
        try:
            payload_dict = record._prepare_operation()
        except PendingDependency:
            record._reschedule("Waiting for dependent sync to complete.")
            return
        except Exception as exc:
            if hasattr(exc, "missing_refs"):
                record._reschedule("Waiting for dependent sync to complete.")
                return
            record._mark_failed(str(exc))
            return

        record.payload = json.dumps(payload_dict, indent=2, default=str)

        # Make the HTTP call
        try:
            resp_text, docname = record._call_api(config, payload_dict)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 500
            if 400 <= status < 500 and status != 429:
                # Permanent client error (bad payload/404/401) -> fail fast
                record._mark_failed(f"HTTP {status} Client Error: {exc}")
            else:
                # Transient 5xx or rate limit -> retry
                record._retry(f"HTTP {status} Server Error: {exc}")
            return
        except Exception as exc:
            record._retry(str(exc))
            return

        # Success
        record._on_success(resp_text, docname)

    def _call_api(self, config, payload_dict):
        """Execute the HTTP request with SSRF protection and return (response_text, docname)."""
        self.ensure_one()

        base_url = (config.erpnext_url or "").strip().rstrip("/")
        parsed = urlparse(base_url)

        # SSRF Protection: validate scheme and block metadata IP
        if parsed.scheme not in ("http", "https"):
            raise UserError("Invalid URL scheme in configuration. Only HTTP/HTTPS allowed.")
        hostname = (parsed.hostname or "").lower()
        if hostname in ("169.254.169.254", "metadata.google.internal") or hostname.startswith("169.254."):
            raise UserError("Access to internal cloud metadata service is strictly blocked.")

        url = f"{base_url}/{self.endpoint.lstrip('/')}"
        headers = {"Content-Type": "application/json"}
        if config.erpnext_api_key and config.erpnext_api_secret:
            headers["Authorization"] = f"token {config.erpnext_api_key}:{config.erpnext_api_secret}"

        _logger.info("Nexus Core: %s %s [tx %s]", self.http_method, url, self.transaction_id[:12])
        response = requests.request(
            self.http_method,
            url,
            json=payload_dict,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        resp_json = response.json()
        data = resp_json.get("data", resp_json)
        docname = data.get("name") if isinstance(data, dict) else None

        _logger.info("Nexus Core: success — %s → %s", self.transaction_id[:12], docname or "ok")
        return response.text[:2000], docname

    def _on_success(self, resp_text, docname):
        self.ensure_one()
        self.write({
            "state": "done",
            "response": resp_text,
            "docname": docname,
            "done_date": fields.Datetime.now(),
        })
        self.message_post(body=_("Nexus Core sync completed successfully.\nDoc: %(doc)s", doc=docname or "N/A"))

    def _retry(self, error_message):
        """Increment retry counter and schedule next attempt with backoff and jitter."""
        self.ensure_one()
        new_retry = self.retry_count + 1
        # Exponential backoff with jitter
        backoff_seconds = min(60 * (2 ** (new_retry - 1)), 3600) + random.randint(1, 10)
        next_at = fields.Datetime.now() + timedelta(seconds=backoff_seconds)

        self.write({
            "state": "pending",
            "retry_count": new_retry,
            "last_error": error_message[:4000],
            "next_attempt": next_at,
        })
        _logger.warning(
            "Nexus Core: retry %d/%d in %ds for [%s] — %s",
            new_retry,
            self.max_retries,
            backoff_seconds,
            self.transaction_id[:12],
            error_message[:120],
        )

    def _mark_failed(self, error_message):
        self.ensure_one()
        self.write({
            "state": "failed",
            "last_error": error_message[:4000],
            "last_attempt": fields.Datetime.now(),
        })
        _logger.error("Nexus Core: permanently failed [%s] — %s", self.transaction_id[:12], error_message[:200])

    def _reschedule(self, reason=None):
        """Reschedule pending dependency with maximum attempt cap (prevent infinite loop)."""
        self.ensure_one()
        new_reschedule = self.reschedule_count + 1
        if new_reschedule > 10:
            self._mark_failed(f"Maximum dependency reschedule limit reached (10 attempts). Last reason: {reason}")
            return

        next_at = fields.Datetime.now() + timedelta(minutes=2)
        self.write({
            "state": "pending",
            "reschedule_count": new_reschedule,
            "next_attempt": next_at,
            "last_error": reason[:4000] if reason else False,
        })
        _logger.info("Nexus Core: rescheduled (%d/10) [%s] — %s", new_reschedule, self.transaction_id[:12], reason or "unknown reason")

    def action_retry(self):
        for record in self:
            record.write({"state": "pending", "next_attempt": fields.Datetime.now(), "last_error": False})

    def action_cancel(self):
        for record in self:
            record.write({"state": "cancelled"})

    def action_process_now(self):
        for record in self:
            with self.env.cr.savepoint():
                record._process_single(record)

    @api.model
    def _cron_drain(self):
        """Cron entry point: process up to 50 pending records per run."""
        pending = self.search([
            ("state", "=", "pending"),
            "|",
            ("next_attempt", "=", False),
            ("next_attempt", "<=", fields.Datetime.now()),
        ], order="priority asc, id asc", limit=50)
        processed = 0
        for record in pending:
            try:
                with self.env.cr.savepoint():
                    if record._process_single(record):
                        processed += 1
            except Exception as exc:  # pragma: no cover
                _logger.warning("Cron drain: uncaught exception: %s", exc)
        return processed
