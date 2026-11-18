import json, os, logging
from datetime import date

from abvorn.core.models import parse_json

logger = logging.getLogger("abvorn.writer")

# Centralized affiliate tag: AMAZON_TAG secret, falling back to the real
# Associates tag. Links must never be hardcoded to a different tag, or
# commissions go to the wrong account.
def _amazon_tag() -> str:
    return os.environ.get("AMAZON_TAG") or "viraltestco-20"

CONTENT_ANGLES = {
    "problem_solution": "Lead with a vivid problem the persona faces. Agitate it. Present product as answer.",
    "comparison": "Compare this product against alternatives. Honest pros/cons for each.",
    "how_to": "Step-by-step guide showing how to achieve their goal using this product.",
    "listicle": "'5 Reasons Why [Product] Is the Best'. Easy to scan, high shareability.",
    "deep_dive": "The definitive resource — features, setup, tips, maintenance, FAQ.",
    "case_study": "Story of someone like the persona who solved their problem with this product.",
    "objection_buster": "Directly address the #1 objection. Dismantle it with facts.",
    "seasonal": "Connect product to current event, season, or trend.",
}

# Today's real date, injected into every LLM prompt so generated copy anchors
# itself to the actual current year instead of hallucinating a stale one
# (e.g. "Best X 2025" shipping in 2026).
def _today_note() -> str:
    today = date.today()
    return (
        f"TODAY IS {today.strftime('%B %d, %Y')}. The current year is "
        f"{today.year}. Use the CURRENT year ({today.year}) anywhere a year "
        f"belongs in this content — titles, images, date-stamped claims. Never "
        f"reuse an earlier year ('{today.year - 1}' is wrong if {today.year} "
        "is today's year of record). Hard rule, not a suggestion."
    )

def generate_outline(niche: str, products: list, persona: dict, router,
                     knowledge_chunks: list = None, reflection_learnings: list = None) -> dict:
    """OUTLINE stage: produce structured outline + angle selection."""
    product_names = [p.get("name", "") for p in products[:3]]
    persona_context = ""
    if persona:
        persona_context = f"""
Persona: {persona.get('name', 'Customer')}
Frustrations: {json.dumps(persona.get('frustrations', []))}
Fears: {json.dumps(persona.get('fears', []))}
Desires: {json.dumps(persona.get('desires', []))}
Tone: {persona.get('tone_of_voice', 'conversational')}"""

    expert_guidance = ""
    if knowledge_chunks:
        top = knowledge_chunks[0]["text"][:500] if knowledge_chunks else ""
        if top:
            expert_guidance = f"\n\nEXPERT GUIDANCE:\n{top}\n\nApply this principle when selecting your angle and outline."

    reflection_guidance = ""
    if reflection_learnings:
        items = "\n".join(f"- {l}" for l in reflection_learnings[:6])
        reflection_guidance = (
            f"\n\nLESSONS FROM PAST CONTENT (apply these to avoid repeating failures):\n{items}"
        )

    prompt = f"""You are a content strategist planning a buying guide for '{niche}'.
Products: {json.dumps(product_names)}
{persona_context}
{expert_guidance}
{reflection_guidance}

Available content angles and when to use them:
{json.dumps(CONTENT_ANGLES, indent=2)}

{_today_note()}

Select the BEST angle for this niche and persona. Then produce a detailed outline.

Return JSON:
{{
    "selected_angle": "angle_key",
    "angle_rationale": "why this angle works for this persona",
    "outline": [
        "H2: [Section Title] — [2-3 sentence explanation of what this section covers]",
        "H2: Next Section — ..."
    ],
    "primary_keyword": "best long-tail keyword for this niche",
    "search_intent": "commercial / informational / transactional"
}}"""
    result = router.ask(prompt, json_mode=True)
    if result:
        try:
            if isinstance(result, str):
                return json.loads(result)
            return result
        except json.JSONDecodeError:
            logger.warning("Outline JSON parse failed, using defaults")
    return {"selected_angle": "problem_solution", "outline": ["H2: Introduction", "H2: Product Review"], "primary_keyword": f"best {niche}"}


def _outline_lines(outline: dict) -> str:
    """Render outline entries as text for the draft prompt.

    Models sometimes ignore the schema and return a list of objects
    ({"heading": ..., "description": ...}) instead of strings. A bare
    "\\n".join() on that raises "sequence item 0: expected str instance, dict
    found", which used to kill the whole ContentAgent cycle. Flatten both
    shapes instead.
    """
    lines = []
    for item in (outline or {}).get("outline") or []:
        if isinstance(item, str):
            lines.append(item)
        elif isinstance(item, dict):
            head = item.get("heading") or item.get("title") or item.get("h2") or ""
            detail = item.get("description") or item.get("explanation") or ""
            line = " — ".join(str(p) for p in (head, detail) if p)
            if line:
                lines.append(line)
        elif item is not None:
            lines.append(str(item))
    return "\n".join(lines)


def _parse_draft(result):
    """Parse a draft completion; None means the model output is unusable."""
    if not isinstance(result, str):
        return result
    return parse_json(result)


def write_draft(niche: str, products: list, outline: dict, persona: dict,
                research_data: list, router, brain_context: dict = None) -> dict:
    """DRAFT stage: write full article from outline + research."""
    product_json = json.dumps(products, indent=2)[:2000]
    outline_sections = _outline_lines(outline)
    persona_context = ""
    if persona:
        persona_context = f"""
Tone: {persona.get('tone_of_voice', 'conversational and honest')}
Pain points: {json.dumps(persona.get('frustrations', []))}
Objections: {json.dumps(persona.get('objections', []))}"""

    copywriting_guidance = ""
    psych_guidance = ""
    seo_guidance = ""
    reflection_guidance = ""
    ai_seo_guidance = """
AI-SEO RULES (make content extractable so AI answers/LLMs can cite it):
- Open the article with a self-contained 40-60 word direct answer to the primary question
- Phrase H2/H3 headings as natural questions people actually ask ("What is the best ... under $50?")
- Include at least one comparison table for key product trade-offs (decision matrix)
- Give each product a standalone verdict block (Best Overall / Best Value / Premium Pick) with a one-line why
- Back claims with specific numbers and spec details; add dates to any statistics or price claims
- Always state when prices were checked (e.g., "Prices checked [today's date]")
- Include a short FAQ section with natural-language questions and 2-3 sentence answers
- Include a Methodology section explaining evaluation criteria and scoring
- For EACH product provide detailed analysis with Pros and Cons including rationale
"""
    amazon_tag = _amazon_tag()
    if brain_context:
        copy_principles = brain_context.get("copywriting_principles", [])
        if copy_principles:
            texts = [c["text"][:300] for c in copy_principles[:2]]
            copywriting_guidance = "\nCOPYWRITING PRINCIPLES:\n" + "\n---\n".join(texts)
        psych_triggers = brain_context.get("psychology_triggers", [])
        if psych_triggers:
            texts = [c["text"][:300] for c in psych_triggers[:2]]
            psych_guidance = "\nPSYCHOLOGY TRIGGERS:\n" + "\n---\n".join(texts)
        seo_tactics = brain_context.get("seo_tactics", [])
        if seo_tactics:
            texts = [c["text"][:300] for c in seo_tactics[:2]]
            seo_guidance = "\nSEO TACTICS:\n" + "\n---\n".join(texts)
        refl_learnings = brain_context.get("reflection_learnings", [])
        if refl_learnings:
            items = "\n".join(f"- {l}" for l in refl_learnings[:6])
            reflection_guidance = (
                f"\n\nLESSONS FROM PAST CONTENT (mandatory — avoid these patterns):\n{items}"
            )

    prompt = f"""Write a comprehensive buying guide for '{niche}'.

{_today_note()}

PRODUCTS TO FEATURE:
{product_json}
{copywriting_guidance}
{psych_guidance}
{seo_guidance}
{ai_seo_guidance}
{reflection_guidance}

OUTLINE TO FOLLOW:
{outline_sections}
{persona_context}

WRITING RULES:
- Lead with the reader's problem, not the product
- Be specific — use real numbers and scenarios
- Connect every feature back to a benefit for THIS reader
- Address objections head-on before the reader raises them
- Use PAS framework (Problem → Agitate → Solution) for each product section
- Include exactly 2-3 natural affiliate links within the body
- Affiliate link format: <a href='https://www.amazon.com/s?k=PRODUCT&tag={amazon_tag}' rel='nofollow sponsored' target='_blank'>check price on Amazon</a>
- End with a clear, low-risk call to action
- NEVER claim first-hand or lab testing ("based on our testing", "we tested",
  "hands-on testing", "our test bench") — Abvorn does not conduct lab tests.
  Describe research, spec comparison, and owner feedback instead.
- NEVER invent sales or popularity figures ("units sold in the past month",
  "best-selling numbers"). Only report figures present in the PRODUCTS data.

Return JSON:
{{
    "post_title": "SEO title (50-65 chars)",
    "meta_description": "Meta description (150-160 chars)",
    "intro": "<p>2-3 sentence hook paragraph (HTML)</p>",
    "article_html": "Full article body HTML (1000-2000 words)",
    "tags": ["{niche}", "buying guide", "review"],
    "lead_magnet_title": "Checklist title",
    "lead_magnet_description": "Short pitch",
    "socials": {{
        "x": "tweet (max 280 chars)",
        "linkedin": "post (max 1300 chars)",
        "pinterest": "description (max 500 chars)",
        "facebook": "1-2 paragraph post"
    }}
}}"""
    result = router.ask(prompt, json_mode=True)
    parsed = _parse_draft(result)
    if parsed is None and isinstance(result, str):
        # The long-article prompt regularly produces a response that is cut off
        # mid-string (tails end inside <table> markup or a tag attribute), so
        # no amount of fence/brace stripping can recover it. Retry once with a
        # deliberately compact output contract instead of discarding the whole
        # stage after paying for one generation.
        head = result[:120].encode("unicode_escape").decode("ascii")
        tail = result[-120:].encode("unicode_escape").decode("ascii")
        logger.warning(
            "Draft JSON incomplete (%d chars) head=%r tail=%r; retrying with a compact draft",
            len(result), head, tail,
        )
        compact_prompt = prompt.replace(
            '"Full article body HTML (1000-2000 words)"',
            '"Full article body HTML (600-900 words, plain semantic tags only)"',
        ) + (
            "\n\nOUTPUT CONTRACT (overrides the earlier table requirement): "
            "your previous response was cut off before the JSON closed. Write a "
            "SHORTER article: 600-900 words using only <h2>, <h3>, <p>, <ul>, "
            "<li>, <strong> and <a>. No <table>, no inline style attributes, no "
            "prose outside the JSON object. Close every string and the final }."
        )
        result = router.ask(compact_prompt, json_mode=True)
        parsed = _parse_draft(result)
        if parsed is None:
            logger.error("Draft JSON parse failed again after the compact retry")
    return parsed
