"""HTTP client for the /saas/db-provisioner/* control-plane endpoints."""
import logging
from typing import List, Optional

import requests

from .config import OdooConfig

_logger = logging.getLogger(__name__)


class OdooClient:
    def __init__(self, config: OdooConfig):
        self._config = config
        self._session = requests.Session()
        self._session.headers.update({"X-Provisioner-Api-Key": config.api_key})

    def fetch_pending_jobs(self) -> List[dict]:
        try:
            resp = self._session.get(self._config.pending_url, timeout=self._config.request_timeout)
        except requests.RequestException as exc:
            _logger.warning("Failed to poll pending jobs: %s", exc)
            return []

        if resp.status_code == 401:
            _logger.error("Provisioner API key rejected (401). Check config.yaml.")
            return []
        if resp.status_code >= 400:
            _logger.error("Unexpected response polling jobs: %s %s", resp.status_code, resp.text[:300])
            return []

        try:
            return resp.json().get("jobs", [])
        except ValueError:
            _logger.error("Non-JSON response polling jobs: %s", resp.text[:300])
            return []

    def report_result(
        self,
        request_id: int,
        success: bool,
        message: str = "",
        log: str = "",
    ) -> bool:
        try:
            resp = self._session.post(
                self._config.callback_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "request_id": request_id,
                        "success": success,
                        "message": message,
                        "log": log,
                    },
                },
                timeout=self._config.request_timeout,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            _logger.error(
                "Failed to report result for request %s (will retry next cycle): %s",
                request_id,
                exc,
            )
            return False
