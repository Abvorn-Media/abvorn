import json, logging
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.analytics")

def compute_ga4_score(views: int, users: int, avg_duration: float) -> float:
    """Weighted score: views baseline, users ×2 for engagement, duration bonus."""
    return round(views + users * 2 + avg_duration / 10, 1)


def pull_ga4_analytics(secrets: dict) -> dict:
    """Pull real page views, users, and session duration from GA4 Data API.
    
    Returns dict: {slug: {"views": int, "users": int, "avg_duration": float, "pages": int}}
    """
    ga4_property_id = secrets.get("GA4_PROPERTY_ID", "")
    ga4_creds_json = secrets.get("GA4_CREDENTIALS_JSON", "")

    if not ga4_property_id or not ga4_creds_json:
        logger.warning("GA4: GA4_PROPERTY_ID or GA4_CREDENTIALS_JSON not configured")
        return {}

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta import RunReportRequest, Metric, DateRange, Dimension
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_info(
            json.loads(ga4_creds_json)
        )
        client = BetaAnalyticsDataClient(credentials=creds)

        request = RunReportRequest(
            property=f"properties/{ga4_property_id}",
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"),
                     Metric(name="activeUsers"),
                     Metric(name="averageSessionDuration")],
            date_ranges=[DateRange(start_date="28daysAgo", end_date="today")],
            limit=50
        )
        response = client.run_report(request)
        analytics = {}
        for row in response.rows:
            path = row.dimension_values[0].value
            slug = path.strip("/").split("/")[0]
            if not slug or slug in ("", "index.html", "about.html", "contact.html", "privacy.html"):
                continue
            views = int(row.metric_values[0].value or 0)
            users = int(row.metric_values[1].value or 0)
            duration = float(row.metric_values[2].value or 0)
            if slug not in analytics:
                analytics[slug] = {"views": 0, "users": 0, "avg_duration": 0, "pages": 0}
            analytics[slug]["views"] += views
            analytics[slug]["users"] += users
            analytics[slug]["avg_duration"] = max(analytics[slug]["avg_duration"], duration)
            analytics[slug]["pages"] += 1

        logger.info(f"GA4: pulled analytics for {len(analytics)} niches")
        return analytics

    except Exception as e:
        logger.error(f"GA4 pull failed: {e}")
        return {}


def apply_analytics_feedback(state, analytics: dict):
    """Feed GA4 data back into niche priorities and persona tracking."""
    if not analytics:
        return

    for slug, data in analytics.items():
        score = compute_ga4_score(data["views"], data["users"], data["avg_duration"])
        state.update_niche_analytics(slug, data["views"], data["users"], score)

        niche = state.get_niche(slug)
        if niche:
            if score > 100 and niche["avg_quality"] >= 7.0:
                logger.info(f"  ⬆️ Double down: {slug} (score={score}, quality={niche['avg_quality']})")
                state.enqueue(slug, "content", priority=15)
            elif score < 10 and niche["total_posts"] >= 3:
                logger.info(f"  ⬇️ Pivot: {slug} (score={score}, posts={niche['total_posts']})")
                state.enqueue(slug, "content", priority=5,
                              payload={"try_new_angle": True})

    all_niches = state.get_all_niches()
    top = sorted(all_niches, key=lambda n: n["ga4_score"], reverse=True)[:3]
    if top:
        top_strs = [f"{n['slug']}({n['ga4_score']})" for n in top]
        logger.info(f"GA4 top niches: {', '.join(top_strs)}")