#!/usr/bin/env python3
"""build_blog.py - generate, illustrate and publish The Abvorn Dispatch.

Pipeline per dispatch:
  1. generate  (LLM, only with --generate/--all)  -> data/blog/posts.json
  2. images    (Pexels, hero + inline >=2)         -> docs/assets/blog/<slug>/
  3. field kit (one product for the cross-sell niche)
  4. render    (index + post pages via src.blog_site, through write_checked)
  5. sitemap   (append /blog/ + post URLs)

Examples:
  python scripts/build_blog.py --all                 # top up + illustrate + publish
  python scripts/build_blog.py --generate --persona calm-desk
  python scripts/build_blog.py --build               # re-render from posts.json
  python scripts/build_blog.py --build --refresh-images
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from abvorn.content import blog  # noqa: E402
from fetch_blog_images import fetch_blog_images, get_pexels_key  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_blog")


def _router():
    import time

    from abvorn.core.models import ModelRouter
    from abvorn.core.secrets import load_secrets

    import os

    secrets = load_secrets()
    timeout = float(os.environ.get("ABVORN_BLOG_LLM_TIMEOUT", "45"))
    router = ModelRouter(secrets, timeout=timeout)
    # Without a probe the router walks dead providers first and can stall on
    # their timeout/retry-after; the probe bans them up front.
    router.probe()
    time.sleep(5)
    alive = [p.name for p in router.providers if p.available]
    logger.info("Providers available: %s", alive)
    return router


def _next_topic(persona_id: str, posts: dict):
    used_titles = {p.get("title", "") for p in posts.values()}
    for title, dek in blog.TOPIC_BANK.get(persona_id, []):
        if title not in used_titles:
            return title, dek
    return None


def generate_one(persona_id: str, posts: dict, router) -> dict | None:
    topic = _next_topic(persona_id, posts)
    if not topic:
        logger.info("No unused topics left for %s", persona_id)
        return None
    title, dek = topic
    logger.info("Generating [%s] %s", persona_id, title)
    post = blog.generate_blog_post(title, dek, persona_id, router)
    if not post:
        return None
    posts[post["slug"]] = post
    blog.save_posts(posts)
    logger.info("  -> %s (%d sections)", post["slug"], len(post["sections"]))
    return post


def attach_images(post: dict, key: str, refresh: bool = False) -> None:
    queries = post.get("image_queries") or []
    if not queries:
        queries = [post.get("title", "editorial photograph"), post.get("category", "lifestyle")]
    hero, images = fetch_blog_images(post["slug"], queries, key, count=3, refresh=refresh)
    if hero:
        post["hero"] = hero
    if images:
        post["images"] = images
    logger.info("  images: hero=%s inline=%d", bool(hero), len(images))


def attach_product(post: dict) -> None:
    niche = post.get("cross_sell_niche")
    if not niche:
        return
    try:
        from run_cycle import research_products

        products = research_products(niche) or []
        if products:
            post["cross_sell_product"] = products[0]
            post["cross_sell_name"] = niche.replace("-", " ").title()
            logger.info("  field kit: %s", products[0].get("name", "")[:60])
    except Exception as e:
        logger.warning("  field kit skipped: %s", e)


def render(posts: dict, base: str) -> None:
    from src.blog_site import build_blog_index_page, build_blog_post_page
    from src.deployment import write_checked

    docs = REPO / "docs"
    blog_dir = docs / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)

    index_html = build_blog_index_page(posts, base)
    write_checked(blog_dir / "index.html", index_html, "blog index")
    logger.info("Wrote docs/blog/index.html")

    for slug, post in posts.items():
        post_dir = blog_dir / slug
        post_dir.mkdir(parents=True, exist_ok=True)
        html = build_blog_post_page(post, posts, base)
        write_checked(post_dir / "index.html", html, f"blog post {slug}")
    logger.info("Wrote %d blog posts", len(posts))


def update_sitemap(posts: dict, base: str) -> None:
    site = (base or "https://abvorn.com").rstrip("/")
    path = REPO / "docs" / "sitemap.xml"
    if not path.exists():
        return
    xml = path.read_text(encoding="utf-8")
    # Rebuild the blog block from scratch: drop every existing /blog/ URL first
    # so a renamed or removed dispatch can never linger as a dead sitemap entry.
    stripped = re.sub(r"\s*<url><loc>[^<]*/blog/[^<]*</loc>(?:<lastmod>[^<]*</lastmod>)?</url>",
                      "", xml)
    additions = [f"{site}/blog/"] + [f"{site}/blog/{s}/" for s in posts]
    block = "".join(f"<url><loc>{u}</loc></url>\n" for u in additions)
    xml = stripped.replace("</urlset>", block + "</urlset>")
    path.write_text(xml, encoding="utf-8")
    logger.info("Sitemap: reconciled blog URLs (%d kept)", len(additions))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="generate any missing, then build")
    ap.add_argument("--generate", action="store_true", help="generate one post")
    ap.add_argument("--build", action="store_true", help="render from posts.json only")
    ap.add_argument("--persona", default="", help="persona id for --generate")
    ap.add_argument("--base", default="https://abvorn.com", help="URL base for links")
    ap.add_argument("--refresh-images", action="store_true")
    ap.add_argument("--target", type=int, default=3, help="aim for this many posts with --all")
    args = ap.parse_args()

    if not (args.all or args.generate or args.build):
        ap.print_help()
        return 1

    posts = blog.load_posts()

    if args.generate or args.all:
        router = _router()
        personas = [args.persona] if args.persona else list(blog.BLOG_PERSONAS)
        made = 0
        for pid in personas:
            if not pid:
                continue
            if args.all and len(posts) >= args.target:
                break
            post = generate_one(pid, posts, router)
            if post:
                made += 1
                if not args.all:
                    break
        logger.info("Generated %d post(s)", made)

    # Illustrate + field kit for every post that is missing either.
    key = get_pexels_key()
    if not key:
        logger.warning("No Pexels key - post pages will render with placeholders")
    for slug, post in posts.items():
        if key and (not post.get("hero") or not post.get("images") or args.refresh_images):
            attach_images(post, key, refresh=args.refresh_images)
        if not post.get("cross_sell_product"):
            attach_product(post)
    blog.save_posts(posts)

    render(posts, args.base)
    update_sitemap(posts, args.base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
