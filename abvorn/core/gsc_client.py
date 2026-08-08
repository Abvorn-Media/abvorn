"""gsc_client.py - Google Search Console client for Abvorn.

Fetches Search Console performance data using a Google Cloud service account
and formats it for the Brain, the Hindsight Learner and the Evolution Journal.

Uses google-auth + google-api-python-client directly (both already in
requirements.txt). The `searchconsole` wrapper from the integration guide only
supports OAuth client-secrets auth, not service accounts, so it is not used.
"""

import logging
import os
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

DEFAULT_CREDENTIALS_PATH = "gsc-credentials.json"


def _apply_system_proxy():
    """Apply the Windows system proxy to env vars so google-auth/googleapiclient use it.

    Google's API calls time out with a direct connection when the machine routes
    internet traffic through a local proxy (browsers honour it, Python does not).
    Reads the proxy from the Windows registry and sets HTTP(S)_PROXY when no
    proxy is already configured in the environment.
    """
    if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
        return
    try:
        proxies = urllib.request.getproxies_registry()
    except Exception:
        proxies = {}
    https = proxies.get("https") or proxies.get("http")
    if https:
        os.environ["HTTPS_PROXY"] = https
        os.environ["HTTP_PROXY"] = https


class GSCClient:
    """Google Search Console client for Abvorn.

    Fetches performance data and formats it for the Brain and Hindsight Learner.
    """

    def __init__(self, credentials_path: str = DEFAULT_CREDENTIALS_PATH):
        self.credentials_path = Path(credentials_path)

        if not self.credentials_path.exists():
            logger.warning("GSC credentials not found at %s. Client disabled.", credentials_path)
            self.enabled = False
            self.property_url = None
            return

        try:
            _apply_system_proxy()
            creds = service_account.Credentials.from_service_account_file(
                str(self.credentials_path), scopes=GSC_SCOPES
            )
            self._service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
            self.property_url = self._pick_property()
            if not self.property_url:
                logger.warning("No Search Console property found for this service account.")
                self.enabled = False
                return
            self.enabled = True
            logger.info("GSC Client enabled for %s", self.property_url)
        except Exception as e:
            logger.error("Failed to initialize GSC Client: %s", e)
            self.enabled = False
            self.property_url = None

    def _pick_property(self) -> Optional[str]:
        """Return the first available Search Console property URL."""
        try:
            result = self._service.sites().list().execute()
        except Exception as e:
            logger.error("Failed to list Search Console properties: %s", e)
            return None
        entries = result.get("siteEntry", [])
        for entry in entries:
            url = entry.get("siteUrl", "")
            # Only usable properties (not pending) qualify.
            permission = entry.get("permissionLevel", "")
            if url and permission not in ("siteUnverifiedUser",):
                return url
        return entries[0]["siteUrl"] if entries else None

    def fetch_performance(
        self, days: int = 7, dimensions: Optional[List[str]] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch performance data for the last N days.

        Args:
            days: Number of days to look back.
            dimensions: List of dimensions (query, page, device, country).
            limit: Maximum number of rows to fetch.

        Returns:
            List of row dicts with keys, clicks, impressions, ctr, position.
        """
        if not self.enabled:
            logger.warning("GSC Client disabled. Returning empty list.")
            return []

        if dimensions is None:
            dimensions = ["query", "page"]

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": limit,
        }

        try:
            response = (
                self._service.searchanalytics()
                .query(siteUrl=self.property_url, body=body)
                .execute()
            )
            rows = response.get("rows", [])
            logger.info("Fetched %d rows from GSC", len(rows))
            return rows
        except Exception as e:
            logger.error("Failed to fetch GSC data: %s", e)
            return []

    def fetch_top_performing(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch the top performing pages based on clicks."""
        rows = self.fetch_performance(days, ["page"], limit=1000)
        if not rows:
            return []

        top = sorted(rows, key=lambda r: r.get("clicks", 0), reverse=True)[:limit]
        results = []
        for row in top:
            keys = row.get("keys", [])
            results.append({
                "url": keys[0] if keys else "",
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": float(row.get("ctr", 0)),
                "position": float(row.get("position", 0)),
                "date": datetime.now().isoformat(),
            })
        return results

    def fetch_growth_opportunities(self, days: int = 30) -> List[Dict[str, Any]]:
        """Identify pages with high impressions but low CTR (growth opportunities)."""
        rows = self.fetch_performance(days, ["query", "page"], limit=1000)
        if not rows:
            return []

        opportunities = [
            row for row in rows
            if row.get("impressions", 0) > 100 and row.get("ctr", 1) < 0.02
        ]
        opportunities.sort(key=lambda r: r.get("impressions", 0), reverse=True)

        results = []
        for row in opportunities[:20]:
            keys = row.get("keys", [])
            results.append({
                "query": keys[0] if keys else "",
                "page": keys[1] if len(keys) > 1 else "",
                "impressions": int(row.get("impressions", 0)),
                "clicks": int(row.get("clicks", 0)),
                "ctr": float(row.get("ctr", 0)),
                "position": float(row.get("position", 0)),
                "opportunity_score": row.get("impressions", 0) * (0.02 - row.get("ctr", 0)),
            })
        return results

    def get_summary(self) -> Dict[str, Any]:
        """Get a high-level summary of GSC performance."""
        if not self.enabled:
            return {"enabled": False, "message": "GSC Client disabled"}

        rows = self.fetch_performance(30, [], limit=1000)
        if not rows:
            return {
                "enabled": True,
                "message": "No data available yet",
                "property": self.property_url,
                "total_clicks": 0,
                "total_impressions": 0,
                "avg_ctr": 0.0,
                "avg_position": 0.0,
                "data_rows": 0,
            }

        total_clicks = sum(r.get("clicks", 0) for r in rows)
        total_impressions = sum(r.get("impressions", 0) for r in rows)
        ctrs = [r.get("ctr", 0) for r in rows]
        positions = [r.get("position", 0) for r in rows]

        return {
            "enabled": True,
            "property": self.property_url,
            "total_clicks": int(total_clicks),
            "total_impressions": int(total_impressions),
            "avg_ctr": float(sum(ctrs) / len(ctrs)) if ctrs else 0.0,
            "avg_position": float(sum(positions) / len(positions)) if positions else 0.0,
            "data_rows": len(rows),
        }
