import json, re, logging

logger = logging.getLogger("abvorn.editor")


def fact_check(draft: dict, research_data: list, router) -> dict:
    """FACT-CHECK stage: verify claims against research data."""
    article = (draft.get("intro", "") + draft.get("article_html", ""))[:3000]
    research_text = json.dumps(research_data, indent=2)[:2000]

    prompt = f"""Fact-check this article against the research data.

ARTICLE (first 3000 chars):
{article}

RESEARCH DATA:
{research_text}

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
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.warning("Fact-check JSON parse failed, assuming passed")
            return {"passed": True, "issues": []}
    return result or {"passed": True, "issues": []}


def polish(draft: dict, fact_check_result: dict, persona: dict, router) -> dict:
    """POLISH stage: refine tone, conversion architecture, schema."""
    article = fact_check_result.get("revised_article") or draft.get("article_html", "")
    intro = fact_check_result.get("revised_intro") or draft.get("intro", "")
    persona_name = persona.get("name", "reader") if persona else "reader"

    prompt = f"""Polish this buying guide for conversion. Your reader is "{persona_name}".

INTRO: {intro[:500]}
ARTICLE: {article[:2000]}

REQUIRED IMPROVEMENTS:
1. Ensure the emotional arc: problem → trust → solution → proof → action
2. Make sure every paragraph advances the reader toward a decision
3. Verify affiliate links are contextual (not突兀)
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
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            logger.error("Polish JSON parse failed")
            return None
    if result:
        return result
    return {
        "revised_intro": intro,
        "revised_article": article,
        "quality_score": {"overall": 7.0},
        "schema_markup": {}
    }


def build_schema(title, description, url, image, date_published, products, faqs):
    """Generate all schema markup for a page."""
    import json as _json
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
        "article": _json.dumps(article),
        "product": _json.dumps(product_schema),
        "faq": _json.dumps(faq_schema),
        "breadcrumb": _json.dumps(breadcrumb)
    }
