"""Tests for the per-user customizable cockpit layout."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCockpitLayout(TransactionCase):

    def test_get_for_user_creates_default_layout(self):
        layout = self.env["nexus.cockpit.layout"].get_for_user(self.env.user)
        data = layout.get_layout()
        self.assertIn("liquidity", data["order"])
        self.assertEqual(data["hidden"], [])

    def test_get_for_user_is_idempotent(self):
        layout1 = self.env["nexus.cockpit.layout"].get_for_user(self.env.user)
        layout2 = self.env["nexus.cockpit.layout"].get_for_user(self.env.user)
        self.assertEqual(layout1.id, layout2.id)

    def test_set_layout_persists_order_and_hidden(self):
        layout = self.env["nexus.cockpit.layout"].get_for_user(self.env.user)
        new_order = ["daily_sales", "liquidity", "gross_margin"]
        result = layout.set_layout(order=new_order, hidden=["anomaly_alerts"])
        self.assertEqual(result["order"], new_order)
        self.assertEqual(result["hidden"], ["anomaly_alerts"])
        # Re-fetch to confirm persistence.
        reloaded = self.env["nexus.cockpit.layout"].get_for_user(self.env.user)
        self.assertEqual(reloaded.get_layout()["order"], new_order)

    def test_unique_layout_per_user_constraint(self):
        from psycopg2 import IntegrityError

        self.env["nexus.cockpit.layout"].create({"user_id": self.env.user.id})
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["nexus.cockpit.layout"].create({"user_id": self.env.user.id})
