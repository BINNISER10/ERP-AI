"""Tests for the hybrid-ledger sync write/unlink guard on account.move."""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged("post_install", "-at_install")
class TestAccountMoveOverride(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Sync Test Partner"})
        cls.move = cls.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": cls.partner.id,
        })
        # Mark the move as synced using the superuser bypass context so the
        # guard itself is not involved in this setup step.
        cls.move.with_context(force_erpnext_write=True).write({
            "erpnext_synced": True,
            "erpnext_docname": "SINV-0001",
        })

        billing_group = cls.env.ref("account.group_account_invoice", raise_if_not_found=False)
        cls.regular_user = cls.env["res.users"].create({
            "name": "Regular Accountant",
            "login": "regular_accountant_test",
            "email": "regular_accountant_test@example.com",
            "groups_id": [(6, 0, [billing_group.id])] if billing_group else [],
        })

    def test_protected_field_write_is_blocked(self):
        """Editing accounting content of a synced move must raise UserError."""
        move = self.move.with_user(self.regular_user)
        with self.assertRaises(UserError):
            move.write({"ref": "Manual edit attempt"})

    def test_internal_bookkeeping_write_is_allowed(self):
        """Fields outside the protected set (e.g. payment_state) must not be blocked."""
        move = self.move.with_user(self.regular_user)
        move.write({"payment_state": "paid"})
        self.assertEqual(move.payment_state, "paid")

    def test_unlink_is_blocked(self):
        """Deleting a synced move must raise UserError."""
        move = self.move.with_user(self.regular_user)
        with self.assertRaises(UserError):
            move.unlink()

    def test_force_context_bypasses_guard_for_superuser(self):
        """The sync process can still update protected fields via the explicit bypass."""
        self.move.with_context(force_erpnext_write=True).write({"ref": "Sync update"})
        self.assertEqual(self.move.ref, "Sync update")

    def test_unsynced_move_is_not_protected(self):
        """Moves that were never synced remain freely editable."""
        other = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
        })
        other.with_user(self.regular_user).write({"ref": "Free edit"})
        self.assertEqual(other.ref, "Free edit")
