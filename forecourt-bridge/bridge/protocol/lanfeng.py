"""Lanfeng RS-485 protocol adapter.

STATUS: skeleton only. Per the Ocean Seven fuel-automation technical
study (Section 13 — "خطة التنفيذ على مراحل"), Phase 1 requires a field
capture session — connecting one pump to a test PC via a USB<->RS-485
converter and recording the raw byte stream for pump number, fuel type,
volume, and amount — before the exact frame format can be implemented
here. The main board on-site is labeled ``LD23110446``; its connector
type must be confirmed on-site as well.

Once the byte-level protocol is confirmed, implement:

  1. ``connect()``  — open ``serial.Serial(...)`` with the configured
     port/baudrate/parity from ``serial_config``.
  2. ``poll()``     — read available bytes, frame them (start/end
     markers or fixed-length records depending on what Phase 1 finds),
     parse pump/nozzle address + fuel type + volume + amount, and
     ``yield`` one ``Reading`` per completed transaction frame.
  3. Deduplicate re-transmitted frames using whatever sequence/CRC field
     the protocol provides, mapped into ``Reading.transaction_ref``
     (fall back to a hash of the frame bytes if no explicit ID exists).

This file intentionally raises ``NotImplementedError`` until that work
is done, so the bridge fails loudly instead of silently sending bad
data to Odoo.
"""
import logging
from typing import Iterator, Optional

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover - optional at simulator-only install
    serial = None

from .base import ProtocolAdapter, Reading

_logger = logging.getLogger(__name__)


class LanfengAdapter(ProtocolAdapter):
    def __init__(self, serial_config):
        super().__init__(serial_config)
        self._conn: Optional["serial.Serial"] = None

    def connect(self) -> None:
        if serial is None:
            raise RuntimeError(
                "pyserial is not installed. Run: pip install -r requirements.txt"
            )
        self._conn = serial.Serial(
            port=self.serial_config.port,
            baudrate=self.serial_config.baudrate,
            bytesize=self.serial_config.bytesize,
            parity=self.serial_config.parity,
            stopbits=self.serial_config.stopbits,
            timeout=self.serial_config.timeout,
        )
        _logger.info(
            "Lanfeng adapter connected to %s @ %s baud",
            self.serial_config.port,
            self.serial_config.baudrate,
        )

    def disconnect(self) -> None:
        if self._conn and self._conn.is_open:
            self._conn.close()

    def poll(self) -> Iterator[Reading]:
        # TODO(Phase 1 field capture): replace with real frame parsing.
        #
        # raw = self._conn.read(self._conn.in_waiting or 1)
        # for frame in self._frame(raw):
        #     yield self._parse_frame(frame)
        raise NotImplementedError(
            "Lanfeng byte-level protocol not yet captured. Run Phase 1 "
            "field evaluation (see module docstring) and implement "
            "poll()/_parse_frame() before switching serial.protocol to "
            "'lanfeng' in config.yaml. Use protocol: 'simulator' until then."
        )
