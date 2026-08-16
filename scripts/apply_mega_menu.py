import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Jean Mare\Documents\Default Project")
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT))

from src.deployment import build_category_dropdown, build_footer_categories, MEGA_MENU_CSS

B = "/abvorn"
MEGA_GROUPS = build_category_dropdown(B)
CATEGORY_LINKS = build_footer_categories(B)

# ── Canonical social SVGs (extracted from the homepage footer) ───────────
home = (DOCS / "index.html").read_text(encoding="utf-8")
m = re.search(r'<div class="footer-social">(.*?)</div>', home, re.S)
SOCIAL_SVGS = m.group(1)

# ── Canonical footer markup (matches homepage/generators) ────────────────
CANON_FOOTER = (
    '<footer class="footer"><div class="container">\n'
    '    <div class="footer-grid">\n'
    '        <div class="footer-col">\n'
    '            <img src="/abvorn/logo.svg" alt="Abvorn" style="max-height:28px;width:auto;margin-bottom:8px">\n'
    '            <p>Independent product reviews and buying guides, based on real testing.</p>\n'
    '            <div class="footer-social">' + SOCIAL_SVGS + '</div>\n'
    '        </div>\n'
    '        <div class="footer-col"><h4>Categories</h4>' + CATEGORY_LINKS + '</div>\n'
    '        <div class="footer-col"><h4>Company</h4><a href="/abvorn/about.html">About</a></div>\n'
    '        <div class="footer-col"><h4>Legal</h4><a href="/abvorn/privacy.html">Privacy policy</a></div>\n'
    '    </div>\n'
    '    <div class="footer-bottom"><img src="/abvorn/logo.svg" alt="Abvorn" style="max-height:20px;width:auto;filter:brightness(0.6)"><span>&copy; 2026 Abvorn. All rights reserved.</span><span>Reviews updated weekly</span></div>\n'
    '</div></footer>'
)

# ── Canonical header markup (matches run_cycle.nav_html) ─────────────────
CANON_HEADER = (
    '<header><div class="container navbar">\n'
    '    <a href="/abvorn/" class="logo"><img src="/abvorn/logo.svg" alt="Abvorn" style="max-height:44px;width:auto"></a>\n'
    '    <button class="nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="nav-links">\n'
    '        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>\n'
    '    </button>\n'
    '    <nav class="nav-links" id="nav-links">\n'
    '        <div class="nav-item"><a href="#">Categories</a><div class="nav-dropdown nav-dropdown--mega">' + MEGA_GROUPS + '</div></div>\n'
    '        <a href="/abvorn/">Home</a>\n'
    '        <a href="/abvorn/about.html">About</a>\n'
    '    </nav>\n'
    '</div></header>'
)

NAV_SCRIPT = ("<script>\n(function(){var b=document.getElementById('nav-toggle');var n=document.getElementById('nav-links');"
              "if(!b||!n)return;b.addEventListener('click',function(){var o=n.classList.toggle('open');"
              "b.setAttribute('aria-expanded',o?'true':'false')})})();\n</script>")

# ── Canonical footer CSS (token-based, matches generators) ───────────────
FOOTER_CSS = """        .footer { background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }
        .footer-grid { display:grid; grid-template-columns: 1.6fr 1fr 1fr 1fr; gap: var(--space-lg); margin-bottom: var(--space-xl); }
        .footer-col h4 { color:#fff; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:14px; }
        .footer-col p { color:#999; font-size:0.9rem; max-width:32ch; }
        .footer-col a { display:block; color:#999; text-decoration:none; padding:4px 0; font-size:0.9rem; }
        .footer-col a:hover { color:#fff; }
        .footer-social { display:flex; gap:10px; margin-top:16px; }
        .footer-social a { width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
        .footer-social a:hover { background: var(--clr-accent); color:#0a0a0a; }
        .footer-social svg { width:16px; height:16px; }
        .footer-bottom { border-top:1px solid #222; padding-top:20px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:0.85rem; color:#777; }
        @media (max-width: 760px) { .footer-grid { grid-template-columns: 1fr 1fr; } }
"""

# Literal-value footer CSS for pages lacking the design tokens
FOOTER_CSS_LITERAL = """        .footer { background:#0a0a0a; color:#999; padding:64px 0 32px; }
        .footer .container { max-width:1200px; margin:0 auto; padding:0 24px; }
        .footer-grid { display:grid; grid-template-columns:1.6fr 1fr 1fr 1fr; gap:32px; margin-bottom:48px; }
        .footer-col h4 { color:#fff; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:14px; }
        .footer-col p { color:#999; font-size:0.9rem; max-width:32ch; }
        .footer-col a { display:block; color:#999; text-decoration:none; padding:4px 0; font-size:0.9rem; }
        .footer-col a:hover { color:#fff; }
        .footer-social { display:flex; gap:10px; margin-top:16px; }
        .footer-social a { width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; }
        .footer-social a:hover { background:var(--clr-accent,#c98a2c); color:#0a0a0a; }
        .footer-social svg { width:16px; height:16px; }
        .footer-bottom { border-top:1px solid #222; padding-top:20px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:0.85rem; color:#777; }
        @media (max-width:760px) { .footer-grid { grid-template-columns:1fr 1fr; } }
"""

# Header CSS for minimal pages (literal values, self-contained)
HEADER_CSS = """        header { background:#0a0a0a; padding:18px 0; border-bottom:1px solid #2a2a2a; }
        .navbar { display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }
        .logo img { max-height:44px; width:auto; }
        .nav-links { display:flex; align-items:center; gap:8px; }
        .nav-links > a, .nav-item > a { color:#fff; text-decoration:none; padding:8px 16px; font-weight:600; font-size:0.9rem; border-radius:var(--radius-sm,8px); }
        .nav-links > a:hover, .nav-item > a:hover { background:rgba(255,255,255,0.08); color:var(--clr-accent,#c98a2c); }
        .nav-item { position:relative; }
        .nav-item > a { padding:8px 16px; display:flex; align-items:center; gap:4px; }
        .nav-item > a::after { content:'\\25be'; font-size:0.6rem; opacity:0.5; }
        .nav-item::after { content:''; position:absolute; top:100%; left:0; right:0; height:4px; }
        .nav-dropdown { display:none; position:absolute; top:100%; left:0; margin-top:4px; background:#fff; min-width:240px; border-radius:var(--radius-sm,8px); box-shadow:0 8px 30px rgba(0,0,0,0.12); padding:8px 0; z-index:30; }
        .nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown { display:block; }
        .nav-dropdown a { display:block; color:#1a1a1a; padding:8px 20px; font-weight:400; font-size:0.85rem; text-decoration:none; }
        .nav-dropdown a:hover { background:#f6f5f2; color:var(--clr-accent-text,#996015); }
        .nav-toggle { display:none; background:none; border:none; color:#fff; padding:6px; cursor:pointer; }
        .nav-toggle svg { width:24px; height:24px; }
        @media (max-width:640px) {
            .nav-toggle { display:block; }
            .nav-links { display:none; position:absolute; top:100%; left:0; right:0; background:#0a0a0a; flex-direction:column; padding:8px 20px 20px; border-top:1px solid #2a2a2a; }
            .nav-links.open { display:flex; }
            .nav-links > a, .nav-item { margin:0; }
            .nav-links > a, .nav-item > a { padding:10px 0; }
            .nav-item > a::after { display:none; }
            .nav-dropdown { position:static; box-shadow:none; margin-top:0; padding-left:16px; display:block; background:transparent; border:none; }
            .nav-dropdown a { color:#888; padding:6px 0; font-size:0.8rem; }
            .nav-dropdown a:hover { background:transparent; color:#fff; }
        }
"""


def transform_dropdown_page(html):
    """Pages that already have a header with a nav dropdown. Idempotent."""
    # 1) Replace the dropdown markup with the mega version (keep the existing <a> trigger).
    if 'nav-dropdown--mega' not in html:
        pat = re.compile(
            r'(<div class="nav-item">)(<a[^>]*>[^<]*</a>)(<div class="nav-dropdown">)(.*?)(</div></div>)',
            re.S,
        )
        html, n = pat.subn(lambda m: m.group(1) + m.group(2) + '<div class="nav-dropdown nav-dropdown--mega">' + MEGA_GROUPS + '</div></div>', html, count=1)
        if n == 0:
            print("  !! no nav-item dropdown markup found")

    # 1b) Drop a literal ▾ caret from the trigger text (CSS ::after draws it).
    html = re.sub(r'(<div class="nav-item"><a[^>]*>)[^<]*▾([^<]*</a>)', r'\1\2', html, count=1)

    # 2) Base .nav-dropdown rule -> white (spaced or minified). Idempotent.
    html, n = re.subn(r'\.nav-dropdown\s*\{[^}]*\}', (
        '.nav-dropdown { display:none; position:absolute; top:100%; left:0; margin-top:14px; '
        'background:#ffffff; min-width:240px; border-radius:var(--radius-sm); '
        'box-shadow:var(--shadow-lg); padding:8px 0; z-index:30; }'
    ), html, count=1)
    if n == 0:
        print("  !! no base .nav-dropdown css rule")

    # 3) Link color in first .nav-dropdown a rule (dark -> dark-on-white).
    html = re.sub(r'(\.nav-dropdown a\s*\{[^}]*?color:#ffffff)', lambda m: m.group(1).replace('color:#ffffff', 'color:#1a1a1a'), html, count=1)
    # 4) Hover in the desktop .nav-dropdown a:hover rule (white bg variant).
    html = re.sub(r'(\.nav-dropdown a:hover\s*\{[^}]*?)background:#2a2a2a', lambda m: m.group(1) + 'background:#f6f5f2', html, count=1)
    def _fix_hover(m):
        s = m.group(0)
        return s.replace('color:#fff;', 'color:var(--clr-accent-text);').replace('color:#fff}', 'color:var(--clr-accent-text)}')
    html = re.sub(r'\.nav-dropdown a:hover\s*\{[^}]*background:#f6f5f2[^}]*\}', _fix_hover, html, count=1)

    # 4b) Fix mangled dropdown caret in .nav-item > a::after.
    html = re.sub(r"(\.nav-item\s*>\s*a::after\s*\{\s*content:')[^']*(')", lambda m: m.group(1) + '\\25be' + m.group(2), html, count=1)

    # 5) Inject MEGA_MENU_CSS before </style> (idempotent).
    if MEGA_MENU_CSS not in html:
        html = html.replace('</style>', MEGA_MENU_CSS + '\n</style>', 1)

    return html


def transform_footer_css(html):
    """Replace token-based footer CSS with canonical full-footer CSS. Idempotent."""
    if not re.search(r'\.footer\s*\{', html):
        print("  + injecting literal footer CSS (no token-based rules)")
        if FOOTER_CSS_LITERAL not in html:
            html = html.replace('</style>', FOOTER_CSS_LITERAL + '\n</style>', 1)
        return html
    rules = [
        (r'\.footer\s*\{[^}]*\}',
         '.footer { background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }'),
        (r'\.footer-grid\s*\{[^}]*\}',
         '.footer-grid { display:grid; grid-template-columns: 1.6fr 1fr 1fr 1fr; gap: var(--space-lg); margin-bottom: var(--space-xl); }'),
        (r'\.footer-col h4\s*\{[^}]*\}',
         '.footer-col h4 { color:#fff; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:14px; }'),
        (r'\.footer-col a\s*\{[^}]*\}',
         '.footer-col a { display:block; color:#999; text-decoration:none; padding:4px 0; font-size:0.9rem; }'),
        (r'\.footer-col a:hover\s*\{[^}]*\}',
         '.footer-col a:hover { color:#fff; }'),
        (r'\.footer-social\s*\{[^}]*\}',
         '.footer-social { display:flex; gap:10px; margin-top:16px; }'),
        (r'\.footer-social a\s*\{[^}]*\}',
         '.footer-social a { width:44px; height:44px; border-radius:50%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:#ccc; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }'),
        (r'\.footer-social a:hover\s*\{[^}]*\}',
         '.footer-social a:hover { background: var(--clr-accent); color:#0a0a0a; }'),
        (r'\.footer-social svg\s*\{[^}]*\}',
         '.footer-social svg { width:16px; height:16px; }'),
        (r'\.footer-bottom\s*\{[^}]*\}',
         '.footer-bottom { border-top:1px solid #222; padding-top:20px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:0.85rem; color:#777; }'),
    ]
    for pat, repl in rules:
        html, n = re.subn(pat, repl, html, count=1)
        if n == 0:
            print("  !! footer css rule not found: " + pat)
    # Media query: normalize any footer-grid breakpoint to 1fr 1fr (tolerant of formatting).
    html, n = re.subn(
        r'@media \(max-width:\s*760px\)\s*\{\s*\.footer-grid\s*\{\s*grid-template-columns:[^}]*\}\s*\}',
        '@media (max-width: 760px) { .footer-grid { grid-template-columns: 1fr 1fr; } }',
        html, count=1)
    if n == 0:
        print("  !! footer media query not found")
    # Ensure .footer-col p exists.
    if '.footer-col p' not in html:
        html = html.replace('.footer-col h4 {', '.footer-col p { color:#999; font-size:0.9rem; max-width:32ch; }\n        .footer-col h4 {', 1)
    return html


def dedupe_nav_scripts(html):
    """Keep only the last nav-toggle <script> block (header template already includes one)."""
    blocks = list(re.finditer(r'<script>[\s\S]*?</script>', html, re.S))
    nav = [m for m in blocks if 'nav-toggle' in m.group(0)]
    for m in nav[:-1]:
        html = html.replace(m.group(0), '')
    return html


def main():
    html_files = sorted(DOCS.rglob("*.html"))
    changed = []
    skipped = []
    for p in html_files:
        rel = p.relative_to(DOCS).as_posix()
        html = p.read_text(encoding="utf-8")
        orig = html
        print(f"== {rel}")

        if '<div class="nav-item">' in html:
            html = transform_dropdown_page(html)
            if '<div class="footer-col"><h4>Legal</h4>' not in html:
                html = re.sub(r'<footer[^>]*>.*?</footer>', CANON_FOOTER, html, count=1, flags=re.S)
            html = transform_footer_css(html)
        else:
            # Minimal page: inject full header + nav script + full footer + CSS.
            if 'id="nav-toggle"' not in html:
                # Strip any old top-bar / header markup.
                html = re.sub(r'<div class="top-bar">.*?</div>\s*</div>', '', html, count=1, flags=re.S) if '<div class="top-bar">' in html else html
                html = re.sub(r'<header[^>]*>.*?</header>', '', html, count=1, flags=re.S)
                # Drop stale legacy header/footer CSS rules.
                for stale in (r'\.header-inner\s*\{[^}]*\}', r'\.logo-img\s*\{[^}]*\}', r'footer\s*\{[^}]*\}', r'footer a\s*\{[^}]*\}', r'footer a:hover\s*\{[^}]*\}'):
                    html = re.sub(stale, '', html, count=1)
                # Inject header after <body>.
                html = html.replace('<body>', '<body>\n' + CANON_HEADER, 1)
            # Inject header + footer + mega CSS before </style>.
            if MEGA_MENU_CSS not in html:
                css_block = HEADER_CSS + MEGA_MENU_CSS + "\n" + FOOTER_CSS_LITERAL
                html = html.replace('</style>', css_block + '\n</style>', 1)
            # Replace footer markup.
            if '<div class="footer-col"><h4>Legal</h4>' not in html:
                html = re.sub(r'<footer[^>]*>.*?</footer>', CANON_FOOTER, html, count=1, flags=re.S)
            # Add nav-toggle script before </body>.
            if 'getElementById' not in html:
                html = html.replace('</body>', NAV_SCRIPT + '\n</body>', 1)

        # Drop duplicated nav-toggle scripts (header template already ships one).
        html = dedupe_nav_scripts(html)

        # Add Home link to the header nav if missing (idempotent).
        about_link = '        <a href="/abvorn/about.html">About</a>'
        home_link = '        <a href="/abvorn/">Home</a>'
        if about_link in html and home_link not in html:
            html = html.replace(about_link, home_link + '\n' + about_link, 1)

        if html != orig:
            p.write_text(html, encoding="utf-8")
            changed.append(rel)
        else:
            skipped.append(rel)

    print("\nCHANGED:", len(changed))
    for c in changed:
        print("  ", c)
    print("UNCHANGED:", len(skipped))
    for s in skipped:
        print("  ", s)


if __name__ == "__main__":
    main()
