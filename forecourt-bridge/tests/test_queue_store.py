import os
import tempfile
import unittest

from bridge.queue_store import QueueStore


class TestQueueStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "queue.sqlite3")
        self.queue = QueueStore(self.db_path)

    def tearDown(self):
        self.queue.close()
        self._tmpdir.cleanup()

    def test_enqueue_and_peek(self):
        self.queue.enqueue({"transaction_ref": "TXN-1", "nozzle_address": "P01-N01", "volume": 10.0})
        batch = self.queue.peek_batch(10)
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0]["transaction_ref"], "TXN-1")

    def test_duplicate_enqueue_is_idempotent(self):
        payload = {"transaction_ref": "TXN-1", "nozzle_address": "P01-N01", "volume": 10.0}
        self.queue.enqueue(payload)
        self.queue.enqueue(payload)
        self.assertEqual(self.queue.pending_count(), 1)

    def test_mark_sent_removes_row(self):
        self.queue.enqueue({"transaction_ref": "TXN-1", "nozzle_address": "P01-N01", "volume": 10.0})
        batch = self.queue.peek_batch(10)
        self.queue.mark_sent([item["_row_id"] for item in batch])
        self.assertEqual(self.queue.pending_count(), 0)

    def test_survives_reopen(self):
        self.queue.enqueue({"transaction_ref": "TXN-1", "nozzle_address": "P01-N01", "volume": 10.0})
        self.queue.close()

        reopened = QueueStore(self.db_path)
        self.assertEqual(reopened.pending_count(), 1)
        reopened.close()


if __name__ == "__main__":
    unittest.main()
