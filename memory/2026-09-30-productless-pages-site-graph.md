# Debug report — productless pages leaked into the site graph (2026-09-30)

**Status:** DONE

## Symptom
Two follow-on findings from the "Categories covered = 3" fix:

1. `reviews/laptops/hotel-booking.html`, `reviews/laptops/solar-panels.html`
   and `reviews/robot-vacuums/hotel-booking.html` were live, self-canonical
   and not `noindex`, with zero products.
2. Stale dead-TV references were reported in `sitemap.xml`, `llms.txt`,
   `llms-full.txt` and `feed.xml`.

## Root cause
`scan_published_reviews()` (`src/deployment.py`) accepted every
`docs/reviews/<dir>/*.html` file as a published product review. It has no
product invariant, and it is the single source of truth for the homepage
cards, the category listings, `sitemap.xml`, `feed.xml`, `llms.txt` and
`llms-full.txt`. That one missing check let the content pipeline leak two
kinds of junk:

* **Off-topic article filed under a real niche.** The LLM wrote "First-Time
  Hotel Booking Guide" and "Solar Panels for Beginners" into `reviews/laptops/`
  and "First-Time Hotel Booking Guide" into `reviews/robot-vacuums/`.
* **A directory named after a product title**, created when the LLM returned a
  product name where a niche slug was expected:
  `reviews/roku-40-inch-select-series-smart-tv-2026-1080p-full-hd-tv-ro/` and
  `reviews/roku-55-inch-select-series-smart-tv-2026-4k-qled-tv-roku-tv-`.
  Both were meta-refresh stubs already redirecting to `/reviews/tv/`.

The daemon's `state.db` rated every one `quality_score = 10.0`, the maximum,
so the quality gate did not catch them either. They were absent from the
sitemap **only because the sitemap happened to be stale** — regenerating pulls
all five in (verified). So finding #2 (stale references) was a symptom of the
same staleness, not a separate defect.

Same failure class as the phantom "Coffee Grinder Buying Guide" card guarded in
`_reviews()` — see AGENTS.md, "Without a live page, no card".

## Fix
`page_has_products()` in `src/deployment.py`, applied as a filter inside
`scan_published_reviews()`. A page qualifies via a sponsored Amazon `/dp/`
link, a `compare.html?asin=` link, a non-empty `abvorn-rps-data` product set,
or a JSON-LD `Product` block.

Two signals that look right but are not:

* `itemprop="mainEntity"` — that is the FAQPage schema's question list. All
  three off-topic pages shipped with it, so using it as a product signal
  accepts exactly the pages this gate exists to reject. Excluded deliberately.
* `/dp/` alone is insufficient — `reviews/wireless-earbuds/index.html` has 1
  product and 0 `/dp/` links. It qualifies via the RPS JSON only.

Also deleted the 5 junk pages and 2 orphan PDFs. 12 real niches and 150
product-carrying reviews remain.

## Evidence
* New test `tests/test_productless_pages.py` — 6 tests, 4 fail without the fix.
* Full suite 1148 passed / 1 skipped; `test_pipeline.py` 2/2.
* `scripts/check_publish_content.py` and `scripts/repair_false_claims.py`
  clean on 205 files (was 210 — matches the 5 HTML deletions).
* Real tree: 150 published reviews across 12 niches, junk gone.
* VPS regeneration into a throwaway dir: all four meta files CLEAN.
* Live: all junk 404, homepage dropped 157 → 150 guides, stats still
  `categories=6`, 6 sections, all niche hubs 200.

## Recurrence vector (closed)
`state.db` held 5 `pending` rows whose `filename` pointed at the deleted
files, all off-topic and all `quality_score = 10.0`
(ids 78, 109, 143, 370, 497 — hotel booking, solar panels, coffee grinder).
The publisher would have recreated the pages on its next cycle. All 5 set to
`deployment_status='unpublished'`; backup at
`/home/ubuntu/.abvorn/state.db.bak-junk-20260930-132317`.

Note the VPS daemon's DB is `/home/ubuntu/.abvorn/state.db`, **not**
`/opt/abvorn-core/.abvorn/state.db` as AGENTS.md states. All three of
`/home/ubuntu`, `/opt/abvorn-core/data` and `/root` hold a `state.db`; the
daemon uses the first.

## Follow-ups (not fixed here)
* The productless-page gate is the *containment* fix. The deeper cause is
  still upstream: the content agent produces off-topic articles and a product
  name where a niche slug is expected, and the scorer rates both 10.0. A
  niche-relevance check in `abvorn/agents/` would stop them at the source.
* `quality_score = 10.0` on obviously off-topic content suggests the scorer
  does not evaluate topical relevance at all.
* `scan_published_reviews()` returns an empty `updated` for every scanned
  review, so "newest" ordering on the homepage is not actually date-driven.
