# Growth foundation — design (2026-11-20)

**Status:** draft for review

## Intent and why

Abvorn already has a full autonomous content and distribution pipeline. Its growth loop is
inert for a mundane reason: the demand signal feeding it is wrong, and the machine-readable
surfaces that answer engines read are stale or malformed. Search Console data currently
comes from a `github.io` property with 6 impressions and 0 clicks, so the evidence gate,
GSC opportunity minting and the `seo-growth` win loop all correctly refuse to act. At the
same time `llms.txt`, `sitemap.xml` and `feed.xml` carry flattened dates and omit whole
sections, and several blog pages emit invalid JSON-LD.

This project fixes the signal and the surfaces before any new agents or concurrency are
added. It is phase 1 of a three-phase initiative; phases 2 (activate authorized
integrations) and 3 (owned-agent coordination layer) are explicitly out of scope here.

Location note: this document lives in `notes/`, not `docs/superpowers/specs/`, because
`docs/` is the published web root in this repository and internal specs must not ship to
abvorn.com. The repo also ignores `.agents/` and `docs/specs/`; `notes/` is the tracked
home for internal working documents.

## Goals

1. **Demand path is real.** GSC selection prefers the canonical `abvorn.com` property,
   logs a warning on host mismatch, and category evidence consumes both top-click pages
   and high-impression/low-CTR opportunity rows. Existing thresholds stay unchanged.
2. **Discovery metadata is truthful.** `lastmod`/`pubDate` use each page's real updated
   date; `llms.txt` is ordered by recency and carries a generated timestamp; one metadata
   builder owns core pages, categories, reviews, blog and comparisons so a later write
   cannot erase a section.
3. **Structured data is consistent.** No invalid or duplicate JSON-LD; hub pages expose
   `WebPage`/`ItemList`; compared products are exposed via a `Product`/`ItemList` graph
   using the final canonical URL, with no fabricated ratings.
4. **Verification is reproducible.** Targeted tests for each behavior, full suite, ruff,
   encoding scan, regenerated committed artifacts, green CI, successful Pages build and
   a live-site check.

## Non-goals

- No new articles, new categories, or changes to opportunity scores/thresholds.
- No MCP/A2A protocol, new agent types, or cross-process locking (phase 3).
- No credential rotation, account setup, or external posting (phase 2). The Telegram
  token rotation tracked separately remains separate.
- No change to the evidence-gate policy (`min_sources` stays as-is in this phase).
- No widening of `mobile_server.py` `/api/exec`, `/api/write` or any auth surface.

## Anti-goals (what would make this a failure even if it "works")

- Publishing a spec, test artifact or scratch file to the live site.
- A second metadata builder or post-build rewriter that becomes a competing source of
  truth — this repo has already been burned by duplicate writers and phantom pages.
- Silent degradation: integrations that fail open without a warning when the configured
  property or date source is wrong.
- Any mojibake or copy-gate regression at the publish boundary.

## Constraints

- The daemon publishes through the GitHub API to the remote branch tree; local `docs/`
  is a generated snapshot. Artifacts regenerated locally must go through `write_checked()`
  and `scripts/check_publish_content.py`.
- CI runs pytest on a clean checkout with no `state.db`. Tests must not depend on local
  state, and `CATEGORY_MAP` must remain deterministic (the `tv` static-map fix stays).
- Copy guard hard-blocks social/email and is report-only for pages; encoding guard raises
  on mojibake. Neither may be bypassed.
- Secrets are resolved at runtime; only key names may appear in code, logs or this doc.
  Never print values.
- Single-writer `state.db` with no cross-process lock on the autonomous path — this
  phase must not add concurrent writers.

## Approaches considered

1. **Surgical patches to the existing builders (chosen).** Change `gsc_client.py`,
   `gsc_ingestor.py`, `src/deployment.py`, `run_cycle.py` and `scripts/inject_ai_seo.py`
   in place, add tests, regenerate artifacts. Smallest diff, preserves the generation
   flow, easy to verify against the 1,600-page tree. Trade-off: leaves two writer
   functions in `src/deployment.py` and `run_cycle.py`; we reduce divergence by making
   both call the same metadata/schema helpers rather than deleting either writer.
2. **New unified metadata/schema module that replaces both writers.** Cleaner endpoint,
   but a large refactor with high regression risk across every generated page and no
   additional user-visible benefit for this phase. Rejected for now.
3. **Post-generation fixer script that rewrites `docs/` after each build.** Fastest to
   ship but creates a second source of truth and guarantees future drift — the same
   failure mode as the duplicate-writer bug. Rejected.

## Design decisions (builder should treat these as settled)

- GSC property preference order: explicit override env var (new, additive) → a
  `sc-domain:abvorn.com` property → an `https://abvorn.com/*` property → existing
  first-property fallback with a warning. No new required configuration.
- `category_evidence()` reads a new optional page-level growth input alongside the
  existing top-performing file; missing files remain a no-op. Thresholds and segment
  mapping are unchanged.
- Metadata dates come from the review's own `updated` field; core pages use the newest
  review date only where a per-page date genuinely does not exist. `llms.txt` gets a
  generated line and sorts its "Latest reviews" slice by `updated` descending.
- One helper produces the full URL inventory and is called by every writer path, so
  blog and comparison URLs survive later metadata writes.
- The AI-SEO injector detects an existing valid `Article` node and does not inject a
  duplicate; malformed concatenated blog JSON-LD is wrapped in a single `@graph`.
- Hub pages get `WebPage` + `ItemList`; product schema is built from all products with
  the final canonical base. No `aggregateRating` unless real review data backs it.

## Reviewer answers — builder calls

A fresh engineer reviewer asked eight questions that a wrong guess would make expensive.
These are settled here as builder calls; none require a product decision from the owner.

1. **Growth input source and schema.** `_ingest_to_graphify()` already writes
   `data/gsc_growth_opportunity.json` whenever `fetch_growth_opportunities()` returns
   rows (the file is simply absent today because there are none). The ingestor will keep
   that write and add `url` (derived from `page`) to each row; the envelope stays the
   same as `gsc_top_performing.json` (`{type, subtype, timestamp, items: [...]}`), and
   items carry `url`, `page`, `query`, `impressions`, `clicks`, `ctr`, `position` and
   `opportunity_score`. `category_evidence()` reads both files; either one missing
   remains a no-op.
2. **Merge semantics.** Per URL, take the **max** of impressions and clicks across all
   sources and rows; then sum those per-URL maxima within a segment. Never sum
   query-level rows — one page appearing under many queries would multiply its demand
   and falsely cross the threshold. The current top-performing file has one row per URL,
   so this is a no-op for it.
3. **URL inventory scope.** Exactly the five named groups: core pages, category hubs,
   reviews, blog posts, comparison pages. Do not enumerate all ~1,600 HTML files.
   `llms.txt`, `llms-full.txt` and `sitemap.xml` get all five; `feed.xml` stays a
   review-only RSS feed but gets real `pubDate` values. This bounds the diff and keeps
   feed semantics intact.
4. **Property override and host mismatch.** New additive env var `ABVORN_GSC_PROPERTY`
   holds an exact property id. If it names a missing, unverified or inaccessible
   property, warn loudly and fall through to the preference list — never silently query
   a wrong host, and never disable a working integration. Canonical host is exactly
   `abvorn.com`; `www.abvorn.com`, `http://abvorn.com/` and `github.io` all warn. Log the
   chosen property at INFO.
5. **Blog JSON-LD fragments.** Yes — split concatenated objects with
   `json.JSONDecoder().raw_decode()` in a loop, wrap them into one `@graph`, and treat an
   `Article` inside those fragments as an existing Article so the injector skips its own.
   If a fragment cannot be parsed, leave the block untouched and log a warning rather
   than emitting more invalid JSON.
6. **Backfill.** Code-only in phase 1. During verification, attempt one manual re-ingest
   with the existing service-account credentials; if it succeeds, use the refreshed
   (gitignored) files to confirm behavior but do not commit them. If it fails, keep the
   stale data and rely on the scheduled 24h ingest. No new credentials are requested.
7. **Product schema source.** Parse the existing `abvorn-rps-data` JSON already embedded
   in review pages (name, price, URL, image where present). Emit `ItemList` → `Product`
   with the final canonical base and real values; omit price/image rather than invent
   them. No `aggregateRating` from the computed verdict score — ratings require real
   user review data, which we do not have.
8. **JSON-LD invariant scope.** A global read-only audit over every HTML file under
   `docs/` is a verification step. Repair only the affected page types (blog, hubs, and
   review pages the injector touches). The audit reports any remaining invalid or
   duplicate blocks without failing the build unless they are in the repaired set.

## What is left to the builder

- Exact function signatures, module boundaries and test file names.
- Whether the 7 malformed blog pages are repaired in place or regenerated, whichever
  keeps the diff smaller and passes the encoding/copy guards.
- Ordering of artifact regeneration and verification commands.
- Any small compatibility shim needed so the two writer paths share the new helpers.

## Verification checklist

- `python -m pytest tests -q` (full suite, including the no-`state.db` CI condition)
- `python -m ruff check .`
- `python scripts/check_publish_content.py`
- Regenerate `docs/` metadata with the canonical builder; confirm no card/payload
  regressions and no unrelated page churn.
- Push, wait for CI + Pages build, then fetch the live homepage, `llms.txt`,
  `sitemap.xml` and `feed.xml` and verify dates, ordering and coverage.
