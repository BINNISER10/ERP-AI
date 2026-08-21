"""Main run loop: read from the field protocol, enqueue durably, push to Odoo."""
import argparse
import logging
import signal
import sys
import time

from .config import load_config, setup_logging
from .protocol import get_adapter
from .queue_store import QueueStore
from .uploader import Uploader

_logger = logging.getLogger(__name__)

_running = True


def _handle_shutdown(signum, frame):
    global _running
    _logger.info("Shutdown signal received, stopping after current cycle...")
    _running = False


def run(config_path: str) -> None:
    config = load_config(config_path)
    setup_logging(config)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    queue = QueueStore(config.queue.db_path)
    uploader = Uploader(config.odoo)
    adapter = get_adapter(config.serial.protocol, config.serial)

    nozzle_map = config.nozzle_map or {}

    _logger.info(
        "Nexus Forecourt Bridge starting — protocol=%s, odoo=%s, pending_in_queue=%s",
        config.serial.protocol,
        config.odoo.readings_url,
        queue.pending_count(),
    )

    last_push = 0.0

    with adapter:
        while _running:
            try:
                for reading in adapter.poll():
                    mapped_address = nozzle_map.get(
                        reading.nozzle_address, reading.nozzle_address
                    )
                    reading.nozzle_address = mapped_address
                    queue.enqueue(reading.to_payload())
                    _logger.info(
                        "Captured transaction %s on %s: %.3f L",
                        reading.transaction_ref,
                        reading.nozzle_address,
                        reading.volume,
                    )
            except NotImplementedError as exc:
                _logger.error(str(exc))
                sys.exit(1)
            except Exception as exc:  # noqa: BLE001 - never let the field loop die
                _logger.error("Protocol adapter error: %s", exc, exc_info=True)
                time.sleep(1.0)

            now = time.monotonic()
            if now - last_push >= config.odoo.push_interval_seconds:
                last_push = now
                batch = queue.peek_batch(config.odoo.batch_size)
                if batch:
                    row_ids = [item["_row_id"] for item in batch]
                    queue.mark_attempt(row_ids)
                    safe_to_delete = uploader.push(batch)
                    queue.mark_sent(safe_to_delete)
                    remaining = queue.pending_count()
                    if remaining:
                        _logger.info("%s readings still pending in local queue.", remaining)

    queue.close()
    _logger.info("Nexus Forecourt Bridge stopped.")


def cli():
    parser = argparse.ArgumentParser(description="Nexus Forecourt Bridge")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config.yaml (default: ./config.yaml)"
    )
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    cli()
