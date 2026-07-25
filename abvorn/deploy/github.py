import os, json, logging, base64, re, html
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

from abvorn.uix import UIXComponents, UIX_STYLE_CSS, UIX_SCRIPT_JS
from abvorn.sites.model import DNAProfile

logger = logging.getLogger("abvorn.deploy")

DNA_CSS = {
    DNAProfile.TECH: "--font-family-heading: 'Inter', sans-serif;--border-radius: 2px;--card-style: flat;--button-style: outline;--button-radius: 2px;--image-radius: 2px;--spacing-unit: 8px;--heading-weight: 700;",
    DNAProfile.WARM: "--font-family-heading: 'Nunito', sans-serif;--border-radius: 12px;--card-style: shadow;--button-style: filled;--button-radius: 24px;--image-radius: 16px;--spacing-unit: 12px;--heading-weight: 600;",
    DNAProfile.PREMIUM: "--font-family-heading: 'Playfair Display', serif;--border-radius: 0px;--card-style: elevated;--button-style: ghost;--button-radius: 0px;--image-radius: 0px;--spacing-unit: 16px;--heading-weight: 400;",
}

_STYLE_CSS = """/* Abvorn — Wirecutter-inspired, fully responsive */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{font-family:'Merriweather',Georgia,serif;color:#1a1a1a;background:#fff;line-height:1.7;-webkit-font-smoothing:antialiased;overflow-x:hidden}
h1,h2,h3,h4,.logo,.site-nav a,.pick-badge,.disclosure-banner{font-family:'Inter',-apple-system,sans-serif}
.site-header{border-bottom:1px solid #e5e5e5;background:#fff;position:sticky;top:0;z-index:100}
.header-inner{max-width:1100px;margin:0 auto;padding:12px 20px;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:clamp(1rem, 2.5vw, 1.25rem);font-weight:700;color:#1a1a1a;text-decoration:none;letter-spacing:-0.02em}
.site-nav{display:flex;gap:clamp(12px, 3vw, 24px)}
.site-nav a{font-size:clamp(0.8rem, 2vw, 0.875rem);color:#555;text-decoration:none;font-weight:500;padding:4px 0}
.site-nav a:hover{color:#1a1a1a}
.disclosure-banner{background:#f7f7f7;text-align:center;font-size:clamp(0.65rem, 1.8vw, 0.75rem);color:#777;padding:clamp(6px, 1.5vw, 8px) clamp(12px, 3vw, 16px);border-bottom:1px solid #e5e5e5;font-family:'Inter',sans-serif;line-height:1.5}
main{max-width:min(720px, 100% - 40px);margin:0 auto;padding:clamp(24px, 5vw, 40px) 20px clamp(40px, 8vw, 60px)}
.article-header{margin-bottom:clamp(20px, 4vw, 32px)}
.breadcrumb{font-size:clamp(0.7rem, 1.8vw, 0.8rem);color:#888;margin-bottom:8px;font-family:'Inter',sans-serif;text-transform:uppercase;letter-spacing:0.05em}
.review-article h1{font-size:clamp(1.5rem, 4.5vw, 2.25rem);font-weight:700;line-height:1.2;letter-spacing:-0.02em;margin-bottom:12px;word-break:break-word}
.byline{font-size:clamp(0.75rem, 2vw, 0.85rem);color:#888;margin-bottom:16px;font-family:'Inter',sans-serif}
.subtitle{font-size:clamp(0.95rem, 2.5vw, 1.1rem);color:#555;line-height:1.5}
.our-pick{background:#fafaf8;border:1px solid #e5e5e5;border-radius:8px;padding:clamp(16px, 3vw, 24px);margin:clamp(20px, 4vw, 32px) 0;display:flex;align-items:flex-start;gap:clamp(8px, 2vw, 16px)}
.pick-badge{display:inline-block;background:#1a1a1a;color:#fff;font-size:clamp(0.65rem, 1.8vw, 0.75rem);font-weight:600;padding:4px 10px;border-radius:4px;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;flex-shrink:0}
.pick-text{font-size:clamp(0.85rem, 2.2vw, 0.95rem);color:#444;line-height:1.6;margin-top:0}
.review-article h2{font-size:clamp(1.2rem, 3.5vw, 1.5rem);font-weight:700;margin-top:clamp(28px, 6vw, 48px);margin-bottom:clamp(10px, 2vw, 16px);line-height:1.3;font-family:'Inter',sans-serif}
.review-article h3{font-size:clamp(1rem, 2.8vw, 1.2rem);font-weight:600;margin-top:clamp(20px, 4vw, 32px);margin-bottom:clamp(8px, 1.5vw, 12px);font-family:'Inter',sans-serif}
.review-article p{font-size:clamp(0.9rem, 2.4vw, 1rem);margin-bottom:clamp(14px, 3vw, 20px);color:#2a2a2a;line-height:clamp(1.6, 2.8vw, 1.7)}
.review-article ul,.review-article ol{margin-bottom:clamp(14px, 3vw, 20px);padding-left:clamp(18px, 4vw, 24px)}
.review-article li{margin-bottom:clamp(6px, 1.5vw, 8px);font-size:clamp(0.9rem, 2.4vw, 1rem)}
.review-article a{color:#0066cc;text-decoration:underline;text-underline-offset:2px;word-break:break-word}
.review-article a:hover{color:#004499}
.review-article img{max-width:100%;height:auto;border-radius:8px;margin:clamp(16px, 3vw, 24px) 0;display:block}
.review-article blockquote{border-left:clamp(2px, 0.5vw, 3px) solid #1a1a1a;padding-left:clamp(14px, 3vw, 20px);margin:clamp(16px, 3vw, 24px) 0;color:#555;font-style:italic}
.review-article table{width:100%;border-collapse:collapse;margin:clamp(16px, 3vw, 24px) 0;font-family:'Inter',sans-serif;font-size:clamp(0.75rem, 2vw, 0.9rem);display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}
.review-article th,.review-article td{border:1px solid #e5e5e5;padding:clamp(6px, 1.5vw, 10px) clamp(8px, 2vw, 14px);text-align:left;white-space:nowrap}
.review-article th{background:#f7f7f7;font-weight:600}
.review-article code{background:#f4f4f4;padding:2px 6px;border-radius:3px;font-size:0.9rem;word-break:break-word}
.article-footer{border-top:1px solid #e5e5e5;margin-top:clamp(28px, 6vw, 48px);padding-top:clamp(16px, 3vw, 24px)}
.article-footer .disclosure{font-size:clamp(0.75rem, 2vw, 0.85rem);color:#777;line-height:1.6}
.site-footer{border-top:1px solid #e5e5e5;background:#fafaf8;margin-top:clamp(32px, 8vw, 60px)}
.footer-inner{max-width:min(720px, 100% - 40px);margin:0 auto;padding:clamp(16px, 4vw, 24px) 20px;text-align:center;font-size:clamp(0.7rem, 2vw, 0.8rem);color:#999;font-family:'Inter',sans-serif}
.related-posts{margin-top:32px;padding:20px;background:#fafaf8;border-radius:8px;border:1px solid #e5e5e5}
.related-posts h3{font-size:1rem;margin-bottom:12px}
.related-posts ul{list-style:none;padding:0}
.related-posts li{margin-bottom:8px}
.related-posts a{font-size:0.9rem}

/* Tablet */
@media(min-width:601px) and (max-width:1024px){main{max-width:min(680px, 100% - 48px);padding:32px 24px 48px}.header-inner{padding:12px 24px}}

/* Mobile */
@media(max-width:600px){main{max-width:100%;padding:20px 16px 40px}.header-inner{padding:10px 12px}.site-header{position:sticky}.our-pick{flex-direction:column;gap:8px}.review-article img{border-radius:6px}.review-article table{font-size:0.7rem}.review-article th,.review-article td{padding:4px 6px}.disclosure-banner{padding:6px 12px;font-size:0.65rem;text-align:left}}

/* Print */
@media print{body{font-size:12pt;color:#000}.site-header,.disclosure-banner,.site-footer,.pick-badge{display:none}main{padding:0;max-width:100%}a{text-decoration:none;color:#000}}

/* Subscribe */
.subscribe-section,.subscribe-box{background:#f0f7ff;border:1px solid #d0e3f7;border-radius:8px;padding:clamp(20px,4vw,32px);margin:clamp(24px,5vw,40px) 0;text-align:center}
.subscribe-section h3,.subscribe-box h3{font-size:clamp(1rem,2.8vw,1.3rem);font-weight:700;margin-bottom:8px;font-family:'Inter',sans-serif}
.subscribe-section p,.subscribe-box p{font-size:clamp(0.85rem,2.2vw,0.95rem);color:#555;margin-bottom:16px}
.subscribe-fields,.subscribe-form-inline{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;max-width:500px;margin:0 auto}
.subscribe-fields input,.subscribe-form-inline input{flex:1 1 180px;padding:10px 14px;border:1px solid #ccc;border-radius:6px;font-size:0.9rem;font-family:'Inter',sans-serif}
.subscribe-fields button,.subscribe-form-inline button{background:#1a1a1a;color:#fff;border:none;padding:10px 20px;border-radius:6px;font-size:0.9rem;font-weight:600;cursor:pointer;font-family:'Inter',sans-serif;white-space:nowrap}
.subscribe-fields button:hover,.subscribe-form-inline button:hover{background:#333}
.subscribe-niche{margin-top:12px;display:block}
.subscribe-niche select{padding:8px 12px;border:1px solid #ccc;border-radius:6px;font-size:0.85rem;font-family:'Inter',sans-serif;background:#fff;max-width:100%}
#subscribe-status,#subscribe-status-inline{margin-top:12px;font-size:0.9rem;font-family:'Inter',sans-serif}
#subscribe-status .success,#subscribe-status-inline .success{color:#2e7d32}
#subscribe-status .error,#subscribe-status-inline .error{color:#c62828}
@media(max-width:600px){.subscribe-fields,.subscribe-form-inline{flex-direction:column;align-items:stretch}.subscribe-fields input,.subscribe-form-inline input{flex:1 1 auto}}

""" + UIX_STYLE_CSS

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{tags}">
{seo_tags}
{og_tags}
{twitter_tags}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
{brand_css_vars}
{adsense_script}
</head>
<body class="dna-{dna_profile}">
<header class="site-header">
    <div class="header-inner">
        <a href="/" class="logo">{brand_logo_html}</a>
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
        <p class="disclosure"><strong>{trust_text}</strong> Our team spends hours researching and testing products so you can buy with confidence. Every recommendation is independent and free from sponsor influence.</p>
    </footer>
</article>
{uix_block}
{subscribe_section}
</main>
<footer class="site-footer">
    <div class="footer-inner">
        {footer_text}
    </div>
</footer>
<script type="application/ld+json">{schema}</script>
{uix_script}
</body>
</html>"""

class GitHubDeployer:
    """Deploys content to GitHub Pages via the GitHub API."""

    def __init__(self, token: str, repo: str, branch: str = "main", site_dir: str = "", adsense_id: str = "",
                 api_endpoint: str = ""):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.site_dir = Path(site_dir) if site_dir else Path("docs")
        self.adsense_id = adsense_id
        self.api_endpoint = api_endpoint
        if not self.api_endpoint and repo and "/" in repo:
            self.api_endpoint = f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/api/subscribe"

    def prepare_files(self, content: dict, output_dir: Path, brand=None) -> list[str]:
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

        canonical_url = f"https://{self.repo.split('/')[0]}.github.io/{self.repo.split('/')[1]}/{safe_slug}/"
        seo_tags = f'<link rel="canonical" href="{canonical_url}">'

        og_image_url = f"{canonical_url}og.png"
        og_tags = f"""<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical_url}">
<meta property="og:image" content="{og_image_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">"""

        twitter_tags = f"""<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{meta_desc}">
<meta name="twitter:image" content="{og_image_url}">"""

        featured_image_html = ""
        if content.get("has_image"):
            featured_image_html = f'<figure class="featured-image"><img src="og.png" alt="{title}" width="1200" height="630" loading="eager"></figure>'

        subscribe_section = f"""<div class="subscribe-section">
  <h3>Stay up to date</h3>
  <p>Get the latest reviews and deals sent to your inbox. No spam, unsubscribe anytime.</p>
  <form class="subscribe-form-inline" onsubmit="return abvornSubscribeInline(event)">
    <input type="text" id="sub-name-inline" placeholder="Your name" required>
    <input type="email" id="sub-email-inline" placeholder="Your email" required>
    <button type="submit">Subscribe</button>
  </form>
  <div id="subscribe-status-inline"></div>
</div>
<script>
window.abvornSubscribeInline = function(e) {{
  e.preventDefault();
  var name = document.getElementById('sub-name-inline').value.trim();
  var email = document.getElementById('sub-email-inline').value.trim();
  var niche = '{safe_slug}';
  var statusEl = document.getElementById('subscribe-status-inline');
  statusEl.textContent = 'Subscribing...';
  var x = new XMLHttpRequest();
  x.open('POST', '{self.api_endpoint}', true);
  x.setRequestHeader('Content-Type', 'application/json');
  x.onload = function() {{
    if (x.status === 200) {{
      statusEl.innerHTML = '<span class="success">Thanks! Check your inbox.</span>';
      document.getElementById('sub-name-inline').value = '';
      document.getElementById('sub-email-inline').value = '';
    }} else {{
      statusEl.innerHTML = '<span class="error">Could not subscribe. Try again?</span>';
    }}
  }};
  x.onerror = function() {{
    statusEl.innerHTML = '<span class="error">Connection error. Try again later.</span>';
  }};
  x.send(JSON.stringify({{name: name, email: email, niche: niche}}));
  return false;
}};
</script>"""

        adsense_script = ""
        if self.adsense_id:
            adsense_script = f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={html.escape(self.adsense_id, quote=True)}" crossorigin="anonymous"></script>'

        year = datetime.now().year
        if brand is None:
            brand_logo_html = "Abvorn"
            trust_text = "Why you can trust Abvorn:"
            footer_text = f"&copy; {year} Abvorn. As an Amazon Associate we earn from qualifying purchases."
            brand_css_vars = ""
            dna_profile = ""
        else:
            brand_logo_html = f"{brand.logo_icon} {brand.logo_text}".strip()
            trust_text = f"Why you can trust {brand.brand_name}:"
            footer_text = f"&copy; {year} {brand.brand_name}. As an Amazon Associate we earn from qualifying purchases."
            dna_vars = DNA_CSS.get(brand.dna_profile, "")
            brand_css_vars = f"<style>:root{{--primary:{brand.primary_color};--secondary:{brand.secondary_color};{dna_vars}}}</style>"
            dna_profile = brand.dna_profile.value

        full_html = TEMPLATE.format(
            title=title, meta_desc=meta_desc, tags=tags_str,
            seo_tags=seo_tags, og_tags=og_tags, twitter_tags=twitter_tags,
            content=featured_image_html + "\n" + intro + "\n" + article_html,
            schema=schema_json, niche_label=niche_label, date=today,
            reading_time=reading_time, pick_badge=pick_badge,
            year=year, adsense_script=adsense_script,
            uix_block="", uix_script=UIX_SCRIPT_JS,
            subscribe_section=subscribe_section,
            brand_logo_html=brand_logo_html, trust_text=trust_text,
            footer_text=footer_text, brand_css_vars=brand_css_vars,
            dna_profile=dna_profile,
        )

        post_dir = output_dir / safe_slug
        post_dir.mkdir(parents=True, exist_ok=True)
        index_file = post_dir / "index.html"
        index_file.write_text(full_html, encoding="utf-8")

        # Save OG image if provided
        image_bytes = content.get("image_bytes")
        if image_bytes:
            og_file = post_dir / "og.png"
            og_file.write_bytes(image_bytes)
            logger.info(f"Image saved: {og_file}")

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