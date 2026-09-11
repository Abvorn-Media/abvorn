# Abvorn Full-System Audit — 2026-09-03

**Scope:** Entire system — win.sh business loops, automation workflows (n8n / CI / evolution), analytics & revenue pipeline, content & links, security posture, secrets hygiene.
**Method:** Reused prior audit (AUDIT_2026-08-31) as baseline, verified which of its findings are now fixed, and re-audited each domain against current source.
**Lens:** Nadella enterprise-AI frameworks (surplus test, feedback loops, trust architecture / secure-by-default).

---

## Executive Verdict

Abvorn remains a **working autonomous content engine with a real, functioning core loop**. Since the 2026-08-31 audit:

- **The three top security/CI findings from the last audit are genuinely FIXED** (fail-closed auth, CI serialization, `git add` scoping). Verified in source, not just commit messages.
- **The win.sh loops subsystem is a hollow scaffold**: 5 loops installed, only 1 (ads-budget-guard) produced any substantive output (one no-op diagnosis on 2026-08-02), and the formal state ledger (all JSONL files) is **completely empty**. Zero loop activity in 32 days.
- **Content/deployment regressed on the `/abvorn/` base-path**: every review page now has broken Compare-button and price-chart references (404), even as the homepage is correct.
- **The surplus test still fails** — revenue remains entirely estimated, and the economic signal in the drive score is **permanently zero** due to a path bug.
- **New source-prefix, RSS, and staleness issues** surfaced in sitemap/feed/llms metadata.

---

## 1. Security (mobile_server.py) — Priority 1 of 4

### Fixed since prior audit (verified in source)
| Prior finding | Status |
|---|---|
| Fail-open `/api/*` when token unset | **FIXED** — middleware is fail-closed: 503 when no token, 401 when wrong token (L65–90) |
| `/api/exec` + `/api/write` exposed | **FIXED by default** — masked (403) unless `ABVORN_ALLOW_EXEC=1`; exec blocklist hardened |
| `/webhook` + CI not serialized, `git add -A` leak | **FIXED** — concurrency group + scoped `git add docs/ data/` |

### Residual / new issues (ranked)

| # | Sev | Finding | Where |
|---|---|---|---|
| **S1** | CRIT | **Entitlements approve/deny are still unauthenticated** (`/api/entitlements/approve`, `/api/entitlements/deny` in `PUBLIC_API_PATHS`) — anyone can approve/deny pending agent actions. Was flagged before, **still unfixed.** | L35–40, L899, L914 |
| **S2** | CRIT | **`_call_ai_subprocess` prompt injection** — user prompt interpolated into a generated Python script; the new `\"`/`\'` escaping is **trivially bypassable** (newlines, triple-quotes, backslashes). Reachable via `/api/chat` without `ABVORN_ALLOW_EXEC`. | L677–703, L710 |
| **S3** | CRIT | **`/api/exec` still `shell=True` + denylist** — a denylist approach to an allowlist problem; bypassable via `powershell -enc`, `cmd /c`, `curl|sh`, `python -c`, base64. Disabled by default, but if ever enabled it's RCE. | L723–752 |
| **S4** | HIGH | **`/webhook/abvorn/{action}` is completely unauthenticated** (not under `/api/`), can trigger publish/evolution/journal-write/GSC ops. | L553 |
| **S5** | HIGH | **`/api/write`** — path-confined to PROJECT_DIR (good) but no blocklist for `.env`/`secrets.json`/`*.py`, no size limit, can poison config or drop executable files. | L782–797 |
| **S6** | MED | Token compared with `!=` (timing attack). Use `hmac.compare_digest`. | L88 |
| **S7** | LOW | Dead code: duplicate `GET /api/price-alerts` (`L378` shadowed by `L844`); unused `import shlex`. | L3, L378, L844 |

**Bottom line:** The previous audit's headline auth issue is fixed, but **two CRITICALs persist** (entitlements auth, prompt injection) and the `/webhook` route is a new blind spot.

---

## 2. win.sh Business Loops — Priority 2 of 4

**Verdict: Hollow scaffold. 1 of 5 loops has any substantive output; the state ledger has never recorded anything.**

### Loop health
| Loop | Journal | Run brief | JSONL state | Verdict |
|---|---|---|---|---|
| ads-budget-guard | 2 entries (1 substantive, 2026-08-02) | 1 (completed no-op) | none | Partially operational |
| conversion-optimizer | 1 stub ("diagnosing") | none | none | Hollow scaffold |
| seo-growth | 2 stubs | none | none | Hollow scaffold |
| feedback-to-fix | 0 | none | none | Dormant |
| traffic-growth-optimizer | 0 | none | none | Dormant |

### Key findings
1. **All 6 JSONL state files are empty** (runs/outcomes/executions/artifacts/artifact-suggestions/approvals = 0 entries). The formal ledger that should record loop activity has never captured anything.
2. **`state.json` frozen at install** — every loop's `updatedAt == installedAt` (all within a 3-sec window 2026-08-01). The persistence layer is never invoked after runs.
3. **Run briefs referenced but missing** — 4 journal entries reference run IDs with no `.win/runs/` file on disk.
4. **32 days of total inactivity** (last journal write 2026-08-02; today 2026-09-03). No scheduled follow-ups ran.
5. **Contracts are excellent but untested** — LOOP.md files are thorough (feedback-to-fix 186 lines, seo-growth 197 lines) with clear authority (`ask_first`), connectors, and verification. None of the machinery has been exercised beyond the one ads no-op.

**Implications:** Either (a) the loops are aspirational and need an actual triggering mechanism (they never fire on their own), or (b) they're expected to run through the agent but nobody has driven them. Recommend: wire a real trigger (scheduler / data event) for at least one loop and prove the full path (brief→execute→journal→JSONL artifact) end-to-end, or treat `.win/` as design docs, not operational automation.

---

## 3. Content, Deployment & Links — Priority 3 of 4

Sitemap/feed/llms metadata **was** fixed structurally by `6a25004` (all writes now flow through `write_checked()` mojibake guard; sitemap emits conditional `<lastmod>`; `llms-full.txt` added; core pages included). A `scripts/check_publish_content.py` run confirms **191 files, zero mojibake** — the encoding guard works. **But:**

| # | Sev | Finding |
|---|---|---|
| **C1** | **ISSUE** | **Broken `/abvorn/` links on review pages.** Every review page references `/abvorn/compare.html` (149 links) and `/abvorn/js/price-charts.js` (150 refs) → **404** (no `docs/abvorn/` dir). The homepage uses correct root paths. **Compare button and price charts are broken on essentially every review page** in the real root-layout deploy (masked locally by `_serve.py` stripping the prefix). Origin: base-path handling differs between legacy cell builders and the current `docs/` layout. |
| **C2** | ISSUE | **`<lastmod>` is a frozen placeholder.** All 147 sitemap entries are `2025-01-01` because `"date": ... if 'datetime' in dir() else "2025-01-01"` — inside a function `dir()` never sees the module-level `datetime` import, so it always falls to the literal. Actual dates never computed. Same bug pollutes RSS `pubDate` (`<pubDate>2025-01-01</pubDate>`). (`deployment.py:3106`, `run_cycle.py:3019`, `deployment.py:2892`) |
| **C3** | ISSUE | **Metadata is stale** — the newest review (`best-wireless-earbuds-2026-09-03`) is absent from `sitemap.xml`, `feed.xml`, `llms.txt`, `llms-full.txt` (committed `95e724c`, metadata last regenerated in `bc0511f`). |
| **C4** | ISSUE | **`cycle_state.json` under-reports reality** — says 89 posts (2026-07-31); actual review articles in `docs/reviews/` = **140**. ~51 articles unaccounted. `last_processed`/`updated_at` stale. |
| **C5** | GAP | **Category & niche index pages omitted from sitemap** (only 7 core + review articles included). |
| **C6** | GAP | **RSS `pubDate` is ISO 8601, not RFC 822** (breaks feed validators/readers). |
| **C7** | LOW | Legacy duplicate sitemap at `var/www/abvorn/sitemap.xml` (129 URLs, 0 lastmod) — stale artifact. |
| **C8** | LOW | **`.gitignore` contains mojibake** (`�?"` in comments) and Telegram message text in workflows is corrupted (`?? <b>`). Cosmetic, but ironic vs. the encoding guard. |

---

## 4. Analytics, Revenue & Cost — Priority 4 of 4

| # | Sev | Finding |
|---|---|---|
| **A1** | **ISSUE** | **Drive-score economic signal is permanently zero.** `abvorn/core/relentless_core.py:28` reads `data/economic_records.json` (doesn't exist); the real file is `data/surplus/economic_records.json` → `surplus=0.0` always, killing the 30%-weight signal. **Path bug.** |
| **A2** | **ISSUE** | **Revenue is 100% estimated** (`config.yaml mode:"estimated"`, 7% × 6% × $50). `economic_records.json` has 6 identical synthetic `$1.05` records. No Amazon affiliate API / reporting integration — real commissions never measured. **Surplus test fails.** |
| **A3** | GAP | **Cost tracking is in-memory only** — `ModelCostTracker` (`abvorn/core/models.py:238`) stores calls in a list (lost on restart), uses a hardcoded `$0.002/1k` flat rate, never persists. `InfrastructureReporter`/`EnergyAccounting` (src/) are also in-memory. Commit `2f313c7 feat(cost)` added computation but **no durable cost log**. |
| **A4** | GAP | **clicks.db is real but empty of real traffic** — 3 test clicks (all `test-niche-0`, 2026-07-31); 260 click_targets populated. Schema + bot filtering are solid; the site just has no organic traffic. Also confirm the `/click/` FastAPI endpoint is actually reachable in the static/Pages deploy. |
| **A5** | OK | **GA4**: consent-gated tag present in deployed pages; measurement ID from env (not hardcoded); slug base-path stripping correct. Legacy cell builders lack the consent gate (dual-path drift). |
| **A6** | OK | **GSC**: fully wired (service account, read-only scope, daily ingest → dashboard/journal/neural memory/API). Add a staleness indicator to the dashboard. |

---

## 5. Secrets & Hygiene

**Good:** `gsc-credentials.json` is **not tracked** (gitignored), `.win/` is gitignored, secrets load from `~/.abvorn/boardroom/secrets.json`/env, API token confirmed fail-closed. `_*.py` scratch scripts are untracked.

**Watch:** the two untracked audit reports (`LEVIE_Audit_Report.md`, `ai-scaling-laws-amodei_audit_report.md`) at repo root plus my own `ai-scaling-laws-amodei_audit_report.md` — decide whether these belong in the repo; currently they'd show as untracked noise.

---

## Prioritized Action List (surplus-test & risk ranked)

| # | Sev | Action |
|---|---|---|
| 1 | CRIT | **Require auth on `/api/entitlements/approve` and `/deny`** (remove from `PUBLIC_API_PATHS`). "Secure by default." |
| 2 | CRIT | **Fix prompt injection in `_call_ai_subprocess`** — pass prompt via stdin/temp file / `json.dumps()`, never string-interpolate into a Python `-c` script. |
| 3 | CRIT | **Lock down `/webhook/abvorn/*`** with a webhook token/signature (currently fully unauthenticated). |
| 4 | HIGH | **Fix `/abvorn/` broken links on review pages** (C1) — the cross-cutting base-path inconsistency is user-visible (dead Compare buttons + price charts) on every review article. |
| 5 | HIGH | **Fix the sitemap/RSS frozen-date bug** (C2) — replace the `'datetime' in dir()` trap with a real date, and emit RFC-822 `pubDate` (C5 style). |
| 6 | HIGH | **Fix the drive-score path bug** (A1) `relentless_core.py:28` → `data/surplus/economic_records.json`. |
| 7 | MED | **Regenerate stale sitemap/feed/llms/llms-full** after the latest review (C3); add category/niche pages to sitemap (C5); refresh `cycle_state.json` to actual 140 articles (C4). |
| 8 | MED | **Persist AI cost** to a `cost_log` table / SQLite with per-provider rates (A3). |
| 9 | MED | **Wire real affiliate revenue** (Amazon API or manual import) so the surplus test can pass (A2). |
| 10 | MED | **Refer to win.sh loops**: prove one loop end-to-end (brief→execute→journal→JSONL artifact) or demote the subsystem to design docs; currently hollow (Section 2). |
| 11 | LOW | Token compare via `hmac.compare_digest` (S6); remove dead price-alerts handler + `shlex` (S7); fix `.gitignore`/Telegram mojibake (C8); GSC staleness indicator (A6); unify GA4 template / base-path function (`abvorn_cell3.py:49`). |

---

## Reconciliation notes
- The `6a25004` "fix(security)" commit **did** implement: fail-closed auth, exec/write masking, CI concurrency lock, scoped `git add`, sitemap `<lastmod>`, `llms-full.txt`, mojibake guard on feed/sitemap, Fable double-execution fix, evolution-counter reset. Those verified. It did **not** fix the entitlements auth bypass (S1) nor the prompt-injection root cause (S2), and the `<lastmod>` values it emits are non-functional placeholders (C2).
- n8n workflows hardcode `127.0.0.1:8080` (mobile server) which is a local-only assumption; if the mobile/backend server is not reachable from the n8n host, those workflows no-op.
