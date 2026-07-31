"""click_server.py — Lightweight redirect server for affiliate click tracking.

Serves static files from docs/ and handles /click/<article_id>/<product_index>
by logging the click and redirecting to the actual Amazon affiliate URL.

Run: python click_server.py --port 8000
"""
import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from http.server import HTTPServer, SimpleHTTPRequestHandler

from src.click_tracker import log_click, get_clicks, register_articles_batch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ARTICLES_DB_PATH = Path("data/articles_db.json")
AFFILIATE_TAG = os.environ.get("AMAZON_TAG", "viraltestco-20")


def _load_articles_db() -> Dict[str, Any]:
    if ARTICLES_DB_PATH.exists():
        try:
            return json.loads(ARTICLES_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_articles_db(data: Dict[str, Any]):
    ARTICLES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTICLES_DB_PATH.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")


def track_click(article_id: str, product_index: int) -> Dict[str, Any]:
    db = _load_articles_db()
    article = db.get(article_id, {})
    products = article.get("products", [])
    affiliate_urls = article.get("affiliate_urls", [])

    if not affiliate_urls and products:
        product = products[product_index] if product_index < len(products) else products[0]
        raw_url = product.get("url", "") or product.get("affiliate_query", "")
        if raw_url and not raw_url.startswith("http"):
            raw_url = f"https://www.amazon.com/s?k={raw_url.replace(' ', '+')}&tag={AFFILIATE_TAG}"
        elif raw_url:
            if "tag=" not in raw_url:
                sep = "&" if "?" in raw_url else "?"
                raw_url = f"{raw_url}{sep}tag={AFFILIATE_TAG}"
    else:
        raw_url = affiliate_urls[product_index] if product_index < len(affiliate_urls) else (
            affiliate_urls[0] if affiliate_urls else f"https://www.amazon.com/s?k={article_id.replace('-','+')}&tag={AFFILIATE_TAG}"
        )

    return log_click(article_id, raw_url)


class ClickHandler(SimpleHTTPRequestHandler):
    """Serve docs/ and handle /click/ redirects."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/click/"):
            self._handle_click(path)
        elif path == "/clicks/stats":
            self._handle_stats()
        else:
            super().do_GET()

    def _handle_click(self, path):
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            self.send_error(400, "Expected /click/<article_id>/<product_index>")
            return

        article_id = parts[1]
        product_index = int(parts[2]) if parts[2].isdigit() else 0

        db = _load_articles_db()
        article = db.get(article_id, {})
        products = article.get("products", [])
        affiliate_urls = article.get("affiliate_urls", [])

        if not affiliate_urls and products:
            product = products[product_index] if product_index < len(products) else products[0]
            raw_url = product.get("url", "") or product.get("affiliate_query", "")
            if raw_url and not raw_url.startswith("http"):
                raw_url = f"https://www.amazon.com/s?k={raw_url.replace(' ', '+')}&tag={AFFILIATE_TAG}"
            elif raw_url:
                if "tag=" not in raw_url:
                    sep = "&" if "?" in raw_url else "?"
                    raw_url = f"{raw_url}{sep}tag={AFFILIATE_TAG}"
        else:
            raw_url = affiliate_urls[product_index] if product_index < len(affiliate_urls) else (
                affiliate_urls[0] if affiliate_urls else f"https://www.amazon.com/s?k={article_id.replace('-','+')}&tag={AFFILIATE_TAG}"
            )

        log_click(article_id, raw_url, user_agent=self.headers.get("User-Agent", ""))

        self.send_response(302)
        self.send_header("Location", raw_url)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _handle_stats(self):
        db = _load_articles_db()
        stats = {"articles": len(db), "total_clicks": sum(
            get_clicks(aid) for aid in db.keys()
        )}
        body = json.dumps(stats, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        logger.info(format % args)


def run(port: int = 8000, docs_dir: str = "docs"):
    os.chdir(docs_dir)
    server = HTTPServer(("", port), ClickHandler)
    logger.info(f"Serving {docs_dir} at http://localhost:{port}")
    logger.info(f"Click redirects: http://localhost:{port}/click/<article_id>/<product_index>")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Abvorn click tracker + static server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--docs", default="docs")
    args = parser.parse_args()
    run(port=args.port, docs_dir=args.docs)
