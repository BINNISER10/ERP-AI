import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class FuelReadingBuffer(models.Model):
    """Landing zone for every raw reading pushed by a Forecourt Controller.

    Every reading is persisted here *before* any business logic runs.
    This gives us:

    * **Resilience to connection drops** — the controller can resend the
      whole backlog once the network is back; already-processed
      transactions are silently skipped (idempotency below).
    * **Idempotency** — ``(device_id, transaction_ref)`` is unique, so a
      retried push never double-counts a fill-up.
    * **Auditability / debugging** — the raw payload and any processing
      error are kept for inspection instead of being lost.
    """

    _name = "fuel.reading.buffer"
    _description = "Fuel Forecourt Reading Buffer"
    _order = "received_at desc"

    device_id = fields.Many2one(
        "fuel.forecourt.device",
        string="Forecourt Controller",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="device_id.company_id",
        store=True,
        readonly=True,
    )
    transaction_ref = fields.Char(
        string="Controller Transaction Ref",
        required=True,
        index=True,
        help="Unique ID assigned by the Forecourt Controller to this "
        "dispensing transaction. Used as the idempotency key.",
    )
    nozzle_address = fields.Char(string="Nozzle Controller Address", required=True)
    nozzle_id = fields.Many2one("fuel.pump.nozzle", string="Matched Nozzle", readonly=True)
    volume = fields.Float(string="Volume (Liters)", digits=(16, 3), required=True)
    amount = fields.Float(string="Amount", digits=(16, 2))
    unit_price = fields.Float(string="Unit Price", digits=(16, 4))
    meter_total = fields.Float(
        string="Cumulative Meter",
        digits=(16, 3),
        help="Running totalizer reported by the nozzle after this "
        "transaction, if available. When absent, the closing meter is "
        "derived from the nozzle's last known reading + volume.",
    )
    controller_timestamp = fields.Datetime(string="Controller Timestamp")
    raw_payload = fields.Text(string="Raw Payload (JSON)")
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("processed", "Processed"),
            ("error", "Error"),
            ("ignored", "Ignored (Unmatched Nozzle)"),
        ],
        string="Status",
        default="pending",
        required=True,
        index=True,
    )
    error_message = fields.Text(string="Error Message", readonly=True)
    shift_log_id = fields.Many2one(
        "fuel.shift.log", string="Generated Shift Log", readonly=True, copy=False
    )
    received_at = fields.Datetime(
        string="Received At", default=fields.Datetime.now, required=True
    )
    processed_at = fields.Datetime(string="Processed At", readonly=True)

    _sql_constraints = [
        (
            "device_transaction_uniq",
            "unique(device_id, transaction_ref)",
            "This transaction has already been received from this controller "
            "(duplicate/retry — ignored safely).",
        ),
    ]

    def process(self):
        """Process pending/error buffer rows into ``fuel.shift.log`` entries.

        Each row is processed in its own savepoint so a single bad
        reading (unmatched nozzle, tank overflow, etc.) never blocks the
        rest of the batch.
        """
        FuelShiftLog = self.env["fuel.shift.log"]
        for reading in self:
            if reading.state == "processed":
                continue
            try:
                with self.env.cr.savepoint():
                    reading._process_one(FuelShiftLog)
            except Exception as exc:  # noqa: BLE001 — isolate per-row failures
                _logger.error(
                    "Fuel reading buffer #%s failed to process: %s",
                    reading.id,
                    exc,
                    exc_info=True,
                )
                reading.write({"state": "error", "error_message": str(exc)})
        return True

    def _process_one(self, FuelShiftLog):
        self.ensure_one()

        nozzle = self.nozzle_id
        if not nozzle:
            nozzle = self.env["fuel.pump.nozzle"].search(
                [("controller_address", "=", self.nozzle_address)], limit=1
            )
            if not nozzle:
                self.write(
                    {
                        "state": "ignored",
                        "error_message": _(
                            "No nozzle configured with controller address '%s'."
                        )
                        % self.nozzle_address,
                    }
                )
                return
            self.nozzle_id = nozzle.id

        opening_meter = nozzle.meter_end
        closing_meter = (
            self.meter_total if self.meter_total else opening_meter + self.volume
        )

        shift_log = FuelShiftLog.create(
            {
                "date": self.controller_timestamp or fields.Datetime.now(),
                "nozzle_id": nozzle.id,
                "source": "forecourt",
                "reading_buffer_id": self.id,
                "opening_meter": opening_meter,
                "closing_meter": closing_meter,
                "user_id": False,
            }
        )
        shift_log.action_confirm()

        self.write(
            {
                "state": "processed",
                "shift_log_id": shift_log.id,
                "processed_at": fields.Datetime.now(),
                "error_message": False,
            }
        )

    @api.model
    def _cron_retry_errors(self):
        """Retry any reading stuck in 'error' state (e.g. nozzle added later)."""
        stuck = self.search([("state", "=", "error")])
        if stuck:
            _logger.info("Retrying %s stuck fuel reading buffer rows.", len(stuck))
            stuck.process()
