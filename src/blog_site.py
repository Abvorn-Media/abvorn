"""The Abvorn Dispatch - static page builders for the editorial blog.

Two page types, both rendered as plain HTML and written through
src.deployment.write_checked (encoding + copy gates):

  /blog/                 build_blog_index_page()   masthead, lead story,
                                                   contents list, newsletter
  /blog/<slug>/          build_blog_post_page()    photo hero, field-note
                                                   margin column, field-kit
                                                   cross-sell, FAQ, related

Design world: editorial warmth on the existing Abvorn base. Warm paper canvas,
Libre Franklin display, Newsreader reading serif, brand gold rule work. The
signature is the field-note column - numbered asides that sit in the left
margin of each section on desktop and fold inline on mobile.
"""

from __future__ import annotations

import html as html_mod
import json
import re
from datetime import date, datetime

from src.deployment import (
    ANALYTICS_HTML,
    CONSENT_CSS,
    DESIGN_SYSTEM_CSS,
    MEGA_MENU_CSS,
    SITE_BASE,
    SITE_CHROME_CSS,
    _SITE_URL,
    affiliate_url,
    build_site_footer,
    build_site_header,
)

BLOG_PATH = "blog"

# Newsreader carries the long-form reading; it is loaded only on blog pages so
# the rest of the site keeps its single Inter + Libre Franklin system.
BLOG_FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Libre+Franklin:wght@600;700;800&'
    'family=Inter:wght@400;500;600;700&'
    'family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&'
    'family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">'
)


BLOG_CSS = """
/* ── The Abvorn Dispatch ─────────────────────────────────────────── */
:root {
  --dsp-paper: #faf7f1; --dsp-paper-deep: #f1ebdf; --dsp-card: #ffffff;
  --dsp-ink: #191510; --dsp-ink-soft: #4c453a; --dsp-ink-mute: #8b8272;
  --dsp-rule: #e4dbc9; --dsp-rule-strong: #d3c6ac;
  --dsp-gold: #c98a2c; --dsp-gold-deep: #8a5a12; --dsp-gold-tint: #f6ead2;
  --dsp-sage: #5b6a54;
  --dsp-serif: 'Newsreader', Georgia, 'Times New Roman', serif;
  --dsp-display: 'Libre Franklin', -apple-system, sans-serif;
  --dsp-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
  --dsp-shadow: 0 18px 50px rgba(38, 28, 10, 0.14);
}
body.dsp { background: var(--dsp-paper); color: var(--dsp-ink); }
body.dsp .footer { background: #14110c; }
body.dsp .footer .footer-bottom { border-top-color: #2a251c; }

/* Reading progress thread (fixed under the sticky header) */
.dsp-progress { position: fixed; top: 0; left: 0; height: 3px; width: 0%;
  background: linear-gradient(90deg, var(--dsp-gold), var(--dsp-gold-deep));
  z-index: 300; transition: width 120ms linear; }

/* Shared type */
.dsp-eyebrow { display: inline-flex; align-items: center; gap: 10px;
  font-family: var(--dsp-mono); font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--dsp-gold-deep); }
.dsp-eyebrow::before { content: ''; width: 26px; height: 2px; background: var(--dsp-gold); }
.dsp-kicker { font-family: var(--dsp-mono); font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--dsp-gold-deep); }

/* ── Index: masthead ─────────────────────────────────────────────── */
.dsp-masthead { background:
    radial-gradient(120% 90% at 100% 0%, var(--dsp-gold-tint), transparent 55%),
    var(--dsp-paper-deep);
  border-bottom: 1px solid var(--dsp-rule); padding: clamp(48px, 7vw, 92px) 0 clamp(28px, 4vw, 44px); }
.dsp-masthead__title { font-family: var(--dsp-display); font-weight: 800;
  font-size: clamp(2.6rem, 7vw, 5rem); line-height: 0.98; letter-spacing: -0.03em;
  margin: 18px 0 0; color: var(--dsp-ink); }
.dsp-masthead__lede { font-family: var(--dsp-serif); font-size: clamp(1.15rem, 2.2vw, 1.5rem);
  line-height: 1.5; color: var(--dsp-ink-soft); max-width: 46ch; margin: 18px 0 30px; }
.dsp-persona-rail { display: flex; flex-wrap: wrap; gap: 10px; }
.dsp-chip { font-family: var(--dsp-mono); font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--dsp-ink-soft);
  background: var(--dsp-card); border: 1px solid var(--dsp-rule-strong);
  border-radius: 100px; padding: 9px 16px; cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out); }
.dsp-chip:hover { border-color: var(--dsp-gold); color: var(--dsp-gold-deep); }
.dsp-chip.is-active { background: var(--dsp-ink); border-color: var(--dsp-ink); color: #fff; }

/* ── Index: lead story ───────────────────────────────────────────── */
.dsp-lead { display: grid; grid-template-columns: 1.25fr 1fr; gap: clamp(20px, 3vw, 44px);
  align-items: stretch; padding: clamp(40px, 6vw, 72px) 0 clamp(20px, 3vw, 32px); }
.dsp-lead__media { position: relative; border-radius: var(--radius-lg); overflow: hidden;
  min-height: 340px; background: var(--dsp-paper-deep); box-shadow: var(--dsp-shadow); }
.dsp-lead__media img { position: absolute; inset: 0; width: 100%; height: 100%;
  object-fit: cover; transition: transform var(--duration-slow) var(--ease-out); }
.dsp-lead:hover .dsp-lead__media img { transform: scale(1.03); }
.dsp-lead__body { display: flex; flex-direction: column; justify-content: center; }
.dsp-lead__title { font-family: var(--dsp-display); font-weight: 800;
  font-size: clamp(1.7rem, 3.4vw, 2.7rem); line-height: 1.04; letter-spacing: -0.02em;
  margin: 14px 0 14px; }
.dsp-lead__title a { color: inherit; text-decoration: none; }
.dsp-lead__title a:hover { color: var(--dsp-gold-deep); }
.dsp-lead__dek { font-family: var(--dsp-serif); font-size: 1.1rem; line-height: 1.55;
  color: var(--dsp-ink-soft); max-width: 52ch; margin: 0 0 18px; }
.dsp-meta { font-family: var(--dsp-mono); font-size: 0.74rem; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--dsp-ink-mute); display: flex; flex-wrap: wrap; gap: 8px 14px; }
.dsp-meta span { display: inline-flex; align-items: center; gap: 14px; }
@media (max-width: 860px) { .dsp-lead { grid-template-columns: 1fr; }
  .dsp-lead__media { min-height: 240px; } }

/* ── Index: contents list ────────────────────────────────────────── */
.dsp-contents { padding: clamp(28px, 4vw, 52px) 0 var(--space-2xl); }
.dsp-contents__head { display: flex; align-items: baseline; justify-content: space-between;
  gap: 16px; border-bottom: 2px solid var(--dsp-ink); padding-bottom: 14px; margin-bottom: 4px; }
.dsp-contents__head h2 { font-family: var(--dsp-display); font-size: clamp(1.4rem, 2.6vw, 2rem);
  margin: 0; letter-spacing: -0.01em; }
.dsp-contents__head p { margin: 0; font-family: var(--dsp-mono); font-size: 0.74rem;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--dsp-ink-mute); }
.dsp-list { list-style: none; margin: 0; padding: 0; }
.dsp-item { display: grid; grid-template-columns: 56px 132px minmax(0, 1fr) auto;
  gap: clamp(14px, 2.4vw, 30px); align-items: center; padding: 26px 6px;
  border-bottom: 1px solid var(--dsp-rule); transition: background var(--duration-fast) var(--ease-out); }
.dsp-item:hover { background: var(--dsp-card); }
.dsp-item__no { font-family: var(--dsp-mono); font-size: 0.9rem; font-weight: 700;
  color: var(--dsp-ink-mute); }
.dsp-item__thumb { width: 132px; aspect-ratio: 4 / 3; border-radius: var(--radius-md);
  overflow: hidden; background: var(--dsp-paper-deep); }
.dsp-item__thumb img { width: 100%; height: 100%; object-fit: cover;
  transition: transform var(--duration-slow) var(--ease-out); }
.dsp-item:hover .dsp-item__thumb img { transform: scale(1.05); }
.dsp-item__title { font-family: var(--dsp-display); font-weight: 700;
  font-size: clamp(1.1rem, 2vw, 1.45rem); line-height: 1.2; letter-spacing: -0.01em; margin: 6px 0 6px; }
.dsp-item__title a { color: inherit; text-decoration: none; }
.dsp-item__title a:hover { color: var(--dsp-gold-deep); }
.dsp-item__dek { font-family: var(--dsp-serif); font-size: 1rem; line-height: 1.5;
  color: var(--dsp-ink-soft); margin: 0; max-width: 60ch; }
.dsp-item__go { font-family: var(--dsp-mono); font-size: 1.1rem; color: var(--dsp-gold-deep);
  justify-self: end; transition: transform var(--duration-fast) var(--ease-spring); }
.dsp-item:hover .dsp-item__go { transform: translateX(4px); }
.dsp-empty { padding: 48px 0; color: var(--dsp-ink-mute); font-family: var(--dsp-serif); }
@media (max-width: 760px) {
  .dsp-item { grid-template-columns: 40px minmax(0, 1fr); grid-template-areas:
    'no title' 'thumb thumb'; row-gap: 14px; }
  .dsp-item__no { grid-area: no; } .dsp-item__thumb { grid-area: thumb; width: 100%; }
  .dsp-item__body { grid-area: title; } .dsp-item__go { display: none; } }

/* ── Newsletter band ─────────────────────────────────────────────── */
.dsp-news { background: var(--dsp-ink); color: #f4efe4; border-radius: var(--radius-lg);
  padding: clamp(30px, 4vw, 54px); display: grid; grid-template-columns: 1.3fr 1fr;
  gap: clamp(20px, 3vw, 46px); align-items: center; margin: 0 auto var(--space-2xl); }
.dsp-news h2 { color: #fff; font-family: var(--dsp-display); font-size: clamp(1.5rem, 2.8vw, 2.1rem);
  margin: 10px 0 12px; letter-spacing: -0.02em; }
.dsp-news p { color: #c9c2b2; font-family: var(--dsp-serif); font-size: 1.05rem; margin: 0; max-width: 46ch; }
.dsp-news .dsp-eyebrow { color: var(--dsp-gold); }
.dsp-news form { display: flex; gap: 10px; }
.dsp-news input { flex: 1; padding: 14px 16px; border-radius: var(--radius-sm); border: 1px solid #3a352b;
  background: #221e17; color: #f4efe4; font-family: var(--dsp-mono); font-size: 0.9rem; }
.dsp-news input:focus { outline: 2px solid var(--dsp-gold); outline-offset: 1px; }
.dsp-news button { padding: 14px 22px; border: none; border-radius: var(--radius-sm);
  background: var(--dsp-gold); color: #1a1400; font-weight: 700; cursor: pointer;
  font-family: var(--dsp-mono); font-size: 0.82rem; letter-spacing: 0.05em; text-transform: uppercase; }
.dsp-news button:hover { filter: brightness(1.08); }
@media (max-width: 760px) { .dsp-news { grid-template-columns: 1fr; } .dsp-news form { flex-direction: column; } }

/* ── Post: hero + masthead card ──────────────────────────────────── */
.dsp-hero { position: relative; max-width: 1160px; margin: 0 auto; }
.dsp-hero__img { width: 100%; aspect-ratio: 16 / 8; object-fit: cover; display: block; }
.dsp-hero__credit { position: absolute; right: 14px; bottom: 12px; z-index: 2;
  font-family: var(--dsp-mono); font-size: 0.66rem; letter-spacing: 0.04em; color: #fff;
  background: rgba(20, 17, 12, 0.62); padding: 4px 10px; border-radius: 100px; backdrop-filter: blur(4px); }
.dsp-hero__credit a { color: #fff; text-decoration: underline; }
.dsp-head { max-width: 1080px; margin: -96px auto 0; padding: 0 24px; position: relative; z-index: 3; }
.dsp-head__card { background: var(--dsp-card); border: 1px solid var(--dsp-rule);
  border-radius: var(--radius-lg); box-shadow: var(--dsp-shadow); padding: clamp(26px, 4vw, 54px); }
.dsp-head__title { font-family: var(--dsp-display); font-weight: 800;
  font-size: clamp(2rem, 5vw, 3.6rem); line-height: 1.02; letter-spacing: -0.03em;
  margin: 16px 0 0; color: var(--dsp-ink); }
.dsp-head__dek { font-family: var(--dsp-serif); font-size: clamp(1.15rem, 2.2vw, 1.5rem);
  line-height: 1.5; color: var(--dsp-ink-soft); max-width: 56ch; margin: 16px 0 22px; }
@media (max-width: 860px) { .dsp-head { margin-top: -48px; } .dsp-hero__img { aspect-ratio: 4 / 3; } }

/* ── Post: body grid with field notes ────────────────────────────── */
.dsp-body { max-width: 1080px; margin: 0 auto; padding: clamp(34px, 5vw, 60px) 24px 0; }
.dsp-row { display: grid; grid-template-columns: 1fr; }
.dsp-row--full { max-width: 720px; margin: 0 auto; }
@media (min-width: 1000px) {
  .dsp-row { grid-template-columns: 208px minmax(0, 1fr); column-gap: 46px; }
  .dsp-row--full { max-width: 760px; margin: 0 auto; grid-template-columns: minmax(0, 1fr); }
}
.dsp-main { min-width: 0; }
.dsp-prose { font-family: var(--dsp-serif); font-size: clamp(1.12rem, 1.5vw, 1.28rem);
  line-height: 1.75; color: #26211a; }
.dsp-prose p { margin: 0 0 1.35em; max-width: 68ch; }
.dsp-prose ul { margin: 0 0 1.35em 1.1em; max-width: 66ch; }
.dsp-prose li { margin-bottom: 0.5em; }
.dsp-prose strong { color: var(--dsp-ink); }
.dsp-prose a { color: var(--dsp-gold-deep); text-underline-offset: 3px; }
.dsp-prose__intro p:first-of-type::first-letter { font-family: var(--dsp-display);
  font-weight: 800; font-size: 3.6em; line-height: 0.82; float: left; padding: 6px 12px 0 0;
  color: var(--dsp-gold-deep); }
.dsp-section { margin: 0 0 clamp(34px, 4vw, 54px); }
.dsp-section__no { font-family: var(--dsp-mono); font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.14em; color: var(--dsp-gold-deep); display: block; margin-bottom: 10px; }
.dsp-section h2 { font-family: var(--dsp-display); font-weight: 700;
  font-size: clamp(1.45rem, 2.6vw, 2rem); line-height: 1.12; letter-spacing: -0.02em;
  margin: 0 0 16px; color: var(--dsp-ink); }
.dsp-note { font-family: var(--dsp-mono); font-size: 0.8rem; line-height: 1.6;
  color: var(--dsp-ink-soft); border-top: 2px solid var(--dsp-gold);
  padding-top: 12px; margin: 26px 0; max-width: 30ch; }
.dsp-note::before { content: attr(data-note); display: block; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--dsp-gold-deep);
  font-size: 0.62rem; margin-bottom: 8px; }
@media (min-width: 1000px) {
  .dsp-note { grid-column: 1; align-self: start; position: sticky; top: 92px;
    margin: 6px 0 0; max-width: none; } }
.dsp-figure { margin: clamp(30px, 4vw, 50px) 0; }
.dsp-figure img { width: 100%; border-radius: var(--radius-md); display: block;
  background: var(--dsp-paper-deep); }
.dsp-figure figcaption { font-family: var(--dsp-mono); font-size: 0.72rem; color: var(--dsp-ink-mute);
  margin-top: 10px; display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
.dsp-figure figcaption a { color: var(--dsp-ink-mute); }
.dsp-pull { margin: clamp(36px, 5vw, 60px) auto; padding: 6px 0 6px 26px;
  border-left: 3px solid var(--dsp-gold); }
.dsp-pull p { font-family: var(--dsp-serif); font-style: italic;
  font-size: clamp(1.5rem, 3vw, 2.1rem); line-height: 1.3; color: var(--dsp-ink); margin: 0; max-width: 40ch; }

/* ── Post: field kit cross-sell ──────────────────────────────────── */
.dsp-kit { max-width: 760px; margin: clamp(44px, 6vw, 72px) auto; border-radius: var(--radius-lg);
  overflow: hidden; border: 1px solid var(--dsp-rule-strong); background: var(--dsp-card);
  box-shadow: var(--dsp-shadow); display: grid; grid-template-columns: 240px minmax(0, 1fr); }
.dsp-kit__media { position: relative; background: var(--dsp-paper-deep); display: flex;
  align-items: center; justify-content: center; padding: 20px; }
.dsp-kit__media img { max-width: 100%; max-height: 210px; object-fit: contain; mix-blend-mode: multiply; }
.dsp-kit__body { padding: clamp(22px, 3vw, 34px); }
.dsp-kit__label { font-family: var(--dsp-mono); font-size: 0.66rem; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--dsp-gold-deep);
  display: inline-flex; align-items: center; gap: 8px; }
.dsp-kit__label::before { content: '\\2726'; color: var(--dsp-gold); }
.dsp-kit h3 { font-family: var(--dsp-display); font-size: 1.3rem; line-height: 1.2;
  margin: 12px 0 6px; color: var(--dsp-ink); }
.dsp-kit__blurb { font-family: var(--dsp-serif); font-size: 1.02rem; line-height: 1.55;
  color: var(--dsp-ink-soft); margin: 0 0 16px; }
.dsp-kit__row { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.dsp-kit__price { font-family: var(--dsp-mono); font-weight: 700; font-size: 1.05rem; color: var(--dsp-ink); }
.dsp-kit__cta { display: inline-flex; align-items: center; gap: 8px; background: var(--dsp-ink);
  color: #fff; text-decoration: none; font-family: var(--dsp-mono); font-size: 0.78rem;
  font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 13px 20px;
  border-radius: var(--radius-sm); transition: background var(--duration-fast) var(--ease-out); }
.dsp-kit__cta:hover { background: var(--dsp-gold-deep); }
@media (max-width: 620px) { .dsp-kit { grid-template-columns: 1fr; }
  .dsp-kit__media { min-height: 180px; } }

/* ── Post: FAQ + related ─────────────────────────────────────────── */
.dsp-faq { max-width: 760px; margin: clamp(30px, 4vw, 50px) auto 0; }
.dsp-faq h2 { font-family: var(--dsp-display); font-size: clamp(1.4rem, 2.6vw, 1.9rem);
  margin: 0 0 18px; letter-spacing: -0.02em; }
.dsp-faq details { border-top: 1px solid var(--dsp-rule); padding: 18px 0; }
.dsp-faq details:last-child { border-bottom: 1px solid var(--dsp-rule); }
.dsp-faq summary { font-family: var(--dsp-display); font-weight: 600; font-size: 1.08rem;
  cursor: pointer; list-style: none; display: flex; justify-content: space-between; gap: 16px; }
.dsp-faq summary::-webkit-details-marker { display: none; }
.dsp-faq summary::after { content: '+'; font-family: var(--dsp-mono); color: var(--dsp-gold-deep); }
.dsp-faq details[open] summary::after { content: '\\2212'; }
.dsp-faq p { font-family: var(--dsp-serif); font-size: 1.05rem; line-height: 1.65;
  color: var(--dsp-ink-soft); margin: 14px 0 0; max-width: 64ch; }
.dsp-related { max-width: 1080px; margin: var(--space-2xl) auto 0; padding: 0 24px var(--space-2xl); }
.dsp-related__head { border-bottom: 2px solid var(--dsp-ink); padding-bottom: 14px; margin-bottom: 26px; }
.dsp-related__head h2 { font-family: var(--dsp-display); font-size: clamp(1.4rem, 2.6vw, 1.9rem);
  margin: 0; letter-spacing: -0.01em; }
.dsp-related__grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: clamp(18px, 2.6vw, 30px); }
.dsp-rcard { text-decoration: none; color: inherit; }
.dsp-rcard__media { aspect-ratio: 3 / 2; border-radius: var(--radius-md); overflow: hidden;
  background: var(--dsp-paper-deep); margin-bottom: 14px; }
.dsp-rcard__media img { width: 100%; height: 100%; object-fit: cover; transition: transform var(--duration-slow) var(--ease-out); }
.dsp-rcard:hover .dsp-rcard__media img { transform: scale(1.04); }
.dsp-rcard h3 { font-family: var(--dsp-display); font-weight: 700; font-size: 1.12rem;
  line-height: 1.22; margin: 0 0 8px; letter-spacing: -0.01em; }
.dsp-rcard:hover h3 { color: var(--dsp-gold-deep); }
.dsp-rcard p { font-family: var(--dsp-serif); font-size: 0.95rem; color: var(--dsp-ink-soft); margin: 0; }
@media (max-width: 760px) { .dsp-related__grid { grid-template-columns: 1fr; } }

@media (prefers-reduced-motion: reduce) {
  .dsp-lead__media img, .dsp-item__thumb img, .dsp-rcard__media img { transition: none !important; }
}
"""


def _clean_html(raw: str) -> str:
    """Strip script/iframe/style and inline event handlers from model HTML."""
    text = raw or ""
    text = re.sub(r"<\s*(script|iframe|style|object|embed)[^>]*>.*?<\s*/\s*\1\s*>", "", text,
                  flags=re.I | re.S)
    text = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", text, flags=re.I)
    text = re.sub(r"\son\w+\s*=\s*'[^']*'", "", text, flags=re.I)
    return text.strip()


def _read_time(post: dict) -> int:
    words = len(re.sub(r"<[^>]+>", " ", post.get("intro", "")).split())
    for s in post.get("sections", []):
        words += len(re.sub(r"<[^>]+>", " ", s.get("html", "")).split())
    return max(3, round(words / 225))


def _fmt_date(value: str) -> str:
    try:
        d = datetime.fromisoformat(str(value)).date()
    except Exception:
        try:
            d = date.fromisoformat(str(value))
        except Exception:
            return str(value)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _credit_html(img: dict) -> str:
    if not img:
        return ""
    who = html_mod.escape(img.get("photographer", "")) or "Pexels"
    url = img.get("pexels_url") or ""
    who_html = f'<a href="{html_mod.escape(url)}" target="_blank" rel="noopener">{who}</a>' if url else who
    return f"Photo: {who_html} / Pexels"


def _hero_src(img: dict, b: str, slug: str) -> str:
    if not img:
        return ""
    local = img.get("file") or img.get("local") or ""
    if local:
        return f"{b}/{local.lstrip('/')}"
    return img.get("src_medium") or img.get("src") or ""


def _img_or_placeholder(post: dict, b: str) -> str:
    src = _hero_src(post.get("hero") or {}, b, post.get("slug", ""))
    if src:
        return src
    return f"{b}/assets/hero-home.svg"


def _meta_line(post: dict) -> str:
    return (
        '<div class="dsp-meta">'
        f'<span>{html_mod.escape(post.get("persona", ""))}</span>'
        f'<span>{_fmt_date(post.get("published", ""))}</span>'
        f'<span>{_read_time(post)} min read</span>'
        '</div>'
    )


def _persona_chips(posts: list, b: str) -> str:
    try:
        from abvorn.content.blog import BLOG_PERSONAS
    except Exception:
        BLOG_PERSONAS = {}
    seen = []
    for p in posts:
        pid = p.get("persona_id")
        if pid and pid not in seen:
            seen.append(pid)
    chips = ['<button type="button" class="dsp-chip is-active" data-persona="all">All dispatches</button>']
    for pid in seen:
        name = (BLOG_PERSONAS.get(pid, {}) or {}).get("name") or pid.replace("-", " ").title()
        chips.append(
            f'<button type="button" class="dsp-chip" data-persona="{html_mod.escape(pid)}">'
            f'{html_mod.escape(name)}</button>'
        )
    return '<nav class="dsp-persona-rail" aria-label="Filter by reader">' + "".join(chips) + "</nav>"


def _page_head(title: str, description: str, canonical: str, og_type: str = "website",
               image: str = "") -> str:
    og_img = image or f"{_SITE_URL}/assets/logo.png?v=2"
    return f'''<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/png" href="{SITE_BASE}/assets/favicon-32x32.png">
<title>{html_mod.escape(title)}</title>
<meta name="description" content="{html_mod.escape(description)}">
<link rel="canonical" href="{html_mod.escape(canonical)}">
<meta property="og:title" content="{html_mod.escape(title)}">
<meta property="og:description" content="{html_mod.escape(description)}">
<meta property="og:url" content="{html_mod.escape(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:image" content="{html_mod.escape(og_img)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html_mod.escape(title)}">
<meta name="twitter:description" content="{html_mod.escape(description)}">
<meta name="twitter:image" content="{html_mod.escape(og_img)}">'''


def _issue_no(posts: list) -> str:
    return f"No. {max(1, len(posts)):03d}"


# ── Index page ────────────────────────────────────────────────────────────
def build_blog_index_page(posts_by_slug: dict, b: str = "") -> str:
    b = b or SITE_BASE
    posts = sorted(posts_by_slug.values(), key=lambda p: str(p.get("published", "")), reverse=True)
    lead = posts[0] if posts else None
    rest = posts[1:] if len(posts) > 1 else posts

    if lead:
        lead_media = _img_or_placeholder(lead, b)
        lead_html = f'''<section class="dsp-lead" data-persona="{html_mod.escape(lead.get("persona_id", ""))}">
    <a class="dsp-lead__media" href="{b}/blog/{html_mod.escape(lead.get("slug", ""))}/">
        <img src="{html_mod.escape(lead_media)}" alt="{html_mod.escape((lead.get("hero") or {}).get("alt", lead.get("title", "")))}" loading="eager">
    </a>
    <div class="dsp-lead__body">
        <span class="dsp-kicker">Lead dispatch · {html_mod.escape(lead.get("persona", ""))}</span>
        <h2 class="dsp-lead__title"><a href="{b}/blog/{html_mod.escape(lead.get("slug", ""))}/">{html_mod.escape(lead.get("title", ""))}</a></h2>
        <p class="dsp-lead__dek">{html_mod.escape(lead.get("dek", ""))}</p>
        {_meta_line(lead)}
    </div>
</section>'''
    else:
        lead_html = '<section class="dsp-lead"><p class="dsp-empty">The first dispatch is on its way.</p></section>'

    rows = []
    for i, p in enumerate(rest, start=1):
        thumb = _img_or_placeholder(p, b)
        rows.append(
            f'<li class="dsp-item" data-persona="{html_mod.escape(p.get("persona_id", ""))}">'
            f'<span class="dsp-item__no">{i:02d}</span>'
            f'<span class="dsp-item__thumb"><img src="{html_mod.escape(thumb)}" alt="" loading="lazy"></span>'
            f'<div class="dsp-item__body">'
            f'<span class="dsp-kicker">{html_mod.escape(p.get("persona", ""))}</span>'
            f'<h3 class="dsp-item__title"><a href="{b}/blog/{html_mod.escape(p.get("slug", ""))}/">'
            f'{html_mod.escape(p.get("title", ""))}</a></h3>'
            f'<p class="dsp-item__dek">{html_mod.escape(p.get("dek", ""))}</p>'
            f'</div>'
            f'<span class="dsp-item__go" aria-hidden="true">&rarr;</span></li>'
        )
    if not rows:
        rows.append('<li class="dsp-item dsp-item--empty"><p class="dsp-empty">More dispatches coming soon.</p></li>')

    header_html = build_site_header(b)
    footer_html = build_site_footer(b)
    form_url = _newsletter_form_url()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<!--
THESIS: The Abvorn Dispatch - a publication, not a storefront. Persona-led
utility writing that earns attention first and recommends nothing until the end.
OWN-WORLD: warm paper canvas (#faf7f1), brand gold (#c98a2c) rule work, Libre
Franklin display, Newsreader reading serif. Rejects the site's dark showroom
for the reading surface without leaving the brand.
STORY: a visitor recognises themselves in a persona, scans a periodical
contents list, and opens a dispatch.
FIRST VIEWPORT: paper masthead, the issue line, the big title, persona chips.
FINISH: builds to the lead photograph and the numbered contents.
-->
{_page_head("The Abvorn Dispatch - field notes for people who research before they spend",
            "Editorial guides on travel, focus, home and habits from Abvorn. Practical writing for people who read before they buy.",
            f"{_SITE_URL}/blog/")}
{BLOG_FONT_LINK}
<style>
{DESIGN_SYSTEM_CSS}
{SITE_CHROME_CSS}
{MEGA_MENU_CSS}
{BLOG_CSS}
</style>
<style>{CONSENT_CSS}</style>
{ANALYTICS_HTML}
</head>
<body class="dsp">
<a class="skip-link" href="#main">Skip to content</a>
{header_html}
<main id="main">
<section class="dsp-masthead">
    <div class="container">
        <span class="dsp-eyebrow">The Abvorn Dispatch · {_issue_no(posts)}</span>
        <h1 class="dsp-masthead__title">Field notes for<br>people who read<br>before they buy.</h1>
        <p class="dsp-masthead__lede">Practical writing on travel, focus, home and habits - the parts of a good decision that happen before the shopping starts.</p>
        {_persona_chips(posts, b)}
    </div>
</section>
<div class="container">{lead_html}</div>
<section class="container dsp-contents" id="contents">
    <div class="dsp-contents__head">
        <h2>Contents</h2>
        <p>{len(posts)} dispatch{'es' if len(posts) != 1 else ''}</p>
    </div>
    <ol class="dsp-list">{"".join(rows)}</ol>
</section>
<div class="container">
    <section class="dsp-news">
        <div>
            <span class="dsp-eyebrow">The weekly dispatch</span>
            <h2>One useful idea, every Friday.</h2>
            <p>No product pitches, no clickbait - a short field note you can use that weekend. Unsubscribe in one tap.</p>
        </div>
        <form action="{html_mod.escape(form_url)}" method="post" target="_blank">
            <input type="email" name="email" placeholder="you@example.com" required aria-label="Email address">
            <button type="submit">Subscribe</button>
        </form>
    </section>
</div>
</main>
{footer_html}
<script>
(function(){{
  var chips = document.querySelectorAll('.dsp-chip');
  var items = document.querySelectorAll('[data-persona]');
  chips.forEach(function(c){{
    c.addEventListener('click', function(){{
      var want = c.getAttribute('data-persona');
      chips.forEach(function(x){{ x.classList.toggle('is-active', x === c); }});
      items.forEach(function(el){{
        var show = want === 'all' || el.getAttribute('data-persona') === want;
        el.style.display = show ? '' : 'none';
      }});
    }});
  }});
}})();
</script>
</body>
</html>'''


# ── Post page ─────────────────────────────────────────────────────────────
def _figure(img: dict, b: str, caption: str = "") -> str:
    src = _hero_src(img, b, "")
    if not src:
        return ""
    alt = html_mod.escape(img.get("alt", ""))
    cap = html_mod.escape(caption) if caption else ""
    credit = _credit_html(img)
    return f'''<figure class="dsp-figure">
    <img src="{html_mod.escape(src)}" alt="{alt}" loading="lazy">
    <figcaption><span>{cap}</span><span>{credit}</span></figcaption>
</figure>'''


def _field_kit(post: dict) -> str:
    niche = post.get("cross_sell_niche", "")
    if not niche:
        return ""
    prod = post.get("cross_sell_product") or {}
    name = prod.get("name", "") if isinstance(prod, dict) else ""
    price = prod.get("price", "") if isinstance(prod, dict) else ""
    image = prod.get("image", "") if isinstance(prod, dict) else ""
    url = prod.get("url", "") if isinstance(prod, dict) else ""
    from abvorn.core.verdict import clean_product_name

    if name:
        name = clean_product_name(name)
    label = post.get("cross_sell_name", niche.replace("-", " ").title())
    blurb = post.get("cross_sell_blurb", "")
    if not name:
        return ""
    media = (
        f'<div class="dsp-kit__media"><img src="{html_mod.escape(image)}" alt="{html_mod.escape(name)}" loading="lazy"></div>'
        if image else ""
    )
    href = affiliate_url(url, "") or url or "#"
    price_html = f'<span class="dsp-kit__price">{html_mod.escape(str(price))}</span>' if price else ""
    return f'''<aside class="dsp-kit" aria-label="Field kit recommendation">
    {media}
    <div class="dsp-kit__body">
        <span class="dsp-kit__label">Field kit · if you want one</span>
        <h3>{html_mod.escape(name)}</h3>
        <p class="dsp-kit__blurb">{html_mod.escape(blurb)}</p>
        <div class="dsp-kit__row">
            {price_html}
            <a class="dsp-kit__cta" href="{html_mod.escape(href)}" target="_blank" rel="sponsored nofollow noopener">Check the {html_mod.escape(label)} &rarr;</a>
        </div>
    </div>
</aside>'''


def _faq_html(post: dict) -> str:
    faqs = post.get("faqs") or []
    if not faqs:
        return ""
    items = "".join(
        f'<details><summary>{html_mod.escape(f.get("question", ""))}</summary>'
        f'<p>{html_mod.escape(f.get("answer", ""))}</p></details>'
        for f in faqs if f.get("question")
    )
    return f'<section class="dsp-faq"><h2>Questions people ask</h2>{items}</section>'


def _related_html(post: dict, posts_by_slug: dict, b: str) -> str:
    others = [p for s, p in posts_by_slug.items() if s != post.get("slug")]
    others.sort(key=lambda p: (p.get("persona_id") != post.get("persona_id"),
                               str(p.get("published", ""))), reverse=False)
    picks = others[:3]
    if not picks:
        return ""
    cards = "".join(
        f'<a class="dsp-rcard" href="{b}/blog/{html_mod.escape(p.get("slug", ""))}/">'
        f'<div class="dsp-rcard__media"><img src="{html_mod.escape(_img_or_placeholder(p, b))}" alt="" loading="lazy"></div>'
        f'<span class="dsp-kicker">{html_mod.escape(p.get("persona", ""))}</span>'
        f'<h3>{html_mod.escape(p.get("title", ""))}</h3>'
        f'<p>{html_mod.escape(p.get("dek", ""))}</p></a>'
        for p in picks
    )
    return f'''<section class="dsp-related">
    <div class="dsp-related__head"><h2>Keep reading</h2></div>
    <div class="dsp-related__grid">{cards}</div>
</section>'''


def _jsonld(post: dict, b: str) -> str:
    hero = _img_or_placeholder(post, b)
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.get("title", ""),
        "description": post.get("meta_description") or post.get("dek", ""),
        "image": [hero],
        "datePublished": post.get("published", ""),
        "dateModified": post.get("updated") or post.get("published", ""),
        "author": {"@type": "Organization", "name": "Abvorn Dispatch"},
        "publisher": {"@type": "Organization", "name": "Abvorn",
                      "logo": {"@type": "ImageObject", "url": f"{_SITE_URL}/logo.png"}},
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"{_SITE_URL}/blog/{post.get('slug', '')}/"},
        "articleSection": post.get("persona", ""),
        "keywords": ", ".join(post.get("tags", [])),
    }
    blocks = [article]
    faqs = post.get("faqs") or []
    if faqs:
        blocks.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f.get("question", ""),
                 "acceptedAnswer": {"@type": "Answer", "text": f.get("answer", "")}}
                for f in faqs if f.get("question")
            ],
        })
    blocks.append({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{_SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Dispatch", "item": f"{_SITE_URL}/blog/"},
        ],
    })
    packed = "\n".join(json.dumps(bk, ensure_ascii=False) for bk in blocks)
    return f'<script type="application/ld+json">\n{packed}\n</script>'


def build_blog_post_page(post: dict, posts_by_slug: dict, b: str = "") -> str:
    b = b or SITE_BASE
    slug = post.get("slug", "")
    hero = post.get("hero") or {}
    hero_src = _hero_src(hero, b, slug)
    hero_alt = html_mod.escape(hero.get("alt", post.get("title", "")))
    credit = _credit_html(hero)

    images = list(post.get("images") or [])
    # Place inline images after evenly spaced sections so the body is never
    # text-only (the brief: minimum two sourced photographs per post).
    sections = post.get("sections", [])
    img_slots: dict[int, list] = {}
    if images and sections:
        step = max(1, len(sections) // (len(images) + 1))
        idx = step
        for img in images:
            while idx in img_slots and idx < len(sections):
                idx += 1
            img_slots.setdefault(min(idx, len(sections) - 1), []).append(img)
            idx += step

    rows = []
    intro_html = _clean_html(post.get("intro", ""))
    rows.append(
        f'<div class="dsp-row dsp-row--full"><div class="dsp-main dsp-prose dsp-prose__intro">'
        f'{intro_html}</div></div>'
    )

    for i, sec in enumerate(sections):
        note = _clean_html(sec.get("note", ""))
        note_html = (
            f'<aside class="dsp-note" data-note="Field note {i + 1:02d}">{html_mod.escape(note)}</aside>'
            if note else ""
        )
        rows.append(
            f'<div class="dsp-row dsp-section" id="s{i + 1}">'
            f'{note_html}'
            f'<div class="dsp-main">'
            f'<span class="dsp-section__no">{i + 1:02d} / {len(sections):02d}</span>'
            f'<h2>{html_mod.escape(sec.get("heading", ""))}</h2>'
            f'<div class="dsp-prose">{_clean_html(sec.get("html", ""))}</div>'
            f'</div></div>'
        )
        for img in img_slots.get(i, []):
            rows.append(
                f'<div class="dsp-row dsp-row--full">{_figure(img, b, img.get("caption", ""))}</div>'
            )

    pull = _clean_html(post.get("pull_quote", ""))
    pull_html = (
        f'<div class="dsp-row dsp-row--full"><blockquote class="dsp-pull">'
        f'<p>{html_mod.escape(pull)}</p></blockquote></div>' if pull else ""
    )

    header_html = build_site_header(b)
    footer_html = build_site_footer(b)
    kit_html = _field_kit(post)
    faq_html = _faq_html(post)
    related_html = _related_html(post, posts_by_slug, b)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<!--
THESIS: a single Dispatch story - a field guide with an honest margin. It
refuses the blog default of an SEO wall with a product grid stapled on.
OWN-WORLD: paper + ink + gold, Newsreader reading serif, field notes pinned in
the left margin, one field-kit recommendation at the end.
STORY: reader arrives from search with a real problem, reads a calm guide,
leaves with a plan - and optionally one honest product.
FIRST VIEWPORT: full-bleed photo, title card, then the drop-capped opening.
FINISH: builds through numbered sections to the field kit, FAQ and related reads.
-->
{_page_head(post.get("title", "Dispatch"), post.get("meta_description") or post.get("dek", ""),
            f"{_SITE_URL}/blog/{slug}/", og_type="article", image=hero_src)}
{BLOG_FONT_LINK}
<style>
{DESIGN_SYSTEM_CSS}
{SITE_CHROME_CSS}
{MEGA_MENU_CSS}
{BLOG_CSS}
</style>
<style>{CONSENT_CSS}</style>
{ANALYTICS_HTML}
{_jsonld(post, b)}
</head>
<body class="dsp">
<a class="skip-link" href="#main">Skip to content</a>
<div class="dsp-progress" id="dsp-progress" aria-hidden="true"></div>
{header_html}
<main id="main">
<article>
<div class="dsp-hero">
    <img class="dsp-hero__img" src="{html_mod.escape(hero_src or f'{b}/assets/hero-home.svg')}" alt="{hero_alt}" loading="eager">
    <span class="dsp-hero__credit">{credit}</span>
</div>
<header class="dsp-head">
    <div class="dsp-head__card">
        <span class="dsp-kicker">Dispatch · {html_mod.escape(post.get("persona", ""))}</span>
        <h1 class="dsp-head__title">{html_mod.escape(post.get("title", ""))}</h1>
        <p class="dsp-head__dek">{html_mod.escape(post.get("dek", ""))}</p>
        {_meta_line(post)}
    </div>
</header>
<div class="dsp-body">
    {"".join(rows)}
    {pull_html}
</div>
<div class="container">{kit_html}</div>
<div class="container">{faq_html}</div>
</article>
{related_html}
</main>
{footer_html}
<script>
(function(){{
  var bar = document.getElementById('dsp-progress');
  if(!bar) return;
  function onScroll(){{
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    var pct = max > 0 ? (h.scrollTop || document.body.scrollTop) / max * 100 : 0;
    bar.style.width = pct + '%';
  }}
  window.addEventListener('scroll', onScroll, {{passive:true}});
  onScroll();
}})();
</script>
</body>
</html>'''


def _newsletter_form_url() -> str:
    """Reuse the site's listmonk form when configured, else the on-site form."""
    import os

    return os.environ.get("ABVORN_BLOG_FORM_URL") or f"{SITE_BASE}/#newsletter"
