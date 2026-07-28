"""Viral Script Generator — converts blog content into platform-native scripts
with hook-first architecture, tested against engagement benchmarks."""

import logging, re, textwrap
from datetime import datetime

logger = logging.getLogger("abvorn.domination.viral_script")

PLATFORM_SPECS = {
    "x": {"max_length": 280, "style": "thread", "hook_priority": "controversial"},
    "tiktok": {"max_length": 2200, "style": "script", "hook_priority": "curiosity"},
    "instagram": {"max_length": 2200, "style": "carousel", "hook_priority": "visual"},
    "linkedin": {"max_length": 3000, "style": "story", "hook_priority": "educational"},
    "pinterest": {"max_length": 500, "style": "pin", "hook_priority": "useful"},
}

HOOK_TEMPLATES = {
    "curiosity": [
        "Nobody talks about this, but {niche} has a dirty secret.",
        "The {niche} you're using is probably wrong for you.",
        "I tested 10 {niche} so you don\u2019t have to. Here\u2019s the one that won.",
        "Stop buying {niche} before watching this.",
        "This {price} {niche} outperforms everything I\u2019ve tried.",
    ],
    "controversial": [
        "Hot take: your favorite {niche} isn\u2019t actually good.",
        "Unpopular opinion: most {niche} reviews are paid lies.",
        "Here\u2019s why professionals don\u2019t use {brand_name}.",
        "The {niche} industry is lying to you about what matters.",
        "Everyone recommends {brand_name}. I\u2019m here to tell you why they\u2019re wrong.",
    ],
    "educational": [
        "How to choose the right {niche} in {num_steps} steps.",
        "The only {niche} buying guide you\u2019ll need this year.",
        "What nobody tells you about buying {niche} online.",
        "I wasted {years} buying wrong {niche}. Don\u2019t be me.",
        "The science behind choosing the perfect {niche}.",
    ],
        "visual": [
            "POV: You finally found the perfect {niche}.",
            "Which {niche} are you picking? \U0001F440",
            "The transformation this {niche} brings is insane.",
            "Before you buy another {niche}, watch this.",
            "Your {niche} setup is incomplete without this.",
        ],
    "useful": [
        "Save this {niche} checklist for your next purchase.",
        "{num_steps} things to check before buying {niche}.",
        "The ultimate {niche} comparison for {year}.",
        "Don\u2019t buy {niche} until you\u2019ve read this.",
        "This {niche} hack will save you {price}.",
    ],
}


class ViralScriptGenerator:
    """Generates platform-optimized scripts with A/B hook variants."""

    def __init__(self):
        self._history: list[dict] = []

    def generate(self, post: dict, platforms: list[str] | None = None) -> dict:
        targets = platforms or list(PLATFORM_SPECS.keys())
        result = {}
        for platform in targets:
            result[platform] = self._generate_for_platform(post, platform)
        self._history.append({
            "post_title": post.get("title", ""),
            "platforms": targets,
            "generated_at": datetime.now().isoformat(),
        })
        return result

    def _generate_for_platform(self, post: dict, platform: str) -> dict:
        spec = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["x"])
        title = post.get("title", "New Post")
        niche = post.get("niche", "product")
        summary = post.get("summary", "")
        url = post.get("url", "")
        hooks = post.get("hooks", {}).get(platform, [])

        price_match = re.search(r"\$\d+[\.,]?\d*", title + " " + summary)
        price = price_match.group(0) if price_match else "$XX"

        number_match = re.search(r"\b(\d+)\b", title + " " + summary)
        num = number_match.group(1) if number_match else "5"

        brand_match = re.search(r"(Sony|Samsung|LG|Apple|Logitech|Keychron|Anker)", summary)
        brand = brand_match.group(1) if brand_match else "top"

        hook_variants = self._generate_hooks(title, niche, price, num, brand, spec["hook_priority"])
        selected_hook = hook_variants[0] if hook_variants else title[:100]
        hooks_for_testing = hook_variants[:3]

        if spec["style"] == "thread":
            script = self._thread_script(title, selected_hook, summary, niche, url, spec["max_length"])
        elif spec["style"] == "script":
            script = self._tiktok_script(title, selected_hook, summary, niche, url)
        elif spec["style"] == "carousel":
            script = self._carousel_script(title, selected_hook, summary, niche, hooks)
        elif spec["style"] == "story":
            script = self._linkedin_script(title, selected_hook, summary, niche, url)
        elif spec["style"] == "pin":
            script = self._pin_script(title, selected_hook, summary, niche, num)
        else:
            script = {"text": selected_hook[:spec["max_length"]]}

        return {
            "platform": platform,
            "hook": selected_hook,
            "hook_variants": hooks_for_testing,
            "script": script,
            "char_count": len(str(script)),
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_hooks(self, title: str, niche: str, price: str,
                        num: str, brand: str, priority: str) -> list[str]:
        templates = HOOK_TEMPLATES.get(priority, HOOK_TEMPLATES["curiosity"])
        hooks = []
        for tmpl in templates:
            hook = tmpl.replace("{niche}", niche)
            hook = hook.replace("{price}", price)
            hook = hook.replace("{brand_name}", brand)
            hook = hook.replace("{num_steps}", num)
            hook = hook.replace("{years}", str(max(int(num) if num.isdigit() else 3, 2)))
            hook = hook.replace("{year}", str(datetime.now().year))
            hooks.append(hook)

        hooks.append(title[:120])
        return list(dict.fromkeys(hooks))[:5]

    def _thread_script(self, title: str, hook: str, summary: str,
                       niche: str, url: str, max_len: int) -> list[str]:
        paragraphs = [p for p in summary.split("\n") if p.strip()]
        thread = [hook[:max_len]]
        for p in paragraphs[:5]:
            clean = re.sub(r"<[^>]+>", "", p).strip()
            if clean:
                thread.append(clean[:max_len])
        thread.append(f"Full breakdown: {url}")
        return thread

    def _tiktok_script(self, title: str, hook: str, summary: str,
                       niche: str, url: str) -> dict:
        clean_summary = re.sub(r"<[^>]+>", "", summary)[:400]
        return {
            "hook": hook,
            "body": clean_summary,
            "cta": f"Link in bio for the full {niche} breakdown. Follow for more honest reviews.",
            "suggested_duration_s": 45,
            "caption": f"{hook}\n\nFull guide: {url}\n\n#affiliate #{niche.replace('-', '')} #productreview",
        }

    def _carousel_script(self, title: str, hook: str, summary: str,
                         niche: str, hooks: list) -> list[str]:
        slides = [f"\U0001F4CC {hook}"]
        for h in hooks[:4]:
            slides.append(f"{h}\n\nSwipe for more \u2192")
        slides.append(f"Which one is YOUR pick? \U0001F447\n\nFull guide in bio \U0001F517")
        return slides

    def _linkedin_script(self, title: str, hook: str, summary: str,
                         niche: str, url: str) -> dict:
        clean = re.sub(r"<[^>]+>", "", summary)[:800]
        paragraphs = clean.split("\n")[:4]
        body = "\n\n".join(p for p in paragraphs if p.strip())
        return {
            "headline": hook,
            "body": body,
            "engagement_question": f"What\u2019s your experience with {niche}? Drop it below \U0001F447",
            "url": url,
        }

    def _pin_script(self, title: str, hook: str, summary: str,
                    niche: str, num: str) -> dict:
        return {
            "title": hook[:100],
            "description": f"{re.sub(r'<[^>]+>', '', summary)[:300]}\n\n#affiliatemarketing #{niche} #{niche.replace('-', '')}",
        }

    def get_history(self) -> list[dict]:
        return list(self._history)
