"""Tavily search client — AI-native web search for agentic research.

Signup: https://tavily.com (1000 free searches/month, no credit card needed)
Docs: https://docs.tavily.com
"""

import json, logging, os, time
from typing import Optional

logger = logging.getLogger("abvorn.tavily")

TAVILY_API_URL = "https://api.tavily.com"


class TavilyClient:
    """Lightweight Tavily search client. No dependencies beyond requests."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("TAVILY_KEY", "")
        self._last_call = 0.0

    @property
    def available(self) -> bool:
        return bool(self.api_key) and "YOUR_" not in self.api_key

    def search(self, query: str, max_results: int = 5, search_depth: str = "basic",
               include_answer: bool = True, include_raw_content: bool = False) -> dict:
        """Search the web via Tavily.

        Args:
            query: Search query
            max_results: 1-10 results
            search_depth: 'basic' (faster) or 'advanced' (deeper)
            include_answer: Include AI-generated summary
            include_raw_content: Include full page HTML (uses more credits)

        Returns:
            dict with keys: answer (str), results (list), response_time (float)
            Each result: {title, url, content, score, raw_content}
        """
        if not self.available:
            logger.warning("Tavily: no API key configured")
            return {"answer": "", "results": [], "response_time": 0}

        # Rate limit: 1 req/s
        now = time.time()
        if now - self._last_call < 1.0:
            time.sleep(1.0 - (now - self._last_call))

        import requests as rq
        try:
            resp = rq.post(f"{TAVILY_API_URL}/search", json={
                "api_key": self.api_key,
                "query": query,
                "search_depth": search_depth,
                "include_answer": include_answer,
                "include_raw_content": include_raw_content,
                "max_results": max_results,
            }, timeout=15)
            self._last_call = time.time()

            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Tavily: '{query[:40]}' → {len(data.get('results', []))} results in {data.get('response_time', 0)}s")
                return data
            elif resp.status_code == 429:
                logger.warning("Tavily: rate limited (429)")
                return {"answer": "", "results": [], "response_time": 0}
            else:
                logger.warning(f"Tavily: HTTP {resp.status_code}: {resp.text[:200]}")
                return {"answer": "", "results": [], "response_time": 0}

        except Exception as e:
            logger.warning(f"Tavily: request failed: {e}")
            return {"answer": "", "results": [], "response_time": 0}

    def search_context(self, query: str, max_results: int = 5) -> str:
        """Search and return a formatted context string for LLM prompts."""
        data = self.search(query, max_results=max_results, include_answer=True)
        parts = []
        if data.get("answer"):
            parts.append(f"Summary: {data['answer']}")
        for i, r in enumerate(data.get("results", []), 1):
            parts.append(f"\n[{i}] {r.get('title', '')}")
            parts.append(f"    URL: {r.get('url', '')}")
            parts.append(f"    {r.get('content', '')[:500]}")
        return "\n".join(parts)

    def extract_products(self, niche: str, router=None) -> list:
        """Search for products in a niche and extract structured product data via LLM.

        Returns list of dicts with name, price, description, features.
        """
        data = self.search(f"best {niche} 2025 2026 buying guide review", max_results=8,
                           search_depth="advanced", include_answer=True)
        results = data.get("results", [])
        if not results:
            return []

        snippets = []
        for r in results[:6]:
            snippets.append(f"[{r.get('title','')}]({r.get('url','')}): {r.get('content','')[:400]}")

        if not router:
            return snippets

        summary = data.get("answer", "")
        context = summary + "\n\n" + "\n".join(snippets) if summary else "\n".join(snippets)

        prompt = f"""From these search results about '{niche}', extract up to 5 specific real products with brand and model names.

Search results:
{context[:3000]}

Return a JSON array. Each product must have:
- name: specific brand + model (e.g. "Sony WH-1000XM5")
- price: realistic price string or "Check Price"
- description: 1-2 sentence highlight (what makes it great)
- features: array of 3-4 key features
- category: "best_overall", "best_value", or "premium_pick"
- source_url: URL of the source

Return ONLY the JSON array, no other text."""
        result = router.ask(prompt, json_mode=True)
        if not result:
            return []
        try:
            products = json.loads(result)
            return products if isinstance(products, list) else ([products] if isinstance(products, dict) else [])
        except json.JSONDecodeError:
            import re
            m = re.search(r'\[.*\]', result, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except:
                    pass
            return []
