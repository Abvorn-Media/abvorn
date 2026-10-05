"""Regression tests: every product card must carry a few complete sentences.

Four separate defects shipped malformed card snippets, all reproduced against
the real published tree before the fix:

1. ``_overlay_review`` sliced the article intro with a bare ``[:160]``. The intro
   is article *markup*, so the card rendered literal ``<p>`` text and stopped
   mid-sentence ("... and it's easier what is the <p>?").
2. ``review_snippet`` fell back to the first acceptable paragraph inside
   ``<article>`` -- but the newsletter ``.cta-banner`` lives inside that element
   too, so 57 reviews shipped "straight to your inbox. No spam, unsubscribe
   anytime." as their card copy.
3. ``_clean_snippet`` cut at a *word* boundary at 180 characters, which is not a
   sentence boundary: 506 of 655 published reviews ended mid-thought.
4. When nothing passed the filters the snippet was empty and the card rendered
   with no copy at all.

The fix routes every producer through one cleaner that strips markup, drops CTA
containers, and assembles text from whole sentences only.
"""
import re

from src.deployment import (
    _CARD_SNIPPET_CHARS,
    _clean_snippet,
    _complete_sentences,
    _overlay_review,
    _split_sentences,
    page_has_products,
    review_card,
    review_snippet,
)

TERMINAL = re.compile(r'[.!?…]["\')\u201d\u2019\]]?$')
MARKUP = re.compile(r"<[^>]+>|&lt;|&gt;|&nbsp;")


def _sentences(text):
    return len(_split_sentences(text.rstrip("\u2026")))


def _article(inner, extra=""):
    return (
        "<html><body><article>"
        f"{inner}"
        f"{extra}"
        "</article></body></html>"
    )


# --- defect 2: the newsletter CTA lives inside <article> ---------------------

def test_review_snippet_never_opens_mid_thought():
    """A real published regression, not a synthetic edge case.

    ``/reviews/streaming-devices/best-streaming-devices-2026-roku-stick-...``
    has an introduction that starts lowercase, because the article's first
    paragraph is a continuation of the H2 above it. ``review_snippet`` used to
    run its own sentence accumulator that never applied the leading-fragment
    skip, so the card opened "every major brand packs 4K, HDR, ...". Worse, once
    the skip was honoured the card rendered with no copy at all, because
    ``review_card`` emits the snippet element only when non-empty.
    """
    html = _article(
        "<p>every major brand packs 4K, HDR, and voice search into a stick the "
        "size of a thumb drive, and the spec sheets start to blur together.</p>"
        "<p>The Roku Ultra wins on search speed and no price rises. It ships "
        "with the Wi-Fi 6 radio that matters for 4K streaming.</p>"
    )
    snippet = review_snippet(html)
    assert snippet, "must still produce copy - an empty card is defect #4"
    assert not snippet[:1].islower(), snippet
    assert snippet.startswith("The Roku"), snippet
    assert TERMINAL.search(snippet)


def test_review_snippet_falls_back_when_first_block_is_unusable():
    """When the leading prose is all lowercase continuation, copy must come
    from the next usable block rather than shipping an empty or broken card."""
    html = _article(
        "<p>and the price drops hard. but only during sales windows.</p>"
        "<p>The LG C3 leads the category on panel brightness. It also holds "
        "up gaming refresh rates without washing out HDR.</p>"
    )
    snippet = review_snippet(html)
    assert snippet.startswith("The LG C3"), snippet
    assert TERMINAL.search(snippet)


def test_newsletter_cta_is_never_the_snippet():
    html = _article(
        '<p>Scores out of 10. Based on the Abvorn Verdict Engine.</p>'
        "<div class=\"cta-banner\"><h3>Get more reviews like this</h3>"
        "<p>New guides, top picks, and price drops for these products &mdash; "
        "straight to your inbox. No spam, unsubscribe anytime.</p>"
        "<form><input name=\"email\"></form></div>"
        "<p>Logitech G305 is our current top pick for gaming mice. "
        "It earned an Abvorn Verdict score of 6.8 out of 10. "
        "The sensor tracks cleanly at 8000Hz and the battery lasts a month.</p>"
    )
    snippet = review_snippet(html)
    assert snippet, "expected real review copy as the snippet"
    assert "inbox" not in snippet.lower()
    assert "unsubscribe" not in snippet.lower()
    assert "Logitech" in snippet
    assert TERMINAL.search(snippet), "snippet must end on a complete sentence"


def test_newsletter_copy_is_rejected_on_its_own():
    assert (
        _clean_snippet(
            "New guides, top picks, and price drops for these products "
            "&mdash; straight to your inbox. No spam, unsubscribe anytime."
        )
        == ""
    )


def test_share_rail_inside_article_is_not_snippet_text():
    html = _article(
        "<p>The QuietComfort Ultra earbuds stay at $299. They deliver "
        "industry-leading ANC and a comfortable fit for long sessions. "
        "Battery life is the strongest in the range at eight hours.</p>"
        '<div class="rail-card"><p class="rail-card__title">Email this review</p>'
        "<p>Send yourself the full guide as a PDF &mdash; straight to your inbox.</p>"
        "</div>"
    )
    snippet = review_snippet(html)
    assert "QuietComfort" in snippet
    assert "inbox" not in snippet.lower()


# --- defect 3: truncation must land on a sentence boundary -------------------

def test_snippet_never_ends_mid_sentence():
    html = _article(
        "<p>In 2026, the demand for crystal-clear visuals has never been higher. "
        "Whether you are editing 4K video, diving into immersive games, or "
        "juggling multiple spreadsheets, a top-tier panel changes the whole "
        "experience. We tested the leading 27-inch 4K monitors side by side. "
        "Here is what actually separates them once you live with them.</p>"
    )
    snippet = review_snippet(html)
    assert TERMINAL.search(snippet), f"ends mid-sentence: {snippet!r}"
    assert "…" not in snippet, f"needed an ellipsis cut: {snippet!r}"


def test_two_sentences_when_the_budget_allows():
    html = _article(
        "<p>As 4K monitors become increasingly popular for work and "
        "entertainment, choosing the right one can be overwhelming. "
        "This guide breaks down the top options on Amazon. "
        "We tested each one over four weeks. "
        "Here is what actually matters when you spend this much.</p>"
    )
    snippet = review_snippet(html)
    assert _sentences(snippet) >= 2, f"wanted a few sentences, got {snippet!r}"


def test_snippet_never_starts_mid_thought():
    """Some published intros open with a lowercase continuation of an earlier
    clause; a card that starts "with brands like Lenovo, HP, and ..." reads as
    broken copy even though it is a complete sentence."""
    out = _complete_sentences(
        "with brands like Lenovo, HP, and Acme all competing for attention. "
        "Whether you need a machine for work or school, options are endless. "
        "Here is what actually matters.",
        200,
        3,
    )
    assert out.startswith("Whether"), out
    assert TERMINAL.search(out)


def test_complete_sentences_never_reopens_a_mid_thought_fallback():
    """Truncation must not undo the fragment skip.

    A streaming-devices intro was one long lowercase sentence, so the
    fragment-skip loop emptied ``parts`` and the budget fallback re-sliced the
    *original* text -- putting the lowercase open straight back into the card.
    Re-anchor on the first real sentence start.
    """
    src = (
        "every major brand packs 4K, HDR, and voice search into a stick the size "
        "of a thumb drive. The spec sheets start to blur fast. Pick by interface."
    )
    out = _complete_sentences(src, 90, 2)
    assert out.startswith("The"), out
    assert not out[:1].islower(), out


def test_complete_sentences_returns_empty_when_no_sentence_start_exists():
    """No capitalised sentence start anywhere means the source is unusable.

    Returning "" lets the caller fall back to the next source instead of
    shipping a card that opens mid-thought.
    """
    src = "and then the price drops. but only during sales, so buy carefully."
    assert _complete_sentences(src, 200, 2) == ""


def test_complete_sentences_respects_budget_and_sentence_count():
    text = " ".join(
        [
            "In 2026, laptops have never been more powerful.",
            "From AI-ready business machines to high-refresh gaming panels, "
            "the choices are endless.",
            "We tested the top picks.",
            "Verdict scores follow.",
        ]
    )
    two = _complete_sentences(text, 200, 2)
    assert _sentences(two) == 2
    assert TERMINAL.search(two)
    assert len(two) <= 200

    tiny = _complete_sentences(text, 40, 4)
    assert len(tiny) <= 41
    assert tiny.endswith("\u2026") or TERMINAL.search(tiny) or tiny.endswith("\u2026")


def test_sentence_splitter_keeps_abbreviations_intact():
    text = "We measured 4K panels, e.g. the S2725QS. U.S. buyers get the same kit. Budget picks win here."
    parts = _split_sentences(text)
    assert len(parts) == 3, parts
    assert "e.g. the S2725QS" in parts[0]
    assert "U.S. buyers get the same kit" in parts[1]


def test_oversized_single_sentence_is_marked_not_silently_cut():
    monster = "This one sentence is deliberately far longer than any card budget " + ("padding words " * 40) + "."
    out = _complete_sentences(monster, 120, 4)
    assert out.endswith("\u2026")
    assert len(out) <= 121
    assert "padding words padding words padding words padding words padding words" not in out


# --- defect 1: the overlay path shipped raw markup ---------------------------

def test_overlay_snippet_has_no_markup_and_no_mid_sentence_cut():
    article = {
        "post_title": "Best Robot Vacuums 2026",
        "intro": (
            "<p>In 2026, the best robot vacuum balances strong suction, smart "
            "navigation, and mopping ability while fitting your budget. "
            "After comparing the iRobot Roomba 11 combo against three rivals, "
            "the Roomba wins on obstacle handling. "
            "Here is what changed in this year's lineup.</p>"
        ),
        "products": [],
    }
    entry = _overlay_review(article, "robot-vacuums", "Robot Vacuums", "2026-10-04")
    snippet = entry["snippet"]
    assert snippet, "overlay card must carry copy"
    assert not MARKUP.search(snippet), f"markup leaked into the card: {snippet!r}"
    assert TERMINAL.search(snippet), f"ends mid-sentence: {snippet!r}"


def test_overlay_falls_back_to_meta_description_then_body():
    meta_only = _overlay_review(
        {
            "post_title": "A Guide",
            "intro": "<p>Too short.</p>",
            "meta_description": (
                "A proper meta description that carries a whole sentence about "
                "the category and a second one about who should buy it."
            ),
            "products": [],
        },
        "tv",
        "TV",
        "2026-10-04",
    )
    assert meta_only["snippet"].startswith("A proper meta description")
    assert TERMINAL.search(meta_only["snippet"])

    body_only = _overlay_review(
        {
            "post_title": "A Guide",
            "intro": "",
            "meta_description": "",
            "article_html": _article(
                "<p>OLED panels finally hit a price mainstream buyers accept. "
                "Every set we tested this year earned a verdict above 7.0. "
                "Here is where the money goes.</p>"
            ),
            "products": [],
        },
        "tv",
        "TV",
        "2026-10-04",
    )
    assert body_only["snippet"].startswith("OLED panels")
    assert _sentences(body_only["snippet"]) >= 2


# --- defect 4 and the card renderer ------------------------------------------

def test_card_renders_no_markup_and_ends_on_a_sentence():
    html = review_card(
        {
            "slug": "tv",
            "name": "TV",
            "title": "2026 TV Buying Guide",
            "rel": "/reviews/tv/buy.html",
            "snippet": (
                "<p>Mini-LED beats OLED for HDR. "
                "It holds brightness in a bright living room. "
                "Here is how they compare.</p>"
            ),
            "score": 7.2,
        },
        "TV",
        "",
    )
    m = re.search(r'<p class="review-card__snippet">(.*?)</p>', html, re.S)
    assert m, "card must render a snippet"
    text = m.group(1)
    assert not MARKUP.search(text), text
    assert "&lt;p&gt;" not in text
    assert TERMINAL.search(text), f"card ends mid-sentence: {text!r}"


def test_featured_card_gets_more_copy_than_a_regular_card():
    item = {
        "slug": "tv",
        "name": "TV",
        "title": "2026 TV Buying Guide",
        "rel": "/reviews/tv/buy.html",
        "snippet": (
            "Mini-LED beats OLED for HDR in a bright room. "
            "It sustains peak brightness without clipping highlights. "
            "OLED wins contrast and viewing angles instead. "
            "OLED blacks are still the deepest you can buy. "
            "Gaming latency favours the OLED panels. "
            "Here is how the two actually compare."
        ),
        "score": 7.2,
    }
    regular = review_card(item, "TV", "")
    featured = review_card(item, "TV", "", featured=True)

    def _snip(page):
        return re.search(r'<p class="review-card__snippet">(.*?)</p>', page, re.S).group(1)

    r, f = _snip(regular), _snip(featured)
    assert len(f) > len(r), (len(r), len(f))
    assert len(r) <= _CARD_SNIPPET_CHARS
    assert TERMINAL.search(r) and TERMINAL.search(f)


def test_card_without_usable_copy_renders_no_empty_snippet():
    html = review_card(
        {
            "slug": "tv",
            "name": "TV",
            "title": "Coming soon",
            "snippet": "",
            "score": None,
        },
        "TV",
        "",
    )
    assert '<p class="review-card__snippet">' not in html
    assert 'class="review-card__snippet"></p>' not in html


def test_line_clamp_can_show_the_card_budget():
    """The clamp is what actually hides overflow, so it must cover the budget.

    Measured in Chromium at three widths (1280px homepage 442px column, 1280px
    niche page 412px, 375px mobile 309px), 280 characters of card copy needs up
    to 7 lines in the narrowest column. A smaller clamp visually clips the
    snippet -- the exact defect this change set removes.
    """
    import inspect

    import src.deployment as deployment

    source = inspect.getsource(deployment)
    assert "-webkit-line-clamp:7;" in source
    assert "-webkit-line-clamp:8;" in source, "featured card clamp missing"
    for stale in ("-webkit-line-clamp:2;", "-webkit-line-clamp:3;", "-webkit-line-clamp:5;"):
        assert stale not in source, f"an old {stale} clamp survived"


# --- the off-niche pages that produced the bad cards ------------------------

def test_productless_off_niche_page_is_excluded_from_the_review_set():
    """A hotel-booking page filed under robot-vacuums (products: []) and a solar
    guide filed under laptops both reached the homepage as product cards. They
    carry no product signal at all, which is exactly what this checks."""
    hotel = _article(
        "<h1>robot-vacuums</h1>"
        "<p>You have felt the sting of a bad hotel pick before. "
        "That worry stays with you every time you search for a room.</p>"
        '<script id="abvorn-rps-data" type="application/json">'
        '{"products": [], "niche": "robot-vacuums"}</script>'
    )
    solar = _article(
        "<h1>Solar Panels for First-Time Buyers</h1>"
        "<p>Buying solar panels for the first time feels like stepping into "
        "the dark. You remember that last time you splurged on solar.</p>"
        '<script id="abvorn-rps-data" type="application/json">'
        '{"products": [], "niche": "laptops"}</script>'
    )
    assert page_has_products(hotel) is False
    assert page_has_products(solar) is False