"""Add consent-gated Google Analytics tag to every published page.

Replaces any existing analytics snippet (immediate-load gtag or the old
G-XXXXXXXXXX placeholder) with the consent-gated loader + cookie banner
used by the run_cycle/deployment templates, so analytics only fires after
the visitor accepts.
"""
import re
from pathlib import Path

GA_ID = "G-J0GTXLC86C"

# Consent-gated loader: analytics only loads once analytics_consent=granted.
GA_LOADER = (
    '<script>window.loadAnalytics=function(){var s=document.createElement("script");'
    's.async=true;s.src="https://www.googletagmanager.com/gtag/js?id=%s";'
    'document.head.appendChild(s);window.dataLayer=window.dataLayer||[];'
    'function gtag(){dataLayer.push(arguments)};gtag("js",new Date());'
    'gtag("config","%s")};(function(){var c=document.cookie.match('
    '/(?:^|;) *analytics_consent=([^;]*)/);if(c&&c[1]==="granted"){loadAnalytics()}})()</script>'
) % (GA_ID, GA_ID)

COOKIE_BANNER_CSS = """<style>
#cookie-banner{position:fixed;bottom:0;left:0;right:0;background:#0a0a0a;color:#fff;padding:16px 24px;z-index:9999;display:none;font-size:13px;line-height:1.5;box-shadow:0 -4px 12px rgba(0,0,0,.15)}
#cookie-banner.show{display:flex;flex-wrap:wrap;align-items:center;gap:12px;justify-content:center}
#cookie-banner p{margin:0;color:#ffffff;font-size:13px}
#cookie-banner a{color:#c98a2c;text-decoration:underline}
#cookie-banner .btn{background:#c98a2c;color:#0a0a0a;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700}
#cookie-banner .btn:hover{background:#d4a03a}
#cookie-banner .btn-secondary{background:transparent;color:#ffffff;border:1px solid #555;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px}
#cookie-banner .btn-secondary:hover{border-color:#888}
</style>"""

COOKIE_BANNER = """<div id="cookie-banner" role="dialog" aria-label="Cookie consent">
<p>We use cookies to analyze traffic and improve your experience. <a href="/abvorn/privacy/">Privacy Policy</a></p>
<button class="btn-secondary" onclick="declineAnalytics()">Decline</button>
<button class="btn" onclick="acceptAnalytics()">Accept</button>
</div>"""

CONSENT_JS = """<script>
(function(){var c=document.cookie.match(/(?:^|;) *analytics_consent=([^;]*)/);if(c&&c[1]==="granted"){return}var b=document.getElementById("cookie-banner");if(b){b.classList.add("show")}window.acceptAnalytics=function(){document.cookie="analytics_consent=granted; max-age=31536000; path=/; SameSite=Lax";b.classList.remove("show");if(typeof loadAnalytics==="function"){loadAnalytics()}};window.declineAnalytics=function(){document.cookie="analytics_consent=denied; max-age=31536000; path=/; SameSite=Lax";b.classList.remove("show")}})();
</script>"""

# Patterns for the snippets we want to strip before inserting the clean block.
_OLD_GTAG_RE = re.compile(
    r'<script[^>]*src="https://www\.googletagmanager\.com/gtag/js\?id=[^"]*"[^>]*></script>\s*'
    r'<script>window\.dataLayer=window\.dataLayer\|\|\[\];function gtag\(\)\{dataLayer\.push\(arguments\)\};'
    r'gtag\(\'js\',new Date\(\)\);gtag\(\'config\',\'[^\']*\'\);</script>'
)
_LOADER_RE = re.compile(
    r'<script>window\.loadAnalytics=function\(\).*?gtag\("config","[^"]+"\)\};\('
    r'function\(\)\{var c=document\.cookie\.match.*?loadAnalytics\(\)\}\)\(\)</script>',
    re.S,
)
_BANNER_RE = re.compile(r'<div id="cookie-banner"[^>]*>.*?</div>', re.S)
_CONSENT_JS_RE = re.compile(r'<script>\s*\(function\(\)\{var c=document\.cookie\.match.*?analytics_consent.*?</script>', re.S)
_CONSENT_CSS_RE = re.compile(r'<style>#cookie-banner\{[^}]*\}.*?</style>', re.S)


def add_ga(filepath):
    html = filepath.read_text(encoding="utf-8")
    if "assets" in filepath.parts or "plans" in filepath.parts or "specs" in filepath.parts:
        return False
    orig = html
    # Strip any existing analytics / consent snippets so we never duplicate.
    html = _OLD_GTAG_RE.sub("", html)
    html = _LOADER_RE.sub("", html)
    html = _BANNER_RE.sub("", html)
    html = _CONSENT_JS_RE.sub("", html)
    html = _CONSENT_CSS_RE.sub("", html)
    block = f"\n{COOKIE_BANNER_CSS}\n{GA_LOADER}\n{COOKIE_BANNER}\n{CONSENT_JS}\n"
    html = html.replace("</head>", f"{block}</head>")
    if html == orig:
        return False
    filepath.write_text(html, encoding="utf-8")
    return True


docs = Path("docs")
updated = 0
for f in sorted(docs.rglob("*.html")):
    if add_ga(f):
        updated += 1

print(f"\nDone: {updated} files updated with consent-gated analytics.")
