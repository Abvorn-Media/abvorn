"""Brand identity — the programmatic soul of Abvorn.

Every agent, pipeline, and deployer checks against this before acting.
"""

import re, logging
from abvorn.brain.principles import BRANDING_PRINCIPLES, COPYWRITING_PRINCIPLES

logger = logging.getLogger("abvorn.brand")

# ─── Visual Identity ───────────────────────────────────────────────

COLORS = {
    "primary_text": "#1a1a1a",
    "secondary_text": "#555555",
    "meta_text": "#888888",
    "background": "#ffffff",
    "surface": "#fafaf8",
    "border": "#e5e5e5",
    "accent": "#c98a2c",
    "link": "#996015",
}

FONTS = {
    "heading": "'Libre Franklin', -apple-system, sans-serif",
    "body": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "mono": "Inconsolata, 'Courier New', monospace",
}

MAX_READING_WIDTH = 720  # px

# ─── Banned Words & Phrases ────────────────────────────────────────

BANNED_PHRASES = [
    "in today's rapidly evolving landscape",
    "game-changer",
    "game changer",
    "revolutionary",
    "cutting-edge",
    "cutting edge",
    "dive into",
    "let's dive in",
    "unlock",
    "unleash",
    "supercharge",
    "in the world of",
    "when it comes to",
    "ultimately",
    "thought-provoking",
    "must-read",
    "cannot recommend enough",
    "can't recommend enough",
]

BANNED_FILLER_WORDS = [
    "ultimately", "essentially", "basically",
    "very", "really", "extremely", "incredibly",
]

BANNED_PATTERNS = [
    r"from \w+, the makers of",
]


def check_text(content: str, field: str = "content") -> list[str]:
    """Check content against brand soul rules. Returns list of violations."""
    violations = []
    lower = content.lower()

    for phrase in BANNED_PHRASES:
        if phrase in lower:
            violations.append(f"{field}: banned phrase '{phrase}'")

    for p in BANNED_PATTERNS:
        if re.search(p, content, re.IGNORECASE):
            violations.append(f"{field}: matches banned pattern '{p}'")

    for word in BANNED_FILLER_WORDS:
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, lower):
            violations.append(f"{field}: filler word '{word}'")

    return violations


def check_soul(proposed_action: str, context: dict = None) -> dict:
    """Check if a proposed action aligns with the Abvorn soul.

    Returns {"pass": True/False, "violations": [...]}
    """
    context = context or {}
    violations = []

    if "text" in context:
        violations.extend(check_text(context["text"]))

    if "title" in context:
        violations.extend(check_text(context["title"], "title"))

    soul_check = {
        "pass": len(violations) == 0,
        "violations": violations,
    }

    if not soul_check["pass"]:
        logger.warning(f"Soul check failed for '{proposed_action}': {violations}")

    return soul_check


# ─── Voice Rules (used by content generation) ──────────────────────

VOICE_RULES = """
- Every paragraph advances the reader toward a decision
- Specific over general: real prices, real specs, real numbers
- Address objections before the reader raises them
- Connect every feature back to a benefit for THIS persona
- End with a clear, low-risk call to action
- Use contractions (it's, don't, they're)
- No adverbs (very, really, extremely — delete them)
- Numbers everywhere: prices, weights, battery life, inches
- Short sentences. One idea per paragraph.
- Start paragraphs with the point. First sentence = headline.
"""


def format_voice_rules() -> str:
    """Return formatted voice rules for injection into generation prompts."""
    return VOICE_RULES


# ─── Disclosure Templates ──────────────────────────────────────────

DISCLOSURE_BANNER = "We independently review everything we recommend. When you buy through our links, we may earn a commission."

TRUST_SIGNAL = "Why you can trust Abvorn: Our team spends hours researching and testing products so you can buy with confidence. Every recommendation is independent and free from sponsor influence."

AFFILIATE_FOOTER = "As an Amazon Associate we earn from qualifying purchases."


def get_disclosure_html() -> str:
    """Return the standard affiliate disclosure for blog footers."""
    return f'<p class="disclosure"><strong>{TRUST_SIGNAL}</strong></p><p class="disclosure">{AFFILIATE_FOOTER}</p>'


# ─── Identity ──────────────────────────────────────────────────────

MISSION = "Help people buy with confidence through honest, researched recommendations."

VISION = "A world where the best product recommendation for every purchase — in every niche — is written by Abvorn and read by the person who needs it."

MOTTO = "Buy with confidence."


def get_mission() -> str:
    return MISSION


def get_vision() -> str:
    return VISION


def get_motto() -> str:
    return MOTTO