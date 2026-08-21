"""Tests for the Forecourt Controller ingestion pipeline.

Covers the three properties called out in the Ocean Seven fuel-automation
technical study: idempotency on retry, correct nozzle-level matching for
multi-product pumps, and graceful isolation of unmatched/bad readings.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from psycopg2 import IntegrityError
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestFuelReadingBuffer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )

        cls.product = cls.env["product.product"].create(
            {"name": "Diesel", "type": "product"}
        )
        cls.tank = cls.env["fuel.tank"].create(
            {
                "name": "Tank 1 - Diesel",
                "product_id": cls.product.id,
                "capacity": 10000.0,
                "current_volume": 5000.0,
                "location_id": warehouse.lot_stock_id.id,
            }
        )
        cls.pump = cls.env["fuel.pump"].create({"name": "Pump 03"})
        cls.nozzle = cls.env["fuel.pump.nozzle"].create(
            {
                "pump_id": cls.pump.id,
                "nozzle_number": 1,
                "tank_id": cls.tank.id,
                "meter_start": 1000.0,
                "meter_end": 1000.0,
                "controller_address": "P03-N01",
            }
        )
        cls.device = cls.env["fuel.forecourt.device"].create(
            {"name": "Main Forecourt Controller"}
        )

    def _make_reading(self, **overrides):
        vals = {
            "device_id": self.device.id,
            "transaction_ref": "TXN-0001",
            "nozzle_address": "P03-N01",
            "volume": 25.0,
            "amount": 100.0,
        }
        vals.update(overrides)
        return self.env["fuel.reading.buffer"].create(vals)

    def test_processing_creates_shift_log_and_updates_tank(self):
        reading = self._make_reading()
        reading.process()

        self.assertEqual(reading.state, "processed")
        self.assertTrue(reading.shift_log_id)
        self.assertEqual(reading.shift_log_id.source, "forecourt")
        self.assertEqual(reading.shift_log_id.nozzle_id, self.nozzle)
        self.assertEqual(reading.shift_log_id.state, "confirmed")
        self.assertEqual(self.nozzle.meter_end, 1025.0)
        self.assertEqual(self.tank.current_volume, 4975.0)

    def test_duplicate_transaction_is_rejected_at_db_level(self):
        self._make_reading()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self._make_reading()

    def test_unmatched_nozzle_is_ignored_not_erroring_the_batch(self):
        reading = self._make_reading(nozzle_address="UNKNOWN-ADDR")
        reading.process()
        self.assertEqual(reading.state, "ignored")
        self.assertFalse(reading.shift_log_id)

    def test_batch_isolates_bad_reading_from_good_ones(self):
        good = self._make_reading(transaction_ref="TXN-GOOD")
        bad = self._make_reading(
            transaction_ref="TXN-BAD", nozzle_address="UNKNOWN-ADDR"
        )
        (good | bad).process()

        self.assertEqual(good.state, "processed")
        self.assertEqual(bad.state, "ignored")

    def test_meter_regression_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.nozzle.write({"meter_start": 2000.0, "meter_end": 1000.0})
