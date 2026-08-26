# Changelog

All notable changes to Abvorn are documented here.

## [14.0.0] — 2026-08-26

### Added
- Entitlements system: permission gate (READ/WRITE/DEPLOY/EVADE/TERMINATE) with approval queue and audit trail.
- Genesis Protocol requires operator approval before spawning child agents.
- Reflection-to-pipeline feedback loop: past learnings injected into writer prompts.
- Surplus metrics endpoint (`/api/surplus`) and entitlements API (`/api/entitlements/*`).
- `pyproject.toml` for proper packaging and `pip install -e .`.
- CLI flags: `--help`, `--version`, `--dry-run`.
- `README.md` and `.env.example`.

### Fixed
- GSC Analysis workflow: Code node v2 (`jsCode`, `runOnceForAllItems`), Sheet node `resource: "sheet"`, `sheetName` as ResourceLocator, autoMap columns.
- Normalize node restored with correct `jsCode` and `mode` after DB sync.
- n8n bridge lazy env reads (no crash on missing secrets).

### Changed
- Writer agent (`abvorn/agents/writer.py`) now receives reflection learnings and injects them into outline and draft prompts.
- Content pipeline (`abvorn/content/pipeline.py`) loads learnings from reflection store into brain context.
- Mobile server port default changed to 8090; `ABVORN_SERVER_PORT` env override added.

## [13.0.0] — 2026-07-28

### Added
- Multi-site architecture with brand engine and cross-linker.
- Content persuasion factory (buying-stage detector, product matcher, widget).
- Telegram command interface (20+ commands).
- GA4 analytics integration.
- Daemon mode with kill switch (`/pause`, `/resume`).
- 24 test suite.

### Changed
- Full rewrite from notebook cells (v12) to modular Python package (v13).
