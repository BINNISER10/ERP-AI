"""Unit tests for Cloudflare DNS integration helpers."""
from unittest.mock import patch, MagicMock

from odoo.tests import TransactionCase
from odoo.exceptions import UserError


class TestCloudflareDns(TransactionCase):

    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()
        self.icp.set_param("nexus_saas.cloudflare_api_token", "test-token")
        self.icp.set_param("nexus_saas.base_domain", "nexus-engine.app")
        self.icp.set_param("nexus_saas.cloudflare_cname_target", "app.nexus-engine.app")
        self.icp.set_param("nexus_saas.cloudflare_zone_id", "zone-123")

    @patch("requests.request")
    def test_provision_subdomain_creates_record(self, mock_request):
        mock_request.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "success": True,
                "result": {"id": "rec-123", "name": "acme.nexus-engine.app"},
            },
        )

        result = self.env["nexus.saas.cloudflare.dns"].sudo().provision_tenant_subdomain("acme")
        self.assertEqual(result["id"], "rec-123")
        self.assertTrue(mock_request.called)
        call_args = mock_request.call_args
        self.assertEqual(call_args.args[0], "POST")

    @patch("requests.request")
    def test_missing_token_raises(self, mock_request):
        self.icp.set_param("nexus_saas.cloudflare_api_token", "")
        with self.assertRaises(UserError):
            self.env["nexus.saas.cloudflare.dns"].sudo().provision_tenant_subdomain("acme")

    def test_invalid_record_name(self):
        with self.assertRaises(UserError):
            self.env["nexus.saas.cloudflare.dns"].sudo().create_or_update_record(
                "_bad_.domain", "CNAME", "target.example.com"
            )
