"""Viral Script Generator — converts blog content into platform-native scripts
with hook-first architecture, tested against engagement benchmarks."""

import hashlib
import logging, re
from datetime import datetime

logger = logging.getLogger("abvorn.domination.viral_script")

PLATFORM_SPECS = {
    "x": {"max_length": 280, "style": "thread", "hook_priority": "controversial"},
    "tiktok": {"max_length": 2200, "style": "script", "hook_priority": "curiosity"},
    "instagram": {"max_length": 2200, "style": "carousel", "hook_priority": "visual"},
    "linkedin": {"max_length": 3000, "style": "story", "hook_priority": "educational"},
    "telegram": {"max_length": 2000, "style": "telegram", "hook_priority": "curiosity"},
    "pinterest": {"max_length": 500, "style": "pin", "hook_priority": "useful"},
}

HOOK_TEMPLATES = {
    "curiosity": [
        "Nobody talks about this, but {niche} has a dirty secret.",
        "The {niche} you're using is probably wrong for you.",
        "I compared 10 {niche} so you don\u2019t have to. Here\u2019s the one that wins.",
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


# Niche slugs whose plain humanization would be an adjective without a noun
# ('smart-home' -> 'Smart home' reads as a broken sentence next to a count).
NICHE_LABELS = {
    "smart-home": "Smart home devices",
    "smart home": "Smart home devices",
}

# Token-level case fixes applied after humanization so brand-ish tokens keep
# their canonical spelling instead of being flattened by .capitalize().
_NICHE_CASE_FIXES = {
    "4k": "4K",
}


def _humanize_niche(niche: str) -> str:
    """Turn a URL-style slug into display copy: 'wireless-earbuds' -> 'Wireless earbuds'."""
    niche = (niche or "").strip()
    if not niche:
        return "product"
    if niche in NICHE_LABELS:
        return NICHE_LABELS[niche]
    key = niche.lower().replace("-", " ").replace("_", " ")
    if key in NICHE_LABELS:
        return NICHE_LABELS[key]
    if " " in niche:
        return niche
    words = key.split()
    label = " ".join(w.capitalize() for w in words).capitalize() if words else "product"
    for token, fix in _NICHE_CASE_FIXES.items():
        label = label.replace(token, fix)
    return label


class ViralScriptGenerator:
    """Generates platform-optimized scripts with A/B hook variants."""

    def __init__(self):
        self._history: list[dict] = []

    def generate(self, post: dict, platforms: list[str] | None = None,
                 products: list[dict] | None = None,
                 persona: dict | None = None,
                 learner=None) -> dict:
        targets = platforms or list(PLATFORM_SPECS.keys())
        result = {}
        for platform in targets:
            result[platform] = self._generate_for_platform(
                post, platform, products=products, persona=persona, learner=learner
            )
        self._history.append({
            "post_title": post.get("title", ""),
            "platforms": targets,
            "generated_at": datetime.now().isoformat(),
        })
        return result

    def _generate_for_platform(self, post: dict, platform: str,
                               products: list[dict] | None = None,
                               persona: dict | None = None,
                               learner=None) -> dict:
        spec = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["x"])
        title = post.get("title", "New Post")
        niche = post.get("niche", "product")
        summary = post.get("summary", "")
        url = post.get("url", "")
        hooks = post.get("hooks", {}).get(platform, [])
        products = products or []

        price_match = re.search(r"\$\d+[\.,]?\d*", title + " " + summary)
        price = price_match.group(0) if price_match else "$XX"

        number_match = re.search(r"\b(\d+)\b", title + " " + summary)
        num = number_match.group(1) if number_match else "5"

        brand_match = re.search(r"(Sony|Samsung|LG|Apple|Logitech|Keychron|Anker)", summary)
        brand = brand_match.group(1) if brand_match else "top"

        hook_variants = self._generate_hooks(title, niche, price, num, brand, spec["hook_priority"])
        if products:
            # Honest, product-first hook — references the real comparison set.
            count = len(products)
            hook_variants.insert(0, f"We compared {count} {_humanize_niche(niche)}. Here's what we'd actually buy.")
        learned_hooks = self._learned_hooks(learner, niche, platform)
        if learned_hooks:
            hook_variants = learned_hooks + hook_variants
        persona_variants = self._persona_hooks(niche, persona, len(products or []))
        if persona_variants:
            hook_variants = persona_variants + hook_variants
        selected_hook = hook_variants[0] if hook_variants else title[:100]
        hooks_for_testing = hook_variants[:3]
        product_count = len(products)

        if spec["style"] == "thread":
            script = self._thread_script(title, selected_hook, summary, niche, url,
                                         spec["max_length"],
                                         persona=persona, product_count=product_count)
        elif spec["style"] == "script":
            script = self._tiktok_script(title, selected_hook, summary, niche, url)
        elif spec["style"] == "carousel":
            script = self._carousel_script(title, selected_hook, summary, niche, hooks,
                                            products=products, persona=persona)
        elif spec["style"] == "story":
            script = self._linkedin_script(title, selected_hook, summary, niche, url,
                                           persona=persona, product_count=product_count)
        elif spec["style"] == "telegram":
            script = self._telegram_script(title, selected_hook, summary, niche, url,
                                           persona=persona, product_count=product_count)
        elif spec["style"] == "pin":
            script = self._pin_script(title, selected_hook, summary, niche, url, num)
        else:
            script = {"text": selected_hook[:spec["max_length"]]}

        return {
            "platform": platform,
            "hook": selected_hook,
            "hook_variants": hooks_for_testing,
            "persona": persona.get("name", "") if persona else "",
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

    def _learned_hooks(self, learner, niche: str, platform: str) -> list[str]:
        """Reuse hooks that already performed on this niche+platform.

        The learner's best_hooks() only ranks hooks with measured impressions,
        so nothing is returned until real GA4 feedback lands."""
        if not learner:
            return []
        try:
            best = learner.best_hooks(niche, platform, limit=3)
        except Exception as e:
            logger.warning(f"best_hooks lookup failed (non-fatal): {e}")
            return []
        return [
            b.get("hook_text", "") for b in best
            if b.get("hook_text") and b.get("score", 0) > 0
        ]

    def _persona_hooks(self, niche: str, persona: dict | None,
                       product_count: int = 0) -> list[str]:
        """Honest, persona-aware hooks built from the buyer's anxieties/hopes.

        Stays factual: references the real comparison set, never claims
        physical testing.
        """
        if not persona:
            return []
        psych = persona.get("psychology") or {}
        anxieties = psych.get("anxieties") or []
        hopes = psych.get("hopes") or []
        niche_label = _humanize_niche(niche)
        hooks = []
        # Keep authored casing: anxiety/hope phrases already use natural case
        # for brands ("Matter certification delays"); lowercasing them would
        # mangle proper nouns mid-sentence.
        pain = anxieties[0] if anxieties else ""
        want = hopes[0] if hopes else ""

        if product_count and pain:
            hooks.append(
                f"Tired of {pain}? We compared {product_count} {niche_label} "
                f"so you don\u2019t have to guess. Here\u2019s the pick that finally "
                f"addresses it."
            )
        if pain and want:
            hooks.append(
                f"If you\u2019re reading this, you want {want} \u2014 without {pain}. "
                f"These are the {niche_label} worth comparing."
            )
        if want:
            hooks.append(
                f"Looking for {want}? We put the real {niche_label} options "
                f"side by side so the choice is easy."
            )
        if pain:
            hooks.append(
                f"Stop settling for {niche_label} that still leave you dealing "
                f"with {pain}. Here\u2019s what actually gets compared."
            )
        return list(dict.fromkeys(hooks))[:3]

    def _persona_carousel_slide(self, persona: dict | None) -> str | None:
        """A persona-driven closing slide — no testing claims, just the
        buyer's real payoff for comparing ordinary options."""
        if not persona:
            return None
        psych = persona.get("psychology") or {}
        hopes = psych.get("hopes") or []
        want = hopes[0] if hopes else ""
        if not want:
            return None
        return (
            f"Whatever you\u2019re shopping for \u2014 {want} \u2014 these are the "
            f"real options on the table. Pick the one that fits your budget \U0001F447"
        )

    def _persona_body(self, niche: str, persona: dict | None,
                      product_count: int = 0, platform: str = "") -> str | None:
        """Persona-shaped body copy (not just a hook) for text platforms.

        Leads with the buyer's real problem and shapes the comparison around
        their hopes — honest, factual, claims no physical testing. Returns
        None when no persona is available so callers keep their generic body.
        """
        if not persona:
            return None
        psych = persona.get("psychology") or {}
        anxieties = psych.get("anxieties") or []
        hopes = psych.get("hopes") or []
        niche_label = _humanize_niche(niche)
        persona_name = persona.get("name", "")
        pain = anxieties[0] if anxieties else ""
        want = hopes[0] if hopes else ""
        if not pain and not want:
            return None

        if platform == "x":
            # One tight line for a 280-char-first-post world.
            bits = []
            if pain:
                bits.append(f"if you\u2019re tired of {pain}")
            if want:
                bits.append(f"and just want {want}")
            compare = (
                f"we compared {product_count} {niche_label} side by side"
                if product_count
                else f"these {niche_label} got compared side by side"
            )
            return f"For everyone who said \u2014 {'; '.join(bits)} \u2014 {compare}. Specs, prices, owner feedback. No fluff."[:280]

        pain_lead = f"{persona_name}: tired of {pain}." if (persona_name and pain) else (
            f"Tired of {pain}." if pain else ""
        )
        want_line = f"Most buyers want {want} \u2014 and that\u2019s exactly the bar these {niche_label} were measured against." if want else ""
        compare_line = (
            f"We compared {product_count} {niche_label} on the specs, prices, and "
            f"real owner feedback that actually matter."
            if product_count
            else f"These {niche_label} were compared on specs, prices, and real owner feedback."
        )
        lines = [ln for ln in (pain_lead, want_line, compare_line) if ln]
        return "\n\n".join(lines) if lines else None

    def _thread_script(self, title: str, hook: str, summary: str,
                       niche: str, url: str, max_len: int,
                       persona: dict | None = None,
                       product_count: int = 0) -> list[str]:
        paragraphs = [p for p in summary.split("\n") if p.strip()]
        thread = [hook[:max_len]]
        persona_line = self._persona_body(niche, persona, product_count, platform="x")
        if persona_line:
            thread.append(persona_line[:max_len])
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
                         niche: str, hooks: list,
                         products: list[dict] | None = None,
                         persona: dict | None = None) -> list[str]:
        products = products or []
        if products:
            slides = [
                f"{hook}\n\nSwipe through the real options \u2192",
            ]
            for p in products[:4]:
                name = p.get("name", "")
                price = p.get("price", "")
                role = p.get("role", "")
                line = name
                details = " · ".join(x for x in (role, price) if x)
                if details:
                    line = f"{name}\n{details}"
                slides.append(line)
            persona_slide = self._persona_carousel_slide(persona)
            if persona_slide:
                slides.append(persona_slide)
            slides.append(
                "Which one fits your budget? \U0001F447\n\nFull guide & prices in our bio \U0001F517"
            )
            return slides
        slides = [f"\U0001F4CC {hook}"]
        for h in hooks[:4]:
            slides.append(f"{h}\n\nSwipe for more \u2192")
        slides.append("Which one is YOUR pick? \U0001F447\n\nFull guide in bio \U0001F517")
        return slides

    def _linkedin_script(self, title: str, hook: str, summary: str,
                         niche: str, url: str,
                         persona: dict | None = None,
                         product_count: int = 0) -> dict:
        clean = re.sub(r"<[^>]+>", "", summary)[:800]
        paragraphs = clean.split("\n")[:4]
        body = "\n\n".join(p for p in paragraphs if p.strip())
        persona_body = self._persona_body(niche, persona, product_count, platform="linkedin")
        if persona_body:
            # Persona leads with the reader's problem, then the editorial body.
            body = "\n\n".join(x for x in (persona_body, body) if x)
        if not body:
            body = (
                f"After comparing real specs, prices, and owner "
                f"feedback across the leading {niche} options, here's what "
                f"actually stands out \u2014 and what to skip."
            )
        return {
            "headline": hook,
            "body": body,
            "engagement_question": f"What\u2019s your experience with {niche}? Drop it below \U0001F447",
            "url": url,
            "post": self._linkedin_post_text(hook, body, niche, url),
        }

    def _linkedin_post_text(self, hook: str, body: str, niche: str, url: str) -> str:
        hook = str(hook or "").lstrip(" .\u2022").strip()[:200]
        parts = [hook, body]
        question = f"What\u2019s your experience with {niche}? Drop it below \U0001F447"
        if question:
            parts.append(question)
        if url:
            parts.append(f"Full guide: {url}")
        return "\n\n".join([p for p in parts if p])[:3000]

    def _telegram_script(self, title: str, hook: str, summary: str,
                         niche: str, url: str,
                         persona: dict | None = None,
                         product_count: int = 0) -> dict:
        clean = re.sub(r"<[^>]+>", "", summary)[:700]
        paragraphs = [p.strip() for p in clean.split("\n") if p.strip()]
        body = "\n\n".join(paragraphs[:3])
        persona_body = self._persona_body(niche, persona, product_count, platform="telegram")
        if persona_body:
            body = "\n\n".join(x for x in (persona_body, body) if x)
        if not body:
            body = (
                f"After comparing real specs, prices, and owner feedback "
                f"across the leading {niche} options, here's what actually "
                f"stands out \u2014 and what to skip."
            )
        parts = [str(hook or "").lstrip(" .\u2022").strip(), body]
        if url:
            parts.append(f"Full guide: {url}")
        text = "\n\n".join([p for p in parts if p])[:1900]
        return {"text": text}

    def _pin_script(self, title: str, hook: str, summary: str,
                    niche: str, url: str, num: str) -> dict:
        return {
            "title": hook[:100],
            "description": f"{re.sub(r'<[^>]+>', '', summary)[:300]}\n\n#affiliatemarketing #{niche} #{niche.replace('-', '')}",
            "url": url,
        }

    def get_history(self) -> list[dict]:
        return list(self._history)
