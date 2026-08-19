# -*- coding: utf-8 -*-
"""Nexus IoT Shop-Floor Bridge — ربط المكائن وخط الإنتاج بالإنترنت الأشياء.

Architecture (kept intentionally simple and standard, no custom protocol):

    Machine / PLC ──(OPC-UA / Modbus, vendor-specific)──► Edge Gateway
        Edge Gateway ──(MQTT publish)──► Mosquitto broker (see docker-compose.yml)
            iot_bridge service (see /iot_bridge) ──(HTTPS POST, shared-secret)──►
                this controller ──► mrp.workcenter (this file)

Odoo never talks to a machine or PLC directly — it only receives normalized
telemetry JSON over HTTP from the bridge service. This keeps Odoo isolated
from the shop floor network and lets any MQTT-capable gateway (Node-RED,
Ignition, a Raspberry Pi script, vendor PLC gateways, ...) plug in without
any Odoo-side changes.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

IOT_STATUS = [
    ("offline", "غير متصل / Offline"),
    ("idle", "خامل / Idle"),
    ("running", "يعمل / Running"),
    ("alarm", "إنذار / عطل (Alarm)"),
]

# If no heartbeat is received within this many minutes, the workcenter is
# considered offline (dead-man's switch) even if no explicit "offline"
# telemetry was ever sent (e.g. gateway crashed, network cut).
OFFLINE_THRESHOLD_MINUTES = 5


class MrpWorkcenterIot(models.Model):
    _inherit = "mrp.workcenter"

    iot_enabled = fields.Boolean(
        string="مراقبة IoT مفعّلة",
        help="Enable live machine monitoring for this work center.",
    )
    iot_device_id = fields.Char(
        string="معرّف جهاز IoT",
        copy=False,
        help="Unique device/topic key used by the MQTT gateway for this "
        "machine, e.g. 'line1-cnc-03'. Must match the device_id sent in "
        "telemetry payloads.",
    )
    iot_status = fields.Selection(
        selection=IOT_STATUS,
        string="حالة الماكينة (IoT)",
        default="offline",
        readonly=True,
        copy=False,
        tracking=True,
    )
    iot_last_heartbeat = fields.Datetime(
        string="آخر نبضة اتصال",
        readonly=True,
        copy=False,
    )
    iot_output_count_today = fields.Integer(
        string="الإنتاج اليوم (وحدات)",
        readonly=True,
        copy=False,
    )
    iot_last_alarm_message = fields.Char(
        string="آخر رسالة إنذار",
        readonly=True,
        copy=False,
    )

    _sql_constraints = [
        (
            "iot_device_id_uniq",
            "unique(iot_device_id)",
            "Each IoT device ID must be linked to only one work center.",
        ),
    ]

    def _apply_iot_telemetry(self, status, output_count=None, alarm_message=None):
        """Apply a single telemetry reading coming from the bridge service."""
        self.ensure_one()
        vals = {
            "iot_last_heartbeat": fields.Datetime.now(),
        }
        if status in dict(IOT_STATUS):
            vals["iot_status"] = status
        if output_count is not None:
            try:
                vals["iot_output_count_today"] = int(output_count)
            except (TypeError, ValueError):
                pass
        if alarm_message:
            vals["iot_last_alarm_message"] = alarm_message

        self.write(vals)

        if vals.get("iot_status") == "alarm":
            self._notify_iot_alarm(alarm_message)

        # If a workorder is currently in progress on this work center, and
        # the machine reports an output count, keep the operator-facing
        # progress in sync automatically instead of relying on manual entry.
        if output_count is not None:
            active_workorder = self.env["mrp.workorder"].sudo().search(
                [
                    ("workcenter_id", "=", self.id),
                    ("state", "=", "progress"),
                ],
                limit=1,
            )
            if active_workorder and hasattr(active_workorder, "qty_produced"):
                try:
                    active_workorder.qty_produced = float(output_count)
                except Exception:
                    _logger.exception(
                        "Nexus IoT: failed to sync qty_produced for workorder #%s",
                        active_workorder.id,
                    )

    def _notify_iot_alarm(self, message):
        self.ensure_one()
        self.env["copilot.insight"].sudo().create(
            {
                "name": _("إنذار ماكينة: %s") % self.name,
                "persona": "coo",
                "insight_text": message or _("تم رصد إنذار في الماكينة دون تفاصيل إضافية."),
                "warm_message": _(
                    "الماكينة \"%s\" على خط الإنتاج أبلغت عن حالة إنذار/عطل. "
                    "يُنصح بالتحقق فوراً لتفادي توقف الإنتاج."
                )
                % self.name,
                "source": "iot_alarm",
            }
        )

    @api.model
    def _cron_flag_offline_machines(self):
        """Dead-man's switch: mark IoT-enabled machines offline if no
        heartbeat has been received recently. Runs every few minutes.
        """
        threshold = fields.Datetime.now() - timedelta(minutes=OFFLINE_THRESHOLD_MINUTES)
        stale = self.search(
            [
                ("iot_enabled", "=", True),
                ("iot_status", "!=", "offline"),
                "|",
                ("iot_last_heartbeat", "=", False),
                ("iot_last_heartbeat", "<", threshold),
            ]
        )
        if stale:
            _logger.warning(
                "Nexus IoT: marking %d work center(s) offline (no heartbeat in %d min): %s",
                len(stale),
                OFFLINE_THRESHOLD_MINUTES,
                ", ".join(stale.mapped("name")),
            )
            stale.write({"iot_status": "offline"})
