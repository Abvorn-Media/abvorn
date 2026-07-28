"""Content Intelligence — parses the blog RSS feed, scores each post for
sentiment, engagement potential, and platform-specific virality signals."""

import logging, re, json
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import feedparser

logger = logging.getLogger("abvorn.domination.content_intel")

SENTIMENT_KEYWORDS = {
    "positive": [
        "best", "great", "excellent", "amazing", "love", "perfect",
        "recommended", "top", "winner", "worth", "affordable", "premium",
    ],
    "negative": [
        "worst", "terrible", "avoid", "poor", "bad", "fails",
        "overpriced", "disappointing", "problem", "issue", "break",
    ],
    "controversial": [
        "vs", "versus", "better", "worth it", "overrated", "underrated",
        "debate", "actually", "honest", "truth", "unpopular",
    ],
}

ENGAGEMENT_SIGNALS = {
    "hook_words": [
        "why", "how", "what", "never", "always", "secret",
        "mistake", "everyone", "worst", "best", "stop", "try",
        "these", "this", "real", "actually", "finally",
    ],
    "numbers_pattern": r"\b\d+[kKmM]?\b",
    "price_pattern": r"\$\d+[\.,]?\d*",
    "question_pattern": r"\?",
    "comparison_pattern": r"\b(better|worse|vs|versus|vs\.|than|compared)\b",
}


class ContentIntelligence:
    """Parses blog RSS and scores posts by virality potential."""

    def __init__(self, rss_url: str = "", rss_path: str | None = None):
        self.rss_url = rss_url or ""
        self.rss_path = rss_path
        self._cache: dict = {}

    def parse(self) -> list[dict]:
        """Parse RSS feed and return scored entries."""
        entries = []

        if self.rss_path and Path(self.rss_path).exists():
            raw = Path(self.rss_path).read_text(encoding="utf-8")
            feed = feedparser.parse(raw)
        elif self.rss_url:
            import requests
            try:
                resp = requests.get(self.rss_url, timeout=15)
                feed = feedparser.parse(resp.text)
            except Exception as e:
                logger.warning(f"RSS fetch failed: {e}")
                return []
        else:
            logger.warning("No RSS source configured")
            return []

        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            content_text = summary
            if hasattr(entry, "content") and entry.content:
                for c in entry.content:
                    content_text += " " + re.sub(r"<[^>]+>", "", c.get("value", ""))

            tags = []
            if hasattr(entry, "tags"):
                tags = [t.get("term", "") for t in entry.tags]

            niche = self._detect_niche(title, content_text, tags)
            score = self._score_virality(title, content_text)
            platform_hooks = self._generate_platform_hooks(title, content_text, niche)

            entries.append({
                "title": title,
                "url": link,
                "summary": summary[:500],
                "niche": niche,
                "virality_score": score["total"],
                "sentiment": score["sentiment"],
                "signals": score["signals"],
                "hooks": platform_hooks,
                "tags": tags,
                "published": entry.get("published", ""),
            })

        entries.sort(key=lambda e: e["virality_score"], reverse=True)
        logger.info(f"Content intel: parsed {len(entries)} entries")
        return entries

    def _detect_niche(self, title: str, text: str, tags: list[str]) -> str:
        combined = (title + " " + text + " " + " ".join(tags)).lower()
        niches = {
            "tv": ["tv", "television", "oled", "qled", "4k", "smart tv"],
            "laptop": ["laptop", "notebook", "macbook", "gaming laptop", "ultrabook"],
            "smart-home": ["smart home", "smart", "alexa", "google home", "homekit"],
            "monitor": ["monitor", "display", "ultrawide", "4k monitor"],
            "robot-vacuum": ["robot vacuum", "roborock", "roomba", "vacuum"],
            "webcams": ["webcam", "camera", "logitech"],
            "headphones": ["headphone", "earphone", "airpods", "sony wh"],
            "gaming-mouse": ["gaming mouse", "mouse", "razer", "logitech g"],
            "wireless-chargers": ["wireless charger", "charging pad", "qi charger"],
            "mechanical-keyboard": ["mechanical keyboard", "keyboard", "keychron"],
        }
        for niche, keywords in niches.items():
            if any(k in combined for k in keywords):
                return niche
        return "general"

    def _score_virality(self, title: str, text: str) -> dict:
        combined = (title + " " + text).lower()
        signals = {}

        hook_count = sum(
            1 for w in ENGAGEMENT_SIGNALS["hook_words"]
            if w in combined
        )
        signals["hook_density"] = min(hook_count / max(len(combined.split()), 1) * 100, 10)

        numbers = len(re.findall(ENGAGEMENT_SIGNALS["numbers_pattern"], combined))
        signals["numbers"] = min(numbers, 10)

        prices = len(re.findall(ENGAGEMENT_SIGNALS["price_pattern"], combined))
        signals["prices"] = min(prices, 5)

        questions = len(re.findall(ENGAGEMENT_SIGNALS["question_pattern"], combined))
        signals["questions"] = min(questions, 5)

        comparisons = len(re.findall(ENGAGEMENT_SIGNALS["comparison_pattern"], combined))
        signals["comparisons"] = min(comparisons, 5)

        positive = sum(1 for w in SENTIMENT_KEYWORDS["positive"] if w in combined)
        negative = sum(1 for w in SENTIMENT_KEYWORDS["negative"] if w in combined)
        controversial = sum(1 for w in SENTIMENT_KEYWORDS["controversial"] if w in combined)
        total_sentiment = positive + negative + controversial

        if total_sentiment == 0:
            sentiment = "neutral"
        elif controversial > positive and controversial > negative:
            sentiment = "controversial"
        elif positive > negative:
            sentiment = "positive"
        elif negative > positive:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        total = (
            signals["hook_density"]
            + signals["numbers"] * 1.5
            + signals["prices"] * 2
            + signals["questions"] * 1.5
            + signals["comparisons"] * 2
            + (controversial * 3)
            + (positive * 1)
        )

        return {
            "total": round(total, 1),
            "sentiment": sentiment,
            "signals": signals,
            "keyword_counts": {
                "positive": positive,
                "negative": negative,
                "controversial": controversial,
            },
        }

    def _generate_platform_hooks(self, title: str, text: str, niche: str) -> dict:
        """Generate platform-specific hooks from content."""
        hooks = {}
        combined = title + " " + text[:300]

        price_match = re.search(r"\$\d+[\.,]?\d*", combined)
        number_match = re.search(r"\d+[kKmM]?", combined)

        hooks["x"] = self._hook_for_platform(combined, niche, "x", price_match, number_match)
        hooks["tiktok"] = self._hook_for_platform(combined, niche, "tiktok", price_match, number_match)
        hooks["instagram"] = self._hook_for_platform(combined, niche, "instagram", price_match, number_match)
        hooks["linkedin"] = self._hook_for_platform(combined, niche, "linkedin", price_match, number_match)
        hooks["pinterest"] = self._hook_for_platform(combined, niche, "pinterest", price_match, number_match)

        return hooks

    def _hook_for_platform(
        self, text: str, niche: str, platform: str,
        price_match, number_match,
    ) -> list[str]:
        hooks = []
        sentences = [s.strip() for s in re.split(r"[.!?]", text) if len(s.strip()) > 10]

        for s in sentences[:3]:
            hooks.append(s[:120])

        price_str = price_match.group(0) if price_match else ""
        num_str = number_match.group(0) if number_match else ""

        if platform == "x":
            if price_str:
                hooks.append(f"This {price_str} {niche} changed my mind.")
            hooks.append(f"I tested 5 {niche} so you don't have to.")
            hooks.append(f"Stop overpaying for {niche}.")
        elif platform == "tiktok":
            if price_str:
                hooks.append(f"POV: You just found a {price_str} {niche} that actually works.")
            hooks.append(f"Everyone is sleeping on this {niche}.")
            hooks.append(f"The {niche} industry doesn't want you to know this.")
        elif platform == "instagram":
            hooks.append(f"Save this for your next {niche} purchase.")
            hooks.append(f"Which {niche} would you pick?")
            hooks.append(f"Details in the caption \u2193")
        elif platform == "linkedin":
            hooks.append(f"I spent {num_str or 'months'} researching {niche}. Here's what matters.")
            hooks.append(f"The {niche} you're buying is probably wrong.")
        elif platform == "pinterest":
            hooks.append(f"The ultimate {niche} guide for {num_str or '2026'}.")
            hooks.append(f"{niche.title()} buying checklist \u2014 save this pin!")

        return list(dict.fromkeys(hooks))[:5]

    def get_top_post(self) -> dict | None:
        entries = self.parse()
        return entries[0] if entries else None

    def get_top_n(self, n: int = 5) -> list[dict]:
        entries = self.parse()
        return entries[:n]
