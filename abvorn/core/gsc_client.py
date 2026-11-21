"""gsc_client.py - Google Search Console client for Abvorn.

Fetches Search Console performance data using a Google Cloud service account
and formats it for the Brain, the Hindsight Learner and the Evolution Journal.

Uses google-auth + google-api-python-client directly (both already in
requirements.txt). The `searchconsole` wrapper from the integration guide only
supports OAuth client-secrets auth, not service accounts, so it is not used.
"""

import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

DEFAULT_CREDENTIALS_PATH = "gsc-credentials.json"

CANONICAL_HOST = "abvorn.com"
PROPERTY_OVERRIDE_ENV = "ABVORN_GSC_PROPERTY"


def _property_host(url: str) -> str:
    """Return a normalized host marker for a Search Console property id.

    Domain properties (``sc-domain:abvorn.com``) carry the host in the path,
    URL-prefix properties in the netloc. Only the canonical forms reduce to the
    bare host: ``www.`` is deliberately preserved, and non-https schemes keep a
    scheme marker, so both register as host mismatches in ``_is_canonical_property``.
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "sc-domain":
        host = parsed.netloc or parsed.path
    else:
        host = parsed.netloc
        if host and parsed.scheme != "https":
            return f"{parsed.scheme}:{host.strip('/')}".lower()
    return host.strip("/").lower()


def _is_canonical_property(url: str) -> bool:
    """True when a property targets exactly the canonical abvorn.com host."""
    return _property_host(url) == CANONICAL_HOST


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
        """Return the preferred Search Console property URL, if one is available."""
        try:
            result = self._service.sites().list().execute()
        except Exception as e:
            logger.error("Failed to list Search Console properties: %s", e)
            return None

        entries = result.get("siteEntry", [])
        listed = [
            entry.get("siteUrl", "") for entry in entries if entry.get("siteUrl", "")
        ]
        # Only usable properties (not pending) qualify for the preference list.
        verified = [
            entry.get("siteUrl", "")
            for entry in entries
            if entry.get("siteUrl", "")
            and entry.get("permissionLevel", "") != "siteUnverifiedUser"
        ]

        selected = None
        override = os.environ.get(PROPERTY_OVERRIDE_ENV)
        if override:
            if override in verified:
                selected = override
            elif override in listed:
                # A listed-but-unverified property is not usable either. Keep the
                # warning distinct from the missing-property case for diagnosis.
                # Only the env var *name* is logged, never its value.
                logger.warning(
                    "GSC property override (%s) names a listed but unverified or "
                    "inaccessible property; falling back to canonical property selection",
                    PROPERTY_OVERRIDE_ENV,
                )
            else:
                # A property this account cannot see is never silently queried.
                logger.warning(
                    "GSC property override (%s) is not available to this service account; "
                    "falling back to canonical property selection",
                    PROPERTY_OVERRIDE_ENV,
                )

        if selected is None:
            domain_property = f"sc-domain:{CANONICAL_HOST}"
            if domain_property in verified:
                selected = domain_property
            else:
                selected = next(
                    (
                        url for url in verified
                        if url.startswith("https://") and _is_canonical_property(url)
                    ),
                    None,
                )

        if selected is None:
            # Preserve the legacy fallback: first verified entry, else first listed.
            selected = verified[0] if verified else (listed[0] if listed else None)

        if not selected:
            return None

        logger.info("GSC property selected: %s", selected)
        if not _is_canonical_property(selected):
            logger.warning(
                "GSC host mismatch: selected property %s is not canonical (%s)",
                selected,
                CANONICAL_HOST,
            )
        return selected

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
                "url": keys[1] if len(keys) > 1 else "",
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
