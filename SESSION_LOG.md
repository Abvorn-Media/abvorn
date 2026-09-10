# Session Log — 2026-08-14

## Fixes shipped (all committed, pushed, verified live)
1. **`2085348`** — HTML-escape fix: raw markdown `**` asterisks rendering as text on 4 review pages (32 occurrences), converted to `<strong>`. Editorial prose preserved per user choice.
2. **`1d96e89`** — Skip-link orange-edge bug: `.skip-link` 43px tall but offset `top:-40px`, leaving ~3px visible at top of every page. Changed to `top:-100px` across 61 pages. Also removed a stale `.git/rebase-merge` dir blocking rebases.
3. **`11f630b`** — Laptop review page structure: removed an orphan `<p` tag before the decision matrix that broke the article container (CTA/FAQ/footer rendered full-width), and removed the duplicate editorial FAQ (kept templated "Frequently Asked Questions"). Repaired 2 smart-home pages defected by the content cycle.
4. **`9f4e794`** — Root-cause fix in `src/article_design.py` `sanitize_article_html()`: now strips a dangling trailing `<p>` (AI drafts ending mid-tag) so it no longer swallows the appended decision matrix. Added regression test.

## DeepSeek suggestions — verified, corrected, implemented
- **n8n collection audited** (2026-08-14): 1,653 workflow JSONs / 23,159 nodes / 85 integrations / 174 active in `C:\Users\Jean Mare\Downloads\n8n-20260814T150531Z-1-001\n8n`. README claims 2,053/365/29,445/215 — all inflated.
- **Hindsight Reflection module** — DeepSeek draft REFUTED (imported a nonexistent `hindsight_learner.py`, undefined `generate_reflection_id`, wrong ports). Rebuilt against the real repo, commit `1b39f3e`: `abvorn/core/reflection.py` (Reflection + ReflectionStore, unified SQLite + JSONL + Obsidian), `HindsightLearner` in `abvorn/core/learner.py`, `reflections` table in `unified_database.py`, `/api/reflections` + `/api/reflections/summary` on mobile_server.
- **n8n integration** — DeepSeek draft REFUTED (webhook imported nonexistent module, missing `/api/content/recent`, `journal_update`; workflow 4 read `should_evolve` never returned; wrong port 8000; nonexistent `templates/dashboard.html`; wrong import curl). Rebuilt against the real repo (pending commit):
  - `abvorn/core/n8n_bridge.py`: `N8NBridge` (defaults n8n 5678, webhook target `http://localhost:8080`), triggers + health, singleton.
  - `mobile_server.py`: `POST /webhook/abvorn/{action}` (generate_reflection, publish_content via `Colosseum`, gsc_fetch, evolution_check → returns `should_evolve`, journal_update → Cortex vault Journal), `GET /api/content/recent`, `GET /api/n8n/status`, `POST /api/n8n/trigger/{path}`.
  - `console_dashboard.py`: N8N card in the real dashboard (there is no `templates/dashboard.html`); also fixed pre-existing crash — SPN organ called `len()` on an int.
  - `n8n/workflows/*.json`: 4 corrected workflows (reflection, publish, gsc-analysis, evolution-check) all via `$env.ABVORN_URL`, no hardcoded `:8000`.
  - `tests/test_n8n_bridge.py`: 13 tests.

## Verification
- 47 tests pass (`test_phase4_integration.py` + `test_encoding_guard.py`)
- 70 tests pass after reflection (9) + n8n (13) suites added.
- Mojibake scan: OK on all touched files.

## Still-open items (not fixed)
- `APPS_SCRIPT_URL=""` — newsletter/subscribe forms won't POST.
- Live product fetch needs `OPENWEB_NINJA_KEY` (GitHub Actions only).
- Content cycle regenerates pages that occasionally re-introduce defects; `_repair_warm.py` (untracked) catches them.

## Recurring fact
- GitHub push only via proxy: `git -c http.proxy=http://127.0.0.1:3213 push origin main`.

> NOTE (added 2026-09-08): the uncommitted session sections that sat between
> this 2026-08-14 entry and 2026-09-07 were accidentally reverted with
> `git checkout -- SESSION_LOG.md` during the GSC fix deploy. The 09-07 and
> 09-08 sections below were restored from the working-copy transcript; any
> older middle sections are not recoverable.

---

# Session Log — 2026-09-07 — Building the Instagram publish path (IN PROGRESS)

## Objective
Make Instagram a LIVE publish platform in the daemon. Currently `instagram` is
`export_only` in `social_publisher.py` (PLATFORM_ACTIONS line 30) and NOT in
server env `ABVORN_SOCIAL_PLATFORMS` (currently `linkedin,telegram`).

## Probes completed & verified on server (all success)
- Composition connection live: `ca_ka7Uskzv1Gbr`, toolkit `instagram`, version `20260819_00`, user `pg-test-3b737671-fa87-440b-91ae-a98f263aa7c3`, scopes business_basic + content_publish.
- `INSTAGRAM_GET_USER_INFO` resolves numeric ig_user_id: **`28336534789264284`** (username `abvorn`, name `Abvorn_HQ`, `account_type: MEDIA_CREATOR`). CREATE_POST REQUIRES numeric string (rejects "me").
- `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` schema: fields `ig_user_id` (required), `caption` (<=2200), `children` (creation_ids), `child_image_urls` (public URLs only), **`child_image_files`** = array of FileUploadable `{name, mimetype, s3key}` — THIS is the local-image path. Also `child_video_urls`/`child_video_files`. `share_to_feed` boolean.
- `INSTAGRAM_CREATE_POST` schema: `ig_user_id` (required, numeric), `creation_id` (required, container id).
- Upload mechanics: `FileUploadable.from_path(client=c.client, file=<path>, tool="INSTAGRAM_CREATE_CAROUSEL_CONTAINER", toolkit="instagram", sensitive_file_upload_protection=False).model_dump()` → `{name, mimetype, s3key}`. Signature confirmed server site-packages `_files.py:561`.
- Container creation round-trip tested live (draft only, never published): container `18150776803529433`.

## Code changes made (uncommitted, local workspace)
- `abvorn/deploy/composio_client.py`: added constants
  `INSTAGRAM_TOOLKIT`, `INSTAGRAM_GET_USER_INFO_TOOL`, `INSTAGRAM_CAROUSEL_CONTAINER_TOOL`, `INSTAGRAM_CREATE_POST_TOOL`
  right after `LINKEDIN_MY_INFO_TOOL`. (Real implementation of methods NOT yet added.)

## Next steps (resume here)
1. `composio_client.py`: add `instagram_user_id()` (env override `INSTAGRAM_USER_ID` else GET_USER_INFO) + `instagram_publish_carousel(caption, image_paths)` (resize→1080x1080, upload each via FileUploadable.from_path using `client=self.client.client`? — NOTE: `self.client` is the Composio() instance, HttpClient is `self.client.client`).
2. `social_publisher.py`: un-export-only instagram; add live flow using new client method (honest caption from slides script via `_has_false_testing_claim`/`_honest_text` guard — import from `abvorn.platform.adapters`), fallback to `_export` on any failure or <2 images; `publish()` already takes `media_paths`; `publish_all()` must pass them through.
3. `orchestrator.py`: `run_cycle` calls `publisher.publish_all(publish_targets, target["niche"])` at line 190 — must pass `media_paths` (and optionally url) so IG gets images. Script for instagram (list form) is built by `_carousel_script` in viral_script_generator.py.
4. Local tests (pytest) — keep `tests/test_social.py` etc. green; add a montestable path for honest captions.
5. Deploy via bundle-over-scp, verify daemon, then set server env `ABVORN_SOCIAL_PLATFORMS=linkedin,telegram,instagram`.
6. Live test a real IG carousel post with 2 local images (or do container-only first), then confirm daemon logs IG post.
7. Cleanup server: `probe_ig17.py`, `probe_ig18.py`, `/tmp/grep_igslugs.py`, `/tmp/ig_schemas.py`, `/tmp/ig_fields.py`.

## Important facts to remember
- Local machine: PowerShell only (no grep/tail), github.com blocked via proxy `127.0.0.1:443`; sync via `git bundle` → scp → remote fetch. Server repo at marker `b911a6c`, daemon healthy.
- Image requirements: JPEG, aspect 4:5–1.91:1, width 320–1440px, <=8MB. Carousel needs 2-10 children. CinematicFilter has instagram size `(1080,1080)` at line 132. Server Python 3.10, local 3.14 — avoid f-string `\` in expressions.
- Honesty directive: never claim physically buying/testing; `_FALSE_CLAIM_MARKER` regex in `abvorn/platform/adapters.py:51`.
- `git reset --hard` hazard in sync-runtime.sh only if docs/ not committed (they are now).
---

# Session Log — 2026-09-08 — LinkedIn bare-link posts fixed + deployed

## Bug (user-reported)
"The last 3 posts only had the abvorn link in it and nothing written."

## Root cause (verified chain, no speculation)
1. `docs/feed.xml` items carry NO `<description>` — `write_site_metadata` (src/deployment.py ~2916) emits only title/link/guid/pubDate; run_cycle.py passes only title/slug/date.
2. `ContentIntelligence.parse()` (domination/content_intelligence.py:71) → `summary = entry.summary or entry.description` = `""` for every entry.
3. `ViralScriptGenerator._linkedin_script` (domination/viral_script_generator.py:163) → body built from empty summary → `body = ""`.
4. `SocialPublisher.publish()` → `_linkedin_params` (domination/social_publisher.py:52): commentary resolves `post`→`commentary`→`body`→`_extract_text` = `""`, BUT `url` is present → fires `LINKEDIN_CREATE_ARTICLE_OR_URL_SHARE` with `shareCommentary.text=""` → **LinkedIn post = bare link, zero text**.
- Affected every domination cycle (4h cadence) once feed path was fixed; last 3 posts all bare.

## Fix — local commit `a1bf74e`, server `b4e8c551`
- `social_publisher.py` `_linkedin_params`: commentary never empty on a URL share — strip, then fall back to `headline`/`title`, then a neutral default ("After comparing real specs, prices, and owner feedback across the top options, here's what stands out."). Live-platform guard (belt).
- `viral_script_generator.py` `_linkedin_script`: when summary is empty, build body from the hook + neutral research line (fixes the real generator, so ALL domination LinkedIn posts carry written content) (braces).
- `tests/test_social_publisher.py`: 6 tests (empty-body+url non-empty commentary, neutral default, URL-share args non-empty shareCommentary, empty-summary script body fallback, summary preserved when present, _extract_text).
- Gates: 24 passed (6 new + 18 test_social.py); check_publish_content OK (195 files).
- Deploy: format-patch → scp → `git am` (server `b4e8c551`) → `git push origin main` (`34b4a997..b4e8c551`) → `sync-runtime.sh` (import canary OK, daemon restarted 23:53:55Z, active). `.deployed_commit` = `b4e8c5514953b3dacf2e60e63aeb19ef567986f9`. Verified flat runtime files contain both fixes.
- End-to-end vs live feed (`docs/feed.xml`, 144 entries): every top-10 post now yields non-empty LinkedIn commentary (body_len 180-214, commentary matches).

## Facts for future
- Server SSH key is `~/.ssh/id_ed25519` (NOT `abvorn_oracle`). Host `ubuntu@92.4.157.87`, server clock is UTC (commit times +0800).
- Deploy marker `/.deployed_commit` shows server-side HEAD; flat runtime verified via `grep` on `/opt/abvorn-core/abvorn/domination/...`.
- Feed has NO descriptions by design — domination summary is always empty; any fix depending on it must have a fallback (e.g. LinkedIn body from hook).
- `sync-runtime.sh` compares `FETCH_HEAD` to the marker, so pushing origin first then syncing works as a single-step deploy.

---

# Session Log — 2026-09-08 — Health audit fixes: suite green 773/0

## Objective
After the health dashboard (measured 8.8/10, but the suite could never go
green: 18 fails + one deadlock), fix every failure cluster and tooling gap so
`pytest` is a usable pre-deploy gate. No content-generation changes.

## Root causes + fixes
1. **CI deadlock** — `tests/daemon_test.py` hung the whole suite. Chain:
   `OptimizationDaemon.run_cycle()` → `refresh_brain_if_needed()` → real
   `refresh_brain()` scanned the 292-PDF local corpus and pypdf entered an
   **infinite broken-xref reconstruction loop** on
   `LinkedIn - 60 Days to LinkedIn Mastery` (repeated "Object 861 0 not defined /
   Overwriting cache"). Would also stall a fresh production
   `get_brain_retriever()` (when `brain_index.db` is absent).
   - Fix A (tests hermetic): `tests/daemon_test.py` injects a no-op
     `brain_refresher`; `run_cycle` never touches disk.
   - Fix B (product hardening): `abvorn/brain/scanner.py` `extract_text()` is now
     wall-clock bounded (45s) via a worker thread + in-process failure skip set
     (`_EXTRACT_FAILURES`), so one pathological PDF cannot block a refresh.
     New `tests/test_brain_extract.py` (3 tests).
2. **uix phantom API (10 fails)** — `TestEngagementState` tested an engagement
   API that didn't exist. Implemented on `AbvornState` (documented-but-unbuilt;
   daemon.py report already referenced `get_engagement_summary`): new tables
   `engagement_likes/shares/comments` + `add_like/remove_like/has_liked/
   get_likes/track_share/get_total_shares/add_comment/get_comments/
   moderate_comment/get_engagement_summary`.
3. **notifier drift (4 fails)** — `TelegramNotifier(token="", chat_id="")`
   auto-loads real secrets (local secrets exist), so the "no creds" tests were
   REALLY SENDING to Telegram and returning True. Tests now mock
   `load_secrets`; `__init__` semantics unchanged for production callers.
4. **exploder drift (2 fails)** — test ANCHOR declared "After **testing** 20+
   pairs …" which the honest-copy filter (`_FALSE_CLAIM_MARKER`) correctly
   strips → bodies ~90 chars. Fixture rewritten to honest copy (alternating
   "compared specs, prices, and owner feedback").
5. **n8n stale endpoint (1 fail)** — `abvorn-video-render.json` hardcoded
   `http://127.0.0.1:8080` (MPT). Pinned to `http://92.4.157.87:8080` (Oracle)
   — works on n8n Cloud where `$env` is blocked. Test allows the pinned base.
6. **flaky cost test** — `get_unified_db()` cached the singleton forever, so
   `ABVORN_DB_PATH` isolation in `test_cost_and_revenue` was ignored after the
   first use. Now keyed on the current env path.

## Tooling
- `pytest-timeout` 2.4.0 installed + `addopts = ["--timeout=180"]` in
  `pyproject.toml` — a future hang fails loudly instead of silently stalling CI.
- Declared `ruff`/`vulture` in dev extras (not installed; next
  `pip install -e .[dev]` brings them).

## Verification
- Full suite: **773 passed, 0 failed in 3:13** (was 770 collected / 18 fail /
  1 deadlock). `python -m compileall` clean. `check_publish_content.py` OK
  (195 files, no mojibake).

## Facts for future
- `OptimizationDaemon` is currently TEST-ONLY (not wired into the live daemon
  loops); the live brain refresh path is `get_brain_retriever()` (skips refresh
  when `brain_index.db` exists).
- Local brain corpus lives in
  `C:\Users\Jean Mare\Downloads\Notebook LM Brain-…\Notebook LM Brain`
  (292 PDFs). One PDF there is corrupt (`60 Days to LinkedIn Mastery`) — now
  capped by the timeout guard.

## Follow-up — GSC ingestion "failed" root-caused
Not a bug: service-account creds exist (server `gsc-credentials.json`, `siteFullUser`
on `https://abvorn-media.github.io/abvorn/`), queries return HTTP 200 — but the site
has essentially **no Search Console data** (0 rows/7d; 4 impressions/30d, 0 clicks,
avg pos 2.75). The old daemon loop passed `days=7` and treated an empty window as a
hard `failed`, so `gsc_last_run` never advanced → perpetual retry + log noise.
- `gsc_ingestor.py`: empty window is now `{"status": "no_data_yet", ...}` (honest,
  not "failed"); real failures (disabled client) still `failed`.
- `daemon.py` `_gsc_loop`: window widened 7→30 days (matches top/opportunity fetches
  and the 2-3 day GSC reporting lag); `gsc_last_run` advances on `success` AND
  `no_data_yet`, so the intended 24h cadence holds instead of a retry loop.
- New `tests/test_gsc_ingestor.py` (3 tests). Verified: 3 pass + daemon_test 20 pass.
- Real fix remains indexing/traffic, not code.