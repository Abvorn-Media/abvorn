# Growth foundation phase 1 — implementation plan

**Spec:** `notes/growth-foundation-phase1-design.md` (approved by owner 2026-11-20)
**Status:** ready for execution
**Plan location:** `notes/` — `docs/` is the published web root and internal specs there are gitignored.

## Global conventions (apply to every task)

- Work from the repo root: `C:\Users\Jean Mare\Documents\Default Project`.
- **TDD per task:** add the failing test, run it and confirm it fails for the intended reason,
  implement, run it green, then commit. One commit per task with the message shown.
- Never print, log or commit secret values. `data/gsc_*.json` are gitignored — do not force-add
  them. Only credential *key names* may appear in code.
- Do not modify `state.db` or delete pre-existing untracked scratch files.
- Every generated write goes through `write_checked()` in `src/deployment.py`; never write
  generated pages with raw `Path.write_text`.
- Tests must pass on a clean checkout **without** `state.db` (CI condition). Do not reintroduce
  state-dependent import-time maps.
- Baseline verification commands and current results:
  `python -m pytest tests -q` → 1413 passed, 1 skipped;
  `python -m ruff check .` → clean;
  `python scripts/check_publish_content.py` → clean (1603 files).

---

## Task 1 — Canonical Search Console property selection

**Files:** `abvorn/core/gsc_client.py`, new `tests/test_gsc_client_property.py`

**Tests to write first** (use a fake `_service.sites().list().execute()`; never real credentials):
1. `ABVORN_GSC_PROPERTY` naming an existing property selects exactly it.
2. Override naming a missing/inaccessible property logs a warning and falls through to the
   preference list (does **not** disable the client, does **not** select the bad property).
3. Without override, `sc-domain:abvorn.com` wins over any `github.io` property listed first.
4. Without a domain property, an `https://abvorn.com/*` URL wins over `github.io`.
5. A non-canonical selection (`www.abvorn.com`, `http://abvorn.com/`, `github.io`) emits a
   warning containing `host mismatch`; the chosen property is logged at INFO.
6. All-invalid/empty list preserves today's fallback (first verified entry, else `None` →
   `enabled=False`) so no behavior regresses.

**Implementation:**
- Add module-level constants near `DEFAULT_CREDENTIALS_PATH` (line 25):
  `CANONICAL_HOST = "abvorn.com"`, `PROPERTY_OVERRIDE_ENV = "ABVORN_GSC_PROPERTY"`.
- Add small pure helpers `_property_host(url)` (strip scheme, `www.`, path, trailing slash via
  `urllib.parse.urlsplit`) and `_is_canonical_property(url)` (host == `abvorn.com`).
- In `_pick_property()` (lines 81–95): fetch entries once; compute verified entries as today;
  resolve override first if it exactly matches a listed property; otherwise prefer, in order,
  `sc-domain:abvorn.com`, any `https://abvorn.com/*` verified URL, then the existing first-entry
  fallback. Return the selection, log `INFO GSC property selected: %s`, and `WARNING` with
  `host mismatch` whenever the selected URL is non-canonical. Keep the method signature and
  `Optional[str]` return type unchanged.
- No new required configuration; the env var is additive.

**Verify:** `python -m pytest tests/test_gsc_client_property.py -q` then
`python -m ruff check abvorn/core/gsc_client.py tests/test_gsc_client_property.py`.
**Commit:** `fix(gsc): prefer canonical abvorn.com Search Console property`

---

## Task 2 — Feed high-impression rows into the category demand gate

**Files:** `abvorn/core/gsc_client.py`, `abvorn/core/gsc_ingestor.py`,
`tests/test_evidence_gate.py` (extend), `tests/test_gsc_ingestor.py` (extend)

**Facts to preserve:** `fetch_growth_opportunities()` (gsc_client.py:160–184) filters
`impressions > 100 and ctr < 0.02`, returns `query/page/...` rows, and
`GSCIngestor._ingest_to_graphify()` (gsc_ingestor.py:115–131) already writes them to
`data/gsc_growth_opportunity.json` when non-empty. `category_evidence()` (lines 26–48) reads only
`gsc_top_performing.json` and currently sums rows.

**Tests to write first:**
1. `fetch_growth_opportunities()` rows include `url` equal to the `page` key.
2. `category_evidence(tmp_path)` with only `gsc_growth_opportunity.json` returns the segment's
   impressions/clicks (accept both `url` and legacy `page` keys).
3. **No double counting:** one URL repeated under 20 different queries contributes its
   impressions/clicks exactly once (max per URL, not sum).
4. Same URL in both files contributes max(impressions), max(clicks) — not the sum of both.
5. Two different URLs in one segment sum their per-URL maxima.
6. Missing growth file preserves current top-only behavior exactly; malformed JSON in either
   file is ignored, never raises (existing contract).
7. Existing `tests/test_evidence_gate.py` and `tests/test_discovery.py` cases stay green — the
   evidence gate thresholds and `SITE_CATEGORY_MAP` are unchanged.

**Implementation:**
- gsc_client.py ~line 175: add `"url": keys[1] if len(keys) > 1 else ""` to each result.
- gsc_ingestor.py: replace the body of `category_evidence()` with a small module-private helper
  `_rollup_items(items, totals, per_url)` that:
  - takes `url = it.get("url") or it.get("page")`,
  - regexes `/reviews/([a-z0-9-]+)/` as today,
  - keeps a per-URL dict `{segment: {impressions: max, clicks: max}}`,
  - then folds those maxima into the returned `{segment: {impressions, clicks}}` sums.
  Call it for `gsc_top_performing.json` first, then `gsc_growth_opportunity.json`, each in its
  own `try/except Exception → {}` so one missing/bad file cannot erase the other's evidence.
- Do not change the file name, thresholds, or `GSCIngestor` write path.

**Verify:** `python -m pytest tests/test_evidence_gate.py tests/test_discovery.py tests/test_gsc_ingestor.py -q`
then `python -m ruff check abvorn/core/gsc_client.py abvorn/core/gsc_ingestor.py`.
**Commit:** `fix(gsc): count high-impression pages once in category demand evidence`

---

## Task 3 — Truthful freshness dates and a single URL inventory

**Files:** `src/deployment.py` (`write_site_metadata`, `write_files` items), `run_cycle.py`
(items), new `tests/test_site_metadata_dates.py`; keep `tests/test_feed_xml_escape.py` green.

**Facts:** `scan_published_reviews()` (deployment.py:921–1019) returns each review's real
`updated` in the dict. Both call sites throw it away and stamp `datetime.now()` on every item
(run_cycle.py:3343–3348, deployment.py:3745–3752), which is why all sitemap `<lastmod>` values
were `2026-11-15`. `write_site_metadata()` (3426–3553) emits alphabetical `items[:50]` as
"Latest reviews", flattens all core dates to one `newest`, and knows only core + categories +
reviews. Blog pages live at `docs/blog/<slug>/index.html`; comparisons at
`docs/comparisons/*.html`.

**Tests to write first:**
1. `llms.txt` contains a `Generated:` line (ISO date) and `## Latest reviews` sorted by date
   descending — not alphabetically by slug.
2. `feed.xml` `<pubDate>` matches each item's date (parse with `xml.etree.ElementTree`), and two
   items with different dates produce two different `pubDate` values.
3. `sitemap.xml` emits each item's own `<lastmod>`; items without a date use the newest known
   date; core pages use that newest date rather than "today".
4. With `docs/blog/a/index.html` and `docs/comparisons/x.html` present, both URLs appear in
   `sitemap.xml`, `llms.txt` and `llms-full.txt`; `feed.xml` still contains **only** review
   items (no blog/comparison `<item>`).
5. XML escaping and well-formedness tests from `test_feed_xml_escape.py` remain green.
6. A write with zero items still produces valid empty metadata (existing category test green).

**Implementation:**
- In `write_site_metadata()`, add module-private helpers:
  - `_item_date(it)` → `it.get("updated") or it.get("date") or newest` (accept both keys so
    existing callers/tests keep working).
  - `_discover_extra_urls(docs_dir)` → sorted `(title, path)` pairs from
    `docs_dir/blog/*/index.html` (title from `<title>`/`og:title`, fallback to slug) and
    `docs_dir/comparisons/*.html`; missing directories yield `[]`.
  - `_url_inventory(docs_dir, items, category_pairs)` → one ordered structure of
    `(section, title, path, date)` covering core, categories, reviews, blog, comparisons.
    Every artifact in this function is built from it so no later write can erase a section.
- Replace direct `items[...]` loops in `llms.txt`, `llms-full.txt`, `feed.xml` and `sitemap.xml`
  with the inventory. Keep `write_checked()` for all five files and keep `SITE_ROBOTS_TXT`.
- Add `Generated: <ISO date>` to the `llms.txt` header and `llms-full.txt` header.
- Sort the "Latest reviews" slice by `_item_date` descending before `[:50]`.
- Feed stays review-only; `_rfc822` and `_xml_escape` stay as-is.
- Call sites: in `run_cycle.py:3347` and `src/deployment.py:3751`, set
  `"date": p.get("updated") or p.get("date") or datetime.now().date().isoformat()` and include
  `"updated": p.get("updated", "")`. Where `all_posts` lacks a real date, prefer the matching
  `scan_published_reviews("docs")` entry's `updated` by slug — do not invent a date.
- Both writer paths keep calling `write_site_metadata()`; do not delete either writer.

**Verify:** `python -m pytest tests/test_site_metadata_dates.py tests/test_feed_xml_escape.py tests/test_category_unify.py tests/test_seo.py -q`
then `python -m ruff check src/deployment.py run_cycle.py`.
**Commit:** `fix(seo): real lastmod/pubDate and complete URL inventory`

---

## Task 4 — Consistent, non-duplicated JSON-LD

**Files:** `scripts/inject_ai_seo.py`, `tests/test_inject_ai_seo.py` (extend)

**Facts:** `process()` (lines 167–198) only checks for its own `ai-seo:schema` marker and
injects an `Article` on any `og:type=article` page. Seven blog pages contain one
`<script type="application/ld+json">` holding three concatenated JSON objects
(Article + FAQPage + BreadcrumbList) plus an injected duplicate `Article`. The review pages
embed structured product data in `<script id="abvorn-rps-data" type="application/json">`
(deployment.py:871). `inject_tree()` (201–224) is idempotent via the marker.

**Tests to write first:**
1. A script with three concatenated objects is rewritten to one valid `@graph` containing all
   three `@type`s; `json.loads()` on the single script succeeds.
2. When a valid `Article` exists in the page's JSON-LD (including inside a repaired graph),
   `process()` injects no second `Article` — assert exactly one Article block in the output.
3. An unparseable concatenated fragment is left byte-identical and a warning is logged; no
   extra invalid JSON is emitted.
4. Non-article hub page (`docs/tv/index.html`-shaped HTML with review links) gets `WebPage`
   plus `ItemList` whose `itemListElement` URLs use the final `https://abvorn.com/...` base.
5. Review page with two products in `abvorn-rps-data` gets one `ItemList` with two `Product`
   nodes, names/prices/URLs from the data, canonical `SITE_BASE` URLs, and **no**
   `aggregateRating` key anywhere.
6. `process(process(html)) == process(html)` for all new cases (idempotence).
7. All existing `tests/test_inject_ai_seo.py` cases stay green, including ASCII-safe output.

**Implementation:**
- Add helpers near `ld_block()`:
  - `_parse_ld_fragments(text)` → list of objects using `json.JSONDecoder().raw_decode()` in a
    loop, skipping whitespace; returns `None` if any fragment fails or no object is found.
  - `_existing_ld_types(html)` → set of `@type` values over every `application/ld+json` script,
    flattening `@graph` nodes.
  - `_normalize_ld_scripts(html)` → for each LD script with >1 parsed fragment, replace its
    content with `{"@context": "https://schema.org", "@graph": [...]}`; leave single/invalid
    scripts untouched and `logger.warning` on invalid. Preserve the original newline style.
  - `itemlist_obj(rel, html)` → `ItemList` from either `abvorn-rps-data` products (preferred;
    parse the JSON with `json.loads`, skip entries without a name, omit missing price/image,
    never synthesize `aggregateRating`) or, for hub pages, from `href` links to
    `/reviews/...` / `/categories/...` found in the HTML. Build URLs with `rel_url()`/`SITE`.
- In `process()`: call `_normalize_ld_scripts()` **before** deciding what to inject; compute
  `types = _existing_ld_types(html)`; inject `Article` only when `is_article and "Article" not
  in types`, `WebPage` only when `"WebPage" not in types`; append `itemlist_obj()` for review
  and hub pages when no `ItemList` exists. Keep the date extraction before `wrap_time()`.
- For the 7 already-affected blog pages, the normalization removes the invalid fragment;
  the existing injected duplicate `Article` is suppressed by removing an `ai-seo:schema`
  Article block when a valid Article already exists in the page. This is part of the one-time
  regeneration in Task 5, not a hand-edit of individual pages.

**Verify:** `python -m pytest tests/test_inject_ai_seo.py -q` then
`python -m ruff check scripts/inject_ai_seo.py`.
**Commit:** `fix(seo): normalize JSON-LD graphs and stop duplicate Article schema`

---

## Task 5 — Regenerate artifacts, audit, verify, ship

**Files:** regenerated `docs/llms.txt`, `docs/llms-full.txt`, `docs/sitemap.xml`, `docs/feed.xml`,
plus HTML pages changed by the injector. No hand-edits to generated pages.

**Steps:**
1. Regenerate metadata through the canonical builder using published pages as the source of
   truth (no LLM calls, no `run_cycle.py` full rebuild):
   ```
   python -c "from pathlib import Path; from src.deployment import scan_published_reviews, write_site_metadata; rs=scan_published_reviews('docs'); items=[{'title':r['title'],'slug':r['rel'].lstrip('/'),'date':r.get('updated',''),'updated':r.get('updated','')} for r in rs]; write_site_metadata('docs', items)"
   ```
   Confirm the diff touches only the five metadata files and that review cards/payloads are
   untouched.
2. Apply structured-data repairs: `python scripts/inject_ai_seo.py --root docs`, then
   `python scripts/inject_ai_seo.py --root docs --check` (must report 0 pages needing change).
3. Global read-only JSON-LD audit over `docs/**/*.html`: every LD script must be a single
   parseable JSON value (after Task 4 normalization) and no page may contain two `Article`
   nodes. Report any residual pages; do not broaden the repair set beyond blog, hubs and
   review pages.
4. Attempt one manual GSC re-ingest with the existing service-account credentials to confirm
   Task 1/2 behavior on real rows. Do **not** commit the refreshed gitignored `data/gsc_*.json`.
   If credentials/network fail, record that and rely on the scheduled 24h ingest.
5. Full verification, all before commit:
   ```
   python -m pytest tests -q
   python -m ruff check .
   python scripts/check_publish_content.py
   ```
   Expected: full suite green (allow the known local `test_daemon_start_stop` copyguard timeout
   only if CI is green), ruff exit 0, encoding scan exit 0.
6. Commit generated artifacts, push, and confirm CI + Pages build are green on the pushed SHA.
7. Live checks with cache-busting query strings: fetch `https://abvorn.com/llms.txt`,
   `sitemap.xml`, `feed.xml` and one repaired blog page; verify the `Generated:` line,
   recency ordering, distinct `lastmod`/`pubDate` values, blog + comparison URLs present, and
   valid JSON-LD on the blog page.

**Commit:** `chore(seo): regenerate metadata and structured data`

---

## Done criteria (from the approved design)

- GSC selection prefers canonical `abvorn.com` and warns on mismatch; a bad override falls
  through loudly.
- `category_evidence()` consumes both GSC files with per-URL max semantics; thresholds unchanged.
- Sitemap/feed/AI indexes carry real dates and cover core, hubs, reviews, blog and comparisons.
- No invalid or duplicate JSON-LD in the repaired set; hub `ItemList` and review product schema
  use canonical URLs and no fabricated ratings.
- Full suite, ruff, encoding scan, CI, Pages build and live-site checks all pass; no secrets,
  no `state.db` mutation, no unrelated page churn.
