"""Seed data/debates with real debate logs derived from Abvorn's published reviews.

Reads the Abvorn Verdict JSON embedded in each review page, then writes a
Colosseum-shaped debate log per product so the Pulse Engine has real data to
build its temporal influence graph from day one.

Each log mirrors the schema Colosseum._ingest_debate writes (product, strategy,
puritan_critique, final_verdict, timestamp) plus the verdict breakdown so the
graph captures per-criterion concepts.
"""
import html
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

DOCS = Path("docs")
DEBATES = Path("data/debates")
DEBATES.mkdir(parents=True, exist_ok=True)

NICHE_LABEL = {
    "4k-monitors": "4K Monitors",
    "fitness-trackers": "Fitness Trackers",
    "gaming-mice": "Gaming Mice",
    "laptops": "Laptops",
    "mechanical-keyboards": "Mechanical Keyboards",
    "smart-home": "Smart Home",
    "streaming-devices": "Streaming Devices",
    "webcams": "Webcams",
    "wireless-earbuds": "Wireless Earbuds",
    "wireless-headphones": "Wireless Headphones",
}

VERDICT_RE = re.compile(
    r'id="abvorn-verdict-data"[^>]*>([^<]*)<', re.IGNORECASE
)


def read_verdict(niche: str):
    path = DOCS / "reviews" / niche / "index.html"
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8", errors="replace")
    m = VERDICT_RE.search(raw)
    if not m:
        return None
    try:
        data = json.loads(html.unescape(m.group(1)))
        if not isinstance(data, dict) or "overall" not in data:
            return None
        data["niche"] = niche
        data["niche_label"] = NICHE_LABEL.get(niche, niche)
        return data
    except Exception:
        return None


def make_debate(v: dict, idx: int, total: int) -> dict:
    breakdown = v.get("breakdown", {}) or {}
    criteria = list(breakdown.keys()) or ["Value"]
    product = v.get("productName") or v.get("product_name") or f"{v['niche_label']} pick"
    label = v.get("label", "Average")
    overall = v.get("overall", 0)

    # Realistic strategy angles keyed to verdict strength.
    if overall >= 8:
        angle, driver = "problem_solution", "ambition"
    elif overall >= 6.5:
        angle, driver = "comparison", "curiosity"
    else:
        angle, driver = "honest_flaw", "frustration"

    # The strongest criterion becomes the hook's thesis; the weakest a violation.
    sorted_criteria = sorted(criteria, key=lambda c: breakdown.get(c, 0), reverse=True)
    strong = sorted_criteria[0] if sorted_criteria else "Value"
    weak = sorted_criteria[-1] if len(sorted_criteria) > 1 else None

    violations = []
    if weak and breakdown.get(weak, 0) < 6:
        violations.append(f"underwhelming {weak.lower()} for the price")
    if overall < 6.5:
        violations.append("value does not justify the price")

    verdict_label = label if overall >= 6.5 else "Average"

    # Stagger timestamps across the last ~15 days so the temporal axis has
    # both an "old" and a "recent" window for temporal-shift analysis.
    stamp = datetime.now() - timedelta(days=(total - idx) * 1.5)

    return {
        "product": product,
        "platform": "general",
        "strategy": {
            "angle": angle,
            "emotional_driver": driver,
            "target_audience": v["niche_label"],
        },
        "puritan_critique": {
            "approved": overall >= 6.5,
            "violations": violations,
            "suggested_fix": "anchor value to real price comparison" if violations else "",
        },
        "final_verdict": {
            "hook": f"{v['niche_label']}: the {label.lower()} pick worth your money",
            "verdict_label": verdict_label,
            "product_name": product,
            "slides": {
                "verdict": f"{label} {overall}/10",
                "breakdown": "; ".join(f"{c}: {s}" for c, s in breakdown.items()),
            },
        },
        "verdict_breakdown": breakdown,
        "bias_used": 0.5,
        "timestamp": stamp.isoformat(),
    }


def main():
    verdicts = []
    for niche in NICHE_LABEL:
        v = read_verdict(niche)
        if v:
            verdicts.append(v)
    if not verdicts:
        print("No verdict data found in docs/reviews/*/index.html")
        sys.exit(1)

    written = 0
    for idx, v in enumerate(verdicts):
        debate = make_debate(v, idx, len(verdicts))
        path = DEBATES / f"debate_{idx:02d}_{v['niche']}.json"
        path.write_text(json.dumps(debate, indent=2, ensure_ascii=False), encoding="utf-8")
        written += 1
    print(f"seeded {written} debate logs in {DEBATES}")


if __name__ == "__main__":
    main()
