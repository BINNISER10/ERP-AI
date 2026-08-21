"""Load and validate bridge configuration from config.yaml."""
import logging
import os
from dataclasses import dataclass, field
from typing import Dict

import yaml


@dataclass
class OdooConfig:
    base_url: str
    api_key: str
    request_timeout: float = 10.0
    push_interval_seconds: float = 5.0
    batch_size: int = 50

    @property
    def readings_url(self) -> str:
        return self.base_url.rstrip("/") + "/nexus_fuel/forecourt/readings"


@dataclass
class SerialConfig:
    protocol: str = "simulator"
    port: str = "COM3"
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout: float = 1.0


@dataclass
class QueueConfig:
    db_path: str = "./data/forecourt_queue.sqlite3"


@dataclass
class BridgeConfig:
    odoo: OdooConfig
    serial: SerialConfig
    queue: QueueConfig
    nozzle_map: Dict[str, str] = field(default_factory=dict)
    log_level: str = "INFO"
    log_file: str = "./data/bridge.log"


def load_config(path: str) -> BridgeConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file not found: {path}. Copy config.example.yaml to "
            "config.yaml and fill in the real values first."
        )
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    odoo_raw = raw.get("odoo") or {}
    if not odoo_raw.get("base_url") or not odoo_raw.get("api_key"):
        raise ValueError("config.yaml: 'odoo.base_url' and 'odoo.api_key' are required.")

    serial_raw = raw.get("serial") or {}
    queue_raw = raw.get("queue") or {}
    logging_raw = raw.get("logging") or {}

    return BridgeConfig(
        odoo=OdooConfig(
            base_url=odoo_raw["base_url"],
            api_key=odoo_raw["api_key"],
            request_timeout=float(odoo_raw.get("request_timeout", 10)),
            push_interval_seconds=float(odoo_raw.get("push_interval_seconds", 5)),
            batch_size=int(odoo_raw.get("batch_size", 50)),
        ),
        serial=SerialConfig(
            protocol=serial_raw.get("protocol", "simulator"),
            port=serial_raw.get("port", "COM3"),
            baudrate=int(serial_raw.get("baudrate", 9600)),
            bytesize=int(serial_raw.get("bytesize", 8)),
            parity=serial_raw.get("parity", "N"),
            stopbits=int(serial_raw.get("stopbits", 1)),
            timeout=float(serial_raw.get("timeout", 1.0)),
        ),
        queue=QueueConfig(db_path=queue_raw.get("db_path", "./data/forecourt_queue.sqlite3")),
        nozzle_map=raw.get("nozzle_map") or {},
        log_level=logging_raw.get("level", "INFO"),
        log_file=logging_raw.get("file", "./data/bridge.log"),
    )


def setup_logging(config: BridgeConfig) -> None:
    os.makedirs(os.path.dirname(config.log_file) or ".", exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.log_file, encoding="utf-8"),
        ],
    )
