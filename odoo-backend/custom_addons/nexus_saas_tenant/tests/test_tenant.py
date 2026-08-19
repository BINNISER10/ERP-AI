"""Unit tests for the SaaS tenant module."""
from odoo.tests import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestSaaSTenant(TransactionCase):

    def setUp(self):
        super().setUp()
        self.plan = self.env["nexus.saas.plan"].create({
            "name": "Test Plan",
            "code": "test-plan",
            "max_users": 2,
            "max_companies": 1,
            "max_products": 10,
            "max_invoices_monthly": 5,
        })

    def test_tenant_code_validation(self):
        with self.assertRaises(ValidationError):
            self.env["nexus.saas.tenant"].create({
                "name": "Bad Code",
                "code": "Bad Code!",
                "email": "test@example.com",
                "plan_id": self.plan.id,
            })

    def test_provision_tenant(self):
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="Acme",
            code="acme",
            email="admin@acme.com",
            plan_id=self.plan.id,
        )
        self.assertTrue(tenant)
        self.assertEqual(tenant.code, "acme")
        self.assertEqual(tenant.state, "active")
        self.assertTrue(tenant.primary_company_id)
        self.assertTrue(tenant.owner_user_id)
        self.assertEqual(tenant.primary_company_id.saas_tenant_id, tenant)
        self.assertEqual(tenant.owner_user_id.saas_tenant_id, tenant)

    def test_duplicate_code_blocked(self):
        self.env["nexus.saas.tenant"].provision_tenant(
            name="Acme",
            code="acme",
            email="admin@acme.com",
            plan_id=self.plan.id,
        )
        with self.assertRaises(UserError):
            self.env["nexus.saas.tenant"].provision_tenant(
                name="Acme 2",
                code="acme",
                email="other@acme.com",
                plan_id=self.plan.id,
            )

    def test_user_quota(self):
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="Quota",
            code="quota",
            email="admin@quota.com",
            plan_id=self.plan.id,
        )
        # Owner counts as one user. Creating one more should succeed.
        self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "User 2",
            "login": "user2@quota.com",
            "saas_tenant_id": tenant.id,
            "company_id": tenant.primary_company_id.id,
            "company_ids": [(6, 0, [tenant.primary_company_id.id])],
        })
        # Third user should exceed the quota.
        with self.assertRaises(UserError):
            self.env["res.users"].with_context(no_reset_password=True).create({
                "name": "User 3",
                "login": "user3@quota.com",
                "saas_tenant_id": tenant.id,
                "company_id": tenant.primary_company_id.id,
                "company_ids": [(6, 0, [tenant.primary_company_id.id])],
            })

    def test_user_company_tenant_mismatch(self):
        other_tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="Other",
            code="other",
            email="admin@other.com",
            plan_id=self.plan.id,
        )
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="Main",
            code="main",
            email="admin@main.com",
            plan_id=self.plan.id,
        )
        with self.assertRaises(UserError):
            self.env["res.users"].with_context(no_reset_password=True).create({
                "name": "Mismatch",
                "login": "mismatch@main.com",
                "saas_tenant_id": tenant.id,
                "company_id": other_tenant.primary_company_id.id,
                "company_ids": [(6, 0, [other_tenant.primary_company_id.id])],
            })
