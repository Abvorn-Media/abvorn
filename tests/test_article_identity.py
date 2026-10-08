"""Article identity must survive the deploy boundary.

Two gaps are locked here:

1. ``SiteDeployer.deploy_content`` used to return ``True``/``False`` and throw
   away the page path it wrote. The path is derived from ``post_title`` inside
   ``_title_slug()``, but callers passed no ``article_filename``, so every
   article shipped as ``reviews/<niche>/index.html`` and ``content.published``
   carried no slug, no filename and no url. With no identity, the Ambassador
   could only announce "our <niche> guide" and resolve products by niche, so
   two different articles in one niche produced the same post and the same
   product card.

2. ``review_page_candidates`` only matched niche folders and dated ``.html``
   files. A slugified article title (``best-tvs-of-2026-buying-guide``) matched
   nothing, so product lookup silently fell back to the niche ``index.html``
   and the *current* product set was used for every historical article.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from abvorn.agents.orchestrator import (
    DeployAgent,
    SiteDeployer,
    _article_filename,
    _slugify_article_title,
)
from abvorn.core.state import AbvornState
from abvorn.discovery.scanner import make_slug
from abvorn.domination import product_assets as pa


REAL_PRODUCT = {
    "name": 'Sony Bravia 9 II 65" OLED TV',
    "url": "https://www.amazon.com/dp/B0F1GF1KFC?tag=viraltestco-20",
}


def _deployer():
    return MagicMock()


def _state(tmp_path):
    return AbvornState(str(tmp_path / "state.db"))


def _run_act(state, site_deployer, result, event_id=7, agent=None):
    """Drive DeployAgent.act and return the emitted content.published message."""
    bus = MagicMock()
    bus.get_recent_events.return_value = [
        {"id": event_id, "message": {"niche": "tv", "result": result}}
    ]
    out = {}
    bus.publish.side_effect = lambda t, m: out.update({t: m})

    if agent is None:
        agent = DeployAgent.__new__(DeployAgent)
    agent.state = state
    agent.deployer = _deployer()
    agent.site_deployer = site_deployer
    agent.bus = bus
    asyncio.run(agent.act("deploy:tv"))
    return out.get("content.published", {})


# --- gap 1: deploy_content returns the path it wrote ----------------------

def test_deploy_content_returns_written_path():
    """A refused payload returns ""; a written one returns its repo path."""
    sd = SiteDeployer(_deployer(), None)

    refused = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide", "article_html": "<p>g</p>",
         "products": []},
        all_categories=["tv"],
        require_products=True,
    )
    assert refused == ""

    written = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide", "article_html": "<p>g</p>",
         "products": [REAL_PRODUCT]},
        all_categories=["tv"],
    )
    assert written == "reviews/tv/index.html"
    assert sd.deployer.deploy_html.call_args[0][1] == written


# --- gap 1: content.published carries identity -----------------------------

def test_published_event_carries_path_and_url(tmp_path):
    """The event must name the page that shipped, not just the niche.

    Without the path this payload has no slug/filename/url, so downstream media
selection falls back to the whole niche. ``url`` is set only for a real
        article file - a niche index is not a review, and pretending otherwise is
        what let a category page stand in for an article. The deploy agent now
        derives that file from the title, so the path is a slug rather than
        ``index.html``.
    """
    state = _state(tmp_path)
    sd = SiteDeployer(_deployer(), state)
    msg = _run_act(state, sd, {
        "post_title": "Best TVs of 2026: TCL QM8L vs Sony Bravia 9",
        "article_html": "<p>guide</p>",
        "products": [REAL_PRODUCT],
    })

    assert msg["niche"] == "tv"
    # The article ships at its own slugified URL, never the niche index: an
    # index.html write means each new post overwrote the previous one and no
    # post row could ever carry a filename.
    assert msg["path"] == "reviews/tv/best-tvs-of-2026-tcl-qm8l-vs-sony-bravia-9.html"
    assert msg["slug"] == "tv"
    assert msg["filename"] == "best-tvs-of-2026-tcl-qm8l-vs-sony-bravia-9.html"
    assert msg["url"] == (
        "https://abvorn.com/reviews/tv/"
        "best-tvs-of-2026-tcl-qm8l-vs-sony-bravia-9.html"
    )


def test_published_event_uses_article_filename_when_written(tmp_path):
    """When an article file is written, url/filename point at *it*.

    This is the whole point of returning the path: the niche index is a
    different page from the article, and only the article is a review.
    """
    state = _state(tmp_path)
    article = "best-tvs-of-2026-tcl-qm8l-vs-sony-bravia-9.html"

    class _SD(SiteDeployer):
        def deploy_content(self, niche, content, all_categories=None,
                           article_filename=None, require_products=False):
            # Mirrors what the real path writes when an article file is used.
            self.deployer.deploy_html("<html/>", f"reviews/{niche}/{article}")
            self._last_content = content
            self._last_niche = niche
            return f"reviews/{niche}/{article}"

    sd = _SD(_deployer(), state)
    msg = _run_act(state, sd, {
        "post_title": "Best TVs of 2026: TCL QM8L vs Sony Bravia 9",
        "products": [REAL_PRODUCT],
    })

    assert msg["path"] == f"reviews/tv/{article}"
    assert msg["filename"] == article
    assert msg["slug"] == "tv"
    assert msg["url"].endswith(article)


def test_deploy_records_filename_on_post_row(tmp_path):
    """A post whose article page shipped gets its filename recorded.

    ``_reviews()`` skips posts with no filename (a post with no page is not a
    published review), so the empty column meant deployed articles never
    produced a verifiable card.
    """
    state = _state(tmp_path)
    state.upsert_niche("tv", "Tv")
    state.add_post("tv", "Best TVs of 2026: TCL QM8L", "")

    agent = DeployAgent.__new__(DeployAgent)
    agent.state = state
    agent._record_published_filename("tv", "best-tvs-of-2026-tcl-qm8l.html")

    assert state.get_posts_for_niche("tv")[0]["filename"] == \
        "best-tvs-of-2026-tcl-qm8l.html"


# --- gap 2: per-article product resolution -------------------------------

def test_review_page_candidates_matches_slugified_article_title(tmp_path, monkeypatch):
    """A slugified article title must resolve to its own page.

    DeployAgent writes ``reviews/<niche>/<title-slug>.html``; only the niche
    folder and dated ``.html`` names were being hunted, so this missed and
    lookup silently degraded to the niche index.
    """
    monkeypatch.setattr(pa, "_review_roots", lambda: [tmp_path])
    page = tmp_path / "reviews" / "tv" / "best-tvs-of-2026-tcl-qm8l.html"
    page.parent.mkdir(parents=True)
    page.write_text("<html></html>", encoding="utf-8")

    assert page in pa.review_page_candidates("best-tvs-of-2026-tcl-qm8l")


def test_published_slug_not_clobbered_by_niche_directory(tmp_path):
    """A payload's article slug must survive the path fallback.

    The second path segment is the niche *directory*. Writing it over a
    payload's article slug would re-break the per-article targeting this change
    exists to provide.
    """
    state = _state(tmp_path)
    article = "best-tvs-of-2026-tcl-qm8l.html"

    class _SD(SiteDeployer):
        def deploy_content(self, niche, content, all_categories=None,
                           article_filename=None, require_products=False):
            self.deployer.deploy_html("<html/>", f"reviews/{niche}/{article}")
            return f"reviews/{niche}/{article}"

    sd = _SD(_deployer(), state)
    msg = _run_act(state, sd, {
        "post_title": "Best TVs of 2026: TCL QM8L",
        "slug": "best-tvs-of-2026-tcl-qm8l",
        "products": [REAL_PRODUCT],
    })

    assert msg["slug"] == "best-tvs-of-2026-tcl-qm8l", "niche dir clobbered the article slug"


def test_ambassador_post_body_carries_article_link(tmp_path):
    """The link must be in the post body.

    LinkedIn's image-post action sends ``commentary`` only and drops the
    ``url`` param, so an event that carries identity still produced a post
    linking nowhere. A bare URL in commentary is linkified on every path.
    """
    import abvorn.agents.ambassador as amb

    agent = amb.SocialAmbassador.__new__(amb.SocialAmbassador)
    agent.state = None
    agent.drive = None
    agent.router = MagicMock()
    agent.router.ask = lambda *a, **k: "New TCL QM8L review is live."
    agent.brain = None
    agent.social = MagicMock()

    captured = {}

    def _post(content, platform, media_paths=None):
        captured.update(content)
        captured["_media"] = media_paths
        return {"status": "posted", "platform": platform}

    agent.social.post.side_effect = _post

    url = "https://abvorn.com/reviews/tv/best-tvs-of-2026-tcl-qm8l.html"
    asyncio.run(agent._craft_and_post(
        {"niche": "tv", "platform": "linkedin",
         "headline": "Best TVs of 2026: TCL QM8L", "url": url},
        media_paths=["card.png"],
    ))

    assert captured["url"] == url
    assert url in captured["intro"], "post body must contain the article link"


def test_make_slug_is_word_boundary_and_deterministic():
    """The slugifier truncates on word boundaries, so a 60-char cut can never
    leave a trailing hyphen or split one product into two niches."""
    full = make_slug(
        "Amazon Echo Show 5 (newest model) Smart Display - Designed for a smart home"
    )
    partial = make_slug(
        "Amazon Echo Show 5 (newest model) Smart Display - Designed for"
    )
    assert full == partial, "old naive [:60] cut produced two slugs for one product"
    assert len(full) <= 60
    assert not full.endswith("-")
    # The historical artifact was a 60-char cut mid-word ending in "...-for-a".
    assert not full.endswith("-for-a")


# --- gap 3: the deploy agent derives a real filename -----------------------

def test_slugify_article_title_is_ascii_and_word_bounded():
    """Titles carry non-ASCII (non-breaking hyphens, smart quotes) that would
    mojibake across the Windows ANSI codepage on a path, and a naive ``[:60]``
    cut leaves a dangling hyphen."""
    slug = _slugify_article_title(
        '2026 TV Buying Guide: Insignia 50" & LG 55" Mini\u2011LED'
    )
    assert slug == "2026-tv-buying-guide-insignia-50-lg-55-miniled"
    assert all(ord(c) < 128 for c in slug)

    long = _slugify_article_title("word " * 60)
    assert len(long) <= 60
    assert not long.endswith("-")


def test_article_filename_is_canonical_reuse():
    """A repeated title resolves to the same canonical file.

    The old dedupe minted ``-2.html`` … ``-99.html`` then a timestamped file
    whenever the slug was already recorded for the niche. That is exactly the
    robot-vacuums flood (``best-robot-vacuums-expert-review-90.html``). The slug
    is the identity: the same review always refreshes its canonical URL instead
    of spawning siblings, and volume is bounded by the daily publish cap.
    ``taken`` is still accepted for call-site compatibility but never consulted.
    """
    taken = {"best-2026-tv-buying-guide.html", "best-2026-tv-buying-guide-2.html"}
    assert _article_filename("Best 2026 TV Buying Guide", set()) == (
        "best-2026-tv-buying-guide.html"
    )
    assert _article_filename("Best 2026 TV Buying Guide", taken) == (
        "best-2026-tv-buying-guide.html"
    )
    assert _article_filename("Best 2026 TV Buying Guide", taken) == (
        "best-2026-tv-buying-guide.html"
    )
    assert _article_filename("Best 2026 TV Buying Guide", taken | {
        "best-2026-tv-buying-guide-99.html"}) == "best-2026-tv-buying-guide.html"


def test_repeated_title_same_day_is_refused_by_cap(tmp_path):
    """The cap, not the dedupe, bounds volume: no second page per day.

    The second same-day deploy of an identical title used to mint ``-2.html``
    (then ``-3.html``, then timestamped files) - the flood. Now the daily
    per-niche cap refuses it outright, so the first page stays live and no
    near-identical second URL ships.
    """
    state = _state(tmp_path)
    state.add_post("tv", "Best 2026 TV Buying Guide", "")
    sd = SiteDeployer(_deployer(), state)
    agent = DeployAgent.__new__(DeployAgent)
    first = _run_act(state, sd, {
        "post_title": "Best 2026 TV Buying Guide",
        "article_html": "<p>guide</p>",
        "products": [REAL_PRODUCT],
    }, agent=agent)
    assert first["filename"] == "best-2026-tv-buying-guide.html"

    state.add_post("tv", "Best 2026 TV Buying Guide", "")
    second = _run_act(state, sd, {
        "post_title": "Best 2026 TV Buying Guide",
        "article_html": "<p>guide again</p>",
        "products": [REAL_PRODUCT],
    }, agent=agent)
    assert "filename" not in second, "same-day repeat minted a second page"
    assert second.get("path", "") == ""
    # The first post still owns the canonical filename; nothing was clobbered.
    recorded = {p["filename"] for p in state.get_posts_for_niche("tv")}
    assert recorded == {"", "best-2026-tv-buying-guide.html"}


def test_deploy_content_refuses_second_page_same_day(tmp_path):
    """The daily per-niche cap is the flood gate: one article page per niche/day."""
    state = _state(tmp_path)
    # One page already recorded today (created_at defaults to now).
    state.add_post("tv", "Best 2026 TV Buying Guide", "best-2026-tv-buying-guide.html")
    sd = SiteDeployer(_deployer(), state)
    refused = sd.deploy_content(
        "tv",
        {"post_title": "2026 Robot Vacuum Roundup", "article_html": "<p>g</p>",
         "products": [REAL_PRODUCT]},
        all_categories=["tv"],
        article_filename="2026-robot-vacuum-roundup.html",
    )
    assert refused == ""


def test_deploy_content_allows_first_page_of_day(tmp_path):
    """Before any page ships today the cap is not hit, so the first writes."""
    state = _state(tmp_path)
    sd = SiteDeployer(_deployer(), state)
    ok = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide", "article_html": "<p>g</p>",
         "products": [REAL_PRODUCT]},
        all_categories=["tv"],
        article_filename="2026-tv-buying-guide.html",
    )
    assert ok == "reviews/tv/2026-tv-buying-guide.html"


def test_deploy_content_cap_can_be_raised_by_env(tmp_path, monkeypatch):
    """ABVORN_MAX_NICHE_PUBLISHES_PER_DAY raises the daily limit."""
    monkeypatch.setenv("ABVORN_MAX_NICHE_PUBLISHES_PER_DAY", "2")
    state = _state(tmp_path)
    state.add_post("tv", "A TV Guide", "a-tv-guide.html")
    sd = SiteDeployer(_deployer(), state)
    ok = sd.deploy_content(
        "tv",
        {"post_title": "2026 TV Buying Guide", "article_html": "<p>g</p>",
         "products": [REAL_PRODUCT]},
        all_categories=["tv"],
        article_filename="2026-tv-buying-guide.html",
    )
    assert ok == "reviews/tv/2026-tv-buying-guide.html"


def test_index_html_is_never_reported_as_an_article(tmp_path):
    """A niche index is not a review page, so it must not become a filename.

    Stamping ``index.html`` onto a post would make ``_reviews()`` build a card
    pointing at the category page while claiming an article identity, and the
    post row would claim an article page that does not exist. The path is stubbed
    to the category index so the guard itself is what is under test.
    """
    state = _state(tmp_path)
    state.add_post("tv", "Insignia 50 Fire TV Review", "")

    class _IndexOnlyDeployer(SiteDeployer):
        def deploy_content(self, niche, content, all_categories=None,
                           article_filename=None, require_products=False):
            self.deployer.deploy_html("<html/>", f"reviews/{niche}/index.html")
            return f"reviews/{niche}/index.html"

    sd = _IndexOnlyDeployer(_deployer(), state)
    msg = _run_act(state, sd, {
        "post_title": "Insignia 50 Fire TV Review",
        "article_html": "<p>guide</p>",
        "products": [REAL_PRODUCT],
    })

    assert msg["path"] == "reviews/tv/index.html"
    assert "filename" not in msg, "a category index must not be announced as an article"
    assert "url" not in msg, "a category index is not an article url"
    recorded = [p["filename"] for p in state.get_posts_for_niche("tv")]
    assert "index.html" not in recorded
    # The niche is still recoverable from the directory, so media selection is
    # not left with nothing at all.
    assert msg["slug"] == "tv"


def test_recorded_filename_lands_on_the_post_row(tmp_path):
    """The deployed slug must reach state, otherwise _reviews() still skips it."""
    state = _state(tmp_path)
    # Posts are created before the page exists, with an empty filename - that
    # is the state the deploy step has to repair.
    state.add_post("tv", "Insignia 50 Fire TV Review", "")
    sd = SiteDeployer(_deployer(), state)
    msg = _run_act(state, sd, {
        "post_title": "Insignia 50 Fire TV Review",
        "article_html": "<p>guide</p>",
        "products": [REAL_PRODUCT],
    })
    expected = "insignia-50-fire-tv-review.html"
    assert msg["filename"] == expected

    recorded = [p["filename"] for p in state.get_posts_for_niche("tv")]
    assert expected in recorded, (
        "the slug never reached the post row, so _reviews() keeps skipping it"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))