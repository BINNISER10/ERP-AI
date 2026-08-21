"""Load and validate provisioner configuration from config.yaml."""
import logging
import os
from dataclasses import dataclass, field
from typing import List

import yaml


@dataclass
class OdooConfig:
    base_url: str
    api_key: str
    poll_interval_seconds: float = 15.0
    request_timeout: float = 30.0

    @property
    def pending_url(self) -> str:
        return self.base_url.rstrip("/") + "/saas/db-provisioner/pending"

    @property
    def callback_url(self) -> str:
        return self.base_url.rstrip("/") + "/saas/db-provisioner/callback"


@dataclass
class PostgresConfig:
    host: str = "localhost"
    port: int = 5432
    admin_user: str = "odoo"
    admin_password: str = ""
    template_db: str = ""


@dataclass
class OdooBinConfig:
    path: str = "/opt/odoo/odoo-bin"
    addons_path: str = ""
    extra_args: List[str] = field(default_factory=list)


@dataclass
class ProvisionerConfig:
    odoo: OdooConfig
    postgres: PostgresConfig
    odoo_bin: OdooBinConfig
    log_level: str = "INFO"
    log_file: str = "./data/provisioner.log"


def load_config(path: str) -> ProvisionerConfig:
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

    pg_raw = raw.get("postgres") or {}
    bin_raw = raw.get("odoo_bin") or {}
    logging_raw = raw.get("logging") or {}

    return ProvisionerConfig(
        odoo=OdooConfig(
            base_url=odoo_raw["base_url"],
            api_key=odoo_raw["api_key"],
            poll_interval_seconds=float(odoo_raw.get("poll_interval_seconds", 15)),
            request_timeout=float(odoo_raw.get("request_timeout", 30)),
        ),
        postgres=PostgresConfig(
            host=pg_raw.get("host", "localhost"),
            port=int(pg_raw.get("port", 5432)),
            admin_user=pg_raw.get("admin_user", "odoo"),
            admin_password=pg_raw.get("admin_password", ""),
            template_db=pg_raw.get("template_db", ""),
        ),
        odoo_bin=OdooBinConfig(
            path=bin_raw.get("path", "/opt/odoo/odoo-bin"),
            addons_path=bin_raw.get("addons_path", ""),
            extra_args=list(bin_raw.get("extra_args") or []),
        ),
        log_level=logging_raw.get("level", "INFO"),
        log_file=logging_raw.get("file", "./data/provisioner.log"),
    )


def setup_logging(config: ProvisionerConfig) -> None:
    os.makedirs(os.path.dirname(config.log_file) or ".", exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.log_file, encoding="utf-8"),
        ],
    )
