"""GA4Client — pulls traffic data from Google Analytics 4 Data API."""

import logging, time
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.analytics.ga4")


class GA4Client:
    """Queries GA4 Data API for page views, sessions, and traffic sources."""

    def __init__(self, property_id: str = "", credentials_json: str = ""):
        self.property_id = property_id
        self.credentials_json = credentials_json
        self._client = None
        self._cache = {}
        self._init_client()

    def _init_client(self):
        if not self.property_id:
            return
        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.oauth2.service_account import Credentials
            if self.credentials_json:
                import json
                creds = Credentials.from_service_account_info(json.loads(self.credentials_json))
                self._client = BetaAnalyticsDataClient(credentials=creds)
            else:
                self._client = BetaAnalyticsDataClient()
        except Exception as e:
            logger.warning(f"GA4 client init failed: {e}")

    def query(self, days: int = 7) -> dict:
        """Query GA4 for page views, sessions, top pages."""
        if not self._client:
            return {"status": "unconfigured"}
        cache_key = f"ga4_{days}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached["time"] < 3600:
            return cached["data"]
        try:
            result = self._run_report(days)
            self._cache[cache_key] = {"data": result, "time": time.time()}
            return result
        except Exception as e:
            logger.warning(f"GA4 query failed: {e}")
            return {"status": "error", "error": str(e)[:100]}

    def _run_report(self, days: int) -> dict:
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Dimension, Metric,
        )
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start, end_date=end)],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"), Metric(name="sessions"),
                     Metric(name="activeUsers")],
            limit=10,
        )
        response = self._client.run_report(request)
        total_views = 0
        total_sessions = 0
        total_users = 0
        pages = []
        for row in response.rows:
            path = row.dimension_values[0].value
            views = int(row.metric_values[0].value)
            sessions = int(row.metric_values[1].value)
            users = int(row.metric_values[2].value)
            total_views += views
            total_sessions += sessions
            total_users += users
            pages.append({"path": path, "views": views, "sessions": sessions, "users": users})
        return {
            "status": "ok",
            "total_page_views": total_views,
            "total_sessions": total_sessions,
            "total_users": total_users,
            "pages": pages,
            "period_days": days,
        }