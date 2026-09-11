# Abvorn Full System Audit — 2026-09-11

Skills applied: **health**, **cso**, **gstack-openclaw-retro**, **qa-only**, **design-review** (HTTP-level only), **devex-review**, **autoplan** (n/a).
Scope: repo `main` @ `99d8c9b` (deployed `954a9022` on VPS), prod VPS `92.4.157.87`, live site `https://abvorn.com` (GitHub Pages).

---

## Verdict

**Healthy system.** 828/828 tests pass, live site fully 200, no mojibake, strong secret hygiene and a minimal public attack surface. Issues are bounded: 3 dependency-CVE groups, one embedded PAT in a server-side git remote, SSH password auth left on default, no JSON-LD, no CI test/lint gate. **Weighted score ~8.1/10.**

---

## 1. Health — 8.2/10

| Metric | Result |
|---|---|
| Tests | **828 passed, 0 failed** in 148s (`pytest tests -q --timeout=180`) |
| Focused suites | 55/55 (encoding_guard, daemon_test, test_models) |
| Lines | abvorn 22,712 / tests 7,976 (~35% test ratio) |
| Lint (pyflakes-level) | 147 findings: F401 unused-import 103, F541 empty-fstring 24, F841 unused-var 20; 127 auto-fixable |
| Lint (full default set) | 1350 findings, 575 auto-fixable (no ruff config → style noise) |
| Dead code (vulture ≥70%) | 11 unused imports/vars only; **no dead classes/modules** |
| Silent exception swallow | 37 (30× try/except:pass, 6× except:continue, 1× bare except) — in `agents`, `core`, `domination` |

Positives: excellent green suite for a 22.7k-LOC autonomous system; dead code essentially nil.
Gaps: no `ruff`/`vulture` installed in the tracked venv (gates don't run out of the box); no CI lint/test gate (workflows only build/publish); 37 silently-swallowed exceptions hide real failures.

## 2. CSO — 7.8/10

### Strengths (verified)
- **Git history clean**: 682 commits — no `.env`, no secrets files, no GSC credentials ever committed; tracked-tree secret-pattern scan clean (only a placeholder `ghp_xxx` in `.env.example`).
- **Local repo remote clean**; secret files correctly gitignored: `.env`, `gsc-credentials.json`, `*.db`, `*.log`, `_*.py`, `_shot_*.png`.
- **Prod file perms**: `/opt/abvorn-core/.env` and `~/.abvorn/boardroom/secrets.json` both `0600`.
- **Attack surface minimal**: public = 22/80/443 only. `n8n` (5678/5679), brain (8081), mobile (8080/8090) all **localhost-bound**; only `/click/` and `/api/evolution/` proxy out via nginx.
- **nginx hardened**: TLS via Certbot, HSTS/nosniff/XFO/CSP headers, `deny` for `.git`/`.md`/`.pyc`, gzip.
- `/brain/` and `/api/evolution/` return `401 Unauthorized` without the bearer token (`ABVORN_API_TOKEN` set in `.env`).
- `fail2ban` active; `unattended-upgrades` active; daemon runs as unprivileged `ubuntu`; health: no debug listeners bound to `0.0.0.0`.

### Findings
| Sev | Finding |
|---|---|
| **HIGH** | **11 known CVEs in dependencies** (`pip-audit`): `weasyprint==62.3` ×3 (PYSEC-2026-2034/3412/3940, fix 68/70 — upgrade blocked by the `pydyf==0.10.0` pin workaround), `chromadb 1.5.9` ×5, `nltk 3.10.3` ×1. Versions reflect local install of the same pinned `requirements.txt`. |
| **MED** | **GitHub PAT embedded** in `/opt/abvorn-core/repo-src/.git/config` origin URL (`ghp_…`), file `0664` group-readable. Rotate to a fine-grained token or SSH deploy key. |
| **MED** | **SSH `PasswordAuthentication` left at default (yes)** and **no ufw** (only `fail2ban`). Enable ufw (22/80/443) and set `PasswordAuthentication no`. |
| **LOW** | Daemon unit has no service hardening (`ProtectSystem`, `NoNewPrivileges`, `PrivateTmp` absent). Runs as non-root — acceptable; add flags opportunistically. |
| **LOW** | `n8n 2.8.4` runs a history of n8n RCE CVEs; not exposed publicly — keep it that way, monitor. Single shared `ubuntu` user for all 4 services (no isolation). |
| **LOW** | VPS nginx serves a **stale docroot** (`/var/www/abvorn/docs` → 404 on `/`), superseded by GitHub Pages anyway. Either point DNS at it or retire the copy. |

## 3. Retro — 7-day window

- **Velocity**: 72 commits (682 total). All agent-driven: `Abvorn` 70, `Abvorn Bot` 1, `Abvorn Daemon` 1.
- **Burst (Sep 10)**: 14 consecutive `router`+`daemon` resilience fixes — groq TPD classification, 429-vs-quota split, per-provider call serialization + min 2s gap, verify-providers-at-startup, NIM providers, 12h cadence, full-cycle no-crash fixes, heartbeat boot-race fix.
- **Hotspots**: `abvorn/core/models.py` (9), `abvorn/daemon.py` (11), `abvorn/deploy/social.py` (7), `abvorn/domination/social_publisher.py` (7), `run_cycle.py` (7), `src/deployment.py` (6).
- **Praise**: 828 green after the 14-fix spree; deployed commit == head commit; unattended overnight cycle succeeded (00:49 UTC, article `f915cf52`).
- **Concern**: reliability logic is concentrated in `models.py`+`daemon.py` — the load-bearing pair. Guard them with more focused router/daemon tests.

## 4. QA-only (live site, HTTP-level)

- **151/151 sitemap URLs → 200**. Homepage, categories, guides, reviews, assets all serve.
- **No mojibake**: `check_publish_content.py` — 195 files, 0 (`EXIT 0`). (An earlier regex "flag" was a false positive; en-dashes are correct typography.)
- Titles, meta descriptions, viewport, og:image, Google Fonts all present. Page weights ~75–110 KB — reasonable.
- **Issues**: `application/ld+json` blocks on homepage = **0** (no Organization/Article/Product/FAQ schema — SEO gap, affiliate-critical); raw `/favicon.ico` → 404 (cosmetic; declared `favicon-32x32.png` works); two near-duplicate content pairs ("Best …" vs "Ultimate … Guide") worth de-duplicating for search intent.
- **Constraint**: visual/design review not run — gstack `browse` binary exists but the headless browse daemon isn't provisioned on this Windows host; only HTTP-level QA executed.

## 5. Devex — 7/10

- `pyproject.toml` declares pytest/ruff/vulture + `--timeout=180`; but the tracked venv lacks `ruff`/`vulture`, so gates fail until `pip install -e .[dev]`.
- No CI test/lint gate — regressions reach prod unchecked (would have caught e.g. the mojibake incident class earlier).
- Good docs: `AGENTS.md` (mojibake guard + win loops), `CLAUDE.md`, README; one-command `run.bat`/`run_cycle.py`/`run_daemon.py`.
- Noise: ~40 gitignored scratch `_*.py`/`_shot_*.png` at repo root, 3 `pytest_*.log`; generated `docs/` churn (index.html touched 269×) buries the history signal.

## 6. Autoplan

Not applicable — post-hoc audit, no forward plan gate requested.

---

## Top recommendations

1. **CSO-HIGH**: Bump `weasyprint` to ≥68 (reconcile the `pydyf` pin), upgrade `chromadb`, patch/replace `nltk`; run `pip-audit` in CI.
2. **CSO-MED**: Replace the server-side `ghp_…` PAT with a fine-grained token or SSH deploy key; `git remote set-url`.
3. **CSO-MED**: `ufw allow 22,80,443/tcp` + `PasswordAuthentication no`.
4. **HEALTH/DX**: Add a CI workflow running `ruff check abvorn --select F,E9` and `pytest tests`.
5. **SEO**: Emit JSON-LD (`Organization` on home, `Article` on reviews, `Product`/`FAQPage` where applicable) from `src/deployment.py`.
6. **CSO-LOW**: Add `ProtectSystem=strict`, `NoNewPrivileges`, `PrivateTmp` to the daemon unit; retire the stale VPS nginx docroot (or point DNS at it).

*Scores: health 8.2, cso 7.8, devex 7.0, qa-only pass w/ notes. Weighted ~8.1/10. Full evidence re-runnable via commands noted inline.*

---

## Update — 2026-09-11 (same-day fixes + corrections)

### Audit corrections (verified ON the VPS, overrides the rows above)
- **`PasswordAuthentication` was already `no`** — the audit's "left at default (yes)" was wrong. It was disabled via `60-cloudimg-settings.conf`. Now also enforced explicitly (below).
- **`ufw` was already active** (default deny incoming, `22/tcp` allowed) — the audit's "no ufw" was wrong. `80/tcp` and `443/tcp` have now been explicitly added.

### CSO / hardening — applied on prod VPS `92.4.157.87`
| # | Fix | Status |
|---|---|---|
| A1 | Daemon unit hardened: `/etc/systemd/system/abvorn-daemon.service.d/override.conf` (`NoNewPrivileges=yes`, `ProtectSystem=full`, `PrivateTmp=yes`, `RestrictSUIDSGID=yes`, `ProtectKernelModules=yes`, `ProtectClock=yes`); daemon restarted, active, resumed processing | **DONE** |
| A2 | `ufw allow 80/tcp` + `ufw allow 443/tcp` (22 already allowed); verified rules v4+v6, default deny incoming | **DONE** |
| A3 | `/etc/ssh/sshd_config.d/99-hardening.conf`: `PasswordAuthentication no`, `KbdInteractiveAuthentication no`; `sshd -t` OK, reloaded, connect verified | **DONE** |
| A4 | Repo git config `chmod 600`; PAT-rotation helper `/opt/abvorn-core/rotate_origin.sh` (700) written | **DONE** (rotation blocked on a new fine-grained token from maintainer) |
| A5 | Retire stale VPS nginx docroot (`/var/www/abvorn/docs`) | **PENDING** |

### Dependency + repo — applied locally
| # | Fix | Status |
|---|---|---|
| B1 | `requirements.txt`: `weasyprint==62.3` + `pydyf==0.10.0` pin → `weasyprint==70.0` (3 CVEs cleared); installed locally; 828/828 tests pass | **DONE** |
| B2 | CI gate added: `.github/workflows/ci.yml` — `ruff check .` (F/E9), `pytest tests`, `pip-audit -r requirements.txt` (continue-on-error) | **DONE** |
| B3 | JSON-LD on homepage: `Organization` + `WebSite` `@graph` injected into `HOMEPAGE_TEMPLATE` (`src/deployment.py:3773`); smoke-validated (JSON parses, tokens resolve to `https://abvorn.com/`) | **DONE** |
| B4 | Lint cleanup repo-wide: 127 F401/F541 auto-fixed, ~40 F841 `_`-prefixed, 4 latent **F821 NameErrors fixed** (`CONTENT_TYPE_MAP` in `content_generation.py`, `DAG`/`Task` import in `run_cycle.py`, `html_mod` in `price_alerts.py`, `_first_structural` in `rebuild_reviews.py`); duplicate `OG_META` def removed (`src/deployment.py:917`); `ruff check .` green (F/E9) | **DONE** |

### Remaining / blocked
- **chromadb 1.5.9 ×5 CVEs — no fixed release** (1.5.9 is latest); monitor upstream.
- **nltk 3.10.3 ×1 CVE — no fixed version**; transitive, never pinned; wait/swap.
- **PAT rotation** blocked on maintainer generating a fine-grained token → `/opt/abvorn-core/rotate_origin.sh <token>`.
- Recommend a focused router/daemon test spree (`abvorn/core/models.py` + `abvorn/daemon.py`) to harden the load-bearing pair (retro concern).
- B-series changes not yet committed to `main` nor deployed (requirements bump needs `pip install -r requirements.txt` in the prod venv + daemon restart).