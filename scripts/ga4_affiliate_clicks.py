"""ga4_affiliate_clicks.py — report real affiliate clicks from GA4 events.

The site fires GA4 'affiliate_click' events on every buy button. Server-side
/click/ counting is dead on the static host, so this is the only real
click-through source. Use it (after distribution starts) to see which niches
are actually getting clicks before any sales happen.

Usage:
  python scripts/ga4_affiliate_clicks.py [--days 28] [--json]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="Report real GA4 affiliate clicks")
    ap.add_argument("--days", type=int, default=28, help="lookback days (default 28)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    try:
        from abvorn.core.secrets import load_secrets
        from abvorn.deploy.analytics import pull_ga4_affiliate_clicks
        from src.economic_surplus import EconomicSurplusTracker
    except ImportError as e:
        print(f"Import failed: {e}")
        sys.exit(1)

    secrets = load_secrets()
    if not secrets.get("GA4_PROPERTY_ID") or not secrets.get("GA4_CREDENTIALS_JSON"):
        print("GA4_PROPERTY_ID / GA4_CREDENTIALS_JSON not configured (boardroom env or files)")
        sys.exit(1)

    data = pull_ga4_affiliate_clicks(secrets, days=args.days) or {}
    total = sum(v["clicks"] for v in data.values())

    if args.json:
        print(json.dumps({
            "days": args.days,
            "total_clicks": total,
            "by_niche": data,
        }, indent=2))
        return

    print(f"Affiliate clicks (last {args.days} days) — from GA4 events:")
    if not data:
        print("  No clicks yet. Traffic = 0 → clicks = 0; start distribution.")
        return
    for slug, v in sorted(data.items(), key=lambda kv: -kv[1]["clicks"]):
        print(f"  {slug}: {v['clicks']} clicks")
    print(f"  TOTAL: {total} clicks")
    tracker = EconomicSurplusTracker()
    estimated = tracker.calculate_estimated_revenue(total)
    print(f"  Estimated revenue at {tracker.config.get('estimated', {}).get('estimated_conversion_rate', 0.07):.0%} conv: ${estimated:.2f}")


if __name__ == "__main__":
    main()