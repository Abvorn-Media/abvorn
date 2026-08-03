"""listmonk_client.py — Abvorn's Listmonk integration.

Thin wrapper around the Listmonk self-hosted newsletter API.
Used by the Email Scheduler and Unified Database for subscriber sync,
transactional email and campaign creation.
"""

import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ListmonkClient:
    def __init__(self, base_url: str = "http://localhost:9000",
                 username: str = "admin",
                 password: str = "change_this_admin_password"):
        self.base_url = base_url
        self.auth = (username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"Content-Type": "application/json"})

    def get_lists(self) -> List[Dict]:
        response = self.session.get(f"{self.base_url}/api/lists")
        response.raise_for_status()
        return response.json().get('data', [])

    def create_subscriber(self, email: str, name: str = "", list_ids: List[int] = None) -> Dict:
        data = {"email": email, "name": name, "lists": list_ids or []}
        response = self.session.post(f"{self.base_url}/api/subscribers", json=data)
        response.raise_for_status()
        return response.json()

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
        response = self.session.post(f"{self.base_url}/api/tx", json=data)
        response.raise_for_status()
        return response.json()

    def create_campaign(self, name: str, subject: str, body_html: str,
                        list_ids: List[int]) -> Dict:
        data = {
            "name": name,
            "subject": subject,
            "body": body_html,
            "lists": list_ids,
            "type": "regular"
        }
        response = self.session.post(f"{self.base_url}/api/campaigns", json=data)
        response.raise_for_status()
        return response.json()

    def get_subscribers(self, page: int = 1, per_page: int = 100) -> List[Dict]:
        response = self.session.get(f"{self.base_url}/api/subscribers?page={page}&per_page={per_page}")
        response.raise_for_status()
        return response.json().get('data', [])


_instance = None


def get_listmonk() -> ListmonkClient:
    global _instance
    if _instance is None:
        _instance = ListmonkClient()
    return _instance