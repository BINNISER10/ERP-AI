"""Protocol adapter interface.

Every RS-485 field protocol (Lanfeng, IFSF, vendor-specific, ...) plugs
in behind this single interface so the rest of the bridge (queueing,
upload, retry) never needs to know which physical protocol is in use.
"""
import abc
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional


@dataclass
class Reading:
    """One completed dispensing transaction, protocol-agnostic."""

    transaction_ref: str
    nozzle_address: str
    volume: float
    amount: Optional[float] = None
    unit_price: Optional[float] = None
    meter_total: Optional[float] = None
    timestamp: Optional[datetime] = None

    def to_payload(self) -> dict:
        payload = {
            "transaction_ref": self.transaction_ref,
            "nozzle_address": self.nozzle_address,
            "volume": self.volume,
        }
        if self.amount is not None:
            payload["amount"] = self.amount
        if self.unit_price is not None:
            payload["unit_price"] = self.unit_price
        if self.meter_total is not None:
            payload["meter_total"] = self.meter_total
        if self.timestamp is not None:
            payload["timestamp"] = self.timestamp.isoformat()
        return payload


class ProtocolAdapter(abc.ABC):
    """Base class every field-protocol adapter must implement."""

    def __init__(self, serial_config):
        self.serial_config = serial_config

    @abc.abstractmethod
    def connect(self) -> None:
        """Open the serial port / establish the physical link."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Close the serial port cleanly."""

    @abc.abstractmethod
    def poll(self) -> Iterator[Reading]:
        """Yield any newly completed transactions since the last call.

        Must be non-blocking-ish (bounded by ``serial_config.timeout``)
        so the main loop can also service the upload queue.
        """

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()
