"""Main polling loop: fetch pending jobs, execute them, report results."""
import argparse
import logging
import signal
import time

from . import db_ops
from .config import load_config, setup_logging
from .odoo_client import OdooClient

_logger = logging.getLogger(__name__)

_running = True


def _handle_shutdown(signum, frame):
    global _running
    _logger.info("Shutdown signal received, stopping after current job...")
    _running = False


def process_job(job: dict, config, client: OdooClient) -> None:
    request_id = job["request_id"]
    request_type = job["request_type"]
    db_name = job["target_db_name"]

    _logger.info("Processing %s request #%s for database '%s'", request_type, request_id, db_name)

    if request_type == "create":
        _process_create(job, config, client)
    elif request_type == "drop":
        _process_drop(job, config, client)
    else:
        client.report_result(request_id, success=False, message=f"Unknown request_type '{request_type}'")


def _process_create(job: dict, config, client: OdooClient) -> None:
    request_id = job["request_id"]
    db_name = job["target_db_name"]
    modules = job.get("modules") or ["base"]
    full_log = []

    try:
        db_ops.create_database(config.postgres, db_name)
        full_log.append(f"Database '{db_name}' created.")

        result = db_ops.install_modules(config.odoo_bin, config.postgres, db_name, modules)
        full_log.append(result.log)
        if not result.success:
            raise db_ops.ProvisionError("odoo-bin module installation failed; see log.")

        db_ops.bootstrap_admin(
            base_url=config.odoo.base_url,
            db_name=db_name,
            admin_name=job.get("admin_name") or "Administrator",
            admin_email=job.get("admin_email"),
            admin_password=job.get("admin_password"),
            timeout=config.odoo.request_timeout,
        )
        full_log.append(f"Admin bootstrapped as {job.get('admin_email')}.")

        client.report_result(request_id, success=True, message="Provisioned successfully.", log="\n".join(full_log))
        _logger.info("Request #%s completed successfully.", request_id)

    except Exception as exc:  # noqa: BLE001 - report every failure mode, never crash the loop
        _logger.error("Request #%s failed: %s", request_id, exc, exc_info=True)
        full_log.append(f"ERROR: {exc}")
        # Best-effort cleanup so a half-created DB doesn't block a retry.
        try:
            if db_ops.database_exists(config.postgres, db_name):
                db_ops.drop_database(config.postgres, db_name)
                full_log.append(f"Rolled back: dropped partially-created database '{db_name}'.")
        except Exception as cleanup_exc:  # noqa: BLE001
            full_log.append(f"Cleanup also failed: {cleanup_exc}")
        client.report_result(request_id, success=False, message=str(exc), log="\n".join(full_log))


def _process_drop(job: dict, config, client: OdooClient) -> None:
    request_id = job["request_id"]
    db_name = job["target_db_name"]
    try:
        db_ops.drop_database(config.postgres, db_name)
        client.report_result(request_id, success=True, message="Dropped successfully.")
    except Exception as exc:  # noqa: BLE001
        _logger.error("Drop request #%s failed: %s", request_id, exc, exc_info=True)
        client.report_result(request_id, success=False, message=str(exc))


def run(config_path: str) -> None:
    config = load_config(config_path)
    setup_logging(config)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    client = OdooClient(config.odoo)

    _logger.info(
        "Nexus SaaS DB Provisioner starting — polling %s every %ss",
        config.odoo.pending_url,
        config.odoo.poll_interval_seconds,
    )

    while _running:
        jobs = client.fetch_pending_jobs()
        for job in jobs:
            if not _running:
                break
            process_job(job, config, client)

        if _running:
            time.sleep(config.odoo.poll_interval_seconds)

    _logger.info("Nexus SaaS DB Provisioner stopped.")


def cli():
    parser = argparse.ArgumentParser(description="Nexus SaaS DB Provisioner")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config.yaml (default: ./config.yaml)"
    )
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    cli()
