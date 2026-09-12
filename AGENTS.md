<!-- win-loops:start -->
## win.sh Loops

This repo has win.sh business loops installed. The most recently installed loop is `ads-budget-guard`.

- Loop contracts and journals live in `.win/loops/<loop-id>/`.
- Run briefs live in `.win/runs/` and are the source of truth for the next agent task.
- Codex project skills live in `.agents/skills/win-<loop-id>/SKILL.md`.
- Claude Code project skills live in `.claude/skills/win-<loop-id>/SKILL.md`.
- Use `win status --repo .`, `win inbox --repo .`, and `win next --repo .` to inspect loop state.
- Execute only the run brief selected by `win next --repo .`; stay within the authority rules in `.win/loops/<loop-id>/LOOP.md`.
- Record proof with `win artifact attach` or accept detected proof with `win artifact accept` after execution.
<!-- win-loops:end -->

### Loop triggers

Loops never fire on their own — a data -> signal bridge must create a run brief.
`scripts/win_trigger.py` is that bridge for `seo-growth`: it reads
`data/gsc_latest_summary.json` and only runs `win run seo-growth
--trigger signal` when the loop's minimum-evidence threshold is crossed
(>=100 impressions or >=20 clicks over the window). It skips when evidence is
below threshold or a run is already pending, so daily runs produce no spam.

- Scheduled daily at 08:30 via Windows Task Scheduler task `Abvorn Win Trigger`
  (`scripts/win_trigger.cmd`).
- Also fired after a successful GSC ingest from the daemon
  (`abvorn/daemon.py::_win_trigger_check`).
- All signals must be **ASCII-only**: non-ASCII characters passed through the
  Windows ANSI codepage get double-encoded to mojibake in the win.sh JSONL
  ledgers (same failure mode as the published pages).

## Publishing: always check generated content before commit

Mojibake (double-encoded UTF-8, e.g. `â€"` instead of `—`) has shipped to the
live site before. The corruption comes from reading/writing generated pages
through the Windows ANSI codepage. Guard against it before every publish:

1. **Build pages** via `python run_cycle.py` / `rebuild_site.py`. Every page
   write goes through `write_checked()` in `src/deployment.py`, which runs
   `check_encoding()` and raises `ValueError` if mojibake is detected — a bad
   build fails before it can be committed.
2. **Scan the whole tree before commit**:
   `python scripts/check_publish_content.py`
   - Exit code 0 = clean; exit code 1 = mojibake found (list printed).
   - `--fix` auto-repairs the two known codec-fallback variants.
   - `--path <file>` scans a single file.
3. **Tests**: `python -m pytest tests/test_encoding_guard.py -q` covers the
   detector, the repair path, and the `verify_page` block.

Diagnosis recap (for future mojibake): UTF-8 bytes decoded as cp1252 then
re-encoded as UTF-8. `find_mojibake()`/`repair_mojibake()` in
`src/deployment.py` reverse it; the corruption entered the tree at commit
`536f0d8` via a Windows regen and was repaired tree-wide in `1919d8c`.

## Skill routing

When a task matches one of these domains, load the corresponding skill
before starting work — not after hitting a wall.

| Domain | Skill to load | Trigger |
|--------|--------------|---------|
| Bug investigation / errors | `investigate` | "it broke", "why is this", error in console |
| UI / frontend design | `impeccable` or `frontend-design` | building or redesigning pages, components, layouts |
| Security audit | `cso` | "is this secure?", before deploy to production |
| Content / copy | `brand-voice` + `content-engine` | writing any Abvorn content, product pages, blog posts |
| QA / visual QA | `qa` | "does this work?", "test the site" |
| Scraping / data pull | `scrape` | extracting data from a web page |
| Ship / release | `ship` | ready to commit + push + open PR |
| Email sequences | `emails` | drip campaigns, nurture flows |
| SEO optimization | `ai-seo` | getting cited by LLMs, appearing in AI search |
| Programmatic pages | `programmatic-seo` | generating many similar pages from templates |
| Benchmarking | `benchmark` | measuring page performance, regression checks |
| Design review | `design-review` | visual audit, spacing, hierarchy check |
| Retro | `retro` | weekly engineering retrospective |

Browse is available (daemon provisioned 2026-09-12). Browse-dependent
skills (`qa`, `scrape`, `hackernews-frontpage`, `canary`) are operational.
