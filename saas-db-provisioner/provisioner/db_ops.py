"""Privileged operations: create/drop Postgres databases, run odoo-bin,
and bootstrap the admin user on a freshly initialized tenant database.

Every function here is a thin, testable wrapper around one external
side effect (SQL statement, subprocess, XML-RPC call) so the polling
loop in ``main.py`` can be tested without touching real infrastructure.
"""
import logging
import subprocess
import xmlrpc.client
from dataclasses import dataclass
from typing import List, Optional

import psycopg2
import psycopg2.extensions

from .config import OdooBinConfig, PostgresConfig

_logger = logging.getLogger(__name__)


class ProvisionError(Exception):
    """Raised for any failure during database provisioning."""


def _pg_admin_connection(pg: PostgresConfig):
    conn = psycopg2.connect(
        host=pg.host,
        port=pg.port,
        user=pg.admin_user,
        password=pg.admin_password,
        dbname="postgres",
    )
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def database_exists(pg: PostgresConfig, db_name: str) -> bool:
    with _pg_admin_connection(pg) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            return cur.fetchone() is not None


def create_database(pg: PostgresConfig, db_name: str) -> None:
    """Physically create the Postgres database for a dedicated tenant.

    Uses a Postgres identifier (not a query parameter) for the DB name,
    so it MUST already be validated as subdomain-safe upstream (Odoo's
    ``nexus.saas.tenant.code`` regex already enforces this).
    """
    if database_exists(pg, db_name):
        raise ProvisionError(f"Database '{db_name}' already exists.")

    template_clause = f' TEMPLATE "{pg.template_db}"' if pg.template_db else ""
    with _pg_admin_connection(pg) as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{db_name}"{template_clause}')
    _logger.info("Created database '%s'%s", db_name, f" from template '{pg.template_db}'" if pg.template_db else "")


def drop_database(pg: PostgresConfig, db_name: str) -> None:
    if not database_exists(pg, db_name):
        _logger.warning("Database '%s' does not exist, nothing to drop.", db_name)
        return
    with _pg_admin_connection(pg) as conn:
        with conn.cursor() as cur:
            # Terminate any lingering connections before dropping.
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (db_name,),
            )
            cur.execute(f'DROP DATABASE "{db_name}"')
    _logger.info("Dropped database '%s'", db_name)


@dataclass
class InstallResult:
    success: bool
    log: str


def install_modules(odoo_bin: OdooBinConfig, pg: PostgresConfig, db_name: str, modules: List[str]) -> InstallResult:
    """Run `odoo-bin -d <db> -i <modules> --stop-after-init`."""
    module_list = ",".join(modules) if modules else "base"
    cmd = [
        odoo_bin.path,
        "-d", db_name,
        "-i", module_list,
        "--db_host", pg.host,
        "--db_port", str(pg.port),
        "--db_user", pg.admin_user,
        "--db_password", pg.admin_password,
        "--without-demo=all",
        "--stop-after-init",
    ]
    if odoo_bin.addons_path:
        cmd += ["--addons-path", odoo_bin.addons_path]
    cmd += list(odoo_bin.extra_args or [])

    _logger.info("Running: %s", " ".join(c if "password" not in c.lower() else "***" for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return InstallResult(success=proc.returncode == 0, log=log[-20000:])


def bootstrap_admin(
    base_url: str,
    db_name: str,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    timeout: float = 30.0,
) -> None:
    """Log in as the default 'admin' user (created by `-i base`) and set
    the real tenant admin's name/login/email/password via XML-RPC.
    """
    common = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/common")
    # Odoo's `-i base --without-demo=all` creates login 'admin' / password
    # equal to the master password by convention in most bootstrap setups;
    # environments that differ should override this via a custom hook.
    uid = common.authenticate(db_name, "admin", "admin", {})
    if not uid:
        raise ProvisionError(
            f"Could not authenticate as bootstrap admin on '{db_name}' to finish setup."
        )

    models = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/object")
    models.execute_kw(
        db_name, uid, "admin",
        "res.users", "write",
        [[uid], {
            "name": admin_name,
            "login": admin_email,
            "email": admin_email,
            "password": admin_password,
        }],
    )
    _logger.info("Bootstrapped admin user on '%s' as %s", db_name, admin_email)
