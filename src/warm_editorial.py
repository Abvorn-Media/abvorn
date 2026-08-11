"""Warm-editorial review design system.

Verbatim port of the verified pilot page
(docs/reviews/wireless-earbuds/the-ultimate-2024-buying-guide-compare-haoyuyan-airpods-pro-3-and-more-wireless-earbuds-2026-08-08.html)
so every regenerated review page ships the exact design: black hero with the
"Our Choice" pick card, sticky rail (TOC + email + niche subscribe), warm paper
body, full-contrast accent buttons, and TOC orange squares.

This module also owns the HTML builders for the warm hero-pick, the review rail
(TOC + email + niche subscribe) and the "Ready to buy?" CTA banner, so both
run_cycle.build_article_page and src.deployment.build_article_page stay in sync.
"""
import html as html_mod
import re
import os
from urllib.parse import quote, urlencode

from abvorn.core.verdict import clean_product_name
from src.article_design import upgrade_product_image

WARM_EDITORIAL_CSS = """
:root {
  --clr-black: #2b2419; --clr-off-black: #1a1a1a; --clr-dark-gray: #2a2a2a;
  --clr-mid-gray: #6b6252; --clr-light-gray: #e2d8c4; --clr-off-white: #f5efe2; --clr-white: #ffffff;
  --clr-primary: var(--niche-primary, #1a1a1a); --clr-accent: #c98a2c; --clr-accent-text: #996015;
  --font-display: 'Libre Franklin', -apple-system, sans-serif; --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --scale-ratio: 1.25;
  --text-xs: calc(1rem / var(--scale-ratio) / var(--scale-ratio)); --text-sm: calc(1rem / var(--scale-ratio));
  --text-base: 1rem; --text-lg: calc(1rem * var(--scale-ratio)); --text-xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio));
  --text-2xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --text-3xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --text-4xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --space-xs: 0.25rem; --space-sm: 0.5rem; --space-md: 1rem; --space-lg: 2rem; --space-xl: 4rem; --space-2xl: 8rem;
  --radius-sm: 6px; --radius-md: 12px; --radius-lg: 16px;
  --shadow-sm: 0 1px 3px rgba(43,36,25,0.08); --shadow-md: 0 4px 12px rgba(43,36,25,0.1);
  --shadow-lg: 0 8px 30px rgba(43,36,25,0.12);
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1); --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --duration-fast: 150ms; --duration-base: 300ms; --duration-slow: 500ms;
}
*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
html { scroll-behavior: smooth; font-size: 16px; }
body { font-family: var(--font-body); font-size: var(--text-base); line-height: 1.7; color: #3f382f; background: #faf7f2; -webkit-font-smoothing: antialiased; }
::selection { background:#e6c98f; color:#241e17; }
h1, h2, h3, h4 { font-family: var(--font-display); line-height: 1.15; font-weight: 600; letter-spacing: -0.02em; color: var(--clr-black); }
h1 { font-size: var(--text-4xl); letter-spacing: -0.02em; font-weight: 600; }
h2 { font-size: var(--text-2xl); letter-spacing: -0.01em; }
h3 { font-size: var(--text-xl); }
h4 { font-size: var(--text-lg); }
p { margin-bottom: var(--space-lg); max-width: 65ch; }
a { color: var(--clr-accent-text); text-underline-offset: 3px; }
a:hover { color: #7a4c10; }
.container { width: 100%; max-width: 1200px; margin: 0 auto; padding: 0 var(--space-lg); }
@media (max-width: 768px) { .container { padding: 0 var(--space-md); } h1 { font-size: var(--text-2xl); } h2 { font-size: var(--text-xl); } }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
:focus-visible { outline: 2px solid var(--clr-accent); outline-offset: 2px; }
.skip-link { position: absolute; top: -40px; left: 8px; z-index: 200; background: var(--clr-accent); color: var(--clr-black); padding: 10px 18px; border-radius: 0 0 var(--radius-sm) var(--radius-sm); font-weight: 700; font-size: 0.85rem; text-decoration: none; transition: top var(--duration-fast) var(--ease-out); }
.skip-link:focus { top: 0; color: var(--clr-black); }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }
@media (forced-colors: active) { .btn { border: 2px solid ButtonText; } .card { border: 1px solid ButtonText; } }

header { background:#0a0a0a; padding:18px 0; border-bottom:1px solid #2a2a2a; position:sticky; top:0; z-index:100; }
.navbar { display:flex; justify-content:space-between; align-items:center; max-width:1200px; margin:0 auto; padding:0 20px; }
.logo img { max-height:44px; width:auto; }
.nav-links { display:flex; align-items:center; gap:8px; }
.nav-links > a, .nav-item > a { color:#fff; text-decoration:none; padding:8px 16px; font-weight:600; font-size:0.9rem; border-radius:var(--radius-sm); transition: background var(--duration-fast); }
.nav-links > a:hover, .nav-item > a:hover { background:rgba(255,255,255,0.08); color: var(--clr-accent); }
.nav-item { position:relative; }
.nav-item > a { padding:8px 16px; display:flex; align-items:center; gap:4px; }
.nav-item > a::after { content:'\\25BE'; font-size:0.6rem; opacity:0.5; }
.nav-item::after { content:''; position:absolute; top:100%; left:0; right:0; height:4px; }
.nav-dropdown { display:none; position:absolute; top:100%; left:0; margin-top:4px; background:#fff; min-width:240px; border-radius:var(--radius-sm); box-shadow:var(--shadow-lg); padding:8px 0; z-index:30; }
.nav-item:hover .nav-dropdown, .nav-item:focus-within .nav-dropdown { display:block; }
.nav-dropdown a { display:block; color:#1a1a1a; padding:8px 20px; font-weight:400; font-size:0.85rem; text-decoration:none; }
.nav-dropdown a:hover { background:#f6f5f2; color: var(--clr-accent-text); }
.nav-item:hover .nav-dropdown.nav-dropdown--mega, .nav-item:focus-within .nav-dropdown.nav-dropdown--mega { display:flex; opacity:1; transform:translateY(0); transition:opacity var(--duration-fast) var(--ease-out),transform var(--duration-fast) var(--ease-out); }
@starting-style {
    .nav-item:hover .nav-dropdown.nav-dropdown--mega, .nav-item:focus-within .nav-dropdown.nav-dropdown--mega { opacity:0; transform:translateY(6px); }
}
.nav-dropdown.nav-dropdown--mega { flex-wrap:wrap; gap:6px 8px; min-width:600px; max-width:90vw; padding:14px 18px; right:0; left:auto; }
.nav-dropdown.nav-dropdown--mega .category-group { display:block; flex:1 1 200px; min-width:170px; }
.nav-dropdown.nav-dropdown--mega .category-label { display:block; color:var(--clr-accent-text,var(--clr-accent,#c98a2c)); font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; padding:4px 20px 2px; }
.nav-dropdown.nav-dropdown--mega a { padding:6px 20px; }
@media (max-width:640px) {
    .nav-dropdown.nav-dropdown--mega { display:block; min-width:0; max-width:none; padding:0; opacity:1; transform:none; }
    .nav-dropdown.nav-dropdown--mega .category-group { display:block; flex:1 1 auto; }
    .nav-dropdown.nav-dropdown--mega .category-label { padding:8px 0 2px; }
    .nav-dropdown.nav-dropdown--mega a { padding:5px 0; }
}
.nav-toggle { display:none; background:none; border:none; color:#fff; padding:6px; cursor:pointer; }
.nav-toggle svg { width:24px; height:24px; }
@media (max-width: 640px) {
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

/* -- Article hero (warm editorial) -- */
.article-hero { background:#0a0a0a; padding: var(--space-xl) 0 var(--space-lg); border-bottom:1px solid #2a2a2a; }
.article-hero__inner { animation: doc-rise 0.7s var(--ease-out) both; }
@keyframes doc-rise { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:none; } }
.hero-meta { display:flex; align-items:center; flex-wrap:wrap; gap:8px 16px; font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#d4a03a; margin-bottom: var(--space-md); }
.hero-meta .dot { width:6px; height:6px; border-radius:2px; background:var(--clr-accent); }
.hero-meta .date { color:#b8ad9b; font-weight:600; text-transform:none; letter-spacing:0.02em; }
.article-hero h1 { font-size: clamp(var(--text-3xl), 4.2vw, var(--text-4xl)); color:#f5efe2; margin-bottom: var(--space-md); max-width: 20ch; }
.hero-excerpt { font-size: var(--text-lg); color:#d6cdbb; max-width: 60ch; line-height:1.65; margin-bottom: var(--space-lg); }
.hero-grid { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap: var(--space-xl); align-items:center; }
.hero-pick { background:#ffffff; border:1px solid #e2d8c4; border-radius:var(--radius-lg); padding:20px; box-shadow:var(--shadow-sm); }
.hero-pick .cta-row { flex-wrap:nowrap; }
.hero-pick .cta-row .btn { flex:1 1 auto; justify-content:center; white-space:nowrap; padding:0.6em 0.9em; font-size:0.8rem; }
.hero-pick__media { aspect-ratio:1/1; width:100%; background:#ffffff; border:1px solid #e2d8c4; border-radius:var(--radius-md); display:flex; align-items:center; justify-content:center; overflow:hidden; margin-bottom: var(--space-md); }
.hero-pick__media img { width:100%; height:100%; object-fit:contain; padding: var(--space-md); }
.hero-pick__name { font-size: var(--text-lg); color:#2b2419; margin-bottom:4px; }
.hero-pick__meta { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom: var(--space-md); }
.hero-pick__score { display:inline-flex; align-items:center; gap:6px; background:var(--clr-accent); color:#241e17; font-weight:800; padding:3px 12px; border-radius:100px; font-size:0.78rem; }
.hero-pick__price { color:#6b6252; font-weight:600; font-size:0.9rem; }
.cta-row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.btn { display:inline-flex; align-items:center; gap:8px; padding:0.65em 1.25em; font-family:var(--font-body); font-weight:700; font-size:0.85rem; text-decoration:none; border-radius:var(--radius-sm); cursor:pointer; transition: background var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-spring), box-shadow var(--duration-fast) var(--ease-out); border:1px solid transparent; }
.btn:hover { transform: translateY(-1px); }
.btn:active { transform: scale(0.97); }
.btn.btn--accent { background:var(--clr-accent); color:#241e17; }
.btn.btn--accent:hover { background:#d4a03a; color:#241e17; box-shadow:var(--shadow-md); }
.btn.btn--ink { background:#2b2419; color:#faf7f2; }
.btn.btn--ink:hover { background:#1a150e; color:#fff; box-shadow:var(--shadow-md); }
.btn.btn--ghost { background:#f1e9d7; color:#2b2419; border-color:#c98a2c; }
.btn.btn--ghost:hover { background:var(--clr-accent); color:#241e17; }
.btn.btn--light { background:#ffffff; color:#2b2419; border-color:#e2d8c4; }
.btn.btn--light:hover { border-color:#c98a2c; color:#996015; }

/* -- Review layout: main + rail -- */
.review-layout { display:grid; grid-template-columns: minmax(0,1fr) 300px; gap: var(--space-xl); padding: var(--space-xl) 0 var(--space-2xl); }
.review-rail { position:sticky; top:96px; align-self:start; display:flex; flex-direction:column; gap: var(--space-lg); }
.rail-card { background:#ffffff; border:1px solid #e2d8c4; border-radius:var(--radius-lg); padding: var(--space-lg); }
.rail-card__title { font-family:var(--font-display); font-weight:700; text-transform:uppercase; letter-spacing:0.06em; font-size:0.72rem; color:#996015; margin-bottom: var(--space-md); padding-bottom: var(--space-sm); border-bottom:1px solid #e2d8c4; }
.rail-card p { font-size:0.88rem; color:#4a4236; margin-bottom: var(--space-md); line-height:1.6; }
.rail-card .input { width:100%; padding:0.7em 1em; font-family:var(--font-body); font-size:0.9rem; color:#3f382f; background:#f5efe2; border:2px solid transparent; border-radius:var(--radius-sm); margin-bottom:10px; transition: border-color var(--duration-fast) var(--ease-out); }
.rail-card .input:focus { outline:none; border-color:var(--clr-accent); background:#fff; }
.rail-card .btn { width:100%; justify-content:center; }
.rail-card .form-note { font-size:0.78rem; color:#6b6252; margin-top:8px; line-height:1.5; }
.subscribe-msg { font-size:0.8rem; color:#4a4236; margin-top:10px; font-weight:600; }
.rail-toc ol { list-style:none; padding:0; margin:0; }
.rail-toc li { margin-bottom:2px; }
.rail-toc a { display:flex; align-items:center; gap:10px; padding:6px 10px; border-radius: var(--radius-sm); color:#5a5146; text-decoration:none; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
.rail-toc a::before { content:''; width:6px; height:6px; border-radius:2px; background:var(--clr-accent); flex-shrink:0; }
.rail-toc a:hover { color:#2b2419; background:#f1e9d7; }
.mailto-btn { display:flex; align-items:center; gap:10px; text-decoration:none; color:#2b2419; font-weight:600; font-size:0.9rem; padding:10px 12px; border-radius:var(--radius-sm); transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
.mailto-btn:hover { background:#f1e9d7; color:#996015; }
.mailto-btn svg { flex-shrink:0; color:var(--clr-accent); }

/* -- Article body -- */
.article-body { max-width: 72ch; min-width:0; }
.disclosure { background:#f1e9d7; border-radius: var(--radius-md); padding: var(--space-md) var(--space-lg); font-size:0.85rem; color:#6b6252; margin-bottom: var(--space-lg); }
.article-body p { color:#4a4236; margin-bottom: var(--space-md); }
.article-body h2 { font-size: var(--text-xl); margin: var(--space-xl) 0 var(--space-md); color:#2b2419; scroll-margin-top:110px; }
.article-body h3 { font-size: var(--text-lg); margin: var(--space-lg) 0 var(--space-sm); color:#2b2419; scroll-margin-top:110px; }
.article-body ul, .article-body ol { margin:0 0 var(--space-md); padding-left:1.4em; color:#4a4236; }
.article-body li { margin-bottom: var(--space-sm); }
.article-body strong { color:#2b2419; }
.article-body a { color:#996015; text-decoration:underline; text-underline-offset:3px; text-decoration-thickness:1px; }
.article-body a:hover { color:#7a4c10; }
.article-body a.btn { text-decoration:none; }

/* -- Abvorn Verdict -- */
.abvorn-verdict { background:#ffffff; border:1px solid #e2d8c4; border-radius:var(--radius-lg); padding:28px 32px; margin: var(--space-lg) 0 var(--space-lg); box-shadow:var(--shadow-sm); }
.av-badge { display:inline-flex; align-items:center; gap:6px; background:#2b2419; color:#faf7f2; font-size:.7rem; font-weight:800; padding:4px 14px; border-radius:100px; text-transform:uppercase; letter-spacing:.08em; margin-bottom:16px; }
.av-badge::before { content:''; width:7px; height:7px; border-radius:2px; background:var(--clr-accent); }
.av-score-row { display:flex; align-items:center; gap:20px; margin-bottom:20px; }
.av-score { display:flex; align-items:baseline; gap:2px; }
.av-number { font-size:3rem; font-weight:800; font-family:var(--font-display); color:#2b2419; line-height:1; letter-spacing:-.03em; }
.av-outof { font-size:1.2rem; color:#6b6252; font-weight:600; }
.av-label-row { display:flex; flex-direction:column; gap:2px; }
.av-label { font-size:1.05rem; font-weight:700; color:var(--clr-accent-text); font-family:var(--font-display); }
.av-product { font-size:1.15rem; font-weight:700; color:#2b2419; font-family:var(--font-display); line-height:1.3; margin:0 0 4px; }
.av-breakdown { display:flex; flex-direction:column; gap:8px; margin-bottom:20px; }
.av-bar-row { display:flex; align-items:center; gap:12px; }
.av-bar-label { flex:0 0 140px; font-size:.82rem; font-weight:600; color:#5a5146; text-align:right; }
.av-bar-track { flex:1; height:8px; background:#f1e9d7; border-radius:100px; overflow:hidden; }
.av-bar-fill { height:100%; border-radius:100px; transition:width .6s cubic-bezier(.4,0,.2,1); }
.av-bar-score { flex:0 0 36px; font-size:.85rem; font-weight:700; color:#2b2419; text-align:right; }
.av-summary { font-size:.95rem; color:#5a5146; line-height:1.55; margin-bottom:20px; }
.av-cta { display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
@media(max-width:640px){ .av-score-row{flex-direction:column;align-items:flex-start;gap:8px} .av-bar-label{flex:0 0 96px;font-size:.75rem} .abvorn-verdict{padding:20px 16px} }

/* -- Product reviews -- */
.product-review { display:grid; grid-template-columns: 240px minmax(0,1fr); gap: var(--space-lg); padding: var(--space-lg) 0; border-bottom:1px solid #e2d8c4; scroll-margin-top:110px; }
.product-review:first-of-type { border-top:1px solid #e2d8c4; }
.product-figure { aspect-ratio:1/1; background:#ffffff; border:1px solid #e2d8c4; border-radius:var(--radius-md); display:flex; align-items:center; justify-content:center; overflow:hidden; }
.product-figure img { width:100%; height:100%; object-fit:contain; padding: var(--space-md); }
.product-review__head { display:flex; align-items:baseline; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
.product-review__head h3 { margin:0; font-size: var(--text-lg); }
.rank-chip { display:inline-block; background:#f1e9d7; color:#996015; padding:3px 10px; font-size:0.68rem; font-weight:800; text-transform:uppercase; letter-spacing:0.05em; border-radius:100px; white-space:nowrap; }
.product-review__meta { font-size:0.88rem; color:#6b6252; margin-bottom:10px; }
.product-review__meta strong { color:#2b2419; }
.product-review .price { color:#996015; font-weight:700; }
.product-review__desc { margin-bottom: var(--space-md); }
.pros-cons { display:grid; grid-template-columns:1fr 1fr; gap: var(--space-md); margin-bottom: var(--space-md); }
.pros-cons h4 { font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; color:#996015; margin-bottom:6px; font-weight:700; }
.pros-cons ul { margin:0; padding-left:1.2em; }
.pros-cons li { font-size:0.88rem; margin-bottom:4px; color:#4a4236; }
.bottom-line { background:#f1e9d7; border-radius: var(--radius-md); padding:12px 16px; font-size:0.9rem; color:#4a4236; margin-bottom: var(--space-md); }
.bottom-line strong { color:#2b2419; }
@media (max-width: 720px) { .product-review { grid-template-columns:1fr; gap: var(--space-md); } .product-figure { max-width:260px; } .pros-cons { grid-template-columns:1fr; } }

/* -- Tables -- */
.table-wrap { overflow-x:auto; margin: var(--space-md) 0 var(--space-lg); border:1px solid #e2d8c4; border-radius: var(--radius-md); background:#fff; padding: 18px 20px 4px; }
.doc-table { width:100%; border-collapse:collapse; font-size:0.92rem; min-width:520px; }
.doc-table th { text-align:left; font-family:var(--font-display); font-weight:700; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em; color:#2b2419; background:#f1e9d7; padding:10px 14px; border-bottom:1px solid #e2d8c4; }
.doc-table td { padding:12px 14px; border-top:1px solid #e2d8c4; color:#4a4236; vertical-align:top; }
.doc-table tr:first-child td { border-top:none; }
.decision-matrix td:first-child { font-weight:700; color:#2b2419; white-space:nowrap; }

/* -- Chart -- */
.chart-section { margin: var(--space-lg) 0; padding: var(--space-lg); background:#ffffff; border-radius:var(--radius-lg); border:1px solid #e2d8c4; }
.chart-wrapper { width:100%; max-width:500px; height:400px; margin:0 auto; }
.chart-note { text-align:center; font-size:0.8rem; color:#6b6252; margin-top: var(--space-sm); margin-bottom:0; }
@media (max-width:600px) { .chart-wrapper { height:300px; } }

/* -- CTA banner -- */
.cta-banner { background:#2b2419; color:#faf7f2; border-radius:var(--radius-lg); padding: clamp(28px,4vw,44px); margin: var(--space-xl) 0; position:relative; overflow:hidden; }
.cta-banner::before { content:''; position:absolute; inset:0; background:radial-gradient(circle at 20% 30%, rgba(201,138,44,.25), transparent 55%); }
.cta-banner > * { position:relative; }
.cta-banner h3 { color:#fff; font-size: clamp(1.2rem,2.5vw,1.7rem); margin-bottom:8px; }
.cta-banner p { color:#e6dcc8; max-width:56ch; margin-bottom:20px; }
.cta-banner .btn { background:var(--clr-accent); color:#241e17; font-weight:800; }
.cta-banner .btn:hover { background:#e0a23f; }

/* -- FAQ -- */
.faq-section { margin: var(--space-xl) 0; }
.faq-item { background:#ffffff; border:1px solid #e2d8c4; border-radius: var(--radius-md); margin-bottom: var(--space-sm); overflow:hidden; }
.faq-item summary { cursor:pointer; padding:14px 18px; font-weight:700; font-size:var(--text-base); color:var(--clr-black); list-style:none; display:flex; align-items:center; gap:10px; font-family:var(--font-display); }
.faq-item summary::-webkit-details-marker{display:none}
.faq-item summary::before { content:''; width:9px; height:9px; border-right:2px solid var(--clr-accent); border-bottom:2px solid var(--clr-accent); transform:rotate(45deg) translateY(-2px); transition:transform var(--duration-fast) var(--ease-out); flex-shrink:0; }
.faq-item[open] summary::before { transform:rotate(225deg) translateY(2px); }
.faq-item .faq-answer { padding:0 18px 16px 38px; font-size:var(--text-sm); color:#4a4236; line-height:1.7; }
.faq-item .faq-answer p { margin:0 0 8px; max-width:70ch; color:#4a4236; }
.faq-item .faq-answer p:last-child { margin:0; }

/* -- Reactions & share -- */
.reactions-bar { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin: var(--space-xl) 0 var(--space-lg); padding-top: var(--space-lg); border-top:1px solid #e2d8c4; }
.reactions-bar .reactions-label { font-size:0.85rem; font-weight:700; color:#6b6252; margin-right:4px; }
.reactions-bar .reaction-btn { display:inline-flex; align-items:center; gap:6px; padding:7px 16px; border:1px solid #e2d8c4; border-radius:999px; background:#fff; color:#6b6252; font-size:0.85rem; font-weight:600; font-family:var(--font-body); cursor:pointer; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-out); }
.reactions-bar .reaction-btn:hover { border-color:var(--clr-accent); color:#996015; }
.reactions-bar .reaction-btn.active { border-color:var(--clr-accent); background:var(--clr-accent); color:#241e17; }
.reactions-bar .reaction-btn.loved { border-color:#c0694f; color:#a34a35; background:#f7e4dc; }
.reactions-bar .reaction-count { font-weight:700; min-width:16px; text-align:center; }
.share-row { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin: var(--space-lg) 0 var(--space-xl); padding-top: var(--space-lg); border-top:1px solid #e2d8c4; }
.share-row .share-label { font-size:0.85rem; font-weight:700; color:#6b6252; margin-right:8px; }
.share-btn { display:inline-flex; align-items:center; gap:6px; padding:8px 14px; background:#fff; border:1px solid #e2d8c4; border-radius:var(--radius-sm); font-size:0.85rem; color:#5a5146; text-decoration:none; transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-out); }
.share-btn:hover { border-color:var(--clr-accent); color:#996015; background:#f5efe2; transform:translateY(-1px); }
.share-btn svg { width:15px; height:15px; }

/* -- Further reading & related -- */
.further-reading { margin-top: var(--space-xl); border-top:1px solid #e2d8c4; padding-top: var(--space-lg); }
.further-reading h3 { font-size: var(--text-lg); margin-bottom: var(--space-md); }
.further-reading ul { list-style:none; padding:0; }
.further-reading li { margin-bottom:8px; }
.further-reading a { color:#996015; text-decoration:none; font-weight:600; }
.further-reading a:hover { color:#7a4c10; text-decoration:underline; }
.related-cats { margin-top: var(--space-xl); }
.grid-3 { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap: var(--space-md); }
.cat-card { padding: var(--space-md) var(--space-lg); border:1px solid #e2d8c4; border-radius: var(--radius-md); background:#fff; text-decoration:none; display:block; transition: border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-out); }
.cat-card:hover { border-color:var(--clr-accent); box-shadow:var(--shadow-sm); transform:translateY(-2px); }
.cat-card .cat-name { font-weight:700; font-size:1rem; color:#2b2419; margin-bottom:2px; font-family:var(--font-display); }
.cat-card .cat-count { font-size:0.82rem; color:#6b6252; }

/* -- RPS widget (warm) -- */
.rps-container { border:1px solid #e2d8c4; border-radius: var(--radius-lg); padding: var(--space-lg); margin: var(--space-lg) 0; background:#fff; box-shadow:var(--shadow-sm); }
.rps-badge { display:inline-flex; align-items:center; gap:6px; font-size:.7rem; font-weight:800; color:#996015; text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px; }
.rps-badge::before { content:''; width:7px; height:7px; border-radius:2px; background:var(--clr-accent); }
.rps-header { border-left:3px solid var(--clr-accent); padding-left:16px; margin-bottom:16px; }
.rps-score { display:flex; align-items:baseline; gap:8px; margin-bottom:4px; }
.rps-number { font-size:2.2rem; font-weight:800; font-family:var(--font-display); line-height:1; letter-spacing:-.03em; color:#2b2419; }
.rps-product-name { font-size:.9rem; color:#6b6252; font-weight:500; }
.rps-section-title { font-size:.82rem; font-weight:800; color:#2b2419; margin-bottom:8px; text-transform:uppercase; letter-spacing:.04em; }
.rps-reasons { margin-bottom:16px; }
.rps-reason { padding:10px 14px; border-radius: var(--radius-sm); margin-bottom:8px; font-size:.88rem; line-height:1.5; border-left:3px solid; }
.rps-reason.rps-mismatch { background:#fbe9e2; border-color:#c0694f; color:#8a3a26; }
.rps-reason.rps-notice { background:#faf3df; border-color:#d4a03e; color:#7a5a12; }
.rps-tip { font-size:.85rem; color:#5a5146; padding:12px; background:#f1e9d7; border-radius: var(--radius-sm); margin-bottom:16px; line-height:1.4; }
.rps-alt-title { font-size:.82rem; font-weight:800; color:#2b2419; margin-bottom:10px; text-transform:uppercase; letter-spacing:.04em; }
.rps-alt-item { display:flex; align-items:center; gap:12px; padding:12px 14px; border:1px solid #e2d8c4; border-radius: var(--radius-sm); margin-bottom:8px; text-decoration:none; background:#fff; transition: border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out); }
.rps-alt-item:hover { text-decoration:none; border-color:var(--clr-accent); box-shadow:var(--shadow-sm); }
.rps-alt-name { flex:1; font-weight:600; color:#2b2419; font-size:.9rem; }
.rps-alt-prob { font-size:.78rem; font-weight:700; white-space:nowrap; }
.rps-alt-price { font-size:.8rem; color:#6b6252; }
.rps-footer { font-size:.78rem; color:#6b6252; display:flex; align-items:center; gap:12px; margin-top:12px; padding-top:12px; border-top:1px solid #e2d8c4; }
.rps-reset { background:none; border:1px solid #e2d8c4; border-radius:100px; padding:4px 12px; font-size:.75rem; color:#6b6252; cursor:pointer; font-family:inherit; transition: border-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
.rps-reset:hover { border-color:#2b2419; color:#2b2419; }

/* -- Footer -- */
.footer { background:#0a0a0a; color:#999; padding: var(--space-2xl) 0 var(--space-lg); }
.footer-grid { display:grid; grid-template-columns:1.6fr 2fr 1fr; gap: var(--space-lg); margin-bottom: var(--space-xl); }
.footer-cat-cols { display: flex; gap: var(--space-xl); }
.footer-cat-col { display: flex; flex-direction: column; }
.footer-col h4 + a + h4 { margin-top: var(--space-lg); }
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

@media (max-width: 960px) {
    .hero-grid { grid-template-columns:minmax(0,1fr); gap: var(--space-lg); }
    .review-layout { grid-template-columns: minmax(0,1fr); gap: var(--space-lg); }
    .review-rail { position:static; }
}
@media (max-width: 720px) {
    .hero-grid { grid-template-columns:minmax(0,1fr); }
    .hero-pick { max-width: 320px; }
}

#cookie-banner{position:fixed;bottom:0;left:0;right:0;background:#0a0a0a;color:#fff;padding:16px 24px;z-index:9999;display:none;font-size:13px;line-height:1.5;box-shadow:0 -4px 12px rgba(0,0,0,.15)}
#cookie-banner.show{display:flex;flex-wrap:wrap;align-items:center;gap:12px;justify-content:center}
#cookie-banner p{margin:0;color:#ffffff;font-size:13px}
#cookie-banner a{color:#c98a2c;text-decoration:underline}
#cookie-banner .btn{background:#c98a2c;color:#0a0a0a;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700}
#cookie-banner .btn:hover{background:#d4a03a}
#cookie-banner .btn-secondary{background:transparent;color:#ffffff;border:1px solid #555;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px}
#cookie-banner .btn-secondary:hover{border-color:#888}
"""

# ── Legacy token aliases ────────────────────────────────────────────────
# The shared helpers in article_design.py and the legacy builder CSS still
# reference the generic --bg-alt/--border/--text-muted/--text-secondary/--bg
# tokens. Aliasing them to the warm palette keeps every shared rule working.
WARM_TOKEN_SHIM_CSS = """
:root {
  --bg-alt:#f5efe2; --border:#e2d8c4; --text-muted:#6b6252;
  --text-secondary:#4a4236; --bg:#ffffff; --text:#2b2419; --primary:#2b2419;
}
"""

# ── Products-mentioned grid (warm restyle) ───────────────────────────────
# The pilot has no grid; the products appear as hand-written .product-review
# blocks in prose. The generator keeps the lineup grid but renders it warm.
# Class markers are renamed .warm-product-* so the shared legacy .product-card
# CSS (which clobbers .product-section) never collides with the grid.
WARM_PRODUCT_GRID_CSS = """
.warm-product-section{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--space-lg)}
.warm-grid-heading{font-family:var(--font-display);font-weight:600;letter-spacing:-0.01em;font-size:var(--text-2xl);color:var(--clr-black);margin:var(--space-xl) 0 var(--space-md);scroll-margin-top:110px}
.warm-grid-heading + .warm-product-section{margin-top:0}
.warm-product-card{display:flex;flex-direction:column;gap:var(--space-md);background:#ffffff;border:1px solid #e2d8c4;border-radius:var(--radius-lg);padding:var(--space-lg);box-shadow:var(--shadow-sm)}
.warm-product-card .warm-product-card__media{aspect-ratio:1/1;width:100%;background:#ffffff;border:1px solid #e2d8c4;border-radius:var(--radius-md);display:flex;align-items:center;justify-content:center;overflow:hidden}
.warm-product-card .warm-product-card__media img{width:100%;height:100%;object-fit:contain;padding:var(--space-md)}
.warm-product-card__name{font-size:var(--text-base);color:#2b2419;margin-bottom:2px;font-family:var(--font-display)}
.warm-product-card__price{color:#996015;font-weight:700;font-size:0.9rem;margin-bottom:4px}
.warm-product-card__summary{font-size:0.85rem;color:#5a5146;margin-bottom:6px}
.warm-product-card .cta-row{flex-wrap:wrap}
.warm-product-card .cta-row .btn{flex:1 1 auto;justify-content:center;white-space:nowrap;padding:0.6em 0.9em;font-size:0.8rem}
"""

# ── Warm share row ───────────────────────────────────────────────────────
# Pilot-style share row with warm tokens (replaces the legacy inline-styled
# SHARE_HTML_T whose var(--border) etc. tokens do not exist on the warm page).
WARM_SHARE_HTML_T = """<div class="share-row">
<span class="share-label">Share:</span>
<a class="share-btn" href="https://twitter.com/intent/tweet?text=TITLE_T&url=URL_T&via=Abvorn" target="_blank" rel="noopener" aria-label="Share on X"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg> X</a>
<a class="share-btn" href="https://www.facebook.com/sharer/sharer.php?u=URL_T" target="_blank" rel="noopener" aria-label="Share on Facebook"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg> Facebook</a>
<a class="share-btn" href="https://pinterest.com/pin/create/button/?url=URL_T&description=TITLE_T" target="_blank" rel="noopener" aria-label="Share on Pinterest"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146 1.124.347 2.317.535 3.554.535 6.607 0 11.974-5.367 11.974-11.987C23.97 5.367 18.603.001 12.017.001z"/></svg> Pinterest</a>
<a class="share-btn" href="mailto:?subject=TITLE_T&body=URL_T" aria-label="Share via Email"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg> Email</a>
</div>"""


def _compare_qs(product, overall="", label="", include_score=True):
    """Build the compare.html query string from a product dict."""
    name = clean_product_name(product.get("name", "Product"))
    asin = product.get("asin") or _extract_asin(product.get("url", ""))
    params = {
        "asin": asin,
        "name": name,
        "price": str(product.get("price", "") or ""),
        "image": product.get("image", "") or "",
        "url": product.get("url", "") or "",
    }
    if include_score:
        params["score"] = str(overall or product.get("verdict_score", "") or "")
        params["label"] = str(label or product.get("verdict_label", "") or "")
    return urlencode(params)


def _extract_asin(product_url):
    m = re.search(r"/dp/([A-Z0-9]{10})", product_url or "")
    return (m.group(1) if m else "").upper()


def warm_hero_pick_html(product, overall, label, affiliate_url, base="", niche_slug=""):
    """The pilot hero-pick card: 1:1 white media tile, name, score + price,
    and a cta-row with btn--accent Amazon + btn--ghost compare."""
    if not product:
        return ""
    name = clean_product_name(product.get("name", "Our Choice"))
    price = product.get("price", "Check price")
    image = upgrade_product_image(product.get("image", ""))
    if image:
        shot = (
            f'<div class="hero-pick__media"><img src="{html_mod.escape(image)}" '
            f'alt="{html_mod.escape(name)}" loading="eager" width="400" height="400"></div>'
        )
    else:
        shot = (
            '<div class="hero-pick__media"><span style="color:var(--clr-mid-gray);'
            f'font-size:.8rem;text-align:center;padding:20px">{html_mod.escape(name)}</span></div>'
        )
    compare_href = f"{base}/compare.html?{_compare_qs(product, overall, label)}"
    return f"""
    <aside class="hero-pick">
        {shot}
        <h2 class="hero-pick__name">{html_mod.escape(name)}</h2>
        <div class="hero-pick__meta">
            <span class="hero-pick__score">Abvorn {html_mod.escape(str(overall or ''))}/10 &middot; {html_mod.escape(label or 'Score')}</span>
            <span class="hero-pick__price">{html_mod.escape(str(price))}</span>
        </div>
        <div class="cta-row">
            <a class="btn btn--accent" href="{affiliate_url}" target="_blank" rel="sponsored" data-track="value">Check Price on Amazon &rarr;</a>
            <a class="btn btn--ghost" href="{compare_href}" data-track="compare">Compare &oplus;</a>
        </div>
    </aside>"""


def warm_product_card_html(product, affiliate_url="", base="", overall="", label=""):
    """Warm product card for the Products Mentioned grid.

    Renders the shared `.warm-product-card` markup (media tile, name, price,
    summary) with a full-contrast btn--accent Amazon CTA plus a btn--ghost
    compare link, so the grid matches the warm design system exactly.
    """
    if not product:
        return ""
    name = clean_product_name(product.get("name", "Product"))
    price = product.get("price", "Check price")
    summary = product.get("description", "") or ""
    image = upgrade_product_image(product.get("image", ""))
    if image:
        media = (
            f'<div class="warm-product-card__media"><img src="{html_mod.escape(image)}" '
            f'alt="{html_mod.escape(name)}" loading="lazy" width="400" height="400"></div>'
        )
    else:
        media = (
            '<div class="warm-product-card__media"><span style="color:var(--clr-mid-gray);'
            'font-size:.8rem;text-align:center;padding:20px">Product</span></div>'
        )
    compare_href = f"{base}/compare.html?{_compare_qs(product, overall, label)}"
    return f"""<div class="warm-product-card">
{media}
<h3 class="warm-product-card__name">{html_mod.escape(name)}</h3>
<div class="warm-product-card__price">{html_mod.escape(str(price))}</div>
<p class="warm-product-card__summary">{html_mod.escape(summary)}</p>
<div class="cta-row">
<a class="btn btn--accent" href="{affiliate_url}" target="_blank" rel="sponsored" data-track="value">Check Price on Amazon &rarr;</a>
<a class="btn btn--ghost" href="{compare_href}" data-track="compare">Compare &oplus;</a>
</div>
</div>"""


def warm_shop_cta_banner(query, tag):
    """The pilot's simple 'Ready to buy?' banner — replaces the PDF lead form."""
    t = tag or os.environ.get("AMAZON_TAG", "viraltestco-20")
    href = f"https://www.amazon.com/s?k={query}&tag={t}"
    return f"""<div class="cta-banner">
<h3>Ready to buy?</h3>
<p>We&rsquo;ve done the research. Now get the best price on Amazon.</p>
<a class="btn" href="{href}" target="_blank" rel="sponsored">Shop all picks on Amazon &rarr;</a>
</div>"""


def warm_heading_ids(article_html):
    """Assign stable slug ids to every <h2> so the rail TOC can link to them.

    Returns (article_html, [(id, heading_text), ...]).
    """
    ids = {}
    toc = []

    def _slugify(text):
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug or "section"

    def _repl(m):
        tag = m.group(1) or ""
        inner = m.group(2)
        text = re.sub(r"<[^>]+>", "", inner).strip()
        base = _slugify(text)
        n = ids.get(base, 0) + 1
        ids[base] = n
        slug = base if n == 1 else f"{base}-{n}"
        toc.append((slug, html_mod.unescape(text)))
        return f"<h2 id=\"{slug}\"{tag}>{inner}</h2>"

    out = re.sub(r"<h2(\s[^>]*)?>(.*?)</h2>", _repl, article_html, flags=re.S)
    return out, toc


def build_review_rail(post_title, article_url, niche_slug, niche_name, toc_items, base="", form_url=""):
    """The pilot review rail: TOC card + email-share card + niche subscribe card."""
    toc_links = "".join(
        f'<li><a href="#{slug}">{html_mod.escape(label)}</a></li>' for slug, label in toc_items
    )
    mailto_subject = quote(post_title)
    mailto_body = quote(
        f"Here's the {niche_name} buying guide I wanted to share:\n\n{article_url}"
    )
    mailto_href = f"mailto:?subject={mailto_subject}&amp;body={mailto_body}"
    mailto_svg = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="5" width="19" height="14" rx="2.5"/><path d="M4 7.5l8 5.5 8-5.5"/></svg>'
    return f"""
    <aside class="review-rail" aria-label="Page tools">
        <nav class="rail-card rail-toc" aria-label="In this guide">
            <p class="rail-card__title">In this guide</p>
            <ol>
                <li><a href="#verdict">Abvorn Verdict</a></li>
                {toc_links}
                <li><a href="#faq">FAQ</a></li>
            </ol>
        </nav>

        <div class="rail-card">
            <p class="rail-card__title">Email this review</p>
            <p>Send yourself a copy of this guide &mdash; specs, scores, and buy links &mdash; straight to your inbox.</p>
            <a class="mailto-btn" href="{mailto_href}" aria-label="Email this review to me">{mailto_svg}Email this review to me</a>
        </div>

        <div class="rail-card">
            <p class="rail-card__title">Get updates for this niche</p>
            <p>One email whenever we publish a new {html_mod.escape(niche_name)} guide. No spam, unsubscribe anytime.</p>
            <form id="niche-subscribe-form" onsubmit="submitNicheSubscribe(event)">
                <input type="text" name="_gotcha" style="display:none" tabindex="-1" autocomplete="off">
                <label for="niche-subscribe-email" class="sr-only">Email address</label>
                <input type="email" id="niche-subscribe-email" class="input" placeholder="you@example.com" required>
                <button type="submit" class="btn btn--ink">Notify Me</button>
                <p class="subscribe-msg" id="niche-subscribe-msg" aria-live="polite"></p>
            </form>
            <p class="form-note">Reviews in this niche are updated weekly.</p>
        </div>
    </aside>"""


WARM_NICHE_SUBSCRIBE_JS = """<script>
async function submitNicheSubscribe(e) {
    e.preventDefault();
    const f = e.target;
    const msg = document.getElementById('niche-subscribe-msg');
    if (f._gotcha.value !== "") { msg.textContent = 'Thanks! Check your inbox.'; return; }
    const email = f.querySelector('#niche-subscribe-email').value.trim();
    if (!email) return;
    msg.textContent = 'Sending...';
    const btn = f.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
        const response = await fetch(APPS_SCRIPT_URL, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email: email, niche: CATEGORY_SLUG, source: 'review_rail', lead_magnet: '{niche_name} updates' })
        });
        const result = await response.json();
        msg.textContent = result.success ? 'You are subscribed! Check your inbox to confirm.' : (result.message || 'Something went wrong, please try again.');
    } catch(err) {
        msg.textContent = 'Connection error. Please try later.';
    }
    btn.disabled = false;
}
</script>"""
