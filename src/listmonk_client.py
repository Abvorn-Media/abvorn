"""Listmonk API client for Abvorn."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests  # local import so module loads even if requests is missing
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


class ListmonkClient:
    """Minimal Listmonk API client.

    All public methods return the parsed JSON body on success, or ``None``
    when the Listmonk server is unreachable / misconfigured.  This keeps
    the rest of Abvorn functional without a live Listmonk instance.
    """

    def __init__(
        self,
        base_url: str = "",
        username: str = "",
        password: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._session: Optional[Any] = None

    def _get_session(self) -> Optional[Any]:
        if requests is None:
            return None
        if self._session is None:
            self._session = requests.Session()
            self._session.auth = (self.username, self.password)
            self._session.headers.update({
                "Content-Type": "application/json",
                "User-Agent": "Abvorn/1.0",
            })
        return self._session

    def _request(self, method: str, path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        session = self._get_session()
        if session is None:
            return None
        url = f"{self.base_url}{path}"
        try:
            resp = session.request(method, url, timeout=15, **kwargs)
            if resp.status_code == 401:
                logger.warning("Listmonk auth failed")
                return None
            if resp.status_code >= 400:
                logger.warning("Listmonk %s %s -> %s", method, path, resp.status_code)
                return None
            return resp.json()
        except Exception as e:
            logger.warning("Listmonk request failed %s %s: %s", method, path, e)
            return None

    def health(self) -> Dict[str, Any]:
        data = self._request("GET", "/api/health")
        return data or {"status": "unavailable"}

    def get_lists(self) -> List[Dict[str, Any]]:
        data = self._request("GET", "/api/lists")
        if data:
            return data.get("data", [])
        return []

    def get_or_create_list(self, name: str, description: str = "") -> Optional[int]:
        for lst in self.get_lists():
            if lst.get("name") == name:
                return lst.get("id")
        data = self._request("POST", "/api/lists", json={
            "name": name,
            "description": description,
        })
        if data:
            return data.get("data", {}).get("id")
        return None

    def create_subscriber(
        self,
        email: str,
        name: str = "",
        list_ids: Optional[List[int]] = None,
    ) -> Optional[Dict[str, Any]]:
        list_ids = list_ids or []
        data = self._request("POST", "/api/subscribers", json={
            "email": email,
            "name": name,
            "lists": list_ids,
        })
        return data.get("data") if data else None

    def get_subscriber(self, email: str) -> Optional[Dict[str, Any]]:
        data = self._request("GET", f"/api/subscribers?email={email}")
        if data:
            records = data.get("data", {}).get("results", [])
            return records[0] if records else None
        return None

    def send_transactional(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        from_email: str = "hello@abvorn.com",
        from_name: str = "Abvorn",
    ) -> Optional[Dict[str, Any]]:
        data = self._request("POST", "/api/tx", json={
            "to": [to_email],
            "subject": subject,
            "html": body_html,
            "from_email": from_email,
            "from_name": from_name,
        })
        return data.get("data") if data else None

    def create_campaign(
        self,
        name: str,
        subject: str,
        body_html: str,
        list_ids: List[int],
        send_as: str = "newsletter",
    ) -> Optional[Dict[str, Any]]:
        data = self._request("POST", "/api/campaigns", json={
            "name": name,
            "subject": subject,
            "body": body_html,
            "lists": list_ids,
            "type": send_as,
        })
        return data.get("data") if data else None

    def get_campaigns(self, page: int = 1, per_page: int = 50) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/api/campaigns?page={page}&per_page={per_page}")
        if data:
            return data.get("data", {}).get("results", [])
        return []


_instance: Optional[ListmonkClient] = None


def get_listmonk() -> ListmonkClient:
    global _instance
    if _instance is None:
        base_url = ""
        username = ""
        password = ""
        try:
            import os
            from pathlib import Path
            secrets_path = Path("secrets.json")
            if not secrets_path.exists():
                secrets_path = Path(__file__).resolve().parent.parent / "secrets.json"
            if secrets_path.exists():
                import json
                raw = secrets_path.read_text(encoding="utf-8")
                cfg = json.loads(raw)
                base_url = cfg.get("LISTMONK_URL", "")
                username = cfg.get("LISTMONK_USER", "")
                password = cfg.get("LISTMONK_PASSWORD", "")
        except Exception:
            pass
        _instance = ListmonkClient(
            base_url=base_url or "http://localhost:9000",
            username=username or "admin",
            password=password or "",
        )
    return _instance
