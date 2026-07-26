"""Trend recon providers — real web data sources for trend discovery."""

import logging, re, time, requests

logger = logging.getLogger("abvorn.trends.recon")

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from pytrends.request import TrendReq
    HAS_TRENDREQ = True
except ImportError:
    HAS_TRENDREQ = False


class DuckDuckGoSource:
    """Searches DuckDuckGo for trending products in a niche."""

    def __init__(self):
        self._ddgs = DDGS() if HAS_DDGS else None

    def search(self, category: str, max_results: int = 5) -> list[dict]:
        if not self._ddgs:
            return []
        queries = [f"best {category} 2026", f"top rated {category}", f"{category} review 2026"]
        seen = set()
        results = []
        for q in queries:
            try:
                for r in self._ddgs.text(q, max_results=3):
                    title = r.get("title", "")
                    body = r.get("body", "")
                    products = self._extract_products(title + " " + body)
                    for p in products:
                        key = p.lower().strip()
                        if key not in seen:
                            seen.add(key)
                            results.append({
                                "product_name": p,
                                "category": category,
                                "source": "duckduckgo",
                                "score": 60,
                                "price_range": "",
                                "url": r.get("href", ""),
                            })
                time.sleep(1)
            except Exception as e:
                logger.debug(f"DDG search failed for '{q}': {e}")
        return results[:max_results]

    def _extract_products(self, text: str) -> list[str]:
        patterns = [
            r'([A-Z][a-zA-Z0-9\s]+(?:Pro|Max|Air|Ultra|Plus|Gen\d|M\d|X\d))',
            r'([A-Z][a-z]+(?:\s[A-Z][a-zA-Z0-9]+){1,4})',
        ]
        found = set()
        for pat in patterns:
            for match in re.finditer(pat, text):
                candidate = match.group(1).strip()
                if 5 < len(candidate) < 60 and not candidate.startswith("The "):
                    found.add(candidate)
        return list(found)


class AmazonSource:
    """Scrapes Amazon best sellers for trending products."""

    AMAZON_URLS = {
        "tv": "https://www.amazon.com/gp/bestsellers/electronics/172659",
        "laptop": "https://www.amazon.com/gp/bestsellers/electronics/13896617011",
        "robot vacuum": "https://www.amazon.com/gp/bestsellers/home-garden/13249881",
        "monitor": "https://www.amazon.com/gp/bestsellers/electronics/1292115011",
        "smart home": "https://www.amazon.com/gp/bestsellers/electronics/9811847011",
    }

    def search(self, category: str, max_results: int = 5) -> list[dict]:
        url = self.AMAZON_URLS.get(category)
        if not url:
            return []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for item in soup.select("div.p13n-sc-uncoverable-faceout")[:max_results]:
                title_el = item.select_one("div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
                if title_el:
                    name = title_el.get_text(strip=True)
                    results.append({
                        "product_name": name,
                        "category": category,
                        "source": "amazon",
                        "score": 70,
                        "price_range": "",
                        "url": url,
                    })
            return results
        except Exception as e:
            logger.debug(f"Amazon scrape failed: {e}")
            return []


class RedditSource:
    """Searches Reddit for product recommendation threads."""

    def search(self, category: str, max_results: int = 5) -> list[dict]:
        try:
            subreddits = [category.replace(" ", ""), "buyingadvice", "recommendations"]
            results = []
            seen = set()
            for sub in subreddits:
                try:
                    url = f"https://www.reddit.com/r/{sub}/search.json?q={category}&restrict_sr=1&sort=top&t=year&limit=5"
                    headers = {"User-Agent": "Abvorn/1.0"}
                    resp = requests.get(url, headers=headers, timeout=10)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for child in data.get("data", {}).get("children", []):
                        title = child.get("data", {}).get("title", "")
                        products = self._extract_products(title)
                        for p in products:
                            key = p.lower().strip()
                            if key not in seen:
                                seen.add(key)
                                results.append({
                                    "product_name": p,
                                    "category": category,
                                    "source": "reddit",
                                    "score": 55,
                                    "price_range": "",
                                    "url": child.get("data", {}).get("url", ""),
                                })
                    time.sleep(1)
                except Exception:
                    continue
            return results[:max_results]
        except Exception as e:
            logger.debug(f"Reddit search failed: {e}")
            return []

    def _extract_products(self, text: str) -> list[str]:
        patterns = [
            r'([A-Z][a-zA-Z0-9\s]+(?:Pro|Max|Air|Ultra|Plus|Gen\d|M\d))',
            r'(?:recommend|suggest|best)\s+([A-Z][a-zA-Z\s]{3,40})',
        ]
        found = set()
        for pat in patterns:
            for match in re.finditer(pat, text):
                candidate = match.group(1).strip()
                if 5 < len(candidate) < 60:
                    found.add(candidate)
        return list(found)


class GoogleTrendsSource:
    """Polls Google Trends for rising search terms in a niche."""

    def search(self, category: str, max_results: int = 5) -> list[dict]:
        if not HAS_TRENDREQ:
            return []
        try:
            pytrends = TrendReq(hl="en-US", tz=300)
            pytrends.build_payload(kw_list=[category], timeframe="today 3-m", geo="US")
            related = pytrends.related_queries()
            rising = related.get(category, {}).get("rising", [])
            if rising is None:
                return []
            results = []
            for item in rising.head(max_results).to_dict("records"):
                query = item.get("query", "")
                if query and len(query) > 3:
                    results.append({
                        "product_name": query,
                        "category": category,
                        "source": "googletrends",
                        "score": 65,
                        "price_range": "",
                        "url": "",
                    })
            return results
        except Exception as e:
            logger.debug(f"Google Trends failed: {e}")
            return []