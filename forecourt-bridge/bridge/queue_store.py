"""Durable local queue — survives network outages and process restarts.

A reading is only deleted once Odoo has acknowledged it (HTTP 200 with
an 'accepted' or 'duplicates' result for that transaction_ref). This is
the bridge-side half of the resilience story; ``fuel.reading.buffer``
in Odoo is the server-side half.
"""
import json
import logging
import os
import sqlite3
import threading
from typing import List

_logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_ref TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_attempt_at TEXT
);
"""


class QueueStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def enqueue(self, payload: dict) -> None:
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO pending_readings (transaction_ref, payload) VALUES (?, ?)",
                    (payload["transaction_ref"], json.dumps(payload)),
                )
                self._conn.commit()
            except sqlite3.IntegrityError:
                # Already queued (protocol adapter emitted a duplicate) — fine.
                _logger.debug(
                    "Reading %s already queued locally, skipping.",
                    payload.get("transaction_ref"),
                )

    def peek_batch(self, limit: int) -> List[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, payload FROM pending_readings ORDER BY id ASC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return [{"_row_id": row[0], **json.loads(row[1])} for row in rows]

    def mark_sent(self, row_ids: List[int]) -> None:
        if not row_ids:
            return
        with self._lock:
            placeholders = ",".join("?" * len(row_ids))
            self._conn.execute(
                f"DELETE FROM pending_readings WHERE id IN ({placeholders})", row_ids
            )
            self._conn.commit()

    def mark_attempt(self, row_ids: List[int]) -> None:
        if not row_ids:
            return
        with self._lock:
            placeholders = ",".join("?" * len(row_ids))
            self._conn.execute(
                f"UPDATE pending_readings SET attempts = attempts + 1, "
                f"last_attempt_at = datetime('now') WHERE id IN ({placeholders})",
                row_ids,
            )
            self._conn.commit()

    def pending_count(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM pending_readings")
            return cur.fetchone()[0]

    def close(self) -> None:
        self._conn.close()
