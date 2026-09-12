"""Product Assets — resolves the real products a review page shows on the
website so the social engine can reuse the exact product photos and names
instead of generic stock photography.

Sources, in priority order:
1. The review page's JSON-LD ``Product`` node (hero pick: name, price, photo,
   affiliate URL).
2. The Open Web Ninja cache (``data/openweb_cache/cache.json``) for the full
   per-niche product list (ratings, sales volume, best-seller flags).

Returns normalized products: name, price, image (hi-res Amazon), url, asin.
"""

import hashlib
import json
import logging
import re
import urllib.parse
from pathlib import Path

logger = logging.getLogger("abvorn.domination.products")

CACHE_FILES = [
    Path("data/openweb_cache/cache.json"),
    Path("/opt/abvorn-core/data/openweb_cache/cache.json"),
]

ROLES = ["Overall Winner", "Runner-Up", "Also Great", "Worth Considering"]


def slug_from_url(url: str) -> str:
    """Pull the review niche out of an article URL (the most reliable niche id).

    ``https://abvorn.com/wireless-headphones/`` → ``wireless-headphones``
    ``https://abvorn.com/reviews/gaming-mice/`` → ``gaming-mice``
    ``https://abvorn.com/reviews/smart-home/best-smart-home-...-2026-08-26.html``
        → ``smart-home`` (dated article files live inside the niche folder)
    """
    if not url:
        return ""
    path = urllib.parse.urlparse(url).path
    parts = [p for p in path.split("/") if p]
    if not parts:
        return ""
    if "reviews" in parts:
        idx = parts.index("reviews")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return parts[-1]


def _review_roots() -> list[Path]:
    """Possible repository roots holding ``docs/reviews/``."""
    return [
        Path("docs"),
        Path("/opt/abvorn-core/repo-src/docs"),
        Path("/opt/abvorn-core/docs"),
        Path(__file__).resolve().parent.parent.parent / "docs",
    ]


def review_page_candidates(slug: str) -> list[Path]:
    """Possible on-disk locations of the published review for a slug.

    Matches the ``reviews/<niche>/index.html`` layout (the always-current
    mirror) plus the dated flat files ``reviews/<niche>/<slug>-<date>.html``
    that the RSS feed links point at.
    """
    seen: list[Path] = []
    for root in _review_roots():
        for sub in (f"reviews/{slug}", slug):
            p = root / sub / "index.html"
            if p not in seen:
                seen.append(p)
    # A bare dated filename (``best-...-2026-08-26.html``) may arrive from a
    # URL like ``/reviews/<niche>/<dated>.html`` — hunt it across niche folders.
    if slug.endswith(".html"):
        for root in _review_roots():
            try:
                for hit in root.glob(f"reviews/*/{slug}"):
                    if hit not in seen:
                        seen.append(hit)
            except OSError:
                continue
    return seen


def load_review_html(slug: str) -> str:
    """Return the review page HTML for a slug, or ``""`` when not found."""
    for candidate in review_page_candidates(slug):
        try:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning(f"product: cannot read {candidate}: {e}")
    return ""


def _parse_json_ld_products(html: str) -> list[dict]:
    """Extract Product nodes embedded as application/ld+json blocks."""
    out = []
    if not html:
        return out
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else data
        if isinstance(nodes, dict):
            nodes = [nodes]
        for n in nodes:
            if not isinstance(n, dict):
                continue
            t = n.get("@type")
            if isinstance(t, list):
                t = t[0]
            if t != "Product":
                continue
            offers = n.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if not isinstance(offers, dict):
                offers = {}
            price = str(n.get("price", "") or "").strip()
            if not price:
                price = str(offers.get("price", "") or "").strip()
            out.append({
                "name": str(n.get("name", "") or "").strip(),
                "price": price,
                "image": str(n.get("image", "") or "").strip(),
                "url": str(offers.get("url", "") or "").strip(),
                "asin": str(n.get("sku", "") or "").strip(),
            })
    return out


def _upgrade_image(url: str) -> str:
    """Amazon thumb → hi-res ``_AC_SL1500_`` (same as the website's hero shot)."""
    if not url:
        return url
    return re.sub(r"_AC_(?:SX|SY|UY|UX|SL)\d+(?:_QL\d+)?_", "_AC_SL1500_", url)


def _cache_lookup_for(hero: dict, max_products: int = 4) -> list[dict]:
    """Find the Open Web Ninja list that produced this review's hero pick."""
    hero_name = (hero.get("name") or "").lower()
    hero_img = hero.get("image") or ""
    hero_asin = (hero.get("asin") or "").upper()
    best: list[dict] = []
    for cache_file in CACHE_FILES:
        try:
            if not cache_file.exists():
                continue
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for products in cache.values():
            if not isinstance(products, list) or not products:
                continue
            hit = False
            for p in products:
                pname = str(p.get("name", "") or "").lower().strip()
                pimg = (p.get("image") or "").strip()
                pasin = str(p.get("asin", "") or "").upper()
                if hero_asin and pasin == hero_asin:
                    hit = True
                    break
                if hero_img and pimg and (
                    pimg == hero_img or pimg == hero_img.replace("_AC_UY654_QL65_", "_AC_SL1500_")
                ):
                    hit = True
                    break
                if hero_name and pname and hero_name[:24] in pname:
                    hit = True
                    break
            if hit:
                best = list(products)
                break
        if best:
            break
    return best[:max_products]


def _extract_html_products(html: str, max_products: int = 4) -> list[dict]:
    """Last-resort scrape of product links/images from an unpublished page."""
    out = []
    if not html:
        return out
    seen = set()
    for img_url, name, price in re.findall(
        r'<img[^>]*src="([^"]*(?:m\.media-amazon\.com|images-amazon\.com)[^"]*)"[^>]*>',
        html,
    ):
        if img_url in seen:
            continue
        seen.add(img_url)
        out.append({
            "name": "",
            "price": "",
            "image": _upgrade_image(img_url),
            "url": "",
            "asin": "",
        })
        if len(out) >= max_products:
            break
    return out


def clean_product_name(name: str, limit: int = 52) -> str:
    """Shorten a long Amazon title to a display-friendly line."""
    if not name:
        return ""
    cleaned = re.split(r"\s*[|]\s*", name)[0]
    cleaned = re.split(r"\s*[-]\s*", cleaned)[0]
    cleaned = cleaned.strip(" .|")
    for separator in (", 1", ", with", ", 10", ", "):
        idx = cleaned.find(separator)
        if 0 < idx < 60:
            cleaned = cleaned[:idx]
            break
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned.strip()


def _enrich(card: dict, product: dict) -> dict:
    """Blend a cache product's rich fields into a card."""
    card["name"] = clean_product_name(product.get("name", card.get("name", "")))
    if not card.get("price"):
        card["price"] = str(product.get("price", "") or "").strip()
    if not card.get("url"):
        card["url"] = str(product.get("url", "") or "").strip()
    return card


def load_products_for_niche(slug: str) -> list[dict]:
    """Resolve the products a review page actually shows, website-faithful.

    Returns normalized dicts with name / price / image (hi-res) / url / asin,
    capped at 4 — one per carousel slide. Empty list when nothing resolvable
    (caller falls back to Pexels stock).
    """
    slug = slug or ""
    if not slug:
        return []
    html = load_review_html(slug)
    ld_products = _parse_json_ld_products(html)
    hero = ld_products[0] if ld_products else {}

    products: list[dict] = []
    if ld_products:
        products = list(ld_products)
    if not products:
        products = _extract_html_products(html)

    cache_products = _cache_lookup_for(hero)
    if cache_products:
        indexed = {clean_product_name(p.get("name", "")).lower(): p for p in cache_products}
        ordered = []
        for card in products:
            key = clean_product_name(card.get("name", "")).lower()
            match = indexed.get(key) or _cache_lookup_for(card, max_products=1)
            if isinstance(match, list):
                match = match[0] if match else None
            ordered.append(_enrich(dict(card), match or card))
        # top up to 4 slots with any remaining cache products when the page
        # only exposed the hero pick
        if cache_products:
            names = {clean_product_name(p.get("name", "")).lower() for p in ordered}
            for cp in cache_products:
                if len(ordered) >= 4:
                    break
                if clean_product_name(cp.get("name", "")).lower() not in names:
                    ordered.append({
                        "name": clean_product_name(cp.get("name", "")),
                        "price": str(cp.get("price", "") or "").strip(),
                        "image": _upgrade_image(str(cp.get("image", "") or "")),
                        "url": str(cp.get("url", "") or "").strip(),
                        "asin": str(cp.get("asin", "") or ""),
                    })
                    names.add(clean_product_name(cp.get("name", "")).lower())
        products = ordered[:4]
    else:
        products = [dict(c) for c in products[:4]]

    normalized = []
    for i, p in enumerate(products):
        image = p.get("image") or ""
        normalized.append({
            "name": clean_product_name(p.get("name", "")) or f"{slug} pick {i + 1}",
            "price": _format_price(p.get("price", "")),
            "image": _upgrade_image(image),
            "url": p.get("url", "") or "",
            "asin": p.get("asin", "") or "",
            "role": ROLES[i] if i < len(ROLES) else "Worth Considering",
            "index": i,
        })
    return normalized


def _format_price(price: str) -> str:
    price = (price or "").strip()
    if not price or price.lower() in ("check price", "n/a", "none"):
        return "Check price"
    if price.startswith("$"):
        return price
    return f"${price}"


def download_product_image(url: str, slug: str, index: int,
                           root: Path | None = None) -> str | None:
    """Download a product photo (with an Amazon-friendly UA) to the asset cache."""
    if not url:
        return None
    asset_root = root or Path.home() / ".abvorn" / "assets" / (slug or "general")
    try:
        asset_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    out = asset_root / f"ig_product_{index}.jpg"
    if out.exists() and out.stat().st_size > 0:
        return str(out)

    import requests
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        "Referer": "https://www.amazon.com/",
        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
    }
    try:
        with requests.get(url, headers=headers, timeout=20, stream=True) as r:
            r.raise_for_status()
            data = r.content
        if len(data) < 500:
            logger.warning(f"product: {url} returned a {len(data)}-byte body")
            return None
        out.write_bytes(data)
        logger.info(f"product: downloaded {index} from {url}")
        return str(out)
    except Exception as e:
        logger.warning(f"product: download failed for {url}: {e}")
        return None


def _cache_key(query: str, source: str = "amazon") -> str:
    return hashlib.md5(f"{source}:{query}".encode()).hexdigest()