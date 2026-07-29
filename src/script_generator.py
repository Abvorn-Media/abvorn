"""Script generator — creates platform-optimized viral scripts."""

import logging
from typing import Dict, Any, List

from src.humanizer_engine import HumanizerEngine

logger = logging.getLogger("abvorn.script_generator")

_humanizer = HumanizerEngine()

DEFAULT_HOOKS = {
    "tiktok": [
        "POV: You just found the best {product_type} under ${max_price}",
        "Stop buying {product_type} before watching this",
        "This {product_type} changed everything for me",
    ],
    "youtube_short": [
        "The {product_type} that actually delivers on its promises",
        "I tested 10 {product_type}s — here's the only one worth buying",
        "Nobody talks about this {product_type}, but it's a game-changer",
    ],
    "instagram_reel": [
        "The {product_type} I wish I found sooner",
        "3 reasons this {product_type} is worth every penny",
        "If you buy ONE {product_type} this year, make it this",
    ],
    "x": [
        "The best {product_type} I've tested this year: {score}/10",
        "{product_name} review: {label}. Here's why it (or doesn't) justify the price.",
        "Honest take on the {product_type} everyone's talking about",
    ],
    "linkedin": [
        "After researching 50+ {product_type} options, here's what the data says",
        "The {product_type} buying decision is harder than it should be — here's how to simplify it",
        "Why most {product_type} recommendations miss the mark",
    ],
}

def generate_viral_script(verdict: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """
    Generate a platform-optimized viral script from verdict data.
    
    Args:
        verdict: Product verdict from VerdictEngine
        platform: Target platform (tiktok, youtube_short, instagram_reel, x, linkedin)
        
    Returns:
        Dict with hook, script body, key_points, hashtags, word_count
    """
    product_name = verdict.get("product_name", "this product")
    overall = verdict.get("overall", 0)
    label = verdict.get("label", "")
    breakdown = verdict.get("breakdown", {})
    summary = verdict.get("summary", "")
    
    hooks = DEFAULT_HOOKS.get(platform, DEFAULT_HOOKS["youtube_short"])
    hook = hooks[hash(product_name) % len(hooks)].format(
        product_type=product_name.split()[0],
        max_price=str(int(verdict.get("product_data", {}).get("price", 200))),
        product_name=product_name,
        score=overall,
        label=label.replace("🏆 EXCEPTIONAL", "").replace("⭐ EXCELLENT", "").strip(),
    )
    
    key_points = _extract_key_points(breakdown, overall)
    
    body_template = _get_body_template(platform)
    body = body_template.format(
        hook=hook,
        product=product_name,
        score=overall,
        label=label,
        points="\n".join(f"• {p}" for p in key_points),
        summary=summary,
    )
    
    hashtags = _generate_hashtags(product_name, platform)

    if platform in ("youtube_short", "youtube"):
        body = _humanizer.humanize_youtube_script(body)
    elif platform == "tiktok":
        body = _humanizer.humanize_tiktok_script(body)

    return {
        "platform": platform,
        "hook": hook,
        "script": body,
        "key_points": key_points,
        "hashtags": hashtags,
        "word_count": len(body.split()),
    }


def _extract_key_points(breakdown: Dict[str, float], overall: float) -> List[str]:
    """Extract top 3 selling points from verdict breakdown."""
    sorted_cats = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
    labels = {
        "sound": "Superior sound quality",
        "comfort": "All-day comfort",
        "battery": "All-day battery life",
        "features": "Feature-packed",
        "value": "Outstanding value",
    }
    return [labels.get(cat, f"{cat.title()}") for cat, _ in sorted_cats[:3]]


def _get_body_template(platform: str) -> str:
    templates = {
        "tiktok": "{hook}\n\n{points}\n\nLink in bio!",
        "youtube_short": "{hook}\n\n{points}\n\n{summary}",
        "instagram_reel": "Swipe for the rundown ➡️\n\n{points}\n\n{summary}",
        "x": "{hook}\n\n{points}",
        "linkedin": "{hook}\n\nAfter deep research, here's what the data says:\n{points}\n\n{summary}",
    }
    return templates.get(platform, templates["youtube_short"])


def _generate_hashtags(product_name: str, platform: str) -> List[str]:
    base = product_name.lower().replace(" ", "")[:20]
    tags = [f"#{base}", "#techreview", "#bestoftheyear", "#buyingguide"]
    if platform == "tiktok":
        tags.extend(["#tiktokmadewithme", "#fyp"])
    elif platform == "youtube_short":
        tags.extend(["#shorts", "#ytshorts"])
    elif platform == "linkedin":
        tags = ["#Technology", "#ProductReview", "#TechDecision", "#BuyingGuide"]
    return tags[:5]


if __name__ == "__main__":
    sample = {
        "product_name": "Sony XM6 Headphones",
        "overall": 9.2,
        "label": "🏆 EXCEPTIONAL",
        "breakdown": {"sound": 9.5, "comfort": 9.0, "battery": 8.5, "features": 8.0, "value": 7.5},
        "summary": "The Sony XM6 delivers studio-quality sound with all-day comfort and 30-hour battery life.",
    }
    for platform in ["tiktok", "youtube_short", "linkedin"]:
        script = generate_viral_script(sample, platform)
        print(f"\n=== {platform.upper()} ===")
        print(f"Hook: {script['hook']}")
        print(f"Words: {script['word_count']}")