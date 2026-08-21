"""Push queued readings to the Odoo /nexus_fuel/forecourt/readings endpoint."""
import logging
from typing import List

import requests

from .config import OdooConfig

_logger = logging.getLogger(__name__)


class Uploader:
    def __init__(self, odoo_config: OdooConfig):
        self._config = odoo_config
        self._session = requests.Session()
        self._session.headers.update({"X-Forecourt-Api-Key": odoo_config.api_key})

    def push(self, batch: List[dict]) -> List[int]:
        """Send a batch of readings; return the list of row_ids safe to delete.

        A row is safe to delete once Odoo reports it as 'accepted'
        (successfully buffered — processing errors are retried
        server-side by Odoo's own cron, not by us) or 'duplicates'
        (already received in a previous, possibly-interrupted push).
        """
        if not batch:
            return []

        readings_payload = [
            {k: v for k, v in reading.items() if k != "_row_id"} for reading in batch
        ]

        try:
            response = self._session.post(
                self._config.readings_url,
                json={"readings": readings_payload},
                timeout=self._config.request_timeout,
            )
        except requests.RequestException as exc:
            _logger.warning("Push failed (network/timeout): %s. Will retry next cycle.", exc)
            return []

        if response.status_code == 401:
            _logger.error(
                "Odoo rejected the API key (401). Check config.yaml 'odoo.api_key' "
                "against the fuel.forecourt.device record."
            )
            return []

        if response.status_code >= 500:
            _logger.warning(
                "Odoo server error (%s). Will retry next cycle.", response.status_code
            )
            return []

        if response.status_code >= 400:
            _logger.error(
                "Odoo rejected the batch (%s): %s", response.status_code, response.text[:500]
            )
            return []

        try:
            data = response.json()
        except ValueError:
            _logger.error("Odoo returned non-JSON response: %s", response.text[:500])
            return []

        result = data.get("result", {})
        row_by_ref = {r["transaction_ref"]: r["_row_id"] for r in batch}

        safe_to_delete = []
        for item in result.get("accepted", []):
            row_id = row_by_ref.get(item.get("transaction_ref"))
            if row_id is not None:
                safe_to_delete.append(row_id)
        for item in result.get("duplicates", []):
            row_id = row_by_ref.get(item.get("transaction_ref"))
            if row_id is not None:
                safe_to_delete.append(row_id)

        for item in result.get("errors", []):
            _logger.error("Reading rejected by Odoo: %s", item)

        _logger.info(
            "Pushed %s readings: %s accepted, %s duplicates, %s errors",
            len(batch),
            len(result.get("accepted", [])),
            len(result.get("duplicates", [])),
            len(result.get("errors", [])),
        )
        return safe_to_delete
