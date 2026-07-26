"""AnalyticsEngine — merges GA4 data with internal signals for unified reporting."""

import logging
from datetime import datetime, time

logger = logging.getLogger("abvorn.analytics.engine")


class AnalyticsEngine:
    """Collects internal signals + external GA4 data into unified insight reports."""

    def __init__(self, ga4_client=None, state=None):
        self.ga4_client = ga4_client
        self.state = state
        self.data = {}

    def collect(self, site_id: str = None) -> dict:
        """Collect all signals into one report dict."""
        report = {
            "collected_at": datetime.now().isoformat(),
            "internal": self._collect_internal(),
            "traffic": self._collect_traffic(site_id),
        }
        self.data = report
        return report

    def _collect_internal(self) -> dict:
        if not self.state:
            return {}
        return {
            "total_posts": self.state.get_meta("total_posts", 0),
            "total_ctas": self.state.get_meta("total_ctas", 0),
            "total_hooks_tested": self.state.get_meta("total_hooks_tested", 0),
            "emails_dispatched": self.state.get_meta("emails_dispatched_total", 0),
            "optimization_cycles": self.state.get_meta("optimization_cycle_count", 0),
        }

    def _collect_traffic(self, site_id: str = None) -> dict:
        if not self.ga4_client:
            return {"status": "unconfigured"}
        data = self.ga4_client.query()
        if site_id and data.get("status") == "ok":
            prefix = f"/{site_id}/"
            pages = [p for p in data.get("pages", []) if p["path"].startswith(prefix)]
            data["pages"] = pages
            data["total_page_views"] = sum(p["views"] for p in pages)
            data["total_sessions"] = sum(p["sessions"] for p in pages)
            data["total_users"] = sum(p["users"] for p in pages)
        return data

    def generate_insight_report(self, site_id: str = None) -> str:
        """Generate a human-readable insight report."""
        if not self.data:
            self.collect(site_id=site_id)
        lines = [f"# Abvorn Analytics Report", f"**Generated:** {self.data.get('collected_at', 'now')}", ""]

        traffic = self.data.get("traffic", {})
        if traffic.get("status") == "ok":
            lines.append("## Traffic (GA4)")
            lines.append(f"- **Page views:** {traffic.get('total_page_views', 0)}")
            lines.append(f"- **Sessions:** {traffic.get('total_sessions', 0)}")
            lines.append(f"- **Active users:** {traffic.get('total_users', 0)}")
            lines.append("")
            lines.append("### Top Pages")
            for p in traffic.get("pages", []):
                lines.append(f"- {p['path']}: {p['views']} views, {p['sessions']} sessions")
        else:
            lines.append("## Traffic")
            lines.append("- GA4 not configured")

        internal = self.data.get("internal", {})
        if internal:
            lines.append("")
            lines.append("## Internal Signals")
            for key, val in internal.items():
                label = key.replace("_", " ").title()
                lines.append(f"- **{label}:** {val}")

        return "\n".join(lines)