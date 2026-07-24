import os, json, logging, base64, re, html
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger("abvorn.deploy")

_STYLE_CSS = """/* Abvorn — Wirecutter-inspired design */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;scroll-behavior:smooth}
body{font-family:'Merriweather',Georgia,serif;color:#1a1a1a;background:#fff;line-height:1.7;-webkit-font-smoothing:antialiased}
h1,h2,h3,h4,.logo,.site-nav a,.pick-badge,.disclosure-banner{font-family:'Inter',-apple-system,sans-serif}
.site-header{border-bottom:1px solid #e5e5e5;background:#fff;position:sticky;top:0;z-index:100}
.header-inner{max-width:1100px;margin:0 auto;padding:12px 20px;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:1.25rem;font-weight:700;color:#1a1a1a;text-decoration:none;letter-spacing:-0.02em}
.site-nav{display:flex;gap:24px}
.site-nav a{font-size:0.875rem;color:#555;text-decoration:none;font-weight:500}
.site-nav a:hover{color:#1a1a1a}
.disclosure-banner{background:#f7f7f7;text-align:center;font-size:0.75rem;color:#777;padding:8px 16px;border-bottom:1px solid #e5e5e5;font-family:'Inter',sans-serif}
main{max-width:720px;margin:0 auto;padding:40px 20px 60px}
.article-header{margin-bottom:32px}
.breadcrumb{font-size:0.8rem;color:#888;margin-bottom:8px;font-family:'Inter',sans-serif;text-transform:uppercase;letter-spacing:0.05em}
.review-article h1{font-size:2.25rem;font-weight:700;line-height:1.2;letter-spacing:-0.02em;margin-bottom:12px}
.byline{font-size:0.85rem;color:#888;margin-bottom:16px;font-family:'Inter',sans-serif}
.subtitle{font-size:1.1rem;color:#555;line-height:1.5}
.our-pick{background:#fafaf8;border:1px solid #e5e5e5;border-radius:8px;padding:24px;margin:32px 0;display:flex;align-items:flex-start;gap:16px}
.pick-badge{display:inline-block;background:#1a1a1a;color:#fff;font-size:0.75rem;font-weight:600;padding:4px 10px;border-radius:4px;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap}
.pick-text{font-size:0.95rem;color:#444;line-height:1.6;margin-top:8px}
.review-article h2{font-size:1.5rem;font-weight:700;margin-top:48px;margin-bottom:16px;line-height:1.3;font-family:'Inter',sans-serif}
.review-article h3{font-size:1.2rem;font-weight:600;margin-top:32px;margin-bottom:12px;font-family:'Inter',sans-serif}
.review-article p{font-size:1rem;margin-bottom:20px;color:#2a2a2a}
.review-article ul,.review-article ol{margin-bottom:20px;padding-left:24px}
.review-article li{margin-bottom:8px;font-size:1rem}
.review-article a{color:#0066cc;text-decoration:underline;text-underline-offset:2px}
.review-article a:hover{color:#004499}
.review-article img{max-width:100%;height:auto;border-radius:8px;margin:24px 0}
.review-article blockquote{border-left:3px solid #1a1a1a;padding-left:20px;margin:24px 0;color:#555;font-style:italic}
.review-article table{width:100%;border-collapse:collapse;margin:24px 0;font-family:'Inter',sans-serif;font-size:0.9rem}
.review-article th,.review-article td{border:1px solid #e5e5e5;padding:10px 14px;text-align:left}
.review-article th{background:#f7f7f7;font-weight:600}
.review-article code{background:#f4f4f4;padding:2px 6px;border-radius:3px;font-size:0.9rem}
.article-footer{border-top:1px solid #e5e5e5;margin-top:48px;padding-top:24px}
.article-footer .disclosure{font-size:0.85rem;color:#777;line-height:1.6}
.site-footer{border-top:1px solid #e5e5e5;background:#fafaf8;margin-top:60px}
.footer-inner{max-width:720px;margin:0 auto;padding:24px 20px;text-align:center;font-size:0.8rem;color:#999;font-family:'Inter',sans-serif}
@media(max-width:600px){.review-article h1{font-size:1.75rem}.header-inner{padding:10px 16px}main{padding:24px 16px 40px}.our-pick{flex-direction:column;gap:8px}}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{tags}">
{seo_tags}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<header class="site-header">
    <div class="header-inner">
        <a href="/" class="logo">Abvorn</a>
        <nav class="site-nav">
            <a href="/">Reviews</a>
            <a href="/about">About</a>
        </nav>
    </div>
</header>
<div class="disclosure-banner">We independently review everything we recommend. When you buy through our links, we may earn a commission.</div>
<main>
<article class="review-article">
    <header class="article-header">
        <p class="breadcrumb">Reviews / {niche_label}</p>
        <h1>{title}</h1>
        <p class="byline">Updated {date} &middot; {reading_time} min read</p>
        <p class="subtitle">{meta_desc}</p>
    </header>
    {pick_badge}
    {content}
    <footer class="article-footer">
        <p class="disclosure"><strong>Why you can trust Abvorn:</strong> Our team spends hours researching and testing products so you can buy with confidence. Every recommendation is independent and free from sponsor influence.</p>
    </footer>
</article>
</main>
<footer class="site-footer">
    <div class="footer-inner">
        <p>&copy; {year} Abvorn. As an Amazon Associate we earn from qualifying purchases.</p>
    </div>
</footer>
<script type="application/ld+json">{schema}</script>
</body>
</html>"""

class GitHubDeployer:
    """Deploys content to GitHub Pages via the GitHub API."""

    def __init__(self, token: str, repo: str, branch: str = "main", site_dir: str = "", adsense_id: str = ""):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.site_dir = Path(site_dir) if site_dir else Path("docs")
        self.adsense_id = adsense_id

    def prepare_files(self, content: dict, output_dir: Path) -> list[str]:
        """Generate HTML files for a content item."""
        slug = content.get("niche_slug", content.get("post_title", "post").lower().replace(" ", "-"))
        safe_slug = re.sub(r'[^a-z0-9-]', '', slug.lower())[:80]

        article_html = content.get("article_html", "")
        intro = content.get("intro", "")
        meta_desc = content.get("meta_description", "")[:160]
        title = html.escape(content.get("post_title", "Post"), quote=True)
        tags_str = ", ".join(content.get("tags", []))
        schema_json = json.dumps(content.get("schema", {}))

        niche = content.get("niche", content.get("niche_slug", "products"))
        niche_label = html.escape(niche.replace("-", " ").title(), quote=True)
        today = datetime.now().strftime("%B %d, %Y")
        reading_time = max(1, round(len(article_html) / 1500))
        pick_badge = '<div class="our-pick"><span class="pick-badge">Our pick</span><p class="pick-text">After hours of research, this is the one we recommend.</p></div>' if content.get("is_pick") else ""

        seo_tags = f'<link rel="canonical" href="https://{self.repo.split("/")[0]}.github.io/{self.repo.split("/")[1]}/{safe_slug}/">'

        full_html = TEMPLATE.format(
            title=title, meta_desc=meta_desc, tags=tags_str,
            seo_tags=seo_tags, content=intro + "\n" + article_html,
            schema=schema_json, niche_label=niche_label, date=today,
            reading_time=reading_time, pick_badge=pick_badge,
            year=datetime.now().year,
        )

        post_dir = output_dir / safe_slug
        post_dir.mkdir(parents=True, exist_ok=True)
        index_file = post_dir / "index.html"
        index_file.write_text(full_html, encoding="utf-8")

        assets_dir = output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        style_file = assets_dir / "style.css"
        if not style_file.exists():
            style_file.write_text(_STYLE_CSS, encoding="utf-8")

        logger.info(f"Prepared: {index_file}")
        return [str(index_file)]

    def deploy(self, niche_slug: str) -> dict:
        """Push generated files to GitHub using PyGithub."""
        from github import Github
        from github import InputGitTreeElement

        try:
            g = Github(self.token)
            repo = g.get_repo(self.repo)
            site_path = self.site_dir / niche_slug / "index.html"

            if not site_path.exists():
                return {"status": "error", "message": f"File not found: {site_path}"}

            with open(site_path, "r", encoding="utf-8") as f:
                content = f.read()

            try:
                ref = repo.get_git_ref(f"heads/{self.branch}")
                base_sha = ref.object.sha
                base_tree = repo.get_git_tree(base_sha)
            except Exception:
                ref = repo.get_git_ref("heads/main")
                base_sha = ref.object.sha
                base_tree = repo.get_git_tree(base_sha)

            blob = repo.create_git_blob(content, "utf-8")
            relative_path = str(self.site_dir.name / niche_slug / "index.html")
            element = InputGitTreeElement(relative_path, "100644", "blob", sha=blob.sha)
            new_tree = repo.create_git_tree([element], base_tree)

            parent = repo.get_git_commit(base_sha)
            commit = repo.create_git_commit(f"feat: deploy {niche_slug}", new_tree, [parent])
            ref.edit(commit.sha)

            deploy_url = f"https://{self.repo.split('/')[0]}.github.io/{self.repo.split('/')[1]}/{niche_slug}/"
            logger.info(f"Deployed: {deploy_url}")
            return {"status": "success", "url": deploy_url, "commit": commit.sha}

        except Exception as e:
            logger.error(f"Deploy failed for {niche_slug}: {e}")
            return {"status": "error", "message": str(e)}