import os, sys
sys.path.insert(0, r"C:\Users\Jean Mare\Documents\Default Project")
os.chdir(r"C:\Users\Jean Mare\Documents\Default Project")

from src.deployment import scan_published_reviews, write_checked
from run_cycle import build_category_page

NICHE = "tv"
reviews = [r for r in scan_published_reviews("docs") if r.get("slug") == NICHE]
reviews.sort(key=lambda r: r.get("updated", "") or "", reverse=True)
print(f"tv reviews found: {len(reviews)}")

html = build_category_page(
    NICHE, "Tv".title(), reviews, ["laptops", "tv", "webcams", "monitors", "streaming-devices", "smart-home", "mechanical-keyboards", "wireless-headphones"],
    affiliate_tag=os.environ.get("ABVORN_AMAZON_TAG", "viraltestco-20"),
)
path = os.path.join("docs", "reviews", NICHE, "index.html")
write_checked(path, html, "reviews/tv/index.html")
print("wrote", path, len(html), "bytes")

import re
bad = [m for m in re.findall(r'(?:href|src)="(/abvorn/[^"]*|https?://example\.com[^"]*)"', html)]
gtag = html.count("G-XXXXXXXXXX")
print("abvorn/example.com bad refs:", bad[:10], "gtag-stub:", gtag)