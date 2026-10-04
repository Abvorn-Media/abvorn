"""The Abvorn Dispatch - editorial blog content engine.

Persona-driven lifestyle and utility writing that is deliberately *not* tied to
a product. Posts build trust around the reader's real problem, then the page
cross-sells exactly one relevant product as a "field kit" recommendation.

This module owns:
  - BLOG_PERSONAS / TOPIC_BANK: who we write for and what we write about
  - CROSS_SELL: topic category -> one real niche (so product research works)
  - generate_blog_post(): OUTLINE -> DRAFT -> shape into the post record
  - load_posts() / upsert_post(): persistence in data/blog/posts.json

The page rendering lives in src/blog_site.py; image sourcing in
scripts/fetch_blog_images.py; orchestration in scripts/build_blog.py.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger("abvorn.blog")

POSTS_FILE = Path("data/blog/posts.json")

# ── Personas ──────────────────────────────────────────────────────────────
# Each persona is a real reader, not a demographic bucket. The pain points and
# desires feed the prompt directly; the topic bank keeps the blog from drifting
# into product content, which is what every competitor's "blog" becomes.
BLOG_PERSONAS = {
    "weekend-escaper": {
        "name": "The Weekend Escaper",
        "tagline": "Short trips, small budgets, zero wasted hours.",
        "who": "Works full time, takes long weekends instead of long holidays, "
               "wants a city break that feels designed rather than improvised.",
        "pain_points": [
            "booking the obvious tourist trap and paying over the odds",
            "losing the first day to logistics",
            "coming home more tired than before",
        ],
        "desires": [
            "a trip that feels considered without a planner",
            "small rituals that make a strange place feel personal",
            "coming home with a story, not a spreadsheet",
        ],
        "tone": "warm, specific, a little playful; never aspirational fluff",
        "category": "travel",
    },
    "calm-desk": {
        "name": "The Calm Desk",
        "tagline": "Deep work in a small space.",
        "who": "Works from a bedroom, kitchen table or shared flat and is fighting "
               "for focus in a room that was never meant to be an office.",
        "pain_points": [
            "context-switching every few minutes",
            "noise they cannot control",
            "a desk that quietly makes them tense",
        ],
        "desires": [
            "two hours of uninterrupted flow",
            "a corner that signals 'work' the moment they sit down",
            "ending the day with a clear head",
        ],
        "tone": "calm, practical, unhurried; treats attention as a resource",
        "category": "focus",
    },
    "small-space-host": {
        "name": "The Small-Space Host",
        "tagline": "A home that works when people show up.",
        "who": "Lives in a compact flat and likes having people over without "
               "turning the evening into a production.",
        "pain_points": [
            "a room that feels cramped the moment guests arrive",
            "spending the whole night in the kitchen instead of with people",
            "never quite getting the lighting or the mood right",
        ],
        "desires": [
            "a home that feels generous even when it is small",
            "hosting that feels effortless, not performed",
            "a place guests remember for one small detail",
        ],
        "tone": "generous, tactile, sensory; notices light and texture",
        "category": "home",
    },
    "steady-habits": {
        "name": "The Steady Habits",
        "tagline": "Progress you can actually keep.",
        "who": "Has started and abandoned every wellness routine they can name "
               "and wants one that survives a normal, busy week.",
        "pain_points": [
            "all-or-nothing streaks that collapse after a bad day",
            "advice that assumes unlimited time and energy",
            "no honest way to see whether anything is working",
        ],
        "desires": [
            "a routine small enough to keep on the worst week",
            "gentle, honest feedback instead of guilt",
            "six months of quiet consistency",
        ],
        "tone": "kind, grounded, evidence-aware; never shaming",
        "category": "wellness",
    },
}

# Topic category -> exactly one real niche for the field-kit cross-sell. Every
# value must exist in src.deployment.CATEGORY_NAMES or product research fails.
CROSS_SELL = {
    "travel": "wireless-earbuds",
    "focus": "wireless-headphones",
    "home": "smart-home",
    "wellness": "fitness-trackers",
}

# ── Topic bank ────────────────────────────────────────────────────────────
# Pain-point phrased, product-free. Post titles are generated from these seeds,
# so the seed itself must never name a product.
TOPIC_BANK = {
    "weekend-escaper": [
        ("How to Plan a 3-Day City Break That Doesn't Wipe You Out",
         "A repeatable rhythm for short trips: one anchor a day, everything else left loose."),
        ("The 5-Hour Rule for Arriving Somewhere New",
         "What to do in the first few hours of a trip so the rest of it feels easy."),
        ("How to Eat Well on a City Break Without the Research Spiral",
         "Three rules for finding a good meal in an unfamiliar place."),
        ("A Packing List That Survives a Long Weekend",
         "Pack for the trip you will actually have, not the one in the brochure."),
    ],
    "calm-desk": [
        ("How to Build a Work Corner in a Room That Isn't an Office",
         "Shape a small space so sitting down switches your brain into work."),
        ("The Two-Hour Focus Block, Explained",
         "Why your best work has a start ritual, and how to give it one."),
        ("How to Work When You Can Hear Everything",
         "Practical ways to protect concentration in a noisy home."),
        ("The End-of-Day Shutdown That Ends the Day",
         "A five-minute routine that stops work leaking into your evening."),
    ],
    "small-space-host": [
        ("How to Host in a Small Flat Without the Stress Spiral",
         "The prep order that keeps you out of the kitchen and with your guests."),
        ("Lighting Is the Whole Mood: A Small-Space Guide",
         "Three cheap changes that make an evening feel intentional."),
        ("A One-Table Dinner for People You Actually Like",
         "A small-space hosting format built around conversation, not courses."),
        ("How to Make a Rented Living Room Feel Like Yours",
         "Small, reversible moves that a landlord will never notice."),
    ],
    "steady-habits": [
        ("The Minimum Viable Routine for a Chaotic Week",
         "Design a habit for your worst week, then let good weeks be a bonus."),
        ("How to Tell If a Habit Is Actually Working",
         "Gentle signals to look for when the scale and the mirror lie."),
        ("Why Streaks Break, and What to Do the Day After",
         "A recovery plan that is more important than the streak itself."),
        ("How to Make Time for Yourself Without an Hour",
         "Stack small restorative moments into a day that is already full."),
    ],
}


def _today_note() -> str:
    today = date.today()
    return (
        f"TODAY IS {today.strftime('%B %d, %Y')}. The current year is {today.year}. "
        f"Use the current year if a year belongs anywhere."
    )


# Phrases that mark text as generic AI filler. The blog's whole edge is that it
# does not sound like every other content farm; the model is told outright.
BANNED_PHRASES = [
    "in today's fast-paced world",
    "in this article",
    "whether you're",
    "look no further",
    "game-changer",
    "unlock",
    "elevate",
    "delve",
    "dive in",
    "tapestry",
    "embark",
    "navigate the landscape",
    "it's not just",
    "we've got you covered",
    "take it to the next level",
]


def _persona_block(persona: dict) -> str:
    return f"""PERSONA: {persona['name']} - {persona['tagline']}
Who they are: {persona['who']}
Pain points they would recognise:
{chr(10).join('- ' + p for p in persona['pain_points'])}
What they actually want:
{chr(10).join('- ' + d for d in persona['desires'])}
Voice: {persona['tone']}"""


def generate_blog_post(topic_title: str, topic_dek: str, persona_id: str,
                       router, products: list | None = None) -> dict | None:
    """Generate one Dispatch post and return the post record.

    The post is product-free by design; `products` (when supplied) is used only
    to inform the final field-kit blurb, never the body copy.
    """
    persona = BLOG_PERSONAS.get(persona_id)
    if not persona:
        logger.error("Unknown blog persona: %s", persona_id)
        return None

    category = persona["category"]
    cross_niche = CROSS_SELL.get(category, "")
    cross_name = ""
    try:
        from src.deployment import CATEGORY_NAMES

        cross_name = CATEGORY_NAMES.get(cross_niche, cross_niche.replace("-", " ").title())
    except Exception:
        cross_name = cross_niche.replace("-", " ").title()

    product_names = [p.get("name", "") for p in (products or [])][:3]
    product_block = ""
    if product_names:
        product_block = (
            "\nProducts available for the closing field-kit line (mentioned once, "
            "never pushed): " + "; ".join(product_names)
        )

    banned = "; ".join(f'"{p}"' for p in BANNED_PHRASES)

    prompt = f"""You are the editor of The Abvorn Dispatch, an independent
publication for people who research before they spend. Write a genuine,
useful article. It is NOT a product review and must NOT sell anything.

{_persona_block(persona)}

ARTICLE SEED (write your OWN title in Title Case - do not copy the seed line)
Title direction: {topic_title}
Angle: {topic_dek}

{_today_note()}

HARD RULES
- The body must not name or recommend any specific product, brand, store or
  price. Guide the reader on the decision, not the purchase.
- Lead with the reader's real problem. Be specific: name the moment it goes
  wrong, then give a concrete way through it.
- Warm, confident, plain English. Short sentences. Second person ("you").
- Positivity is about respect for the reader, not cheerleading. No hype.
- Never claim first-hand lab testing ("we tested", "our test bench"). This is
  a research-driven publication, not a lab.
- NO statistics at all: no percentages, no "studies show", no "research says",
  no minutes-per-day figures. Describe experience and principle only. Inventing
  a number is the single fastest way to fail this brief.
- Include exactly one short, natural transition sentence where a margin note
  would sit, but do not write the note itself.
- BANNED phrases (using any of these fails the piece): {banned}
- British-neutral spelling, no emoji. Headings and the title are in Title Case.

STRUCTURE
Return JSON exactly in this shape:
{{
  "title": "Title Case, 45-65 chars, no product names, no colon unless natural",
  "dek": "one-sentence subtitle, under 140 chars, Title-friendly",
  "meta_description": "150-158 chars, plain and honest",
  "intro": "<p>2-3 sentence hook that names the problem (HTML)</p>",
  "sections": [
    {{
      "heading": "Title Case heading",
      "html": "<p>2-4 paragraphs of HTML. Use <p>, <ul><li>, and <strong> where they help. No <h2>.</p>",
      "note": "a 12-24 word margin note that adds a different angle, a caveat, or a small aside - not a summary"
    }}
  ],
  "pull_quote": "one memorable sentence lifted from the piece",
  "faqs": [
    {{"question": "natural question the reader would ask", "answer": "2-3 sentence answer"}}
  ],
  "tags": ["3-5 lowercase topical tags"],
  "cross_sell_blurb": "one sentence that frames what to look for in {cross_name}, product-free",
  "image_queries": ["5-6 short Pexels photo search phrases: concrete, photographable, everyday. Each must name a real object or place plus the light or time of day, e.g. 'sunlit kitchen table with laptop', 'small desk beside a window at dusk'. Never abstract words (focus, calm, productivity), never brands or text. First query is the hero."]
}}

Write 5 to 7 sections. Aim for 900-1300 words total. The margin notes are the
signature of this publication - make each one worth reading on its own.{product_block}"""

    result = router.ask(prompt, json_mode=True, task="draft")
    if not result:
        logger.error("Blog draft returned nothing for %r", topic_title)
        return None
    if isinstance(result, str):
        try:
            data = json.loads(result)
        except json.JSONDecodeError:
            logger.error("Blog draft JSON parse failed")
            return None
    else:
        data = result

    sections = []
    for s in data.get("sections", []):
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading", "")).strip()
        html = str(s.get("html", "")).strip()
        if not heading or not html:
            continue
        sections.append({
            "heading": heading,
            "html": html,
            "note": str(s.get("note", "")).strip(),
        })
    if len(sections) < 3:
        logger.error("Blog draft had too few usable sections (%d)", len(sections))
        return None

    title = _norm(str(data.get("title", topic_title)).strip())
    return _normalize_record({
        "slug": slugify(title),
        "title": title,
        "dek": str(data.get("dek", topic_dek)).strip(),
        "meta_description": str(data.get("meta_description", "")).strip(),
        "persona_id": persona_id,
        "persona": persona["name"],
        "category": category,
        "intro": str(data.get("intro", "")).strip(),
        "sections": sections,
        "pull_quote": str(data.get("pull_quote", "")).strip(),
        "faqs": [
            {"question": str(f.get("question", "")).strip(),
             "answer": str(f.get("answer", "")).strip()}
            for f in data.get("faqs", []) if isinstance(f, dict)
        ],
        "tags": [str(t).strip().lower() for t in data.get("tags", []) if str(t).strip()],
        "image_queries": [str(q).strip() for q in data.get("image_queries", []) if str(q).strip()],
        "cross_sell_niche": cross_niche,
        "cross_sell_name": cross_name,
        "cross_sell_blurb": str(data.get("cross_sell_blurb", "")).strip(),
        "published": date.today().isoformat(),
        "hero": None,
        "images": [],
        "products": [],
    })


def _norm(text: str) -> str:
    """Fold invisible/risky unicode that survives JSON but breaks consoles."""
    return (text.replace("\u2011", "-").replace("\u00a0", " ")
                .replace("\u2018", "'").replace("\u2019", "'")
                .replace("\u201c", '"').replace("\u201d", '"'))


def _normalize_record(obj):
    if isinstance(obj, str):
        return _norm(obj)
    if isinstance(obj, list):
        return [_normalize_record(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _normalize_record(v) for k, v in obj.items()}
    return obj


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "dispatch"


def read_minutes(post: dict) -> int:
    words = len(re.sub(r"<[^>]+>", " ", post.get("intro", "")).split())
    for s in post.get("sections", []):
        words += len(re.sub(r"<[^>]+>", " ", s.get("html", "")).split())
    return max(3, round(words / 225))


def load_posts() -> dict:
    """Return {slug: post}. Never raises."""
    try:
        if POSTS_FILE.exists():
            data = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {p.get("slug", ""): p for p in data if isinstance(p, dict)}
    except Exception as e:
        logger.warning("Could not read blog posts: %s", e)
    return {}


def save_posts(posts: dict) -> None:
    POSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    POSTS_FILE.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def upsert_post(post: dict) -> dict:
    posts = load_posts()
    posts[post["slug"]] = post
    save_posts(posts)
    return posts
