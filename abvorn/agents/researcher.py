import json, re, logging
from ddgs import DDGS

logger = logging.getLogger("abvorn.researcher")

def research_niche(niche: str, router=None) -> list:
    """RESEARCH stage: search web for real products in this niche.
    
    Returns list of dicts: [{name, price, rating, features, pros, cons, summary, source_url}]
    """
    products = []
    # 1. Try web search for real products
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"best {niche} 2025 2026 buying guide", max_results=8))
            snippets = []
            for r in results:
                if r.get("body"):
                    snippets.append(f"[{r.get('title','')}]({r.get('href','')}): {r['body'][:300]}")
            if snippets and router:
                prompt = f"""From these search results about '{niche}', extract up to 5 specific products.
For each product, return: name, estimated price, rating (if found), key features, pros, cons, and a 1-sentence summary.

Search results:
{chr(10).join(snippets[:5])}

Return a JSON array of objects with keys: name, price, rating, features (array), pros (array), cons (array), summary, source_url."""
                result = router.ask(prompt, json_mode=True)
                if result:
                    parsed = _parse_json(result)
                    if isinstance(parsed, list):
                        products = parsed
                    elif isinstance(parsed, dict):
                        products = [parsed]
    except Exception as e:
        logger.warning(f"Web research failed for '{niche}': {e}")

    # 2. Fallback: AI knowledge-based product generation
    if not products and router:
        prompt = f"""You are a product expert. For the niche '{niche}', recommend exactly 3 specific real products with brand and model names. Use your knowledge of real products available on Amazon.

Return a JSON array. Each product must have:
- name: specific brand + model (e.g. "Sony WH-1000XM5")
- price: realistic price string
- description: 1-2 sentence highlight
- features: array of 3-4 key features
- category: "best_overall", "best_value", or "premium_pick"
- affiliate_query: search query for this product (e.g. "Sony+WH-1000XM5")"""
        result = router.ask(prompt, json_mode=True)
        if result:
            parsed = _parse_json(result)
            if isinstance(parsed, list):
                products = parsed

    # 3. Ultimate fallback
    if not products:
        products = [{"name": f"Top {niche} Pick", "price": "Check Price",
                     "description": f"Best {niche} on the market",
                     "features": ["Quality", "Value", "Reliability"],
                     "category": "best_overall",
                     "affiliate_query": niche.replace(" ", "+")}]

    for p in products:
        p.setdefault("affiliate_query", p.get("name", niche).replace(" ", "+"))
        p.setdefault("source_url", "")

    return products


def _parse_json(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\[.*\]|\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None
