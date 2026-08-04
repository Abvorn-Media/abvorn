"""content_generation.py — Content generation functions for Abvorn.

All functions that generate article content, outlines, and social data live here.
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.ai_sql import QueryPlan
from src.infrastructure import infra_reporter
from src.energy_accounting import energy_accounting
from src.agent_reach_adapter import get_agent_reach_adapter
from src.article_design import sanitize_article_html, upgrade_product_image

_cost_per_1k = {
    "openai": 0.002,
    "anthropic": 0.003,
    "gemini": 0.001,
    "deepseek": 0.0005,
    "kimi": 0.0008,
    "kilogateway": 0.0005,
    "default": 0.0005,
}

logger = logging.getLogger(__name__)

# Reference to global ai_sql instance (set by run_cycle.py)
ai_sql = None


def set_ai_sql(instance):
    """Set the global AISQL instance."""
    global ai_sql
    ai_sql = instance


def _track_call(niche: str, provider: str, tokens: int, latency_ms: float = 0.0):
    cost = tokens * (_cost_per_1k.get(provider, _cost_per_1k["default"]) / 1000.0)
    infra_reporter.report_article_cost("", provider, cost, latency_ms, tokens, niche)
    energy_accounting.record_usage(provider, tokens, latency_ms)


def generate_outline(niche, products, knowledge_core=None, workflow_engine=None, social_data=None):
    names = json.dumps([p.get("name", "") for p in products[:3]])

    # Build knowledge context
    knowledge_context = ""
    if knowledge_core:
        try:
            brief = knowledge_core.generate_strategy_brief(niche)
            insights = brief.get("insights", [])
            trend = brief.get("trend", "no_data")
            if insights:
                knowledge_context = f"\n\n📚 Strategic Insights for {niche} (trend: {trend}):\n" + "\n".join(
                    f"- {i}" for i in insights[:5]
                )
        except Exception:
            pass

    # Build social sentiment context
    social_context = ""
    if social_data:
        parts = []
        for platform, items in social_data.items():
            if isinstance(items, list) and items:
                samples = items[:3]
                parts.append(f"{platform}:\n" + "\n".join(
                    f"- {item.get('text', item.get('title', ''))[:100]}"
                    for item in samples
                ))
        if parts:
            social_context = "\n\n💬 Real-Time Social Sentiment:\n" + "\n\n".join(parts)

    prompt = f"""You are a content strategist planning a buying guide for '{niche}'.
Products: {names}{knowledge_context}{social_context}

Return a JSON object with:
- outline: array of H2 section headings (e.g. ["Introduction", "What to Look For", "Product Reviews", "Buying Guide", "FAQ", "Conclusion"])
- selected_angle: one of: problem_solution, comparison, how_to, listicle, deep_dive, objection_buster
- primary_keyword: the main SEO keyword for this guide
- post_title: compelling title for the buying guide
- meta_description: 1-2 sentence SEO description"""
    # Use workflow config for AI params when available
    ai_temp = 0.7
    ai_max_tokens = 500
    if workflow_engine:
        wf = workflow_engine.workflows.get("quality")
        if wf:
            ai_temp = wf.temperature
            ai_max_tokens = wf.max_tokens
    t0 = time.time()
    result = ai_sql.query(QueryPlan(
        system_prompt="You are an expert content strategist returning structured JSON data.",
        user_prompt=prompt,
        params={"temperature": ai_temp, "max_tokens": ai_max_tokens, "format": "json"},
    ))
    result_text = result.content
    _track_call(niche, result.provider_used, result.tokens_used, (time.time() - t0) * 1000)
    if not result_text:
        return None
    try:
        return json.loads(result_text)
    except:
        m = re.search(r'\{.*\}', result_text, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
    return None



def write_draft(niche, products, outline, knowledge_core=None, workflow_engine=None, social_data=None):
    products_text = json.dumps(products, indent=2)
    post_title = outline.get("post_title", f"Best {niche} — Expert Review")
    meta_desc = outline.get("meta_description", f"Find the best {niche} with our expert guide.")
    angle = outline.get("selected_angle", "problem_solution")
    keyword = outline.get("primary_keyword", f"best {niche}")
    outline_sections = json.dumps(outline.get("outline", []))

    # Inject knowledge core insights if available
    knowledge_context = ""
    if knowledge_core:
        try:
            brief = knowledge_core.generate_strategy_brief(niche)
            insights = brief.get("insights", [])
            if insights:
                knowledge_context = "\n\n📚 Business Strategy Insights:\n" + "\n".join(
                    f"- {i}" for i in insights[:5]
                )
        except Exception:
            pass

    # Inject social sentiment data if available
    social_context = ""
    if social_data:
        parts = []
        for platform, items in social_data.items():
            if isinstance(items, list) and items:
                samples = items[:3]
                parts.append(f"{platform}:\n" + "\n".join(
                    f"- {item.get('text', item.get('title', ''))[:100]}"
                    for item in samples
                ))
        if parts:
            social_context = "\n\n💬 Real-Time Social Sentiment:\n" + "\n\n".join(parts)

    # Use workflow config for AI params when available
    ai_temp = 0.7
    ai_max_tokens_intro = 500
    ai_max_tokens_article = 2000
    if workflow_engine:
        wf = workflow_engine.workflows.get("quality")
        if wf:
            ai_temp = wf.temperature
            ai_max_tokens_intro = wf.max_tokens
            ai_max_tokens_article = wf.max_tokens

    intro_prompt = f"""Write the introduction for a buying guide titled '{post_title}' about {niche}.
Angle: {angle}
Keyword: {keyword}
Products: {products_text}{knowledge_context}{social_context}

Write 2-3 short paragraphs (as HTML) that hook the reader, state the problem, and introduce the solution.
Return ONLY the HTML paragraphs, wrapped in <p> tags."""
    t0 = time.time()
    intro_result = ai_sql.query(QueryPlan(
        system_prompt="You write concise, honest product review copy.",
        user_prompt=intro_prompt,
        params={"temperature": ai_temp, "max_tokens": ai_max_tokens_intro},
    ))
    intro_html = intro_result.content
    _track_call(niche, intro_result.provider_used, intro_result.tokens_used, (time.time() - t0) * 1000)
    if not intro_html:
        intro_html = "<p>We tested the top products to find the ones worth your money.</p>"
    intro_html = sanitize_article_html(intro_html, strip_leading_intro=False)

    article_prompt = f"""Write the full article body for '{post_title}' about {niche}.
Products: {products_text}
Outline sections: {outline_sections}
Angle: {angle}
Keyword: {keyword}{knowledge_context}{social_context}

Write the COMPLETE article body as HTML. Follow the outline sections as <h2> headings.
For each product, include: a brief intro, key features, pros/cons, and a bottom-line recommendation.
Use <p> for paragraphs, <ul>/<li> for lists, <strong> for emphasis.
Be honest, specific (use real prices/numbers), and scannable.
Return ONLY the HTML."""
    t0 = time.time()
    article_result = ai_sql.query(QueryPlan(
        system_prompt="You write thorough, honest product reviews with specific details and real prices.",
        user_prompt=article_prompt,
        params={"temperature": ai_temp, "max_tokens": ai_max_tokens_article},
    ))
    article_html = article_result.content
    _track_call(niche, article_result.provider_used, article_result.tokens_used, (time.time() - t0) * 1000)
    if not article_html:
        article_html = "<p>We're reviewing the top products in this category.</p>"
    article_html = sanitize_article_html(article_html)

    # Upgrade any embedded product thumbnails to hi-res studio-ready images.
    products = [dict(p) for p in products]
    for p in products:
        if p.get("image"):
            p["image"] = upgrade_product_image(p["image"])
    products_text = json.dumps(products, indent=2)

    return {
        "post_title": post_title,
        "meta_description": meta_desc,
        "intro": intro_html,
        "article_html": article_html,
        "product_name": products[0].get("name", ""),
        "products": products,
    }



def fetch_social_sentiment(niche_name: str, limit_per_platform: int = 5) -> Dict[str, Any]:
    """Fetch real-time social sentiment data for a niche."""
    try:
        adapter = get_agent_reach_adapter()
        results = adapter.fetch_social_data(
            query=f"{niche_name} product review OR best {niche_name}",
            platforms=["twitter", "reddit", "youtube"],
            limit_per_platform=limit_per_platform,
        )
        return results
    except Exception as e:
        logger.warning(f"Social sentiment fetch failed for {niche_name}: {e}")
        return {}

def generate_persona_content_plan(niche_name, persona, awareness_level="problem_aware",
                                   products=None, content_type_override=None):
    """Generate a content plan matrix for a persona at a given awareness level.
    Returns a dict with title, angle, structure, and SEO metadata — no API call needed."""
    p_name = persona.get("name", "Your Reader")
    frustrations = persona.get("psychology", {}).get("anxieties", ["the problem"])
    hopes = persona.get("psychology", {}).get("hopes", ["a solution"])
    cialdini = persona.get("psychology", {}).get("cialdini_principles", ["social_proof"])
    hoffeld = persona.get("psychology", {}).get("hoffeld_buying_reason", "gain")

    if content_type_override:
        ct = next((v for v in CONTENT_TYPE_MAP.values() if v["type"] == content_type_override),
                  CONTENT_TYPE_MAP["problem_aware"])
    else:
        ct = CONTENT_TYPE_MAP.get(awareness_level, CONTENT_TYPE_MAP["problem_aware"])

    frust = frustrations[0] if frustrations else "the problem"
    hope = hopes[0] if hopes else "a solution"
    niche_lower = niche_name.lower()

    title_templates = {
        "problem_discovery": [
            f"Are You {frust.title()}? Here's What No One Tells You About {niche_lower}",
            f"5 Signs Your {frust.title()} Is Costing You More Than You Think",
            f"Stop Ignoring {frust.title()} — Why {niche_lower} Matters More Than Ever",
        ],
        "problem_deep_dive": [
            f"Why Most People Get {niche_lower} Wrong (And Pay for It)",
            f"The Hidden Cost of Bad {niche_lower}: What Nobody Talks About",
            f"Your {niche_lower} Is Holding You Back. Here's How to Fix It",
        ],
        "how_to": [
            f"How to {hope.title()} Without Breaking the Bank",
            f"{niche_lower} Done Right: A Step-by-Step Guide for {p_name}",
            f"The {p_name}'s Guide to {hope.title()}",
        ],
        "solution_comparison": [
            f"{niche_lower}: The {p_name}'s Dilemma — Which Path Is Right for You?",
            f"Should You Prioritize {hopes[0] if len(hopes)>1 else 'Quality'} or {frust}?",
        ],
        "product_review": [
            f"Best {niche_lower} for {p_name}: Real Testing, Honest Verdict",
            f"We Tested the Top {niche_lower} So {p_name} Doesn't Have To",
        ],
        "micro_comparison": [
            f"[Product A] vs [Product B]: The {p_name}'s Verdict",
            f"Which {niche_lower} Should {p_name} Buy? The 90-Second Answer",
        ],
        "cross_sell": [
            f"The Ultimate {niche_lower} Kit for {p_name}",
            f"3 Products {p_name} Needs for the Perfect {niche_lower} Setup",
        ],
    }

    titles = title_templates.get(ct["type"], [f"Best {niche_lower} for {p_name}"])
    selected_title = titles[0]

    return {
        "persona": p_name,
        "awareness_level": awareness_level,
        "content_type": ct["type"],
        "content_label": ct["label"],
        "purpose": ct["purpose"],
        "suggested_title": selected_title,
        "alternative_titles": titles[1:],
        "angle": f"Help {p_name} overcome {frust} to achieve {hope}",
        "primary_keyword": f"best {niche_lower} for {p_name.lower().replace(' ','-')}",
        "meta_description_template": f"Struggling with {frust}? Our {ct['label'].lower()} helps {p_name} {hope[:40]}. Expert guidance, real results.",
        "persuasion_levers": {
            "cialdini": cialdini,
            "hoffeld": hoffeld,
        },
        "suggested_structure": [
            f"Hook: Name {p_name}'s specific {frust}",
            f"Agitate: Why {frust} costs them time/money/peace",
            "Solution: Present the method or approach",
            "Trust: Specific examples, data, or social proof",
            "Action: Clear next step with product recommendation",
        ],
    }



def generate_persona_article(niche_name, persona, awareness_level,
                               products=None, content_type_override=None):
    """Generate full persona-specific article using AISQL.
    Falls back to returning a content plan + placeholder structure."""
    plan = generate_persona_content_plan(niche_name, persona, awareness_level,
                                          products, content_type_override)

    # Check if AISQL is available (has working providers)
    ai_sql_available = any(p.health_check() for p in ai_sql.providers.values())
    if not ai_sql_available:
        plan["mode"] = "manual"
        plan["article_html"] = _persona_article_template(plan, persona, niche_name, products)
        plan["instructions"] = "Replace placeholder text with original content. See mission phase 4 for guidelines."
        return plan

    # Generate full article via AISQL
    p = persona.get("psychology", {})
    frustrations = p.get("anxieties", [])
    hopes = p.get("hopes", [])
    prod_names = json.dumps([pr.get("name", "") for pr in (products or [])])

    prompt = f"""You are writing a {plan['content_label']} article for Abvorn.

NICHE: {niche_name}
CONTENT TYPE: {plan['content_type']} — {plan['purpose']}
PRIMARY KEYWORD: {plan['primary_keyword']}

TARGET READER — {persona.get('name', 'Your Reader')}
Their frustrations: {json.dumps(frustrations)}
Their hopes: {json.dumps(hopes)}
Awareness level: {awareness_level}

Products to feature: {prod_names or 'None yet — write generically'}

INSTRUCTIONS:
1. Lead with the persona's frustration. Make them feel seen.
2. Agitate the problem — why it costs them time/money/peace of mind.
3. Present the solution (method, not just product).
4. Cross-sell naturally: if mentioning a product, use an affiliate link.
5. End with a clear, low-friction CTA.

Return JSON:
{{
  "post_title": "Compelling title (50-65 chars)",
  "meta_description": "SEO meta (150-160 chars) that speaks to the persona",
  "intro": "2-3 paragraph hook (HTML)",
  "article_html": "Full article body (800-1200 words HTML). Include 1-2 natural affiliate links with tag=viraltestco-20"
}}"""

    result = ai_sql.query(QueryPlan(
        system_prompt="You are an expert content writer for Abvorn, an independent product review platform.",
        user_prompt=prompt,
        params={"temperature": 0.9, "max_tokens": 1500, "format": "json"},
    )).content
    if not result:
        plan["mode"] = "fallback"
        plan["article_html"] = _persona_article_template(plan, persona, niche_name, products)
        return plan

    import json as _json
    try:
        data = _json.loads(result)
    except Exception:
        plan["mode"] = "fallback"
        plan["article_html"] = _persona_article_template(plan, persona, niche_name, products)
        return plan

    plan["mode"] = "ai_generated"
    plan["post_title"] = data.get("post_title", plan["suggested_title"])
    plan["meta_description"] = data.get("meta_description", "")
    plan["intro"] = data.get("intro", "")
    plan["article_html"] = data.get("article_html", "")
    return plan



def _persona_article_template(plan, persona, niche_name, products=None):
    """Generate a well-structured HTML template for manual filling."""
    p_name = persona.get("name", "Your Reader")
    frustrations = persona.get("psychology", {}).get("anxieties", [])
    hopes = persona.get("psychology", {}).get("hopes", [])
    frust = frustrations[0] if frustrations else "this problem"
    hope = hopes[0] if hopes else "your goal"
    ct = plan["content_type"]
    prod = products[0].get("name", "our recommended product") if products else "our recommended product"
    prod_price = products[0].get("price", "$XX") if products else "$XX"

    templates = {
        "problem_discovery": f"""<p>You know that feeling when {frust}? It's not just annoying — it's a sign that something isn't working.</p>
<p>Most people ignore it. They adapt, they cope, they tell themselves it's fine. But here's the truth: {frust} is costing you more than you realize.</p>
<p>In this guide, we'll show you exactly what's going wrong and — more importantly — how to fix it. No fluff, no theory. Just actionable steps that actually work.</p>
<h2>The Real Cost of Ignoring {frust}</h2>
<p>The problem with {frust.lower()} isn't just the inconvenience. It's the cumulative drain on your time, your focus, and your peace of mind.</p>
<p>Think about it: every time you deal with {frust.lower()}, you're spending mental energy you could be using for something that matters. Multiply that by days, weeks, months — and the cost adds up fast.</p>
<h2>What You Can Do About It</h2>
<p>The good news? You don't have to live with this. Here's a proven approach to solving {frust.lower()} once and for all.</p>
<p>Start by acknowledging the problem. Then look at the tools and techniques available. And finally — make a decision based on what actually works, not what's marketed the hardest.</p>
<p>If you're ready to take action, we recommend starting with <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod} ({prod_price})</a> — it's what we use and trust.</p>""",
        "problem_deep_dive": f"""<p>Let's talk about {frust}. It's one of the most overlooked issues in {niche_name}, and it's quietly costing people like {p_name} thousands in wasted time and money.</p>
<p>Most articles tell you what to buy. This one tells you why the problem exists in the first place — and how to fix it at the root.</p>
<h2>Why {frust} Happens</h2>
<p>The root cause is almost never what people think. It's not about budget, or brand, or even the specific product. It's about how {niche_name} fits into your specific situation.</p>
<p>When you understand the underlying mechanics, you stop wasting money on Band-Aid fixes and start investing in solutions that last.</p>
<h2>What {p_name} Should Do Instead</h2>
<p>Here's the framework we use after testing dozens of options. Step one: identify your actual use case. Step two: match it to proven solutions. Step three: ignore everything else.</p>
<p>Want the shortcut? Start with <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod}</a> — it consistently outperforms alternatives in this exact scenario.</p>""",
        "how_to": f"""<p>If you've been struggling with {frust}, here's a step-by-step system that will help you achieve {hope}.</p>
<h2>Step 1: Assess Your Starting Point</h2>
<p>Before you can fix {frust.lower()}, you need to understand where you are now. Take 5 minutes to evaluate your current setup and identify the specific gaps.</p>
<h2>Step 2: Choose the Right Approach</h2>
<p>Not all solutions are created equal. For {p_name}, the best approach prioritizes {hope.lower()} without creating new problems. Here's what to look for...</p>
<h2>Step 3: Invest in What Works</h2>
<p>Once you've identified the right approach, it's time to execute. We've tested extensively and found that <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod}</a> delivers the best results for people in your situation.</p>
<h2>Step 4: Optimize and Maintain</h2>
<p>Getting it right is one thing. Keeping it right is another. Here's how to maintain your setup for long-term success...</p>""",
        "solution_comparison": f"""<p>If you're reading this, you already know {frust} is a problem. Now the question is: what's the best way to solve it?</p>
<p>We've tested every major approach. Here's our honest assessment of what works best for {p_name}.</p>
<h2>Option A: The Quick Fix</h2>
<p>Fast, affordable, but often temporary. Good if you need an immediate solution and are comfortable iterating.</p>
<h2>Option B: The Long-Term Solution</h2>
<p>More investment upfront, but delivers {hope} sustainably. This is what we recommend for most people.</p>
<h2>Our Verdict</h2>
<p>For {p_name}, we recommend <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod}</a>. It strikes the best balance of performance, value, and reliability.</p>""",
        "product_review": f"""<p>After spending [X hours] testing {prod} against its top competitors, here's our honest verdict — including what we didn't like.</p>
<h2>First Impressions</h2>
<p>Out of the box, {prod} feels {hope.lower()} in mind. The build quality is solid, the setup is straightforward, and the initial performance is impressive.</p>
<h2>How It Performs in Real-World Use</h2>
<p>We tested {prod} for [X days/weeks] in real conditions. Here's what we found...
<strong>What we loved:</strong> [Key strengths]
<strong>What we didn't:</strong> [Honest weaknesses]</p>
<h2>Bottom Line</h2>
<p>Is {prod} right for {p_name}? If {frust} is your main concern, then yes — this is the best option at {prod_price}. <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">Check the current price on Amazon</a>.</p>""",
        "micro_comparison": f"""<p>Quick question for {p_name}: Are you better off with the market leader or the value pick? We tested both to give you a straight answer.</p>
<h2>At a Glance</h2>
<table class="decision-matrix"><thead><tr><th>Feature</th><th>{prod}</th><th>Alternative</th></tr></thead><tbody>
<tr><td>Price</td><td>{prod_price}</td><td>$XX</td></tr>
<tr><td>Performance</td><td>Excellent</td><td>Good</td></tr>
<tr><td>Best For</td><td>{p_name}</td><td>Budget buyers</td></tr>
</tbody></table>
<h2>The Verdict</h2>
<p>If {frust} is your priority, <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod}</a> is the clear choice.</p>""",
        "cross_sell": f"""<p>Most people stop at one product. But if you really want to solve {frust}, you need a system — not just a gadget.</p>
<h2>The Essential Kit for {p_name}</h2>
<p>After extensive testing, here are the three products {p_name} needs for the perfect {niche_name} setup:</p>
<p><strong>1. {prod}</strong> — The cornerstone. This handles the core {frust.lower()} problem.</p>
<p><strong>2. [Complementary product]</strong> — Extends your capabilities and fills the gaps.</p>
<p><strong>3. [Accessory]</strong> — The finishing touch that makes everything work together seamlessly.</p>
<p>Start with <a href="https://www.amazon.com/s?k={niche_name.replace(' ','+')}&tag=viraltestco-20" target="_blank" rel="sponsored">{prod} ({prod_price})</a> and build from there.</p>""",
    }

    return templates.get(ct, templates["problem_discovery"])



def get_persona_content_matrix(niche_name):
    """Build a complete content matrix for a niche: all personas × all awareness levels.
    Returns list of content plan dicts, one per cell in the matrix."""
    from abvorn.persona.engine import PersonaEngine
    engine = PersonaEngine()
    personas = engine.discover_personas(niche_name)
    matrix = []
    for persona in personas:
        for level in ["unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"]:
            plan = generate_persona_content_plan(niche_name, persona, level)
            matrix.append(plan)
        # Add cross-sell
        plan = generate_persona_content_plan(niche_name, persona, "solution_aware",
                                             content_type_override="cross_sell")
        matrix.append(plan)
    return matrix



def write_persona_content_plan(niche_name, matrix, docs_dir="docs/plans"):
    """Write persona content plan to a markdown file for the mission to use."""
    import os
    plans_dir = os.path.join(docs_dir, "")
    os.makedirs(plans_dir, exist_ok=True)
    slug = niche_name.lower().replace(" ", "-")
    path = os.path.join(plans_dir, f"content-plan-{slug}.md")
    lines = [
        f"# Content Plan: {niche_name}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]
    for plan in matrix:
        lines.extend([
            f"## Persona: {plan['persona']} — {plan['content_label']}",
            f"- **Awareness**: {plan['awareness_level']}",
            f"- **Suggested Title**: {plan['suggested_title']}",
            f"- **Angle**: {plan['angle']}",
            f"- **Keyword**: {plan['primary_keyword']}",
            f"- **Persuasion**: Cialdini={plan['persuasion_levers']['cialdini']}, Hoffeld={plan['persuasion_levers']['hoffeld']}",
            f"- **Structure**:",
        ])
        for s in plan["suggested_structure"]:
            lines.append(f"  - {s}")
        lines.append("")
    content = "\n".join(lines)
    with open(path, "w") as f:
        f.write(content)
    print(f"  Written: {path} ({len(matrix)} content pieces planned)")
    return path


# ─── Document writer ────────────────────────────────────────────────────

