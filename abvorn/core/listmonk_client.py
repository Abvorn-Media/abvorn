"""listmonk_client.py — Abvorn's Listmonk integration.

Thin wrapper around the Listmonk self-hosted newsletter API.
Used by the Email Scheduler and Unified Database for subscriber sync,
transactional email and campaign creation.

Configuration via environment variables (falls back to localhost defaults):
    LISTMONK_URL       e.g. http://localhost:9000
    LISTMONK_USERNAME  e.g. admin
    LISTMONK_PASSWORD  e.g. your_admin_password
    LISTMONK_TIMEOUT   request timeout in seconds (default 10)
    LISTMONK_RETRIES   retry count on transient failures (default 3)
"""

import os
import time
import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ListmonkClient:
    def __init__(self, base_url: str = None,
                 username: str = None,
                 password: str = None,
                 timeout: float = None,
                 retries: int = None):
        self.base_url = (base_url or os.environ.get("LISTMONK_URL", "http://localhost:9000")).rstrip("/")
        username = username or os.environ.get("LISTMONK_USERNAME", "admin")
        password = password or os.environ.get("LISTMONK_PASSWORD", "change_this_admin_password")
        self.auth = (username, password)
        self.timeout = timeout or float(os.environ.get("LISTMONK_TIMEOUT", "10"))
        self.retries = retries if retries is not None else int(os.environ.get("LISTMONK_RETRIES", "3"))
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"Content-Type": "application/json"})

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        last_error = ""
        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code >= 400:
                    body = response.text[:500]
                    logger.warning("Listmonk %s %s -> %s: %s",
                                   method.upper(), path, response.status_code, body)
                    response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                last_error = str(e)[:300]
                if attempt < self.retries:
                    wait = 2 ** attempt
                    logger.debug("Listmonk retry %s/%s after %.1fs: %s",
                                 attempt + 1, self.retries, wait, last_error)
                    time.sleep(wait)
        raise RuntimeError(f"Listmonk request failed after {self.retries} retries: {last_error}")

    def get_lists(self) -> List[Dict]:
        return self._request("get", "/api/lists").get("data", [])

    def create_subscriber(self, email: str, name: str = "", list_ids: List[int] = None) -> Dict:
        data = {"email": email, "name": name, "lists": list_ids or []}
        return self._request("post", "/api/subscribers", json=data)

    def send_transactional_email(self, to_email: str, subject: str, body_html: str,
                                 from_email: str = "hello@abvorn.com",
                                 from_name: str = "Abvorn") -> Dict:
        data = {
            "to": [to_email],
            "subject": subject,
            "html": body_html,
            "from_email": from_email,
            "from_name": from_name
        }
        return self._request("post", "/api/tx", json=data)

    def create_campaign(self, name: str, subject: str, body_html: str,
                        list_ids: List[int]) -> Dict:
        data = {
            "name": name,
            "subject": subject,
            "body": body_html,
            "lists": list_ids,
            "type": "regular"
        }
        return self._request("post", "/api/campaigns", json=data)

    def get_subscribers(self, page: int = 1, per_page: int = 100) -> List[Dict]:
        return self._request("get",
                             f"/api/subscribers?page={page}&per_page={per_page}").get("data", [])


_instance = None


def get_listmonk() -> ListmonkClient:
    global _instance
    if _instance is None:
        _instance = ListmonkClient()
    return _instance
