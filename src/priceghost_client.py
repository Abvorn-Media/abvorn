"""PriceGhost API client for Abvorn."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests  # noqa: F401 — local import so module loads without requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]


class PriceGhostClient:
    """Minimal PriceGhost API client.

    All methods return ``None`` when the PriceGhost server is unreachable
    or misconfigured, so Abvorn continues to function without it.
    """

    def __init__(self, base_url: str = "", api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session: Optional[Any] = None

    def _get_session(self) -> Optional[Any]:
        if requests is None:
            return None
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "Content-Type": "application/json",
                "User-Agent": "Abvorn/1.0",
            })
            if self.api_key:
                self._session.headers["X-API-Key"] = self.api_key
        return self._session

    def _request(self, method: str, path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        session = self._get_session()
        if session is None:
            return None
        url = f"{self.base_url}{path}"
        try:
            resp = session.request(method, url, timeout=15, **kwargs)
            if resp.status_code == 401:
                logger.warning("PriceGhost auth failed")
                return None
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                logger.warning("PriceGhost %s %s -> %s", method, path, resp.status_code)
                return None
            return resp.json()
        except Exception as e:
            logger.warning("PriceGhost request failed %s %s: %s", method, path, e)
            return None

    def health(self) -> Dict[str, Any]:
        data = self._request("GET", "/api/health")
        return data or {"status": "unavailable"}

    def create_watch(
        self,
        url: str,
        target_price: Optional[float] = None,
        watch_type: str = "price",
        currency: str = "USD",
    ) -> Optional[Dict[str, Any]]:
        data = self._request("POST", "/api/watches", json={
            "url": url,
            "target_price": target_price,
            "watch_type": watch_type,
            "currency": currency,
        })
        return data.get("data") if data else None

    def get_watch(self, watch_id: int) -> Optional[Dict[str, Any]]:
        data = self._request("GET", f"/api/watches/{watch_id}")
        return data.get("data") if data else None

    def get_watches(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/api/watches?page={page}&limit={limit}")
        if data:
            return data.get("data", [])
        return []

    def get_price_history(self, watch_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/api/watches/{watch_id}/price-history?limit={limit}")
        if data:
            return data.get("data", [])
        return []

    def trigger_check(self, watch_id: int) -> Optional[Dict[str, Any]]:
        data = self._request("POST", f"/api/watches/{watch_id}/check")
        return data.get("data") if data else None

    def delete_watch(self, watch_id: int) -> bool:
        resp = self._request("DELETE", f"/api/watches/{watch_id}")
        return bool(resp)


_instance: Optional[PriceGhostClient] = None


def get_priceghost() -> PriceGhostClient:
    global _instance
    if _instance is None:
        base_url = ""
        api_key = ""
        try:
            import json
            from pathlib import Path
            secrets_path = Path("secrets.json")
            if not secrets_path.exists():
                secrets_path = Path(__file__).resolve().parent.parent / "secrets.json"
            if secrets_path.exists():
                raw = secrets_path.read_text(encoding="utf-8")
                cfg = json.loads(raw)
                base_url = cfg.get("PRICEGHOST_URL", "")
                api_key = cfg.get("PRICEGHOST_API_KEY", "")
        except Exception:
            pass
        _instance = PriceGhostClient(
            base_url=base_url or "http://localhost:3000",
            api_key=api_key or "",
        )
    return _instance
