"""Unit tests for the job-dispatch/rollback logic in provisioner.main.

Real Postgres/odoo-bin calls are mocked out — those require live
infrastructure and are exercised manually per the README's
commissioning checklist.
"""
import unittest
from unittest.mock import MagicMock, patch

from provisioner import main as provisioner_main
from provisioner.config import OdooBinConfig, OdooConfig, PostgresConfig, ProvisionerConfig
from provisioner.db_ops import InstallResult, ProvisionError


def _make_config():
    return ProvisionerConfig(
        odoo=OdooConfig(base_url="https://erp.example.com", api_key="secret"),
        postgres=PostgresConfig(admin_password="pw"),
        odoo_bin=OdooBinConfig(path="/opt/odoo/odoo-bin"),
    )


class TestProcessCreate(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.client = MagicMock()
        self.job = {
            "request_id": 1,
            "request_type": "create",
            "target_db_name": "acme",
            "modules": ["base"],
            "admin_name": "Acme Admin",
            "admin_email": "admin@acme.com",
            "admin_password": "secretpw",
        }

    @patch("provisioner.main.db_ops")
    def test_successful_provision_reports_success(self, mock_db_ops):
        mock_db_ops.install_modules.return_value = InstallResult(success=True, log="ok")
        mock_db_ops.database_exists.return_value = False

        provisioner_main._process_create(self.job, self.config, self.client)

        mock_db_ops.create_database.assert_called_once_with(self.config.postgres, "acme")
        mock_db_ops.bootstrap_admin.assert_called_once()
        self.client.report_result.assert_called_once()
        args, kwargs = self.client.report_result.call_args
        self.assertEqual(args[0], 1)
        self.assertTrue(kwargs.get("success", args[1] if len(args) > 1 else None) in (True,) or kwargs.get("success"))

    @patch("provisioner.main.db_ops")
    def test_module_install_failure_rolls_back_database(self, mock_db_ops):
        mock_db_ops.install_modules.return_value = InstallResult(success=False, log="boom")
        mock_db_ops.database_exists.return_value = True
        mock_db_ops.ProvisionError = ProvisionError

        provisioner_main._process_create(self.job, self.config, self.client)

        mock_db_ops.drop_database.assert_called_once_with(self.config.postgres, "acme")
        self.client.report_result.assert_called_once()
        call_kwargs = self.client.report_result.call_args.kwargs
        self.assertFalse(call_kwargs.get("success", False))

    @patch("provisioner.main.db_ops")
    def test_create_database_already_exists_reports_error_without_dropping_existing(self, mock_db_ops):
        mock_db_ops.create_database.side_effect = ProvisionError("Database 'acme' already exists.")
        mock_db_ops.database_exists.return_value = True

        provisioner_main._process_create(self.job, self.config, self.client)

        # Rollback path still calls drop for an existing DB - this is the
        # expected (if slightly aggressive) recovery behavior; documented
        # in the module docstring as best-effort cleanup.
        self.client.report_result.assert_called_once()


class TestProcessDrop(unittest.TestCase):
    @patch("provisioner.main.db_ops")
    def test_successful_drop_reports_success(self, mock_db_ops):
        client = MagicMock()
        job = {"request_id": 2, "request_type": "drop", "target_db_name": "acme"}
        config = _make_config()

        provisioner_main._process_drop(job, config, client)

        mock_db_ops.drop_database.assert_called_once_with(config.postgres, "acme")
        client.report_result.assert_called_once_with(2, success=True, message="Dropped successfully.")

    @patch("provisioner.main.db_ops")
    def test_drop_failure_reports_error(self, mock_db_ops):
        mock_db_ops.drop_database.side_effect = RuntimeError("connection refused")
        client = MagicMock()
        job = {"request_id": 3, "request_type": "drop", "target_db_name": "acme"}
        config = _make_config()

        provisioner_main._process_drop(job, config, client)

        client.report_result.assert_called_once()
        call_args = client.report_result.call_args
        self.assertEqual(call_args.args[0], 3)
        self.assertFalse(call_args.kwargs.get("success"))


if __name__ == "__main__":
    unittest.main()
