"""Per-platform voice profiles — every platform has its own voice rules.

The brand soul (docs/soul.md) is the foundation. These profiles adapt it per platform.
"""

PLATFORM_VOICES: dict[str, dict] = {
    "x": {
        "tone": "conversational, punchy, opinionated",
        "sentence_length": "very short (10-20 words max)",
        "personality": "The friend who did the research and has strong opinions",
        "rules": [
            "Start with a hook that stops the scroll",
            "Every tweet must stand alone (people read threads out of order)",
            "Use line breaks between tweets, not within them",
            "Numbers and prices in every thread",
            "End with a question or CTA to drive engagement",
            "No fluff — every word earns its place",
            "Emojis: 1-2 per thread max, used deliberately",
            "Avoid: 'check out', 'click the link', 'full review' — be specific",
        ],
        "banned_patterns": [
            "🧵 (let the content speak)",
            "selling used car salesman energy",
        ],
        "bio_style": "direct, benefit-first",
        "bio_template": "Reviews of {niche}. {motto}",
    },
    "linkedin": {
        "tone": "professional, authoritative, value-first",
        "sentence_length": "medium (15-30 words)",
        "personality": "A domain expert sharing hard-earned insights",
        "rules": [
            "Lead with the insight, not the product",
            "Use data and specific numbers to build credibility",
            "Keep paragraphs to 2-3 sentences max",
            "End with a question that invites discussion",
            "No hard selling — sell the thinking, not the thing",
            "Use line breaks generously for readability",
            "Emojis: sparingly, professional ones only (✅ 📊 💡)",
            "Avoid: 'I'm excited to share', 'game-changer', hype language",
        ],
        "banned_patterns": [
            "I'm thrilled to announce",
            "game-changer",
        ],
        "bio_style": "credential-first, value-driven",
        "bio_template": "Honest {niche} reviews. Data-driven recommendations. {motto}",
    },
    "tiktok": {
        "tone": "casual, energetic, trend-aware, entertaining",
        "sentence_length": "very short (5-15 words), fast-paced",
        "personality": "A knowledgeable friend showing you a hack",
        "rules": [
            "First 3 seconds must hook — start with the payoff",
            "Use pattern interrupts ('Stop buying...', 'Here's why...')",
            "Short phrases, not full sentences",
            "Visual-first: describe what to show on screen",
            "Trend-aware: reference current formats where natural",
            "No corporate language — sound like a real person",
            "End with a save/share CTA",
            "Emojis: heavy use, trend-native",
        ],
        "banned_patterns": [
            "corporate jargon",
            "long introductions",
        ],
        "bio_style": "casual, hook-driven",
        "bio_template": "{niche} reviews you can trust 🎧",
    },
    "instagram": {
        "tone": "aspirational, visual-first, warm",
        "sentence_length": "short (10-20 words per slide)",
        "personality": "A stylish friend with great taste sharing their finds",
        "rules": [
            "First slide is the headline — make it compelling",
            "Keep captions short per slide (2-3 lines max)",
            "Use emojis naturally as bullet points",
            "End each carousel with a question",
            "Focus on lifestyle benefit, not specs",
            "Avoid walls of text — people swipe fast",
            "Hashtags: 3-5 relevant ones in caption, rest in comments",
        ],
        "banned_patterns": [
            "walls of text",
            "spec-heavy descriptions",
        ],
        "bio_style": "aspirational, benefit-driven",
        "bio_template": "Curating the best {niche} for you ✨ | {motto}",
    },
    "facebook": {
        "tone": "conversational, community-oriented, trustworthy",
        "sentence_length": "medium (15-25 words)",
        "personality": "A trusted neighbor sharing a great find",
        "rules": [
            "Lead with the problem, then the solution",
            "Write like you're talking to one person",
            "Encourage comments and shares",
            "Be helpful first, promotional second",
            "Use storytelling — 'I tested 12 pairs so you don't have to'",
            "Emojis: moderate, friendly",
            "Avoid: clickbait, too-good-to-be-true language",
        ],
        "banned_patterns": [
            "clickbait formulas",
            "LIKE if you agree (too aggressive)",
        ],
        "bio_style": "trustworthy, community-first",
        "bio_template": "Honest {niche} reviews for real people. {motto}",
    },
    "pinterest": {
        "tone": "descriptive, keyword-rich, instructional",
        "sentence_length": "medium (15-20 words)",
        "personality": "A helpful curator organizing the best options",
        "rules": [
            "Front-load keywords for search",
            "Describe the benefit, then the content",
            "Use numbers in titles ('10 Best...', '5 Things...')",
            "Include practical, actionable language",
            "End with a discovery CTA ('Save for later')",
            "Emojis: minimal, decorative only",
        ],
        "banned_patterns": [
            "vague descriptions without keywords",
        ],
        "bio_style": "keyword-rich, descriptive",
        "bio_template": "The best {niche} — reviewed and ranked. {motto}",
    },
    "medium": {
        "tone": "thoughtful, narrative, authoritative",
        "sentence_length": "varied (10-35 words, mix of short and long)",
        "personality": "A meticulous researcher sharing their full process",
        "rules": [
            "Open with a story or surprising data point",
            "Use subheadings to structure the argument",
            "Support every claim with evidence",
            "Be willing to go deep — Medium readers want depth",
            "End with a clear takeaway and discussion prompt",
            "Emojis: none or very sparing",
            "Avoid: listicles without substance, shallow takes",
        ],
        "banned_patterns": [
            "clickbait titles",
            "shallow listicles",
        ],
        "bio_style": "credential-first, depth-oriented",
        "bio_template": "In-depth {niche} reviews and buying guides. {motto}",
    },
    "youtube": {
        "tone": "engaging, scripted, retention-optimized",
        "sentence_length": "varied (8-25 words), conversational when spoken",
        "personality": "A thorough reviewer who respects your time",
        "rules": [
            "First 30 seconds must hook and state the value",
            "Use pattern: problem → solution → evidence → recommendation",
            "Keep sentences punchy for spoken delivery",
            "Use verbal signposts ('Here's what we found...', 'The key difference...')",
            "End with a clear CTA (subscribe, comment, link)",
            "Visual cues for editing: describe B-roll moments",
        ],
        "banned_patterns": [
            "long, rambling intros",
            "begging for likes",
        ],
        "bio_style": "authoritative, channel-focused",
        "bio_template": "{niche} reviews, tested honestly. {motto}",
    },
}


def get_voice(platform: str) -> dict:
    """Get the voice profile for a platform. Returns default if not found."""
    return PLATFORM_VOICES.get(platform, {
        "tone": "honest, helpful, specific",
        "sentence_length": "varied",
        "personality": "A helpful expert",
        "rules": ["Be honest and specific", "Use numbers"],
        "banned_patterns": [],
        "bio_style": "standard",
        "bio_template": "Honest {niche} reviews. {motto}",
    })


def format_voice_rules_for_prompt(platform: str) -> str:
    """Format voice rules as a prompt injection string for LLM content generation."""
    voice = get_voice(platform)
    lines = [f"PLATFORM VOICE — {platform.upper()}:"]
    lines.append(f"Tone: {voice['tone']}")
    lines.append(f"Sentence length: {voice['sentence_length']}")
    lines.append(f"Personality: {voice['personality']}")
    lines.append("Rules:")
    for r in voice.get("rules", []):
        lines.append(f"  - {r}")
    if voice.get("banned_patterns"):
        lines.append("Banned:")
        for b in voice["banned_patterns"]:
            lines.append(f"  - {b}")
    return "\n".join(lines)


def format_bio_for_platform(platform: str, niche: str = "", motto: str = "Buy with confidence") -> str:
    """Generate a brand-compliant bio adapted to the platform voice."""
    voice = get_voice(platform)
    template = voice.get("bio_template", "Honest {niche} reviews. {motto}")
    return template.format(niche=niche or "products", motto=motto)