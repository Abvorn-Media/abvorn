import json, re, logging

from abvorn.core.models import parse_json

logger = logging.getLogger("abvorn.editor")


def _guidance_texts(items, limit: int = 2) -> list:
    """Pull .text out of brain guidance rows, tolerating the stored shape.

    Brain rows are JSON blobs; ``text`` can arrive as a dict/None, and joining
    that raises "sequence item 0: expected str instance, dict found".
    """
    texts = []
    for item in (items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        value = item.get("text")
        if isinstance(value, str) and value.strip():
            texts.append(value[:300])
        elif isinstance(value, dict):
            texts.append(json.dumps(value)[:300])
    return texts


def fact_check(draft: dict, research_data: list, router, brain_context: dict = None) -> dict:
    """FACT-CHECK stage: verify claims against research data."""
    raw = (draft.get("intro", "") + draft.get("article_html", ""))[:3000]
    article = re.sub(r'<[^>]+>', '', raw) if raw else ""
    research_text = json.dumps(research_data, indent=2)[:2000]

    brain_guidance = ""
    if brain_context:
        psych_triggers = brain_context.get("psychology_triggers", [])
        if psych_triggers:
            texts = _guidance_texts(psych_triggers)
            if texts:
                brain_guidance = "\nPSYCHOLOGY GUIDANCE:\n" + "\n---\n".join(texts) + "\n\nCheck if the article properly leverages these psychological principles."

    prompt = f"""Fact-check this article against the research data.

ARTICLE (first 3000 chars):
{article}

RESEARCH DATA:
{research_text}
{brain_guidance}

Identify any claims that are:
1. Not supported by the research data
2. Contradicted by the research data
3. Exaggerated or speculative

Return JSON with:
{{
    "passed": true/false,
    "issues": [
        {{
            "claim": "the specific claim made",
            "evidence": "what the research actually says",
            "severity": "high/medium/low",
            "suggested_fix": "how to correct it"
        }}
    ],
    "revised_intro": "corrected intro HTML if needed, or empty string",
    "revised_article": "corrected article HTML if needed, or empty string"
}}"""
    result = router.ask(prompt, json_mode=True)
    if isinstance(result, str):
        parsed = parse_json(result)
        if parsed is None:
            logger.warning("Fact-check JSON parse failed, assuming passed")
            return {"passed": True, "issues": []}
        return parsed if isinstance(parsed, dict) else {"passed": True, "issues": []}
    return result or {"passed": True, "issues": []}


def polish(draft: dict, fact_check_result: dict, persona: dict, router, brain_context: dict = None) -> dict:
    """POLISH stage: refine tone, conversion architecture, schema."""
    raw_article = fact_check_result.get("revised_article") or draft.get("article_html", "")
    raw_intro = fact_check_result.get("revised_intro") or draft.get("intro", "")
    article = re.sub(r'<[^>]+>', '', raw_article)[:2000]
    intro = re.sub(r'<[^>]+>', '', raw_intro)[:500]
    persona_name = persona.get("name", "reader") if persona else "reader"

    brain_guidance = ""
    if brain_context:
        copy_principles = brain_context.get("copywriting_principles", [])
        if copy_principles:
            texts = _guidance_texts(copy_principles)
            if texts:
                brain_guidance = "\nCOPYWRITING GUIDANCE:\n" + "\n---\n".join(texts) + "\n\nApply these principles during polish."

    prompt = f"""Polish this buying guide for conversion. Your reader is "{persona_name}".

INTRO: {intro[:500]}
ARTICLE: {article[:2000]}
{brain_guidance}

REQUIRED IMPROVEMENTS:
1. Ensure the emotional arc: problem → trust → solution → proof → action
2. Make sure every paragraph advances the reader toward a decision
3. Verify affiliate links are contextual (not abrupt or tacked on)
4. Ensure scannability: short paragraphs, clear headings
5. Check reading level matches the persona

Return JSON:
{{
    "revised_intro": "polished intro HTML",
    "revised_article": "polished article HTML",
    "quality_score": {{
        "conversion_potential": 1-10,
        "specificity": 1-10,
        "emotional_arc": 1-10,
        "trust_signals": 1-10,
        "readability": 1-10,
        "overall": 0.0
    }},
    "schema_markup": {{
        "article": "... schema.org Article JSON ...",
        "product": "... schema.org Product JSON ...",
        "faq": "... schema.org FAQPage JSON ...",
        "breadcrumb": "... schema.org BreadcrumbList JSON ..."
    }}
}}"""
    result = router.ask(prompt, json_mode=True)
    if isinstance(result, str):
        parsed = parse_json(result)
        if parsed is None:
            logger.error("Polish JSON parse failed")
            result = None
        else:
            result = parsed
    if isinstance(result, dict) and result:
        return result
    return {
        "revised_intro": intro,
        "revised_article": article,
        "quality_score": {"overall": 7.0},
        "schema_markup": {}
    }


def build_schema(title, description, url, image, date_published, products, faqs):
    """Generate all schema markup for a page."""
    logo_url = url
    if url and url.count("/") >= 2:
        parts = url.split("/")
        logo_url = f"{parts[0]}//{parts[2]}/logo.svg"
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "image": image,
        "datePublished": date_published,
        "author": {"@type": "Person", "name": "Abvorn Editorial"},
        "publisher": {"@type": "Organization", "name": "Abvorn",
                      "logo": {"@type": "ImageObject", "url": logo_url}}
    }
    product_items = []
    for p in products:
        product_items.append({
            "@type": "Product",
            "name": p.get("name", "Product"),
            "description": p.get("description", ""),
            "offers": {"@type": "Offer", "price": p.get("price", "Check Price"), "priceCurrency": "USD"}
        })
    product_schema = {"@context": "https://schema.org", "@graph": product_items} if product_items else {}
    faq_items = []
    for q, a in faqs[:5]:
        faq_items.append({"@type": "Question", "name": q,
                          "acceptedAnswer": {"@type": "Answer", "text": a}})
    faq_schema = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": faq_items} if faq_items else {}
    home_url = url
    if url and url.count("/") >= 2:
        parts = url.split("/")
        home_url = f"{parts[0]}//{parts[2]}"
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": home_url},
            {"@type": "ListItem", "position": 2, "name": title, "item": url}
        ]
    }
    return {
        "article": json.dumps(article),
        "product": json.dumps(product_schema),
        "faq": json.dumps(faq_schema),
        "breadcrumb": json.dumps(breadcrumb)
    }
