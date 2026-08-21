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

    def test_product_quota_enforced_on_create(self):
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="ProdQuota",
            code="prodquota",
            email="admin@prodquota.com",
            plan_id=self.plan.id,
        )
        self.plan.write({"max_products": 1})
        self.env["product.template"].create({
            "name": "Product 1",
            "company_id": tenant.primary_company_id.id,
        })
        with self.assertRaises(UserError):
            self.env["product.template"].create({
                "name": "Product 2",
                "company_id": tenant.primary_company_id.id,
            })

    def test_product_quota_ignores_products_without_company(self):
        # Products shared across all companies (company_id=False) are not
        # attributable to a single tenant and must not be blocked.
        self.env["product.template"].create({"name": "Shared Product"})

    def test_company_quota_enforced_on_create(self):
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="CompanyQuota",
            code="companyquota",
            email="admin@companyquota.com",
            plan_id=self.plan.id,
        )
        # max_companies=1 on the shared test plan; primary company already
        # counts as 1, so attaching a second company must be blocked.
        with self.assertRaises(UserError):
            self.env["res.company"].create({
                "name": "Second Company",
                "saas_tenant_id": tenant.id,
            })

    def test_invoice_quota_enforced_on_post(self):
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="InvoiceQuota",
            code="invoicequota",
            email="admin@invoicequota.com",
            plan_id=self.plan.id,
        )
        self.plan.write({"max_invoices_monthly": 1})
        partner = self.env["res.partner"].create({"name": "Test Customer"})

        def _make_invoice():
            return self.env["account.move"].create({
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "company_id": tenant.primary_company_id.id,
                "invoice_line_ids": [(0, 0, {
                    "name": "Line",
                    "quantity": 1,
                    "price_unit": 100.0,
                })],
            })

        first = _make_invoice()
        first.action_post()

        second = _make_invoice()
        with self.assertRaises(UserError):
            second.action_post()

    def test_quota_check_skipped_with_context_flag(self):
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="SkipQuota",
            code="skipquota",
            email="admin@skipquota.com",
            plan_id=self.plan.id,
        )
        # max_users=2; owner already counts as 1. Create 2 more with the
        # escape hatch context flag — must NOT raise despite exceeding quota.
        for i in range(2, 4):
            self.env["res.users"].with_context(
                no_reset_password=True, skip_saas_quota_check=True
            ).create({
                "name": f"User {i}",
                "login": f"user{i}@skipquota.com",
                "saas_tenant_id": tenant.id,
                "company_id": tenant.primary_company_id.id,
                "company_ids": [(6, 0, [tenant.primary_company_id.id])],
            })

    def test_dedicated_db_blocked_without_plan_flag(self):
        with self.assertRaises(UserError):
            self.env["nexus.saas.tenant"].provision_tenant(
                name="NoDedicated",
                code="nodedicated",
                email="admin@nodedicated.com",
                plan_id=self.plan.id,
                isolation_mode="dedicated_db",
            )

    def test_dedicated_db_provisioning_enqueues_request(self):
        self.plan.write({"allows_dedicated_db": True})
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="Enterprise",
            code="enterprise",
            email="admin@enterprise.com",
            plan_id=self.plan.id,
            isolation_mode="dedicated_db",
        )
        self.assertEqual(tenant.state, "provisioning")
        self.assertEqual(tenant.isolation_mode, "dedicated_db")
        self.assertFalse(tenant.primary_company_id)
        self.assertFalse(tenant.owner_user_id)

        requests = tenant.provision_request_ids
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests.request_type, "create")
        self.assertEqual(requests.target_db_name, "enterprise")
        self.assertEqual(requests.state, "pending")
        self.assertTrue(requests.admin_password)

    def test_dedicated_db_callback_activates_tenant(self):
        self.plan.write({"allows_dedicated_db": True})
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="Enterprise2",
            code="enterprise2",
            email="admin@enterprise2.com",
            plan_id=self.plan.id,
            isolation_mode="dedicated_db",
        )
        request = tenant.provision_request_ids
        tenant._on_dedicated_db_provisioned(request, success=True)
        self.assertEqual(tenant.state, "active")

    def test_dedicated_db_callback_failure_keeps_provisioning(self):
        self.plan.write({"allows_dedicated_db": True})
        tenant = self.env["nexus.saas.tenant"].provision_tenant(
            name="Enterprise3",
            code="enterprise3",
            email="admin@enterprise3.com",
            plan_id=self.plan.id,
            isolation_mode="dedicated_db",
        )
        request = tenant.provision_request_ids
        tenant._on_dedicated_db_provisioned(request, success=False, message="disk full")
        self.assertEqual(tenant.state, "provisioning")

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
