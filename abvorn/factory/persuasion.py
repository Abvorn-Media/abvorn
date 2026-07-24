"""Modular persuasion pipeline stages — each stage builds a prompt section."""


def build_pre_suade(persona: dict) -> str:
    """Cialdini: frame context and establish trust before the pitch."""
    anxieties = persona.get("psychology", {}).get("anxieties", [])
    if anxieties:
        return f"You've been burned by bad {anxieties[0].lower()} before? We get it. That's why we actually tested these."
    return "We tested 20+ products so you don't have to waste money on the wrong one."


def build_awareness_match(persona: dict) -> str:
    """Schwartz: lead at the prospect's awareness level."""
    level = persona.get("psychology", {}).get("awareness_level", "problem_aware")
    name = persona.get("name", "the reader")
    mapping = {
        "unaware": f"{name} doesn't know they have a problem yet. Educate first.",
        "problem_aware": f"{name} knows they have a problem. Agitate it. Present solution.",
        "solution_aware": f"{name} knows solutions exist. Help them choose the right one.",
        "product_aware": f"{name} knows about specific products. Direct comparison.",
        "most_aware": f"{name} knows exactly what they want. Give them the best deal.",
    }
    return mapping.get(level, mapping["problem_aware"])


def build_desire_tap(persona: dict) -> str:
    """Whitman LF8: activate the right Life-Force 8 desire."""
    desire = persona.get("psychology", {}).get("primary_lf8_desire", "freedom_from_pain")
    mapping = {
        "freedom_from_pain": "Tap the desire for relief from their specific pain point.",
        "superiority": "Appeal to their desire to win, be better, dominate.",
        "comfortable_living": "Position as an investment in a better daily life.",
        "social_approval": "Show how others will perceive them positively.",
        "care_for_loved_ones": "Frame as protecting or providing for family.",
        "survival": "Frame as essential, not optional.",
        "food_enjoyment": "Appeal to sensory pleasure and enjoyment.",
        "companionship": "Frame as connection, belonging, shared experience.",
    }
    return mapping.get(desire, mapping["freedom_from_pain"])


def build_neuro_engage(persona: dict) -> str:
    """Lindstrom: mirror neuron language. Sensory-rich descriptions."""
    anxieties = persona.get("psychology", {}).get("anxieties", [])
    hopes = persona.get("psychology", {}).get("hopes", [])
    pain = anxieties[0].lower() if anxieties else "the frustration"
    hope = hopes[0].lower() if hopes else "the satisfaction"
    return f"Use sensory-rich language. Let them FEEL {pain} then imagine {hope}. Mirror neuron triggers: 'Imagine...', 'Picture this...', 'You know that feeling when...'"


def build_evidence_block(persona: dict) -> str:
    """Hoffeld: progressive commitments, address objections."""
    return """Structure evidence progressively:
1. Smallest commitment first (agree there's a problem)
2. Build case with specific data points
3. Address top 2 objections before the reader raises them
4. End with a concrete, low-risk recommendation"""


def build_scannable_structure() -> str:
    """Krug: F-pattern, billboard design."""
    return """Structure for scanning, not reading:
- Headlines must do the work (each readable alone)
- Bullet lists replace paragraphs
- Short paragraphs (1-3 sentences max)
- Clear visual hierarchy: H2 > H3 > bold"""


def build_conversion_block() -> str:
    """Ash + Pribyl: one CTA, trust signals, accurate link."""
    return """Conversion architecture:
- Singular CTA: ONE action you want them to take
- Trust signals near the CTA (testimonials, guarantees, specs)
- Accurate affiliate link to exact product buying page
- Scarcity or urgency only if genuine"""