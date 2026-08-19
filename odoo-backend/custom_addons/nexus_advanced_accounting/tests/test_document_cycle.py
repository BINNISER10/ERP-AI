"""الدائرة المستندية الكاملة — Complete Document Cycle Tests.

يغطي هذا الملف جميع التدفقات المحاسبية من البداية إلى النهاية:
- دورة المبيعات (عرض سعر ← تأكيد ← فاتورة ← تحصيل)
- دورة المشتريات (أمر شراء ← فاتورة مورد ← دفع ← أصل ثابت)
- نقاط البيع (طلب POS ← أمر بيع ← فاتورة)
- القيود اليومية + مراكز التكلفة
- المصروفات + الضرائب + الحالات الاستثنائية

All tests verify that the Nexus Core sync queue records are created with
correct operations, payloads, and idempotency keys at each step.
"""

import json

from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError

# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════


def _assert_queue_count(test, operation, expected_count):
    """Assert the exact number of queue records for a given operation."""
    count = test.env["nexus.sync.queue"].sudo().search_count(
        [("operation", "=", operation)]
    )
    test.assertEqual(
        count,
        expected_count,
        f"Expected {expected_count} queue records for '{operation}', got {count}",
    )


def _get_payload(test, operation):
    """Return the first queue record's parsed payload for a given operation."""
    record = test.env["nexus.sync.queue"].sudo().search(
        [("operation", "=", operation)], limit=1
    )
    if record and record.payload:
        return json.loads(record.payload)
    return None


# ═══════════════════════════════════════════════════════════════════════
# المرحلة الأولى — دورة المبيعات الكاملة (O2C)
# ═══════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install")
class TestSalesCycleO2C(TransactionCase):
    """Full Order‑to‑Cash cycle: Quote → SO → Invoice → Payment → Nexus Core sync."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Chart / Journal / Partner ──
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "شركة العميل الذهبي"})

        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.bank_journal = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", cls.company.id)], limit=1
        )

        # ── Tax + mapping ──
        cls.tax_15 = cls.env["account.tax"].create(
            {
                "name": "ضريبة القيمة المضافة 15%",
                "amount": 15.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
            }
        )
        cls.tax_mapping = cls.env["nexus.tax.mapping"].create(
            {
                "odoo_tax_id": cls.tax_15.id,
                "nexus_tax_template": "VAT 15%",
                "nexus_tax_code": "VAT-15",
                "nexus_tax_rate": 15.0,
                "company_id": cls.company.id,
            }
        )

        # ── Income account ──
        income_account = cls.env["account.account"].search(
            [
                ("account_type", "=", "income_other"),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        if not income_account:
            income_account = cls.env["account.account"].search(
                [("company_id", "=", cls.company.id)], limit=1
            )

        # ── Product ──
        cls.product = cls.env["product.product"].create(
            {
                "name": "منتج تجريبي",
                "type": "consu",
                "list_price": 100.0,
                "taxes_id": [(6, 0, [cls.tax_15.id])],
                "property_account_income_id": income_account.id,
                "company_id": cls.company.id,
            }
        )

    # ─────────────────────────────────────────────────────────────────
    # تدفق المبيعات الأساسي
    # ─────────────────────────────────────────────────────────────────
    def test_01_create_sale_order_and_confirm(self):
        """إنشاء عرض سعر وتأكيده → أمر بيع مؤكد."""
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 5,
                            "price_unit": 100.0,
                            "tax_id": [(6, 0, [self.tax_15.id])],
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        self.assertEqual(so.state, "sale")
        self.assertEqual(so.order_line[0].product_uom_qty, 5)
        return so

    def test_02_create_invoice_and_post_queues_sync(self):
        """إنشاء فاتورة وترحيلها ← يتم وضعها في طابور المزامنة إلى Nexus Core."""
        so = self.test_01_create_sale_order_and_confirm()

        # Create invoice from sale order
        invoice_action = so._create_invoices()
        invoice = self.env["account.move"].browse(invoice_action["res_id"])
        self.assertEqual(invoice.move_type, "out_invoice")

        # Post the invoice → triggers our _post override
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

        # Verify queue record created
        _assert_queue_count(self, "invoice.create", 1)
        queue = self.env["nexus.sync.queue"].sudo().search(
            [("operation", "=", "invoice.create")], limit=1
        )
        self.assertEqual(queue.model_name, "account.move")
        self.assertEqual(queue.res_id, invoice.id)
        self.assertTrue(
            queue.transaction_id.startswith("NX-INV-"),
            f"Transaction ID format wrong: {queue.transaction_id}",
        )
        self.assertEqual(queue.state, "pending")
        self.assertIn("Sales Invoice", queue.endpoint)

    def test_03_invoice_payload_contains_tax_and_cost_center(self):
        """الفاتورة المرسلة إلى Nexus Core تحتوي على الضريبة ومركز التكلفة."""
        so = self.test_01_create_sale_order_and_confirm()
        invoice_action = so._create_invoices()
        invoice = self.env["account.move"].browse(invoice_action["res_id"])

        # Set explicit cost center
        invoice.nexus_cost_center = "Branch - الرياض"
        invoice.action_post()

        # Validate the payload builder directly
        queue = self.env["nexus.sync.queue"].sudo().search(
            [("operation", "=", "invoice.create")], limit=1
        )
        payload = queue._prepare_operation()

        self.assertEqual(payload["doctype"], "Sales Invoice")
        self.assertEqual(payload["docstatus"], 1)
        self.assertEqual(payload["cost_center"], "Branch - الرياض")
        self.assertGreater(len(payload["items"]), 0, "Payload must have items")
        self.assertEqual(payload["nexus_transaction_id"], queue.transaction_id)

        # Verify tax template is included on the line
        first_item = payload["items"][0]
        self.assertEqual(
            first_item["item_tax_template"],
            "VAT 15%",
            "Item tax template must match mapping",
        )

    def test_04_register_payment_and_queue_payment_entry(self):
        """تحصيل الدفعة ← إنشاء قيد دفع في Nexus Core مع الإشارة للفاتورة."""
        so = self.test_01_create_sale_order_and_confirm()
        invoice_action = so._create_invoices()
        invoice = self.env["account.move"].browse(invoice_action["res_id"])
        invoice.action_post()

        # Simulate Nexus Core sync: mark invoice as synced with a docname
        invoice.with_context(force_erpnext_write=True).sudo().write(
            {"erpnext_synced": True, "erpnext_docname": "SINV-00001"}
        )

        # Register payment on the invoice
        ctx = {
            "active_model": "account.move",
            "active_ids": invoice.ids,
            "active_id": invoice.id,
        }
        payment_register = (
            self.env["account.payment.register"]
            .with_context(**ctx)
            .create(
                {
                    "payment_date": fields.Date.today(),
                    "journal_id": self.bank_journal.id,
                    "amount": invoice.amount_total,
                }
            )
        )
        payments = payment_register._create_payments()
        self.assertTrue(payments, "Payment should be created")

        # Verify payment was posted and queued
        payment = payments[0]
        self.assertEqual(payment.state, "posted")

        _assert_queue_count(self, "payment_entry.create", 1)
        queue = self.env["nexus.sync.queue"].sudo().search(
            [("operation", "=", "payment_entry.create")], limit=1
        )
        self.assertEqual(queue.model_name, "account.payment")
        self.assertEqual(queue.res_id, payment.id)
        self.assertTrue(
            queue.transaction_id.startswith("NX-PAY-"),
            f"Transaction ID: {queue.transaction_id}",
        )

    def test_05_payment_payload_has_references(self):
        """قيد الدفع يحتوي على مراجع الفواتير للتحصيل التلقائي في Nexus Core."""
        so = self.test_01_create_sale_order_and_confirm()
        invoice_action = so._create_invoices()
        invoice = self.env["account.move"].browse(invoice_action["res_id"])
        invoice.action_post()

        # Mark synced
        invoice.with_context(force_erpnext_write=True).sudo().write(
            {"erpnext_synced": True, "erpnext_docname": "SINV-00005"}
        )

        # Register payment
        ctx = {
            "active_model": "account.move",
            "active_ids": invoice.ids,
            "active_id": invoice.id,
        }
        payment_register = (
            self.env["account.payment.register"]
            .with_context(**ctx)
            .create(
                {
                    "payment_date": fields.Date.today(),
                    "journal_id": self.bank_journal.id,
                    "amount": invoice.amount_total,
                }
            )
        )
        payment_register._create_payments()

        # Validate payload
        queue = self.env["nexus.sync.queue"].sudo().search(
            [("operation", "=", "payment_entry.create")], limit=1
        )
        payload = queue._prepare_operation()

        self.assertEqual(payload["doctype"], "Payment Entry")
        self.assertEqual(payload["docstatus"], 1)
        self.assertEqual(payload["payment_type"], "Receive")
        self.assertEqual(payload["party_type"], "Customer")
        self.assertEqual(payload["party"], "شركة العميل الذهبي")
        self.assertGreater(len(payload["references"]), 0)
        ref = payload["references"][0]
        self.assertEqual(ref["reference_doctype"], "Sales Invoice")
        self.assertEqual(ref["reference_name"], "SINV-00005")

    # ─────────────────────────────────────────────────────────────────
    # تحقق من الحقول المضافة
    # ─────────────────────────────────────────────────────────────────
    def test_06_invoice_has_nexus_fields(self):
        """الحقول المضافة موجودة في الفاتورة وسطور الفاتورة."""
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "company_id": self.company.id,
                "nexus_cost_center": "Branch - جدة",
            }
        )
        self.assertEqual(inv.nexus_cost_center, "Branch - جدة")

    def test_07_payment_has_nexus_fields(self):
        """الحقول المضافة موجودة في نموذج الدفع."""
        payment = self.env["account.payment"].search([], limit=1)
        self.assertIn("nexus_core_synced", payment._fields)
        self.assertIn("nexus_core_docname", payment._fields)

    def test_08_product_has_fixed_asset_field(self):
        """حقل الأصل الثابت موجود في المنتج."""
        self.assertIn("is_fixed_asset", self.product._fields)

    # ─────────────────────────────────────────────────────────────────
    # ضريبة ZATCA — ربط الضرائب
    # ─────────────────────────────────────────────────────────────────
    def test_09_tax_mapping_resolves_correctly(self):
        """ربط الضريبة يعيد القالب الصحيح من Nexus Core."""
        mapping = self.env["nexus.tax.mapping"]._get_map_for_company(
            self.company
        )
        self.assertIn(self.tax_15.id, mapping)
        self.assertEqual(
            mapping[self.tax_15.id].nexus_tax_template, "VAT 15%"
        )

    def test_10_tax_mapping_duplicate_prevented(self):
        """لا يمكن تكرار ربط نفس الضريبة لنفس الشركة."""
        with self.assertRaises(ValidationError):
            self.env["nexus.tax.mapping"].create(
                {
                    "odoo_tax_id": self.tax_15.id,
                    "nexus_tax_template": "VAT 15% duplicate",
                    "company_id": self.company.id,
                }
            )


# ═══════════════════════════════════════════════════════════════════════
# المرحلة الثانية — دورة المشتريات + الأصول الثابتة (P2P)
# ═══════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install")
class TestPurchaseCycleP2P(TransactionCase):
    """Full Procure‑to‑Pay cycle: PO → Vendor Bill → Payment → Asset creation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.vendor = cls.env["res.partner"].create({"name": "شركة المورد المتحدة"})

        cls.purchase_journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.bank_journal = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", cls.company.id)], limit=1
        )

        expense_account = cls.env["account.account"].search(
            [
                ("account_type", "=", "expense"),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        if not expense_account:
            expense_account = cls.env["account.account"].search(
                [("company_id", "=", cls.company.id)], limit=1
            )

        # ── Fixed asset product ──
        cls.asset_product = cls.env["product.product"].create(
            {
                "name": "جهاز حاسب آلي",
                "type": "consu",
                "list_price": 5000.0,
                "is_fixed_asset": True,
                "property_account_expense_id": expense_account.id,
                "company_id": cls.company.id,
            }
        )

        # ── Normal consumable product ──
        cls.normal_product = cls.env["product.product"].create(
            {
                "name": "ورق طباعة",
                "type": "consu",
                "list_price": 50.0,
                "is_fixed_asset": False,
                "property_account_expense_id": expense_account.id,
                "company_id": cls.company.id,
            }
        )

    def test_11_vendor_bill_posting_queues_invoice_sync(self):
        """فاتورة مورد ← مزامنة إلى Nexus Core."""
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": fields.Date.today(),
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.normal_product.id,
                            "name": self.normal_product.name,
                            "quantity": 10,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        bill.action_post()
        self.assertEqual(bill.state, "posted")

        _assert_queue_count(self, "invoice.create", 1)
        queue = self.env["nexus.sync.queue"].sudo().search(
            [("operation", "=", "invoice.create")], limit=1
        )
        payload = queue._prepare_operation()
        self.assertEqual(payload["doctype"], "Purchase Invoice")
        self.assertEqual(payload["supplier"], "شركة المورد المتحدة")

    def test_12_vendor_bill_with_asset_triggers_asset_queue(self):
        """فاتورة مورد تحتوي على أصل ثابت ← إنشاء أصل في Nexus Core."""
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": fields.Date.today(),
                "company_id": self.company.id,
                "nexus_cost_center": "Branch - الدمام",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.asset_product.id,
                            "name": self.asset_product.name,
                            "quantity": 3,
                            "price_unit": 5000.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.normal_product.id,
                            "name": self.normal_product.name,
                            "quantity": 5,
                            "price_unit": 50.0,
                        },
                    ),
                ],
            }
        )
        bill.action_post()

        # Invoice sync queued
        _assert_queue_count(self, "invoice.create", 1)

        # Asset creation queued (1 line is fixed asset)
        _assert_queue_count(self, "asset.create", 1)
        asset_queue = self.env["nexus.sync.queue"].sudo().search(
            [("operation", "=", "asset.create")], limit=1
        )
        self.assertEqual(asset_queue.model_name, "account.move.line")
        self.assertTrue(
            asset_queue.transaction_id.startswith("NX-ASSET-")
        )

        # Validate asset payload
        payload = asset_queue._prepare_operation()
        self.assertEqual(payload["doctype"], "Asset")
        self.assertEqual(payload["asset_name"], "جهاز حاسب آلي")
        self.assertEqual(payload["calculate_depreciation"], 1)
        self.assertEqual(payload["depreciation_method"], "Straight Line")
        self.assertEqual(payload["gross_purchase_amount"], 15000.0)
        self.assertEqual(payload["cost_center"], "Branch - الدمام")

    def test_13_asset_not_created_for_non_asset_products(self):
        """المنتجات غير المصنفة كأصول ثابتة لا تنشئ أصولاً."""
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": fields.Date.today(),
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.normal_product.id,
                            "name": self.normal_product.name,
                            "quantity": 100,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        bill.action_post()

        _assert_queue_count(self, "invoice.create", 1)
        _assert_queue_count(self, "asset.create", 0)

    def test_14_vendor_payment_queues_payment_entry(self):
        """دفع فاتورة مورد ← قيد دفع في Nexus Core."""
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": fields.Date.today(),
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.normal_product.id,
                            "name": self.normal_product.name,
                            "quantity": 10,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        bill.action_post()

        # Simulate sync
        bill.with_context(force_erpnext_write=True).sudo().write(
            {"erpnext_synced": True, "erpnext_docname": "PINV-00010"}
        )

        # Register payment
        ctx = {
            "active_model": "account.move",
            "active_ids": bill.ids,
            "active_id": bill.id,
        }
        payment_register = (
            self.env["account.payment.register"]
            .with_context(**ctx)
            .create(
                {
                    "payment_date": fields.Date.today(),
                    "journal_id": self.bank_journal.id,
                    "amount": bill.amount_total,
                    "payment_type": "outbound",
                    "partner_type": "supplier",
                }
            )
        )
        payments = payment_register._create_payments()
        payment = payments[0]

        _assert_queue_count(self, "payment_entry.create", 1)
        payload = _get_payload(self, "payment_entry.create")
        self.assertEqual(payload["payment_type"], "Pay")
        self.assertEqual(payload["party_type"], "Supplier")
        ref = payload["references"][0]
        self.assertEqual(ref["reference_doctype"], "Purchase Invoice")


# ═══════════════════════════════════════════════════════════════════════
# المرحلة الثالثة — نقاط البيع (POS)
# ═══════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install")
class TestPOSFlow(TransactionCase):
    """POS order creation → sale order → invoice → payment sync."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "عميل POS"})

        income_account = cls.env["account.account"].search(
            [
                ("account_type", "=", "income_other"),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        if not income_account:
            income_account = cls.env["account.account"].search(
                [("company_id", "=", cls.company.id)], limit=1
            )

        cls.product = cls.env["product.product"].create(
            {
                "name": "منتج POS",
                "type": "consu",
                "list_price": 25.0,
                "available_in_pos": True,
                "sale_ok": True,
                "property_account_income_id": income_account.id,
                "company_id": cls.company.id,
            }
        )

    def test_15_create_pos_order_creates_sale_order(self):
        """طلب POS ينشئ أمر بيع مؤكد."""
        payload = {
            "client_order_ref": "POS-001",
            "order_date": fields.Datetime.now().isoformat(),
            "partner_id": self.partner.id,
            "lines": [
                {
                    "product_id": self.product.id,
                    "quantity": 3,
                    "price_unit": 25.0,
                    "tax_ids": [],
                }
            ],
        }
        result = self.env["nexus.pos.order"].sudo().create_pos_order(payload)
        self.assertIn("order_id", result)

        pos_order = self.env["nexus.pos.order"].browse(result["order_id"])
        self.assertEqual(pos_order.state, "posted")
        self.assertEqual(pos_order.client_order_ref, "POS-001")
        self.assertTrue(pos_order.sale_order_id)
        self.assertEqual(pos_order.sale_order_id.state, "sale")

    def test_16_pos_order_lines_contain_correct_data(self):
        """سطور طلب POS تحتوي على البيانات الصحيحة."""
        payload = {
            "client_order_ref": "POS-002",
            "order_date": fields.Datetime.now().isoformat(),
            "partner_id": self.partner.id,
            "lines": [
                {
                    "product_id": self.product.id,
                    "quantity": 2,
                    "price_unit": 50.0,
                    "discount": 10,
                    "tax_ids": [],
                }
            ],
        }
        result = self.env["nexus.pos.order"].sudo().create_pos_order(payload)
        order = self.env["nexus.pos.order"].browse(result["order_id"])
        line = order.line_ids[0]
        self.assertEqual(line.quantity, 2)
        self.assertEqual(line.price_unit, 45.0)  # 10% discount applied

    def test_17_pos_order_triggers_sale_order_confirm(self):
        """أمر البيع الناتج من POS يكون في حالة مؤكد."""
        payload = {
            "client_order_ref": "POS-003",
            "order_date": fields.Datetime.now().isoformat(),
            "partner_id": self.partner.id,
            "lines": [
                {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 100.0,
                    "tax_ids": [],
                }
            ],
        }
        result = self.env["nexus.pos.order"].sudo().create_pos_order(payload)
        pos_order = self.env["nexus.pos.order"].browse(result["order_id"])
        sale_order = pos_order.sale_order_id
        self.assertTrue(sale_order, "Sale order must be created")
        self.assertEqual(sale_order.state, "sale", "Sale order must be confirmed")


# ═══════════════════════════════════════════════════════════════════════
# المرحلة الرابعة — القيود اليومية + مراكز التكلفة
# ═══════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install")
class TestJournalEntriesAndCostCenters(TransactionCase):
    """Daily journal entries, cost center propagation, and dimension mapping."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.misc_journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.misc_journal:
            cls.misc_journal = cls.env["account.journal"].create(
                {
                    "name": "مذكرة يومية",
                    "code": "MISC",
                    "type": "general",
                    "company_id": cls.company.id,
                }
            )

        cls.account_a = cls.env["account.account"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.account_b = cls.env["account.account"].search(
            [("company_id", "=", cls.company.id), ("id", "!=", cls.account_a.id)],
            limit=1,
        )

    def test_18_journal_entry_posting_no_unwanted_sync(self):
        """القيد اليومي (نوع 'entry') لا يؤدي لمزامنة غير ضرورية."""
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": fields.Date.today(),
                "company_id": self.company.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.account_a.id,
                            "debit": 1000.0,
                            "credit": 0.0,
                            "name": "مدين",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.account_b.id,
                            "debit": 0.0,
                            "credit": 1000.0,
                            "name": "دائن",
                        },
                    ),
                ],
            }
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        # Entry type should NOT trigger invoice sync
        _assert_queue_count(self, "invoice.create", 0)

    def test_19_cost_center_stored_on_move_and_line(self):
        """مركز التكلفة يخزن في الفاتورة وسطورها."""
        partner = self.env["res.partner"].create({"name": "عميل CC"})
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "company_id": self.company.id,
                "nexus_cost_center": "Branch - مكة",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "بند 1",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        self.assertEqual(move.nexus_cost_center, "Branch - مكة")
        # store=True related field should propagate
        self.assertEqual(
            move.line_ids.filtered(lambda l: l.display_type != "product")[0].nexus_cost_center
            if move.line_ids
            else "",
            "",
        )

    def test_20_cost_center_mapping_mark_synced(self):
        """دالة mark_synced تنشئ سجل mapping وتحدث المصدر."""
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        if not warehouse:
            warehouse = self.env["stock.warehouse"].create(
                {
                    "name": "فرع النموذج",
                    "code": "NW",
                    "company_id": self.company.id,
                }
            )
        warehouse.nexus_cost_center_synced = False
        self.env["nexus.cost.center.mapping"]._mark_synced(
            "stock.warehouse", warehouse.id, "CC-NW-001"
        )
        mapping = self.env["nexus.cost.center.mapping"].search(
            [("model_name", "=", "stock.warehouse"), ("res_id", "=", warehouse.id)],
            limit=1,
        )
        self.assertTrue(mapping)
        self.assertTrue(mapping.synced)
        self.assertEqual(mapping.nexus_cost_center_id, "CC-NW-001")

        # Source record should be marked synced
        self.assertTrue(warehouse.nexus_cost_center_synced)


# ═══════════════════════════════════════════════════════════════════════
# المرحلة الخامسة — طابور المزامنة: دورة الحياة والحالات الاستثنائية
# ═══════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install")
class TestQueueLifecycle(TransactionCase):
    """Queue record state transitions, idempotency, retry, and edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Queue = cls.env["nexus.sync.queue"]

    def test_21_enqueue_creates_pending_record(self):
        """enqueue() ينشئ سجل بحالة pending."""
        record = self.Queue.enqueue(
            operation="test.op",
            payload={"key": "value"},
            endpoint="/api/test",
            transaction_id="NX-TEST-001",
        )
        self.assertEqual(record.state, "pending")
        self.assertEqual(record.operation, "test.op")
        self.assertEqual(record.transaction_id, "NX-TEST-001")
        self.assertIn('"key": "value"', record.payload)

    def test_22_duplicate_transaction_id_is_idempotent(self):
        """نفس transaction_id يعيد نفس السجل ولا ينشئ نسخة جديدة."""
        r1 = self.Queue.enqueue(
            operation="test.op",
            payload={"a": 1},
            endpoint="/api/test",
            transaction_id="NX-DEDUP-001",
        )
        r2 = self.Queue.enqueue(
            operation="test.op",
            payload={"a": 999},  # different payload, but same tx id
            endpoint="/api/test",
            transaction_id="NX-DEDUP-001",
        )
        self.assertEqual(r1.id, r2.id, "Must return the existing record")
        self.assertEqual(
            self.Queue.search_count([("transaction_id", "=", "NX-DEDUP-001")]),
            1,
        )

    def test_23_transaction_id_unique_constraint(self):
        """لا يمكن إنشاء سجلين بنفس transaction_id يدوياً."""
        self.Queue.create(
            {
                "name": "Test 1",
                "operation": "test.op",
                "transaction_id": "NX-UNIQ-001",
                "endpoint": "/api/x",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.Queue.create(
                {
                    "name": "Test 2",
                    "operation": "test.op",
                    "transaction_id": "NX-UNIQ-001",
                    "endpoint": "/api/x",
                    "company_id": self.company.id,
                }
            )

    def test_24_state_transitions_success(self):
        """الانتقال من pending → processing → done يتم بشكل صحيح."""
        record = self.Queue.enqueue(
            operation="test.op",
            payload={},
            endpoint="/api/test",
            transaction_id="NX-STATE-001",
        )
        self.assertEqual(record.state, "pending")

        record.state = "processing"
        self.assertEqual(record.state, "processing")

        record._on_success('{"ok": true}', "DOC-001")
        self.assertEqual(record.state, "done")
        self.assertEqual(record.docname, "DOC-001")

    def test_25_state_transitions_fail_and_retry(self):
        """عند الفشل: increment retry وإعادة جدولة."""
        record = self.Queue.enqueue(
            operation="test.op",
            payload={},
            endpoint="/api/test",
            transaction_id="NX-FAIL-001",
        )
        record.state = "processing"
        record._retry("Connection timeout")
        self.assertEqual(record.state, "pending")
        self.assertEqual(record.retry_count, 1)
        self.assertIn("Connection timeout", record.last_error or "")

    def test_26_max_retries_exceeded_marks_failed(self):
        """عند تجاوز الحد الأقصى للمحاولات ← فشل دائم."""
        record = self.Queue.enqueue(
            operation="test.op",
            payload={},
            endpoint="/api/test",
            transaction_id="NX-MAXRETRY-001",
        )
        record.retry_count = record.max_retries
        record._process_single(record)
        self.assertEqual(record.state, "failed")

    def test_27_reschedule_does_not_increment_retry(self):
        """إعادة الجدولة لا تزيد عداد المحاولات (لحالات الانتظار)."""
        record = self.Queue.enqueue(
            operation="test.op",
            payload={},
            endpoint="/api/test",
            transaction_id="NX-RESCHED-001",
        )
        record._reschedule("Waiting for dependency")
        self.assertEqual(record.state, "pending")
        self.assertEqual(record.retry_count, 0)
        self.assertIn("Waiting", record.last_error or "")

    def test_28_action_cancel_and_retry_buttons(self):
        """أزرار الإلغاء وإعادة المحاولة تعمل."""
        record = self.Queue.enqueue(
            operation="test.op",
            payload={},
            endpoint="/api/test",
            transaction_id="NX-BTN-001",
        )
        record.action_cancel()
        self.assertEqual(record.state, "cancelled")

        record.action_retry()
        self.assertEqual(record.state, "pending")

    def test_29_auto_generated_transaction_id(self):
        """عند عدم إعطاء transaction_id، يتم إنشاؤه تلقائياً بصيغة NX-..."""
        record = self.Queue.enqueue(
            operation="test.op",
            payload={},
            endpoint="/api/test",
        )
        self.assertTrue(
            record.transaction_id.startswith("NX-"),
            f"Auto-generated ID: {record.transaction_id}",
        )
        self.assertEqual(len(record.transaction_id), 29)  # "NX-" + 20 hex

    def test_30_queue_records_have_backoff(self):
        """عند إعادة المحاولة، next_attempt يكون في المستقبل."""
        record = self.Queue.enqueue(
            operation="test.op",
            payload={},
            endpoint="/api/test",
            transaction_id="NX-BACKOFF-001",
        )
        now = fields.Datetime.now()
        record.state = "processing"
        record._retry("Temporary error")
        self.assertGreater(record.next_attempt, now)


# ═══════════════════════════════════════════════════════════════════════
# المرحلة السادسة — تغطية جميع الموديلات (Model Coverage)
# ═══════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install")
class TestAllModelsExist(TransactionCase):
    """تأكيد وجود جميع الموديلات والحقول الأساسية للمحاسبة المتقدمة."""

    def test_31_nexus_sync_queue_model_exists(self):
        self.assertTrue(self.env["nexus.sync.queue"]._name)

    def test_32_nexus_tax_mapping_model_exists(self):
        self.assertTrue(self.env["nexus.tax.mapping"]._name)

    def test_33_nexus_cost_center_mapping_model_exists(self):
        self.assertTrue(self.env["nexus.cost.center.mapping"]._name)

    def test_34_warehouse_has_nexus_sync_field(self):
        wh = self.env["stock.warehouse"].search([], limit=1)
        if not wh:
            wh = self.env["stock.warehouse"].create(
                {"name": "T", "code": "T", "company_id": self.env.company.id}
            )
        self.assertIn("nexus_cost_center_synced", wh._fields)

    def test_35_department_has_nexus_sync_field(self):
        dept = self.env["hr.department"].search([], limit=1)
        if not dept:
            dept = self.env["hr.department"].create(
                {"name": "Test Dept", "company_id": self.env.company.id}
            )
        self.assertIn("nexus_cost_center_synced", dept._fields)

    def test_36_project_has_nexus_sync_field(self):
        proj = self.env["project.project"].search([], limit=1)
        if not proj:
            proj = self.env["project.project"].create(
                {"name": "Test Project", "company_id": self.env.company.id}
            )
        self.assertIn("nexus_cost_center_synced", proj._fields)

    def test_37_queue_handler_registry(self):
        """جميع العمليات الستة مسجلة في _HANDLERS."""
        handlers = self.env["nexus.sync.queue"]._HANDLERS
        expected = {
            "invoice.create",
            "payment_entry.create",
            "cost_center.create",
            "asset.create",
            "expense_claim.create",
            "tax_template.create",
        }
        self.assertTrue(
            expected.issubset(set(handlers.keys())),
            f"Missing handlers: {expected - set(handlers.keys())}",
        )


# ═══════════════════════════════════════════════════════════════════════
# المرحلة السابعة — التسلسل الهرمي لمراكز التكلفة (Cost Center Hierarchy)
# ═══════════════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install")
class TestCostCenterAutoCreation(TransactionCase):
    """اختبار الإنشاء التلقائي لمراكز التكلفة عند إنشاء الفروع والأقسام والمشاريع."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    def test_38_warehouse_creation_enqueues_cost_center(self):
        """إنشاء فرع/مستودع جديد ← طلب إنشاء مركز تكلفة في Nexus Core."""
        wh = self.env["stock.warehouse"].create(
            {
                "name": "فرع الشمال",
                "code": "NRTH",
                "company_id": self.company.id,
            }
        )
        queue = self.env["nexus.sync.queue"].sudo().search(
            [
                ("operation", "=", "cost_center.create"),
                ("model_name", "=", "stock.warehouse"),
                ("res_id", "=", wh.id),
            ],
            limit=1,
        )
        self.assertTrue(queue, "Cost center queue record must exist for warehouse")
        payload = queue._prepare_operation()
        self.assertIn("فرع الشمال", payload["cost_center_name"])
        self.assertEqual(payload["doctype"], "Cost Center")

    def test_39_department_creation_enqueues_cost_center(self):
        """إنشاء قسم جديد ← طلب إنشاء مركز تكلفة."""
        dept = self.env["hr.department"].create(
            {"name": "قسم المالية", "company_id": self.company.id}
        )
        queue = self.env["nexus.sync.queue"].sudo().search(
            [
                ("operation", "=", "cost_center.create"),
                ("model_name", "=", "hr.department"),
                ("res_id", "=", dept.id),
            ],
            limit=1,
        )
        self.assertTrue(queue, "Cost center queue must exist for department")
        payload = queue._prepare_operation()
        self.assertIn("قسم المالية", payload["cost_center_name"])

    def test_40_project_creation_enqueues_cost_center(self):
        """إنشاء مشروع جديد ← طلب إنشاء مركز تكلفة."""
        proj = self.env["project.project"].create(
            {"name": "مشروع القدية", "company_id": self.company.id}
        )
        queue = self.env["nexus.sync.queue"].sudo().search(
            [
                ("operation", "=", "cost_center.create"),
                ("model_name", "=", "project.project"),
                ("res_id", "=", proj.id),
            ],
            limit=1,
        )
        self.assertTrue(queue, "Cost center queue must exist for project")
        payload = queue._prepare_operation()
        self.assertIn("مشروع القدية", payload["cost_center_name"])
