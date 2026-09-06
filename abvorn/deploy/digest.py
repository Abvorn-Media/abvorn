"""Daily Telegram digest — operator pulse: new content, traffic, affiliate clicks.
Run standalone:  python -m abvorn.deploy.digest
"""

import asyncio, json, logging, sys
from datetime import datetime, timezone
from pathlib import Path
import re

logger = logging.getLogger("abvorn.deploy.digest")

from ..core.state import AbvornState
from ..core.secrets import load_secrets
from .notifier import TelegramNotifier
from .analytics import pull_ga4_analytics, pull_ga4_affiliate_clicks


def published_today(repo_docs: Path) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    count = 0
    total = 0
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2})\.html$")
    if not repo_docs.exists():
        return 0, 0
    for page in repo_docs.glob("reviews/*/*.html"):
        total += 1
        m = pattern.search(page.name)
        if m and m.group(1) == today:
            count += 1
    return count, total


def build_digest() -> dict:
    secrets = load_secrets()
    analytics = pull_ga4_analytics(secrets) or {}
    clicks = pull_ga4_affiliate_clicks(secrets, 7) or {}

    state = AbvornState(Path.home() / ".abvorn" / "state.db")
    summary_raw = state.get_meta("analytics_summary", "")
    loop_summary = {}
    try:
        loop_summary = json.loads(summary_raw) if summary_raw else {}
    except Exception:
        pass

    reviews_today, reviews_total = published_today(Path("repo-src/docs"))

    views = sum(a.get("views", 0) for a in analytics.values())
    users = sum(a.get("users", 0) for a in analytics.values())
    niches = len(analytics)
    clicks_total = sum(v.get("clicks", 0) for v in clicks.values())
    if clicks_total == 0 and isinstance(loop_summary, dict):
        clicks_total = int(loop_summary.get("affiliate_clicks") or 0)
    if views == 0 and isinstance(loop_summary, dict):
        views = int(loop_summary.get("total_views") or 0)
        niches = int(loop_summary.get("niches") or 0)

    top = max(analytics.items(), key=lambda kv: kv[1].get("views", 0)) if analytics else None
    top_line = f"🏆 <b>Top niche:</b> {top[0]} — {top[1].get('views', 0)} views" if top else "🏆 No measurable traffic yet"

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = (
        f"📊 <b>Abvorn Daily Digest</b>\n"
        f"<i>{date}</i>\n\n"
        f"📝 <b>New content today:</b> {reviews_today} review article(s)\n"
        f"📚 <b>Live reviews:</b> {reviews_total}\n"
        f"👀 <b>Traffic (28d):</b> {views} views · {users} users · {niches} niches\n"
        f"🛒 <b>Affiliate clicks (7d):</b> {clicks_total}\n"
        f"{top_line}"
    )
    return {"text": text, "views": views, "niches": niches, "clicks": clicks_total}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    try:
        digest = build_digest()
        ok = TelegramNotifier().send(digest["text"])
        logger.info("Sent digest (views=%s niches=%s clicks=%s) ok=%s",
                    digest["views"], digest["niches"], digest["clicks"], ok)
        return 0 if ok else 1
    except Exception as e:
        logger.exception("Digest failed: %s", e)
        try:
            TelegramNotifier().send(f"⚠️ Abvorn digest failed: {e}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())