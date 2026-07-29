"""Data ingestion layer — centralizes RSS, Tavily, DuckDuckGo, and Open Web Ninja feeds."""

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("abvorn.data_ingestion")

DATA_RAW = Path("data/raw")
DATA_PROCESSED = Path("data/processed")
DATA_INSIGHTS = Path("data/insights")


def _ensure_dirs():
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    DATA_INSIGHTS.mkdir(parents=True, exist_ok=True)


def _save_raw(product_id: str, data: dict) -> Path:
    _ensure_dirs()
    path = DATA_RAW / f"{product_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(f"Saved raw data: {path}")
    return path


def _load_raw(product_id: str) -> Optional[dict]:
    path = DATA_RAW / f"{product_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_processed(product_id: str, data: dict) -> Path:
    _ensure_dirs()
    path = DATA_PROCESSED / f"{product_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(f"Saved processed data: {path}")
    return path


def fetch_rss(url: str) -> list:
    """Fetch and parse an RSS feed URL. Returns list of dicts with title, link, summary, pub_date."""
    import requests
    import xml.etree.ElementTree as ET
    items = []
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return items
        root = ET.fromstring(resp.content)
        ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
        for entry in root.iter("item"):
            title = entry.findtext("title", "").strip()
            link = entry.findtext("link", "").strip()
            desc = entry.findtext("description", "")[:500]
            date = entry.findtext("pubDate", "")[:16]
            content = entry.findtext("content:encoded", "", ns)[:1000]
            body = content or desc
            if title and link:
                items.append({"title": title, "link": link, "summary": body, "pub_date": date})
    except Exception as e:
        logger.warning(f"RSS fetch failed for {url}: {e}")
    return items


def fetch_article_text(url: str) -> str:
    """Fetch an article URL and return readable text via BeautifulSoup."""
    import requests
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup not installed; cannot extract article text")
        return ""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.split("\n") if len(l) > 40]
        return "\n".join(lines[:80])[:5000]
    except Exception as e:
        logger.warning(f"Article fetch failed for {url}: {e}")
        return ""


def search_tavily(query: str, max_results: int = 5) -> dict:
    """Search via Tavily API and return structured results."""
    from abvorn.core.secrets import load_secrets
    from abvorn.core.tavily import TavilyClient
    secrets = load_secrets()
    key = secrets.get("TAVILY_KEY", "")
    if not key:
        logger.warning("TAVILY_KEY not configured; search skipped")
        return {"results": [], "answer": ""}
    try:
        client = TavilyClient(key)
        data = client.search(query, max_results=max_results, include_answer=True)
        return data
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        return {"results": [], "answer": ""}


def search_ddg(query: str, max_results: int = 5) -> list:
    """Fallback search via DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.warning("duckduckgo-search not installed")
        return []
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return []


def fetch_open_web_ninja(query: str, api_key: str = "") -> dict:
    """Fetch product data via Open Web Ninja API."""
    if not api_key:
        from abvorn.core.secrets import load_secrets
        secrets = load_secrets()
        api_key = secrets.get("OPENWEB_NINJA_KEY", "")
    if not api_key:
        logger.warning("Open Web Ninja key not configured")
        return {}
    try:
        import requests
        resp = requests.get(
            f"https://api.openwebninja.com/v1/products?q={query}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"Open Web Ninja returned {resp.status_code}")
        return {}
    except Exception as e:
        logger.warning(f"Open Web Ninja fetch failed: {e}")
        return {}


def ingest_product_data(product_name: str, niche: str = "") -> dict:
    """
    Ingest product data from multiple sources for a single product.

    Priority: Tavily > DuckDuckGo > Open Web Ninja > RSS

    Returns a unified product dict with name, price, rating, features, pros, cons, summary.
    """
    product_id = product_name.lower().replace(" ", "-")[:60]
    cached = _load_raw(product_id)
    if cached:
        logger.info(f"Using cached data for {product_id}")
        return cached

    query = f"{product_name} review price specs 2026"
    sources = {}

    sources["tavily"] = search_tavily(query, max_results=3)
    if not sources["tavily"].get("answer") and not sources["tavily"].get("results"):
        sources["ddg"] = search_ddg(query, max_results=3)

    sources["owninja"] = fetch_open_web_ninja(product_name)

    result = {
        "product_id": product_id,
        "product_name": product_name,
        "niche": niche,
        "query": query,
        "sources": sources,
        "ingested_at": __import__("datetime").datetime.now().isoformat(),
    }

    _save_raw(product_id, result)
    return result


def ingest_niche_rss(niche: str, state: dict = None) -> list:
    """
    Fetch RSS feeds for a niche, returns combined article list.

    RSS source mapping mirrors abvorn_cell2.py:1829.
    """
    RSS_MAP = {
        "wireless-headphones": ["https://www.wirecutter.com/rss/", "https://www.engadget.com/rss.xml"],
        "gaming-mice": ["https://www.theverge.com/rss/index.xml", "https://www.arstechnica.com/rss-feed/"],
        "4k-monitors": ["https://www.theverge.com/rss/index.xml", "https://www.arstechnica.com/rss-feed/"],
        "laptops": ["https://www.theverge.com/rss/index.xml", "https://www.engadget.com/rss.xml"],
        "streaming-devices": ["https://www.theverge.com/rss/index.xml", "https://www.arstechnica.com/rss-feed/"],
        "mechanical-keyboards": ["https://www.engadget.com/rss.xml", "https://www.theverge.com/rss/index.xml"],
        "wireless-earbuds": ["https://www.wirecutter.com/rss/", "https://www.engadget.com/rss.xml"],
        "fitness-trackers": ["https://www.theverge.com/rss/index.xml"],
        "webcams": ["https://www.engadget.com/rss.xml", "https://www.theverge.com/rss/index.xml"],
        "smart-home": ["https://www.gizmodo.com/rss", "https://www.theverge.com/rss/index.xml"],
    }

    urls = RSS_MAP.get(niche, [])
    all_articles = []
    for url in urls:
        articles = fetch_rss(url)
        for a in articles:
            a["source_url"] = url
            a["niche"] = niche
        all_articles.extend(articles)

    logger.info(f"Ingested {len(all_articles)} RSS articles for {niche}")
    return all_articles


def ingest_niche(niche: str, product_name: str = "", state: dict = None) -> dict:
    """
    Full ingestion for a niche: RSS + product search.

    Returns dict with articles and product info.
    """
    articles = ingest_niche_rss(niche, state)
    product_data = {}
    if product_name:
        product_data = ingest_product_data(product_name, niche)

    return {
        "niche": niche,
        "articles": articles,
        "product_data": product_data,
        "ingested_at": __import__("datetime").datetime.now().isoformat(),
    }