"""Dry-run adapter — generates synthetic transactions without hardware.

Useful for end-to-end testing of the queue/upload/Odoo pipeline before
the real Lanfeng RS-485 protocol has been captured and confirmed
(Phase 1 of the technical study).
"""
import logging
import random
import time
import uuid
from datetime import datetime
from typing import Iterator

from .base import ProtocolAdapter, Reading

_logger = logging.getLogger(__name__)

# Default 23-nozzle layout matching the Ocean Seven station
# (11 pumps, 14x Gasoline91 / 6x Diesel / 3x Gasoline95).
_DEFAULT_NOZZLES = [f"P{p:02d}-N{n:02d}" for p in range(1, 12) for n in range(1, 3)][:23]


class SimulatorAdapter(ProtocolAdapter):
    def __init__(self, serial_config):
        super().__init__(serial_config)
        self._last_emit = 0.0

    def connect(self) -> None:
        _logger.warning(
            "SimulatorAdapter active — NOT reading real hardware. "
            "Switch 'serial.protocol' to 'lanfeng' for production."
        )

    def disconnect(self) -> None:
        pass

    def poll(self) -> Iterator[Reading]:
        now = time.monotonic()
        if now - self._last_emit < 3.0:
            time.sleep(self.serial_config.timeout)
            return
        self._last_emit = now

        if random.random() < 0.6:
            nozzle = random.choice(_DEFAULT_NOZZLES)
            volume = round(random.uniform(5.0, 60.0), 3)
            unit_price = round(random.uniform(2.0, 4.5), 2)
            yield Reading(
                transaction_ref=str(uuid.uuid4()),
                nozzle_address=nozzle,
                volume=volume,
                amount=round(volume * unit_price, 2),
                unit_price=unit_price,
                timestamp=datetime.utcnow(),
            )
