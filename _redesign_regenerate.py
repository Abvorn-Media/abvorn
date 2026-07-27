"""Regenerate all pages with new design."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_cycle import *
import json
from pathlib import Path

state = json.load(open("cycle_state.json", encoding="utf-8"))
all_slugs = [n["slug"] for n in state["niches"]]
b = SITE_BASE

# Collect existing articles
articles = {}
for n in state["niches"]:
    slug = n["slug"]
    name = n["name"]
    review_dir = Path("docs") / "reviews" / slug
    if review_dir.is_dir():
        try:
            content = (review_dir / "index.html").read_text(encoding="utf-8")
            articles[slug] = [{"post_title": f"Best {name}", "slug": slug}]
        except Exception:
            pass

# Regenerate category pages
for n in state["niches"]:
    slug = n["slug"]
    name = n["name"]
    niche_posts = [{"title": a.get("post_title", ""), "slug": f"reviews/{slug}"} for a in articles.get(slug, [])]
    cat_dir = Path("docs") / slug
    cat_dir.mkdir(exist_ok=True)
    (cat_dir / "index.html").write_text(
        build_category_page(slug, name, niche_posts, all_slugs, "viraltestco-20"),
        encoding="utf-8",
    )
    print(f"  Written: docs/{slug}/index.html")

# Write root index
all_posts = []
for n in state["niches"]:
    for a in articles.get(n["slug"], []):
        all_posts.append({"title": a.get("post_title", ""), "slug": f"reviews/{n['slug']}"})
    all_posts.append({"title": f"Best {n['name']}", "slug": n["slug"]})
Path("docs/index.html").write_text(
    build_root_index(state, all_posts, ""), encoding="utf-8"
)
print("  Written: docs/index.html")

# Write methodology
method_dir = Path("docs") / "how-we-test"
method_dir.mkdir(exist_ok=True)
(method_dir / "index.html").write_text(
    build_methodology_page(all_slugs, ""), encoding="utf-8"
)
print("  Written: docs/how-we-test/index.html")

# RSS + sitemap
items = []
for n in state["niches"]:
    items.append({"title": f"Best {n['name']}", "slug": n["slug"]})
    for a in articles.get(n["slug"], []):
        items.append({"title": a.get("post_title", ""), "slug": f"reviews/{n['slug']}"})
rss = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Abvorn Reviews</title><link>https://abvorn.com</link><description>Product reviews you can trust</description>'
for it in items:
    rss += f'<item><title>{it["title"]}</title><link>https://abvorn.com/{it["slug"]}</link><guid>https://abvorn.com/{it["slug"]}</guid><pubDate>2026-07-27</pubDate></item>'
rss += "</channel></rss>"
(Path("docs") / "feed.xml").write_text(rss, encoding="utf-8")
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n<url><loc>https://abvorn.com/</loc></url>\n'
for it in items:
    sitemap += f'<url><loc>https://abvorn.com/{it["slug"]}</loc></url>\n'
sitemap += "</urlset>"
(Path("docs") / "sitemap.xml").write_text(sitemap, encoding="utf-8")
print("  Written: feed.xml, sitemap.xml")

print("\nDone!")
