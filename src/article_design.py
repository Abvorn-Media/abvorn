"""article_design.py — shared article-page design system for Abvorn reviews.

Single source of truth for the studio product photography treatment, the
"Our Choice" hero pick, the content sanitizer, the guaranteed FAQ section,
and the "?" explainer tooltips. Both run_cycle.py and src/deployment.py
import from here so the two builders never drift.
"""
import re
import html as html_mod

from abvorn.core.verdict import clean_product_name

# ── Universal studio product photography ───────────────────────────────
# One standardized treatment for every product photo on the site: a bright
# studio sweep with a soft lighting filter, consistent square canvas, and a
# uniform border radius. Used in the hero, product cards, review cards, and
# inline article photos so the whole catalogue looks like it was shot in the
# same studio.
PROD_SHOT_CSS = """
.product-shot{position:relative;display:flex;align-items:center;justify-content:center;
  background:#ffffff;
  border:1px solid var(--clr-light-gray);border-radius:var(--radius-lg);
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.6),0 12px 32px rgba(0,0,0,.08);
  overflow:hidden;padding:var(--space-lg);margin:0}
.product-shot__img{width:100%;height:100%;object-fit:contain;display:block;
  filter:saturate(1.05) contrast(1.02) brightness(1.01)}
.product-shot__badge{position:absolute;top:12px;left:12px;z-index:2;
  background:var(--clr-accent);color:#1a1200;font-size:.7rem;font-weight:800;
  text-transform:uppercase;letter-spacing:.06em;padding:4px 12px;border-radius:100px;
  box-shadow:var(--shadow-sm)}
.product-shot--hero{aspect-ratio:1/1;width:100%;max-width:300px;margin:0 auto;
  padding:var(--space-lg);box-shadow:none}
.product-shot--hero .product-shot__img{filter:saturate(1.06) contrast(1.03) brightness(1.02)}
.product-shot--hero .product-shot__badge{box-shadow:none}
.product-shot--card{aspect-ratio:1/1;width:100%;padding:var(--space-md)}
.product-shot--sm{width:100%;height:100%;padding:var(--space-sm);border-radius:var(--radius-sm)}
.product-shot--body{max-width:420px;margin:var(--space-md) auto;padding:var(--space-lg)}
.niche-card__image-wrapper .product-shot{width:100%;height:100%;aspect-ratio:auto;
  border:0;border-radius:0;box-shadow:none;padding:var(--space-sm);margin:0}
@media (max-width:600px){.product-shot--body{max-width:100%}}
"""

# ── "?" explainer tooltips ──────────────────────────────────────────────
# Pure-CSS tooltips so the methodology behind every tool (Verdict Engine,
# scoring, RPS) is one hover away without loading a library.
INFO_DOT_CSS = """
.info-dot{position:relative;display:inline-flex;align-items:center;justify-content:center;
  width:18px;height:18px;border-radius:50%;background:var(--clr-light-gray,#e8e8e8);
  color:var(--clr-mid-gray,#666);font-size:.68rem;font-weight:800;line-height:1;
  cursor:help;vertical-align:middle;margin-left:6px;flex-shrink:0;border:0;padding:0;
  font-family:var(--font-body)}
.info-dot:hover,.info-dot:focus{background:var(--clr-accent);color:#1a1200}
.info-dot__tip{position:absolute;bottom:calc(100% + 8px);left:50%;transform:translateX(-50%) translateY(4px);
  width:270px;padding:12px 14px;background:#0a0a0a;color:#fff;font-size:.76rem;line-height:1.55;
  font-weight:400;border-radius:var(--radius-sm);box-shadow:var(--shadow-lg);text-align:left;
  opacity:0;visibility:hidden;transition:all var(--duration-fast) var(--ease-out);
  z-index:60;pointer-events:none}
.info-dot:hover .info-dot__tip,.info-dot:focus .info-dot__tip{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0)}
.info-dot__tip::after{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);
  border:6px solid transparent;border-top-color:#0a0a0a}
@media (max-width:640px){.info-dot__tip{width:210px;left:auto;right:-48px;transform:translateY(4px)}
  .info-dot:hover .info-dot__tip,.info-dot:focus .info-dot__tip{transform:translateY(0)}
  .info-dot__tip::after{left:auto;right:40px}}
"""

# ── Guaranteed FAQ section ──────────────────────────────────────────────
FAQ_CSS = """
.faq-section{margin:var(--space-xl) 0;padding:var(--space-lg);background:var(--clr-white);
  border:1px solid var(--clr-light-gray);border-radius:var(--radius-lg);box-shadow:var(--shadow-sm)}
.faq-section .section-title{margin-bottom:var(--space-lg)}
.faq-item{border:1px solid var(--clr-light-gray);background:var(--clr-white);
  border-radius:var(--radius-sm);margin-bottom:var(--space-sm);overflow:hidden}
.faq-item summary{cursor:pointer;padding:14px 18px;font-weight:700;font-size:var(--text-base);
  color:var(--clr-black);list-style:none;display:flex;align-items:center;gap:10px;
  font-family:var(--font-body)}
.faq-item summary::-webkit-details-marker{display:none}
.faq-item summary::before{content:'+';font-size:1.1rem;font-weight:800;color:var(--clr-accent);
  transition:transform var(--duration-fast) var(--ease-out);flex-shrink:0}
.faq-item[open] summary::before{transform:rotate(45deg)}
.faq-item .faq-answer{padding:0 18px 16px 40px;font-size:var(--text-sm);color:var(--clr-mid-gray);line-height:1.7}
.faq-item .faq-answer p{margin:0 0 8px;max-width:70ch}
.faq-item .faq-answer p:last-child{margin:0}
@media (max-width:600px){.faq-section{padding:var(--space-md)}}
"""

# ── Our Choice hero pick card ───────────────────────────────────────────
HERO_PICK_CSS = """
.hero-pick{display:flex;flex-direction:column;gap:var(--space-md);align-items:stretch}
.hero-pick__info{text-align:center}
.hero-pick__name{font-size:var(--text-xl);color:var(--clr-black);margin-bottom:6px}
.hero-pick__meta{display:flex;justify-content:center;gap:10px;flex-wrap:wrap;
  font-size:var(--text-sm);margin-bottom:var(--space-md)}
.hero-pick__score{display:inline-flex;align-items:center;gap:6px;background:var(--clr-accent);
  color:#1a1200;font-weight:800;padding:3px 12px;border-radius:100px}
.hero-pick__price{display:inline-flex;align-items:center;color:var(--clr-off-black);font-weight:600}
.hero-pick__link{color:var(--clr-mid-gray);font-size:.8rem;text-decoration:none;display:inline-block;margin-top:6px}
.hero-pick__link:hover{color:var(--clr-black);text-decoration:underline}
"""

# ── RPS (Regret Probability Score) widget ──────────────────────────────
# Rendered client-side by RPS_JS inside the article body. The legacy CSS for
# this widget lived in CSS_SHARED, which article pages never included, so the
# widget shipped unstyled. This copy is mapped to the real design tokens that
# ARE present on article pages (--clr-*, --radius-*, --space-*).
RPS_CSS = """
.rps-container{border:1px solid var(--clr-light-gray);border-radius:var(--radius-lg);
  padding:var(--space-lg) var(--space-xl);margin:var(--space-lg) 0;
  background:var(--clr-off-white);box-shadow:var(--shadow-sm)}
.rps-badge{display:inline-flex;align-items:center;gap:6px;font-size:.7rem;font-weight:700;
  color:var(--clr-mid-gray);text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px}
.rps-badge::before{content:'\\01F52E';font-size:.8rem}
.rps-header{border-left:4px solid var(--clr-accent);padding-left:16px;margin-bottom:16px}
.rps-score{display:flex;align-items:baseline;gap:8px;margin-bottom:4px}
.rps-number{font-size:2.2rem;font-weight:700;font-family:var(--font-display);line-height:1;letter-spacing:-.03em}
.rps-product-name{font-size:.9rem;color:var(--clr-mid-gray);font-weight:500}
.rps-section-title{font-size:.85rem;font-weight:700;color:var(--clr-off-black);margin-bottom:8px;
  text-transform:uppercase;letter-spacing:.04em}
.rps-reasons{margin-bottom:16px}
.rps-reason{padding:10px 14px;border-radius:var(--radius-sm);margin-bottom:8px;font-size:.88rem;
  line-height:1.5;border-left:3px solid}
.rps-reason.rps-mismatch{background:#fef2f2;border-color:#c0392b;color:#7f1d1d}
.rps-reason.rps-notice{background:#fffbeb;border-color:#d4a03e;color:#78350f}
.rps-tip{font-size:.85rem;color:var(--clr-mid-gray);padding:12px;background:var(--clr-white);
  border-radius:var(--radius-sm);margin-bottom:16px;line-height:1.4}
.rps-alt-title{font-size:.85rem;font-weight:700;color:var(--clr-off-black);margin-bottom:10px;
  text-transform:uppercase;letter-spacing:.04em}
.rps-alt-item{display:flex;align-items:center;gap:12px;padding:12px 14px;
  border:1px solid var(--clr-light-gray);border-radius:var(--radius-sm);margin-bottom:8px;
  text-decoration:none;transition:all .15s;background:var(--clr-white)}
.rps-alt-item:hover{text-decoration:none;border-color:var(--clr-primary);box-shadow:var(--shadow-sm)}
.rps-alt-name{flex:1;font-weight:600;color:var(--clr-off-black);font-size:.9rem}
.rps-alt-prob{font-size:.78rem;font-weight:600;white-space:nowrap}
.rps-alt-price{font-size:.8rem;color:var(--clr-mid-gray)}
.rps-footer{font-size:.78rem;color:var(--clr-mid-gray);display:flex;align-items:center;gap:12px;
  margin-top:12px;padding-top:12px;border-top:1px solid var(--clr-light-gray)}
.rps-reset{background:none;border:1px solid var(--clr-light-gray);border-radius:100px;padding:4px 12px;
  font-size:.75rem;color:var(--clr-mid-gray);cursor:pointer;font-family:inherit;transition:all .15s}
.rps-reset:hover{border-color:var(--clr-primary);color:var(--clr-primary)}
"""

ARTICLE_DESIGN_CSS = PROD_SHOT_CSS + INFO_DOT_CSS + FAQ_CSS + HERO_PICK_CSS + RPS_CSS


def upgrade_product_image(url):
    """Upgrade a low-res Amazon thumbnail to the hi-res _AC_SL1500_ image.

    e.g. ...81wWGYF+tUL._AC_UY654_QL65_.jpg  ->  ...81wWGYF+tUL._AC_SL1500_.jpg
    """
    if not url:
        return url
    return re.sub(
        r"_AC_(?:SX|SY|UY|UX|SL)\d+(?:_QL\d+)?_",
        "_AC_SL1500_",
        url,
    )


def product_shot_html(url, name, size="card", badge=None, eager=False):
    """Universal studio product photograph block.

    Applies the site-wide lighting treatment and standardized square canvas
    to any product photo. Used everywhere products appear.
    """
    url = upgrade_product_image(url)
    img = (
        f'<img class="product-shot__img" src="{html_mod.escape(url)}" '
        f'alt="{html_mod.escape(name)}" loading="{"eager" if eager else "lazy"}">'
    )
    badge_html = f'<span class="product-shot__badge">{html_mod.escape(badge)}</span>' if badge else ""
    return f'<figure class="product-shot product-shot--{size}">{badge_html}{img}</figure>'


def info_dot(text):
    """Small '?' trigger with a pure-CSS tooltip explaining a tool."""
    return (
        '<span class="info-dot" tabindex="0" role="button" '
        f'aria-label="Why does this matter?"><span class="info-dot__mark">?</span>'
        f'<span class="info-dot__tip">{text}</span></span>'
    )


# ── Price floor (per-niche) ─────────────────────────────────────────────
PRICE_FLOORS = {
    "wireless-headphones": "50",
    "gaming-mice": "30",
    "4k-monitors": "300",
    "laptops": "500",
    "streaming-devices": "30",
    "mechanical-keyboards": "60",
    "wireless-earbuds": "40",
    "fitness-trackers": "50",
    "webcams": "40",
    "smart-home": "30",
}


def price_floor_for(niche_slug):
    return PRICE_FLOORS.get(niche_slug, "50")


# ── Content sanitizer ───────────────────────────────────────────────────
_CHART_NOTE_RE = re.compile(
    r"(?is)<p[^>]*class=[\"']chart-note[\"'][^>]*>.*?</p>"
)
_CHART_SECTION_RE = re.compile(
    r"(?is)<div[^>]*class=[\"']chart-section[\"'][^>]*>.*?</div>\s*"
)
_EMBEDDED_BODY_RE = re.compile(r"(?is)<body[^>]*>(.*?)</body>")
_EMBEDDED_DOC_RE = re.compile(r"(?is)<!DOCTYPE html>.*?</head>\s*(.*?)\s*(?:</body>\s*)?</html>")
_LEADING_INTRO_RE = re.compile(r"(?is)^\s*<h2>\s*Introduction\s*</h2>\s*")


def sanitize_article_html(html, strip_leading_intro=True):
    """Clean dirty AI-generated article HTML.

    Removes: embedded full-document wrappers, duplicated chart-note /
    chart-section fragments left over from earlier templates, stray U+FFFD
    replacement characters, and a duplicated "<h2>Introduction</h2>" heading
    (the template already provides the opening hook). Closes an unclosed
    trailing paragraph.
    """
    if not html:
        return ""
    text = html

    # Extract body content if a full <!DOCTYPE html> wrapper got embedded.
    m = _EMBEDDED_BODY_RE.search(text)
    if m:
        text = m.group(1)
    else:
        m = _EMBEDDED_DOC_RE.search(text)
        if m:
            text = m.group(1)

    # Drop duplicated chart fragments — the template owns its own.
    text = _CHART_SECTION_RE.sub("", text)
    text = _CHART_NOTE_RE.sub("", text)

    # Remove stray replacement characters / broken entities.
    text = re.sub(r"\ufffd", "", text)
    text = text.replace("&nbsp", " ")

    # Drop a duplicated Introduction heading when the intro hook exists.
    if strip_leading_intro:
        text = _LEADING_INTRO_RE.sub("", text)

    # Close unclosed paragraphs so the block stays valid. If the last opening
    # <p> has no matching close (a truncated AI draft), append the missing
    # close tags. Paragraphs never nest, so the open/close difference is the
    # number of unterminated paragraphs.
    opens = list(re.finditer(r"<p(?:\s[^>]*)?>", text))
    if opens:
        closes = len(re.findall(r"</p>", text))
        if len(opens) > closes:
            text = text.rstrip() + "</p>" * (len(opens) - closes)

    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def inject_product_photos(article_html, products):
    """Insert a studio product photo after each product's heading.

    Adds a standardized photo block right after the <h3> (or <h2>) heading
    that names a product, if the article section does not already include
    that product's image. This guarantees per-product photography even when
    the AI writer omits images.
    """
    if not products:
        return article_html
    result = article_html
    for prod in products:
        name = clean_product_name(prod.get("name", ""))
        image = upgrade_product_image(prod.get("image", ""))
        if not name or not image:
            continue
        if html_mod.escape(image) in result or image in result:
            continue
        # Match a heading that contains the product name (with optional
        # HTML-entity escaping inside the text).
        esc_name = re.escape(name)
        esc_name_escaped = re.escape(html_mod.escape(name))
        pattern = re.compile(
            r"(<h[23][^>]*>)(.*?" + esc_name + r".*?)(</h[23]>)",
            re.I,
        )
        pattern_esc = re.compile(
            r"(<h[23][^>]*>)(.*?" + esc_name_escaped + r".*?)(</h[23]>)",
            re.I,
        )

        def _replace(m):
            return m.group(0) + "\n" + product_shot_html(image, name, size="body")

        result, n = pattern.subn(_replace, result, count=1)
        if n == 0:
            result, n = pattern_esc.subn(_replace, result, count=1)
    return result


# ── Guaranteed FAQ ──────────────────────────────────────────────────────
def build_faq(niche_slug, niche_name, products, product_name, price_floor,
              verdict_summary=None, top_score=None):
    """Build a guaranteed FAQ section from product + rubric data.

    Returns (faq_html, questions) where questions is a list of (q, a) tuples
    suitable for faq_schema() JSON-LD.
    """
    from abvorn.core.verdict import CATEGORY_WEIGHTS, FALLBACK_WEIGHTS
    weights = CATEGORY_WEIGHTS.get(niche_slug, FALLBACK_WEIGHTS)
    top = sorted(weights.items(), key=lambda kv: -kv[1]["weight"])[:3]
    criteria = ", ".join(cfg["label"] for _, cfg in top)
    best = products[0] if products else {}
    best_name = clean_product_name(best.get("name", product_name))
    best_price = best.get("price", price_floor)
    score = top_score or best.get("verdict_score", "8+")
    niche_lower = (niche_name or niche_slug).lower()

    questions = [
        (
            f"What is the best {niche_lower}?",
            f"{best_name} is our current top pick for {niche_name or niche_lower}. "
            f"It earned an Abvorn Verdict score of {score}/10 for {criteria.lower()}, "
            f"and at {best_price} it offers the strongest balance of "
            f"{criteria.lower()} for the money.",
        ),
        (
            f"Is {best_name} worth it?",
            f"Based on our testing, yes for most people. {best_name} scored "
            f"{score}/10 on our rubric, which weighs {criteria.lower()} in "
            f"proportion to what real buyers care about. "
            f"{verdict_summary or 'It is the best-rounded option in this category today.'}",
        ),
        (
            f"How much should I spend on {niche_lower}?",
            f"You can get a genuinely good {niche_lower} for around "
            f"${price_floor}. Spending more buys premium materials and extra "
            f"features, but our top pick delivers the best combination of "
            f"performance and value at its current price.",
        ),
        (
            f"What should I look for when buying {niche_lower}?",
            f"We score every product on {criteria.lower()}. Start by deciding "
            f"which of those matters most to you, then compare products on "
            f"that axis first — the Abvorn Verdict breakdown below each review "
            f"shows exactly how every model scores on each one.",
        ),
        (
            "How does Abvorn test products?",
            "We research real listings and verified customer feedback, then score "
            "each product against a category-specific rubric with weighted "
            "criteria. Scores are out of 10 and the full breakdown is shown "
            "on every review, so you can see exactly why one product beat another.",
        ),
    ]

    items = "".join(
        f'<details class="faq-item" itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">'
        f'<summary itemprop="name">{html_mod.escape(q)}</summary>'
        f'<div class="faq-answer" itemprop="acceptedAnswer" itemscope itemtype="https://schema.org/Answer">'
        f'<p itemprop="text">{html_mod.escape(a)}</p></div></details>'
        for q, a in questions
    )
    faq_html = (
        f'<section class="faq-section" id="faq">'
        f'<span class="section-eyebrow">Answers</span>'
        f'<h3 class="section-title">Frequently Asked Questions</h3>{items}</section>'
    )
    return faq_html, questions


def hero_pick_html(product, overall, label, affiliate_url, base="", niche_slug=""):
    """The 'Our Choice' hero pick block shown in the article hero."""
    if not product:
        return ""
    name = clean_product_name(product.get("name", "Our Choice"))
    price = product.get("price", "Check price")
    image = product.get("image", "")
    if image:
        shot = product_shot_html(image, name, size="hero", badge="Our Choice", eager=True)
    else:
        shot = (
            '<div class="product-shot product-shot--hero">'
            '<span class="product-shot__badge">Our Choice</span>'
            '<div style="color:var(--clr-mid-gray);font-size:.8rem;text-align:center;padding:20px">'
            f'{html_mod.escape(name)}</div></div>'
        )
    return f"""
    <div class="hero-pick">
        {shot}
        <div class="hero-pick__info">
            <h2 class="hero-pick__name">{html_mod.escape(name)}</h2>
            <div class="hero-pick__meta">
                <span class="hero-pick__score">Abvorn {overall}/10 &middot; {html_mod.escape(label or "Score")}</span>
                <span class="hero-pick__price">{html_mod.escape(str(price))}</span>
            </div>
            <a class="buy-btn" href="{affiliate_url}" target="_blank" rel="sponsored">Check Price on Amazon &rarr;</a>
        </div>
    </div>"""


def render_article_body(disclosure, intro, verdict_html, chart_html, article_html,
                        matrix_html, faq_html, reactions, share, related_html,
                        product_cards, further_reading, cta=""):
    """Assemble the strategic article-body flow in the order readers consume.

    Hook (intro) first, then the verdict, then the at-a-glance comparison,
    then the evidence (article body, chart), then the buyable lineup, then
    FAQ, then the lead-capture CTA, then engagement + related content.
    """
    return f"""{disclosure}
{intro}
{verdict_html}
{matrix_html}
{article_html}
{chart_html}
{product_cards}
{faq_html}
{cta}
{reactions}
{share}
{related_html}
{further_reading}"""
